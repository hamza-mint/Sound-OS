"""Sound OS speech-to-text module (Owner: Mahmoud Hamed).

Exposes:
    transcribe(wav_path, lang_hint=None) -> dict (matches CONTRACT.md)
    SpeechToText (Mahmoud's core Whisper class)
"""
import os
from .stt import SpeechToText, SAMPLE_RATE, PROMPTS

_model_instance = None


def get_model(model_size: str = "tiny", cpu_threads: int = 0) -> SpeechToText:
    """Singleton getter for the Whisper model (loaded once)."""
    global _model_instance
    if _model_instance is None:
        effective_size = os.environ.get("SOUNDOS_STT_MODEL", model_size)
        _model_instance = SpeechToText(model_size=effective_size, cpu_threads=cpu_threads)
    return _model_instance


def transcribe(wav_path: str, lang_hint: str | None = None) -> dict:
    """WAV file -> {"text": str, "lang": "ar" | "en", "confidence": 0..1}.

    Fulfills CONTRACT.md specification.
    On silence or error return text "" - never raise.
    """
    try:
        model = get_model()
        text, lang = model.transcribe(wav_path, language=lang_hint)

        # Cross-language recovery: if auto-detect produced an unrecognized intent,
        # test the alternative language (en/ar) to recover accented commands (e.g. "Open calculator")
        if lang_hint is None and text:
            try:
                from intent_parser import parse
                if parse(text).get("intent") == "unknown":
                    other_lang = "en" if lang == "ar" else "ar"
                    other_text, other_l = model.transcribe(wav_path, language=other_lang)
                    if other_text and parse(other_text).get("intent") != "unknown":
                        text = other_text
                        lang = other_l
            except Exception:
                pass

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
