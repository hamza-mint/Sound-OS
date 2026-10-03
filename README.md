# Sound OS

Sound OS is a university Operating Systems project.

It is **not** a new operating system. It is a small voice layer on Linux.
You say a short command. Linux does a safe, fixed action.

The real challenge is to make this work on a **weak computer**
(about 4 GB RAM, no GPU, often inside a virtual machine)
and to understand **simple Arabic**.

---

## How it works

```
voice  →  text  →  command name  →  Linux action  →  reply
```

1. Listen and turn speech into text.
2. Match the text to one known command.
3. Run only that command from a short allowlist.
4. Tell the user what happened.

Each step is a separate Python file. The files share small JSON messages,
so each person can write their part alone.

**Example**

```text
{"text": "افتح المتصفح"}
        ↓
{"intent": "open_browser", "args": {}}
        ↓
{"ok": true, "message": "تم فتح المتصفح"}
```

If the phrase is not known, return `"intent": "unknown"` and say you did not understand.

---

## First working version (MVP)

If these three commands work from the microphone to Linux, the project succeeds.
Anything else can wait.

| You say | Command name | What Linux does |
|---|---|---|
| افتح المتصفح / open the browser | `open_browser` | open the default browser |
| ارفع الصوت / turn the volume up | `volume_up` | raise the volume a little |
| اطفي الجهاز / shut down | `shutdown` | power off **after a confirm step** |

---

## Keep it light

We all work on **Xubuntu 24.04 LTS** in a shared virtual machine (`.ova`).

| Part | Light tool | Why |
|---|---|---|
| Speech to text | Vosk small Arabic model | offline, low RAM |
| Understand the phrase | RapidFuzz or simple matching | no big language model |
| Speak back | espeak-ng | fast and tiny |
| Window | Tkinter | already in Python |
| Run the action | `subprocess` + Linux tools | `xdg-open`, `pactl`, `systemctl` |

Do not add heavy tools unless the team agrees.

---

## Folders

This repo has empty folders on purpose. **We write the code ourselves.**

```text
src/     Python files for each step
tests/   Tests and QA notes
docs/    Weekly reports and team notes
```

When you start coding, create these files in `src/`:

| File | Job |
|---|---|
| `speech.py` | voice → `{"text": "..."}` |
| `intent.py` | text → `{"intent": "...", "args": {}}` |
| `execution.py` | intent → `{"ok": true/false, "message": "..."}` |
| `ui.py` | show status and optional voice reply |
| `main.py` | connect all steps |

---

## Safety

- Do not put secrets or API keys on GitHub. Use a `.env` file.
- Do not run raw user text as a shell command.
- Only run commands on the allowlist.
- Shutdown needs a clear yes.
- Default mode should print the command and **not** run it.

Large VM files (`.ova`) stay on Google Drive, not in this repo.

---

## Team

Seven people. Six weeks. GitHub is for code and docs. Trello is for tasks.

1. Leader — repo, shared contract, merge
2. Speech — microphone to text
3. Intent — text to command name
4. Linux actions — run the command
5. UI — status window and reply
6. QA — tests, noise, and speed
7. Docs — weekly reports and this README

---

## Start

```bash
git clone https://github.com/hamza-mint/Sound-OS.git
cd Sound-OS
```

Then add your files under `src/`, `tests/`, and `docs/`.
Install only the light libraries your part needs.
