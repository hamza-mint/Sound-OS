#!/usr/bin/env python3
"""
replay_clips.py - run saved microphone clips through other models / settings and compare.

    export SOUNDOS_SAVE_AUDIO=/tmp/soundos_clips    # 1) run main.py and say the commands (clips are saved)
    python scripts/replay_clips.py /tmp/soundos_clips --expect close_app --models tiny base small

For every clip and every setting it prints what Whisper heard and which intent the parser found.
--expect <intent>  : the intent ALL these clips should give (record one command per folder), prints a score.
--lang ar|en       : force the language (default: auto-detect, like the app does).
Settings compared: the app's current decode, no prompt, and beam search 5 (slower, often more accurate).
Nothing is changed in the project: this only reads WAV files.
"""
import argparse
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--models", nargs="+", default=["tiny", "base"])
    ap.add_argument("--expect", default=None, help="intent every clip should produce, e.g. close_app")
    ap.add_argument("--lang", default=None, choices=["ar", "en"])
    args = ap.parse_args()

    from stt import SpeechToText
    from stt.stt import PROMPTS
    from intent_parser import parse

    clips = sorted(Path(args.folder).glob("*.wav"))
    if not clips:
        sys.exit(f"no .wav files in {args.folder}")
    audio = []
    for c in clips:
        a, sr = sf.read(str(c), dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        audio.append((c.name, a))
    print(f"{len(clips)} clips from {args.folder}\n")

    for size in args.models:
        s = SpeechToText(size)
        print(f"===== model: {size}")
        score = {}
        for name, a in audio:
            row = []
            for label in ("current", "no-prompt", "beam5"):
                if label == "current":
                    text, _ = s.transcribe(a, language=args.lang)
                elif label == "no-prompt":
                    text, _ = s.transcribe(a, language=args.lang, use_prompt=False)
                else:
                    lang = args.lang or "ar"
                    segs, _ = s.model.transcribe(a, language=lang, beam_size=5, temperature=0.0,
                                                 condition_on_previous_text=False, vad_filter=True,
                                                 initial_prompt=PROMPTS.get(lang))
                    text = " ".join(x.text.strip() for x in segs).strip()
                intent = parse(text)["intent"]
                score.setdefault(label, [0, 0])
                score[label][1] += 1
                score[label][0] += (intent == args.expect) if args.expect else 0
                row.append(f"{label:9} {text!r:36} -> {intent}")
            print(f"  {name[:48]}")
            for r in row:
                print(f"      {r}")
        if args.expect:
            print("  score (intent == %s): " % args.expect + ",  ".join(f"{k} {v[0]}/{v[1]}" for k, v in score.items()))
        print()


if __name__ == "__main__":
    main()
