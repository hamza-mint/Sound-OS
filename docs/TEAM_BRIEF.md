# 🎙️ Sound OS — Comprehensive Team Brief & Status

> **Project Phase:** Core Foundation & Production Integration Complete. All modules merged into `main` with 100% automated test coverage.  
> **Objective:** Document the system pipeline, module architecture, component interfaces, and team member deliverables.

---

## 🗺️ 1. End-to-End Pipeline Map

Sound OS is an offline-first Linux voice operating layer running on X11 / Wayland environments. Users issue spoken commands in colloquial Egyptian Arabic or English, and the system executes them deterministically:

```
🎙️ Microphone / Audio In
      ↓
🔔 [Role 1] Audio & Wake Word       ← Abram           (audio/)
      ↓  (16kHz mono WAV / PCM stream)
🗣️ [Role 2] Speech-to-Text          ← Mahmoud Hamed   (stt/)
      ↓  ({"text": "...", "lang": "ar"|"en", "confidence": ...})
🧠 [Role 3] Intent Parser           ← Kurollos (Kero) (intent_parser/)
      ↓  ({"intent": "...", "params": {...}})
🤖 [Backup] Qwen3 Fallback (Ollama)  ← Kurollos        (intent_parser/llm_fallback.py)
      ↓
🛡️ [Role 4] Safety Layer            ← Antonius        (safety/)
      ↓  ({"decision": "allow"|"confirm"|"block"})
⚙️ [Role 5] Command Executor        ← Yassin          (executor/)
      ↓  ({"success": true/false, "message": "..."})
🔊 [Role 6] UI & TTS Feedback       ← Youssef Alam    (ui_tts/)
```

**Quality Assurance & Continuous Testing:**
- 🎙️ **Role 7 — QA & Soundsets:** Kirollos Ibrahim (`testdata/`)
- 🧪 **Role 8 — Automated Testing & Benchmarks:** Kareem Waleed (`tests/`)

---

## 🤝 2. The Unified Interface Contract

The official project specification is defined in the root contract: [`CONTRACT.md`](../CONTRACT.md).

### Payload Schema Across Module Boundaries:

#### 1. STT Output (Mahmoud) ➡️ Intent Parser (Kero):
```json
{
  "text": "افتح فايرفوكس",
  "lang": "ar",
  "confidence": 0.95
}
```

#### 2. Intent Parser Output (Kero) ➡️ Safety Layer (Antonius):
```json
{
  "intent": "open_app",
  "params": { "app": "firefox" },
  "lang": "ar",
  "raw_text": "افتح فايرفوكس"
}
```

#### 3. Safety Layer Output (Antonius) ➡️ Command Executor (Yassin):
```json
{
  "decision": "allow",
  "message": "Action permitted."
}
```
*(Or `"decision": "confirm"` for sensitive intents like system shutdown and file deletion).*

#### 4. Executor Output (Yassin) ➡️ UI & TTS Feedback (Youssef):
```json
{
  "success": true,
  "message": "Opened firefox."
}
```

---

## 📊 3. Core Component Implementation Summary

| Module | Role Owner | Implementation Highlights |
|---|---|---|
| **Speech-to-Text (`stt/`)** | **Mahmoud Hamed** | Offline `faster-whisper` integration, Egyptian Arabic text normalization, VAD endpointing, and WER benchmarking. |
| **Intent Parser (`intent_parser/`)** | **Kurollos (Kero)** | Rule-based normalization covering all intents across Egyptian Arabic and English, compound multi-action splitter, and typo-tolerant fuzzy matching. |
| **LLM Fallback (`intent_parser/llm_fallback.py`)** | **Kurollos (Kero)** | Local fallback connector targeting Qwen3 via Ollama with strict timeouts and prompt containment. |
| **Safety Layer (`safety/`)** | **Antonius** | Tri-state gatekeeper verifying allowlists, interactive confirmation dialogs, confidence score filtering, and security cooldown timers. |
| **Command Executor (`executor/`)** | **Yassin** | Direct $O(1)$ dispatch table, detached process spawning, audio server detection (PipeWire/PulseAudio), VM brightness gamma scaling, and trash-based file sandboxing. |
| **UI & Voice Feedback (`ui_tts/`)** | **Youssef Alam** | Dave animated interactive voice window, desktop notifications (`notify-send`), and high-speed bilingual speech synthesis. |
| **Automated Testing (`tests/`)** | **Kareem Waleed** | 470+ automated unit, regression, integration, and contract tests. |

---

## 🔒 4. Engineering Principles

1. **Never Raise Exceptions:** Public functions across all modules must adhere to exception containment. Failures return structured error dictionaries (`{"success": false, "message": "..."}`) rather than crashing the runtime loop.
2. **Modular Decoupling:** Components interact exclusively through standard Python function arguments and primitive dictionaries defined in `CONTRACT.md`.
3. **Defense-in-Depth:** Safety checks operate both at the governance layer (`safety/`) and within the execution engine's filesystem sandbox (`executor/`).
4. **Offline First:** Zero telemetry and zero cloud dependencies for all core voice control tasks.

---

## 🚀 Running and Testing the Pipeline

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run automated test suite
pytest -q

# 3. Simulate text commands (no microphone required)
python main.py --text "افتح فايرفوكس"
python main.py --text "turn up volume"
python main.py --text "open terminal and turn up volume"
```
