"""
tests/test_recorder.py - Unit tests for audio recorder, MicStream, and laptop mic resilience.
"""

import os
import wave
import numpy as np
import pytest

from audio.recorder import (
    BLOCK_SAMPLES,
    CHANNELS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    MicStream,
    compute_threshold,
    record_utterance,
    record_wake_clip,
    rms,
    write_wav,
)


def test_rms_energy():
    silence = b"\x00\x00" * 480
    assert rms(silence) == 0.0

    # Sine wave
    t = np.linspace(0, 1, 480, endpoint=False)
    wave_data = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
    val = rms(wave_data.tobytes())
    assert 6000 < val < 8000


def test_compute_threshold():
    floor = compute_threshold([])
    assert floor >= 300.0

    low_noise = [50.0] * 10
    assert compute_threshold(low_noise) >= 300.0

    high_noise = [500.0] * 10
    assert compute_threshold(high_noise) == 1500.0


def test_write_wav(tmp_path):
    path = str(tmp_path / "test.wav")
    pcm = b"\x00\x00" * 1600
    assert write_wav(path, pcm) is True

    with wave.open(path, "rb") as wf:
        assert wf.getnchannels() == CHANNELS
        assert wf.getsampwidth() == SAMPLE_WIDTH
        assert wf.getframerate() == SAMPLE_RATE
        assert wf.getnframes() == 1600


def test_micstream_software_downsampling_48k():
    mic = MicStream(BLOCK_SAMPLES)
    mic._downsample = True
    mic._native_sr = 48000
    mic._native_channels = 2
    mic._native_block_samples = 1440

    class DummySDStream:
        def read(self, samples):
            # 1440 samples * 2 channels = 2880 int16 samples
            fake_hw = (np.ones(samples * 2, dtype=np.int16) * 500).tobytes()
            return fake_hw, False

    mic._sd_stream = DummySDStream()
    block = mic.read()
    assert block is not None
    assert len(block) == BLOCK_SAMPLES * SAMPLE_WIDTH
    arr = np.frombuffer(block, dtype=np.int16)
    assert len(arr) == BLOCK_SAMPLES
    assert arr[0] == 500


def test_micstream_software_downsampling_44k():
    mic = MicStream(BLOCK_SAMPLES)
    mic._downsample = True
    mic._native_sr = 44100
    mic._native_channels = 2
    mic._native_block_samples = 1323

    class DummySDStream:
        def read(self, samples):
            fake_hw = (np.ones(samples * 2, dtype=np.int16) * 750).tobytes()
            return fake_hw, False

    mic._sd_stream = DummySDStream()
    block = mic.read()
    assert block is not None
    assert len(block) == BLOCK_SAMPLES * SAMPLE_WIDTH
    arr = np.frombuffer(block, dtype=np.int16)
    assert len(arr) == BLOCK_SAMPLES
    assert arr[0] == 750


def test_record_utterance_never_raises():
    # CONTRACT Rule 1: public function must never raise even with invalid timeouts
    path = record_utterance(max_seconds=0.01)
    assert isinstance(path, str)
    if path:
        assert os.path.isabs(path)
        assert os.path.isfile(path)


def test_record_wake_clip_never_raises():
    clip = record_wake_clip(max_seconds=0.01)
    assert isinstance(clip, str)
