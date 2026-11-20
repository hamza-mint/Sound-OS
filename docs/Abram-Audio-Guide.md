# 🎙️ Abram's Guide — Audio Capture & Wake Word Module (`audio/`)
### Sound OS · Role 1 · Audio Capture & Wake Word Detection

> [!NOTE]
> **Scope & Boundaries:** You are the initial gatekeeper of the entire pipeline and the only module communicating directly with hardware audio inputs.  
> ❌ No responsibility for transcription (STT), intent parsing, or graphical rendering.  
> ✅ Your core deliverables: **Listen for the wake phrase (`wait_for_wake_word`) + Capture user utterances into clean 16 kHz Mono WAV audio (`record_utterance`)**.

---

## 1. Quick Reference & Specification

```text
Module Location: `audio/`
Input: Microphone audio streams (ALSA, PulseAudio, PipeWire, sounddevice)
Output: 16 kHz, 16-bit Mono PCM audio frames / WAV file path
Contract Rules: CONTRACT.md Rule 1: Functions must NEVER raise unhandled exceptions.
```

### Core Functions:
1. `wait_for_wake_word() -> None`:
   - Continuously reads microphone blocks.
   - Detects the wake phrase ("Hey Dave" / "ديف").
   - Provides graceful fallback to Enter key override when no microphone is present or for manual debugging.
2. `record_utterance(max_seconds: float = 6.0) -> str`:
   - Records speech until silence is detected via energy VAD (or until `max_seconds` timeout).
   - Writes the audio into an in-memory/temp WAV file (16 kHz, mono, 16-bit PCM).
   - Returns the absolute file path to the audio recording.

---

## 2. Hardware Rate Adaptation & Laptop Microphones

Many integrated laptop microphones (Realtek ALC, AMD ACP, Intel HDA) reject requests for 16000 Hz directly in Linux.

### Recommended Pattern:
- Open the input stream at the hardware's native rate (e.g., 44.1 kHz or 48 kHz).
- Convert and downsample the audio in-memory to 16 kHz mono using vectorized `numpy` operations.
- Avoid opening and closing the audio stream in tight loops; maintain persistent streaming where appropriate to prevent boundary loss.

---

## 3. Testing Your Module Locally

```bash
# Test audio capture independently
python3 -c "from audio import wait_for_wake_word, record_utterance; print('Imports valid!')"

# Run microphone diagnostic utility
python check_mic.py

# Run module unit tests
pytest tests/test_recorder.py
```
