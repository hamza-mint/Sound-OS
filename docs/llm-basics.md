# 🧠 LLM Basics in Sound OS

> A concise guide explaining **what components we use** and **key terminology**. For hands-on setup instructions, refer to `LLM-setup.md`.

---

## 1) Conceptual Analogy

Using the restaurant analogy:

| In a Restaurant | In Sound OS |
|---|---|
| Kitchen | **Ollama**: The engine executing the local language model |
| Chef | **The Model**: Comprehends the sentence and infers user intent |
| Waiter | **Our Code** (`intent.py` / `rules.py`): Relays the utterance and parses the response |

The LLM is positioned in Phase 2 (Intent Parsing):

```
🎤 Voice → [STT] Text → [Intent Parsing: Rule matching, fallback → LLM] → Intent Name → [Allowlist] → Linux Execution → Feedback
```

**Cardinal Rule:** The LLM **only proposes an intent name from the allowed list** (`open_browser` / `volume_up` / `shutdown` / `unknown`). It **never executes anything directly**. Execution is strictly guarded by the Allowlist, and high-risk actions (e.g., shutdown, file deletion) strictly mandate interactive confirmation.

### Responsibilities by Role

| Role | LLM Scope & Integration |
|---|---|
| 🧠 Role 3 (NLU) | Implements client code communicating with the LLM and parsing response payloads |
| 🐧 Role 4 (Linux) | Enforces Allowlist constraints regardless of LLM recommendations |
| 🔍 Role 6 (QA) | Benchmarks accuracy, response latency, and validates edge-case prompts |
| 👑 Role 1 (Leader) | Determines deployment strategy (inside VM vs. shared network host) |

---

## 2) Core Terminology (14 Key Concepts)

### LLM Runtime

| Term | Definition | Analogy / Example |
|---|---|---|
| **Ollama** | Local runtime service that serves open-source LLMs on your machine | The Kitchen |
| **Model** | Pre-trained neural network weights. Pulled by model identifier, e.g., `qwen3.5:2b`. Command: `ollama pull <model_name>` | The Chef |

### Networking (When LLM runs on a separate machine)

| Term | Definition | Analogy / Example |
|---|---|---|
| **localhost** | "This local machine". Ollama listens strictly on `localhost` by default. | "Only answering people inside the room." |
| **IP Address** | Network identifier of a node on a local or virtual network. | Apartment unit number. |
| **Port** | The network endpoint number Ollama listens on. Default: `11434`. | Specific doorway into the unit. |
| **API** | HTTP interface used by Python code to send prompts and receive responses. | The waiter carrying orders between table and kitchen. |
| **Host vs. VM** | **Host** = Physical OS (e.g., Windows). **VM** = Guest Linux instance (e.g., Xubuntu). | The entire building vs. a specific apartment inside. |
| **NAT vs. Bridged** | VM network adapter modes affecting host and subnet reachability. | How private building access connects to the street. |
| **Firewall** | Network packet filter. Port 11434 must be explicitly permitted for the safe subnet. | Security guard at the building gate. |
| **Tailscale** | Zero-config mesh VPN providing encrypted peer-to-peer tunnels without public port forwarding. | A private, dedicated intercom line between team members. |

### Architectural Rules

| Term | Definition | Analogy / Example |
|---|---|---|
| **Allowlist** | Strict enumerated whitelist of allowed system commands; all others are rejected even if the LLM suggests them. | The guest list at a VIP event. |
| **Fallback** | Tiered contingency plan: if the LLM is unreachable or times out, degrade gracefully to fuzzy matching (`rapidfuzz`). | Backup menu item if the chef is overloaded. |
| **Timeout** | Maximum permissible latency deadline before abandoning the LLM and failing over. | "If no response within 2 seconds, continue without it." |
| **OLLAMA_URL** | Environment variable configuring the Ollama endpoint dynamically across environments. | Writing the kitchen address on paper rather than engraving it into stone. |

---

## 3) References & Further Reading

- Ollama Official Site: https://ollama.com
- Ollama FAQ & Configuration (`OLLAMA_HOST`, ports): https://docs.ollama.com/faq.md
- Tailscale Documentation: https://tailscale.com/pricing/faq

> All definitions are tailored for system engineering. Model sizing, VRAM footprint, and latency must be empirically measured on team hardware before inclusion in project benchmarks.
