# 🧪 Testing & Validation Guide (For All Team Members)

**Goal:** Enable every team member to test Sound OS on their local machine (or VM) and report clear, reproducible results. Real testing across diverse hardware reveals microphone, audio level, and accent discrepancies that automated tests cannot capture.

> [!IMPORTANT]
> **Safety Rule:** Always export `SOUNDOS_DRY_RUN=1` in your terminal session before testing. Without it, confirming "اقفل الجهاز" (Shutdown) with "yes" will **actually shut down your machine**. Only disable dry-run mode during final live demos.

---

## 1. Setup (10 Minutes, One-Time)

```bash
git pull                                   # Fetch latest updates
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
sudo apt install libportaudio2 alsa-utils wmctrl espeak-ng   # On Ubuntu / Xubuntu
python scripts/doctor.py                   # Check hardware & dependencies
```

`doctor.py` outputs ✅ / ⚠️ / ❌ with actionable fix commands. Resolve any ❌ items before proceeding.  
**Microphone issues inside a VM?** Enable **Sound Card → Connect at power on** in VMware settings, grant microphone permissions in the host OS, and run `python check_mic.py`.

```bash
pytest -q          # All 475+ tests must pass. If anything fails, note the error.
```

---

## 2. Text Simulation (No Microphone Required)

```bash
export SOUNDOS_DRY_RUN=1
python main.py --text "افتح المتصفح"
```

Test the representative phrases below. The second column shows the expected behavior:

| Input Phrase | Expected Intent | Notes |
|---|---|---|
| `افتح المتصفح` | `open_app` (firefox) | Launches browser |
| `علي الصوت` / `وطي الصوت` / `اكتم الصوت` | `volume_up` / `volume_down` / `mute` | Adjusts volume |
| `علي السطوع` | `brightness_up` | Uses xrandr inside VMs |
| `افتح الحاسبة` / `افتح الترمينال` / `افتح الملفات` | `open_app` | Launches target app |
| `افتح التحميلات` | `open_folder` (downloads) | Opens folder |
| `ابحث عن طقس القاهرة` | `web_search` | Requires active internet |
| `شغل موسيقى` | `play_media` | Opens default player |
| `اقفل التطبيق` | `close_app` (current active window) | Requires `wmctrl` on X11 |
| `افتح المتصفح وعلي الصوت` | Multi-action compound execution | Executes sequentially |
| `Open calculator` / `Turn up volume` | Standard English commands | Works identically |
| `اقفل الجهاز` | Triggers "Are you sure?" confirmation | Reply "yes" -> dry-run simulation |

**Negative Test Cases (Must NOT trigger any command — must return "unknown"):**  
`الساعة كام` (What time is it), `افتح الباب` (Open the door), `اقفل النور` (Turn off the light), `احكيلي نكتة` (Tell me a joke), `اطفي الجهار` (Misspelling of shutdown; destructive commands never trigger via fuzzy matching).

---

## 3. Live Voice Testing (Microphone)

```bash
export SOUNDOS_DRY_RUN=1
python main.py
```

Say **"Hey Dave"** or **"ديف"**, followed by your command. Repeat each phrase **3 times** (ideally with low ambient noise like a desk fan):
Record: Did the system understand correctly 3 out of 3 times? If not, what text was printed in `Heard Input`?

**Key Evaluation Points:**
- **Dialect & Vocabulary:** Test both colloquial Egyptian and formal Arabic (e.g., *"وطي الصوت"* vs *"خفض الصوت"*).
- **Latency:** Observe `Total Duration` printed from end of speech to execution.
- **Confirmation Flow:** Say *"اقفل الجهاز"* -> answer *"لا"* -> verify cancellation. Test remaining silent -> verify timeout.
- **Low-Resource Systems:** On machines with <= 4 GB RAM, test with `export SOUNDOS_STT_MODEL=tiny`.

---

## 4. Recording Test Datasets (Measuring WER)

To measure recognition accuracy across team voices:

```bash
cd stt
python record_set.py --speaker spk01 --condition quiet     # Replace spk01 with your handle
python record_set.py --speaker spk01 --condition noisy     # Background noise condition
```

Follow on-screen prompts. Blank lines indicate silence trials to measure false-trigger rates.

To calculate Word Error Rate (WER):
```bash
pip install jiwer
python eval_wer.py tiny            # Compare across tiny, base, and small models
python eval_wer.py tiny --no-prompt
```

---

## 5. Issue Reporting Template

```
Hardware: (Bare Metal / VMware / VirtualBox)   RAM: (e.g. 8GB)   Python: (python --version)
Model: (tiny / base / small)                   Microphone: (Built-in / USB / Headset)
Spoken Phrase:
Recognized Text (Heard Input):
Expected Intent:
Observed Output:
```
