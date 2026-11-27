"""Sound OS pipeline glue (owner: Kero).
Run with no microphone:  python main.py --text "افتح فايرفوكس"
Run the real loop:       python main.py
"""
import argparse
import os
import re
import sys
import threading
import time

if sys.platform.startswith("linux") and "DISPLAY" in os.environ and "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "xcb"

from audio import wait_for_wake_word, record_utterance, get_pending_command, get_pending_audio
from stt import transcribe, transcribe_probe
from intent_parser import parse, parse_yes_no, split_compound
from safety import check, notify_confirmed
from executor import execute
from ui_tts import speak, notify, play_wake_ack, play_done_sound, wait_until_silent, strip_own_speech
try:
    from ui_tts.dave_bridge import on_wake, on_heard, on_done, say as say_bubble, hush
except ImportError:
    from ui_tts.coucou_bridge import on_wake, on_heard, on_done, say as say_bubble, hush
try:
    from ui_tts.dave_bridge import set_llm_state
except ImportError:
    def set_llm_state(state):                 # no GUI available: terminal line only
        return None


def _llm_thinking(active):
    """Shown while the local LLM (Plan B) works: ~10 s on a CPU, so the user must see that Dave is not frozen."""
    if active:
        print("[Sound OS] \U0001F914 Asking the local LLM (Plan B)... this can take ~10 s", flush=True)
        try:
            say_bubble("Thinking... \U0001F914", seconds=25)
        except Exception:
            pass
    else:
        try:
            hush()
        except Exception:
            pass


def _llm_state_changed(state, detail):
    """Every LLM state change: one clear line in the terminal and the same state on Dave's screen."""
    from intent_parser.llm_fallback import STATE_TEXT
    icon = {"ready": "\U0001F9E0", "thinking": "\U0001F914", "starting": "\u23F3", "down": "\u26A0", "off": "\u26D4"}.get(state, "")
    line = f"[Sound OS] {icon} LLM {STATE_TEXT.get(state, state)}" + (f" - {detail}" if detail else "")
    print(line, flush=True)
    try:
        set_llm_state(state)
    except Exception:
        pass


def _setup_llm(block=True):
    """The local LLM (Plan B) is ON by default: SOUNDOS_LLM=0 turns it off. Starts `ollama serve` if it is not
    running, checks the model, loads it in the background. Never raises: without it the rules still work."""
    if os.environ.setdefault("SOUNDOS_LLM", "1") != "1":
        _llm_state_changed("off", "SOUNDOS_LLM=0")
        return
    from intent_parser import llm_fallback
    llm_fallback.set_thinking_callback(_llm_thinking)
    llm_fallback.set_state_callback(_llm_state_changed)

    def work():
        try:
            llm_fallback._set_state("starting")
            ok, msg = llm_fallback.ensure_running()
            if not ok:
                print(f"[Sound OS] \u26A0 {msg}. The rules keep working without it.", flush=True)
                llm_fallback.disable()
            else:
                llm_fallback.warm_up(wait=block)        # single-shot: finish loading first; live loop: in the background
                llm_fallback._set_state("ready", msg)
        except Exception as exc:
            print(f"[Sound OS] \u26A0 LLM fallback disabled: {exc!r}", flush=True)
            llm_fallback.disable()

    if block:
        work()
    else:
        threading.Thread(target=work, daemon=True).start()      # do not delay the microphone loop


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


# ---- "I said CLOSE but it OPENED again" -------------------------------------------------------------
# Whisper (especially tiny/base) often hears "اقفل المتصفح" as "افتح المتصفح": same letters, similar sound.
# Opening an app that we opened a moment ago is almost always that mistake (or a retry of it), so instead of
# opening a 2nd window we ask once. yes -> close it, no -> open it again as asked, silence -> do nothing.
# SOUNDOS_REPEAT_CHECK=0 turns it off.
REPEAT_WINDOW_SEC = int(os.environ.get("SOUNDOS_REPEAT_WINDOW", "15"))
_RECENT_OPEN = {}                      # app -> time.monotonic() of the last successful open_app


def _remember_result(parsed, ok):
    intent, app = parsed.get("intent"), (parsed.get("params") or {}).get("app")
    if not app:
        return
    if intent == "open_app" and ok:
        _RECENT_OPEN[app] = time.monotonic()
    elif intent == "close_app":
        _RECENT_OPEN.pop(app, None)


def _check_repeat_open(parsed, ask_yes_no):
    """Returns (parsed_to_run, skip). May turn an open_app into close_app after the user says yes."""
    if os.environ.get("SOUNDOS_REPEAT_CHECK", "1") == "0" or parsed.get("intent") != "open_app" or ask_yes_no is None:
        return parsed, False
    # Only suspect افتح/اقفل confusion on Arabic commands, never clear English ("Open the browser")
    raw = parsed.get("raw_text") or ""
    if parsed.get("lang") == "en" or (raw and not _ARABIC.search(raw)):
        return parsed, False
    app = (parsed.get("params") or {}).get("app")
    last = _RECENT_OPEN.get(app)
    if not app or last is None or time.monotonic() - last > REPEAT_WINDOW_SEC:
        return parsed, False
    print(f"[Sound OS] ❓ {app} was opened {int(time.monotonic() - last)}s ago: did you mean CLOSE it?")
    answer = _ask_close(app, ask_yes_no)
    if answer is True:
        return dict(parsed, intent="close_app"), False
    if answer is False:
        _RECENT_OPEN[app] = time.monotonic()
        return parsed, False                                      # really wants a second one
    print("[Sound OS] ❓ No clear answer: doing nothing.")
    return parsed, True


# ---- "open" or "close"? -------------------------------------------------------------------------------
# Whisper copies the FIRST verb of its prompt when the audio is unclear, so "اقفل المتصفح" comes out as "افتح المتصفح".
# The clip is decoded again WITHOUT a prompt (garbled but honest); if that text gives no evidence for the heard verb
# (intent_parser/verb_check.py) we ask ONE short yes/no question (yes/no sound nothing like افتح/اقفل).
# SOUNDOS_PROBE=0 turns it off. Costs one extra (prompt-free) decode, only for Arabic open/close of a known app.
_ARABIC = re.compile("[\u0600-\u06FF]")


def _ask_close(app, ask_yes_no):
    """One short question. True = close, False = open, None = unclear."""
    speak(f"Close {app}? Yes or no.", "en")
    resp = ask_yes_no()
    return parse_yes_no(resp if isinstance(resp, str) else (resp or {}).get("text", ""))


def _resolve_open_close(text, audio, ask_yes_no, probe=None):
    """Returns the text to run ("" = do nothing)."""
    if (os.environ.get("SOUNDOS_PROBE", "1") == "0" or ask_yes_no is None or audio is None
            or not text or not _ARABIC.search(text)):
        return text
    from intent_parser.verb_check import verb_doubt, command_text, APP_NOUN
    first = parse(text)
    app = first["params"].get("app")
    if first["intent"] not in ("open_app", "close_app") or app not in APP_NOUN:
        return text
    try:
        probe_text = (probe or transcribe_probe)(audio)
    except Exception:
        return text
    if not verb_doubt(first["intent"], app, probe_text):
        return text                                               # the audio backs the heard verb
    print(f"[Sound OS] \u2753 Not sure if you said OPEN or CLOSE {app} (heard {text!r}, prompt-free: {probe_text!r}).")
    answer = _ask_close(app, ask_yes_no)
    if answer is True:
        return command_text("close_app", app)
    if answer is False:
        return command_text("open_app", app)
    print("[Sound OS] \u2753 No clear answer: doing nothing.")
    return ""


def _speakable(msg):
    """Text for the voice: the [DRY-RUN] / [تجربة] tag is for the screen, read aloud it was 'D-R-Y R-U-N'."""
    return re.sub(r"\[(?:DRY-RUN|تجربة)\]\s*", "", str(msg or "")).strip()


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
    lang = "ar" if _ARABIC.search(text) else (lang_hint or "en")

    for i, cmd in enumerate(commands, 1):
        t_cmd_start = time.perf_counter()
        parsed = parse(cmd, lang=lang)
        intent = parsed.get("intent", "unknown")
        params = parsed.get("params", {})

        prefix = f"[{i}/{len(commands)}]" if len(commands) > 1 else ""
        print(f"[Sound OS] 🧠 Understood Action {prefix}:")
        print(f"   • Command:  {cmd!r}")
        print(f"   • Intent:   {intent}")
        if params:
            print(f"   • Params:   {params}")
        print(f"   • Status:   Executing...")

        parsed, skip = _check_repeat_open(parsed, ask_yes_no)
        if skip:
            results.append({"success": True, "message": "", "lang": parsed.get("lang", "en")})
            continue
        if parsed.get("intent") == "close_app":
            intent, params = "close_app", parsed.get("params", params)
        res = _execute_single(cmd, ask_yes_no, lang_hint=lang_hint, confidence=confidence, parsed=parsed)
        _remember_result(parsed, res.get("success", False))
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
            speak(_speakable(combined_msg), lang)
    else:
        speak(_speakable(combined_msg) or ("Failed." if lang == "en" else "فشل."), lang)

    notify("Sound OS", combined_msg or "Done")
    on_done(all_success)
    total_elapsed = time.perf_counter() - t_start
    print(f"[Sound OS] ⏱ Total Duration: {total_elapsed:.2f}s")
    print(f"[Sound OS] ──────────────────────────────────────────────\n")
    return {"success": all_success, "message": combined_msg, "results": results}


def listen_utterance(resolve_open_close: bool = True, prompt_user: bool = False):
    """Real microphone path: record one utterance and return full STT metadata dict."""
    wait_until_silent()            # never record Dave's own "Yes?" / answer (the mic hears the speakers)
    if prompt_user:
        print("[Sound OS] 🎙 Listening for command... Speak now.", flush=True)
    wav_path = record_utterance()
    if not wav_path:
        return {"text": "", "lang": "en", "confidence": 0.0}
    res = transcribe(wav_path)
    if resolve_open_close and res.get("text"):
        res = dict(res, text=_resolve_open_close(
            res["text"], wav_path, lambda: listen_utterance(resolve_open_close=False).get("text", ""),
        ))
    try:
        from audio.debug_clips import save_clip
        save_clip(wav_path, res.get("text", ""), "cmd")        # only if SOUNDOS_SAVE_AUDIO is set
    except Exception:
        pass
    cleaned = strip_own_speech(res.get("text", ""))
    if cleaned != res.get("text", ""):
        print(f"[Sound OS] 🔇 Ignored Dave's own voice: {res.get('text', '')!r} -> {cleaned!r}")
        res = dict(res, text=cleaned)
    return res


def listen_text():
    """Legacy helper returning just the text (skips open/close re-prompting to avoid recursion)."""
    res = listen_utterance(resolve_open_close=False)
    return res.get("text", "")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="skip mic + STT and parse this text")
    ap.add_argument("--wav", help="skip mic and transcribe this WAV file")
    ap.add_argument("--no-ui", "--headless", dest="no_ui", action="store_true", help="run in background/headless mode without GUI window")
    args = ap.parse_args()
    if args.no_ui:
        os.environ["SOUNDOS_NO_UI"] = "1"
    _setup_llm(block=bool(args.text or args.wav))     # single-shot modes wait for it; the live loop does not
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
            wait_until_silent()        # finish speaking first, so the wake word listener doesn't hear Dave
            wait_for_wake_word()
            pending_cmd = get_pending_command()
            pending_audio = get_pending_audio()
            if pending_cmd:
                pending_cmd = _resolve_open_close(pending_cmd, pending_audio, listen_text)
                if not pending_cmd:
                    continue
                print(f"\n[Sound OS] 🚀 Command captured directly: {pending_cmd!r}")
                on_wake()
                handle(pending_cmd, ask_yes_no=listen_text)
            else:
                print("\n[Sound OS] 🔔 Wake word detected!")
                on_wake()
                # TTS speaks wake response naturally (no static i_am_here.wav file)
                tts_lang = os.environ.get("SOUNDOS_TTS_LANG", "en").lower().strip()
                wake_prompt = "Yes?" if tts_lang == "en" else "نعم؟"
                speak(wake_prompt, tts_lang)
                stt_data = listen_utterance(prompt_user=True)
                raw_text = stt_data.get("text", "")
                if raw_text:
                    handle(
                        raw_text,
                        ask_yes_no=listen_text,
                        lang_hint=stt_data.get("lang"),
                        confidence=stt_data.get("confidence", 1.0),
                    )
                else:
                    print("[Sound OS] 🔇 No speech detected.", flush=True)
                    on_done(False)

