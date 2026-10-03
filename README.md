# Sound OS

A university Operating Systems project. Sound OS is a voice control tool for Linux. You speak a command, and Linux runs it.

```
voice -> [speech to text] -> [find the command] -> [run it on Linux] -> [reply to the user]
```

## Small first version (MVP)

These 3 commands should work from the microphone:

1. "open the browser" -> `open_browser`
2. "turn the volume up" -> `volume_up`
3. "shut down the computer" (after a confirm step) -> `shutdown`

Anything else can wait until later.

## How to run (on Xubuntu 24.04)

```bash
git clone https://github.com/hamza-mint/Sound-OS.git
cd Sound-OS
pip install -r requirements.txt
python3 src/main.py          # safe test mode: prints the command, does not run it
python3 src/main.py --real   # real run (use with care)
python3 -m pytest tests      # tests
```

## Project files

| Path | Team role | What it does |
|---|---|---|
| `src/speech.py` | Role 2 | Turns voice into text (for now it reads from the keyboard) |
| `src/intent.py` | Role 3 | Turns text into a command name |
| `src/execution.py` | Role 4 | Runs the command on Linux (allowlist + confirm for risky commands) |
| `src/ui.py` | Role 5 | Shows status and speaks a reply |
| `src/main.py` | Role 1 | Connects all the steps |
| `tests/` | Role 6 | Tests and QA notes |
| `docs/` | Role 7 + 1 | Weekly reports and `ARCHITECTURE.md` |

The full plan between the parts is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Important rules

- Do not put secrets (API keys and similar) on GitHub. Use a `.env` file (it is in `.gitignore`).
- Do not run raw text as a system command. Every command must be on the allowlist.
- If you change how the parts work together, tell the whole team and update `docs/ARCHITECTURE.md`.
