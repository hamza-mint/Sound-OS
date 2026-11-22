"""Regression tests for hardening fixes (executor, safety, confirmation, STT helper).
Run: pytest -q tests/test_hardening.py
"""
import typing
from types import SimpleNamespace

import numpy as np
import pytest

from executor import actions, execute, _find_app, _resolve_folder
from intent_parser import parse_yes_no
from safety.safety_layer import SafetyLayer


# ---------------------------------------------------------------- executor
def test_actions_module_annotations_resolve():
    """`Optional` was used but never imported: harmless on Python 3.14 (lazy annotations) but it
    crashed `import executor.actions` on 3.12 = Xubuntu 24.04. get_type_hints forces the check."""
    typing.get_type_hints(actions)


@pytest.mark.parametrize("name", ["../../bin/sh", "/usr/bin/id", "--help", "rm -rf", "a b", "x;y", "", "A" * 80])
def test_executor_refuses_names_that_are_not_plain_program_names(name):
    assert _find_app(name) is None
    assert execute({"intent": "open_app", "params": {"app": name}, "lang": "en"})["success"] is False


def test_executor_still_resolves_known_and_plain_names():
    assert _find_app("firefox")[0] == "firefox"
    assert _find_app("telegram")[0] == "telegram"        # allowlisted, not in apps.json: plain-name fallback


@pytest.mark.parametrize("folder", ["../../etc", "/etc", "~root", "a/b", "..\\x"])
def test_open_folder_refuses_paths_that_climb_out_of_home(folder):
    assert _resolve_folder(folder) == ""
    out = execute({"intent": "open_folder", "params": {"folder": folder}, "lang": "en"})
    assert out["success"] is False


def test_open_folder_known_and_custom_names_still_work(monkeypatch):
    monkeypatch.setenv("SOUNDOS_DRY_RUN", "1")
    assert _resolve_folder("downloads")
    assert _resolve_folder("MyProjects") == "~/MyProjects"
    assert execute({"intent": "open_folder", "params": {"folder": "downloads"}, "lang": "en"})["success"] is True


def test_close_current_reports_failure_when_nothing_was_closed(monkeypatch):
    monkeypatch.setattr(actions.shutil, "which", lambda name: None)
    monkeypatch.setattr(actions, "_last_launched_process", None)
    ok, msg = actions.terminate_app({"process": "current"})
    assert ok is False and "No window" in msg


# ------------------------------------------------------- confirmation words
@pytest.mark.parametrize("answer", [
    "ايوه", "yes", "نعم اكيد", "yes go ahead",
])
def test_short_answers_confirm(answer):
    assert parse_yes_no(answer) is True


@pytest.mark.parametrize("garbled", [
    "افتح المتصفح علي الصوت وطي السطوع ok",
    "the weather today is very nice and the answer is yes",
    "ايضا افتح الترمينال صح وطي الاضاءه",
])
def test_long_transcript_never_confirms_a_dangerous_action(garbled):
    assert parse_yes_no(garbled) is None


def test_safety_layer_rejects_long_confirmation():
    layer = SafetyLayer()
    cmd = {"intent": "shutdown", "params": {}, "lang": "en", "raw_text": "shut down", "confidence": 1.0}
    res = layer.check(cmd, listen_yes_no_fn=lambda timeout: "blah blah blah blah blah yes")
    assert res["decision"] == "block"
    res = SafetyLayer().check(cmd, listen_yes_no_fn=lambda timeout: "yes")
    assert res["decision"] == "allow"


# -------------------------------------------------------------- stt helper
def test_last_candidates_is_filled_for_run_live():
    from stt import SpeechToText
    from stt.tests.test_stt import make_stt, StubModel
    t = np.arange(16000) / 16000
    audio = np.concatenate([np.zeros(8000), 0.3 * np.sin(2 * np.pi * 200 * t), np.zeros(8000)]).astype(np.float32)
    model = StubModel([("افتح المتصفح", "ar", [("ar", 0.9), ("en", 0.1)])])
    stt = make_stt(model)
    text, lang = stt.transcribe(audio)
    assert text == "افتح المتصفح" and lang == "ar"
    assert stt.last_candidates == [{"lang": "ar", "text": "افتح المتصفح", "score": 0.9}]


# ------------------------------------------------- folders open in a FILE MANAGER
class _Mime:
    def __init__(self, handler):
        self.stdout = handler


def _fm_env(monkeypatch, handler, installed, desktop=""):
    monkeypatch.delenv("SOUNDOS_FILE_MANAGER", raising=False)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
    monkeypatch.setattr(actions.subprocess, "run", lambda *a, **k: _Mime(handler))
    monkeypatch.setattr(actions.shutil, "which", lambda n: f"/usr/bin/{n}" if n in installed else None)


def test_folder_is_not_opened_by_an_editor_that_hijacked_inode_directory(monkeypatch):
    """Real bug: xdg-mime said antigravity.desktop (an editor) handles folders, so 'open downloads' opened it."""
    _fm_env(monkeypatch, "antigravity.desktop\n", {"xdg-open", "dolphin", "thunar"}, desktop="KDE")
    assert actions._file_manager_cmd("/x") == ["dolphin", "/x"]
    _fm_env(monkeypatch, "antigravity.desktop\n", {"xdg-open", "dolphin", "thunar"}, desktop="XFCE")
    assert actions._file_manager_cmd("/x") == ["thunar", "/x"]


def test_xdg_open_is_still_used_when_the_default_handler_is_a_file_manager(monkeypatch):
    _fm_env(monkeypatch, "org.kde.dolphin.desktop\n", {"xdg-open", "dolphin"})
    assert actions._file_manager_cmd("/x") == ["xdg-open", "/x"]
    _fm_env(monkeypatch, "thunar.desktop\n", {"xdg-open", "thunar"})
    assert actions._file_manager_cmd("/x") == ["xdg-open", "/x"]


def test_file_manager_can_be_forced_and_has_a_last_resort(monkeypatch):
    _fm_env(monkeypatch, "code.desktop\n", {"xdg-open", "dolphin", "pcmanfm"})
    monkeypatch.setenv("SOUNDOS_FILE_MANAGER", "pcmanfm")
    assert actions._file_manager_cmd("/x") == ["pcmanfm", "/x"]
    _fm_env(monkeypatch, "code.desktop\n", {"xdg-open"})
    assert actions._file_manager_cmd("/x") == ["xdg-open", "/x"]       # nothing else installed


def test_open_files_app_uses_the_file_manager_helper(monkeypatch):
    seen = []
    monkeypatch.setattr(actions, "open_directory", lambda p: seen.append(p) or (True, "ok"))
    out = execute({"intent": "open_app", "params": {"app": "files"}, "lang": "en"})
    assert out["success"] is True and seen == ["~"]
