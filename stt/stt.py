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
import math
import os
import re
import time

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
ALLOWED_LANGS = ("ar", "en")     # the only languages the project supports

# ONE concise domain-rich prompt per language to guide vocabulary and punctuation
PROMPTS = {
    "ar": "ديف، افتح المتصفح، اقفل المتصفح، اقفل التطبيق، اقفلي، سكر، علي الصوت، وطي الصوت، خفف الصوت، اكتم، شغل موسيقى، افتح الآلة الحاسبة، افتح الملفات، اقفل، ابحث عن، ارسل رسالة، افتح الترمينال، اعلي السطوع، وطي الإضاءة، افتحلي، ابعت رسالة.",
    "en": "Hey Dave, open the browser, close the browser, close the app, turn up volume, lower volume, mute, play music, open calculator, open files, close, search, send message, open terminal.",
}

SILENCE_RMS = 0.003    # gate for (almost) digital silence; VAD handles real noise
_FOREIGN_SCRIPT = re.compile("[\u0370-\u03FF\u0400-\u04FF\u0530-\u058F\u0590-\u05FF\u0900-\u0DFF\u0E00-\u0EFF\u10A0-\u10FF\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF]")
def _beam_size():
    """Beam search width for COMMAND decoding. 5 is Whisper's own default; 1 (greedy) is faster but makes more
    mistakes. Measured here (tiny/base, 40 clips, synthetic voice): total correct 19 -> 25 (tiny) and
    15 -> 17..23 (base) going from beam 1 to 5, for ~+0.15 s. SOUNDOS_STT_BEAM=1 restores the old speed.
    The wake-word decode stays at 1 (it runs all the time)."""
    try:
        return max(1, min(10, int(os.environ.get("SOUNDOS_STT_BEAM", "5"))))
    except ValueError:
        return 5


MIN_SECONDS = 0.3      # shorter than this -> ignore
MAX_WORDS_PER_SECOND = 2.5   # generous for isolated spoken commands; see trim_to_speech


_HALLUCINATIONS = (
    "thanks for watching", "thank you for watching", "subtitles by", "amara org", "please subscribe",
    "like and subscribe", "شكرا للمشاهده", "شكرا لمشاهدتكم", "شكرا علي المشاهده", "اشتركوا في القناه",
    "اشترك في القناه", "ترجمه نانسي قنقر",
)


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
        """Path or array or bytes -> mono float32 in [-1, 1].
        Files are read with soundfile (NOT PyAV) to avoid the
        'metadata_errors' incompatibility seen with faster-whisper + av."""
        if isinstance(audio, (bytes, bytearray)):
            return np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        if hasattr(audio, "__fspath__") or isinstance(audio, str):
            audio, sr = sf.read(str(audio), dtype="float32")
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

    @staticmethod
    def voiced_seconds(audio):
        """Seconds of audio that really contain sound (20 ms frames well above the noise floor).
        Used only to sanity-check how many words the clip can hold."""
        n = int(0.02 * SAMPLE_RATE)
        if len(audio) < n:
            return len(audio) / SAMPLE_RATE
        frames = audio[: len(audio) // n * n].reshape(-1, n)
        level = np.sqrt(np.mean(frames ** 2, axis=1))
        loud = level > max(2 * SILENCE_RMS, 0.10 * float(level.max()))
        return float(loud.sum()) * 0.02 + 0.1      # +0.1 s: soft word endings fall below the threshold

    @staticmethod
    def has_foreign_script(text):
        """True if the text contains Greek/Cyrillic/Hebrew/Indic/Thai/Chinese/Japanese/Korean letters. Whisper writes
        those when it hallucinates on noise (real log: '還不算是'); a command is only Arabic or Latin."""
        return bool(_FOREIGN_SCRIPT.search(text))

    @staticmethod
    def is_hallucination(text):
        """True if the text contains common YouTube/subtitle artifacts that Whisper hallucinates on noise."""
        if not text:
            return False
        norm = text.lower().replace("ة", "ه").replace("ى", "ي").strip()
        return any(h in norm for h in _HALLUCINATIONS)

    @staticmethod
    def dedupe_repeats(text):
        """'Open calculator, open calculator.' -> 'Open calculator,'  (Whisper repeating the same clause).
        Only identical neighbouring clauses are merged, so two different commands are untouched."""
        parts = re.split(r"(?<=[،,.؟?!])\s+", text.strip())
        kept, last = [], None
        for part in parts:
            key = " ".join(re.findall(r"[^\W_]+", part.lower()))
            if key and key == last:
                continue
            kept.append(part)
            last = key or last
        return " ".join(kept)

    @staticmethod
    def trim_to_speech(text, voiced_seconds):
        """Cut words the audio cannot contain (prompt leakage).

        With a command-list prompt Whisper sometimes keeps going after the real command and writes
        other prompt words ("..., افتح الترمينال، وطي الإضاءة"). The parser would then run the WRONG
        command. A short clip cannot hold that many words, so keep whole clauses (split by ، , . ؟ ?)
        only while they fit in about MAX_WORDS_PER_SECOND; the first clause is always kept.
        Missing a 2nd command is safe (the user repeats it); executing an invented one is not."""
        clauses = [c.strip() for c in re.split(r"[،,.؟?!؛;]+", text) if c.strip()]
        if len(clauses) < 2:
            return text
        allowed = max(len(clauses[0].split()), math.ceil(voiced_seconds * MAX_WORDS_PER_SECOND))
        kept, words = [], 0
        for c in clauses:
            n = len(c.split())
            if kept and words + n > allowed:
                break
            kept.append(c)
            words += n
        return text if len(kept) == len(clauses) else "، ".join(kept)

    # ---------- decoding ----------
    def _decode(self, audio, language, use_prompt, custom_prompt=None):
        if custom_prompt is not None:
            prompt = custom_prompt
        elif not use_prompt:
            prompt = None
        elif language:
            prompt = PROMPTS[language]
        else:
            prompt = PROMPTS["en"] + " " + PROMPTS["ar"]

        segments, info = self.model.transcribe(
            audio,
            language=language,
            beam_size=_beam_size(),   # 5 by default: see _beam_size()
            initial_prompt=prompt,
            temperature=0.0,                    # no slow retries
            condition_on_previous_text=False,   # less repetition
            vad_filter=True,                    # drop silence/noise before decoding
            vad_parameters={"min_silence_duration_ms": 300},
            max_new_tokens=96,                  # support compound/longer commands without truncation
            no_repeat_ngram_size=3,             # completely prevent repetitive hallucination loops
            repetition_penalty=1.2,
        )
        # `segments` is a generator: the real decoding happens in this line
        text = " ".join(s.text.strip() for s in segments).strip()
        if self._is_repetitive(text) or self.has_foreign_script(text) or self.is_hallucination(text):
            text = ""
        elif text:
            text = self.trim_to_speech(self.dedupe_repeats(text), self.voiced_seconds(audio))
        return text, info

    def transcribe(self, audio, language=None, use_prompt=True, prompt=None):
        """audio: path or array (16 kHz mono). language: None | 'ar' | 'en'.
        Returns (text, lang)."""
        import os
        audio = self._load(audio)
        self.last_candidates = []        # what the auto-detect step produced (used by run_live.py to show it)

        # 1) too short / too quiet -> do not even run the model
        if len(audio) < MIN_SECONDS * SAMPLE_RATE or self.rms(audio) < SILENCE_RMS:
            return "", language or "en"

        # 1b) check environment language override if caller did not specify
        if not language:
            env_lang = os.environ.get("SOUNDOS_LANG", "").lower().strip()
            if env_lang in ALLOWED_LANGS:
                language = env_lang

        # 2) language given by the caller or env
        if language in ALLOWED_LANGS:
            text, _ = self._decode(audio, language, use_prompt, custom_prompt=prompt)
            return text, language

        # 3) auto-detect, then restrict to ar/en
        text, info = self._decode(audio, None, use_prompt, custom_prompt=prompt)
        lang = info.language
        probs = dict(info.all_language_probs or [])
        if lang not in ALLOWED_LANGS:
            lang = max(ALLOWED_LANGS, key=lambda l: probs.get(l, 0.0))
            text, _ = self._decode(audio, lang, use_prompt, custom_prompt=prompt)
        self.last_candidates = [{"lang": lang, "text": text, "score": probs.get(lang)}]
        return text, lang

    def transcribe_wake(self, audio):
        """Ultra-fast wake phrase decoding optimized for sub-second wake response."""
        audio = self._load(audio)
        if len(audio) < 0.2 * SAMPLE_RATE or self.rms(audio) < SILENCE_RMS:
            return "", "en"

        prompt = "Hey Dave, Dave, ديف, دايف, يا ديف."
        segments, info = self.model.transcribe(
            audio,
            beam_size=1,
            temperature=0.0,
            initial_prompt=prompt,
            without_timestamps=True,
            max_new_tokens=20,
            condition_on_previous_text=False,
            repetition_penalty=1.2,
            no_repeat_ngram_size=2,
            # VAD ON: without it the prompt above is echoed on plain noise. Measured (tiny, 32 synthetic noise
            # clips): 31/32 false wakes ("Hey Dave, Dave.") with VAD off, 0/32 with VAD on, while the 15 spoken
            # "hey dave" clips were still all detected. Real session logs showed the same repeated false wakes.
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=200, min_silence_duration_ms=100),
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        if self._is_repetitive(text) or self.has_foreign_script(text) or self.is_hallucination(text):
            text = ""
        lang = info.language if info and info.language in ALLOWED_LANGS else "en"
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
