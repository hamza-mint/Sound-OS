"""
audio/wakeword.py - Lightweight wake-word detection for Sound OS.

Detection modes, tried in order:
    1. openwakeword  - if SOUNDOS_WAKEWORD_MODEL is set and the package works
    2. energy/Enter  - fallback: wakes on a sustained loud sound (voice/clap)
                       OR when the user presses Enter in the terminal
    3. Enter only    - if no microphone is usable

Optional environment variables:
    SOUNDOS_WAKEWORD_MODEL      openwakeword model name (e.g. "hey_jarvis")
                                or path to a .onnx/.tflite file. Unset -> fallback.
    SOUNDOS_WAKE_THRESHOLD      openwakeword score threshold   (default: 0.5)
    SOUNDOS_WAKE_ENERGY_RMS     fixed RMS threshold for energy fallback
                                (default: auto-calibrated from ambient noise)

CONTRACT.md Rule 1: wait_for_wake_word() NEVER raises. (KeyboardInterrupt is
deliberately not swallowed so Ctrl+C can still stop the program.)
"""

import os
import re
import select
import sys
import tempfile
import threading
import time
from typing import Optional

from .recorder import SAMPLE_WIDTH, MicStream, compute_threshold, rms, record_utterance

WAKE_BLOCK_SAMPLES = 1280        # 80 ms - frame size expected by openwakeword
ENERGY_TRIGGER_BLOCKS = 3        # ~240 ms of sustained loudness
CALIBRATION_BLOCKS = 8           # ~640 ms ambient measurement

_oww_model = None                # cached openwakeword model
_oww_failed = False              # don't retry loading after a failure


def _log(msg: str) -> None:
    try:
        print(f"[audio] {msg}", file=sys.stderr)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Enter-key helper
# --------------------------------------------------------------------------- #
def _enter_pressed() -> bool:
    """Non-blocking check for Enter on stdin (only when stdin is a TTY)."""
    try:
        if not sys.stdin or not sys.stdin.isatty():
            return False
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if ready:
            sys.stdin.readline()
            return True
    except Exception:
        pass
    return False


def _stdin_is_tty() -> bool:
    try:
        return bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# openwakeword
# --------------------------------------------------------------------------- #
def _load_oww():
    """Load (and cache) the openwakeword model. Returns None if unavailable."""
    global _oww_model, _oww_failed
    if _oww_model is not None or _oww_failed:
        return _oww_model

    spec = os.environ.get("SOUNDOS_WAKEWORD_MODEL", "").strip()
    if not spec:
        _oww_failed = True
        return None

    try:
        import openwakeword  # noqa: F401
        from openwakeword.model import Model

        def build():
            try:
                return Model(wakeword_models=[spec], inference_framework="onnx")
            except TypeError:
                return Model(wakeword_models=[spec])

        try:
            _oww_model = build()
        except Exception:
            # Try downloading if spec is a named model and download helper is available
            try:
                from openwakeword.utils import download_models
                download_models([spec])
                _oww_model = build()
            except Exception:
                _oww_model = None
        _log(f"openwakeword model loaded: {spec}")
    except Exception as exc:
        _log(f"openwakeword unavailable ({exc}); using fallback")
        _oww_model = None
        _oww_failed = True
    return _oww_model


def _wait_openwakeword(model) -> bool:
    """Block until the wake word fires. Returns False if mic/model failed."""
    import numpy as np

    try:
        threshold = float(os.environ.get("SOUNDOS_WAKE_THRESHOLD", "0.5"))
    except Exception:
        threshold = 0.5

    mic = MicStream(WAKE_BLOCK_SAMPLES)
    if not mic.open():
        return False
    _log("Listening for wake word... (press Enter to skip)")
    try:
        try:
            model.reset()
        except Exception:
            pass
        while True:
            block = mic.read()
            if block is None:
                return False
            frame = np.frombuffer(block, dtype=np.int16)
            scores = model.predict(frame)
            if any(float(v) >= threshold for v in scores.values()):
                return True
            if _enter_pressed():
                return True
    finally:
        mic.close()


# --------------------------------------------------------------------------- #
# Wake phrase detection via STT + Energy/Enter fallback
# --------------------------------------------------------------------------- #
def _is_wake_word(text: str) -> bool:
    """Check if recognized speech contains wake word trigger with robust phonetic & dialect support."""
    if not text:
        return False
    norm = text.lower().strip()
    clean = re.sub(r"[^\w\s\u0621-\u064A]", " ", norm)
    words = clean.split()

    # 1. Custom wake word from env
    custom = os.environ.get("SOUNDOS_WAKEWORD", "").lower().strip()
    if custom and custom in clean:
        return True

    # Check model name env (e.g. SOUNDOS_WAKEWORD_MODEL=hey_dave)
    model_env = os.environ.get("SOUNDOS_WAKEWORD_MODEL", "").lower().replace("_", " ").strip()
    if model_env and model_env in clean:
        return True

    # 2. Individual name tokens (English + Arabic speech variants of Dave)
    name_tokens = {
        "dave", "daves", "dev", "david", "dafe", "deaf", "day", "they", "theyve", "date",
        "ديف", "دايف", "ديب", "ديفيد", "ضيف", "الديف", "ديڤ", "داف", "ديفز"
    }
    if any(w in name_tokens for w in words):
        return True

    # 3. Substring match for 'dav' or 'ديف'
    if any("dav" in w or "ديف" in w or "ديڤ" in w for w in words):
        return True

    # 4. Phrasal triggers
    triggers = [
        "dave", "hey dave", "hay dave", "hi dave", "hello dave", "ok dave", "ya dave",
        "dev", "hey dev", "hay dev", "hi dev",
        "david", "hey david", "hay david", "hi david",
        "day", "hey day", "hay day",
        "jarvis", "hey jarvis", "hi jarvis",
        "sound os", "soundos",
        "ديف", "دايف", "هاي ديف", "هي ديف", "يا ديف", "الو ديف", "ياعم ديف", "يا عم ديف"
    ]
    if any(t in clean for t in triggers):
        return True

    # 5. Regex pattern matching (prefix + name)
    if re.search(r"\b(hey|hay|hi|ay|hello|ok|ya|yah)?\s*(dave|dev|david|dafe|day|date|deaf)\b", clean):
        return True
    if re.search(r"\b(هاي|هي|يا|الو|ياعم|يا عم)?\s*(ديف|دايف|ديب|ضيف|ديڤ)\b", clean):
        return True

    return False


_pending_command = None
_pending_audio = None                  # the clip that produced _pending_command (main.py may need a 2nd opinion on it)
_pending_lock = threading.Lock()


def get_pending_audio():
    """The audio (float32 array) behind the command returned by get_pending_command(), or None."""
    global _pending_audio
    with _pending_lock:
        audio = _pending_audio
        _pending_audio = None
        return audio


def get_pending_command() -> Optional[str]:
    """Retrieve and clear any command pre-captured during wake detection in a thread-safe way."""
    global _pending_command
    with _pending_lock:
        cmd = _pending_command
        _pending_command = None
        return cmd


def _extract_stt_text(res) -> str:
    """Safely extract transcript text whether STT returns dict, tuple, or string."""
    if isinstance(res, dict):
        return str(res.get("text", "") or "")
    if isinstance(res, (tuple, list)) and len(res) > 0:
        return str(res[0] or "")
    return str(res or "")


def _strip_wake_word(text: str) -> str:
    """Remove leading/trailing wake word phrases from text (e.g. 'Hey Dave open browser' -> 'open browser')."""
    norm = text.strip()
    patterns = [
        r"^(?:hey|hay|hi|ay|hello|ok|okay)?\s*(?:dave|dev|david|dafe|day)\s*[,.:\-]?\s*",
        r"^(?:هاي|هي|يا|الو)?\s*(?:ديف|دايف|ديب)\s*[,.:\-]?\s*",
        r"\s*[,.:\-]?\s*(?:hey|hay|hi|ay|hello|ok|okay)?\s*(?:dave|dev|david|dafe|day)$",
        r"\s*[,.:\-]?\s*(?:هاي|هي|يا|الو)?\s*(?:ديف|دايف|ديب)$",
    ]
    for p in patterns:
        norm = re.sub(p, "", norm, flags=re.IGNORECASE).strip()
    return norm


# Commands that must NEVER start from ambient speech (TV, a conversation, a hallucination): the user has to
# say "Hey Dave" first. Real log: 'Send the message.' was executed as a "direct command" with no wake word.
DIRECT_BLOCKED = {"shutdown", "delete_file", "send_message", "close_app"}
# close_app is only blocked when it would close "the current window" ("اقفل" alone is a very common Arabic word
# in conversation). Closing a NAMED app ("اقفل المتصفح") works without the wake word.
# SOUNDOS_DIRECT_ALLOW=close_app (comma list) lets you allow more yourself.


def _classify(text: str, full_decode=None):
    """Decide what a wake-listening clip is. Returns (kind, payload):
         ("wake", command_or_None)   "Hey Dave" (+ an optional command said in the same breath)
         ("direct", text)            a safe command said without the wake word
         ("needs_wake", (intent, text))  a risky command said without the wake word -> ignored
         ("heard", text)             nothing usable

    The first decode is the fast English-prompted wake decode. An Arabic command comes out of it as Latin
    gibberish ('Hoping down loads' for 'افتح التحميلات'), so if it is not a wake word we decode the same audio
    again with the full, language-aware decoder (`full_decode`) before giving up. SOUNDOS_NO_DIRECT=1 turns the
    no-wake-word mode off completely."""
    from intent_parser import parse
    if _is_wake_word(text):
        cmd = _strip_wake_word(text)
        return ("wake", cmd if cmd and parse(cmd)["intent"] != "unknown" else None)
    def verdict(cand):
        res = parse(cand)
        intent = res["intent"]
        if intent == "unknown":
            return None
        allowed = {x.strip() for x in os.environ.get("SOUNDOS_DIRECT_ALLOW", "").split(",") if x.strip()}
        risky = intent in DIRECT_BLOCKED - allowed
        if intent == "close_app" and res["params"].get("app") != "current":
            risky = False
        if risky or os.environ.get("SOUNDOS_NO_DIRECT") == "1":
            return ("needs_wake", (intent, cand))
        return ("direct", cand)

    first = verdict(text)
    if first:
        return first
    if full_decode is None:
        return ("heard", text)
    try:                                           # only now: the slower second decode
        second = full_decode()
    except Exception:
        second = ""
    if second and second != text:
        return verdict(second) or ("heard", second)
    return ("heard", text)


def _wait_phrase_or_enter() -> bool:
    """Wake on 'Hey Dave' / 'Hi Dave', combined wake+command, or direct command using continuous stream VAD."""
    global _pending_command, _pending_audio
    try:
        from stt import transcribe_wake, transcribe
    except Exception:
        transcribe_wake, transcribe = None, None

    # Fallback to pure energy mode if requested or if stt unavailable
    if transcribe is None or os.environ.get("SOUNDOS_WAKE_ENERGY_ONLY") == "1":
        return _wait_energy_or_enter()

    _log("Listening... Say 'Hey Dave' or speak a direct command (or press Enter)")
    from collections import deque
    from .recorder import MicStream, BLOCK_SAMPLES, BLOCK_MS, rms, compute_threshold
    import numpy as np

    mic = MicStream(BLOCK_SAMPLES)
    if not mic.open():
        return _wait_energy_or_enter()

    preroll = deque(maxlen=14)      # ~420 ms preroll buffer (never clip initial consonants)
    speech_frames = []
    started = False
    silent_run = 0
    noise_samples = []
    threshold = 300.0
    calibrated = False
    blocks_read = 0

    try:
        while True:
            if _enter_pressed():
                _log("Wake bypassed via Enter key.")
                return True

            block = mic.read()
            if block is None:
                return False

            blocks_read += 1
            if blocks_read <= 2:
                # Discard the very first 2 blocks (60 ms) to let hardware settle without pops
                continue

            level = rms(block)

            # Quick initial calibration (first 6 blocks = ~180 ms)
            if not calibrated:
                noise_samples.append(level)
                preroll.append(block)
                if len(noise_samples) >= 6:
                    threshold = compute_threshold(noise_samples)
                    calibrated = True
                continue

            # Continuously adapt background noise floor while idle, bounded to safe range [200.0, 800.0]
            if not started and level < threshold * 1.5:
                threshold = min(800.0, max(200.0, 0.98 * threshold + 0.02 * max(level * 1.5, 200.0)))

            loud = level > threshold

            if not started:
                preroll.append(block)
                if loud:
                    started = True
                    speech_frames = list(preroll)
                    silent_run = 0
                continue

            # Speech in progress: accumulate audio
            speech_frames.append(block)
            if not loud:
                silent_run += 1
            else:
                silent_run = 0

            # Utterance finished on trailing silence (~360 ms, configurable) or max duration (~2.2 s)
            try:
                wake_max_sec = float(os.environ.get("SOUNDOS_WAKE_MAX_SECONDS", "2.2"))
            except Exception:
                wake_max_sec = 2.2
            max_frames = int(wake_max_sec * 1000 / BLOCK_MS)
            wake_silence_blocks = int(os.environ.get("SOUNDOS_WAKE_SILENCE_BLOCKS", "12"))
            if silent_run >= wake_silence_blocks or len(speech_frames) >= max_frames:
                # Discard ultra-short click/noise spikes (< 240 ms = 8 blocks)
                if len(speech_frames) >= 8:
                    pcm = b"".join(speech_frames)
                    audio_arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
                    try:
                        res = transcribe_wake(audio_arr) if transcribe_wake else transcribe(audio_arr)
                        text = _extract_stt_text(res)
                        try:
                            from .debug_clips import save_clip
                            save_clip(audio_arr, text, "wake")      # only if SOUNDOS_SAVE_AUDIO is set
                        except Exception:
                            pass
                        if text:
                            kind, payload = _classify(text, lambda: _extract_stt_text(transcribe(audio_arr)))
                            if kind == "wake":
                                if payload:
                                    _log(f"Wake word + Command captured: '{text}' -> '{payload}' \U0001F680")
                                    with _pending_lock:
                                        _pending_command = payload
                                        _pending_audio = audio_arr
                                else:
                                    _log(f"Wake word matched: '{text}' \u2705")
                                return True
                            if kind == "direct":
                                _log(f"Direct command captured: '{payload}' \U0001F680")
                                with _pending_lock:
                                    _pending_command = payload
                                    _pending_audio = audio_arr
                                return True
                            if kind == "needs_wake":
                                _log(f"Heard '{payload[1]}' ({payload[0]}) - say 'Hey Dave' first for this one.")
                            else:
                                _log(f"Heard: '{payload}' (waiting for 'Hey Dave' or command)...")
                    except Exception as exc:
                        _log(f"STT check error: {exc}")

                # Reset to resume continuous listening without reopening the mic
                started = False
                speech_frames = []
                silent_run = 0
                preroll.clear()
    finally:
        mic.close()


def _wait_energy_or_enter() -> bool:
    """Wake on sustained loud audio or Enter. Returns False if mic unavailable."""
    mic = MicStream(WAKE_BLOCK_SAMPLES)
    if not mic.open():
        return False
    _log("Wake word waiting (make a loud sound or press Enter)...")
    try:
        threshold: Optional[float] = None
        fixed = os.environ.get("SOUNDOS_WAKE_ENERGY_RMS")
        if fixed:
            try:
                threshold = float(fixed)
            except Exception:
                threshold = None

        noise = []
        loud_run = 0
        while True:
            block = mic.read()
            if block is None:
                return False
            if _enter_pressed():
                return True
            level = rms(block)

            if threshold is None:                       # calibrate first
                noise.append(level)
                if len(noise) >= CALIBRATION_BLOCKS:
                    threshold = max(compute_threshold(noise) * 2.0, 600.0)
                continue

            loud_run = loud_run + 1 if level > threshold else 0
            if loud_run >= ENERGY_TRIGGER_BLOCKS:
                return True
    finally:
        mic.close()


def _wait_enter_only() -> None:
    """Last resort when there is no microphone."""
    if _stdin_is_tty():
        _log("No microphone available - press Enter to continue...")
        try:
            sys.stdin.readline()
            return
        except Exception:
            pass
    time.sleep(1.0)      # no mic and no TTY: avoid a busy loop in callers


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def wait_for_wake_word() -> None:
    """Block until the wake word (or fallback trigger) is detected. Never raises."""
    try:
        model = _load_oww()
        if model is not None:
            try:
                if _wait_openwakeword(model):
                    return
            except Exception as exc:
                _log(f"openwakeword loop failed: {exc}")
        if _wait_phrase_or_enter():
            return
        _wait_enter_only()
    except Exception as exc:
        _log(f"wait_for_wake_word error: {exc}")
        try:
            time.sleep(0.5)
        except Exception:
            pass

