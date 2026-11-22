"""Optional debugging aid: keep what the microphone heard, so a wrong transcript can be analysed later.

    export SOUNDOS_SAVE_AUDIO=/tmp/soundos_clips      # then run main.py as usual

Every clip that reaches the speech recogniser is saved as  <time>_<where>_<what-was-heard>.wav  (16 kHz mono).
Replay them with other models / settings:  python scripts/replay_clips.py /tmp/soundos_clips
Nothing is saved unless the variable is set. It never raises and never blocks the pipeline.
"""
import os
import re
import time
import wave

import numpy as np

SAMPLE_RATE = 16000


def _slug(text: str) -> str:
    s = re.sub(r"[^\w]+", "-", str(text or ""), flags=re.UNICODE).strip("-")
    return s[:40] or "empty"


def save_clip(audio, text: str, where: str) -> None:
    """audio: float32 array in [-1, 1] (16 kHz mono) or a path to an existing WAV file."""
    folder = os.environ.get("SOUNDOS_SAVE_AUDIO", "").strip()
    if not folder:
        return
    try:
        os.makedirs(folder, exist_ok=True)
        name = f"{time.strftime('%H%M%S')}_{int(time.time() * 1000) % 1000:03d}_{where}_{_slug(text)}.wav"
        path = os.path.join(folder, name)
        if isinstance(audio, (str, os.PathLike)):
            import shutil
            shutil.copyfile(audio, path)
            return
        pcm = (np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0) * 32767).astype(np.int16)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm.tobytes())
    except Exception:
        pass
