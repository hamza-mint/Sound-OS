"""Parser accuracy report per intent and per group (owner: Kareem).  Run: python scripts/parser_report.py"""
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from tests.test_parser import ROWS, check_row  # noqa: E402

by_intent = collections.defaultdict(lambda: [0, 0])
fails = []
for row in ROWS:
    why = check_row(row)
    by_intent[row["intent"]][1] += 1
    by_intent[row["intent"]][0] += (why == "")
    if why:
        fails.append((row["id"], row["phrase"], why))

total_ok = sum(v[0] for v in by_intent.values())
print(f"{'intent':16} ok/total")
for intent, (ok, n) in sorted(by_intent.items()):
    print(f"{intent:16} {ok}/{n}  {100 * ok / n:.0f}%")
print(f"\nTOTAL {total_ok}/{len(ROWS)} = {100 * total_ok / len(ROWS):.1f}%")
for f in fails:
    print("FAIL", *f)
