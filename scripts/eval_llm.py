"""Compare the rules alone with rules + LLM on a CSV of phrases (default testdata/holdout.csv).

    python3 scripts/eval_llm.py                     # needs `ollama serve` + the model pulled
    python3 scripts/eval_llm.py --csv testdata/phrases.csv
Do NOT tune rules on holdout.csv: it only stays honest while the rules have never seen it.
"""
import argparse, csv, os, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intent_parser import parse, llm_fallback            # noqa: E402
from intent_parser.normalize import normalize as N       # noqa: E402

CANON = {"home", "downloads", "documents", "desktop", "pictures", "music", "videos"}


def params_ok(exp, got):
    for pair in filter(None, exp.split(";")):
        k, v = pair.split("=", 1)
        g = got.get(k, "")
        if k == "app" or (k == "folder" and v in CANON):
            if g != v:
                return False
        elif N(v) not in N(g):
            return False
    return True


def run(phrase, llm):
    if llm: os.environ["SOUNDOS_LLM"] = "1"
    else:   os.environ.pop("SOUNDOS_LLM", None)
    t0 = time.time(); r = parse(phrase); return r, time.time() - t0


def llm_only(rows):
    ok = wrong = miss = 0; lat = []; bad = []
    for row in rows:
        exp = "unknown" if row["intent"] in ("shutdown", "delete_file") else row["intent"]   # the LLM must refuse these
        t0 = time.time(); status, ans = llm_fallback.ask_llm_ex(row["phrase"]); lat.append(time.time() - t0)
        got, gp = (ans if ans else ("unknown", {}))
        good = got == exp and (exp == "unknown" or params_ok(row["params"], gp))
        if good: ok += 1
        elif got == "unknown": miss += 1
        else: wrong += 1
        if not good: bad.append(f'  {row["id"]} [{row["group"]}] {row["phrase"]!r}: expected {exp} {row["params"]} | got {got} {gp} ({status})')
    n = len(rows)
    print(f"LLM ONLY ({llm_fallback.MODEL}, prompt={'rules-aware' if os.getenv('SOUNDOS_PROMPT') == 'rules' else 'basic'}): "
          f"correct {ok}/{n} ({100*ok/n:.0f}%) | unknown(safe miss) {miss} | WRONG ACTION {wrong} | "
          f"avg {sum(lat)/len(lat):.1f}s max {max(lat):.1f}s")
    print("\n".join(bad))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "testdata" / "holdout.csv"))
    ap.add_argument("--llm-only", action="store_true",
                    help="ask ONLY the LLM about every row (no rules, no cue gate): measures the prompt itself. Slow.")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8")))
    print(f"model={llm_fallback.MODEL} url={llm_fallback.URL} threshold={llm_fallback.FUZZY_THRESHOLD} rows={len(rows)}")
    llm_fallback.ask_llm("ارفع الصوت")                      # warm-up, not counted
    if a.llm_only:
        return llm_only(rows)
    st = {m: dict(ok=0, wrong=0, miss=0) for m in ("rules", "rules+llm")}
    calls = 0; lat = []; diffs = []
    for row in rows:
        exp = row["intent"]; res = {}
        for mode, llm in (("rules", False), ("rules+llm", True)):
            r, dt = run(row["phrase"], llm); res[mode] = (r, dt)
            good = r["intent"] == exp and params_ok(row["params"], r["params"])
            if good: st[mode]["ok"] += 1
            elif r["intent"] == "unknown": st[mode]["miss"] += 1            # safe failure
            else: st[mode]["wrong"] += 1                                    # confident wrong action
            if not good and mode == "rules+llm":
                diffs.append(f'  {row["id"]} [{row["group"]}] {row["phrase"]!r}: expected {exp} {row["params"]} | got {r["intent"]} {r["params"]}')
        if res["rules+llm"][1] > 1.0:
            calls += 1; lat.append(res["rules+llm"][1])
    n = len(rows)
    for m, s in st.items():
        print(f'{m:10} correct {s["ok"]}/{n} ({100*s["ok"]/n:.0f}%) | unknown(safe miss) {s["miss"]} | WRONG ACTION {s["wrong"]}')
    if lat:
        print(f"LLM calls: {calls} | avg {sum(lat)/len(lat):.1f}s | max {max(lat):.1f}s")
    print("still wrong with LLM:" if diffs else "nothing wrong with LLM")
    print("\n".join(diffs))


if __name__ == "__main__":
    main()
