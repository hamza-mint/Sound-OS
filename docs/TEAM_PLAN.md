# Team plan: rules, 3-week schedule, stand-up, blockers

## 1. Branching and pull-request rules (student version)
1. `main` always works. Nobody pushes to `main` (turn on branch protection: PR required, 1 approval, tests must pass).
2. One branch per task, from fresh `main`: `module/short-name`, e.g. `parser/egyptian-volume`, `executor/pactl-volume`.
3. Start every day with `git pull --rebase origin main`. Branches live at most 2 days.
4. Small PRs (under ~300 lines), each linked to an issue (`Closes #12`). Fill the PR template.
5. Review pairs (reviewer is never the author): parser <-> safety, audio <-> stt, executor <-> ui_tts, tests <-> testdata. Review within 24 h.
6. Squash-merge, delete the branch. The reviewer merges; Kero merges if the pair is stuck.
7. Touch only your own folder. Need a change elsewhere? Open an issue for the owner, or ask in the stand-up.
8. Interface changes only through CONTRACT.md (label `contract`).
9. Tags at milestones: `v0.1` (end week 1), `v0.2` (end week 2), `v1.0` (demo).

## 2. GitHub Projects board
Columns: Backlog - Ready - In progress - In review - Blocked - Done.
Fields: Owner, Module, Week (1/2/3). Labels: `contract`, `blocked`, `unblock-me`, `bug`, `dangerous`.
Rule: nobody has more than 2 cards in "In progress".

## 3. Three-week schedule (checklist per day)
**Week 1 - every module works alone against the contract**
- [ ] D1 Kickoff (45 min): read CONTRACT.md. Everyone clones, makes a venv, runs `python main.py --text "افتح فايرفوكس"` and `pytest -q`. Kero: branch protection, board, invite everyone. Everyone: 3 issues on the board.
- [ ] D2 Spikes (try 2 options each, 1 page of notes): Abram mic capture + wake-word options; Mahmoud STT options on 10 clips (AR + EN); Yassin volume/mute; Youssef offline TTS voices (AR + EN); Antonius safety rules table; Kirollos recording protocol (speakers, mics, noise levels); Kareem CI green; Kero parser v0.
- [ ] D3 Freeze tool choices (wake word, STT, TTS). First PRs merged.
- [ ] D4 Each module replaces its stub for at least 2 intents/functions and passes `tests/test_contract.py`.
- [ ] D5 Parser covers all 13 intents (done in this repo); Kirollos + Kareem start with `testdata/phrases.csv`; executor: open/close app + volume.
- [ ] D6 5-minute solo demo per module. Fix contract gaps.
- [ ] D7 Buffer + 15-min retro. Tag `v0.1`.

**Week 2 - end to end**
- [ ] D8 Wire real audio -> STT -> parser (print the JSON).
- [ ] D9 Safety + executor wired: 5 commands by voice (open/close app, volume up/down, mute).
- [ ] D10 Add brightness, open_folder, web_search, play_media; spoken feedback live.
- [ ] D11 Kirollos records the full voice set (AR + EN, 3+ speakers, quiet + noisy). Kareem's script reports STT word error rate and parser accuracy.
- [ ] D12 Fix the top 5 failures from the report (parser synonyms, STT model size, wake-word threshold).
- [ ] D13 Dangerous intents: confirmation flow, sandboxed delete, dry-run tests.
- [ ] D14 Buffer + retro. Tag `v0.2` (10+ commands end to end).

**Week 3 - harden and demo**
- [ ] D15 systemd user service: autostart on login, logs, restart on crash (Yassin).
- [ ] D16 Security + system testing (Kirollos): false wake-ups, misheard dangerous commands, runs as normal user, no secrets in the repo.
- [ ] D17 Re-measure. Decide on the Ollama fallback: only if rules miss > 15% on the real voice set AND latency stays acceptable.
- [ ] D18 FEATURE FREEZE. Docs finished (Antonius): install guide, command list, known limits.
- [ ] D19 Clean-install test on a fresh Xubuntu machine or VM, following only the README.
- [ ] D20 Demo rehearsal x2. Record a backup video. Fix only blockers.
- [ ] D21 Final demo. Tag `v1.0`. Retro.

## 4. Leader's daily checklist (Kero, ~20 min)
- [ ] Morning: open the board filter `label:blocked` and `label:unblock-me`; clear anything older than 24 h.
- [ ] Review queue: any PR waiting > 24 h? Ping the reviewer.
- [ ] Run the 15-min stand-up.
- [ ] After stand-up: talk to each blocker pair; update the board.
- [ ] Evening: `main` green? Merge ready PRs. Count Done cards (simple progress check).
- [ ] Write 3 lines in the stand-up thread: risks, decisions, tomorrow's focus.

Everyone daily: pull `main`, push your branch, update your issue, post your 3 stand-up lines.

## 5. 15-minute stand-up (8 people)
Standing, same time every day, start on time even if someone is missing. Rotate facilitator and timekeeper.

| Time | What |
|---|---|
| 0:00-0:12 | Round, max 90 s each. Exactly 3 lines per person (below). No problem-solving in the round. |
| 0:12-0:15 | Leader reads every blocker aloud and assigns an owner + a time. Decisions. Contract changes. |
After: a "parking lot" chat only for the people involved in a problem.

Each person posts this in the daily GitHub Discussion (or issue) "Stand-up YYYY-MM-DD":
```
Yesterday: <done / not done, issue #>
Today:     <ONE concrete task, issue #>
Blocked:   <@name - what exactly I need - needed by when>   (or: none)
```

## 6. Who is blocked on whom
1. Blocked? Put the card in **Blocked**, add label `blocked`, write the name in the "Blocked by" note.
2. Open an issue assigned to the blocker: `[UNBLOCK] <what I need> for @me`, label `unblock-me`, due date.
3. The blocker treats `unblock-me` issues as top priority. Not solved in 24 h -> Kero steps in (use a stub, change the plan, or pair up).
4. Because every module has a working stub, nobody should be blocked for more than a day.

Usual dependencies (check these first):
| Waiting person | Waits for | Fallback while waiting |
|---|---|---|
| Kero (parser) | Mahmoud: real STT text samples | `testdata/phrases.csv` |
| Antonius (safety) | Kero: parser JSON | `tests` + stub parser output |
| Yassin (executor) | Kero + Antonius: final intents and params | CONTRACT.md table |
| Youssef (TTS/UI) | Yassin: message text | stub messages |
| Mahmoud (STT) | Abram: WAV files | Kirollos' recordings |
| Kareem (tests) | everybody | stubs; he can write tests on day 1 |
| Kirollos (test set) | Kero: phrase list | `testdata/phrases.csv` |
