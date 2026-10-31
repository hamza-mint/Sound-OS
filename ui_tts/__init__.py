"""STUB - Youssef replaces the bodies, keeps the signatures (see CONTRACT.md)."""


def speak(text: str, lang: str) -> None:
    """Say `text` out loud in "ar" or "en". Empty text = say nothing."""
    if text:
        print(f"[speak:{lang}] {text}")


def notify(title: str, body: str) -> None:
    """Desktop notification (Xfce: notify-send)."""
    print(f"[notify] {title}: {body}")
