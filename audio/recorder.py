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
from typing import List, Optional, Any

import numpy as np

SAMPLE_RATE = 16000          # Hz  (Whisper requirement)
CHANNELS = 1                 # mono
SAMPLE_WIDTH = 2             # bytes -> 16-bit PCM
BLOCK_MS = 30                # VAD analysis window
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000   # 480 samples

SILENCE_SECONDS = 0.65        # stop after ~650ms of silence once speech began (fast response)
NO_SPEECH_TIMEOUT = 4.0      # give up if nobody speaks within this time
PREROLL_BLOCKS = 14          # ~420 ms kept from before speech was detected (never clip first syllable)
TRAILING_KEEP_BLOCKS = 8     # ~240 ms of trailing silence kept in the file
START_BLOCKS = 2             # consecutive loud blocks required to start speech (fast trigger)
CONTINUE_RATIO = 0.6         # once speaking, only energy below 60% of the start threshold counts as silence
                             # (soft endings like the final ح/ه/ع in Arabic must not end the recording early)
QUIET_PEAK = 8192            # clips whose loudest sample is below 25% of full scale get lifted ...
TARGET_PEAK = 16384          # ... to about 50% of full scale (-6 dBFS) ...
MAX_GAIN = 8.0               # ... but never by more than 8x (+18 dB), so noise is not blown up


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
        # Drop highest spike if hardware pop occurred on stream startup
        clean = ordered[:-1] if len(ordered) > 4 else ordered
        noise = clean[len(clean) // 4]          # 25th percentile
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


class _Resampler:
    """Streaming sample-rate converter (numpy only): low-pass FIR first, then linear interpolation.

    Why: just taking every 3rd sample (48 kHz -> 16 kHz) folds everything above 8 kHz back into the
    speech band (aliasing). Arabic sibilants (س ش ص ز) carry energy up to 8-10 kHz, so they get
    corrupted exactly where Whisper listens. The FIR cuts at 7.2 kHz before picking samples.
    State is kept between blocks, so there is no click at block borders.
    """
    TAPS = 63

    def __init__(self, src: int, dst: int = SAMPLE_RATE):
        self.step = src / float(dst)
        fc = 0.45 * dst / float(src)                      # cutoff in cycles/sample (= 0.45 * dst Hz)
        n = np.arange(self.TAPS) - (self.TAPS - 1) / 2.0
        h = 2 * fc * np.sinc(2 * fc * n) * np.blackman(self.TAPS)
        self.h = h / h.sum()                              # DC gain exactly 1
        self.hist: Optional[np.ndarray] = None            # last TAPS-1 input samples
        self.buf = np.zeros(0)                            # filtered samples not consumed yet
        self.pos = 0.0                                    # where the next output sample sits in buf

    def process(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        if x.size == 0:
            return np.zeros(0)
        if self.hist is None:                             # start in steady state: no ramp-up artefact
            self.hist = np.full(self.TAPS - 1, x[0])
        joined = np.concatenate([self.hist, x])
        y = np.convolve(joined, self.h, mode="valid")     # len(y) == len(x)
        self.hist = joined[-(self.TAPS - 1):]
        buf = np.concatenate([self.buf, y])
        last = len(buf) - 1
        n_out = int(math.floor((last - self.pos) / self.step)) + 1 if last >= self.pos else 0
        out = np.interp(self.pos + np.arange(n_out) * self.step, np.arange(len(buf)), buf)
        nxt = self.pos + n_out * self.step
        drop = int(math.floor(nxt))
        self.buf = buf[drop:]
        self.pos = nxt - drop
        return out


def polish_pcm(pcm: bytes) -> bytes:
    """Clean a finished utterance before STT: remove DC offset, lift a very quiet recording.
    Quiet laptop mics are a common cause of wrong Arabic transcripts. Never clips. SOUNDOS_NORMALIZE=0 skips it."""
    try:
        if os.environ.get("SOUNDOS_NORMALIZE", "1") == "0" or len(pcm) < 2:
            return pcm
        x = np.frombuffer(pcm[: len(pcm) - (len(pcm) % 2)], dtype=np.int16).astype(np.float64)
        x -= x.mean()
        peak = float(np.abs(x).max())
        if peak >= 32000:
            _log("mic is clipping (too loud): lower the input gain in pavucontrol / system sound settings")
        elif 0 < peak < QUIET_PEAK:
            x *= min(TARGET_PEAK / peak, MAX_GAIN)
        return np.clip(np.rint(x), -32768, 32767).astype(np.int16).tobytes()
    except Exception as exc:
        _log(f"polish_pcm skipped: {exc}")
        return pcm


# --------------------------------------------------------------------------- #
# Microphone source
# --------------------------------------------------------------------------- #
class MicStream:
    """
    Blocking microphone reader yielding fixed-size blocks of int16 PCM bytes (16 kHz mono).

        with MicStream(480) as mic:
            block = mic.read()      # bytes, or None on failure

    Automatically handles laptop hardware constraints:
      - Adapts when hardware rejects 16 kHz mono (common on Realtek/AMD/Intel laptop mics).
      - Opens at hardware native rate (e.g. 44.1 kHz or 48 kHz stereo) and downsamples
        on-the-fly to 16 kHz 16-bit mono in microseconds.
      - Probes all available audio input devices (virtual and hardware) if default fails.
      - Falls back to `arecord` CLI if PortAudio/sounddevice is unavailable.
    """

    def __init__(self, block_samples: int = BLOCK_SAMPLES):
        self.block_samples = block_samples
        self.block_bytes = block_samples * SAMPLE_WIDTH
        self.backend = ""
        self.device_name = ""
        self._sd_stream = None
        self._proc: Optional[subprocess.Popen] = None
        self._downsample = False
        self._native_sr = SAMPLE_RATE
        self._native_channels = CHANNELS
        self._native_block_samples = block_samples
        self._resampler: Optional[_Resampler] = None
        self._pending = np.zeros(0)                  # converted samples waiting to fill the next block

    # -- context manager ---------------------------------------------------- #
    def __enter__(self) -> "MicStream":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- open / close ------------------------------------------------------- #
    def open(self) -> bool:
        """Open the mic. Returns True on success; never raises."""
        self._resampler = None
        self._pending = np.zeros(0)
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

    def _find_sd_candidate_devices(self, sd) -> List[Any]:
        """Find and prioritize available sounddevice input devices."""
        candidates = []
        user_dev = os.environ.get("SOUNDOS_MIC_DEVICE")

        # 1. User-specified device from env
        if user_dev is not None and user_dev.strip():
            user_dev = user_dev.strip()
            if user_dev.isdigit():
                candidates.append(int(user_dev))
            else:
                # Substring match on device name
                try:
                    for idx, dev in enumerate(sd.query_devices()):
                        if user_dev.lower() in dev.get("name", "").lower():
                            candidates.append(idx)
                            break
                except Exception:
                    pass

        # 2. System default device (if valid input)
        try:
            default_in = sd.default.device[0]
            if default_in is not None and default_in >= 0:
                dev_info = sd.query_devices(default_in)
                if dev_info.get("max_input_channels", 0) > 0:
                    candidates.append(default_in)
        except Exception:
            pass

        # 3. Enumerate all audio input devices
        virtual_devs = []
        hw_devs = []
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    name = dev.get("name", "").lower()
                    # Virtual sound servers (pipewire, pulse, default) prioritize cleanly
                    if any(v in name for v in ("pipewire", "pulse", "default")):
                        virtual_devs.append(idx)
                    else:
                        hw_devs.append(idx)
        except Exception:
            pass

        # Order: user preference -> system default -> virtual servers -> hardware devices -> None (default)
        all_ordered = candidates + virtual_devs + hw_devs + [None]
        seen = set()
        deduped = []
        for d in all_ordered:
            if d not in seen:
                seen.add(d)
                deduped.append(d)
        return deduped

    def _open_sounddevice(self) -> bool:
        try:
            import sounddevice as sd
        except ImportError:
            return False

        candidate_devices = self._find_sd_candidate_devices(sd)

        for dev in candidate_devices:
            # Query info about this device if possible
            dev_info = {}
            if dev is not None:
                try:
                    dev_info = sd.query_devices(dev)
                    if dev_info.get("max_input_channels", 0) <= 0:
                        continue
                except Exception:
                    pass

            dev_name = dev_info.get("name", f"device #{dev}" if dev is not None else "default")
            native_sr = int(dev_info.get("default_samplerate", 44100))
            max_ch = int(dev_info.get("max_input_channels", 2))

            # Attempt A: Direct 16000 Hz Mono (optimal zero-overhead path)
            try:
                stream = sd.RawInputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=self.block_samples,
                    device=dev,
                )
                stream.start()
                self._sd_stream = stream
                self._downsample = False
                self._native_sr = SAMPLE_RATE
                self._native_channels = CHANNELS
                self._native_block_samples = self.block_samples
                self.device_name = f"{dev_name} (16kHz mono native)"
                return True
            except Exception as e_direct:
                _log(f"Direct 16kHz mono failed on {dev_name}: {e_direct}; attempting laptop rate adaptation...")

            # Attempt B: Laptop Hardware-Rate & Stereo Adaptation
            candidate_rates = [native_sr, 48000, 44100, 32000]
            candidate_channels = [min(2, max_ch), 1]
            # Deduplicate rates
            candidate_rates = list(dict.fromkeys([r for r in candidate_rates if r >= 8000]))

            for sr in candidate_rates:
                for ch in candidate_channels:
                    try:
                        native_block = max(1, int(round(self.block_samples * sr / SAMPLE_RATE)))
                        stream = sd.RawInputStream(
                            samplerate=sr,
                            channels=ch,
                            dtype="int16",
                            blocksize=native_block,
                            device=dev,
                        )
                        stream.start()
                        self._sd_stream = stream
                        self._downsample = (sr != SAMPLE_RATE or ch != CHANNELS)
                        self._native_sr = sr
                        self._native_channels = ch
                        self._native_block_samples = native_block
                        self.device_name = f"{dev_name} ({sr}Hz {ch}ch -> 16kHz mono software adapted)"
                        _log(f"Configured laptop mic: {self.device_name}")
                        return True
                    except Exception:
                        continue

        return False

    def _open_arecord(self) -> bool:
        devices_to_try = []
        user_dev = os.environ.get("SOUNDOS_MIC_DEVICE")
        if user_dev:
            devices_to_try.append(user_dev)
        devices_to_try.extend(["default", "pulse", "pipewire", "plughw:0,0", "plughw:1,0", "sysdefault"])

        for dev in devices_to_try:
            cmd = ["arecord", "-q", "-t", "raw", "-f", "S16_LE",
                   "-r", str(SAMPLE_RATE), "-c", str(CHANNELS), "-D", dev]
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0
                )
                time.sleep(0.12)
                if proc.poll() is None:
                    self._proc = proc
                    self.device_name = f"arecord ({dev})"
                    return True
                else:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            except Exception:
                continue
        return False

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
        """Return exactly one block of 16 kHz 16-bit mono PCM bytes (480 samples = 960 bytes)."""
        try:
            if self._sd_stream is not None:
                if not self._downsample:
                    data, _overflow = self._sd_stream.read(self.block_samples)
                    return bytes(data)

                # Hardware adaptation: read native rate/channels, average channels, band-limit + resample
                if self._resampler is None or abs(self._resampler.step - self._native_sr / SAMPLE_RATE) > 1e-9:
                    self._resampler = _Resampler(self._native_sr) if self._native_sr != SAMPLE_RATE else None
                    self._pending = np.zeros(0)
                for _ in range(4):                       # normally 1 read; extra only to fill rounding gaps
                    raw_bytes, _overflow = self._sd_stream.read(self._native_block_samples)
                    if not raw_bytes:
                        return None
                    arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float64)
                    if self._native_channels > 1:
                        # average ALL channels (a mic array may have one dead/quiet channel)
                        arr = arr[: len(arr) // self._native_channels * self._native_channels]
                        arr = arr.reshape(-1, self._native_channels).mean(axis=1)
                    conv = self._resampler.process(arr) if self._resampler is not None else arr
                    self._pending = np.concatenate([self._pending, conv])
                    if len(self._pending) >= self.block_samples:
                        break

                block, self._pending = self._pending[: self.block_samples], self._pending[self.block_samples:]
                out = np.clip(np.rint(block), -32768, 32767).astype(np.int16).tobytes()
                if len(out) < self.block_bytes:
                    out = out + b"\x00" * (self.block_bytes - len(out))
                return out

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
    silence_seconds: Optional[float] = None,
) -> str:
    """
    Record one spoken utterance and save it as a 16 kHz mono 16-bit WAV.

    Recording starts when speech is detected and stops after `silence_seconds`
    of silence, or when `max_seconds` have elapsed in total. Returns the
    absolute path of a temporary WAV file. Never raises.
    """
    try:
        if silence_seconds is None:
            silence_seconds = _env_float("SOUNDOS_SILENCE_SECONDS", SILENCE_SECONDS)
        return _record_utterance(float(max_seconds), float(silence_seconds))
    except Exception as exc:
        _log(f"record_utterance error: {exc}")
        return _silent_wav()


def record_wake_clip(max_seconds: float = 1.4, silence_seconds: float = 0.22) -> str:
    """Ultra-fast recorder for wake-phrase detection (short window, fast trigger)."""
    try:
        return _record_utterance(float(max_seconds), float(silence_seconds), is_wake=True)
    except Exception as exc:
        _log(f"record_wake_clip error: {exc}")
        return ""


def _silent_wav(seconds: float = 0.5) -> str:
    """Valid silent WAV used as a safe fallback. Returns '' if even that fails."""
    try:
        path = _new_wav_path()
        pcm = b"\x00\x00" * int(SAMPLE_RATE * seconds)
        return path if write_wav(path, pcm) else ""
    except Exception:
        return ""


def _record_utterance(max_seconds: float, silence_seconds: float, is_wake: bool = False) -> str:
    if max_seconds <= 0:
        return "" if is_wake else _silent_wav()

    max_blocks = max(1, int(max_seconds * 1000 / BLOCK_MS))
    silence_blocks = max(1, int(silence_seconds * 1000 / BLOCK_MS))
    no_speech_blocks = int(min(NO_SPEECH_TIMEOUT, max_seconds) * 1000 / BLOCK_MS)
    calib_blocks = min(4 if is_wake else 8, max_blocks)

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
        return "" if is_wake else _silent_wav()

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
            speaking = level > threshold * CONTINUE_RATIO    # hysteresis: easier to stay "speaking" than to start

            # 2) Waiting for the user to start talking.
            if not started:
                preroll.append(block)
                loud_run = loud_run + 1 if loud else 0
                if loud_run >= (1 if is_wake else START_BLOCKS):
                    started = True
                    frames = list(preroll)
                    silent_run = 0
                elif i >= no_speech_blocks:
                    break                                    # nobody spoke
                continue

            # 3) Recording speech until enough trailing silence.
            frames.append(block)
            silent_run = 0 if speaking else silent_run + 1
            if silent_run >= silence_blocks:
                stopped_on_silence = True
                break
    finally:
        mic.close()

    if not started:
        if is_wake:
            return ""                                        # no speech during wake listening: skip STT entirely
        frames = list(preroll)                               # keep short ambient clip for normal commands
    elif stopped_on_silence:
        trim = silent_run - TRAILING_KEEP_BLOCKS
        if trim > 0:
            frames = frames[:-trim]

    pcm = b"".join(frames) or (b"\x00\x00" * BLOCK_SAMPLES)
    if started:
        pcm = polish_pcm(pcm)                                # only real speech: never amplify an empty room
    path = _new_wav_path()
    if not write_wav(path, pcm):
        return "" if is_wake else _silent_wav()
    return path
