"""Sound OS - GUI package (notifications + stubs). Public functions never raise."""

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


def speak(text: str, lang: str) -> None:
    """Stub: no TTS in this module. Never raises."""
    try:
        print(f"[ui_tts.speak:{lang}] {text}")
    except Exception:
        pass
