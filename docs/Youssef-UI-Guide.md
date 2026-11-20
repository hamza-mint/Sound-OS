# 🎨 Youssef's Guide — Voice UI & Feedback Module (`ui_tts/`)
### Sound OS · Role 6 · Graphical User Interface & Audio Feedback

> [!NOTE]
> **Scope & Boundaries:** Responsible for visual state indicators and desktop feedback.  
> ❌ No responsibility for audio recording, STT transcription, or intent parsing.  
> ✅ Your core deliverables: **Visual interface representing assistant states (idle, listening, processing, done, failed) + Desktop notifications (`notify`) + Speech feedback (`speak`)**.

---

## 1. Quick Reference & Specification

```text
Module Location: `ui_tts/`
Input: Pipeline events (on_wake, on_heard, on_done) & feedback text
Output: Graphical window display, system notifications, spoken audio
Contract Rules: CONTRACT.md Rule 7: Functions must NEVER raise unhandled exceptions.
```

### Core Functions:
1. `notify(title: str, body: str) -> None`:
   - Triggers native desktop notifications using `notify-send`.
   - Never raises exceptions if `notify-send` is absent or the display is headless.
2. `speak(text: str, lang: str = "en") -> None`:
   - Uses `espeak-ng` to generate fast speech output.
   - Respects `SOUNDOS_TTS_LANG` environment overrides.
3. Dave UI Bridge (`ui_tts/dave_bridge.py`):
   - `on_wake()`: Signals the visual interface that the wake word was triggered.
   - `on_heard(text)`: Displays the recognized utterance.
   - `on_done(success)`: Displays success checkmark or error indicators.
   - Respects `SOUNDOS_NO_UI=1` for headless or hidden background execution.

---

## 2. Testing Your Module Locally

```bash
# Verify UI and feedback imports
python3 -c "from ui_tts import notify, speak, on_wake, on_heard, on_done; print('UI imports valid!')"

# Test visual feedback window
python3 -c "from ui_tts import on_wake, on_heard, on_done; on_wake(); on_heard('Open browser'); on_done(True)"

# Run module unit tests
pytest ui_tts/test_ui.py
```
