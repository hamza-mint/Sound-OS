"""Unit tests that run WITHOUT downloading any model (the Whisper model is stubbed)."""
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from stt import SpeechToText, PROMPTS, SAMPLE_RATE, MAX_NEW_TOKENS


def make_stt(model=None, strategy="both"):
    obj = SpeechToText.__new__(SpeechToText)     # skip __init__ (no model download)
    obj.model = model
    obj.auto_strategy = strategy
    obj.last_candidates = []
    return obj


class StubModel:
    """Mimics faster-whisper: returns (segments, info). Records the calls.
    replies: (text, detected_lang, language_probs, avg_logprob)."""
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def transcribe(self, audio, **kw):
        self.calls.append(kw)
        text, lang, probs, score = (list(self.replies.pop(0)) + [None, -0.5])[:4]
        segs = iter([SimpleNamespace(text=f" {text} ", avg_logprob=score)]) if text else iter([])
        return segs, SimpleNamespace(language=lang, all_language_probs=probs)


def tone(seconds=1.0, amp=0.3):
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


# ---------- input handling ----------
def test_int16_is_scaled():
    a = np.array([0, 16384, -32768], dtype=np.int16)
    out = SpeechToText._load(a)
    assert out.dtype == np.float32
    assert out[1] == pytest.approx(0.5) and out[2] == pytest.approx(-1.0)


def test_stereo_to_mono():
    assert SpeechToText._load(np.stack([tone(), tone()], axis=1)).ndim == 1


def test_wrong_sample_rate_file_raises(tmp_path):
    p = tmp_path / "x.wav"
    sf.write(str(p), tone(), 8000)
    with pytest.raises(ValueError, match="16000"):
        SpeechToText._load(str(p))


def test_reads_wav_path(tmp_path):
    p = tmp_path / "x.wav"
    sf.write(str(p), tone(), SAMPLE_RATE)
    assert len(SpeechToText._load(str(p))) == SAMPLE_RATE


# ---------- gates ----------
def test_silence_never_calls_model():
    assert make_stt(None).transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32)) == ("", "en")


def test_too_short_never_calls_model():
    s = make_stt(None)
    assert s.transcribe(tone(0.1)) == ("", "en")
    assert s.transcribe(tone(0.1), language="ar") == ("", "ar")


def test_repetition_detector():
    assert SpeechToText._is_repetitive("mute mute mute")
    assert SpeechToText._is_repetitive("افتح، افتح، افتح")
    assert not SpeechToText._is_repetitive("turn the volume down")
    assert not SpeechToText._is_repetitive("")


# ---------- forced language ----------
def test_forced_language_no_prompt_by_default():
    m = StubModel([("وطي الصوت", "ar", None, -0.4)])
    text, lang = make_stt(m).transcribe(tone(), language="ar")
    assert (text, lang) == ("وطي الصوت", "ar")
    c = m.calls[0]
    assert c["language"] == "ar" and c["initial_prompt"] is None
    assert c["vad_filter"] is True and c["max_new_tokens"] == MAX_NEW_TOKENS
    assert len(m.calls) == 1


def test_prompt_is_opt_in():
    m = StubModel([("mute", "en", None, -0.4)])
    make_stt(m).transcribe(tone(), language="en", use_prompt=True)
    assert m.calls[0]["initial_prompt"] == PROMPTS["en"]


def test_forced_language_sets_candidates():
    s = make_stt(StubModel([("mute", "en", None, -0.3)]))
    s.transcribe(tone(), language="en")
    assert s.last_candidates == [{"lang": "en", "text": "mute", "score": pytest.approx(-0.3)}]


# ---------- auto: both languages ----------
def test_auto_both_picks_more_confident():
    # Arabic audio: the English decode is garbage with a worse score
    m = StubModel([("وطي سوت", "ar", None, -0.6), ("What the soot?", "en", None, -1.4)])
    s = make_stt(m)
    assert s.transcribe(tone()) == ("وطي سوت", "ar")
    assert [c["language"] for c in m.calls] == ["ar", "en"]
    assert {c["lang"] for c in s.last_candidates} == {"ar", "en"}


def test_auto_both_picks_english_when_more_confident():
    m = StubModel([("اوبن", "ar", None, -1.5), ("Volume up.", "en", None, -0.3)])
    assert make_stt(m).transcribe(tone()) == ("Volume up.", "en")


def test_auto_both_ignores_empty_candidate():
    m = StubModel([("", "ar", None, -0.1), ("mute", "en", None, -2.0)])
    assert make_stt(m).transcribe(tone()) == ("mute", "en")


def test_auto_both_all_empty():
    m = StubModel([("", "ar", None, -0.1), ("", "en", None, -0.1)])
    assert make_stt(m).transcribe(tone()) == ("", "en")


def test_repetitive_candidate_loses():
    m = StubModel([("افتح افتح افتح", "ar", None, -0.1), ("open", "en", None, -2.0)])
    assert make_stt(m).transcribe(tone()) == ("open", "en")


# ---------- auto: whisper strategy (kept as an option) ----------
def test_whisper_strategy_restricts_to_ar_en():
    m = StubModel([("garbage", "nn", [("ar", 0.30), ("en", 0.10), ("nn", 0.48)], -1.0),
                   ("افتح المتصفح", "ar", None, -0.5)])
    text, lang = make_stt(m, "whisper").transcribe(tone())
    assert lang == "ar" and text == "افتح المتصفح"
    assert m.calls[1]["language"] == "ar"


def test_whisper_strategy_keeps_valid_detection():
    m = StubModel([("open the browser", "en", None, -0.2)])
    assert make_stt(m, "whisper").transcribe(tone()) == ("open the browser", "en")
    assert len(m.calls) == 1


def test_bad_strategy_rejected():
    with pytest.raises(ValueError):
        SpeechToText.__init__(SpeechToText.__new__(SpeechToText), auto_strategy="nope")
