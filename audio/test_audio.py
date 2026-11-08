#!/usr/bin/env python3
"""
audio/test_audio.py - Standalone manual test for the Sound OS audio module.

Run from the project root (the folder that contains `audio/`):

    python3 -m audio.test_audio
    python3 -m audio.test_audio --skip-wake      # skip the wake-word step
    python3 audio/test_audio.py                  # also works

Steps:
    1. Microphone level check (2 s)
    2. Wake-word detection (or Enter / loud-sound fallback)
    3. Record a phrase (max 3 s)
    4. Verify the WAV is 16 kHz / 16-bit / mono
"""

import argparse
import os
import sys
import time
import wave

# Allow `python3 audio/test_audio.py` as well as `python3 -m audio.test_audio`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio import record_utterance, wait_for_wake_word  # noqa: E402
from audio.recorder import BLOCK_SAMPLES, MicStream, rms  # noqa: E402


def step_mic_level(seconds: float = 2.0) -> bool:
    print("\n[1/4] Microphone check - speak or make noise for 2 seconds...")
    mic = MicStream(BLOCK_SAMPLES)
    if not mic.open():
        print("  FAIL: could not open microphone "
              "(try: sudo apt install libportaudio2 alsa-utils)")
        return False
    levels = []
    try:
        end = time.time() + seconds
        while time.time() < end:
            block = mic.read()
            if block is None:
                break
            level = rms(block)
            levels.append(level)
            bar = "#" * min(40, int(level / 100))
            print(f"\r  level {level:7.1f} |{bar:<40}|", end="", flush=True)
    finally:
        mic.close()
    print()
    if not levels:
        print("  FAIL: no audio received")
        return False
    print(f"  backend={mic.backend}  avg={sum(levels)/len(levels):.1f}  peak={max(levels):.1f}")
    print("  PASS")
    return True


def step_wake() -> bool:
    print("\n[2/4] Wake word - say the wake word, make a loud sound, or press Enter...")
    start = time.time()
    wait_for_wake_word()
    print(f"  PASS: triggered after {time.time() - start:.1f}s")
    return True


def step_record() -> str:
    print("\n[3/4] Recording - speak a short phrase now (max 3 s)...")
    path = record_utterance(max_seconds=3.0)
    print(f"  returned path: {path!r}")
    return path


def step_verify(path: str) -> bool:
    print("\n[4/4] Verifying WAV file...")
    if not path or not os.path.isabs(path) or not os.path.isfile(path):
        print("  FAIL: path is empty, not absolute, or file does not exist")
        return False
    try:
        with wave.open(path, "rb") as wf:
            ch, width, rate, frames = (
                wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getnframes()
            )
    except Exception as exc:
        print(f"  FAIL: not a valid WAV ({exc})")
        return False

    duration = frames / rate if rate else 0.0
    checks = {
        "mono (1 channel)": ch == 1,
        "16-bit samples": width == 2,
        "16000 Hz": rate == 16000,
        "non-empty": frames > 0,
    }
    for name, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    print(f"  channels={ch} width={width * 8}bit rate={rate} "
          f"duration={duration:.2f}s size={os.path.getsize(path)} bytes")
    print(f"  Listen with: aplay {path}")
    return all(checks.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Sound OS audio module test")
    parser.add_argument("--skip-wake", action="store_true", help="skip wake-word step")
    args = parser.parse_args()

    results = [step_mic_level()]
    if args.skip_wake:
        print("\n[2/4] Wake word - skipped")
    else:
        results.append(step_wake())
    results.append(step_verify(step_record()))

    ok = all(results)
    print("\n" + ("ALL TESTS PASSED" if ok else "SOME TESTS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
