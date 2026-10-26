"""pipeline_demo.py - how the STT module plugs into the Sound OS pipeline.

Run from the repo root:  python -m examples.pipeline_demo
The wake word and recording parts are PLACEHOLDERS (owned by the audio/wake-word
teammate). Replace the two functions below with the real ones; the STT call
itself does not change.
"""
import json

import sounddevice as sd

from stt import SpeechToText, SAMPLE_RATE
from textnorm import normalize


def wait_for_wake_word():
    """PLACEHOLDER: replace with the real wake-word detector (openWakeWord)."""
    input("\n[push-to-talk] press Enter to simulate the wake word... ")


def record_command(seconds=4):
    """PLACEHOLDER: replace with the real buffer after the wake word
    (ideally cut by voice-activity detection). Must return 16 kHz mono audio."""
    print("listening...")
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="float32")
    sd.wait()
    return audio.reshape(-1)


def main():
    stt = SpeechToText("tiny")                 # loaded once
    print(f"STT ready (model loaded in {stt.load_seconds:.1f}s). Ctrl+C to stop.")
    while True:
        wait_for_wake_word()
        audio = record_command()
        text, lang = stt.transcribe(audio)
        if not text:
            print("(nothing understood)")
            continue
        # What the intent parser receives from us:
        print(json.dumps({"raw_text": text, "norm_text": normalize(text), "lang": lang},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
