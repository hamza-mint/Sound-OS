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


def _has_prompt_evidence(matched_clauses: list[str], probe_norm: str) -> bool:
    """True if prompt-free audio shares a 3-char stem/suffix with any content word of each matched prompt clause."""
    if not probe_norm:
        return False
    probe_words = [w.removeprefix("ال") for w in probe_norm.split() if w]
    for clause in matched_clauses:
        content = [w.removeprefix("ال") for w in clause.split() if len(w.removeprefix("ال")) >= 3]
        if content and not any(
            (cw[:3] in bw or cw[-3:] in bw)
            for cw in content
            for bw in probe_words
        ):
            return False
    return True


def _verify_ar_prompt(model: SpeechToText, wav_path: str, text: str, prompt_clauses: list[str]):
    """Return (verified_text, probe_text). Blanks `text` if it echoes PROMPTS['ar'] without audio backing."""
    from intent_parser.normalize import normalize as norm_ar

    norm_text = norm_ar(text)
    matched = [pc for pc in prompt_clauses if pc in norm_text]
    if not matched and not any(p in text for p in ["اقفل،", "سكر", "المتصفح الصوت", "انشئ ملفات"]):
        return text, None
    probe_text, _ = model.transcribe(wav_path, language="ar", use_prompt=False)
    if matched and not _has_prompt_evidence(matched, norm_ar(probe_text)):
        return "", probe_text
    return text, probe_text


def _recover_transcript(model: SpeechToText, wav_path: str, text: str, lang: str):
    """Verify Arabic prompt phrases against a prompt-free decode and recover English/Arabic mis-detections."""
    from intent_parser import parse
    from intent_parser.normalize import normalize as norm_ar

    prompt_clauses = [norm_ar(c.strip()) for c in PROMPTS["ar"].split("،") if c.strip() and c.strip() != "ديف"]
    probe_text = None

    if text and lang == "ar":
        text, probe_text = _verify_ar_prompt(model, wav_path, text, prompt_clauses)

    is_unknown = not text or parse(text).get("intent") == "unknown"
    is_suspicious_leak = bool(text and lang == "ar" and any(p in text for p in ["اقفل،", "سكر", "المتصفح الصوت", "انشئ ملفات"]))
    if not (is_unknown or is_suspicious_leak):
        return text, lang

    other_lang = "en" if lang == "ar" else "ar"
    other_text, other_l = model.transcribe(wav_path, language=other_lang)
    if other_text and other_l == "ar":
        other_text, ar_probe = _verify_ar_prompt(model, wav_path, other_text, prompt_clauses)
        if probe_text is None and ar_probe is not None:
            probe_text = ar_probe

    # Prefer prompt-free probe if it already yields a valid non-prompt intent
    if probe_text and parse(probe_text).get("intent") != "unknown":
        return probe_text, "ar"
    if other_text and parse(other_text).get("intent") != "unknown":
        return other_text, other_l
    # Fallback: prompt-free decode in the originally detected language
    lang_probe, _ = model.transcribe(wav_path, language=lang, use_prompt=False)
    if lang_probe and parse(lang_probe).get("intent") != "unknown":
        return lang_probe, lang
    return text, lang


def transcribe(wav_path: str, lang_hint: str | None = None) -> dict:
    """WAV file -> {"text": str, "lang": "ar" | "en", "confidence": 0..1}.

    Fulfills CONTRACT.md specification.
    On silence or error return text "" - never raise.
    """
    try:
        model = get_model()
        text, lang = model.transcribe(wav_path, language=lang_hint)

        # Cross-language & prompt-echo recovery: verify prompt-matched Arabic output against
        # prompt-free audio and try the alternative language when accented/English commands fail.
        if lang_hint is None:
            try:
                text, lang = _recover_transcript(model, wav_path, text, lang)
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
