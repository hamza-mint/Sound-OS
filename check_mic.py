#!/usr/bin/env python3
"""
check_mic.py - Sound OS Microphone Diagnostic & Verification Tool.

Run this script to test and verify microphone detection on your laptop/PC:
    python check_mic.py
    python check_mic.py --device 4     # test specific device ID
"""

import argparse
import os
import sys
import time

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def print_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def list_devices():
    print_header("1. Scanning Available Audio Devices")
    try:
        import sounddevice as sd
    except ImportError:
        print("  [!] sounddevice is not installed. Run: pip install sounddevice")
        return []

    try:
        devices = sd.query_devices()
        default_in = sd.default.device[0]
    except Exception as exc:
        print(f"  [!] Failed to query audio devices: {exc}")
        return []

    input_devs = []
    print(f"  System Default Input Device Index: {default_in}")
    print("  Available Audio Input Devices:")
    for idx, d in enumerate(devices):
        max_in = d.get("max_input_channels", 0)
        if max_in > 0:
            is_def = " [DEFAULT]" if idx == default_in else ""
            sr = int(d.get("default_samplerate", 0))
            name = d.get("name", "Unknown")
            print(f"    [{idx:2d}] {name} (inputs: {max_in}, default_sr: {sr} Hz){is_def}")
            input_devs.append((idx, name, max_in, sr))

    if not input_devs:
        print("  [!] No microphone input devices detected by PortAudio.")
        print("      Check system audio settings or Linux permissions (alsa-utils / pipewire / pulseaudio).")
    return input_devs


def test_microphone_stream(device_override=None):
    print_header("2. Testing Microphone Capture & Laptop Rate Adaptation")
    if device_override is not None:
        os.environ["SOUNDOS_MIC_DEVICE"] = str(device_override)

    from audio.recorder import MicStream, BLOCK_SAMPLES, rms

    mic = MicStream(BLOCK_SAMPLES)
    opened = mic.open()
    if not opened:
        print("  [FAIL] Could not open any microphone.")
        print("  Troubleshooting tips:")
        print("    1. On Linux: ensure PortAudio & ALSA are installed:")
        print("       sudo apt install libportaudio2 alsa-utils (Debian/Ubuntu) or dnf install portaudio (Fedora)")
        print("    2. Check if your user is in the 'audio' group.")
        print("    3. Test arecord fallback: SOUNDOS_MIC_BACKEND=arecord python check_mic.py")
        return False

    print(f"  [OK] Microphone opened successfully!")
    print(f"       Backend: {mic.backend}")
    print(f"       Device:  {mic.device_name}")

    print("\n3. Measuring Audio Levels (Speak into your mic for 2.5 seconds)...")
    levels = []
    start_time = time.time()
    try:
        while time.time() - start_time < 2.5:
            block = mic.read()
            if block is None:
                break
            level = rms(block)
            levels.append(level)
            bar_len = min(35, int(level / 80))
            meter = "#" * bar_len + "-" * (35 - bar_len)
            print(f"\r  Volume: [{meter}] RMS: {level:6.1f}", end="", flush=True)
    finally:
        mic.close()

    print()
    if not levels:
        print("  [FAIL] No audio frames were received from the microphone.")
        return False

    avg_lvl = sum(levels) / len(levels)
    peak_lvl = max(levels)
    print(f"\n  Average Energy: {avg_lvl:.1f} RMS | Peak Energy: {peak_lvl:.1f} RMS")

    if peak_lvl > 200:
        print("  [SUCCESS] Microphone is working and capturing clear audio! 🎤✨")
    elif peak_lvl > 60:
        print("  [OK] Audio detected, but levels are low. Consider moving closer or increasing mic gain.")
    else:
        print("  [WARNING] Very low audio detected (near silence).")
        print("  Check that your laptop microphone is unmuted and the volume is turned up in system sound settings.")

    return True


def main():
    parser = argparse.ArgumentParser(description="Sound OS Laptop Microphone Diagnostic")
    parser.add_argument("--device", type=str, default=None, help="Explicit sounddevice device index or name")
    args = parser.parse_args()

    list_devices()
    ok = test_microphone_stream(args.device)
    if ok:
        print("\nAll microphone tests passed. You are ready to run Sound OS!")
        sys.exit(0)
    else:
        print("\nMicrophone check failed. See tips above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
