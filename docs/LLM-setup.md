# 🛠️ Running the LLM (Ollama) — Step-by-Step Guide

> Read `llm-basics.md` first if any terminology or concepts are unfamiliar.
> After each milestone, verify against the **✅ Expected Result** indicator. If the result does not match, pause and inspect system logs before proceeding.

<a id="index"></a>

---

## 📑 Index

### Action Checklist by Role

| Role | Step-by-Step Execution Sequence |
|---|---|
| 👑 **Host Machine Owner** (GPU Laptop) | [Phase 1](#phase-1) → [Phase 2](#phase-2) → [Phase 3](#phase-3) → [Phase 4 (Node Sharing)](#phase-4) → [Common Commands](#commands) → [Final Verification](#final-test) |
| 👥 **Team Members** | [Phase 4](#phase-4) → [Common Commands](#commands) → [Final Verification](#final-test) |

> Team members should begin their setup **after** the host machine owner has verified Phases 1 and 2.

### Table of Contents

| Section | Target Audience |
|---|---|
| [System Architecture & Tailscale Overview](#big-picture) | All (Reference) |
| [Phase 0: Pre-Flight Checklist](#phase-0) | Entire Team |
| [Phase 1: Ollama & Model Provisioning (Windows Host)](#phase-1) | Host Machine Owner |
| [Phase 2: Tailscale Mesh & Firewall Configuration (Windows Host)](#phase-2) | Host Machine Owner |
| [Phase 3: Host Machine Guest VM Configuration](#phase-3) | Host Machine Owner |
| [Phase 4: Team Guest VMs & Tailscale Node Sharing](#phase-4) | Team Members + Host Owner |
| [Common Commands & Environment Configuration](#commands) | All |
| [Final Model Inference Verification](#final-test) | All |
| [Standalone Fallback: Local VM Ollama (No Host Dependency)](#fallback) | Fallback / Standalone |
| [Official References](#sources) | All |

---

<a id="big-picture"></a>

## System Architecture & Tailscale Overview

```
[GPU Host Laptop (Windows)] ──── Ollama + Model + Tailscale
          ▲
          │  Tailscale Encrypted Mesh (Private WireGuard Overlay)
          │
[Team Guest VMs (Xubuntu)]  ──── Tailscale + HTTP Inference Client
```

The GPU host acts as the **central compute node (Kitchen)**, the guest VMs act as **inference clients (Waiters)**, and Tailscale provides the **zero-trust private network tunnel**.

### 5 Essential Tailscale Concepts

| Concept | Description |
|---|---|
| **Tailscale** | Mesh VPN software built on WireGuard, connecting devices over a private overlay without opening public ports. |
| **Tailnet** | Your isolated private network, provisioned automatically upon initial account authentication. |
| **Admin Console** | Web portal displaying your active **Machines** and their network properties. |
| **`100.x.y.z` Address** | CGNAT virtual IP assigned to each device on the Tailnet, used as the server endpoint. |
| **Node Sharing** | Grants an external user or account secure access to a single designated node within your Tailnet. |

### Why Node Sharing Instead of a Single Team Tailnet?

The Tailscale free tier establishes user limitations per Tailnet. To accommodate teams flexibly without commercial licensing constraints:
- **Each member registers an individual free account**, maintaining their own Tailnet.
- **The host owner shares only the Ollama server node** directly with each member's account.
- Sharing a single machine does not consume additional member seats on the host's primary tier, while restricting team members strictly to the inference host.

---

<a id="phase-0"></a>

## Phase 0: Pre-Flight Checklist (Team Alignment)

- [ ] **Identify the Host Machine:** Discrete NVIDIA GPU with high VRAM, sufficient system RAM, stable AC power connection, and reliable internet access.
- [ ] **Select Baseline Model:** Default: `qwen3.5:2b` (subject to empirical latency validation).
- [ ] **Identity Accounts:** Every member has an active Google, Microsoft, or GitHub account for Tailscale SSO.
- [ ] **Standardized VM Deployed:** All members have imported the team Xubuntu VM with operational bridged/NAT networking.

---

<a id="phase-1"></a>

## Phase 1: Host Machine Setup — Ollama on Windows

**1) Install Ollama:** Download from https://ollama.com/download and run `OllamaSetup.exe`.  
✅ Ollama tray icon appears in the Windows system notification area.

**2) Verify CLI runtime:** Open PowerShell:
```powershell
ollama -v
```
✅ Prints active Ollama version string.

**3) Pull target model:**
```powershell
ollama pull qwen3.5:2b
```
✅ Download and verification complete with exit code 0.

**4) Verify model registry:** Navigate to `http://localhost:11434/api/tags` in your browser.  
✅ Returns JSON listing containing `"name": "qwen3.5:2b"`. Record the exact model tag.

**5) Bind Ollama to all network interfaces:**
1. Right-click the Ollama tray icon and select **Quit**.
2. Open Windows Start menu, search for `Environment Variables` → select **Edit the system environment variables**.
3. Under User Variables, click **New**:
   - Variable name: `OLLAMA_HOST`
   - Variable value: `0.0.0.0:11434`
4. Click **OK** to save and apply.
5. Launch Ollama again from the Start menu.  
✅ Ollama binds to `0.0.0.0:11434`. If Windows Firewall prompts for network access, allow it temporarily (we will secure it in Phase 2).

**6) Prevent Host Power Sleep:**  
Navigate to Windows Settings → System → Power & Sleep → Set **Sleep** to **Never** when plugged into AC power.

---

<a id="phase-2"></a>

## Phase 2: Host Machine Setup — Tailscale & Windows Firewall

**1) Download and Install Tailscale:** Obtain Windows installer from https://tailscale.com/download/windows.  
✅ Tailscale icon appears in the system tray.

**2) Authenticate:** Right-click tray icon → **Log in** → Authenticate using Google, Microsoft, or GitHub SSO.  
✅ State updates to "Connected". Your primary Tailnet is initialized.

**3) Identify Server IP Address:** Open https://console.tailscale.com/admin/machines or execute in PowerShell:
```powershell
tailscale ip -4
```
✅ Output displays a virtual IPv4 address starting with `100.`. Note this down as `SERVER_IP`.

**4) Configure Firewall Inbound Filtering (Restrict Port 11434 to Tailnet):**
1. Open **Windows Defender Firewall with Advanced Security** (`wf.msc`).
2. Navigate to **Inbound Rules** → Click **New Rule...**.
3. Select **Port** → **TCP** → Specific local ports: `11434` → **Allow the connection**.
4. Rule Name: `Ollama-Tailscale-Only`.
5. Open properties for `Ollama-Tailscale-Only` → Select **Scope** tab.
6. Under **Remote IP address**, choose **These IP addresses** → Click **Add...** → Enter `100.0.0.0/8` (the complete Tailscale CGNAT subnet).
7. Delete or disable any generic, unrestricted `ollama.exe` inbound rules that permit 0.0.0.0/0 traffic.  
> ⚠️ Ollama lacks native authentication tokens. Restricting remote access strictly to the `100.0.0.0/8` subnet prevents unauthorized external network access.

**5) Verify Local Endpoint:** Navigate to `http://<SERVER_IP>:11434` in the host browser.  
✅ Displays plain text response: `Ollama is running`.

---

<a id="phase-3"></a>

## Phase 3: Host Machine — Guest VM Configuration

> The host machine's own guest VM connects directly to the host Tailnet under the same account without requiring node sharing.

**1) Install Tailscale inside guest VM:**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```
✅ Package installation finishes cleanly.

**2) Authenticate:**
```bash
sudo tailscale up
```
Open the generated authentication URL in the guest browser, log in using the **same account used on the Windows host**, and authorize the machine.  
✅ Command returns to shell prompt with status connected.

**3) Verify Peer Status:**
```bash
tailscale status
```
✅ Both the guest VM and Windows host node appear in the active peer table.

**4) Verify Endpoint Connectivity:**
```bash
curl http://<SERVER_IP>:11434
```
✅ Returns `Ollama is running`.

Proceed to [Common Commands](#commands) and [Final Verification](#final-test).

---

<a id="phase-4"></a>

## Phase 4: Team Guest VMs & Tailscale Node Sharing

> Performed by each team member inside their respective Xubuntu VM.

**1) Install Tailscale in Guest VM:**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```
✅ Script completes with exit code 0.

**2) Authenticate with Individual Personal Account:**
```bash
sudo tailscale up
```
Open the generated URL and log in with your **own personal SSO account** (not the host owner's credentials).  
> ⚠️ Use your personal account to ensure proper isolation. Remember the identity used, as the invitation must match.

**3) Check Local Node State:**
```bash
tailscale status
```
✅ Displays your guest VM node.

**4) Transmit SSO Email to Host Owner:** Send your account email securely via direct message.

**5) Host Owner Shares Server Node:**
1. Host owner opens https://console.tailscale.com/admin/machines.
2. Locates the server host node → clicks the context menu (⋯) → **Share**.
3. Selects **Share by email** → enters the team member's email → **Share**.
4. Alternatively, generates a one-time single-use invite link. Do not enable reusable links.

**6) Member Accepts Invitation:**
1. Open the invitation link sent to your email.
2. Sign in using the **exact account used to authenticate the VM in Step 2**.
3. Accept the shared node invitation.  
✅ Shared server node appears in your Tailscale admin console under Machines.

**7) Verify Shared Node Resolution:**
```bash
tailscale status
curl http://<SERVER_IP>:11434
```
Obtain `<SERVER_IP>` from your local `tailscale status` output.  
✅ Returns `Ollama is running`.

### 🔧 Troubleshooting Reference Matrix

| Symptom | Root Cause | Remediation Step |
|---|---|---|
| Guest VM node offline | Tailscale daemon not active | Run `sudo tailscale up` |
| Server not visible in console | Invitation accepted under mismatched SSO identity | Log out and accept invite with VM identity |
| Expired invite link | Invite timed out (30-day limit) or revoked | Host owner generates fresh single-use invite |
| Connection timeout (port 11434) | Host asleep or Ollama service stopped | Verify Phase 1 steps 5 & 6 on host |
| Connection refused by host | Host firewall blocking `100.0.0.0/8` | Inspect Windows Defender rule `Ollama-Tailscale-Only` |
| Peer authentication expired | Tailscale session expiry triggered | Run `sudo tailscale up --force-reauth` |

---

<a id="commands"></a>

## Common Commands & Environment Configuration

Executed by all team members inside their respective guest VMs to ensure seamless code portability across different workstation setups.

### 1) Routine Network Verification

| Command | Operational Purpose |
|---|---|
| `curl -fsSL https://tailscale.com/install.sh \| sh` | Install Tailscale client |
| `sudo tailscale up` | Authenticate and register node with Tailnet |
| `tailscale status` | List active mesh peers and assigned `100.x` addresses |
| `curl http://<SERVER_IP>:11434` | Health check verifying Ollama daemon availability |

### 2) Environment Variable Persistence

Set persistent environment variables in `~/.bashrc`:

```bash
echo 'export OLLAMA_URL=http://<SERVER_IP>:11434' >> ~/.bashrc
echo 'export OLLAMA_MODEL=qwen3.5:2b' >> ~/.bashrc
source ~/.bashrc
echo "Configured endpoint: $OLLAMA_URL with model: $OLLAMA_MODEL"
```

*(Replace `<SERVER_IP>` with the actual `100.x.y.z` address of the Ollama server node).*

**Design Rationale:** Hardcoding server IPs inside Python modules breaks repository portability. Storing endpoint metadata in environment variables decouples codebase logic from machine-specific network topography:

```python
import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:2b")
```

---

<a id="final-test"></a>

## Final Model Inference Verification

Execute these verification checks to validate complete end-to-end functionality.

**1) Endpoint Availability:**
```bash
curl $OLLAMA_URL
```
✅ Expected response: `Ollama is running`.

**2) Model Registry Check:**
```bash
curl $OLLAMA_URL/api/tags
```
✅ Expected response: JSON document containing the target model tag.

**3) Single-Shot Inference Test:**
```bash
curl "$OLLAMA_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"$OLLAMA_MODEL\", \"prompt\": \"Reply with exactly one word: Ready\", \"stream\": false}" \
  | python3 -m json.tool --no-ensure-ascii
```
✅ Returns JSON response containing `"response": "Ready"`. Note: First prompt execution incurs initial model loading into VRAM.

*Optimization Note:* If inference latency is elevated due to reasoning overhead, include `"think": false` inside the request payload:
```bash
curl "$OLLAMA_URL/api/generate" \
  -d "{\"model\": \"$OLLAMA_MODEL\", \"prompt\": \"...\", \"think\": false, \"stream\": false}"
```

| Verification Result | Operational Status |
|---|---|
| All 3 verification steps pass | **Fully Operational** ✅ |
| Step 1 fails | Check `$OLLAMA_URL` assignment and review [Troubleshooting Matrix](#phase-4) |
| Step 2 missing model tag | Model tag misspelled or host download incomplete |
| Step 3 timeout or failure | Insufficient host VRAM or severe network latency |

---

<a id="fallback"></a>

## Standalone Fallback: Local VM Ollama (No Host Dependency)

If network connectivity is disrupted or the host machine is offline during local development:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:2b
curl http://localhost:11434/api/tags
```

Update your local shell environment to use the local fallback daemon:
```bash
export OLLAMA_URL=http://localhost:11434
```
Ensure the guest VM is allocated at least 4 GB of RAM to execute `2b` quantized weights comfortably on CPU.

---

<a id="sources"></a>

## Official References

**Tailscale Documentation:**
- Linux Client Installation: https://tailscale.com/docs/install/linux
- Windows Client Installation: https://tailscale.com/docs/install/windows
- Node Sharing Architecture: https://tailscale.com/docs/features/sharing
- Invitations vs. Node Sharing: https://tailscale.com/docs/reference/inviting-vs-sharing
- Tailscale Free Tier Capabilities: https://tailscale.com/docs/how-to/quickstart

**Ollama Documentation:**
- Linux Daemon Guide: https://docs.ollama.com/linux
- Network Binding FAQ (`OLLAMA_HOST`): https://docs.ollama.com/faq.md
- HTTP Generate Endpoint Specification: https://docs.ollama.com/api/generate.md

**GNU Bash:**
- Shell Startup File Hierarchy (`~/.bashrc`): https://www.gnu.org/s/bash/manual/html_node/Bash-Startup-Files.html
