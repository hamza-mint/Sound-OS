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


def test_direct_approval_enforcement_on_dangerous_intents():
    os.environ["SOUNDOS_DRY_RUN"] = "0"
    # Unapproved shutdown attempt must be rejected
    res = execute({"intent": "shutdown", "params": {}, "lang": "en"})
    assert res["success"] is False
    assert "approval required" in res["message"].lower()

    # When approved=True, it proceeds (simulated via dry_run or system_shutdown mock)
    from unittest.mock import patch
    with patch("executor.actions.system_shutdown", return_value=(True, "")):
        res_approved = execute({"intent": "shutdown", "params": {}, "lang": "en", "approved": True})
        assert res_approved["success"] is True


def test_send_message_dispatch():
    os.environ["SOUNDOS_DRY_RUN"] = "1"
    res = execute({"intent": "send_message", "params": {"recipient": "Ahmed", "message": "Salam"}, "lang": "en"})
    assert res["success"] is True
    assert "Ahmed" in res["message"]


# ---------------------------------------------------------------------------
# 12. Phase 4: New Hardening Tests (Timeout, Duplicate File, Type Validation)
# ---------------------------------------------------------------------------

def test_timeout_enforcement_mock_slow_handler(monkeypatch):
    """Mock a slow handler and verify timeout returns in <1s with user-facing error."""
    import threading
    import time

    def slow_handler(*args, **kwargs):
        time.sleep(2)  # Slower than 1s limit
        return True, "Done"

    # Patch the handler in the DISPATCH_TABLE that execute() actually uses.
    # executor.execute uses executor.DISPATCH_TABLE (not executor.__init__.DISPATCH_TABLE)
    import executor
    original_handler = executor.DISPATCH_TABLE["open_app"]
    executor.DISPATCH_TABLE["open_app"] = slow_handler

    try:
        os.environ["SOUNDOS_DRY_RUN"] = "0"
        t0 = time.monotonic()
        res = execute({"intent": "open_app", "params": {"app": "firefox"}, "lang": "en"})
        elapsed = time.monotonic() - t0

        # Should timeout and return in ~1s (much less than the 2s the handler would take)
        # Allow small margin for threading overhead
        assert elapsed < 1.1, f"Timeout enforcement took {elapsed:.3f}s (limit 1.1s)"
        assert res["success"] is False
        assert "timed out" in res["message"].lower() or "timeout" in res["message"].lower()
    finally:
        executor.DISPATCH_TABLE["open_app"] = original_handler


def test_duplicate_file_rejection():
    """Create a file, try again, verify rejection with 'already exists' message."""
    os.environ["SOUNDOS_DRY_RUN"] = "0"
    from executor import actions
    from pathlib import Path

    SAFE_FILES_DIR = Path.home() / "SoundOS_Files"
    SAFE_FILES_DIR.mkdir(parents=True, exist_ok=True)
    test_file = SAFE_FILES_DIR / "duplicate_test.txt"

    # Clean up first
    if test_file.exists():
        test_file.unlink()

    try:
        # First creation should succeed
        res1 = execute({"intent": "create_file", "params": {"name": "duplicate_test.txt"}, "lang": "en"})
        assert res1["success"] is True, f"First create failed: {res1['message']}"

        # Second creation should be rejected
        res2 = execute({"intent": "create_file", "params": {"name": "duplicate_test.txt"}, "lang": "en"})
        assert res2["success"] is False, f"Second create should fail but got: {res2['message']}"
        assert "already exists" in res2["message"].lower(), f"Expected 'already exists' in: {res2['message']}"

        # Arabic version too
        res3 = execute({"intent": "create_file", "params": {"name": "duplicate_test.txt"}, "lang": "ar"})
        assert res3["success"] is False
        assert "موجود" in res3["message"] or "already" in res3["message"].lower()
    finally:
        if test_file.exists():
            test_file.unlink()


@pytest.mark.parametrize("intent,param_name,invalid_value,description", [
    # open_app: app must be str (required)
    ("open_app", "app", 123, "int instead of str"),
    ("open_app", "app", [], "list instead of str"),
    ("open_app", "app", {}, "dict instead of str"),
    ("open_app", "app", None, "None instead of str"),
    ("open_app", "app", True, "bool instead of str"),

    # close_app: app must be str if present (optional - None is valid "not provided")
    ("close_app", "app", 123, "int instead of str"),
    ("close_app", "app", [], "list instead of str"),
    ("close_app", "app", {}, "dict instead of str"),

    # web_search: query must be str (required)
    ("web_search", "query", 123, "int instead of str"),
    ("web_search", "query", [], "list instead of str"),
    ("web_search", "query", {}, "dict instead of str"),
    ("web_search", "query", None, "None instead of str"),

    # create_file: name must be str if present (optional - None is valid "not provided")
    ("create_file", "name", 123, "int instead of str"),
    ("create_file", "name", [], "list instead of str"),
    ("create_file", "name", {}, "dict instead of str"),

    # delete_file: name must be str (required)
    ("delete_file", "name", 123, "int instead of str"),
    ("delete_file", "name", [], "list instead of str"),
    ("delete_file", "name", {}, "dict instead of str"),
    ("delete_file", "name", None, "None instead of str"),

    # open_folder: folder must be str if present (optional - None is valid "not provided")
    ("open_folder", "folder", 123, "int instead of str"),
    ("open_folder", "folder", [], "list instead of str"),
    ("open_folder", "folder", {}, "dict instead of str"),

    # play_media: query must be str if present (optional - None is valid "not provided")
    ("play_media", "query", 123, "int instead of str"),
    ("play_media", "query", [], "list instead of str"),
    ("play_media", "query", {}, "dict instead of str"),

    # send_message: recipient and message must be str if present
    ("send_message", "recipient", 123, "int instead of str"),
    ("send_message", "recipient", [], "list instead of str"),
    ("send_message", "message", 123, "int instead of str"),
    ("send_message", "message", [], "list instead of str"),
])
def test_invalid_param_types(intent, param_name, invalid_value, description):
    """Test that each intent rejects wrong parameter types with proper error messages."""
    params = {param_name: invalid_value}
    res = execute({"intent": intent, "params": params, "lang": "en"})
    assert res["success"] is False, f"{intent}.{param_name}={description} should fail but got success"
    assert "invalid" in res["message"].lower() or "must be" in res["message"].lower() or "type" in res["message"].lower(), \
        f"Expected validation error for {intent}.{param_name}={description}, got: {res['message']}"


@pytest.mark.parametrize("intent,lang", [
    ("open_app", "en"),
    ("open_app", "ar"),
    ("close_app", "en"),
    ("close_app", "ar"),
    ("web_search", "en"),
    ("web_search", "ar"),
    ("create_file", "en"),
    ("create_file", "ar"),
    ("delete_file", "en"),
    ("delete_file", "ar"),
    ("open_folder", "en"),
    ("open_folder", "ar"),
    ("play_media", "en"),
    ("play_media", "ar"),
    ("send_message", "en"),
    ("send_message", "ar"),
])
def test_validation_error_messages_localized(intent, lang):
    """Test that validation errors are properly localized for each intent."""
    # Use invalid type to trigger validation
    params = {"app": 123} if intent in ("open_app", "close_app") else \
             {"query": 123} if intent in ("web_search", "play_media") else \
             {"name": 123} if intent in ("create_file", "delete_file") else \
             {"folder": 123} if intent == "open_folder" else \
             {"recipient": 123}

    res = execute({"intent": intent, "params": params, "lang": lang})
    assert res["success"] is False

    if lang == "ar":
        # Should contain Arabic text
        assert any("؀" <= ch <= "ۿ" for ch in res["message"]), \
            f"Expected Arabic in error message for {intent}, got: {res['message']}"
    else:
        # Should contain English text
        assert any(ch.isascii() and ch.isalpha() for ch in res["message"]), \
            f"Expected English in error message for {intent}, got: {res['message']}"


def test_validation_edge_cases():
    """Test edge cases: empty strings, None values, path traversal attempts."""
    os.environ["SOUNDOS_DRY_RUN"] = "0"

    # Empty string for required string fields
    res = execute({"intent": "open_app", "params": {"app": ""}, "lang": "en"})
    assert res["success"] is False
    assert "empty" in res["message"].lower() or "required" in res["message"].lower() or "invalid" in res["message"].lower()

    res = execute({"intent": "web_search", "params": {"query": "  "}, "lang": "en"})
    assert res["success"] is False

    res = execute({"intent": "delete_file", "params": {"name": ""}, "lang": "en"})
    assert res["success"] is False

    # Path traversal in create_file
    res = execute({"intent": "create_file", "params": {"name": "../../etc/passwd"}, "lang": "en"})
    assert res["success"] is False
    assert "traversal" in res["message"].lower() or "not permitted" in res["message"].lower()

    # Path traversal in delete_file
    res = execute({"intent": "delete_file", "params": {"name": "..\\windows\\system32"}, "lang": "en"})
    assert res["success"] is False
    assert "traversal" in res["message"].lower() or "not permitted" in res["message"].lower()

    # Valid Arabic empty/whitespace
    res = execute({"intent": "open_app", "params": {"app": "   "}, "lang": "ar"})
    assert res["success"] is False


def test_no_params_field_handling():
    """Test that missing params field is handled gracefully."""
    res = execute({"intent": "open_app", "lang": "en"})  # No params key at all
    _assert_contract(res)
    assert res["success"] is False

    res = execute({"intent": "volume_up", "lang": "en"})  # No params key for param-less intent
    _assert_contract(res)
    assert res["success"] is True


def test_subcommand_timeout_budget():
    """Verify that subcommand timeout budget (0.85s) is respected in multi-step operations."""
    from executor import actions
    import time

    # The _run_subcommand default timeout should be 0.85s
    import inspect
    sig = inspect.signature(actions._run_subcommand)
    assert sig.parameters["timeout_sec"].default == 0.85, \
        f"_run_subcommand timeout default should be 0.85s, got {sig.parameters['timeout_sec'].default}"

    # search_web and play_media_content should accept budget_sec parameter
    sig_search = inspect.signature(actions.search_web)
    assert "budget_sec" in sig_search.parameters
    assert sig_search.parameters["budget_sec"].default == 0.85

    sig_play = inspect.signature(actions.play_media_content)
    assert "budget_sec" in sig_play.parameters
    assert sig_play.parameters["budget_sec"].default == 0.85
