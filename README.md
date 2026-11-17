# Sound OS 🎙️💻

Voice control system for Linux (X11 / Wayland), optimized for Egyptian Arabic & English commands. Fully local, privacy-respecting, and offline-capable.

```
[ Microphone ]  -->  [ Wake Word: "Hey Dave" / "ديف" ]  -->  [ STT: Whisper ]
        |                                                           |
[ Voice / Dave UI ]  <--  [ Executor ]  <--  [ Safety Guard ]  <--  [ Intent Parser ]
```

---

## 🚀 Quick Start Guide (For Any Team Member)

### 1. Setup Environment
```bash
git clone https://github.com/sound-os/Sound-OS.git
cd Sound-OS

# Create and activate virtual environment (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> [!NOTE]
> On Ubuntu/Debian, make sure PortAudio is installed:
> ```bash
> sudo apt install libportaudio2 alsa-utils
> ```
> On Fedora:
> ```bash
> sudo dnf install portaudio alsa-utils
> ```

---

### 2. Verify Your Laptop Microphone 🎤
Run the built-in diagnostic tool to auto-detect and test your laptop mic:
```bash
python check_mic.py
```
This automatically detects Realtek, AMD, Intel, and USB microphones, auto-adjusts sample rates (e.g. 48 kHz / 44.1 kHz stereo to 16 kHz mono), and verifies volume levels.

---

### 3. Run Automated Tests ✅
```bash
pytest
```
Runs 300+ automated unit and integration tests across all modules.

---

### 4. Run Sound OS

#### A. Direct Text Command (No Mic Needed)
```bash
python main.py --text "افتح المتصفح وعلي الصوت"
python main.py --text "Open calculator and open terminal"
```

#### B. Full Live Voice Mode (With Animated Dave UI)
```bash
python main.py
```
- Say **"Hey Dave"** or **"ديف"** (or press **Enter**).
- Speak your command:
  - Arabic: *"افتح المتصفح"*, *"علي الصوت"*, *"افتح الآلة الحاسبة"*
  - English: *"Open terminal"*, *"Turn up volume"*, *"Open files"*
  - Compound: *"افتح المتصفح وعلي الصوت واقفل الحاسبة"*

---

## 🛠️ Helpful Options & Environment Variables

| Variable | Values / Example | Description |
|---|---|---|
| `SOUNDOS_MIC_DEVICE` | `0`, `4`, or name substring | Force a specific microphone device index or name. |
| `SOUNDOS_MIC_BACKEND` | `auto`, `sounddevice`, `arecord` | Choose audio recording backend (`auto` selects best). |
| `SOUNDOS_DRY_RUN` | `1` | Test dangerous commands without actually shutting down / deleting. |
| `SOUNDOS_TTS_SPEED` | `240` (default) | Words per minute for speech synthesis. |
| `SOUNDOS_LANG` | `ar`, `en` | Override language detection for STT. |

---

## 📁 Repository Structure & Roles

| Folder | Owner | Role & Functionality |
|---|---|---|
| `audio/` | Abram | Mic capture, laptop rate adaptation, wake-word detection ("Hey Dave" / "ديف") |
| `stt/` | Mahmoud | Speech-to-text (offline faster-whisper, candidate scoring, VAD endpointing) |
| `intent_parser/` | Kero | Intent parser, multi-action compound splitters, regex & LLM rules |
| `safety/` | Antonius | Action guardrails (allow, confirm, block dangerous actions) |
| `executor/` | Yassin | Execution engine (apps, volume, audio, brightness, files, system) |
| `ui_tts/` | Youssef | Animated Dave GUI, system tray, fast English/Arabic TTS |
| `tests/` | Kareem | Automated test suite (300+ pytest tests) |
| `docs/` | Team | Architecture, contracts, and guides |

See [CONTRACT.md](CONTRACT.md) for module API agreements.
