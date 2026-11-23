"""'اقفل المتصفح' heard as 'افتح المتصفح': the probe (2nd decode with the close-first prompt) detects unclear audio.
On real recordings (base/small) the normal prompt gave 'افتح' and the close-first prompt gave 'اقفل' for the
unclear clip, while a clearly spoken 'افتح' was 'افتح' with both.   Run: pytest -q tests/test_open_close_probe.py
"""
import numpy as np
import pytest

import main as sm
from audio import wakeword

AUDIO = np.zeros(16000, np.float32)


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.delenv("SOUNDOS_PROBE", raising=False)
    said = []
    monkeypatch.setattr(sm, "speak", lambda text, lang="en": said.append(text))
    return said


def probe_returning(text, calls=None):
    def probe(audio):
        if calls is not None:
            calls.append(1)
        if isinstance(text, Exception):
            raise text
        return text
    return probe


def ask_returning(answer, asked=None):
    def ask():
        if asked is not None:
            asked.append(1)
        return answer
    return ask


def test_both_decodes_agree_so_no_question():
    asked = []
    out = sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning("ايوه", asked), probe=probe_returning("افتح المتصفح."))
    assert out == "افتح المتصفح" and asked == []
    out = sm._resolve_open_close("اقفل المتصفح", AUDIO, ask_returning("ايوه", asked), probe=probe_returning("اقفل المتصفح"))
    assert out == "اقفل المتصفح" and asked == []


@pytest.mark.parametrize("answer,expected", [
    ("ايوه", "اقفل المتصفح"),            # yes = close
    ("نعم", "اقفل المتصفح"),
    ("لا", "افتح المتصفح"),              # no = open
    ("", ""), ("blah", ""), (None, ""),  # unclear: do nothing
])
def test_the_decodes_disagree_so_one_yes_no_question_decides(answer, expected, quiet):
    asked = []
    out = sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning(answer, asked), probe=probe_returning("اقفل المتصفح"))
    assert out == expected and asked == [1]
    assert any("close firefox" in s for s in quiet)


def test_works_the_other_way_round_too():
    out = sm._resolve_open_close("اقفل المتصفح", AUDIO, ask_returning("لا"), probe=probe_returning("افتح المتصفح"))
    assert out == "افتح المتصفح"


def test_no_probe_when_it_cannot_matter():
    calls = []
    p = probe_returning("اقفل المتصفح", calls)
    assert sm._resolve_open_close("open the browser", AUDIO, ask_returning("yes"), probe=p) == "open the browser"   # English
    assert sm._resolve_open_close("علي الصوت", AUDIO, ask_returning("yes"), probe=p) == "علي الصوت"                  # not open/close
    assert sm._resolve_open_close("افتح المتصفح", None, ask_returning("yes"), probe=p) == "افتح المتصفح"             # no audio
    assert sm._resolve_open_close("افتح المتصفح", AUDIO, None, probe=p) == "افتح المتصفح"                            # cannot ask
    assert sm._resolve_open_close("", AUDIO, ask_returning("yes"), probe=p) == ""
    assert calls == []


def test_different_apps_or_failures_are_not_an_open_close_doubt():
    asked = []
    assert sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning("yes", asked),
                                  probe=probe_returning("اقفل الترمينال")) == "افتح المتصفح" and asked == []
    for bad in ("", RuntimeError("model busy"), "علي الصوت", "blah"):
        assert sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning("yes", asked), probe=probe_returning(bad)) == "افتح المتصفح"
    assert asked == []


def test_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SOUNDOS_PROBE", "0")
    calls = []
    assert sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning("yes"), probe=probe_returning("اقفل المتصفح", calls)) == "افتح المتصفح"
    assert calls == []


def test_probe_uses_the_close_first_prompt():
    from stt import PROBE_PROMPT_AR
    assert PROBE_PROMPT_AR.index("اقفل المتصفح") < PROBE_PROMPT_AR.index("افتح المتصفح")
    from stt.stt import PROMPTS
    assert PROMPTS["ar"].index("افتح المتصفح") < PROMPTS["ar"].index("اقفل المتصفح")     # the two are opposite


def test_probe_never_raises():
    from stt import transcribe_probe
    assert transcribe_probe(object()) == ""


def test_pending_audio_travels_with_the_pending_command():
    with wakeword._pending_lock:
        wakeword._pending_command, wakeword._pending_audio = "افتح المتصفح", AUDIO
    assert wakeword.get_pending_command() == "افتح المتصفح"
    assert wakeword.get_pending_audio() is AUDIO
    assert wakeword.get_pending_audio() is None            # cleared after reading
