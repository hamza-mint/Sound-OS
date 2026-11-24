"""Audio quality tests: anti-aliased resampling, channel averaging, VAD hysteresis, clip polish.
No microphone needed (synthetic signals + fake streams).   Run: pytest -q tests/test_audio_quality.py
"""
import wave

import numpy as np
import pytest

from audio import recorder
from audio.recorder import (BLOCK_SAMPLES, SAMPLE_RATE, SAMPLE_WIDTH, MicStream, _Resampler,
                            polish_pcm, _record_utterance)


def tone(freq, seconds, sr, amp=10000):
    t = np.arange(int(seconds * sr)) / sr
    return amp * np.sin(2 * np.pi * freq * t)


def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))


# ---------------------------------------------------------------- resampler
def test_old_method_aliases_but_new_resampler_does_not():
    """A 10 kHz hiss component (fricatives) at 48 kHz: naive [::3] folds it to 6 kHz at FULL strength."""
    x = tone(10000, 1.0, 48000)
    naive = x[::3]
    good = _Resampler(48000).process(x)[200:-200]           # skip filter edge
    assert rms(naive) > 0.9 * rms(x)                         # naive: alias is as loud as the original
    assert rms(good) < 0.03 * rms(x)                         # new: > 30 dB quieter


@pytest.mark.parametrize("sr", [48000, 44100, 32000])
def test_speech_band_passes_unchanged(sr):
    """1 kHz (well inside speech) keeps its level and its frequency."""
    x = tone(1000, 1.0, sr)
    y = _Resampler(sr).process(x)[300:-300]
    assert abs(rms(y) / rms(x) - 1) < 0.03
    spectrum = np.abs(np.fft.rfft(y))
    assert abs(np.argmax(spectrum) * SAMPLE_RATE / len(y) - 1000) < 10


@pytest.mark.parametrize("sr", [48000, 44100])
def test_streaming_blocks_equal_one_shot(sr):
    """No click at block borders: block-by-block output == whole-signal output."""
    x = tone(700, 1.0, sr) + tone(3100, 1.0, sr, amp=3000)
    whole = _Resampler(sr).process(x)
    r = _Resampler(sr)
    step = int(round(0.03 * sr))
    parts = np.concatenate([r.process(x[i:i + step]) for i in range(0, len(x) - step + 1, step)])
    n = min(len(whole), len(parts))
    assert n > 14000
    assert np.max(np.abs(whole[:n] - parts[:n])) < 1e-6


def test_constant_input_stays_constant_from_the_first_sample():
    y = _Resampler(44100).process(np.full(1323, 750.0))
    assert np.allclose(y, 750.0)


def test_output_length_does_not_drift():
    r = _Resampler(44100)
    total = sum(len(r.process(np.zeros(1323))) for _ in range(200))      # 200 x 30 ms
    assert abs(total - 200 * BLOCK_SAMPLES) <= 2


# ------------------------------------------------------------ MicStream.read
def make_mic(sr, channels, stream):
    mic = MicStream(BLOCK_SAMPLES)
    mic._downsample = True
    mic._native_sr = sr
    mic._native_channels = channels
    mic._native_block_samples = int(round(BLOCK_SAMPLES * sr / SAMPLE_RATE))
    mic._sd_stream = stream
    return mic


class FakeStream:
    def __init__(self, data):
        self.data, self.i = data, 0

    def read(self, n):
        chunk = self.data[self.i:self.i + n * self.channels]
        self.i += n * self.channels
        return chunk.astype(np.int16).tobytes(), False


def test_stereo_with_one_dead_channel_is_averaged_not_dropped():
    """Old code took channel 0 only. If that channel is silent the whole recording was silent."""
    left_dead = np.stack([np.zeros(48000 * 2), tone(500, 2.0, 48000)], axis=1).reshape(-1)
    s = FakeStream(left_dead); s.channels = 2
    mic = make_mic(48000, 2, s)
    out = np.concatenate([np.frombuffer(mic.read(), np.int16) for _ in range(20)])
    assert rms(out[100:]) > 2000


def test_every_read_returns_exactly_one_block_and_no_drift_at_44k():
    s = FakeStream(tone(500, 5.0, 44100)); s.channels = 1
    mic = make_mic(44100, 1, s)
    for _ in range(100):
        block = mic.read()
        assert block is not None and len(block) == BLOCK_SAMPLES * SAMPLE_WIDTH


# ------------------------------------------------------------ polish_pcm
def pcm(x):
    return np.asarray(x, dtype=np.int16).tobytes()


def test_polish_removes_dc_offset():
    x = tone(300, 0.5, SAMPLE_RATE, amp=6000) + 2500
    out = np.frombuffer(polish_pcm(pcm(x)), np.int16)
    assert abs(out.mean()) < 50


def test_polish_lifts_quiet_speech_but_caps_the_gain():
    quiet = tone(300, 0.5, SAMPLE_RATE, amp=1500)
    out = np.frombuffer(polish_pcm(pcm(quiet)), np.int16)
    assert 1.5 * np.abs(quiet).max() < np.abs(out).max() <= 8.0 * np.abs(quiet).max() + 2
    very_quiet = tone(300, 0.5, SAMPLE_RATE, amp=100)                    # gain limited to 8x, noise not exploded
    out2 = np.frombuffer(polish_pcm(pcm(very_quiet)), np.int16)
    assert np.abs(out2).max() <= 8 * 100 + 2


def test_polish_leaves_normal_and_loud_speech_alone():
    normal = tone(300, 0.5, SAMPLE_RATE, amp=12000)
    out = np.frombuffer(polish_pcm(pcm(normal)), np.int16)
    assert np.abs(out - normal).max() < 5                                # only DC (~0) removed
    loud = tone(300, 0.5, SAMPLE_RATE, amp=32500)
    out = np.frombuffer(polish_pcm(pcm(loud)), np.int16)
    assert np.abs(out).max() <= 32767


def test_polish_can_be_switched_off_and_never_raises(monkeypatch):
    data = pcm(tone(300, 0.2, SAMPLE_RATE, amp=500))
    monkeypatch.setenv("SOUNDOS_NORMALIZE", "0")
    assert polish_pcm(data) == data
    monkeypatch.delenv("SOUNDOS_NORMALIZE")
    assert polish_pcm(b"") == b""
    assert polish_pcm(b"\x01") == b"\x01"


# ------------------------------------------------- VAD hysteresis (fake mic)
class ScriptedMic:
    """Replaces MicStream: plays a list of block levels (RMS values), then ends."""
    levels = []

    def __init__(self, block_samples=BLOCK_SAMPLES):
        self.i = 0

    def open(self):
        return True

    def close(self):
        pass

    def read(self):
        if self.i >= len(self.levels):
            return None
        lvl = self.levels[self.i]; self.i += 1
        return pcm(np.full(BLOCK_SAMPLES, lvl))                           # constant block: RMS == lvl


def run_script(monkeypatch, levels, **kw):
    ScriptedMic.levels = levels
    monkeypatch.setattr(recorder, "MicStream", ScriptedMic)
    monkeypatch.setenv("SOUNDOS_NORMALIZE", "0")
    path = _record_utterance(10.0, kw.get("silence", 0.3))
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def test_soft_word_ending_does_not_cut_the_recording(monkeypatch):
    """Threshold is 300. A soft tail at 0.8x threshold (like a final ح or ه) is still speech,
    so the recording keeps going until real silence (the soft part lasts 0.45 s, longer than the 0.3 s silence limit)."""
    quiet = [50] * 8                                                     # calibration -> threshold = 300
    speech = [2000] * 10
    soft_tail = [200] * 15                                               # 200 > 0.6*300 = 180: still speaking
    more = [2000] * 10
    silence = [50] * 30
    with_tail = run_script(monkeypatch, quiet + speech + soft_tail + more + silence)
    cut_early = run_script(monkeypatch, quiet + speech + [100] * 15 + more + silence)   # 100 < 180: real pause
    assert with_tail > cut_early + 0.25                                  # the "more" part was kept only in the first


def test_silence_still_ends_the_recording(monkeypatch):
    levels = [50] * 8 + [2000] * 10 + [50] * 60
    secs = run_script(monkeypatch, levels)
    assert secs < 1.5                                                    # stopped on silence, not at max_seconds


def test_no_speech_returns_pure_digital_silence(monkeypatch):
    """When nobody speaks during NO_SPEECH_TIMEOUT, return pure zero PCM so Whisper never hallucinates on room noise."""
    ScriptedMic.levels = [180] * 25                                      # ambient noise below 300 threshold
    monkeypatch.setattr(recorder, "MicStream", ScriptedMic)
    monkeypatch.setenv("SOUNDOS_NORMALIZE", "0")
    path = _record_utterance(1.0, 0.3)
    assert path
    with wave.open(path) as w:
        raw = w.readframes(w.getnframes())
    assert recorder.rms(raw) == 0.0
