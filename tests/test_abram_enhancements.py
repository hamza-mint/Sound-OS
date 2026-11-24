"""tests/test_abram_enhancements.py - verify safe enhancements adopted from Abram's review.

Covers:
1. Rejection of conversations ABOUT Dave (e.g., 'Dave said...', 'قال ديف...').
2. Bounded SOUNDOS_WAKE_MAX_SECONDS parsing.
3. Pending command thread-safety, read-once consumption, and TTL expiration.
4. Whisper YouTube/subtitle hallucination filtering.
"""
import math
import os
import threading
import time
import pytest

from audio import wakeword as w
from stt.stt import SpeechToText


def test_talk_about_dave_rejected_as_wake_word():
    # Sentences talking ABOUT Dave should not trigger wake word activation
    phrases = [
        "dave said do not delete the file",
        "Dave says hello world",
        "dave told me to shut down",
        "قال ديف لا تحذف الملف",
        "يقول ديف اقفل البرنامج",
        "dave is not here",
        "dave was talking",
    ]
    for p in phrases:
        kind, payload = w._classify(p)
        assert kind in ("needs_wake", "heard") and kind != "wake", f"Expected wake rejection for {p!r}, got {kind!r}"


def test_real_wake_commands_still_work():
    # Direct calls to Dave must still match wake word
    valid = [
        ("hey dave delete file", "delete file"),
        ("Hey Dave, volume up", "volume up"),
        ("يا ديف افتح المتصفح", "افتح المتصفح"),
        ("ديف اقفل تطبيق", "اقفل تطبيق"),
    ]
    for text, expected_cmd in valid:
        kind, payload = w._classify(text)
        assert kind == "wake", f"Expected 'wake' for {text!r}, got {kind!r}"


def test_wake_max_seconds_bounds_and_fallbacks(monkeypatch):
    monkeypatch.delenv("SOUNDOS_WAKE_MAX_SECONDS", raising=False)
    assert w.get_wake_max_seconds() == 2.2

    # Valid values
    monkeypatch.setenv("SOUNDOS_WAKE_MAX_SECONDS", "1.5")
    assert w.get_wake_max_seconds() == 1.5
    monkeypatch.setenv("SOUNDOS_WAKE_MAX_SECONDS", "3.0")
    assert w.get_wake_max_seconds() == 3.0

    # Out of bounds (< 0.8 or > 5.0) -> fallback 2.2
    monkeypatch.setenv("SOUNDOS_WAKE_MAX_SECONDS", "0.2")
    assert w.get_wake_max_seconds() == 2.2
    monkeypatch.setenv("SOUNDOS_WAKE_MAX_SECONDS", "10.0")
    assert w.get_wake_max_seconds() == 2.2

    # Invalid string / NaN -> fallback 2.2
    monkeypatch.setenv("SOUNDOS_WAKE_MAX_SECONDS", "invalid")
    assert w.get_wake_max_seconds() == 2.2
    monkeypatch.setenv("SOUNDOS_WAKE_MAX_SECONDS", "nan")
    assert w.get_wake_max_seconds() == 2.2


def test_pending_command_consume_once():
    w.set_pending("open browser")
    assert w.consume_pending() == "open browser"
    assert w.consume_pending() is None
    assert w.get_pending_command() is None


def test_pending_command_ttl_expiration():
    w.set_pending("open browser")
    # Consume with zero/negative TTL -> expired
    assert w.consume_pending(ttl=-1.0) is None


def test_pending_command_thread_safety():
    w.set_pending("safe_cmd")
    results = []

    def reader():
        cmd = w.consume_pending()
        if cmd is not None:
            results.append(cmd)

    threads = [threading.Thread(target=reader) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread should consume the command
    assert results == ["safe_cmd"]


def test_stt_hallucination_filtering():
    hallucinations = [
        "Thanks for watching!",
        "Thank you for watching.",
        "Please subscribe to our channel",
        "Subtitles by Amara org",
        "شكرا لمشاهدتكم",
        "اشتركوا في القناة",
        "شكرا على المشاهدة",
    ]
    for h in hallucinations:
        assert SpeechToText.is_hallucination(h), f"Expected hallucination for {h!r}"

    valid_commands = [
        "افتح المتصفح",
        "open the browser",
        "علي الصوت",
        "اقفل النافذة",
        "create file test.txt",
    ]
    for cmd in valid_commands:
        assert not SpeechToText.is_hallucination(cmd), f"Did not expect hallucination for {cmd!r}"
