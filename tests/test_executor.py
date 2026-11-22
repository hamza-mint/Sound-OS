"""
Pytest suite for executor module (Owner: Yassin / Kareem)
Covers: CONTRACT.md compliance, safety, dry-run, Arabic aliases, timing.
"""
import os
import time

import pytest

from executor import execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _dry_run_on():
    """Most tests run with dry-run enabled for safety."""
    os.environ["SOUNDOS_DRY_RUN"] = "1"
    yield
    os.environ.pop("SOUNDOS_DRY_RUN", None)


def _assert_contract(res):
    """Every executor result MUST satisfy the CONTRACT.md shape."""
    assert isinstance(res, dict), f"Expected dict, got {type(res)}"
    assert set(res) == {"success", "message"}, f"Keys mismatch: {set(res)}"
    assert isinstance(res["success"], bool)
    assert isinstance(res["message"], str)


# ---------------------------------------------------------------------------
# 1. Contract shape — all 13 intents
# ---------------------------------------------------------------------------
ALL_INTENTS = [
    {"intent": "open_app",        "params": {"app": "firefox"},       "lang": "en", "raw_text": "open firefox"},
    {"intent": "close_app",       "params": {"app": "firefox"},       "lang": "en", "raw_text": "close firefox"},
    {"intent": "volume_up",       "params": {},                       "lang": "en", "raw_text": "turn volume up"},
    {"intent": "volume_down",     "params": {},                       "lang": "ar", "raw_text": "خفض الصوت"},
    {"intent": "mute",            "params": {},                       "lang": "ar", "raw_text": "اكتم الصوت"},
    {"intent": "brightness_up",   "params": {},                       "lang": "en", "raw_text": "brightness up"},
    {"intent": "brightness_down", "params": {},                       "lang": "ar", "raw_text": "خفض السطوع"},
    {"intent": "create_file",     "params": {"name": "hello.txt"},    "lang": "en", "raw_text": "create file hello.txt"},
    {"intent": "open_folder",     "params": {"folder": "downloads"},  "lang": "en", "raw_text": "open downloads"},
    {"intent": "web_search",      "params": {"query": "weather"},     "lang": "en", "raw_text": "search weather"},
    {"intent": "play_media",      "params": {"query": "music"},       "lang": "ar", "raw_text": "شغل موسيقى"},
    {"intent": "shutdown",        "params": {},                       "lang": "en", "raw_text": "shut down"},
    {"intent": "delete_file",     "params": {"name": "test.txt"},     "lang": "ar", "raw_text": "احذف الملف test.txt"},
]


@pytest.mark.parametrize("cmd", ALL_INTENTS, ids=[c["intent"] for c in ALL_INTENTS])
def test_contract_shape_all_intents(cmd):
    """Every intent must return exactly {success: bool, message: str}."""
    _assert_contract(execute(cmd))


# ---------------------------------------------------------------------------
# 2. Dry-run mode — dangerous intents
# ---------------------------------------------------------------------------
def test_dry_run_shutdown():
    res = execute({"intent": "shutdown", "params": {}, "lang": "en"})
    assert res["success"] is True
    assert "DRY-RUN" in res["message"]


def test_dry_run_delete():
    res = execute({"intent": "delete_file", "params": {"name": "x.txt"}, "lang": "en"})
    _assert_contract(res)
    # dry-run should NOT actually delete; file didn't exist so success is False
    # but the contract shape must be valid either way


# ---------------------------------------------------------------------------
# 3. Safety — path traversal
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_name", [
    "../etc/passwd",
    "../../evil.sh",
    "foo/bar.txt",
    "/absolute/path.txt",
])
def test_path_traversal_create_blocked(bad_name):
    os.environ["SOUNDOS_DRY_RUN"] = "0"
    res = execute({"intent": "create_file", "params": {"name": bad_name}, "lang": "en"})
    assert res["success"] is False
    assert "traversal" in res["message"].lower() or "not permitted" in res["message"].lower()


@pytest.mark.parametrize("bad_name", [
    "../etc/passwd",
    "foo/bar.txt",
])
def test_path_traversal_delete_blocked(bad_name):
    os.environ["SOUNDOS_DRY_RUN"] = "0"
    res = execute({"intent": "delete_file", "params": {"name": bad_name}, "lang": "en"})
    assert res["success"] is False


def test_delete_no_name():
    res = execute({"intent": "delete_file", "params": {"name": ""}, "lang": "en"})
    assert res["success"] is False


# ---------------------------------------------------------------------------
# 4. Arabic aliases
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alias,expected_canonical", [
    ("المتصفح", "firefox"),
    ("الحاسبة", "calculator"),
    ("الطرفية", "terminal"),
    ("المحرر", "editor"),
    ("الإعدادات", "settings"),
])
def test_arabic_alias_resolves(alias, expected_canonical):
    res = execute({"intent": "open_app", "params": {"app": alias}, "lang": "ar"})
    assert res["success"] is True
    assert expected_canonical in res["message"]


# ---------------------------------------------------------------------------
# 5. Arabic folders
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("folder_ar", ["التنزيلات", "المستندات", "سطح المكتب"])
def test_arabic_folder_resolves(folder_ar):
    res = execute({"intent": "open_folder", "params": {"folder": folder_ar}, "lang": "ar"})
    _assert_contract(res)
    assert res["success"] is True


# ---------------------------------------------------------------------------
# 6. Unknown / unsupported intent
# ---------------------------------------------------------------------------
def test_unknown_intent_en():
    res = execute({"intent": "fly_to_moon", "params": {}, "lang": "en"})
    assert res["success"] is False
    assert "unsupported" in res["message"].lower() or "unknown" in res["message"].lower()


def test_unknown_intent_ar():
    res = execute({"intent": "fly_to_moon", "params": {}, "lang": "ar"})
    assert res["success"] is False
    assert "غير مدعوم" in res["message"]


# ---------------------------------------------------------------------------
# 7. Invalid input resilience
# ---------------------------------------------------------------------------
def test_non_dict_input():
    res = execute("not a dict")
    _assert_contract(res)
    assert res["success"] is False


def test_none_input():
    res = execute(None)
    _assert_contract(res)
    assert res["success"] is False


def test_empty_dict():
    res = execute({})
    _assert_contract(res)
    assert res["success"] is False


# ---------------------------------------------------------------------------
# 8. Language in message matches lang
# ---------------------------------------------------------------------------
def test_message_is_arabic_when_lang_ar():
    res = execute({"intent": "volume_up", "params": {}, "lang": "ar"})
    # Arabic response should contain Arabic text
    assert any("\u0600" <= ch <= "\u06FF" for ch in res["message"]), \
        f"Expected Arabic text in message, got: {res['message']}"


def test_message_is_english_when_lang_en():
    res = execute({"intent": "volume_up", "params": {}, "lang": "en"})
    # English response should NOT be all-Arabic
    assert any(ch.isascii() and ch.isalpha() for ch in res["message"])


# ---------------------------------------------------------------------------
# 9. Execution time — CONTRACT.md §7: executor < 1 second
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cmd", ALL_INTENTS, ids=[c["intent"] for c in ALL_INTENTS])
def test_execution_time_under_one_second(cmd):
    t0 = time.monotonic()
    execute(cmd)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0, f"{cmd['intent']} took {elapsed:.3f}s (limit 1.0s)"


# ---------------------------------------------------------------------------
# 10. Create file default name & edge cases
# ---------------------------------------------------------------------------
def test_create_file_default_name():
    res = execute({"intent": "create_file", "params": {}, "lang": "en"})
    assert res["success"] is True
    assert "new_file.txt" in res["message"]


def test_none_params_field():
    """Missing or None params should not crash."""
    res = execute({"intent": "open_app", "params": None, "lang": "en"})
    _assert_contract(res)
    assert res["success"] is False


def test_none_lang_field():
    """Missing or None lang should default safely to English without crashing."""
    res = execute({"intent": "volume_up", "params": {}, "lang": None})
    _assert_contract(res)
    assert res["success"] is True


def test_path_traversal_backslash_blocked():
    """Backslash and absolute paths must be rejected."""
    res = execute({"intent": "create_file", "params": {"name": "..\\secret.txt"}, "lang": "en"})
    _assert_contract(res)
    assert res["success"] is False
    assert "traversal" in res["message"].lower()


def test_web_search_empty_query():
    """Empty web search query should return failure."""
    res = execute({"intent": "web_search", "params": {"query": "  "}, "lang": "en"})
    _assert_contract(res)
    assert res["success"] is False


def test_web_search_offline(monkeypatch):
    """When offline and not in dry-run, web search must notify user of offline status (CONTRACT.md §4)."""
    monkeypatch.delenv("SOUNDOS_DRY_RUN", raising=False)
    from executor import actions
    monkeypatch.setattr(actions, "check_internet_connection", lambda: False)

    res = execute({"intent": "web_search", "params": {"query": "python"}, "lang": "en"})
    _assert_contract(res)
    assert res["success"] is False
    assert "internet" in res["message"].lower()

    res_ar = execute({"intent": "web_search", "params": {"query": "python"}, "lang": "ar"})
    _assert_contract(res_ar)
    assert res_ar["success"] is False
    assert "الإنترنت" in res_ar["message"]


# ---------------------------------------------------------------------------
# 11. v2 Enhancements (Offline handling, Actions resilience)
# ---------------------------------------------------------------------------
def test_internet_check_speed():
    from executor.actions import check_internet_connection
    t0 = time.monotonic()
    online = check_internet_connection(timeout_sec=0.1)
    elapsed = time.monotonic() - t0
    assert isinstance(online, bool)
    assert elapsed < 0.25, f"Internet check too slow: {elapsed:.3f}s"


def test_web_search_offline_graceful():
    os.environ["SOUNDOS_DRY_RUN"] = "0"
    from unittest.mock import patch
    with patch("executor.actions.check_internet_connection", return_value=False):
        res = execute({"intent": "web_search", "params": {"query": "test"}, "lang": "ar"})
        assert res["success"] is False
        assert "إنترنت" in res["message"]


def test_play_media_offline_graceful():
    os.environ["SOUNDOS_DRY_RUN"] = "0"
    from unittest.mock import patch
    with patch("executor.actions.check_internet_connection", return_value=False):
        res = execute({"intent": "play_media", "params": {"query": "amr diab"}, "lang": "en"})
        assert res["success"] is False
        assert "internet" in res["message"].lower()


# ---------------------------------------------------------------------------
# 12. v3 Hardening: Timeout enforcement
# ---------------------------------------------------------------------------
def test_timeout_returns_error_message_en():
    """A slow handler must be killed and return a timeout message within ~1s."""
    from unittest.mock import patch
    import time as _time

    def slow_handler(params, lang, dry_run):
        _time.sleep(3)  # deliberate slow
        return True, "Should never reach"

    with patch.dict("executor.DISPATCH_TABLE", {"open_app": slow_handler}):
        t0 = _time.monotonic()
        res = execute({"intent": "open_app", "params": {"app": "firefox"}, "lang": "en"})
        elapsed = _time.monotonic() - t0

    _assert_contract(res)
    assert res["success"] is False
    assert "timed out" in res["message"].lower()
    assert elapsed < 1.5, f"Timeout took too long: {elapsed:.3f}s"


def test_timeout_returns_error_message_ar():
    """Arabic timeout message."""
    from unittest.mock import patch
    import time as _time

    def slow_handler(params, lang, dry_run):
        _time.sleep(3)
        return True, "Should never reach"

    with patch.dict("executor.DISPATCH_TABLE", {"open_app": slow_handler}):
        res = execute({"intent": "open_app", "params": {"app": "firefox"}, "lang": "ar"})

    _assert_contract(res)
    assert res["success"] is False
    assert "مهلة" in res["message"]


# ---------------------------------------------------------------------------
# 13. v3 Hardening: Duplicate file rejection
# ---------------------------------------------------------------------------
def test_duplicate_file_rejected(tmp_path, monkeypatch):
    """Creating a file that already exists must fail with a clear message."""
    import executor.actions as act
    monkeypatch.setattr(act, "SAFE_FILES_DIR", tmp_path)
    monkeypatch.delenv("SOUNDOS_DRY_RUN", raising=False)

    # First creation succeeds
    res1 = execute({"intent": "create_file", "params": {"name": "dup.txt"}, "lang": "en"})
    _assert_contract(res1)
    assert res1["success"] is True

    # Second creation fails (duplicate)
    res2 = execute({"intent": "create_file", "params": {"name": "dup.txt"}, "lang": "en"})
    _assert_contract(res2)
    assert res2["success"] is False
    assert "already exists" in res2["message"].lower()


def test_duplicate_file_rejected_ar(tmp_path, monkeypatch):
    """Duplicate file rejection in Arabic context."""
    import executor.actions as act
    monkeypatch.setattr(act, "SAFE_FILES_DIR", tmp_path)
    monkeypatch.delenv("SOUNDOS_DRY_RUN", raising=False)

    res1 = execute({"intent": "create_file", "params": {"name": "dup_ar.txt"}, "lang": "ar"})
    assert res1["success"] is True

    res2 = execute({"intent": "create_file", "params": {"name": "dup_ar.txt"}, "lang": "ar"})
    _assert_contract(res2)
    assert res2["success"] is False
    assert "already exists" in res2["message"].lower()


# ---------------------------------------------------------------------------
# 14. v3 Hardening: Invalid parameter types
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("intent, params, lang", [
    ("open_app",    {"app": 123},           "en"),
    ("open_app",    {"app": ["firefox"]},    "en"),
    ("open_app",    {"app": None},           "en"),
    ("web_search",  {"query": []},           "en"),
    ("web_search",  {"query": 42},           "ar"),
    ("create_file", {"name": ["x"]},         "en"),
    ("create_file", {"name": 999},           "en"),
    ("delete_file", {"name": 123},           "en"),
    ("delete_file", {"name": True},          "ar"),
    ("play_media",  {"query": 42},           "en"),
    ("open_folder", {"folder": 123},         "en"),
], ids=[
    "open_app-int", "open_app-list", "open_app-None",
    "web_search-list", "web_search-int-ar",
    "create_file-list", "create_file-int",
    "delete_file-int", "delete_file-bool-ar",
    "play_media-int",
    "open_folder-int",
])
def test_invalid_param_types_rejected(intent, params, lang):
    """Non-string params for string fields must fail without crashing."""
    res = execute({"intent": intent, "params": params, "lang": lang})
    _assert_contract(res)
    assert res["success"] is False
    assert "must be" in res["message"].lower() or "يجب" in res["message"]


def test_open_app_empty_string_rejected():
    """open_app with empty string app name must fail."""
    res = execute({"intent": "open_app", "params": {"app": "   "}, "lang": "en"})
    _assert_contract(res)
    assert res["success"] is False


def test_web_search_empty_string_rejected():
    """web_search with empty string query must fail."""
    res = execute({"intent": "web_search", "params": {"query": ""}, "lang": "en"})
    _assert_contract(res)
    assert res["success"] is False


def test_delete_file_empty_string_rejected():
    """delete_file with empty string name must fail."""
    res = execute({"intent": "delete_file", "params": {"name": "   "}, "lang": "en"})
    _assert_contract(res)
    assert res["success"] is False


# ---------------------------------------------------------------------------
# 15. v3 Hardening: Subcommand timeout (0.85s)
# ---------------------------------------------------------------------------
def test_subcommand_timeout_085():
    """_run_subcommand must use 0.85s timeout by default."""
    from executor.actions import _SUBCOMMAND_TIMEOUT
    assert _SUBCOMMAND_TIMEOUT == 0.85
