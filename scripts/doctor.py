#!/usr/bin/env python3
"""
doctor.py - one command that tells a teammate if their machine is ready to run Sound OS.

    python scripts/doctor.py            # full check (includes a 1-second microphone test)
    python scripts/doctor.py --no-mic   # skip the microphone test (e.g. a VM without a mic yet)

Every line is  OK / WARN / FAIL  and, when something is missing, the exact command to fix it.
Exit code is 1 if there is any FAIL. It never changes anything on your machine.
"""
import argparse
import importlib
import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results = {"OK": 0, "WARN": 0, "FAIL": 0}


def show(status, what, hint=""):
    icon = {"OK": "✅", "WARN": "⚠️ ", "FAIL": "❌"}[status]
    results[status] += 1
    print(f"  {icon} {what}")
    if hint and status != "OK":
        print(f"       ↳ {hint}")


def section(title):
    print(f"\n{title}\n" + "-" * len(title))


def check_python():
    section("1) Python")
    v = sys.version_info
    label = f"Python {v.major}.{v.minor}.{v.micro}"
    if v < (3, 10):
        show("FAIL", label, "need Python 3.10 or newer (the code uses `str | None`).")
    elif v[:2] == (3, 12):
        show("OK", f"{label}  (same version as Xubuntu 24.04, the team VM)")
    else:
        show("OK", label)
        show("WARN", "the team VM (Xubuntu 24.04) uses Python 3.12",
             "before you push, also run the tests inside the VM: a bug can hide on one version only.")
    if sys.prefix == sys.base_prefix:
        show("WARN", "not inside a virtual environment", "python3 -m venv .venv && source .venv/bin/activate")


def check_packages():
    section("2) Python packages")
    required = [("numpy", "numpy"), ("soundfile", "soundfile"), ("sounddevice", "sounddevice"),
                ("faster_whisper", "faster-whisper")]
    optional = [("PySide6", "PySide6-Essentials", "the Dave animated window (without it the app still runs)"),
                ("piper", "piper-tts", "natural English voice (espeak-ng is the fallback)"),
                ("scipy", "scipy", "only some tools"), ("jiwer", "jiwer", "measuring accuracy: stt/eval_wer.py"),
                ("pytest", "pytest", "running the tests")]
    for mod, pip_name in required:
        try:
            importlib.import_module(mod)
            show("OK", pip_name)
        except Exception as exc:
            show("FAIL", f"{pip_name} cannot be imported ({exc.__class__.__name__})", f"pip install {pip_name}")
    for mod, pip_name, why in optional:
        try:
            importlib.import_module(mod)
            show("OK", f"{pip_name}  (optional)")
        except Exception:
            show("WARN", f"{pip_name} missing: {why}", f"pip install {pip_name}")


def check_system_tools():
    section("3) Linux tools used by the executor")
    session = os.environ.get("XDG_SESSION_TYPE", "").lower() or "unknown"
    print(f"  ℹ️  desktop session: {session}")
    if platform.system() != "Linux":
        show("WARN", f"this is {platform.system()}, not Linux",
             "the executor commands (pactl, xdg-open, wmctrl...) are Linux-only; use the Xubuntu VM to test them.")
        return
    if not any(shutil.which(t) for t in ("wpctl", "pactl", "amixer")):
        show("FAIL", "no volume tool (wpctl / pactl / amixer)", "sudo apt install pulseaudio-utils alsa-utils")
    else:
        found = [t for t in ("wpctl", "pactl", "amixer") if shutil.which(t)]
        show("OK", "volume control: " + ", ".join(found))
    for tool, pkg, why in [
        ("xdg-open", "xdg-utils", "open folders, web search"),
        ("pkill", "procps", "close apps"),
        ("wmctrl", "wmctrl", "close the active window / focus a running app (X11)"),
        ("espeak-ng", "espeak-ng", "Arabic voice replies"),
        ("gio", "libglib2.0-bin", "delete_file goes to the trash"),
    ]:
        if shutil.which(tool):
            show("OK", f"{tool}  ({why})")
        else:
            show("WARN", f"{tool} missing: {why}", f"sudo apt install {pkg}")
    if shutil.which("brightnessctl") or shutil.which("xrandr"):
        show("OK", "brightness: " + ("brightnessctl" if shutil.which("brightnessctl") else "xrandr (software, VM-friendly)"))
    else:
        show("WARN", "no brightness tool", "sudo apt install brightnessctl x11-xserver-utils")
    if session == "wayland":
        show("WARN", "Wayland session: wmctrl / xdotool / xrandr only work on X11",
             "log in with 'Xfce / X11' (Xubuntu default) or expect 'close active window' and software brightness to fail.")


def check_memory_and_models():
    section("4) Memory and Whisper models")
    try:
        kb = int(next(l for l in open("/proc/meminfo") if l.startswith("MemTotal")).split()[1])
        gb = kb / 1024 / 1024
        tier = "weak (use tiny)" if gb < 5 else "medium (tiny or base)" if gb < 12 else "strong (base or small)"
        show("OK", f"RAM {gb:.1f} GB  ->  {tier}")
    except Exception:
        show("WARN", "could not read RAM size")
    cache = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    have = sorted(p.name.split("faster-whisper-")[-1] for p in cache.glob("models--*faster-whisper-*")) if cache.exists() else []
    if have:
        show("OK", "Whisper models already downloaded: " + ", ".join(have))
    else:
        show("WARN", "no Whisper model downloaded yet",
             "the first voice command downloads one (tiny is ~75 MB). Do it once with internet: "
             "python -c \"from faster_whisper import WhisperModel; WhisperModel('tiny')\"")
    print(f"  ℹ️  selected model: SOUNDOS_STT_MODEL={os.environ.get('SOUNDOS_STT_MODEL', '(default: tiny)')}")


def check_microphone(skip):
    section("5) Microphone")
    if skip:
        show("WARN", "skipped (--no-mic)")
        return
    try:
        import numpy as np
        from audio.recorder import MicStream, SAMPLE_RATE
    except Exception as exc:
        show("FAIL", f"audio module cannot be imported: {exc}")
        return
    mic = MicStream()
    try:
        if not mic.open():
            show("FAIL", "no microphone could be opened",
                 "VM: Settings -> Sound Card/Audio -> enable 'Connect at power on' and allow the mic in Windows "
                 "Privacy settings. Then run: python check_mic.py")
            return
        levels = []
        for _ in range(33):                                   # ~1 second
            block = mic.read()
            if block:
                x = np.frombuffer(block, np.int16).astype(np.float64)
                levels.append(float(np.sqrt(np.mean(x ** 2))))
        mic.close()
        if not levels:
            show("FAIL", "microphone opened but gave no audio", "python check_mic.py --device <id>")
            return
        peak, avg = max(levels), sum(levels) / len(levels)
        show("OK", f"microphone works (backend: {getattr(mic, 'backend', 'auto')}, 16 kHz after conversion)")
        if peak < 20:
            show("WARN", "the signal is almost zero (muted or wrong input?)",
                 "pavucontrol -> Input Devices: unmute, raise the level, pick the right device.")
        else:
            print(f"  ℹ️  room noise level: avg {avg:.0f}, peak {peak:.0f} (speak louder than this)")
    except Exception as exc:
        show("FAIL", f"microphone test crashed: {exc}", "python check_mic.py")
    finally:
        try:
            mic.close()
        except Exception:
            pass


def check_pipeline():
    section("6) Pipeline smoke test (no microphone, nothing is really executed)")
    os.environ["SOUNDOS_DRY_RUN"] = "1"
    try:
        from intent_parser import parse
        for text, want in [("افتح المتصفح", "open_app"), ("علي الصوت", "volume_up"), ("open the brouser", "open_app")]:
            got = parse(text)["intent"]
            show("OK" if got == want else "FAIL", f"parse({text!r}) -> {got}", f"expected {want}")
        from executor import execute
        res = execute({"intent": "volume_up", "params": {}, "lang": "en"})
        show("OK" if res["success"] else "FAIL", f"executor (dry-run) -> {res['message']}")
    except Exception as exc:
        show("FAIL", f"pipeline import/run failed: {exc.__class__.__name__}: {exc}",
             "run: pytest -q   and send the first error to the team")


def check_safety_flags():
    section("7) Safety switches")
    env_file = ROOT / ".env"
    if env_file.exists() and "SOUNDOS_DRY_RUN=1" in env_file.read_text(errors="ignore"):
        show("OK", ".env has SOUNDOS_DRY_RUN=1: shutdown / delete are only simulated")
    else:
        show("WARN", "SOUNDOS_DRY_RUN is not set in .env",
             "while testing, run:  export SOUNDOS_DRY_RUN=1   (otherwise 'اطفي الجهاز' REALLY powers the machine off "
             "after you say yes). Remove it only for the final demo.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mic", action="store_true", help="skip the microphone test")
    args = ap.parse_args()
    print("Sound OS doctor  -  checking this machine\n" + "=" * 41)
    check_python()
    check_packages()
    check_system_tools()
    check_memory_and_models()
    check_microphone(args.no_mic)
    check_pipeline()
    check_safety_flags()
    print(f"\nResult: {results['OK']} ok, {results['WARN']} warnings, {results['FAIL']} failed")
    if results["FAIL"]:
        print("Fix the ❌ lines first (top to bottom), then run this again.")
    else:
        print("Ready. Next: python main.py --text \"افتح المتصفح\"   then   python main.py")
    return 1 if results["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
