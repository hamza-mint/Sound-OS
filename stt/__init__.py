"""STUB - Mahmoud replaces the body, keeps the signature (see CONTRACT.md)."""


def transcribe(wav_path: str, lang_hint: str | None = None) -> dict:
    """WAV file -> {"text": str, "lang": "ar" | "en", "confidence": 0..1}.
    On silence or error return text "" - never raise."""
    return {"text": "افتح فايرفوكس", "lang": "ar", "confidence": 0.9}
