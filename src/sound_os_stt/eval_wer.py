"""eval_wer.py - measure WER / CER / language accuracy / latency on the test set.

    python eval_wer.py tiny                 # uses the language written in references.csv
    python eval_wer.py tiny --auto          # auto-detect language (harder, realistic)
    python eval_wer.py tiny --no-prompt     # compare with / without initial_prompt

Change ONE thing per run and record the numbers.
Silence clips (empty reference) are counted separately as "false triggers".
"""
import argparse
import collections
import csv
import os
import time

import jiwer

from stt import SpeechToText
from textnorm import normalize

ap = argparse.ArgumentParser()
ap.add_argument("model", nargs="?", default="tiny")
ap.add_argument("--testset", default="testset")
ap.add_argument("--no-prompt", action="store_true")
ap.add_argument("--auto", action="store_true",
                help="auto-detect language instead of using the CSV language")
args = ap.parse_args()

refs_path = os.path.join(args.testset, "references.csv")
if not os.path.exists(refs_path):
    raise SystemExit(f"{refs_path} not found. Record clips first: python record_set.py ...")
rows = list(csv.DictReader(open(refs_path, encoding="utf-8")))
if not rows:
    raise SystemExit("references.csv is empty.")

stt = SpeechToText(args.model)
groups = collections.defaultdict(lambda: ([], []))     # key -> (refs, hyps)
lang_ok = lang_n = silence_n = false_triggers = 0
times = []

for r in rows:
    t = time.perf_counter()
    hyp, lang = stt.transcribe(
        os.path.join(args.testset, "audio", r["file"]),
        language=None if args.auto else r["lang"],
        use_prompt=not args.no_prompt)
    times.append(time.perf_counter() - t)
    r["hyp"] = hyp

    ref_n, hyp_n = normalize(r["reference"]), normalize(hyp)
    if not ref_n:                                  # silence clip
        silence_n += 1
        false_triggers += bool(hyp_n)
        continue
    lang_n += 1
    lang_ok += (lang == r["lang"])
    for key in ("ALL", f"lang={r['lang']}", f"cond={r['condition']}",
                f"spk={r['speaker']}"):
        groups[key][0].append(ref_n)
        groups[key][1].append(hyp_n or "xxx")      # jiwer rejects empty hypotheses

print(f"model={args.model} auto_lang={args.auto} prompt={not args.no_prompt}")
for key, (refs, hyps) in sorted(groups.items()):
    print(f"{key:14s} n={len(refs):3d}  WER={jiwer.wer(refs, hyps):.3f}  "
          f"CER={jiwer.cer(refs, hyps):.3f}")
if lang_n:
    print(f"language accuracy: {lang_ok / lang_n:.1%} ({lang_n} clips)")
if silence_n:
    print(f"false triggers on silence: {false_triggers}/{silence_n}")
times.sort()
print(f"latency median={times[len(times) // 2]:.2f}s  "
      f"p95={times[int(0.95 * (len(times) - 1))]:.2f}s  (n={len(times)})")

with open("results.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("per-clip results -> results.csv")
