"""OPTIONAL - local-LLM fallback through Ollama. OFF by default.

Turn on:      export SOUNDOS_LLM=1
One-time setup:   curl -fsSL https://ollama.com/install.sh | sh ; ollama pull qwen2.5:3b
Trade-offs:   + understands phrasings the rules never saw
              - 1-5 s extra on CPU, ~2-4 GB RAM, can hallucinate
Safety:       the answer is validated, and the LLM can NEVER return a dangerous
              intent (shutdown, delete_file): those only come from explicit rules.
Uses only the standard library. Any failure -> None -> the parser says "unknown".
"""
import json
import os
import urllib.request

# OLLAMA_URL may be the base ("http://host:11434") or the full ".../api/generate" - both work.
_BASE = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
URL = _BASE if _BASE.endswith("/api/generate") else _BASE + "/api/generate"
MODEL = os.getenv("SOUNDOS_MODEL") or os.getenv("OLLAMA_MODEL") or "qwen3.5:4b"
TIMEOUT = float(os.getenv("SOUNDOS_LLM_TIMEOUT", "20"))     # 4B on CPU measured ~9 s per call
# A fuzzy (typo-repaired) hit below this similarity to what was heard gets a second opinion.
FUZZY_THRESHOLD = float(os.getenv("SOUNDOS_LLM_THRESHOLD", "0.85"))

# intent -> allowed param names. Dangerous intents are left out on purpose.
ALLOWED = {
    "open_app": {"app"}, "close_app": {"app"},
    "volume_up": set(), "volume_down": set(), "mute": set(),
    "brightness_up": set(), "brightness_down": set(),
    "create_file": {"name"}, "open_folder": {"folder"},
    "web_search": {"query"}, "play_media": {"query"},
}

PROMPT = (
    "You turn one spoken computer command (Egyptian Arabic or English) into JSON.\n"
    'Reply with JSON only: {"intent": "<name>", "params": {...}}\n'
    "Intents: open_app{app}, close_app{app}, volume_up, volume_down, mute, brightness_up, "
    "brightness_down, create_file{name}, open_folder{folder}, web_search{query}, play_media{query}.\n"
    "Apps: firefox chrome terminal files calculator editor vlc settings.\n"
    "Folders: home downloads documents desktop pictures music videos.\n"
    'If the text is none of these, reply {"intent": "unknown", "params": {}}.\n'
    'Text: "خلي الصوت اعلى شوية" -> {"intent": "volume_up", "params": {}}\n'
    'Text: "افتحلي المتصفح" -> {"intent": "open_app", "params": {"app": "firefox"}}\n'
    'Text: "dim it a bit" -> {"intent": "brightness_down", "params": {}}\n'
    'Text: "what is the capital of France" -> {"intent": "unknown", "params": {}}\n'
    "Text: "
)


def _validate(data):
    """Return (intent, params) if the LLM answer is safe and well-formed, else None."""
    from .rules import APPS                      # late import: avoids a circular import
    if not isinstance(data, dict):
        return None
    intent, params = data.get("intent"), data.get("params", {})
    if intent not in ALLOWED or not isinstance(params, dict):
        return None                              # unknown, or dangerous, or garbage
    if not set(params) <= ALLOWED[intent]:
        return None
    if any(not isinstance(v, str) or not v or len(v) > 100 for v in params.values()):
        return None
    if "app" in params and params["app"] not in APPS:
        return None
    return intent, params


def ask_llm_ex(text, timeout=None):
    """text -> ("ok", (intent, params)) | ("unknown", None) | ("error", None). Never raises.
    "error" = Ollama off / timeout / bad JSON, so the caller can keep its own answer."""
    body = json.dumps({
        "model": MODEL, "prompt": PROMPT + json.dumps(text, ensure_ascii=False),
        "stream": False, "format": "json", "think": False, "keep_alive": "30m",
        "options": {"temperature": 0},
    }).encode()
    try:
        req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as r:
            answer = json.loads(json.loads(r.read())["response"])
    except Exception:
        return "error", None
    ok = _validate(answer)
    return ("ok", ok) if ok else ("unknown", None)


def ask_llm(text, timeout=None):
    """text -> (intent, params) or None. Never raises."""
    return ask_llm_ex(text, timeout)[1]


def verify_fuzzy(raw, heard, hit, repaired):
    """Second opinion for a typo-repaired rule hit. `hit` is (intent, params).
    - repaired text is very close to what was heard (>= FUZZY_THRESHOLD): trust the rules, no LLM call
    - otherwise ask the LLM:  agrees -> hit | disagrees -> None (fail safe: "unknown")
                              LLM unavailable or says unknown -> keep the rules' hit"""
    from difflib import SequenceMatcher
    if SequenceMatcher(None, heard, repaired or heard).ratio() >= FUZZY_THRESHOLD:
        return hit
    status, answer = ask_llm_ex(raw)
    if status != "ok":
        return hit
    return hit if answer == (hit[0], hit[1]) else None
