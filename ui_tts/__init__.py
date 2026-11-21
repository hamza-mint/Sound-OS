"""Sound OS - Dave's UI and voice. Public functions never raise (CONTRACT Rule 7)."""

import os
import subprocess


def notify(title: str, body: str) -> None:
    """Show a desktop notification via notify-send. Never raises."""
    try:
        subprocess.run(
            ["notify-send", str(title), str(body)],
            check=False,
            timeout=3,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def speak(text: str, lang: str = "en") -> None:
    """Dave says `text` out loud, and in his speech bubble. Returns at once; the speech
    plays in the background. Never raises.
    """
    if not text:
        return
    try:
        print(f"[ui_tts.speak:{lang}] {text}", flush=True)
    except Exception:
        pass
    try:
        from . import dave_voice
        if dave_voice.speak(text, lang):
            return
    except Exception:
        pass


def play_wake_ack() -> None:
    """Silenced: Dave UI and voice handle wake feedback directly."""
    pass


def play_done_sound() -> None:
    """Silenced: Dave UI and voice handle completion feedback directly."""
    pass


def play_wake_sound() -> None:
    """Silenced: Dave UI and voice handle wake feedback directly."""
    pass


# Export Dave desktop & bridge API
try:
    from .dave_desktop import (
        start,
        stop,
        on_wake,
        on_heard,
        on_done,
        say,
        hush,
        set_level,
        set_mouth,
    )
except Exception:
    pass

__all__ = [
    "notify",
    "speak",
    "play_wake_ack",
    "play_done_sound",
    "play_wake_sound",
    "start",
    "stop",
    "on_wake",
    "on_heard",
    "on_done",
    "say",
    "hush",
    "set_level",
    "set_mouth",
]
