"""stt.py - Sound OS speech-to-text module (faster-whisper, CPU only, offline).

Usage:
    from stt import SpeechToText
    stt = SpeechToText("tiny")                  # load the model ONCE at startup
    text, lang = stt.transcribe("clip.wav")     # or a 16 kHz mono numpy array
    text, lang = stt.transcribe(audio, language="ar")   # force a language

Contract:
    input : path to a WAV file, or numpy array, 16 kHz mono
            (float32 in [-1, 1], or int16)
    output: (text, lang) where lang is "ar" or "en".
            text == "" means "no speech understood" -> the caller should ignore it.
"""
import time

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
ALLOWED_LANGS = ("ar", "en")     # the only languages the project supports

# ONE short sentence per language. A long list of command words caused
# repetition loops on silence during our tests.
PROMPTS = {
    "ar": "افتح المتصفح",
    "en": "Open the browser.",
}

SILENCE_RMS = 0.003    # gate for (almost) digital silence; VAD handles real noise
MIN_SECONDS = 0.3      # shorter than this -> ignore


class SpeechToText:
    def __init__(self, model_size="tiny", cpu_threads=0):
        """model_size: tiny | base | small | medium.
        cpu_threads=0 -> library default; measure on your machine
        (on a Ryzen 5 1600 explicit values 3-6 were tried)."""
        t0 = time.perf_counter()
        self.model = WhisperModel(model_size, device="cpu",
                                  compute_type="int8", cpu_threads=cpu_threads)
        self.load_seconds = time.perf_counter() - t0

    # ---------- helpers ----------
    @staticmethod
    def _load(audio):
        """Path or array -> mono float32 in [-1, 1].
        Files are read with soundfile (NOT PyAV) to avoid the
        'metadata_errors' incompatibility seen with faster-whisper + av."""
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
            max_new_tokens=24,                  # commands are short
        )
        # `segments` is a generator: the real decoding happens in this line
        text = " ".join(s.text.strip() for s in segments).strip()
        if self._is_repetitive(text):
            text = ""
        return text, info

    def transcribe(self, audio, language=None, use_prompt=True):
        """audio: path or array (16 kHz mono). language: None | 'ar' | 'en'.
        Returns (text, lang)."""
        audio = self._load(audio)

        # 1) too short / too quiet -> do not even run the model
        if len(audio) < MIN_SECONDS * SAMPLE_RATE or self.rms(audio) < SILENCE_RMS:
            return "", language or "en"

        # 2) language given by the caller
        if language in ALLOWED_LANGS:
            text, _ = self._decode(audio, language, use_prompt)
            return text, language

        # 3) auto-detect, then restrict to ar/en
        text, info = self._decode(audio, None, use_prompt)
        lang = info.language
        if lang not in ALLOWED_LANGS:
            probs = dict(info.all_language_probs or [])
            lang = max(ALLOWED_LANGS, key=lambda l: probs.get(l, 0.0))
            text, _ = self._decode(audio, lang, use_prompt)
        return text, lang


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "test.wav"
    forced = sys.argv[2] if len(sys.argv) > 2 else None     # 'ar' / 'en' / omit
    stt = SpeechToText("tiny")
    print(f"model loaded in {stt.load_seconds:.1f}s")
    t = time.perf_counter()
    text, lang = stt.transcribe(path, language=forced)
    print(f"[{lang}] {text!r}  ({time.perf_counter() - t:.2f}s)")
