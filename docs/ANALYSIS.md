# 🎙️ Sound OS — Architectural Analysis & Engineering Decisions

> **Objective:** Document architectural decisions, model evaluation, and technical trade-offs across the Linux environment.

---

## 1. Overall Pipeline Architecture

```
Microphone → Wake Word → Speech-to-Text → Intent Parser → Safety Layer → Executor → UI/TTS
  (Abram)     (Abram)     (Mahmoud)       (Kurollos)      (Antonius)     (Yassin)   (Youssef)
```

The system is designed around **Decoupled Pipelines** where modules interface strictly via specifications defined in [`CONTRACT.md`](../CONTRACT.md). This enables independent unit testing through stubs and mocks without blocking on cross-team dependencies.

---

## 2. Module Implementations & Quality Assessment

| Module | Location | Status | Quality Summary |
|---|---|---|---|
| **Speech-to-Text (STT)** | `stt/` | Production | `faster-whisper` CPU int8 implementation, Egyptian Arabic normalization (`textnorm.py`), silence/repetition filters, and in-memory audio decoding. |
| **Intent Parser** | `intent_parser/` | Production | High-speed rule-based engine (< 5 ms) utilizing regex tokenization, compound splitters, and typo-tolerant fuzzy matching. |
| **Local LLM Fallback** | `intent_parser/llm_fallback.py` | Standby | Local Ollama integration (Qwen model) acting strictly as fallback on unknown inputs; restricted from producing dangerous intents. |
| **Interface Contract** | `CONTRACT.md` | Enforced | Rigorous specification of all payload structures and error containment rules. |
| **Pipeline Orchestrator** | `main.py` | Production | Sequential event orchestrator supporting live voice capture, direct text simulation, and headless background execution. |
| **Automated Test Suite** | `tests/` | 100% Passing | Comprehensive suite of over 475+ unit, integration, and contract tests. |

---

## 3. Key Technical Decisions

### A. Arabic Text Normalization
- **Challenge:** Multiple orthographic variants exist in written Arabic and speech transcriptions (e.g., alef with hamza variations `أ / إ / آ / ا`, taa marbuta `ة / ه`, alef maqsura `ى / ي`). In addition, Whisper sometimes emits diacritics (tashkeel).
- **Solution:** A centralized normalization layer (`intent_parser/normalize.py`) strips tashkeel, standardizes alef/hamza forms, removes character stretching (tatweel), and cleans punctuation prior to rule evaluation.

### B. Role of Local LLMs: When and Why?
- **Engineering Decision:** Primary reliance on a **Rule-Based Parser**. Fixed OS voice commands (applications, volume, brightness, navigation) are deterministic and finite. Rule parsing executes in under 2 ms with negligible memory overhead compared to several gigabytes required by LLMs.
- **LLM Function:** Operates strictly as an **optional fallback** for complex or non-standard phrasing, constrained by:
  1. Complete restriction from generating destructive intents (`shutdown`, `delete_file`).
  2. Enforced 5-second timeout window.
  3. Output formatted strictly according to contract schemas.
  4. Toggleable via `SOUNDOS_LLM=0`.

### C. OS Safety and File Sandboxing
- **Precautionary Principle:** Destructive commands are never executed directly without explicit verification.
- The Safety Layer issues interactive confirmation requests (`confirm`), and the parser verifies affirmative answers (`parse_yes_no`).
- File creation and deletion are restricted to `~/SoundOS_Files/`, and deletions leverage `gio trash` rather than permanent deletion (`rm`).
- `SOUNDOS_DRY_RUN=1` ensures pipeline validation without modifying system state.

### D. Audio Feedback and UI States
- Dual-language speech synthesis powered by `espeak-ng` provides rapid spoken feedback without network reliance.
- Visual state communication handled by the Dave animated interface, with clean fallback for headless execution via `SOUNDOS_NO_UI=1`.

---

## 4. Performance Targets & Empirical Results

| Metric | Target | Measured Result |
|---|---|---|
| Intent Parser Latency | < 50 ms | ~2-5 ms (Rule-based) ✅ |
| STT Latency (3s audio) | < 1.5 s | ~0.7-1.0 s (faster-whisper CPU int8) ✅ |
| Command Execution Latency | < 500 ms | ~0.05 ms (Direct Dispatch) ✅ |
| Memory Footprint (without LLM) | < 500 MB RAM | ~350 MB RAM (with Whisper Tiny) ✅ |
| Test Suite Coverage | 100% Passing | 479 / 479 Tests Passing ✅ |
