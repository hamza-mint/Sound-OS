"""دور 1: بيربط المراحل: صوت ← نص ← أمر ← تنفيذ ← رد.

تشغيل تجريبي آمن (من غير تنفيذ حقيقي):   python3 src/main.py
تشغيل حقيقي (بحذر):                      python3 src/main.py --real
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from speech import listen
from intent import parse_intent
from execution import run_intent, NEEDS_CONFIRM
from ui import show_status, speak


def handle_once(typed_text=None, dry_run=True, ask=input) -> dict:
    show_status("listening")
    text = listen(typed_text)["text"]
    show_status("thinking", text)
    intent = parse_intent(text)["intent"]
    if intent == "unknown":
        result = {"ok": False, "message": "مش فاهم، جرّب تاني"}
    else:
        confirmed = False
        if intent in NEEDS_CONFIRM:
            confirmed = ask("متأكد؟ اكتب نعم للتأكيد: ").strip() == "نعم"
        result = run_intent(intent, confirmed=confirmed, dry_run=dry_run)
    show_status("done" if result["ok"] else "error", result["message"])
    speak(result["message"])
    return result


if __name__ == "__main__":
    real = "--real" in sys.argv
    print("وضع التنفيذ الحقيقي" if real else "وضع التجربة (آمن). Ctrl+C للخروج")
    while True:
        handle_once(dry_run=not real)
