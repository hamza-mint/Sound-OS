"""Unit tests that run WITHOUT downloading any model (the Whisper model is stubbed)."""
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

import stt as stt_module
from stt import SpeechToText, PROMPTS, SAMPLE_RATE


def make_stt(model=None):
    obj = SpeechToText.__new__(SpeechToText)     # skip __init__ (no model download)
    obj.model = model
    return obj


class StubModel:
    """Mimics faster-whisper: returns (segments, info). Records the calls."""
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def transcribe(self, audio, **kw):
        self.calls.append(kw)
        text, lang, probs = self.replies.pop(0)
        segs = iter([SimpleNamespace(text=f" {text} ")]) if text else iter([])
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
    stereo = np.stack([tone(), tone()], axis=1)
    assert SpeechToText._load(stereo).ndim == 1


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
    s = make_stt(model=None)                      # would crash if the model were used
    assert s.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32)) == ("", "en")


def test_too_short_never_calls_model():
    s = make_stt(model=None)
    assert s.transcribe(tone(0.1)) == ("", "en")
    assert s.transcribe(tone(0.1), language="ar") == ("", "ar")


def test_repetition_detector():
    assert SpeechToText._is_repetitive("mute mute mute")
    assert SpeechToText._is_repetitive("افتح، افتح، افتح")
    assert not SpeechToText._is_repetitive("turn the volume down")
    assert not SpeechToText._is_repetitive("")


# ---------- decoding logic ----------
def test_forced_language_and_prompt():
    m = StubModel([("وطي الصوت", "ar", None)])
    text, lang = make_stt(m).transcribe(tone(), language="ar")
    assert (text, lang) == ("وطي الصوت", "ar")
    assert m.calls[0]["language"] == "ar"
    assert m.calls[0]["initial_prompt"] == PROMPTS["ar"]
    assert m.calls[0]["vad_filter"] is True


def test_prompt_can_be_disabled():
    m = StubModel([("mute", "en", None)])
    make_stt(m).transcribe(tone(), language="en", use_prompt=False)
    assert m.calls[0]["initial_prompt"] is None


def test_auto_language_restricted_to_ar_en():
    # the model first guesses Norwegian ("nn"); we must retry with the best of ar/en
    m = StubModel([("garbage", "nn", [("ar", 0.30), ("en", 0.10), ("nn", 0.48)]),
                   ("افتح المتصفح", "ar", None)])
    text, lang = make_stt(m).transcribe(tone())
    assert lang == "ar" and text == "افتح المتصفح"
    assert m.calls[1]["language"] == "ar"


def test_auto_language_keeps_valid_detection():
    m = StubModel([("open the browser", "en", None)])
    assert make_stt(m).transcribe(tone()) == ("open the browser", "en")
    assert len(m.calls) == 1


def test_repetitive_output_is_blanked():
    m = StubModel([("mute mute mute mute", "en", None)])
    assert make_stt(m).transcribe(tone(), language="en") == ("", "en")


def test_empty_model_output():
    m = StubModel([("", "en", None)])
    assert make_stt(m).transcribe(tone(), language="en") == ("", "en")
