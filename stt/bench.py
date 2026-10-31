"""bench.py - latency (and RAM) of one model on a folder of WAV files.

    python bench.py testset/audio tiny
Run ONE model per process so RAM is measured correctly. Run it on the
machine that will be used for the demo, and trust p95, not the average.
"""
import glob
import os
import statistics
import sys

import psutil
import time

from stt import SpeechToText

if len(sys.argv) < 3:
    raise SystemExit("usage: python bench.py <folder_with_wavs> <tiny|base|small|medium>")
folder, size = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(folder, "*.wav")))
if not files:
    raise SystemExit(f"no .wav files in {folder}")

stt = SpeechToText(size)
stt.transcribe(files[0])                      # warm-up: the first call is slower

lat = []
for f in files:
    t = time.perf_counter()
    stt.transcribe(f)
    lat.append(time.perf_counter() - t)
lat.sort()
rss = psutil.Process(os.getpid()).memory_info().rss / 1e9
print(f"{size:6s} n={len(lat)} load={stt.load_seconds:.1f}s "
      f"median={statistics.median(lat):.2f}s "
      f"p95={lat[int(0.95 * (len(lat) - 1))]:.2f}s  RAM={rss:.2f}GB")
