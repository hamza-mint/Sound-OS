"""
audio/recorder.py - Microphone capture + simple energy-based VAD for Sound OS.

Output format (required by Whisper STT): 16 kHz, 16-bit PCM, mono WAV.

Backends (auto-selected, override with SOUNDOS_MIC_BACKEND=sounddevice|arecord):
    1. sounddevice (PortAudio)  - preferred
    2. arecord (ALSA CLI)       - fallback, needs `alsa-utils`

Optional environment variables:
    SOUNDOS_MIC_BACKEND   auto | sounddevice | arecord   (default: auto)
    SOUNDOS_MIC_DEVICE    sounddevice device index/name, or ALSA name for arecord
    SOUNDOS_MIN_RMS       minimum speech energy threshold (default: 300)

CONTRACT.md Rule 1: public functions here NEVER raise. On any failure
`record_utterance` still returns the path of a valid (silent) WAV file,
or "" as the very last resort.
"""

import math
import os
import subprocess
import sys
import tempfile
import time
import wave
from array import array
from collections import deque
from typing import List, Optional

SAMPLE_RATE = 16000          # Hz  (Whisper requirement)
CHANNELS = 1                 # mono
SAMPLE_WIDTH = 2             # bytes -> 16-bit PCM
BLOCK_MS = 30                # VAD analysis window
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000   # 480 samples

SILENCE_SECONDS = 1.0        # stop after this much silence once speech began
NO_SPEECH_TIMEOUT = 4.0      # give up if nobody speaks within this time
PREROLL_BLOCKS = 10          # ~300 ms kept from before speech was detected
TRAILING_KEEP_BLOCKS = 10    # ~300 ms of trailing silence kept in the file
START_BLOCKS = 3             # consecutive loud blocks required to start speech


def _log(msg: str) -> None:
    try:
        print(f"[audio] {msg}", file=sys.stderr)
    except Exception:
        pass


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return default


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def rms(buf: bytes) -> float:
    """Root-mean-square energy of a 16-bit little-endian PCM buffer."""
    try:
        samples = array("h")
        samples.frombytes(buf[: len(buf) - (len(buf) % 2)])
        if not samples:
            return 0.0
        return math.sqrt(sum(s * s for s in samples) / len(samples))
    except Exception:
        return 0.0


def compute_threshold(noise_levels: List[float]) -> float:
    """Derive a speech threshold from ambient-noise RMS measurements."""
    try:
        floor = _env_float("SOUNDOS_MIN_RMS", 300.0)
        if not noise_levels:
            return floor
        ordered = sorted(noise_levels)
        noise = ordered[len(ordered) // 4]          # 25th percentile
        return min(max(floor, noise * 3.0), 3000.0)
    except Exception:
        return 300.0


def write_wav(path: str, pcm: bytes) -> bool:
    """Write raw 16 kHz / 16-bit / mono PCM bytes to `path` as a WAV file."""
    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        return True
    except Exception as exc:
        _log(f"write_wav failed: {exc}")
        return False


def _new_wav_path() -> str:
    fd, path = tempfile.mkstemp(prefix="soundos_", suffix=".wav")
    os.close(fd)
    return os.path.abspath(path)


# --------------------------------------------------------------------------- #
# Microphone source
# --------------------------------------------------------------------------- #
class MicStream:
    """
    Blocking microphone reader yielding fixed-size blocks of int16 PCM bytes.

        with MicStream(480) as mic:
            block = mic.read()      # bytes, or None on failure
    """

    def __init__(self, block_samples: int = BLOCK_SAMPLES):
        self.block_samples = block_samples
        self.block_bytes = block_samples * SAMPLE_WIDTH
        self.backend = ""
        self._sd_stream = None
        self._proc: Optional[subprocess.Popen] = None

    # -- context manager ---------------------------------------------------- #
    def __enter__(self) -> "MicStream":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- open / close ------------------------------------------------------- #
    def open(self) -> bool:
        """Open the mic. Returns True on success; never raises."""
        choice = os.environ.get("SOUNDOS_MIC_BACKEND", "auto").lower()
        order = {
            "sounddevice": ["sounddevice"],
            "arecord": ["arecord"],
        }.get(choice, ["sounddevice", "arecord"])

        for name in order:
            try:
                ok = self._open_sounddevice() if name == "sounddevice" else self._open_arecord()
                if ok:
                    self.backend = name
                    return True
            except Exception as exc:
                _log(f"{name} backend unavailable: {exc}")
        self.backend = ""
        return False

    def _open_sounddevice(self) -> bool:
        import sounddevice as sd  # lazy: module may not be installed

        device = os.environ.get("SOUNDOS_MIC_DEVICE") or None
        if device is not None and device.isdigit():
            device = int(device)
        stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=self.block_samples,
            device=device,
        )
        stream.start()
        self._sd_stream = stream
        return True

    def _open_arecord(self) -> bool:
        cmd = ["arecord", "-q", "-t", "raw", "-f", "S16_LE",
               "-r", str(SAMPLE_RATE), "-c", str(CHANNELS)]
        device = os.environ.get("SOUNDOS_MIC_DEVICE")
        if device:
            cmd += ["-D", device]
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0
        )
        time.sleep(0.15)
        if self._proc.poll() is not None:        # exited immediately -> failed
            self._proc = None
            return False
        return True

    def close(self) -> None:
        try:
            if self._sd_stream is not None:
                self._sd_stream.stop()
                self._sd_stream.close()
        except Exception:
            pass
        self._sd_stream = None
        try:
            if self._proc is not None:
                self._proc.terminate()
                self._proc.wait(timeout=1)
        except Exception:
            try:
                self._proc.kill()  # type: ignore[union-attr]
            except Exception:
                pass
        self._proc = None

    # -- read --------------------------------------------------------------- #
    def read(self) -> Optional[bytes]:
        """Return exactly one block of PCM bytes, or None on failure/EOF."""
        try:
            if self._sd_stream is not None:
                data, _overflow = self._sd_stream.read(self.block_samples)
                return bytes(data)
            if self._proc is not None and self._proc.stdout is not None:
                buf = b""
                while len(buf) < self.block_bytes:
                    chunk = self._proc.stdout.read(self.block_bytes - len(buf))
                    if not chunk:
                        return None
                    buf += chunk
                return buf
        except Exception as exc:
            _log(f"mic read failed: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def record_utterance(
    max_seconds: float = 6.0,
    silence_seconds: float = SILENCE_SECONDS,
) -> str:
    """
    Record one spoken utterance and save it as a 16 kHz mono 16-bit WAV.

    Recording starts when speech is detected and stops after `silence_seconds`
    of silence, or when `max_seconds` have elapsed in total. Returns the
    absolute path of a temporary WAV file. Never raises.
    """
    try:
        return _record_utterance(float(max_seconds), float(silence_seconds))
    except Exception as exc:
        _log(f"record_utterance error: {exc}")
        return _silent_wav()


def _silent_wav(seconds: float = 0.5) -> str:
    """Valid silent WAV used as a safe fallback. Returns '' if even that fails."""
    try:
        path = _new_wav_path()
        pcm = b"\x00\x00" * int(SAMPLE_RATE * seconds)
        return path if write_wav(path, pcm) else ""
    except Exception:
        return ""


def _record_utterance(max_seconds: float, silence_seconds: float) -> str:
    if max_seconds <= 0:
        return _silent_wav()

    max_blocks = max(1, int(max_seconds * 1000 / BLOCK_MS))
    silence_blocks = max(1, int(silence_seconds * 1000 / BLOCK_MS))
    no_speech_blocks = int(min(NO_SPEECH_TIMEOUT, max_seconds) * 1000 / BLOCK_MS)
    calib_blocks = min(10, max_blocks)                       # ~300 ms

    preroll: deque = deque(maxlen=PREROLL_BLOCKS)
    frames: List[bytes] = []
    noise_levels: List[float] = []
    threshold = 300.0
    started = False
    loud_run = 0
    silent_run = 0
    stopped_on_silence = False

    mic = MicStream(BLOCK_SAMPLES)
    if not mic.open():
        _log("no working microphone backend (install sounddevice or alsa-utils)")
        return _silent_wav()

    try:
        for i in range(max_blocks):
            block = mic.read()
            if block is None:
                break
            level = rms(block)

            # 1) Calibrate ambient noise from the first few blocks.
            if i < calib_blocks:
                noise_levels.append(level)
                preroll.append(block)
                if i == calib_blocks - 1:
                    threshold = compute_threshold(noise_levels)
                continue

            loud = level > threshold

            # 2) Waiting for the user to start talking.
            if not started:
                preroll.append(block)
                loud_run = loud_run + 1 if loud else 0
                if loud_run >= START_BLOCKS:
                    started = True
                    frames = list(preroll)
                    silent_run = 0
                elif i >= no_speech_blocks:
                    break                                    # nobody spoke
                continue

            # 3) Recording speech until enough trailing silence.
            frames.append(block)
            silent_run = 0 if loud else silent_run + 1
            if silent_run >= silence_blocks:
                stopped_on_silence = True
                break
    finally:
        mic.close()

    if not started:
        frames = list(preroll)           # nothing heard: keep short ambient clip
    elif stopped_on_silence:
        trim = silent_run - TRAILING_KEEP_BLOCKS
        if trim > 0:
            frames = frames[:-trim]

    pcm = b"".join(frames) or (b"\x00\x00" * BLOCK_SAMPLES)
    path = _new_wav_path()
    if not write_wav(path, pcm):
        return _silent_wav()
    return path
