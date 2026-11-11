# run_live.py - سجّل طول ما بتتكلم، وقف بعد ما تسكت، وحوّل لنص
#   python run_live.py                 # موديل base، لغة تلقائي، سكوت 3 ثواني
#   python run_live.py --silence 1.5   # يوقف أسرع بعد السكوت
#   python run_live.py --lang ar       # ي اللغة (أسرع وأدق)
#   python run_live.py --model tiny    # أسرع وأضعف
# وإنت في وضع الانتظار: Enter = تلقائي | a = عربي | e = English | q = خروج
import argparse
import queue
import sys
import time

import numpy as np
from faster_whisper.vad import VadOptions, get_speech_timestamps

SR = 16000
# speech_pad_ms=0: عشان "آخر نقطة كلام" تبقى حقيقية، ومدة السكوت تتحسب صح
_VAD = VadOptions(speech_pad_ms=0, min_speech_duration_ms=150)


def speech_chunks(audio):
    """Silero VAD (جاي مع faster-whisper). بيرجّع [{'start':..,'end':..}] بالـ samples."""
    return get_speech_timestamps(audio, _VAD, sampling_rate=SR)


class Endpointer:
    """بيقرر امتى نوقف التسجيل. منفصل عن الميكروفون عشان يتجرّب لوحده."""

    def __init__(self, silence_seconds=3.0, wait_seconds=5.0, max_seconds=20.0,
                 vad=speech_chunks):
        self.silence_seconds = silence_seconds   # سكوت بعد الكلام -> وقف
        self.wait_seconds = wait_seconds         # لو محدش اتكلم خالص -> استسلم
        self.max_seconds = max_seconds           # سقف أمان للتسجيل كله
        self.vad = vad
        self.first_start = None                  # أول لحظة كلام (بالثواني)

    def update(self, audio):
        """بيرجّع (state, last_speech_end_seconds).
        state: waiting | speaking | done | no_speech | max"""
        total = len(audio) / SR
        chunks = self.vad(audio) if total >= 0.5 else []
        if not chunks:                           # لسه محدش اتكلم
            return ("no_speech" if total >= self.wait_seconds else "waiting"), None
        self.first_start = chunks[0]["start"] / SR
        last_end = chunks[-1]["end"] / SR
        if total - last_end >= self.silence_seconds:
            return "done", last_end
        if total >= self.max_seconds:
            return "max", last_end
        return "speaking", last_end


def record_until_silence(silence_seconds=3.0, wait_seconds=8.0, max_seconds=20.0,
                         check_every=0.3):
    """بيسجّل من الميكروفون. بيرجّع array (16 kHz mono) أو None لو محدش اتكلم."""
    import sounddevice as sd                     # هنا عشان الاختبارات ما تحتاجش مايك
    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        q.put(indata[:, 0].copy())

    ep = Endpointer(silence_seconds, wait_seconds, max_seconds)
    blocks, n, last_check, shown = [], 0, 0, None
    with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                        blocksize=1600, callback=callback):      # 0.1 ثانية
        while True:
            try:
                block = q.get(timeout=2.0)
            except queue.Empty:
                raise RuntimeError("مفيش صوت جاي من الميكروفون (اتأكد إنه متوصل ومش مقفول)")
            blocks.append(block)
            n += len(block)
            if n - last_check < check_every * SR:
                continue
            last_check = n
            audio = np.concatenate(blocks)
            state, last_end = ep.update(audio)
            if state != shown:                   # اطبع لما الحالة تتغير بس
                msg = {"waiting": "  ...مستني تبدأ كلام",
                       "speaking": "  بسمعك... "}.get(state, "")
                if msg:
                    print(msg, flush=True)
                shown = state
            if state == "no_speech":
                return None
            if state in ("done", "max"):
                start = max(0, int((ep.first_start - 0.3) * SR))   # شيل السكوت اللي قبل الكلام
                end = min(len(audio), int((last_end + 0.5) * SR))  # وزيادة السكوت اللي بعده
                return audio[start:end]


def _fmt(score):
    return "-" if score is None or score == float("-inf") else f"{score:.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="base", help="tiny | base | small")
    ap.add_argument("--silence", type=float, default=3.0, help="ثواني السكوت قبل ما يوقف")
    ap.add_argument("--lang", choices=["auto", "ar", "en"], default="auto")
    ap.add_argument("--prompt", action="store_true",
                    help="شغّل initial_prompt (مقفول افتراضيًا لأنه ضرّ في التجارب)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    from stt import SpeechToText
    print(f"بحمّل الموديل ({args.model})...")
    stt = SpeechToText(args.model)
    print(f"الموديل جاهز (اتحمّل في {stt.load_seconds:.1f} ثانية)")
    lang = None if args.lang == "auto" else args.lang

    while True:
        cmd = input("\nEnter = سجّل | q = خروج > ").strip().lower()
        if cmd == "q":
            break
        use_lang = lang
        try:
            audio = record_until_silence(silence_seconds=args.silence)
        except KeyboardInterrupt:
            print("اتلغى")
            continue
        if audio is None:
            print("محدش اتكلم .")
            continue

        t = time.perf_counter()
        text, detected = stt.transcribe(audio, language=use_lang, use_prompt=args.prompt)
        took = time.perf_counter() - t
        print(f"  مدة الصوت : {len(audio) / SR:.1f} ثانية | الـ STT: {took:.2f} ثانية")
        print(f"  اللغة     : {detected}")
        print(f"  النص      : {text!r}" if text else "  النص      : (مفيش كلام اتفهم)")
        if use_lang is None:                              # تلقائي: وريني الاتنين
            for c in stt.last_candidates:
                print(f"     [{c['lang']}] {c['text']!r}  (ثقة {_fmt(c['score'])})")


if __name__ == "__main__":
    main()
