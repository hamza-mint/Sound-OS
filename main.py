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
from ui_tts import speak, notify, play_wake_ack, play_done_sound
from ui_tts.coucou_bridge import on_wake, on_heard, on_done


def handle(text, ask_yes_no):
    """text -> parse -> safety -> (confirm) -> execute -> feedback. Returns executor result."""
    on_heard(text)
    parsed = parse(text)
    verdict = check(parsed)                       # {"decision": allow|confirm|block, "message": str}
    lang = parsed["lang"]
    if verdict["decision"] == "block":
        speak(verdict["message"], lang)
        on_done(False)
        return {"success": False, "message": verdict["message"]}
    if verdict["decision"] == "confirm":
        speak(verdict["message"], lang)           # e.g. "Shut down the computer? Say yes or no."
        if parse_yes_no(ask_yes_no()) is not True:
            speak("Cancelled." if lang == "en" else "تم الإلغاء.", lang)
            on_done(False)
            return {"success": False, "message": "cancelled"}
    result = execute(parsed)                      # {"success": bool, "message": str}
    if result.get("success", False):
        play_done_sound()
    speak(result["message"], lang)
    notify("Sound OS", result["message"])
    on_done(result.get("success", False))
    return result


def listen_text():
    """Real microphone path: record one utterance and transcribe it."""
    wav_path = record_utterance()
    if not wav_path:
        return ""
    stt_res = transcribe(wav_path)
    return stt_res.get("text", "")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="skip mic + STT and parse this text")
    ap.add_argument("--wav", help="skip mic and transcribe this WAV file")
    args = ap.parse_args()
    if args.text:
        on_wake()
        handle(args.text, ask_yes_no=lambda: input("yes/no> "))
    elif args.wav:
        on_wake()
        stt_res = transcribe(args.wav)
        print(f"[STT Recognized]: text={stt_res['text']!r} lang={stt_res['lang']} (confidence={stt_res.get('confidence', 1.0):.2f})")
        handle(stt_res["text"], ask_yes_no=lambda: input("yes/no> "))
    else:
        print("[Sound OS] Ready and listening for wake word...")
        while True:
            wait_for_wake_word()
            print("[Sound OS] 🔔 Wake word detected! 'I am here'")
            on_wake()
            play_wake_ack()
            raw_text = listen_text()
            if raw_text:
                print(f"[Sound OS] Heard: {raw_text!r}")
                handle(raw_text, ask_yes_no=listen_text)
            else:
                on_done(False)

