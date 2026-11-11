"""
audio - Sound OS audio capture and wake-word module (Role 1: Abram).

Public API (CONTRACT.md Rule 1: neither function ever raises):

    wait_for_wake_word() -> None
        Blocks until the wake word is heard. Falls back to a loud sound or the
        Enter key when no wake-word model is configured.

    record_utterance(max_seconds: float = 6.0) -> str
        Records speech until ~1 s of silence (or max_seconds) and returns the
        absolute path of a 16 kHz / 16-bit / mono WAV file ("" only if even
        writing a fallback file failed).
"""

import sys


def wait_for_wake_word() -> None:
    """Block until the wake word is heard. Never raises."""
    try:
        from .wakeword import wait_for_wake_word as _impl
        _impl()
    except Exception as exc:
        try:
            print(f"[audio] wait_for_wake_word error: {exc}", file=sys.stderr)
        except Exception:
            pass


def record_utterance(max_seconds: float = 6.0) -> str:
    """Record one utterance to a temp WAV (16 kHz mono) and return its path."""
    try:
        from .recorder import record_utterance as _impl
        return _impl(max_seconds)
    except Exception as exc:
        try:
            print(f"[audio] record_utterance error: {exc}", file=sys.stderr)
        except Exception:
            pass
        return ""


__all__ = ["wait_for_wake_word", "record_utterance"]
