# Sound OS - Interface Contract v1.0

Everyone codes against this file. Until your real code is ready, the stub in your folder already obeys it,
so nobody waits for anybody: `python main.py --text "افتح فايرفوكس"` works from day 1.

## 1. Functions (import from the package, never from inside it)
| # | Module | Owner | Function | Returns |
|---|---|---|---|---|
| 1 | `audio` | Abram | `wait_for_wake_word() -> None` (blocks) | - |
| 2 | `audio` | Abram | `record_utterance(max_seconds=6.0) -> str` | path of a 16 kHz mono WAV |
| 3 | `stt` | Mahmoud | `transcribe(wav_path, lang_hint=None) -> dict` | `{"text": str, "lang": "ar"\|"en", "confidence": 0..1}` |
| 4 | `intent_parser` | Kero | `parse(text, lang=None) -> dict` | Parsed (section 2) |
| 4b | `intent_parser` | Kero | `parse_yes_no(text) -> True\|False\|None` | answer to "are you sure?" |
| 5 | `safety` | Antonius | `check(parsed) -> dict` | `{"decision": "allow"\|"confirm"\|"block", "message": str}` |
| 6 | `executor` | Yassin | `execute(parsed) -> dict` | `{"success": bool, "message": str}` |
| 7 | `ui_tts` | Youssef | `speak(text, lang) -> None`, `notify(title, body) -> None` | - |

`main.py` (Kero) calls them in this order. `check()` is called on EVERY parsed command, before `execute()`.

## 2. JSON shapes
Parser output (exactly these four keys):
`{"intent": "open_app", "params": {"app": "firefox"}, "lang": "ar", "raw_text": "افتح فايرفوكس"}`
Executor output: `{"success": true, "message": "تم."}`

| intent | params | notes |
|---|---|---|
| open_app / close_app | `{"app": <canonical>}` | firefox chrome terminal files calculator editor vlc settings |
| volume_up / volume_down / mute | `{}` | mute = set muted, not toggle |
| brightness_up / brightness_down | `{}` | |
| create_file | `{"name": str}` (optional) | name may be missing: executor picks a default like `new_file.txt` |
| open_folder | `{"folder": str}` | canonical: home downloads documents desktop pictures music videos; anything else = a folder name under home |
| web_search | `{"query": str}` | |
| play_media | `{"query": str}` (optional) | no query = play the default / last playlist |
| shutdown | `{}` | DANGEROUS |
| delete_file | `{"name": str}` | DANGEROUS. Parser returns `unknown` if no name was heard |
| unknown | `{}` | no rule matched. Safety MUST block it; UI says "I did not understand" |

## 3. Rules for everybody
1. **Never raise** to the caller. Bad input -> a failure value (`success: false`, `text: ""`, `decision: "block"`).
2. **Text is UTF-8.** Every `message` is written in `parsed["lang"]` (Arabic for `ar`, English for `en`).
3. **Dry run:** if `SOUNDOS_DRY_RUN=1`, the executor only logs. Always use it when testing `shutdown` / `delete_file`.
4. **Dangerous intents** (`shutdown`, `delete_file`): safety returns `confirm`; `main.py` asks the user, listens once, and calls `parse_yes_no`. Only `True` continues. Silence or unclear = cancel.
5. **Delete is sandboxed** (Yassin + Antonius): only inside `~/SoundOS_Files/`, moved to trash (`gio trash`), never `rm`. Names with `/` or `..` are refused.
6. **The LLM fallback can never produce a dangerous intent.**
7. **Targets (adjust after week 1):** wake-to-action under 3 s; parser under 50 ms; executor under 1 s.
8. **Changing this file:** PR with label `contract`, approved by Kero and the owners on both sides, announced at the next stand-up. Bump the version number at the top.

## 4. Executor hints for Xubuntu (Xfce) on X11  (Yassin)
Check the session first: `echo $XDG_SESSION_TYPE` must print `x11`.
| Intent | Suggested tool |
|---|---|
| volume up/down | `pactl set-sink-volume @DEFAULT_SINK@ +5%` / `-5%` |
| mute | `pactl set-sink-mute @DEFAULT_SINK@ 1` |
| brightness | `brightnessctl set 10%+` / `10%-` (needs permission to the backlight; test on the demo laptop) |
| open app / folder / search | `subprocess.Popen([...], start_new_session=True)`, `xdg-open <path or URL>` |
| close app | `pkill -x <process>` (map canonical name -> process name in `executor/apps.py`) |
| shutdown | `systemctl poweroff` |
Keep the canonical-name -> command table in ONE dict so adding an app is one line. web_search needs internet; say so in the message if offline.
