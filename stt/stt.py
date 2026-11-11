"""stt.py - Sound OS speech-to-text module (faster-whisper, CPU only, offline).

    from stt import SpeechToText
    stt = SpeechToText("base")                      # load the model ONCE at startup
    text, lang = stt.transcribe("clip.wav")         # or a 16 kHz mono numpy array
    text, lang = stt.transcribe(audio, language="ar")   # force a language (faster + more reliable)

Contract:
    input : WAV path, or numpy array, 16 kHz mono (float32 in [-1, 1] or int16)
    output: (text, lang), lang is "ar" or "en".
            text == "" means "no speech understood" -> the caller must ignore it.
    extra : stt.last_candidates = what each language decode produced
            [{"lang", "text", "score"}] -> the intent parser MAY use it (optional).

Decisions taken from live tests on one PC (few clips - see README):
  * initial_prompt is OFF by default: with `tiny` it made the model output the
    prompt phrase ("افتح المتصفح") for other commands.
  * Whisper's own language auto-detection often labelled Arabic commands as
    English (all of tiny/base/small). So when the language is not given we
    decode in BOTH languages and keep the more confident one (auto_strategy="both").
    This part is NOT validated on a real test set yet.
"""
import time

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
ALLOWED_LANGS = ("ar", "en")     # the only languages the project supports
NO_SCORE = float("-inf")

# Only used when use_prompt=True (OFF by default, see above).
PROMPTS = {
    "ar": "افتح المتصفح",
    "en": "Open the browser.",
}

SILENCE_RMS = 0.003    # gate for (almost) digital silence; VAD handles real noise
MIN_SECONDS = 0.3      # shorter than this -> ignore
MAX_NEW_TOKENS = 40    # commands are short; Arabic needs more tokens than English


class SpeechToText:
    def __init__(self, model_size="base", cpu_threads=0, auto_strategy="both"):
        """model_size: tiny | base | small.   cpu_threads=0 -> library default.
        auto_strategy (used only when language is None):
          "both"    decode in ar and en, keep the more confident (2x time)
          "whisper" trust Whisper's language detection (restricted to ar/en)"""
        if auto_strategy not in ("both", "whisper"):
            raise ValueError("auto_strategy must be 'both' or 'whisper'")
        t0 = time.perf_counter()
        self.model = WhisperModel(model_size, device="cpu",
                                  compute_type="int8", cpu_threads=cpu_threads)
        self.load_seconds = time.perf_counter() - t0
        self.auto_strategy = auto_strategy
        self.last_candidates = []

    # ---------- helpers ----------
    @staticmethod
    def _load(audio):
        """Path or array -> mono float32 in [-1, 1].
        Files are read with soundfile (NOT PyAV): avoids the faster-whisper/av
        'metadata_errors' incompatibility."""
        if isinstance(audio, str):
            audio, sr = sf.read(audio, dtype="float32")
            if sr != SAMPLE_RATE:
                raise ValueError(
                    f"{sr} Hz file; expected {SAMPLE_RATE} Hz. Convert with: "
                    f"ffmpeg -i in.wav -ar 16000 -ac 1 out.wav")
        audio = np.asarray(audio)
        if audio.ndim > 1:                          # stereo / (n, 1) -> mono
            audio = audio.mean(axis=1)
        if audio.dtype == np.int16:                 # int16 -> [-1, 1]
            return audio.astype(np.float32) / 32768.0
        return audio.astype(np.float32)

    @staticmethod
    def rms(audio):
        """Loudness (0 = digital silence)."""
        return float(np.sqrt(np.mean(audio ** 2)))

    @staticmethod
    def _is_repetitive(text):
        """True if a word repeats 3 times in a row (typical hallucination)."""
        words = text.replace("،", " ").replace(",", " ").split()
        return any(words[i] == words[i + 1] == words[i + 2]
                   for i in range(len(words) - 2))

    # ---------- decoding ----------
    def _decode(self, audio, language, use_prompt):
        """Returns (text, info, score). score = mean avg_logprob (higher = more confident)."""
        if not use_prompt:
            prompt = None
        elif language:
            prompt = PROMPTS[language]
        else:
            prompt = PROMPTS["en"] + " " + PROMPTS["ar"]

        segments, info = self.model.transcribe(
            audio,
            language=language,
            beam_size=1,
            initial_prompt=prompt,
            temperature=0.0,                    # no slow retries
            condition_on_previous_text=False,   # less repetition
            vad_filter=True,                    # drop silence/noise before decoding
            vad_parameters={"min_silence_duration_ms": 300},
            max_new_tokens=MAX_NEW_TOKENS,
        )
        segs = list(segments)                   # `segments` is a generator: decoding happens HERE
        text = " ".join(s.text.strip() for s in segs).strip()
        logprobs = [s.avg_logprob for s in segs if hasattr(s, "avg_logprob")]
        score = float(np.mean(logprobs)) if logprobs else NO_SCORE
        if self._is_repetitive(text):           # hallucination loop -> discard
            text, score = "", NO_SCORE
        return text, info, score

    def transcribe(self, audio, language=None, use_prompt=False):
        """audio: path or array (16 kHz mono). language: None | 'ar' | 'en'.
        Returns (text, lang)."""
        audio = self._load(audio)
        self.last_candidates = []

        # 1) too short / too quiet -> do not even run the model
        if len(audio) < MIN_SECONDS * SAMPLE_RATE or self.rms(audio) < SILENCE_RMS:
            return "", language or "en"

        # 2) language given by the caller (fastest, most reliable)
        if language in ALLOWED_LANGS:
            text, _, score = self._decode(audio, language, use_prompt)
            self.last_candidates = [{"lang": language, "text": text, "score": score}]
            return text, language

        # 3a) auto, strategy "both": decode in each language, keep the more confident
        if self.auto_strategy == "both":
            cands = []
            for lang in ALLOWED_LANGS:
                text, _, score = self._decode(audio, lang, use_prompt)
                cands.append({"lang": lang, "text": text, "score": score})
            self.last_candidates = cands
            valid = [c for c in cands if c["text"]]
            if not valid:
                return "", "en"
            best = max(valid, key=lambda c: c["score"])
            return best["text"], best["lang"]

        # 3b) auto, strategy "whisper": trust Whisper's detection, restricted to ar/en
        text, info, score = self._decode(audio, None, use_prompt)
        lang = info.language
        if lang not in ALLOWED_LANGS:
            probs = dict(info.all_language_probs or [])
            lang = max(ALLOWED_LANGS, key=lambda l: probs.get(l, 0.0))
            text, _, score = self._decode(audio, lang, use_prompt)
        self.last_candidates = [{"lang": lang, "text": text, "score": score}]
        return text, lang


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "test.wav"
    forced = sys.argv[2] if len(sys.argv) > 2 else None     # 'ar' / 'en' / omit
    stt = SpeechToText("base")
    print(f"model loaded in {stt.load_seconds:.1f}s")
    t = time.perf_counter()
    text, lang = stt.transcribe(path, language=forced)
    print(f"[{lang}] {text!r}  ({time.perf_counter() - t:.2f}s)")
