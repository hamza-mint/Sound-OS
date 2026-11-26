"""Unit tests for intent_parser.llm_fallback validation and caching (no Ollama server needed)."""
from intent_parser import llm_fallback


def test_validate_normalizes_case_and_aliases():
    assert llm_fallback._validate({"intent": "open_app", "params": {"app": "Firefox"}}) == (
        "open_app", {"app": "firefox"}
    )
    assert llm_fallback._validate({"intent": "open_app", "params": {"app": "المتصفح"}}) == (
        "open_app", {"app": "firefox"}
    )
    assert llm_fallback._validate({"intent": "open_folder", "params": {"folder": "Downloads"}}) == (
        "open_folder", {"folder": "downloads"}
    )


def test_validate_allows_optional_empty_params_and_blocks_dangerous():
    assert llm_fallback._validate({"intent": "create_file", "params": {"name": ""}}) == ("create_file", {})
    assert llm_fallback._validate({"intent": "play_media", "params": {}}) == ("play_media", {})
    assert llm_fallback._validate({"intent": "shutdown", "params": {}}) is None
    assert llm_fallback._validate({"intent": "delete_file", "params": {"name": "a.txt"}}) is None
    assert llm_fallback._validate({"intent": "open_app", "params": {"app": "unknown_app"}}) is None


def test_ask_llm_ex_caches_responses(monkeypatch):
    llm_fallback._CACHE.clear()
    calls = 0

    def fake_ollama(prompt_text, timeout):
        nonlocal calls
        calls += 1
        return {"intent": "volume_up", "params": {}}

    monkeypatch.setattr(llm_fallback, "_call_ollama", fake_ollama)
    monkeypatch.setattr(llm_fallback, "_down_until", 0.0)

    r1 = llm_fallback.ask_llm_ex("ارفع الصوت شوية", quiet=True)
    r2 = llm_fallback.ask_llm_ex("ارفع الصوت شوية", quiet=True)
    assert r1 == ("ok", ("volume_up", {}))
    assert r2 == ("ok", ("volume_up", {}))
    assert calls == 1
