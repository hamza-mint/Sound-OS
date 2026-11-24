# Sound OS 🎙️💻

> **A fully local, offline-capable, privacy-first voice control operating layer for Linux (X11 & Wayland), optimized for Egyptian Arabic and English commands.**

---

```
                       ┌─────────────────────────┐
                       │   Microphone / Audio    │
                       └────────────┬────────────┘
                                    │ (Continuous Stream VAD)
                       ┌────────────▼────────────┐
                       │ Wake Word: "Hey Dave" / │
                       │         "Dave"          │
                       └────────────┬────────────┘
                                    │
                       ┌────────────▼────────────┐
                       │  STT: faster-whisper    │
                       │   (Local & Primed)      │
                       └────────────┬────────────┘
                                    │
                       ┌────────────▼────────────┐
                       │      Intent Parser      │
                       │ (Compound + Fuzzy NLP)  │
                       └────────────┬────────────┘
                                    │
                       ┌────────────▼────────────┐
                       │      Safety Layer       │
                       │ (Allowlist & Cooldowns) │
                       └────────────┬────────────┘
                                    │
                       ┌────────────▼────────────┐
                       │        Executor         │
                       │  (Apps, Media, System)  │
                       └────────────┬────────────┘
                                    │
                       ┌────────────▼────────────┐
                       │    Dave UI & TTS Voice  │
                       │ (Animated + Bilingual)  │
                       └─────────────────────────┘
```

---

## ✨ Key Features

* **100% Offline & Private:** All audio transcription runs locally on-device using `faster-whisper`. No voice recordings or telemetry ever leave your machine.
* **Bilingual Support (Egyptian Arabic & English):** Understands colloquial Egyptian Arabic verbs, suffixes, and phrasing (`افتحلي`, `اقفلي`, `عليلي الصوت`, `خفف الصوت`, `شغلي`, `ابعت رسالة`, `اقفل تطبيق`, etc.) alongside natural English commands.
* **Ultra-Fast Wake Word Response:** Features continuous streaming Voice Activity Detection (VAD) with zero clip boundary drops and instant in-memory processing.
* **Compound Multi-Action Commands:** Parse and execute multiple chained commands in a single utterance (e.g., *"Open the browser, turn up volume, and open calculator"*).
* **Fuzzy Typo-Tolerance:** Gracefully recovers from minor speech-to-text spelling discrepancies and acoustic variations without requiring heavy external models.
* **Strict Safety Guardrails:** Blocks unauthorized actions, protects destructive commands (`shutdown`, `delete_file`), enforces confirmation dialogs, and activates security cooldowns.
* **Flexible UI with Hidden / Headless Background Modes:** Features Dave, an animated expressive voice assistant GUI, while offering complete headless operation and systemd background service integration.

---

## 🚀 Installation & Quick Start

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/sound-os/Sound-OS.git
cd Sound-OS

# Create and activate virtual environment (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Install System Dependencies
* **On Fedora / RHEL:**
  ```bash
  sudo dnf install portaudio alsa-utils espeak-ng xdotool wmctrl
  ```
* **On Ubuntu / Debian / Linux Mint / Pop!_OS:**
  ```bash
  sudo apt update
  sudo apt install libportaudio2 alsa-utils espeak-ng xdotool wmctrl python3-tk
  ```

---

## 🔍 Diagnostics & Microphone Verification

Before launching the pipeline, run the built-in diagnostic tools to verify system prerequisites and test microphone input:

```bash
# Verify system tools, audio libraries, and model dependencies:
python scripts/doctor.py

# Auto-detect and test laptop microphone input:
python check_mic.py
```
> [!TIP]
> `check_mic.py` automatically detects Realtek, Intel, AMD, and USB microphones, adapting hardware sample rates (such as 48 kHz or 44.1 kHz stereo) to clean 16 kHz mono on-the-fly.

---

## 🎮 How to Run

### 1. Interactive Live Voice Mode (With Animated Dave UI)
```bash
python main.py
```
* Say **"Hey Dave"** or **"ديف"** (or press **Enter** to trigger listening).
* Speak your command in Arabic or English:
  * Arabic: *"افتح المتصفح"*, *"علي الصوت"*, *"افتح الآلة الحاسبة"*, *"اقفل التطبيق"*
  * English: *"Open terminal"*, *"Turn up volume"*, *"Open files"*, *"Close app"*
  * Compound: *"افتح المتصفح وعلي الصوت واقفل الحاسبة"*

### 2. Direct Text Simulation Mode (No Microphone Needed)
Useful for rapid development, testing, and CI pipelines:
```bash
python main.py --text "افتح المتصفح وعلي الصوت"
python main.py --text "Open terminal and turn up volume"
python main.py --text "اقفل تطبيق المتصفح"
```

### 3. WAV Audio File Mode
```bash
python main.py --wav stt/ar_open.wav
```

---

## 🕶️ Running in Background & Hidden Modes

If you want Sound OS to **run silently in the background and listen for voice commands without keeping a window on screen**, multiple methods are supported:

### Method 1: Single-Click Window Hide (Minimal GUI)
* Start the application normally: `python main.py`.
* When the Dave animated window appears, click the close button **(X)** with your mouse.
* **Result:** The graphical window disappears completely, while Sound OS **remains active in the background**, listening for the wake word and executing commands.

### Method 2: Headless Command-Line Flag (`--no-ui`)
Launch directly from the terminal without creating any GUI window:
```bash
# Using command-line argument:
python main.py --no-ui

# Or using environment variable:
SOUNDOS_NO_UI=1 python main.py
```

### Method 3: Permanent Background Service (Systemd User Service) ⭐
**Recommended for daily usage:** Sound OS starts automatically upon user login, restarts on crashes, and runs silently as a background Linux service.

Use the provided management script [`scripts/manage_service.sh`](file:///Workspace/GitHub/Sound-OS/scripts/manage_service.sh):

```bash
# Install and start the service:
./scripts/manage_service.sh install

# Check service status:
./scripts/manage_service.sh status

# Follow live recognition and execution logs:
./scripts/manage_service.sh logs

# Stop the service:
./scripts/manage_service.sh stop

# Restart the service:
./scripts/manage_service.sh restart

# Uninstall the service:
./scripts/manage_service.sh uninstall
```

### Method 4: Detached Daemon via `nohup`
To run in background across terminal sessions:
```bash
nohup python main.py --no-ui > soundos.log 2>&1 &
```
To terminate at any time:
```bash
pkill -f "python main.py"
```

---

## 🗣️ Supported Voice Commands Reference

Sound OS supports hundreds of command variants across English and Arabic. Below is an overview of commonly used actions:

### 1. Application Control
| Arabic Command | English Command | Action |
|---|---|---|
| **افتح المتصفح** / **افتحلي فايرفوكس** / **افتح كروم** | `open browser` / `open chrome` | Launch web browser |
| **اقفل المتصفح** / **اقفلي فايرفوكس** / **طفي الكروم** | `close browser` / `close chrome` | Close specified application |
| **اقفل تطبيق** / **اقفل التطبيق** / **اقفل البرنامج** | `close app` / `close the app` | Close the active/focused application |
| **افتح الطرفية** / **افتح الترمينال** | `open terminal` / `launch terminal` | Open terminal emulator |
| **افتح الآلة الحاسبة** / **هاتلي الحاسبة** | `open calculator` | Launch calculator |
| **افتح محرر النصوص** / **افتح المفكرة** | `open text editor` / `open notepad` | Open text editor |
| **افتح الإعدادات** / **افتح الضبط** | `open settings` | Launch system settings panel |

### 2. Audio & Media Controls
| Arabic Command | English Command | Action |
|---|---|---|
| **علي الصوت** / **عليلي الصوت شوية** / **ارفع الصوت** | `turn up volume` / `volume up` | Increase system volume |
| **وطي الصوت** / **خفف الصوت** / **هدي الصوت** | `lower volume` / `volume down` | Decrease system volume |
| **اكتم الصوت** / **اكتم** / **طفي الصوت** | `mute` / `silence audio` | Mute audio output |
| **شغل موسيقى** / **شغلي أغنية** | `play music` / `play media` | Launch default media player |

### 3. Display & Brightness Controls
| Arabic Command | English Command | Action |
|---|---|---|
| **اعلي السطوع** / **زود الإضاءة** | `brightness up` / `increase brightness` | Increase screen brightness |
| **وطي الإضاءة** / **قلل السطوع** | `brightness down` / `dim screen` | Decrease screen brightness |

### 4. Files & Folders
| Arabic Command | English Command | Action |
|---|---|---|
| **افتح الملفات** / **افتح مدير الملفات** | `open files` / `file manager` | Open default file manager |
| **افتح التنزيلات** / **افتح التحميلات** | `open downloads` | Open Downloads folder |
| **افتح المستندات** | `open documents` | Open Documents folder |
| **اعرض الصور** / **افتح مجلد الصور** | `open pictures` | Open Pictures folder |
| **اعمل ملف باسم notes.txt** / **انشئ hamza.txt** | `create hamza.txt` / `create file.txt` / `create file.py` | Create file directly with extension in home directory (`~/`) |
| **اعمل شيت اكسل** / **اعمل شيت بيانات** | `create excel sheet` / `create excel sheet budget` | Create spreadsheet (`.xlsx`) |
| **اعمل ملف وورد** / **اعمل مستند تقرير** | `create word document` / `create word document report` | Create document (`.docx`) |
| **اعمل ملف بايثون** / **انشئ سكريبت test** | `create python file` / `create python script test` | Create Python script (`.py`) |
| **اعمل ملف ماركداون** | `create markdown file readme.md` | Create Markdown file (`.md`) |

### 5. Search & Messaging
| Arabic Command | English Command | Action |
|---|---|---|
| **ابحث عن الطقس اليوم** / **دور على لينكس** | `search for linux tutorials` | Search query in web browser |
| **ابعت رسالة** / **ارسل رسالة** | `send message` | Open default messaging/mail app |

### 6. Compound Commands 🔗
Chain actions together naturally using conjunctions (**"و"** in Arabic, **"and"** in English):
* *"افتح المتصفح وعلي الصوت واقفل الحاسبة"*
* *"Open terminal and turn up volume and open files"*

---

## ⚙️ Configuration & Environment Variables

| Variable | Default / Options | Purpose |
|---|---|---|
| `SOUNDOS_NO_UI` | `0` (`1` to enable) | Run headless without graphical window. |
| `SOUNDOS_TTS_LANG` | `en` (`ar` or `auto`) | Assistant speech voice output language. |
| `SOUNDOS_TTS_SPEED` | `240` | Words per minute for speech synthesis (`espeak-ng`). |
| `SOUNDOS_MIC_DEVICE` | Empty (auto-detect) | Manually force specific audio device index/name. |
| `SOUNDOS_MIC_BACKEND` | `auto` (`sounddevice` / `arecord`) | Audio capture backend selection. |
| `SOUNDOS_DRY_RUN` | `0` (`1` to enable) | Simulate execution safely without modifying system state. |
| `SOUNDOS_WAKE_THRESHOLD` | `0.5` | Sensitivity threshold for wake word recognition. |

---

## 🧪 Automated Testing

Sound OS includes a comprehensive automated test suite of over **475+ tests** covering all modules:

```bash
# Run all automated tests:
pytest

# Run tests with verbose output:
pytest -v

# Run Arabic NLP & dialect understanding test suite:
pytest tests/test_arabic_nlp.py
```

---

## 📁 Repository Structure & Roles

```
Sound-OS/
├── audio/            # Mic capture, hardware rate adaptation, wake-word detection (Abram)
├── stt/              # Offline faster-whisper STT & VAD endpointing (Mahmoud)
├── intent_parser/    # Normalization, compound parsing, and fuzzy typo-repair (Kero)
├── safety/           # Security matrix, allowlists, cooldowns, and confirmation (Antonius)
├── executor/         # Linux OS execution engine, process termination, system actions (Yassin)
├── ui_tts/           # Dave animated graphical interface and bilingual TTS voice (Youssef)
├── scripts/          # Diagnostics (doctor.py) and system service tools (manage_service.sh)
├── tests/            # End-to-end automated unit and integration tests (Kareem)
├── main.py           # Core pipeline orchestration entry point
└── CONTRACT.md       # Architectural interface contracts and safety guidelines
```

---

## 📜 Architectural Contract

All public APIs across modules adhere strictly to the **"Never Raise"** principle defined in [`CONTRACT.md`](CONTRACT.md). Under no circumstance should a hardware failure or operating system error crash the main pipeline loop.
