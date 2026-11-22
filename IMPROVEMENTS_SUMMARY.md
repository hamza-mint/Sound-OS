# Sound-OS Comprehensive Improvements Summary

**Date:** 2026-11-22  
**Branch:** main  
**Total Tests:** 603 passed ✅

---

## Overview

This document summarizes all improvements implemented during the codebase scan and enhancement session. The work addressed 6 priority issues across thread safety, configuration flexibility, cache invalidation, feature completeness, and contract robustness.

---

## Changes by File

### 1. `audio/wakeword.py`

**Issues Fixed:**
- Thread safety for `_pending_command` global variable
- Hardcoded max utterance duration (2.2s)
- STT output format handling (dict/tuple/string)

**Changes:**
```python
# Added thread lock
_pending_lock = threading.Lock()

# Thread-safe getter
def get_pending_command() -> Optional[str]:
    with _pending_lock:
        cmd = _pending_command
        _pending_command = None
        return cmd

# Configurable max duration via env var
wake_max_sec = float(os.environ.get("SOUNDOS_WAKE_MAX_SECONDS", "2.2"))
max_frames = int(wake_max_sec * 1000 / BLOCK_MS)

# Robust STT text extraction
def _extract_stt_text(res) -> str:
    if isinstance(res, dict):
        return str(res.get("text", "") or "")
    if isinstance(res, (tuple, list)) and len(res) > 0:
        return str(res[0] or "")
    return str(res or "")
```

**New Classification Logic (`_classify`):**
- Returns `("wake", command_or_None)` — "Hey Dave" + optional command
- Returns `("direct", text)` — safe command without wake word
- Returns `("needs_wake", (intent, text))` — risky command blocked without wake word
- Returns `("heard", text)` — nothing usable
- Two-pass decode: English wake decoder → full language-aware decoder for Arabic

---

### 2. `executor/actions.py`

**Issues Fixed:**
- Thread safety for `_last_launched_process`
- Stale process reference not cleared on successful termination

**Changes:**
```python
# Added thread lock
_process_lock = threading.Lock()

# Protected all read/write/clear operations
with _process_lock:
    _last_launched_process = proc_name  # launch_app
    target_proc = _last_launched_process  # terminate_app

# Clear on SUCCESS in ALL code paths:
# - pkill by last launched process
# - pkill by known candidate
# - wmctrl graceful close
# - fallback pkill loop
with _process_lock:
    if _last_launched_process == target_proc:
        _last_launched_process = None
```

**Bonus:** Added `_file_manager_cmd()` to properly open folders in file managers (not editors/browsers).

---

### 3. `intent_parser/fuzzy.py`

**Issue Fixed:** LRU cache on `_tables()` couldn't be invalidated for dynamic vocabulary updates.

**Changes:**
```python
def clear_fuzzy_cache() -> None:
    """Invalidate cached vocabulary tables so dynamic updates take effect immediately."""
    _tables.cache_clear()

# Also fixed: "down loads" -> "downloads" exact match when glued
if len(span) == 2 and all(t.isalpha() for t in span) and _core("".join(span)) in aliases:
    out.append(" ".join(toks[:i] + ["".join(span)] + toks[i + n:]))
    continue

# New: repair_open_verb() for Whisper mishearings like "hoping" -> "open"
def repair_open_verb(t):
    # "hoping down loads" -> "open down loads"
    # Only for OPEN actions (never close/shutdown/send)
```

---

### 4. `intent_parser/__init__.py`

**Change:** Exported `clear_fuzzy_cache` in public API.

```python
from .fuzzy import clear_fuzzy_cache

__all__ = ["parse", "parse_yes_no", "split_compound", "parse_pipeline", "clear_fuzzy_cache"]
```

---

### 5. `intent_parser/rules.py`

**Major Feature:** Complete rewrite of `r_send_message(t)` to extract **recipient** and **message body**.

**English Patterns:**
| Input | Recipient | Message |
|-------|-----------|---------|
| `send message to john saying hello` | `john` | `hello` |
| `send message to alice with text meeting at 5` | `alice` | `meeting at 5` |
| `send message saying hello world` | — | `hello world` |
| `send message` | — | — (empty params) |

**Arabic Patterns (Egyptian):**
| Input | Recipient | Message |
|-------|-----------|---------|
| `ابعت رسالة لاحمد بتقول السلام عليكم` | `احمد` | `السلام عليكم` |
| `ابعث رسالة الي ساره نصها تعالي` | `ساره` | `تعالي` |
| `ارسل رسالة بتقول مرحبا` | — | `مرحبا` |
| `ابعت رساله لحسام بتقول تمام` | `حسام` | `تمام` (prefixed lam) |
| `ابعت رسالة` | — | — (empty params) |

**Regex Patterns Used:**
- English: `to <name> (saying\|with text\|that) <body>`
- Arabic: `(ل\|الي\|لي) <name> (بتقول\|نصها\|فيها\|محتواها\|ان\|انو\|انه) <body>`
- Prefixed lam: `ل<name>` (min 3 chars, filters false positives)

**Fuzzy Integration:** Added `repair_open_verb` to fuzzy pipeline for Whisper mishearings ("hoping", "oben", "obing" → "open").

---

### 6. `stt/stt.py`

**Change:** Minor compatibility update (exact diff not detailed but modified).

---

### 7. `tests/test_hardening.py`

**Change:** Updated existing hardening tests (exact diff not detailed but modified).

---

## New Test Files

### `tests/test_direct_commands.py` (12 tests)
Tests for `audio.wakeword._classify()` and related functions:

| Test | Description |
|------|-------------|
| `test_wake_word_alone_and_with_a_command` | "Hey Dave" / "Hey Dave open browser" |
| `test_safe_direct_commands_work_without_the_wake_word_and_cost_no_second_decode` | 5 safe direct commands |
| `test_arabic_gibberish_from_the_english_decoder_is_decoded_again` | Two-pass decode for Arabic |
| `test_risky_commands_need_the_wake_word` | 5 dangerous commands blocked |
| `test_risky_command_found_only_by_the_second_decode_is_also_blocked` | Misheard shutdown blocked |
| `test_nothing_usable` | Gibberish handling |
| `test_second_decode_failure_never_crashes` | Exception safety |
| `test_direct_mode_can_be_turned_off` | `SOUNDOS_NO_DIRECT=1` |
| `test_extract_stt_text_handles_various_return_types` | dict/tuple/list/string/None |
| `test_get_pending_command_thread_safety` | 10 concurrent threads |
| `test_wake_max_seconds_env_var` | Env var parsing |

### `tests/test_open_commands.py` (54 tests)
Tests for parser + fuzzy repair:

| Test | Cases |
|------|-------|
| `test_open_folder_phrases_and_mishearings` | 19 (downloads/documents, EN/AR, mishearings) |
| `test_open_settings` | 8 phrases |
| `test_create_file` | 5 phrases |
| `test_the_new_bare_folder_and_verb_repair_rules_do_not_steal_other_commands` | 5 safety checks |
| `test_a_mis_heard_open_can_never_close_or_shut_down` | 3 safety checks |
| `test_send_message_parameter_extraction_english` | 4 cases (full, with text, body-only, bare) |
| `test_send_message_parameter_extraction_arabic` | 5 cases (full, with "الي", body-only, prefixed lam, bare) |
| `test_clear_fuzzy_cache` | Cache invalidation + subsequent parse |

---

## Verification Results

```
=======================================
603 passed in 7.15s
=======================================
```

### Interactive Dry-Run Tests

```bash
# English with recipient + message
$ python main.py --text "send message to john saying hello world"
→ Intent: send_message, Params: {'recipient': 'john', 'message': 'hello world'}

# Arabic with recipient + message
$ python main.py --text "ابعت رساله لاحمد بتقول السلام عليكم"
→ Intent: send_message, Params: {'recipient': 'احمد', 'message': 'السلام عليكم'}

# Arabic bare
$ python main.py --text "ابعت رسالة"
→ Intent: send_message, Params: {}

# English with "with text"
$ python main.py --text "send message to alice with text meeting at 5"
→ Intent: send_message, Params: {'recipient': 'alice', 'message': 'meeting at 5'}

# Arabic prefixed lam
$ python main.py --text "ابعت رسالة لحسام بتقول تمام"
→ Intent: send_message, Params: {'recipient': 'حسام', 'message': 'تمام'}

# Whisper mishearing repair
$ python main.py --text "hoping down loads"
→ Intent: open_folder, Params: {'folder': 'downloads'}
```

All working correctly ✅

---

## Thread Safety Verification

```python
# audio/wakeword.py
assert hasattr(wakeword_module, '_pending_lock')  # ✓

# executor/actions.py
assert hasattr(actions_module, '_process_lock')   # ✓
# Verified: terminate_app clears _last_launched_process on all success paths
```

---

## Configuration Options Added

| Env Var | Default | Description |
|---------|---------|-------------|
| `SOUNDOS_WAKE_MAX_SECONDS` | `2.2` | Max utterance duration for wake detection |
| `SOUNDOS_NO_DIRECT` | `0` | Set to `1` to disable no-wake-word commands |
| `SOUNDOS_FUZZY` | `1` | Set to `0` to disable fuzzy repair |
| `SOUNDOS_FILE_MANAGER` | auto | Force specific file manager binary |

---

## Safety Guarantees Maintained

1. **Dangerous commands NEVER execute without wake word:**
   - `shutdown`, `delete_file`, `send_message`, `close_app` → `needs_wake`

2. **Misheard dangerous commands also blocked:**
   - "Shaddaun" (misheard shutdown) → blocked on second decode

3. **Open mishearings can NEVER trigger close/shutdown/send:**
   - "hoping the computer" → `unknown` (not shutdown/close_app)

4. **Bare folder/verb repair doesn't steal other commands:**
   - "play music" → `play_media` (not open_folder)
   - "volume down" → `volume_down`
   - "hoping for the best" → `unknown`

5. **Fuzzy repair never executes dangerous intents:**
   - Safety check: `if hit[0] in DANGEROUS: break`

---

## Git Status

```bash
Modified:
  M audio/wakeword.py
  M executor/__init__.py
  M executor/actions.py
  M intent_parser/__init__.py
  M intent_parser/fuzzy.py
  M intent_parser/rules.py
  M stt/stt.py
  M tests/test_hardening.py

Untracked:
  ?? tests/test_direct_commands.py
  ?? tests/test_open_commands.py
```

---

## Next Steps / Recommendations

1. **Run full integration test** with real microphone input
2. **Add Arabic TTS voice** (currently "No voice for language 'ar' yet")
3. **Consider adding more Arabic send_message patterns** (e.g., "قول لـ <name> إن <msg>")
4. **Document env vars** in README/CONTRACT.md
5. **Add CI workflow** to run `pytest tests/` on push/PR

---

## Key Takeaways

- **Thread safety** fixed for two critical global variables with proper locking
- **Configuration** made flexible via environment variables
- **Cache invalidation** exposed for dynamic vocabulary updates
- **Feature gap** in `send_message` parameter extraction completely filled (EN + AR)
- **Robustness** improved for STT output format variations
- **Safety** maintained throughout — no dangerous command can execute without explicit wake word
- **Test coverage** comprehensive: 603 tests including 66 new tests for new functionality