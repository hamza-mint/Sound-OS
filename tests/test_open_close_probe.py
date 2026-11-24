"""'اقفل المتصفح' heard as 'افتح المتصفح'. A prompt-free decode (probe) decides if the heard verb is backed by the audio;
if not, ONE short yes/no question is asked.   Run: pytest -q tests/test_open_close_probe.py"""
import numpy as np
import pytest

import main as sm
from audio import wakeword
from intent_parser import parse_yes_no

AUDIO = np.zeros(16000, np.float32)
CLOSE_LIKE = "ايه فرمت صفح"        # real prompt-free text of a spoken "اقفل المتصفح"
OPEN_LIKE = "إفتهم صفح"            # real prompt-free text of a spoken "افتح المتصفح"


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


def test_clear_open_audio_is_not_questioned():
    asked = []
    assert sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning("ايوه", asked), probe=probe_returning(OPEN_LIKE)) == "افتح المتصفح"
    assert asked == []


@pytest.mark.parametrize("answer,expected", [
    ("ايوه", "اقفل المتصفح"), ("نعم", "اقفل المتصفح"), ("عيوة، ياس", "اقفل المتصفح"),   # last one = real STT output of "ايوه"
    ("لا", "افتح المتصفح"),
    ("", ""), ("blah", ""), (None, ""),
])
def test_unclear_audio_asks_one_question(answer, expected, quiet):
    asked = []
    out = sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning(answer, asked), probe=probe_returning(CLOSE_LIKE))
    assert out == expected and asked == [1]
    assert quiet and quiet[0] == "Close firefox? Yes or no."           # short: the user answers before a long question ends


def test_heard_close_but_audio_says_open_also_asks():
    out = sm._resolve_open_close("اقفل المتصفح", AUDIO, ask_returning("لا"), probe=probe_returning("افتح المتصفح"))
    assert out == "افتح المتصفح"


def test_heard_close_with_neutral_audio_is_trusted():
    asked = []
    assert sm._resolve_open_close("اقفل المتصفح", AUDIO, ask_returning("ايوه", asked), probe=probe_returning(CLOSE_LIKE)) == "اقفل المتصفح"
    assert asked == []


def test_no_probe_when_it_cannot_matter():
    calls = []
    p = probe_returning(CLOSE_LIKE, calls)
    assert sm._resolve_open_close("open the browser", AUDIO, ask_returning("yes"), probe=p) == "open the browser"
    assert sm._resolve_open_close("علي الصوت", AUDIO, ask_returning("yes"), probe=p) == "علي الصوت"
    assert sm._resolve_open_close("افتح المتصفح", None, ask_returning("yes"), probe=p) == "افتح المتصفح"
    assert sm._resolve_open_close("افتح المتصفح", AUDIO, None, probe=p) == "افتح المتصفح"
    assert sm._resolve_open_close("اقفل", AUDIO, ask_returning("yes"), probe=p) == "اقفل"                  # "current" window
    assert sm._resolve_open_close("", AUDIO, ask_returning("yes"), probe=p) == ""
    assert calls == []


def test_a_crashing_probe_never_blocks_the_command():
    assert sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning("yes"),
                                  probe=probe_returning(RuntimeError("model busy"))) == "افتح المتصفح"


def test_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SOUNDOS_PROBE", "0")
    calls = []
    assert sm._resolve_open_close("افتح المتصفح", AUDIO, ask_returning("yes"), probe=probe_returning(CLOSE_LIKE, calls)) == "افتح المتصفح"
    assert calls == []


def test_transcribe_probe_never_raises_and_is_prompt_free(monkeypatch):
    from stt import transcribe_probe
    import stt as stt_pkg
    assert transcribe_probe(object()) == ""
    seen = {}

    class Fake:
        def transcribe(self, audio, language=None, use_prompt=True, prompt=None):
            seen.update(language=language, use_prompt=use_prompt)
            return "ايه فرمت صفح", "ar"

    monkeypatch.setattr(stt_pkg, "get_model", lambda: Fake())
    assert transcribe_probe(AUDIO) == "ايه فرمت صفح" and seen == {"language": "ar", "use_prompt": False}


def test_pending_audio_travels_with_the_pending_command():
    with wakeword._pending_lock:
        wakeword._pending_command, wakeword._pending_audio = "افتح المتصفح", AUDIO
    assert wakeword.get_pending_command() == "افتح المتصفح"
    assert wakeword.get_pending_audio() is AUDIO
    assert wakeword.get_pending_audio() is None


@pytest.mark.parametrize("answer", ["عيوة، ياس", "عيوه", "yas", "ياس"])
def test_yes_variants_heard_in_a_real_session(answer):
    assert parse_yes_no(answer) is True


def test_listen_utterance_does_not_recurse_probe(monkeypatch):
    """Yes/no follow-up from _resolve_open_close must not re-enter _resolve_open_close (real log bug)."""
    probe_calls = []
    rec_calls = 0

    def fake_record():
        nonlocal rec_calls
        rec_calls += 1
        return f"fake_{rec_calls}.wav"

    def fake_transcribe(wav_path):
        return {"text": "افتح الترمينال", "lang": "ar", "confidence": 1.0}

    def fake_probe(audio):
        probe_calls.append(audio)
        return ""

    monkeypatch.setattr(sm, "wait_until_silent", lambda: None)
    monkeypatch.setattr(sm, "record_utterance", fake_record)
    monkeypatch.setattr(sm, "transcribe", fake_transcribe)
    monkeypatch.setattr(sm, "transcribe_probe", fake_probe)
    monkeypatch.setattr(sm, "speak", lambda *a, **kw: None)

    out = sm.listen_utterance()
    assert out["text"] == ""
    assert len(probe_calls) == 1
    assert rec_calls == 2
