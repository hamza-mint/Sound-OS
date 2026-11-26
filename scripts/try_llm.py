"""Try the LLM fallback by hand - no microphone needed.

    ollama serve                              # in another terminal (if it is not already running)
    python3 scripts/try_llm.py                # type sentences, one per line (empty line = quit)
    python3 scripts/try_llm.py "ضاعف مستوى الصوت"      # one sentence

For each sentence it shows WHO understood it: the rules, the LLM, or nobody - and how long it took.
Model / address can be changed with  SOUNDOS_MODEL=qwen3.5:2b-q4_K_M   OLLAMA_URL=http://host:11434
"""
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intent_parser import parse, llm_fallback as lf            # noqa: E402
from intent_parser.rules import command_cue, _prepare          # noqa: E402


def show(r):
    return f'{r["intent"]} {r["params"] or ""}'.strip()


def explain(text):
    os.environ.pop("SOUNDOS_LLM", None)
    rules_only = parse(text)                                     # 1) the rules alone (instant)
    os.environ["SOUNDOS_LLM"] = "1"
    t0 = time.time()
    final = parse(text)                                          # 2) rules + LLM exactly as in the project
    dt = time.time() - t0
    os.environ.pop("SOUNDOS_LLM", None)
    llm_used = dt > 1.0
    print(f"   rules alone : {show(rules_only)}")
    print(f"   final       : {show(final)}   ({dt:.1f}s)")
    if rules_only["intent"] != "unknown" and not llm_used:
        print("   who         : \u2705 the RULES (instant, no LLM)")
    elif rules_only["intent"] != "unknown" and llm_used and final["intent"] == rules_only["intent"]:
        print("   who         : \U0001F9E0 the LLM double-checked a shaky typo-repair and AGREED")
    elif rules_only["intent"] != "unknown" and final["intent"] == "unknown":
        print("   who         : \U0001F6E1 the LLM DISAGREED with a shaky typo-repair -> refused (safe)")
    elif rules_only["intent"] == "unknown" and final["intent"] != "unknown":
        print("   who         : \U0001F9E0 the LLM understood it (the rules did not)")
    elif llm_used:
        print("   who         : \U0001F937 the LLM was asked and also said unknown")
    elif not command_cue(_prepare(text)):
        print("   who         : \u23E9 no command-like word -> the LLM was NOT asked (saves ~10 s) -> unknown")
    else:
        print("   who         : nobody understood it (LLM unreachable?)")


def main():
    ok, msg = lf.status()
    print(("\u2705 " if ok else "\u274C ") + msg)
    print(f"   model={lf.MODEL}  threshold={lf.FUZZY_THRESHOLD}  timeout={lf.TIMEOUT:.0f}s\n")
    if not ok:
        print("Fix the line above first, then run this again.")
        return
    if len(sys.argv) > 1:
        for text in sys.argv[1:]:
            print(f"> {text}")
            explain(text)
        return
    lf.ask_llm("ارفع الصوت")                                      # warm-up: loads the model once
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        explain(text)


if __name__ == "__main__":
    main()
