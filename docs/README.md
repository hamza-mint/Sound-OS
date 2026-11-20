# 📚 Documentation & Reports Hub

Welcome to the **Sound OS** documentation hub. This directory contains all engineering reports, team planning artifacts, operational runbooks, and module-specific guides.

---

## 🗂️ Documentation Index

### 1. System Architecture & Team Status
* [**`ARCHITECTURE_AND_STATUS_REPORT.md`**](./ARCHITECTURE_AND_STATUS_REPORT.md) — **Comprehensive Architecture & Integration Status Report**  
  Detailed technical analysis of the slide presentation requirements, module integration status, performance bottlenecks, resolved challenges, and production readiness.
* [**`EXECUTOR_AND_SAFETY_REPORT.md`**](./EXECUTOR_AND_SAFETY_REPORT.md) — **Executor & Safety Engineering Defense Report**  
  Deep dive into the 7-layer pipeline flow, subprocess containment, allowlist security, cooldown timers, and zero-crash execution design.
* [**`EXECUTOR_REPORT.md`**](./EXECUTOR_REPORT.md) — **Command Executor & Systemd Service Report**  
  Implementation summary of the command execution module, process lifecycle management, cross-distro command fallbacks, and automated test coverage.
* [**`TEAM_BRIEF.md`**](./TEAM_BRIEF.md) — **Comprehensive Team Brief & Role Roadmap**  
  Detailed overview of the end-to-end pipeline, module milestones, and team member responsibilities.
* [**`TEAM_PLAN.md`**](./TEAM_PLAN.md) — **3-Week Sprint Plan & Branching Guidelines**  
  Branching strategies, daily review pairs, blocker escalation, and sprint timeline.
* [**`ANALYSIS.md`**](./ANALYSIS.md) — **Architectural Decisions & Feasibility Analysis**  
  Comparative study of faster-whisper, local LLM fallbacks, Egyptian Arabic acoustic processing, and performance benchmarks.

---

### 2. Guides & Technical Manuals
* [**`TESTING-GUIDE.md`**](./TESTING-GUIDE.md) — **Team Manual Testing & Hardware Runbook**  
  Step-by-step instructions for testing microphone capture, desktop virtualization (VMware/VirtualBox), audio downsampling, and pipeline dry-runs.
* [**`Abram-Audio-Guide.md`**](./Abram-Audio-Guide.md) — **Audio Capture & Wake Word Guide**  
  Microphone streaming, continuous VAD, wake phrase detection, and ALSA/PulseAudio/PipeWire configuration.
* [**`Youssef-UI-Guide.md`**](./Youssef-UI-Guide.md) — **GUI & Voice Feedback Guide**  
  Dave animated interactive graphical interface, Tkinter rendering, desktop notifications via `notify-send`, and low-latency speech synthesis.
* [**`LLM-setup.md`**](./LLM-setup.md) — **Local LLM Setup & Ollama Guide**  
  Instructions for configuring local LLM backends (Ollama / Qwen) as fallback intent parsers.
* [**`llm-basics.md`**](./llm-basics.md) — **LLM Terminology & Fundamentals**  
  Conceptual reference explaining model weights, quantization (GGUF/AWQ), context lengths, and memory requirements.

---

### 3. Historical Archives
* [**`weekly-reports/`**](./weekly-reports/) — Archive of weekly presentation deliverables and slides.

---

## 🤝 Project Interface Contract

All modules strictly adhere to the formal API specification defined in the root contract:  
👉 [**`CONTRACT.md`**](../CONTRACT.md)

---

## 🧪 System Verification

To run the complete automated test suite:
```bash
source .venv/bin/activate
pytest -q
```
**Expected Status:** All 470+ tests passing (`479 passed in ~7s`).
