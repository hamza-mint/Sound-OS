"""Sound OS - Dave's UI and voice. Public functions never raise (CONTRACT Rule 7)."""

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
    """Dave says `text` out loud, and in his speech bubble. Returns at once; the speech
    plays in the background. Never raises.

    If his voice can't run at all (e.g. numpy is missing) the text is printed instead.
    """
    try:
        from . import dave_voice
        if dave_voice.speak(text, lang):
            return
    except Exception:
        pass
    try:
        print(f"[ui_tts.speak:{lang}] {text}")
    except Exception:
        pass
