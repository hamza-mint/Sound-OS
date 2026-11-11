"""Sound OS speech-to-text module (Owner: Mahmoud Hamed).

Exposes:
    transcribe(wav_path, lang_hint=None) -> dict (matches CONTRACT.md)
    SpeechToText (Mahmoud's core Whisper class)
    Endpointer (voice activity endpointing)
    normalize (Arabic/English text normalization)
"""
import os
import math
import numpy as np

from .stt import (
    SpeechToText,
    SAMPLE_RATE,
    ALLOWED_LANGS,
    NO_SCORE,
    PROMPTS,
    SILENCE_RMS,
    MIN_SECONDS,
    MAX_NEW_TOKENS,
)
from .textnorm import normalize
from .run_live import Endpointer, SR

_model_instance = None


def get_model(model_size: str | None = None, cpu_threads: int = 0) -> SpeechToText:
    """Singleton getter for the Whisper model (loaded once)."""
    global _model_instance
    if _model_instance is None:
        size = model_size or os.getenv("SOUNDOS_STT_MODEL", "base")
        _model_instance = SpeechToText(model_size=size, cpu_threads=cpu_threads)
    return _model_instance


def transcribe(wav_path: str, lang_hint: str | None = None) -> dict:
    """WAV file -> {"text": str, "lang": "ar" | "en", "confidence": 0..1}.

    Fulfills CONTRACT.md specification.
    On silence or error return text "" - never raise.
    """
    try:
        model = get_model()
        text, lang = model.transcribe(wav_path, language=lang_hint)
        conf = 0.0
        if text:
            # If candidates are available, use best score to compute confidence
            if getattr(model, "last_candidates", None):
                cand = next((c for c in model.last_candidates if c.get("lang") == lang), None)
                if cand and cand.get("score", NO_SCORE) != NO_SCORE:
                    try:
                        conf = max(0.0, min(1.0, float(math.exp(cand["score"]))))
                    except OverflowError:
                        conf = 1.0
                else:
                    conf = 1.0
            else:
                conf = 1.0

        return {
            "text": text,
            "lang": lang,
            "confidence": conf,
        }
    except Exception:
        return {
            "text": "",
            "lang": lang_hint or "en",
            "confidence": 0.0,
        }


__all__ = [
    "transcribe",
    "SpeechToText",
    "Endpointer",
    "normalize",
    "PROMPTS",
    "SAMPLE_RATE",
    "ALLOWED_LANGS",
    "NO_SCORE",
    "SILENCE_RMS",
    "MIN_SECONDS",
    "MAX_NEW_TOKENS",
    "SR",
    "get_model",
]
