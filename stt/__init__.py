"""Sound OS speech-to-text module (Owner: Mahmoud Hamed).

Exposes:
    transcribe(wav_path, lang_hint=None) -> dict (matches CONTRACT.md)
    SpeechToText (Mahmoud's core Whisper class)
"""
import os
from .stt import SpeechToText, SAMPLE_RATE, PROMPTS
from .textnorm import normalize
from .run_live import Endpointer, SR

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
        # or if text is empty (e.g. filtered hallucination), or contains suspicious prompt leakage,
        # test the alternative language (en/ar) to recover accented/English commands (e.g. "create file.md")
        if lang_hint is None:
            try:
                from intent_parser import parse
                is_unknown = not text or parse(text).get("intent") == "unknown"
                is_suspicious_leak = bool(text and lang == "ar" and any(p in text for p in ["اقفل،", "سكر", "المتصفح الصوت", "انشئ ملفات"]))
                if is_unknown or is_suspicious_leak:
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


def transcribe_probe(audio_input) -> str:
    """Prompt-FREE Arabic decode of a clip: garbled but honest. Used to check an open/close verb
    (see intent_parser/verb_check.py). Returns the text, or "" on any problem. Never raises."""
    try:
        text, _ = get_model().transcribe(audio_input, language="ar", use_prompt=False)
        return text or ""
    except Exception:
        return ""


def transcribe_wake(audio_input) -> dict:
    """Specialized ultra-fast wake phrase transcriber with 'Hey Dave' prompt."""
    try:
        model = get_model()
        if hasattr(model, "transcribe_wake"):
            text, lang = model.transcribe_wake(audio_input)
        else:
            text, lang = model.transcribe(
                audio_input,
                language=None,
                prompt="Hey Dave, Hi Dave, Dave, ديف, هاي ديف.",
            )
        return {"text": text, "lang": lang, "confidence": 1.0 if text else 0.0}
    except Exception:
        return transcribe(audio_input)


__all__ = [
    "transcribe",
    "transcribe_probe",
    "transcribe_wake",
    "SpeechToText",
    "Endpointer",
    "normalize",
    "PROMPTS",
    "SAMPLE_RATE",
    "SR",
    "get_model",
]
