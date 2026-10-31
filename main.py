"""Sound OS pipeline glue (owner: Kero).
Run with no microphone:  python main.py --text "افتح فايرفوكس"
Run the real loop:       python main.py
"""
import argparse

from audio import wait_for_wake_word, record_utterance
from stt import transcribe
from intent_parser import parse, parse_yes_no
from safety import check
from executor import execute
from ui_tts import speak, notify


def handle(text, ask_yes_no):
    """text -> parse -> safety -> (confirm) -> execute -> feedback. Returns executor result."""
    parsed = parse(text)
    verdict = check(parsed)                       # {"decision": allow|confirm|block, "message": str}
    lang = parsed["lang"]
    if verdict["decision"] == "block":
        speak(verdict["message"], lang)
        return {"success": False, "message": verdict["message"]}
    if verdict["decision"] == "confirm":
        speak(verdict["message"], lang)           # e.g. "Shut down the computer? Say yes or no."
        if parse_yes_no(ask_yes_no()) is not True:
            speak("Cancelled." if lang == "en" else "تم الإلغاء.", lang)
            return {"success": False, "message": "cancelled"}
    result = execute(parsed)                      # {"success": bool, "message": str}
    speak(result["message"], lang)
    notify("Sound OS", result["message"])
    return result


def listen_text():
    """Real microphone path: record one utterance and transcribe it."""
    return transcribe(record_utterance())["text"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="skip mic + STT and parse this text")
    args = ap.parse_args()
    if args.text:
        handle(args.text, ask_yes_no=lambda: input("yes/no> "))
    else:
        while True:
            wait_for_wake_word()
            handle(listen_text(), ask_yes_no=listen_text)
