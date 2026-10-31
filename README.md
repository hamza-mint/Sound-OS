# Sound OS

Voice control for Xubuntu (X11). Egyptian Arabic + English. Offline where possible.

    mic -> wake word -> speech-to-text -> intent parser -> safety -> executor -> voice feedback
    audio/   audio/       stt/            intent_parser/    safety/   executor/   ui_tts/

## Quick start (Python 3.10+)
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt            # pytest only
    echo $XDG_SESSION_TYPE                     # must print: x11
    python main.py --text "افتح فايرفوكس"       # whole pipeline with stubs, no mic
    SOUNDOS_DRY_RUN=1 python main.py --text "shut down"   # dangerous intents: ALWAYS dry-run while testing
    pytest -q                                  # parser + contract tests
    python scripts/parser_report.py            # accuracy per intent

## Where things are
| Folder | Owner | What |
|---|---|---|
| audio/ | Abram | microphone + wake word |
| stt/ | Mahmoud | speech-to-text |
| intent_parser/ | Kero | text -> JSON intent (rules + optional Ollama) |
| safety/ | Antonius | allow / confirm / block |
| executor/ | Yassin | run the command, systemd service |
| ui_tts/ | Youssef | notifications + text-to-speech |
| tests/, scripts/ | Kareem | automated tests, measurements |
| testdata/ | Kirollos | phrase list, recordings, manual test notes |
| docs/ | Antonius | team plan, install guide, user guide |

Read CONTRACT.md before writing code. Team rules and the 3-week plan: docs/TEAM_PLAN.md.
