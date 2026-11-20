"""Prompt-leak guard tests (no model download). Run: pytest -q stt/tests/test_leak_guard.py

Real case behind these tests (faster-whisper base/tiny + the command-list prompt, Arabic clip of
"علي الصوت"): Whisper kept writing prompt words -> "ايضاً، افتح الترمينال، وطي الإضاءة" and the parser
ran brightness_down. The guard keeps only the words the audio can physically contain.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from stt import SpeechToText, SAMPLE_RATE
from stt.tests.test_stt import make_stt, StubModel
from intent_parser import parse

trim = SpeechToText.trim_to_speech


@pytest.mark.parametrize("text,seconds,want", [
    # leaked prompt words after the real command are removed
    ("افتح المتصفح، افتم ترمينال، اعلي السطوع، ايضا، اقفل، اكتبه.", 1.1, "افتح المتصفح"),
    ("ايضاً، افتح الترمينال، وطي الإضاءة،", 0.9, "ايضاً، افتح الترمينال"),
    # a real two-command sentence that fits the speech length is kept
    ("افتح المتصفح، وعلي الصوت", 2.0, "افتح المتصفح، وعلي الصوت"),
    ("open the browser, turn up volume", 2.2, "open the browser, turn up volume"),
    # no punctuation / single clause: never touched
    ("افتح المتصفح وعلي الصوت", 1.2, "افتح المتصفح وعلي الصوت"),
    ("افتح المتصفح", 1.0, "افتح المتصفح"),
    ("", 1.0, ""),
])
def test_trim_to_speech(text, seconds, want):
    assert trim(text, seconds) == want


def test_first_clause_is_always_kept_even_for_tiny_duration():
    assert trim("افتح المتصفح الان فورا، علي الصوت", 0.1) == "افتح المتصفح الان فورا"


def test_trimmed_leak_gives_the_right_intent():
    leaked = "ايضاً، علي الصوت، افتح الترمينال، وطي الإضاءة،"
    assert parse(leaked)["intent"] != "volume_up"                    # what used to happen
    assert parse(trim(leaked, 0.9))["intent"] == "volume_up"


def test_voiced_seconds_ignores_silence_and_counts_sound():
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    tone = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)    # 1.0 s of sound
    clip = np.concatenate([np.zeros(SAMPLE_RATE, np.float32), tone, np.zeros(2 * SAMPLE_RATE, np.float32)])
    v = SpeechToText.voiced_seconds(clip)
    assert 1.0 <= v <= 1.5, v                                        # 1 s + the 0.2 s margin, not 4 s


def test_voiced_seconds_on_pure_silence_is_small():
    assert SpeechToText.voiced_seconds(np.zeros(SAMPLE_RATE * 3, np.float32)) < 0.5


def test_decode_applies_the_guard():
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    audio = np.concatenate([np.zeros(SAMPLE_RATE // 2, np.float32),
                            (0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32),
                            np.zeros(SAMPLE_RATE // 2, np.float32)])
    leaked = "علي الصوت، افتح الترمينال، وطي الإضاءة، اكتم"
    model = StubModel([(leaked, "ar", None)])
    text, lang = make_stt(model).transcribe(audio, language="ar")
    assert text == "علي الصوت"
    assert lang == "ar"
