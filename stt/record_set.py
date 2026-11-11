"""record_set.py - record the speech test set (each teammate runs this).

    python record_set.py --speaker spk01 --condition quiet
    python record_set.py --speaker spk01 --condition noisy

It shows each phrase from phrases.csv, records it (16 kHz mono WAV) into
testset/audio/ and appends a row to testset/references.csv.
Rows with an empty reference are SILENCE clips: say nothing (noisy condition:
leave a fan / background talk running). They measure hallucinations.
Re-running skips clips that already exist, so you can stop (q) and continue.
"""
import argparse
import csv
import os

import sounddevice as sd
import soundfile as sf
import numpy as np

SR = 16000
FIELDS = ["file", "lang", "speaker", "condition", "reference", "expected_intent"]

ap = argparse.ArgumentParser()
ap.add_argument("--speaker", required=True, help="e.g. spk01 (use a different id per person)")
ap.add_argument("--condition", choices=["quiet", "noisy"], required=True)
ap.add_argument("--seconds", type=float, default=3.0)
ap.add_argument("--phrases", default="phrases.csv")
ap.add_argument("--out", default="testset")
args = ap.parse_args()

audio_dir = os.path.join(args.out, "audio")
refs_path = os.path.join(args.out, "references.csv")
os.makedirs(audio_dir, exist_ok=True)
new_file = not os.path.exists(refs_path)

with open(args.phrases, encoding="utf-8") as f:
    phrases = list(csv.DictReader(f))

refs_f = open(refs_path, "a", encoding="utf-8", newline="")
writer = csv.DictWriter(refs_f, fieldnames=FIELDS)
if new_file:
    writer.writeheader()

for i, p in enumerate(phrases, start=1):
    name = f"{args.speaker}_{args.condition}_{p['lang']}_{i:03d}.wav"
    path = os.path.join(audio_dir, name)
    if os.path.exists(path):
        continue
    silence = p["reference"] == ""
    while True:
        shown = "(SILENCE - say nothing)" if silence else p["reference"]
        cmd = input(f"\n[{i}/{len(phrases)}] ({p['lang']}) {shown}\n"
                    f"  Enter = record, s = skip, q = quit > ").strip().lower()
        if cmd == "q":
            refs_f.close()
            raise SystemExit
        if cmd == "s":
            break
        print("  recording...")
        data = sd.rec(int(args.seconds * SR), samplerate=SR, channels=1, dtype="float32")
        sd.wait()
        level = float(np.sqrt(np.mean(data ** 2)))
        print(f"  done (level={level:.4f})")
        if not silence and level < 0.005:
            print("  WARNING: very quiet - is the microphone muted / wrong device?")
        if input("  Enter = keep, r = redo > ").strip().lower() == "r":
            continue
        sf.write(path, data, SR, subtype="PCM_16")
        writer.writerow({"file": name, "lang": p["lang"], "speaker": args.speaker,
                         "condition": args.condition, "reference": p["reference"],
                         "expected_intent": p["intent"]})
        refs_f.flush()
        break

refs_f.close()
print("Finished. Commit testset/audio/*.wav and testset/references.csv.")
