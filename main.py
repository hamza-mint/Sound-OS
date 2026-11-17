"""Sound OS pipeline glue (owner: Kero).
Run with no microphone:  python main.py --text "افتح فايرفوكس"
Run the real loop:       python main.py
"""
import argparse

from audio import wait_for_wake_word, record_utterance
from stt import transcribe
from intent_parser import parse, parse_yes_no, split_compound
from safety import check
from executor import execute
from ui_tts import speak, notify, play_wake_ack, play_done_sound
try:
    from ui_tts.dave_bridge import on_wake, on_heard, on_done
except ImportError:
    from ui_tts.coucou_bridge import on_wake, on_heard, on_done


def _execute_single(text, ask_yes_no):
    """Execute a single atomic command through safety and executor."""
    parsed = parse(text)
    verdict = check(parsed)                       # {"decision": allow|confirm|block, "message": str}
    lang = parsed["lang"]
    if verdict["decision"] == "block":
        return {"success": False, "message": verdict["message"], "lang": lang}
    if verdict["decision"] == "confirm":
        speak(verdict["message"], lang)           # e.g. "Shut down the computer? Say yes or no."
        if parse_yes_no(ask_yes_no()) is not True:
            cancel_msg = "Cancelled." if lang == "en" else "تم الإلغاء."
            return {"success": False, "message": cancel_msg, "lang": lang}
    result = execute(parsed)                      # {"success": bool, "message": str}
    result["lang"] = lang
    return result


def handle(text, ask_yes_no):
    """text -> split_compound -> parse -> safety -> (confirm) -> execute -> feedback.
    Supports single commands as well as multi-action compound requests (Arabic & English).
    """
    on_heard(text)
    commands = split_compound(text)

    if len(commands) > 1:
        # Compound / multi-action request
        results = []
        all_success = True
        lang = "en"
        for cmd in commands:
            res = _execute_single(cmd, ask_yes_no)
            results.append(res)
            lang = res.get("lang", lang)
            if not res.get("success", False):
                all_success = False

        messages = [r.get("message", "").strip().rstrip(".") for r in results if r.get("message", "").strip()]
        connector = " و " if lang == "ar" else " and "
        combined_msg = connector.join(messages)

        if all_success:
            play_done_sound()
            if combined_msg:
                speak(combined_msg, lang)
        else:
            speak(combined_msg or ("Failed." if lang == "en" else "فشل."), lang)

        notify("Sound OS", combined_msg or "Done")
        on_done(all_success)
        return {"success": all_success, "message": combined_msg, "results": results}

    # Single command
    result = _execute_single(text, ask_yes_no)
    success = result.get("success", False)
    msg = result.get("message", "")
    lang = result.get("lang", "en")
    if success:
        play_done_sound()
        # Avoid double 'Done' speech: play_done_sound() already speaks "Done."
        if msg.strip().lower() not in ["done.", "done", "تم.", "تم"]:
            speak(msg, lang)
    else:
        speak(msg or "Failed.", lang)
    notify("Sound OS", msg)
    on_done(success)
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

