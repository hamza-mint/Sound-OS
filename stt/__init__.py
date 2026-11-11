"""Sound OS speech-to-text module (Owner: Mahmoud Hamed).

Exposes:
    transcribe(wav_path, lang_hint=None) -> dict (matches CONTRACT.md)
    SpeechToText (Mahmoud's core Whisper class)
"""
from .stt import SpeechToText, SAMPLE_RATE, PROMPTS

_model_instance = None


def get_model(model_size: str = "tiny", cpu_threads: int = 0) -> SpeechToText:
    """Singleton getter for the Whisper model (loaded once)."""
    global _model_instance
    if _model_instance is None:
        _model_instance = SpeechToText(model_size=model_size, cpu_threads=cpu_threads)
    return _model_instance


def transcribe(wav_path: str, lang_hint: str | None = None) -> dict:
    """WAV file -> {"text": str, "lang": "ar" | "en", "confidence": 0..1}.

    Fulfills CONTRACT.md specification.
    On silence or error return text "" - never raise.
    """
    try:
        model = get_model()
        text, lang = model.transcribe(wav_path, language=lang_hint)
        return {
            "text": text,
            "lang": lang,
            "confidence": 1.0 if text else 0.0,
        }
    except Exception:
        return {
            "text": "",
            "lang": lang_hint or "en",
            "confidence": 0.0,
        }


__all__ = ["transcribe", "SpeechToText", "PROMPTS", "SAMPLE_RATE", "get_model"]
