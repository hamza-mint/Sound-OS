## 🤖 Dave UI & Voice (`ui_tts/`)

Dave (**D**igital **A**ssistant with **V**oice **E**xecution) is the face and the voice of Sound OS. He floats on the desktop with no window around him, shows what the system is doing — listening, working, succeeded, failed — and **talks**: his mouth moves with his voice and his speech bubble shows the words.

```python
from ui_tts import dave_desktop as dave
from ui_tts import notify, speak

dave.on_wake()                             # wake word heard  -> Dave thinks
dave.on_heard("open the browser")          # command recognised -> shows the command
dave.on_done(True)                         # finished (False = failed) -> happy / sad
speak("Done! I opened the browser.", "en") # Dave says it out loud (returns at once)
notify("Sound OS", "Command executed")     # desktop notification
```

---

### What Dave shows

| Pipeline stage | Call | What you see |
|---|---|---|
| Wake word heard | `on_wake()` | Thinking: thought bubble, pulsing antenna |
| Command recognised | `on_heard(text)` | Speech bubble with the recognised command |
| Command finished | `on_done(True)` | Happy hop with sparkles, "Done!" bubble |
| Command failed | `on_done(False)` | Sad Dave, tear, little shake, "Oops" bubble |
| Dave speaking | `speak(text, lang)` | Mouth moves with the voice, bubble shows the words |
| Idle | — | Head bobs, blinks, looks around |

Dave flies in from the corner and waves when he starts, and flies away shrinking when he closes. Drag him anywhere, click him for a little line, right-click for a menu.

---

### Public API

All public functions **never raise** (CONTRACT Rule 7). If a library or file is missing, Dave stays quiet (one hint is printed) instead of crashing.

| Function | Module | Description |
|---|---|---|
| `notify(title, body)` | `ui_tts` | Desktop notification through `notify-send` |
| `speak(text, lang)` | `ui_tts` | Dave says `text`. **Returns at once**; the voice plays in the background. Several calls play one after the other |
| `on_wake()` | `dave_desktop` | Show the listening state |
| `on_heard(text)` | `dave_desktop` | Show the recognised command (long text is shortened to 80 characters) |
| `on_done(success)` | `dave_desktop` | Show success (`True`) or failure (`False`) |
| `say(text, seconds=3.0)` | `dave_desktop` | Show a speech bubble without any sound |
| `hush()` | `dave_desktop` | Close the speech bubble |
| `start()` / `stop()` | `dave_desktop` | Put Dave on the desktop now / send him home (he flies away) |
| `is_speaking()` | `dave_voice` | `True` from the moment `speak()` is called until the last word has played. **Use it to mute the microphone while Dave talks**, so he does not hear himself |
| `stop_speaking()` | `dave_voice` | Cut Dave off and forget everything queued |

> [!NOTE]
> Dave's window runs as a small separate program that `ui_tts.dave_desktop` starts automatically. It closes by itself when your program ends, and he stays closed once the user has sent him home.

---

### Voice

Dave's voice is [Piper](https://github.com/rhasspy/piper) (offline): voice **`en_US-lessac-medium`**, pitched up with a light digital edge. Each sentence is spoken separately with a short pause after `.` `!` `?`, so write replies with proper punctuation. A phrase Dave has said before is cached, so repeats start instantly.

**Voice files** are not in the repo (about 60 MB). Download them once:

```bash
python -m piper.download_voices en_US-lessac-medium
```

Dave looks for `en_US-lessac-medium.onnx` (and its `.onnx.json`) in: `$SOUNDOS_VOICE_DIR`, `<repo>/piper-voices`, `<repo>/models/piper`, the folder next to the repo called `piper-voices`, `~/piper-voices`, and the current folder.

> [!NOTE]
> **Arabic:** there is no Arabic voice yet. `speak(text, "ar")` shows the words in Dave's bubble, silently.

---

### Try it

Run from the repo root (these are visual demos and are **not** part of `pytest`):

```bash
python -m ui_tts.demo_desktop   # Dave on the desktop: listens, answers out loud
python -m ui_tts.demo_voice     # voice only: finds the voice file, speaks, caches, interrupts
```

---

### Requirements

```bash
pip install -r requirements.txt   # needs: PySide6-Essentials, numpy, piper-tts
```

On Ubuntu/Debian also: `sudo apt install libnotify-bin` (notifications) and a sound player — `alsa-utils` (already listed above) or `pulseaudio-utils`.

> [!WARNING]
> **On Linux** Dave needs the desktop's *compositor* turned on to be see-through (Xfce: *Settings → Window Manager Tweaks → Compositor*), otherwise he gets a black box. On a **Wayland** session apps cannot place their own windows, so start Sound OS through XWayland: `QT_QPA_PLATFORM=xcb python main.py`.
> So far Dave has only been tested on Windows.

> [!NOTE]
> **License:** Piper is GPL-3.0-or-later, and each voice has its own license — check the voice's model card.

---

### Settings

| Where | Setting | Meaning |
|---|---|---|
| `dave_voice.py` | `SETTINGS` | Dave's sound: `pitch`, `crush`, `bits`, `smooth`, `wobble`, `pause`, `lead` |
| `dave_voice.py` | `VOICES` | Language → Piper voice (add an Arabic voice here later) |
| `dave_voice.py` | `BUBBLE` | `False` = the words do not appear in his bubble |
| `dave_character.py` | `GREETING`, `GREET_SECONDS`, `RESULT_SECONDS` | Hello bubble and how long happy / sad lasts |
| `dave_desktop.py` | `FLY_IN`, `WAVE`, `FLY_OUT` | Entrance, wave and exit timings (start of `_make_window_class`) |

| Variable | Example | Description |
|---|---|---|
| `SOUNDOS_VOICE_DIR` | `/home/me/voices` | Folder with the Piper voice files |
| `DAVE_DEBUG` | `1` | Dave prints every message he receives. Useful when he does not react |

> `SOUNDOS_TTS_SPEED` (words per minute) does not apply to Dave's Piper voice; his speed comes from `SETTINGS["pitch"]`.

---

### Files

| File | Purpose |
|---|---|
| `__init__.py` | `notify()` and `speak()` |
| `dave_character.py` | Dave himself: looks, moods, movement, talking mouth (no windows, no libraries) |
| `dave_stage.py` | Paints Dave with Qt on a see-through background |
| `dave_desktop.py` | The public functions and the floating window |
| `dave_voice.py` | His voice: Piper, sound effects, background playback, mouth signal |
| `demo_desktop.py`, `demo_voice.py` | Demos |
