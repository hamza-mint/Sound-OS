"""Sound OS pipeline glue (owner: Kero).
Run with no microphone:  python main.py --text "افتح فايرفوكس"
Run the real loop:       python main.py
"""
import argparse
import os
import time

from audio import wait_for_wake_word, record_utterance, get_pending_command
from stt import transcribe
from intent_parser import parse, parse_yes_no, split_compound
from safety import check, notify_confirmed
from executor import execute
from ui_tts import speak, notify, play_wake_ack, play_done_sound
try:
    from ui_tts.dave_bridge import on_wake, on_heard, on_done
except ImportError:
    from ui_tts.coucou_bridge import on_wake, on_heard, on_done


def _execute_single(text, ask_yes_no, lang_hint=None, confidence=1.0, parsed=None):
    """Execute a single atomic command through safety and executor with metadata persistence.
    `parsed` lets the caller reuse a parse it already did (the fuzzy pass makes a 2nd parse not free)."""
    parsed = dict(parsed) if parsed else parse(text, lang=lang_hint)
    parsed["confidence"] = confidence

    # Bilingual voice selection (Slide 8 & 9):
    # If SOUNDOS_TTS_LANG is set, honor it. Otherwise, match the command language!
    env_tts_lang = os.environ.get("SOUNDOS_TTS_LANG", "").lower().strip()
    if env_tts_lang in ("en", "ar"):
        parsed["lang"] = env_tts_lang
    elif not parsed.get("lang"):
        parsed["lang"] = lang_hint or "en"

    verdict = check(parsed)                       # {"decision": allow|confirm|block, "message": str}
    lang = parsed.get("lang", "en")
    if verdict["decision"] == "block":
        return {"success": False, "message": verdict["message"], "lang": lang}
    if verdict["decision"] == "confirm":
        speak(verdict["message"], lang)           # e.g. "Shut down the computer? Say yes or no."
        resp = ask_yes_no()
        resp_text = resp if isinstance(resp, str) else resp.get("text", "")
        if parse_yes_no(resp_text) is not True:
            cancel_msg = "Cancelled." if lang == "en" else "تم الإلغاء."
            return {"success": False, "message": cancel_msg, "lang": lang}

        # Confirmation granted: enforce direct approval and activate cooldown (Slide 6, 7 & 9)
        parsed["approved"] = True
        notify_confirmed(parsed.get("intent", ""))

    result = execute(parsed)                      # {"success": bool, "message": str}
    result["lang"] = lang
    return result


def handle(text, ask_yes_no, lang_hint=None, confidence=1.0):
    """text -> split_compound -> parse -> safety -> (confirm) -> execute -> feedback.
    Provides clear visibility on understanding, execution progress, and timing.
    """
    t_start = time.perf_counter()
    on_heard(text)
    commands = split_compound(text)

    print(f"\n[Sound OS] ──────────────────────────────────────────────")
    print(f"[Sound OS] 🎤 Heard Input: {text!r} (lang={lang_hint or 'auto'}, conf={confidence:.2f})")
    if len(commands) > 1:
        print(f"[Sound OS] 🔗 Multi-action: Split into {len(commands)} commands: {commands}")

    results = []
    all_success = True
    lang = lang_hint or "en"

    for i, cmd in enumerate(commands, 1):
        t_cmd_start = time.perf_counter()
        parsed = parse(cmd, lang=lang_hint)
        intent = parsed.get("intent", "unknown")
        params = parsed.get("params", {})

        prefix = f"[{i}/{len(commands)}]" if len(commands) > 1 else ""
        print(f"[Sound OS] 🧠 Understood Action {prefix}:")
        print(f"   • Command:  {cmd!r}")
        print(f"   • Intent:   {intent}")
        if params:
            print(f"   • Params:   {params}")
        print(f"   • Status:   Executing...")

        res = _execute_single(cmd, ask_yes_no, lang_hint=lang_hint, confidence=confidence, parsed=parsed)
        cmd_time = time.perf_counter() - t_cmd_start
        results.append(res)
        lang = res.get("lang", lang)
        ok = res.get("success", False)
        msg = res.get("message", "")

        if ok:
            print(f"   • Result:   ✅ {msg} (completed in {cmd_time:.2f}s)")
        else:
            all_success = False
            print(f"   • Result:   ❌ {msg} (failed in {cmd_time:.2f}s)")

    messages = [r.get("message", "").strip().rstrip(".") for r in results if r.get("message", "").strip()]
    connector = " and " if lang == "en" else " و "
    combined_msg = connector.join(messages)

    if all_success:
        if combined_msg:
            speak(combined_msg, lang)
    else:
        speak(combined_msg or ("Failed." if lang == "en" else "فشل."), lang)

    notify("Sound OS", combined_msg or "Done")
    on_done(all_success)
    total_elapsed = time.perf_counter() - t_start
    print(f"[Sound OS] ⏱ Total Duration: {total_elapsed:.2f}s")
    print(f"[Sound OS] ──────────────────────────────────────────────\n")
    return {"success": all_success, "message": combined_msg, "results": results}


def listen_utterance():
    """Real microphone path: record one utterance and return full STT metadata dict."""
    wav_path = record_utterance()
    if not wav_path:
        return {"text": "", "lang": "en", "confidence": 0.0}
    return transcribe(wav_path)


def listen_text():
    """Legacy helper returning just the text."""
    res = listen_utterance()
    return res.get("text", "")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="skip mic + STT and parse this text")
    ap.add_argument("--wav", help="skip mic and transcribe this WAV file")
    ap.add_argument("--no-ui", "--headless", dest="no_ui", action="store_true", help="run in background/headless mode without GUI window")
    args = ap.parse_args()
    if args.no_ui:
        os.environ["SOUNDOS_NO_UI"] = "1"
    if args.text:
        on_wake()
        handle(args.text, ask_yes_no=lambda: input("yes/no> "))
    elif args.wav:
        on_wake()
        stt_res = transcribe(args.wav)
        print(f"[STT Recognized]: text={stt_res['text']!r} lang={stt_res['lang']} (confidence={stt_res.get('confidence', 1.0):.2f})")
        handle(stt_res["text"], ask_yes_no=lambda: input("yes/no> "), lang_hint=stt_res["lang"], confidence=stt_res.get("confidence", 1.0))
    else:
        print("[Sound OS] Ready and listening for wake word or direct command...")
        while True:
            wait_for_wake_word()
            pending_cmd = get_pending_command()
            if pending_cmd:
                print(f"\n[Sound OS] 🚀 Command captured directly: {pending_cmd!r}")
                on_wake()
                handle(pending_cmd, ask_yes_no=listen_text)
            else:
                print("\n[Sound OS] 🔔 Wake word detected!")
                on_wake()
                # TTS speaks wake response naturally (no static i_am_here.wav file)
                wake_prompt = "Yes?" if os.environ.get("SOUNDOS_TTS_LANG", "en").lower().strip() == "en" else "نعم؟"
                speak(wake_prompt, "en")
                stt_data = listen_utterance()
                raw_text = stt_data.get("text", "")
                if raw_text:
                    handle(
                        raw_text,
                        ask_yes_no=listen_text,
                        lang_hint=stt_data.get("lang"),
                        confidence=stt_data.get("confidence", 1.0),
                    )
                else:
                    on_done(False)

