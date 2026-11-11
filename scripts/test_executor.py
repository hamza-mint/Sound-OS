#!/usr/bin/env python3
"""
Sound OS - Executor Standalone Verification & Benchmark
Runs every intent with sample JSON, prints Pass/Fail + timing.
Safe to run: All tests use SOUNDOS_DRY_RUN=1.
Usage: python scripts/test_executor.py
"""
import os
import sys
import time

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["SOUNDOS_DRY_RUN"] = "1"

from executor import execute

SAMPLE_COMMANDS = [
    # ---- Application Management ----
    {"name": "Open App (Terminal)",          "cmd": {"intent": "open_app",   "params": {"app": "terminal"},    "lang": "en", "raw_text": "open terminal"}},
    {"name": "Open App Arabic (المتصفح)",    "cmd": {"intent": "open_app",   "params": {"app": "المتصفح"},    "lang": "ar", "raw_text": "افتح المتصفح"}},
    {"name": "Open App Arabic (الحاسبة)",    "cmd": {"intent": "open_app",   "params": {"app": "الحاسبة"},    "lang": "ar", "raw_text": "افتح الحاسبة"}},
    {"name": "Close App (calculator)",       "cmd": {"intent": "close_app",  "params": {"app": "calculator"},  "lang": "en", "raw_text": "close calculator"}},
    # ---- Audio Controls ----
    {"name": "Volume Up (EN)",               "cmd": {"intent": "volume_up",   "params": {},  "lang": "en", "raw_text": "volume up"}},
    {"name": "Volume Down (AR)",             "cmd": {"intent": "volume_down", "params": {},  "lang": "ar", "raw_text": "خفض الصوت"}},
    {"name": "Mute (AR)",                    "cmd": {"intent": "mute",        "params": {},  "lang": "ar", "raw_text": "اكتم الصوت"}},
    # ---- Brightness ----
    {"name": "Brightness Up (EN)",           "cmd": {"intent": "brightness_up",   "params": {}, "lang": "en", "raw_text": "brightness up"}},
    {"name": "Brightness Down (AR)",         "cmd": {"intent": "brightness_down", "params": {}, "lang": "ar", "raw_text": "خفض السطوع"}},
    # ---- File & Folder ----
    {"name": "Open Folder (Downloads EN)",   "cmd": {"intent": "open_folder", "params": {"folder": "downloads"},  "lang": "en", "raw_text": "open downloads"}},
    {"name": "Open Folder (التنزيلات AR)",    "cmd": {"intent": "open_folder", "params": {"folder": "التنزيلات"}, "lang": "ar", "raw_text": "افتح التنزيلات"}},
    {"name": "Create File (safe)",           "cmd": {"intent": "create_file", "params": {"name": "test_sample.txt"}, "lang": "ar", "raw_text": "أنشئ ملف test_sample.txt"}},
    {"name": "Create File (no name)",        "cmd": {"intent": "create_file", "params": {},                        "lang": "en", "raw_text": "create a file"}},
    {"name": "Create File (traversal BAD)",  "cmd": {"intent": "create_file", "params": {"name": "../etc/evil.txt"}, "lang": "en", "raw_text": "create ../etc/evil.txt"}},
    {"name": "Delete File (dry-run)",        "cmd": {"intent": "delete_file", "params": {"name": "test_sample.txt"}, "lang": "ar", "raw_text": "احذف test_sample.txt"}},
    {"name": "Delete File (traversal BAD)",  "cmd": {"intent": "delete_file", "params": {"name": "../passwd"},       "lang": "en", "raw_text": "delete ../passwd"}},
    # ---- Web & Media ----
    {"name": "Web Search (AR)",              "cmd": {"intent": "web_search",  "params": {"query": "weather Cairo"}, "lang": "ar", "raw_text": "ابحث عن الطقس في القاهرة"}},
    {"name": "Play Media (AR)",              "cmd": {"intent": "play_media",  "params": {"query": "fairuz"},        "lang": "ar", "raw_text": "شغل فيروز"}},
    # ---- Dangerous (dry-run) ----
    {"name": "Shutdown (DRY-RUN)",           "cmd": {"intent": "shutdown",    "params": {},  "lang": "en", "raw_text": "shut down"}},
    # ---- Error handling ----
    {"name": "Unknown Intent (AR)",          "cmd": {"intent": "fly_to_moon", "params": {},  "lang": "ar", "raw_text": "طير للقمر"}},
    {"name": "Unknown Intent (EN)",          "cmd": {"intent": "do_magic",    "params": {},  "lang": "en", "raw_text": "do magic"}},
]


def run_tests():
    print("=" * 75)
    print("  Sound OS — Executor Verification & Timing Benchmark (DRY-RUN=1)")
    print("=" * 75)

    passed = 0
    total = len(SAMPLE_COMMANDS)
    timings = []

    for item in SAMPLE_COMMANDS:
        name = item["name"]
        cmd = item["cmd"]
        try:
            t0 = time.monotonic()
            result = execute(cmd)
            elapsed_ms = (time.monotonic() - t0) * 1000

            # Contract checks
            has_keys = isinstance(result, dict) and "success" in result and "message" in result
            valid_types = isinstance(result.get("success"), bool) and isinstance(result.get("message"), str)
            under_limit = elapsed_ms < 1000  # 1 second

            ok = has_keys and valid_types and under_limit
            if ok:
                passed += 1

            status = "PASS" if ok else "FAIL"
            flag = "⏱️" if not under_limit else ""
            print(f"  [{status}] {name:38} {elapsed_ms:7.1f}ms  success={result.get('success')}  {flag}")
            print(f"         └─ {result.get('message', '')}")
            timings.append((cmd["intent"], elapsed_ms))
        except Exception as exc:
            print(f"  [FAIL] {name:38}          EXCEPTION: {exc}")

    # Summary
    print()
    print("=" * 75)
    print(f"  Results: {passed}/{total} passed")
    print()
    if timings:
        avg = sum(t for _, t in timings) / len(timings)
        mx = max(timings, key=lambda x: x[1])
        mn = min(timings, key=lambda x: x[1])
        print(f"  Timing:  avg={avg:.1f}ms  min={mn[1]:.1f}ms ({mn[0]})  max={mx[1]:.1f}ms ({mx[0]})")
        over = [(n, t) for n, t in timings if t >= 1000]
        if over:
            print(f"  ⚠️  {len(over)} intent(s) exceeded 1s limit:")
            for n, t in over:
                print(f"       - {n}: {t:.1f}ms")
        else:
            print("  ✅ All intents executed under 1 second")
    print("=" * 75)
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
