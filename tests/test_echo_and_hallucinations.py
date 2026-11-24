"""Echo / hallucination tests found by reading a REAL session log (/tmp/soundos_session.log).

What the log showed:
  * Dave said "Yes?", the mic recorded it, STT wrote 'Yes?' and it was run as the user's command.
  * "I did not understand." and "[DRY-RUN] Closing calculator" (read aloud as 'D-R-Y R-U-N') were
    heard again by the wake-word listener -> a self-triggering loop.
  * Whisper wrote Chinese ('還不算是') on noise, and repeated 'Open calculator, open calculator.'
Run: pytest -q tests/test_echo_and_hallucinations.py
"""
import time

import pytest

import ui_tts
from stt import SpeechToText
import main as sound_main


@pytest.fixture(autouse=True)
def clean_recent():
    ui_tts._RECENT.clear()
    yield
    ui_tts._RECENT.clear()


def said(text):
    ui_tts._RECENT.append((ui_tts._norm_words(text), time.monotonic()))


# ---------------------------------------------------------- Dave's own voice
@pytest.mark.parametrize("spoken,heard,want", [
    ("Yes?", "Yes?", ""),                                       # only his own word
    ("Yes?", "Yeah.", "Yeah."),                                 # not his word: left alone (not a command anyway)
    ("Yes?", "Yes? Open files.", "Open files."),                # his word + the real command
    ("I did not understand", "I did not understand.", ""),
    ("Opening calculator", "Opening calculator", ""),
    ("نعم؟", "نعم؟ افتح المتصفح", "افتح المتصفح"),
    ("Yes?", "Open files", "Open files"),                       # nothing of his in it
])
def test_strip_own_speech(spoken, heard, want):
    said(spoken)
    assert ui_tts.strip_own_speech(heard) == want


def test_old_speech_is_not_removed():
    ui_tts._RECENT.append((ui_tts._norm_words("Yes?"), time.monotonic() - 60))     # said a minute ago
    assert ui_tts.strip_own_speech("Yes? Open files.") == "Yes? Open files."


def test_user_saying_the_same_word_later_is_a_command_again():
    said("Opening calculator")
    time.sleep(0)                                               # (window is 10 s; this proves the stripping is local)
    assert ui_tts.strip_own_speech("close calculator") == "close calculator"


def test_wait_until_silent_waits_for_the_voice_and_never_hangs(monkeypatch):
    from ui_tts import dave_voice
    states = iter([True, True, False])
    monkeypatch.setattr(dave_voice, "is_speaking", lambda: next(states, False))
    t = time.perf_counter()
    ui_tts.wait_until_silent(timeout=2.0, tail=0.0)
    assert 0.05 < time.perf_counter() - t < 1.0
    monkeypatch.setattr(dave_voice, "is_speaking", lambda: True)           # stuck voice
    t = time.perf_counter()
    ui_tts.wait_until_silent(timeout=0.3, tail=0.0)
    assert time.perf_counter() - t < 1.0                                    # gives up at the timeout


def test_speak_remembers_what_it_said(monkeypatch, capsys):
    from ui_tts import dave_voice
    monkeypatch.setattr(dave_voice, "speak", lambda text, lang="en": True)      # no real audio in tests
    ui_tts.speak("Hello there", "en")
    assert ui_tts._RECENT and ui_tts._RECENT[-1][0] == ["hello", "there"]


def test_speak_remembers_the_english_that_is_really_played(monkeypatch, capsys):
    """Arabic replies are spoken in English; the echo filter must know the English words."""
    from ui_tts import dave_voice
    played = []
    monkeypatch.setattr(dave_voice, "speak", lambda text, lang="en": played.append(text) or True)
    ui_tts.speak("[تجربة] إغلاق النافذة الحالية", "ar")
    assert played and ui_tts._RECENT[-1][0] == ui_tts._norm_words(played[0])


def test_the_dry_run_tag_is_not_read_aloud():
    assert sound_main._speakable("[DRY-RUN] Closing calculator") == "Closing calculator"
    assert sound_main._speakable("[تجربة] فتح تطبيق firefox") == "فتح تطبيق firefox"
    assert sound_main._speakable("Opened firefox") == "Opened firefox"
    assert sound_main._speakable(None) == ""


# -------------------------------------------------------------- hallucinations
@pytest.mark.parametrize("text", ["還不算是", "Привет", "ありがとう", "안녕하세요", "สวัสดี", "नमस्ते", "open 還"])
def test_foreign_script_is_rejected(text):
    assert SpeechToText.has_foreign_script(text)


@pytest.mark.parametrize("text", ["افتح المتصفح", "Open calculator", "Obym brał ze", "علّي الصوت 50"])
def test_arabic_and_latin_are_kept(text):
    assert not SpeechToText.has_foreign_script(text)


@pytest.mark.parametrize("text,want", [
    ("Open calculator, open calculator.", "Open calculator,"),
    ("افتح المتصفح، افتح المتصفح،", "افتح المتصفح،"),
    ("افتح المتصفح، علي الصوت", "افتح المتصفح، علي الصوت"),        # two DIFFERENT commands: untouched
    ("open the browser", "open the browser"),
    ("a, a, a.", "a,"),
])
def test_dedupe_repeats(text, want):
    assert SpeechToText.dedupe_repeats(text) == want


def test_decode_drops_chinese_hallucination():
    import numpy as np
    from stt.tests.test_stt import make_stt, StubModel
    t = np.arange(16000) / 16000
    audio = np.concatenate([np.zeros(8000), 0.3 * np.sin(2 * np.pi * 200 * t), np.zeros(8000)]).astype(np.float32)
    text, _ = make_stt(StubModel([("還不算是", "ar", None)])).transcribe(audio, language="ar")
    assert text == ""


# ------------------------------------------------------------- wake word decode
def _wake_stt(reply):
    import numpy as np
    from stt.tests.test_stt import make_stt, StubModel
    model = StubModel([(reply, "en", None)])
    return make_stt(model), model, (0.2 * np.sin(2 * np.pi * 200 * np.arange(16000) / 16000)).astype("float32")


def test_wake_decode_uses_vad_so_noise_cannot_echo_the_prompt():
    """Real session log: 'Wake word matched: Hey Dave, Dave.' again and again with nobody speaking.
    Measured on 32 noise clips: 31 false wakes with vad_filter=False, 0 with vad_filter=True."""
    stt, model, audio = _wake_stt("Hey Dave.")
    text, _ = stt.transcribe_wake(audio)
    assert text == "Hey Dave."
    assert model.calls[0]["vad_filter"] is True


def test_wake_decode_drops_foreign_script_hallucination():
    stt, model, audio = _wake_stt("お便できます。")
    assert stt.transcribe_wake(audio)[0] == ""


def test_trim_to_speech_preserves_dot_in_filename():
    assert SpeechToText.trim_to_speech("Hey Dave, create file.py", 1.6) == "Hey Dave, create file.py"
    assert SpeechToText.trim_to_speech("Create file.py, open terminal, mute.", 1.2) == "Create file.py"


def test_decode_drops_high_no_speech_prob_hallucination():
    from types import SimpleNamespace
    import numpy as np
    from stt.tests.test_stt import make_stt

    class HighNoSpeechModel:
        def transcribe(self, audio, **kw):
            seg = SimpleNamespace(text=" افتح الترمينال", no_speech_prob=0.80)
            info = SimpleNamespace(language="ar", all_language_probs=[("ar", 0.9), ("en", 0.1)])
            return iter([seg]), info

    t = np.arange(16000) / 16000
    audio = (0.01 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    text, _ = make_stt(HighNoSpeechModel()).transcribe(audio, language="ar")
    assert text == ""
