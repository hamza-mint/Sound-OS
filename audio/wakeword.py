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
import select
import sys
import time
from typing import Optional

from .recorder import SAMPLE_WIDTH, MicStream, compute_threshold, rms

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
            # Pretrained models may need a one-time download (needs internet).
            if not os.path.isfile(spec):
                from openwakeword.utils import download_models
                download_models([spec])
            _oww_model = build()
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
# Energy / Enter fallback
# --------------------------------------------------------------------------- #
def _wait_energy_or_enter() -> bool:
    """Wake on sustained loud audio or Enter. Returns False if mic unavailable."""
    mic = MicStream(WAKE_BLOCK_SAMPLES)
    if not mic.open():
        return False
    _log("Wake word not configured - make a loud sound or press Enter...")
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
        if _wait_energy_or_enter():
            return
        _wait_enter_only()
    except Exception as exc:
        _log(f"wait_for_wake_word error: {exc}")
        try:
            time.sleep(0.5)
        except Exception:
            pass
