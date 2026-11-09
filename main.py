"""Sound OS pipeline glue (owner: Kero).
Run with no microphone:  python main.py --text "افتح فايرفوكس"
Run the real loop:       python main.py
"""
import argparse
import sys
import time

from ui_tts import coucou_bridge as ui     # animated window
if "--no-ui" not in sys.argv:
    ui.start()                              # open the window FIRST (before the heavy STT imports)

from audio import wait_for_wake_word, record_utterance
from stt import transcribe
from intent_parser import parse, parse_yes_no
from safety import check
from executor import execute
from ui_tts import speak, notify


def handle(text, ask_yes_no):
    """text -> parse -> safety -> (confirm) -> execute -> feedback. Returns executor result."""
    parsed = parse(text)
    print(f"[heard] {text}")                      # also print in the terminal
    verdict = check(parsed)                       # {"decision": allow|confirm|block, "message": str}
    lang = parsed["lang"]
    if verdict["decision"] == "block":
        speak(verdict["message"], lang)
        ui.on_done(False)
        return {"success": False, "message": verdict["message"]}
    if verdict["decision"] == "confirm":
        speak(verdict["message"], lang)           # e.g. "Shut down the computer? Say yes or no."
        if parse_yes_no(ask_yes_no()) is not True:
            speak("Cancelled." if lang == "en" else "تم الإلغاء.", lang)
            ui.on_done(False)
            return {"success": False, "message": "cancelled"}
    result = execute(parsed)                      # {"success": bool, "message": str}
    speak(result["message"], lang)
    notify("Sound OS", result["message"])
    ui.on_done(result["success"])
    return result


def listen_text():
    """Real microphone path: record one utterance, transcribe it, show it on the window."""
    ui.on_wake()                                  # window: "Listening..."
    text = transcribe(record_utterance())["text"]
    ui.on_heard(text)                             # window + terminal: what you said
    return text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="skip mic + STT and parse this text")
    ap.add_argument("--no-ui", action="store_true", help="do not open the animated window")
    args = ap.parse_args()
    if args.no_ui:                                # keep the old behaviour: terminal only
        ui.start = ui.on_wake = ui.on_heard = ui.on_done = ui.linger = lambda *a, **k: None
    time.sleep(1.6)                               # let the intro finish before the first command
    if args.text:
        ui.on_heard(args.text)
        handle(args.text, ask_yes_no=lambda: input("yes/no> "))
        ui.linger()                               # keep the window until the result is seen
    else:
        try:
            while True:
                wait_for_wake_word()
                handle(listen_text(), ask_yes_no=listen_text)
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\nBye.")
