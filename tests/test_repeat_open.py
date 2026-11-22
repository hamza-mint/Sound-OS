"""'I said close the browser and it OPENED again' (Whisper hears اقفل as افتح).
Opening an app we opened a moment ago asks once: yes -> close, no -> open again, silence -> nothing.
Run: pytest -q tests/test_repeat_open.py
"""
import time

import pytest

import main as sm
from stt.stt import _beam_size


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    sm._RECENT_OPEN.clear()
    monkeypatch.setenv("SOUNDOS_DRY_RUN", "1")
    monkeypatch.delenv("SOUNDOS_REPEAT_CHECK", raising=False)
    monkeypatch.setattr(sm, "speak", lambda *a, **k: None)
    monkeypatch.setattr(sm, "notify", lambda *a, **k: None)
    yield
    sm._RECENT_OPEN.clear()


OPEN_FF = {"intent": "open_app", "params": {"app": "firefox"}, "lang": "ar"}


def asker(answer, calls):
    def ask():
        calls.append(1)
        return answer
    return ask


def test_first_open_is_never_questioned():
    calls = []
    assert sm._check_repeat_open(dict(OPEN_FF), asker("yes", calls)) == (OPEN_FF, False) and calls == []


def test_same_app_again_asks_and_yes_means_close():
    calls = []
    sm._remember_result(OPEN_FF, True)
    parsed, skip = sm._check_repeat_open(dict(OPEN_FF), asker("ايوه", calls))
    assert calls == [1] and skip is False and parsed["intent"] == "close_app" and parsed["params"] == {"app": "firefox"}


def test_no_means_open_it_again_as_asked():
    sm._remember_result(OPEN_FF, True)
    parsed, skip = sm._check_repeat_open(dict(OPEN_FF), asker("لا", []))
    assert parsed["intent"] == "open_app" and skip is False


@pytest.mark.parametrize("answer", ["", "blah blah", None, "ممكن"])
def test_no_clear_answer_does_nothing(answer):
    sm._remember_result(OPEN_FF, True)
    parsed, skip = sm._check_repeat_open(dict(OPEN_FF), asker(answer, []))
    assert skip is True


def test_other_app_or_old_open_or_close_in_between_are_not_questioned():
    calls = []
    sm._remember_result(OPEN_FF, True)
    other = {"intent": "open_app", "params": {"app": "calculator"}}
    assert sm._check_repeat_open(dict(other), asker("yes", calls))[1] is False and calls == []
    sm._RECENT_OPEN["firefox"] = time.monotonic() - sm.REPEAT_WINDOW_SEC - 1          # a minute ago
    assert sm._check_repeat_open(dict(OPEN_FF), asker("yes", calls)) == (OPEN_FF, False) and calls == []
    sm._remember_result(OPEN_FF, True)
    sm._remember_result({"intent": "close_app", "params": {"app": "firefox"}}, True)   # closed meanwhile
    assert sm._check_repeat_open(dict(OPEN_FF), asker("yes", calls)) == (OPEN_FF, False) and calls == []


def test_failed_open_is_not_remembered_and_the_check_can_be_disabled(monkeypatch):
    sm._remember_result(OPEN_FF, False)
    assert "firefox" not in sm._RECENT_OPEN
    sm._remember_result(OPEN_FF, True)
    monkeypatch.setenv("SOUNDOS_REPEAT_CHECK", "0")
    calls = []
    assert sm._check_repeat_open(dict(OPEN_FF), asker("yes", calls)) == (OPEN_FF, False) and calls == []
    monkeypatch.delenv("SOUNDOS_REPEAT_CHECK")
    assert sm._check_repeat_open(dict(OPEN_FF), None) == (OPEN_FF, False)              # no way to ask -> normal


def test_end_to_end_open_open_yes_closes_the_browser(capsys):
    answers = iter(["ايوه"])
    sm.handle("افتح المتصفح", ask_yes_no=lambda: next(answers))
    sm.handle("افتح المتصفح", ask_yes_no=lambda: next(answers))        # Whisper heard افتح for اقفل
    out = capsys.readouterr().out
    assert out.count("فتح تطبيق") == 1               # opened once, not twice
    assert "did you mean CLOSE" in out
    assert "إغلاق تطبيق firefox" in out              # the 2nd command was turned into a close


# ---------------------------------------------------------------- beam search
def test_beam_size_default_and_env(monkeypatch):
    monkeypatch.delenv("SOUNDOS_STT_BEAM", raising=False)
    assert _beam_size() == 5
    monkeypatch.setenv("SOUNDOS_STT_BEAM", "1")
    assert _beam_size() == 1
    monkeypatch.setenv("SOUNDOS_STT_BEAM", "99")
    assert _beam_size() == 10
    monkeypatch.setenv("SOUNDOS_STT_BEAM", "abc")
    assert _beam_size() == 5
