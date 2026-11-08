"""Sound OS - GUI package (notifications + audio feedback). Public functions never raise."""

from pathlib import Path
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


def speak(text: str, lang: str = "ar") -> None:
    """Say text out loud using espeak-ng if available, with console fallback. Never raises."""
    if not text:
        return
    try:
        print(f"[ui_tts.speak:{lang}] {text}")
        voice = "ar" if lang == "ar" else "en"
        subprocess.run(
            ["espeak-ng", "-v", voice, str(text)],
            check=False,
            timeout=4,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def play_wake_sound() -> None:
    """Play the wake chime/sound (non-blocking). Never raises."""
    try:
        wav = Path(__file__).parent / "assets" / "wake.wav"
        if wav.is_file():
            subprocess.Popen(
                ["aplay", "-q", str(wav)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass

