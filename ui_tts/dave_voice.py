"""Dave's voice: text in, BMO-style speech out.

How it works
    1. Piper (offline) speaks each sentence.
    2. Dave's sound is added: pitched up, a light digital edge, a short pause between
       sentences, and a little silence at the start so speakers wake up in time.
    3. It plays in the background, so your program and Dave's animation never freeze.
    4. While it plays, the loudness of the speech is sent to Dave as a "mouth level"
       (0.0 - 1.0), so his mouth moves in time with the words, and what he says also
       appears in his speech bubble.

Needs:  pip install piper-tts numpy     and the Piper voice files (see find_voice below).
Playback: Windows uses winsound (built in); Linux uses paplay or aplay.

Public functions never raise (CONTRACT Rule 7). If something is missing (Piper, numpy,
the voice file, a sound player) Dave stays silent and one hint is printed, once.
"""

import hashlib
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave

try:
    import numpy as np
except Exception:                                  # speaking is switched off without numpy
    np = None

# ---------- Dave's voice (the settings you chose) ----------
VOICES = {"en": "en_US-lessac-medium"}             # language -> Piper voice (no Arabic voice yet)
SETTINGS = dict(
    pitch=3.0,         # semitones up (also a little faster)
    crush=2,           # keep every Nth sample: the "handheld console" edge
    bits=10,           # fewer volume steps = grittier
    smooth=2,          # softens the hiss
    wobble=0.15,       # volume flutter (0 = off)
    wobble_hz=9.0,
    pause=0.15,        # seconds of silence after each sentence (snappy)
    lead=0.02,         # minimal silence at start (fast response)
)
HOP = 0.02             # the mouth level is measured every 20 ms
BUBBLE = True          # also show what he says in his speech bubble

_q = queue.Queue()
_lock = threading.Lock()
_worker = None
_pending = 0           # utterances waiting or playing
_gen = 0               # bumps on stop_speaking(): anything older gets dropped
_listeners = []        # extra functions that want the mouth level, e.g. a demo
_warned = set()
_warm_lock = threading.Lock()   # warm-up phrases are made one at a time
_last_level = [-1.0, 0.0]     # last mouth level sent, and when

_loaded_voices = {}
_voice_lock = threading.Lock()

COMMON_PHRASES = (
    "Done!",
    "Opened chrome",
    "Opened firefox",
    "Opened terminal",
    "Opened files",
    "Closed current window",
    "Closed application.",
    "Volume increased.",
    "Volume decreased.",
    "Sound muted.",
    "Brightness increased.",
    "Brightness decreased.",
    "File created.",
    "File deleted.",
    "Searching for",
    "Playing media",
    "Cancelled.",
    "Shut down computer? Say yes or no.",
    "Command blocked for safety.",
    "Sorry, I did not understand that.",
    "Oops, that didn't work.",
)


def get_piper_voice(model_path):
    """Load and cache PiperVoice in-memory for ultra-fast, zero-overhead synthesis."""
    if not model_path:
        return None
    with _voice_lock:
        if model_path not in _loaded_voices:
            try:
                from piper import PiperVoice
                _loaded_voices[model_path] = PiperVoice.load(model_path)
            except Exception as e:
                _warn("piper_load", f"Could not load Piper in-memory ({e}); using CLI fallback.")
                return None
        return _loaded_voices.get(model_path)


def _warn(key, message):
    """Print a hint once, never raise."""
    try:
        if key not in _warned:
            _warned.add(key)
            print("[ui_tts voice] " + message, flush=True)
    except Exception:
        pass


# =====================================================================
#  Finding the voice files
# =====================================================================
def find_voice(name):
    """Path of <name>.onnx (its .onnx.json must sit next to it), or None.

    Looked for, in this order:
      $SOUNDOS_VOICE_DIR, <repo>/piper-voices, <repo>/models/piper,
      <repo>/../piper-voices, ~/piper-voices, and the current folder.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folders = []
    env = os.environ.get("SOUNDOS_VOICE_DIR")
    if env:
        folders.append(env)
    folders += [os.path.join(root, "piper-voices"),
                os.path.join(root, "models", "piper"),
                os.path.join(os.path.dirname(root), "piper-voices"),
                os.path.join(os.path.expanduser("~"), "piper-voices"),
                os.getcwd()]
    for folder in folders:
        model = os.path.join(folder, name + ".onnx")
        if os.path.isfile(model) and os.path.isfile(model + ".json"):
            return model
    return None


# =====================================================================
#  Making the speech
# =====================================================================
def _synth_sentence(sentence, model, out_path):
    """Ask Piper to speak one sentence into a WAV file via fast in-memory engine (or fallback)."""
    pv = get_piper_voice(model)
    if pv is not None:
        try:
            with wave.open(out_path, "wb") as wf:
                pv.synthesize_wav(sentence, wf)
            return
        except Exception:
            pass
    flags = 0x08000000 if sys.platform == "win32" else 0          # no console flash on Windows
    subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", out_path, "--", sentence],
                   check=True, capture_output=True, timeout=90, creationflags=flags)


def _read_wav(path):
    with wave.open(path, "rb") as w:
        rate, channels = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    return x, rate


def _write_wav(path, samples, rate):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())


def _dave_sound(x, rate, s):
    """Pitch up, crunch, smooth and wobble one sentence (float samples in, int16 out)."""
    n = max(2, int(len(x) / (2 ** (s["pitch"] / 12))))             # pitch up = read faster
    x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    crush = max(1, int(s["crush"]))
    if crush > 1:
        x = np.repeat(x[::crush], crush)[:n]                       # hold every Nth sample
    step = 2 ** (16 - int(min(16, max(2, s["bits"]))))
    x = np.round(x / step) * step                                  # fewer volume steps
    if s["smooth"] > 1:
        k = int(s["smooth"])
        x = np.convolve(x, np.ones(k) / k, mode="same")            # takes the hiss off
    if s["wobble"] > 0:
        t = np.arange(len(x)) / rate
        x = x * (1 - s["wobble"] * (0.5 + 0.5 * np.sin(2 * np.pi * s["wobble_hz"] * t)))
    peak = np.max(np.abs(x)) or 1.0
    return np.clip(x / peak * 30000, -32768, 32767).astype(np.int16)


def split_sentences(text):
    """'Hi. I am Dave! Ok?' -> ['Hi.', 'I am Dave!', 'Ok?']  (Piper only pauses at . ! ?)"""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip())]
    return [p for p in parts if p]


def _cache_path(text, voice_name):
    key = hashlib.sha1(f"{voice_name}|{sorted(SETTINGS.items())}|{text}".encode("utf-8")).hexdigest()
    folder = os.path.join(tempfile.gettempdir(), "soundos_dave_voice")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, key + ".wav")


_key_locks = {}
_key_guard = threading.Lock()


def _key_lock(path):
    with _key_guard:
        return _key_locks.setdefault(path, threading.Lock())


def render(text, lang="en"):
    """Dave saying `text`: returns (path of a WAV file, samples, sample rate), or None.

    Finished speech is kept in a cache folder, so a phrase he has said before is instant.
    """
    voice_name = VOICES.get((lang or "en")[:2].lower())
    if voice_name is None:
        _warn("lang-" + str(lang), f"No voice for language '{lang}' yet.")
        return None
    path = _cache_path(text, voice_name)
    with _key_lock(path):                       # the same phrase is only ever made once at a time
        if os.path.isfile(path):
            x, rate = _read_wav(path)
            return path, x.astype(np.int16), rate
        return _make(text, voice_name, path)


def _make(text, voice_name, path):
    model = find_voice(voice_name)
    if model is None:
        _warn("nofile", f"Voice file {voice_name}.onnx not found. Put it (with its .onnx.json) in a "
                        "'piper-voices' folder next to the repo, or set SOUNDOS_VOICE_DIR.")
        return None
    pieces, rate = [], None
    with tempfile.TemporaryDirectory() as tmp:
        for i, sentence in enumerate(split_sentences(text)):
            raw = os.path.join(tmp, f"s{i}.wav")
            _synth_sentence(sentence, model, raw)
            x, rate = _read_wav(raw)
            if pieces:
                pieces.append(np.zeros(int(rate * SETTINGS["pause"]), dtype=np.int16))
            pieces.append(_dave_sound(x, rate, SETTINGS))
    if rate is None:
        return None
    pieces.insert(0, np.zeros(int(rate * SETTINGS["lead"]), dtype=np.int16))
    samples = np.concatenate(pieces)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"     # write whole, then swap in: no half files
    _write_wav(tmp, samples, rate)
    os.replace(tmp, path)
    return path, samples, rate


def mouth_envelope(samples, rate):
    """How wide the mouth should be, 0.0 - 1.0, for every 20 ms of the speech."""
    n = max(1, int(rate * HOP))
    m = len(samples) // n
    if m == 0:
        return []
    x = samples[:m * n].astype(np.float32).reshape(m, n)
    rms = np.sqrt((x ** 2).mean(axis=1))
    top = float(np.percentile(rms, 95)) or 1.0
    env = np.clip(rms / top, 0.0, 1.0)
    return list(np.convolve(env, [0.25, 0.5, 0.25], mode="same"))   # a little smoothing: no flicker


# =====================================================================
#  Playing it, and telling the Daves how wide to open their mouths
# =====================================================================
class _Audio:
    """One WAV file playing in the background."""

    def __init__(self, path, seconds):
        self.proc, self.end, self.win = None, time.perf_counter() + seconds + 0.15, False
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.win = True
            return
        for cmd in (["paplay", path], ["aplay", "-q", path]):
            if shutil.which(cmd[0]):
                self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
        _warn("player", "No sound player found. Install one:  sudo apt install pulseaudio-utils alsa-utils")

    def alive(self):
        if self.proc is not None:
            return self.proc.poll() is None
        return self.win and time.perf_counter() < self.end

    def stop(self):
        try:
            if self.win:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            if self.proc is not None and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass


def _dave_desktop():
    """The desktop Dave module, if the program has loaded it (else None)."""
    return sys.modules.get((__package__ or "ui_tts") + ".dave_desktop")


def _mouth(level):
    """Tell Dave (and any listener) how open his mouth is."""
    level = round(float(level), 2)
    now = time.perf_counter()
    last, last_t = _last_level
    changed = abs(level - last) >= 0.02 or (level == 0.0) != (last == 0.0)
    if not changed and now - last_t < 0.15:
        return                                           # nothing new (he still gets a sign of life every 0.15 s)
    _last_level[0], _last_level[1] = level, now
    for fn in [getattr(_dave_desktop(), "set_mouth", None)] + list(_listeners):
        if callable(fn):
            try:
                fn(level)
            except Exception:
                pass


def _bubble(text, seconds):
    """Show `text` in Dave's speech bubble."""
    if not BUBBLE:
        return
    try:
        fn = getattr(_dave_desktop(), "say", None)
        if callable(fn):
            fn(text, seconds)
    except Exception:
        pass


def _play(samples_path, samples, rate, gen, text=""):
    seconds = len(samples) / rate
    env = mouth_envelope(samples, rate)
    audio = _Audio(samples_path, seconds)
    if not audio.alive():
        return
    _bubble(text, seconds + 0.3)
    t0 = time.perf_counter()
    try:
        while audio.alive() and gen == _gen:
            i = int((time.perf_counter() - t0) / HOP)
            _mouth(env[i] if 0 <= i < len(env) else 0.0)
            time.sleep(0.016)
    finally:
        if gen != _gen:
            audio.stop()                                 # interrupted by stop_speaking()
        _mouth(0.0)


def _run_worker():
    global _pending
    while True:
        text, lang, gen = _q.get()
        try:
            if gen == _gen:
                made = render(text, lang)
                if made is not None and gen == _gen:
                    _play(made[0], made[1], made[2], gen, text)
                elif made is None and gen == _gen:        # no sound possible: at least show the words
                    seconds = max(2.0, 0.07 * len(text))
                    _bubble(text, seconds)
                    end = time.perf_counter() + seconds
                    while time.perf_counter() < end and gen == _gen:
                        time.sleep(0.05)
        except Exception as e:
            _warn("fail", f"Could not speak ({type(e).__name__}: {e}). "
                          "Is piper-tts installed?  python -m pip install piper-tts")
        finally:
            with _lock:
                _pending -= 1


# =====================================================================
#  Public functions
# =====================================================================
def speak(text, lang="en") -> bool:
    """Dave says `text`. Returns at once; the speech plays in the background and also
    appears in his speech bubble. Several calls play one after the other.

    Returns False only if nothing at all can be done (numpy missing), so that the caller
    can fall back to printing. A language with no voice yet (e.g. Arabic) still shows the
    words in his bubble, silently."""
    global _pending, _worker
    try:
        if text is None:
            return True
        text = str(text).strip()
        if not text:
            return True
        if np is None:
            _warn("numpy", "numpy is missing, so Dave can't speak:  python -m pip install numpy")
            return False
        with _lock:
            _pending += 1
            if _worker is None or not _worker.is_alive():
                _worker = threading.Thread(target=_run_worker, daemon=True)
                _worker.start()
        _q.put((text, lang, _gen))
        return True
    except Exception:
        return False


def _warm_one(text, lang):
    try:
        with _warm_lock:
            render(text, lang)
    except Exception:
        pass


def warm(text, lang="en") -> None:
    """Get a phrase ready in the background (without playing it), so Dave can say it
    instantly later. Never raises."""
    try:
        text = str(text).strip()
        if text and np is not None:
            threading.Thread(target=_warm_one, args=(text, lang), daemon=True).start()
    except Exception:
        pass


def is_speaking() -> bool:
    """True from the moment speak() is called until the last word has played.
    The microphone code can use this to avoid listening to Dave himself."""
    try:
        return _pending > 0
    except Exception:
        return False


def stop_speaking() -> None:
    """Cut Dave off, close his speech bubble, and forget everything that was waiting."""
    global _gen
    try:
        _gen += 1
        fn = getattr(_dave_desktop(), "hush", None)
        if callable(fn):
            fn()
    except Exception:
        pass


def add_listener(fn) -> None:
    """Optional: fn(level) is called with the mouth level (0.0 - 1.0) while Dave speaks."""
    try:
        _listeners.append(fn)
    except Exception:
        pass