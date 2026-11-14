"""
Pytest suite for safety layer module (Owner: Antonius)
Covers: CONTRACT.md compliance, allowlist, dangerous intents, path traversal, cooldown.
"""
import time
import pytest

from safety import check, SafetyLayer


def _assert_contract(res):
    """Every safety result MUST satisfy CONTRACT.md shape."""
    assert isinstance(res, dict)
    assert "decision" in res
    assert res["decision"] in {"allow", "confirm", "block"}
    assert "message" in res
    assert isinstance(res["message"], str)


def test_safe_intents_allowed():
    safe_commands = [
        {"intent": "open_app", "params": {"app": "firefox"}, "lang": "en", "raw_text": "open firefox"},
        {"intent": "close_app", "params": {"app": "firefox"}, "lang": "en", "raw_text": "close firefox"},
        {"intent": "volume_up", "params": {}, "lang": "en", "raw_text": "volume up"},
        {"intent": "volume_down", "params": {}, "lang": "ar", "raw_text": "خفض الصوت"},
        {"intent": "mute", "params": {}, "lang": "ar", "raw_text": "اكتم الصوت"},
        {"intent": "brightness_up", "params": {}, "lang": "en", "raw_text": "brightness up"},
        {"intent": "create_file", "params": {"name": "hello.txt"}, "lang": "en", "raw_text": "create file"},
        {"intent": "open_folder", "params": {"folder": "downloads"}, "lang": "en", "raw_text": "open downloads"},
        {"intent": "web_search", "params": {"query": "weather"}, "lang": "en", "raw_text": "search weather"},
        {"intent": "play_media", "params": {"query": "music"}, "lang": "ar", "raw_text": "شغل موسيقى"},
    ]
    for cmd in safe_commands:
        res = check(cmd)
        _assert_contract(res)
        assert res["decision"] == "allow", f"Failed for {cmd['intent']}: {res.get('reason')}"
        assert res["approved"] is True


def test_dangerous_intents_require_confirmation():
    for intent in ("shutdown", "delete_file"):
        cmd = {"intent": intent, "params": {"name": "test.txt"}, "lang": "en", "raw_text": f"do {intent}"}
        res = check(cmd)
        _assert_contract(res)
        assert res["decision"] == "confirm"
        assert res["approved"] is False


def test_unknown_intent_is_blocked():
    cmd = {"intent": "unknown", "params": {}, "lang": "ar", "raw_text": "كلام مش مفهوم"}
    res = check(cmd)
    _assert_contract(res)
    assert res["decision"] == "block"
    assert "مفهمتش" in res["message"]


def test_unauthorized_intent_is_blocked():
    cmd = {"intent": "format_disk", "params": {}, "lang": "en", "raw_text": "format disk"}
    res = check(cmd)
    _assert_contract(res)
    assert res["decision"] == "block"


def test_unauthorized_app_blocked():
    cmd = {"intent": "open_app", "params": {"app": "malicious_tool"}, "lang": "en", "raw_text": "open tool"}
    res = check(cmd)
    _assert_contract(res)
    assert res["decision"] == "block"


def test_path_traversal_blocked():
    cmd = {"intent": "delete_file", "params": {"name": "../../etc/shadow"}, "lang": "en", "raw_text": "delete shadow"}
    res = check(cmd)
    _assert_contract(res)
    assert res["decision"] == "block"


def test_low_confidence_blocked():
    cmd = {"intent": "volume_up", "params": {}, "lang": "en", "raw_text": "volume up", "confidence": 0.40}
    res = check(cmd)
    _assert_contract(res)
    assert res["decision"] == "block"


def test_interactive_confirmation_yes():
    safety = SafetyLayer()
    safety.cooldown_seconds = 0.1
    cmd = {"intent": "shutdown", "params": {}, "lang": "ar", "raw_text": "اطفي الجهاز"}
    res = safety.check(cmd, listen_yes_no_fn=lambda timeout: "أيوة تمام")
    assert res["approved"] is True
    assert res["decision"] == "allow"


def test_interactive_confirmation_no():
    safety = SafetyLayer()
    safety.cooldown_seconds = 0.1
    cmd = {"intent": "shutdown", "params": {}, "lang": "ar", "raw_text": "اطفي الجهاز"}
    res = safety.check(cmd, listen_yes_no_fn=lambda timeout: "لا بلاش")
    assert res["approved"] is False
    assert res["decision"] == "block"


def test_cooldown_enforced():
    safety = SafetyLayer()
    safety.cooldown_seconds = 10.0
    cmd = {"intent": "shutdown", "params": {}, "lang": "en", "raw_text": "shut down"}
    res1 = safety.check(cmd, listen_yes_no_fn=lambda timeout: "yes")
    assert res1["approved"] is True

    # Immediate repetition should trigger cooldown
    res2 = safety.check(cmd, listen_yes_no_fn=lambda timeout: "yes")
    assert res2["approved"] is False
    assert "Cooldown active" in res2["reason"]
