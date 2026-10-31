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

URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.getenv("SOUNDOS_MODEL", "qwen2.5:3b")

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


def ask_llm(text, timeout=8):
    """text -> (intent, params) or None. Never raises."""
    body = json.dumps({
        "model": MODEL, "prompt": PROMPT + json.dumps(text, ensure_ascii=False),
        "stream": False, "format": "json", "options": {"temperature": 0},
    }).encode()
    try:
        req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            answer = json.loads(json.loads(r.read())["response"])
        return _validate(answer)
    except Exception:                            # Ollama off, timeout, bad JSON ...
        return None
