"""SOUNDOS_SAVE_AUDIO keeps the clips the microphone produced (for analysing a wrong transcript)."""
import numpy as np
import soundfile as sf

from audio.debug_clips import save_clip


def test_nothing_is_saved_unless_the_variable_is_set(monkeypatch, tmp_path):
    monkeypatch.delenv("SOUNDOS_SAVE_AUDIO", raising=False)
    save_clip(np.zeros(1600, np.float32), "hi", "wake")
    assert list(tmp_path.iterdir()) == []


def test_array_is_saved_as_16k_mono_wav_with_the_heard_text_in_the_name(monkeypatch, tmp_path):
    monkeypatch.setenv("SOUNDOS_SAVE_AUDIO", str(tmp_path / "clips"))
    save_clip(0.3 * np.sin(np.arange(16000) / 5.0).astype(np.float32), "افتح المتصفح،", "wake")
    files = list((tmp_path / "clips").glob("*.wav"))
    assert len(files) == 1 and "wake" in files[0].name and "افتح-المتصفح" in files[0].name
    data, sr = sf.read(str(files[0]))
    assert sr == 16000 and data.ndim == 1 and len(data) == 16000


def test_a_wav_path_is_copied(monkeypatch, tmp_path):
    src = tmp_path / "in.wav"
    sf.write(str(src), np.zeros(800, np.float32), 16000)
    monkeypatch.setenv("SOUNDOS_SAVE_AUDIO", str(tmp_path / "out"))
    save_clip(str(src), "", "cmd")
    assert [p.name.split("_")[2] for p in (tmp_path / "out").glob("*.wav")] == ["cmd"]


def test_it_never_raises(monkeypatch):
    monkeypatch.setenv("SOUNDOS_SAVE_AUDIO", "/proc/definitely/not/writable")
    save_clip(np.zeros(10, np.float32), "x", "wake")
    save_clip(object(), "x", "wake")
