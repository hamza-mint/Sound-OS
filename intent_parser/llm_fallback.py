"""Local-LLM fallback (Plan B) through Ollama.

ON when you run main.py (main.py sets SOUNDOS_LLM=1 and starts `ollama serve` itself if needed);
OFF everywhere else (tests, scripts) unless SOUNDOS_LLM=1.  Turn it off in main.py:  SOUNDOS_LLM=0
One-time setup:   curl -fsSL https://ollama.com/install.sh | sh ; ollama pull qwen3.5:4b
Trade-offs:   + understands phrasings the rules never saw
              - 7-15 s extra on a CPU, ~3-4 GB RAM, can hallucinate
Safety:       the answer is validated, and the LLM can NEVER return a dangerous
              intent (shutdown, delete_file): those only come from explicit rules.
Uses only the standard library. Any failure -> None -> the parser says "unknown".
"""
import atexit
from collections import OrderedDict
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
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

PROMPT_BASIC = (
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



# Few-shot examples taken from the team's own phrase list (testdata/phrases.csv) - they teach the LLM how THIS
# project reads a sentence. NEVER paste phrases from testdata/holdout.csv here: it is the honest exam.
_EXAMPLES = [
    ("الصوت واطي اوي", {"intent": "volume_up", "params": {}}),
    ("نزل الصوت", {"intent": "volume_down", "params": {}}),
    ("من غير صوت لو سمحت", {"intent": "mute", "params": {}}),
    ("الشاشه ضلمه اوي", {"intent": "brightness_up", "params": {}}),
    ("عايز افتح الحاسبه", {"intent": "open_app", "params": {"app": "calculator"}}),
    ("سكرلي الملفات", {"intent": "close_app", "params": {"app": "files"}}),
    ("اعملي ملف اسمه notes.txt", {"intent": "create_file", "params": {"name": "notes.txt"}}),
    ("روح علي الموسيقي", {"intent": "open_folder", "params": {"folder": "music"}}),
    ("دورلي علي اسعار الذهب", {"intent": "web_search", "params": {"query": "اسعار الذهب"}}),
    ("عايز اسمع ام كلثوم", {"intent": "play_media", "params": {"query": "ام كلثوم"}}),
    ("turn up the volume", {"intent": "volume_up", "params": {}}),
    ("اطفي الكمبيوتر", {"intent": "unknown", "params": {}}),
    ("الساعه كام", {"intent": "unknown", "params": {}}),
    ("i installed vlc yesterday", {"intent": "unknown", "params": {}}),
    ("the vlc update has a bug", {"intent": "unknown", "params": {}}),
]


def _build_prompt():
    """Prompt built FROM the rules: app and folder names (and their spellings) come straight from rules.py, so
    when the team adds a spelling to the rules the LLM learns it too. Kept SHORT on purpose: on a CPU every extra
    prompt token costs time (the first long version doubled the latency and made it worse)."""
    from . import rules
    apps = "\n".join(f"  {k} = {', '.join(v[:6])}" for k, v in rules.APPS.items())
    folders = "\n".join(f"  {k} = {', '.join(v[:3])}" for k, v in rules.FOLDERS.items())
    shots = "\n".join(f"Text: {json.dumps(t, ensure_ascii=False)} -> {json.dumps(a, ensure_ascii=False)}"
                      for t, a in _EXAMPLES)
    return (
        "You turn ONE spoken computer command (Arabic or English) into JSON. The text comes from speech-to-text.\n"
        'Reply with JSON only: {"intent": "<name>", "params": {...}}\n'
        "Intents: open_app{app}, close_app{app}, volume_up, volume_down, mute, brightness_up, brightness_down, "
        "create_file{name}, open_folder{folder}, web_search{query}, play_media{query}, unknown.\n"
        "Apps (KEY = spoken forms):\n" + apps + "\n"
        "Folders (KEY = spoken forms; another folder name is kept as said):\n" + folders + "\n"
        "Rules:\n"
        "- Only real COMMANDS. Talking ABOUT something is unknown: an app being slow, crashing or buggy, "
        "greetings, questions, small talk.\n"
        "- Only two complaints count as commands: the SOUND level (too low / too loud) and the SCREEN brightness "
        "(too dark / too bright).\n"
        "- close + sound = mute. close + an app = close_app. A plain 'browser' / متصفح = firefox.\n"
        "- Turning off or restarting the computer, and deleting files: always unknown.\n"
        "- App not in the list: unknown.\n"
        + shots + "\nText: "
    )


_PROMPT_CACHE = None


def _prompt():
    """The prompt for the LLM. Default: the short one (PROMPT_BASIC).
    SOUNDOS_PROMPT=rules selects the experimental rules-aware prompt built from rules.py. Measured on the 82-phrase
    holdout (qwen3.5:4b, CPU): it was NOT more accurate (78/82 vs 79/82) and about 2x slower (16 s vs 8.7 s per call),
    and the first, longer version even made 2 wrong actions. So it stays opt-in."""
    global _PROMPT_CACHE
    if os.getenv("SOUNDOS_PROMPT") != "rules":
        return PROMPT_BASIC
    if _PROMPT_CACHE is None:
        try:
            _PROMPT_CACHE = _build_prompt()
        except Exception:
            _PROMPT_CACHE = PROMPT_BASIC
    return _PROMPT_CACHE


PROMPT = PROMPT_BASIC        # kept for old scripts that import it


def _validate(data):
    """Return (intent, params) if the LLM answer is safe and well-formed, else None."""
    from .rules import APPS, FOLDERS, _find_alias  # late import: avoids a circular import
    from .normalize import normalize as norm_ar
    if not isinstance(data, dict):
        return None
    intent = str(data.get("intent", "")).strip().lower()
    raw_params = data.get("params", {})
    if raw_params is None:
        raw_params = {}
    if intent not in ALLOWED or not isinstance(raw_params, dict):
        return None                              # unknown, or dangerous, or garbage

    # Keep only allowed keys and drop empty optional values (create_file/play_media allow {})
    params = {}
    for k, v in raw_params.items():
        if k not in ALLOWED[intent]:
            return None
        if v is None:
            continue
        if not isinstance(v, str) or len(v) > 100:
            return None
        s = v.strip()
        if not s:
            if intent in ("create_file", "play_media"):
                continue
            return None
        params[k] = s

    if "app" in params:
        app_val = params["app"].lower()
        if app_val not in APPS:
            app_val = _find_alias(APPS, norm_ar(app_val)) or ""
        if app_val not in APPS:
            return None
        params["app"] = app_val
    if "folder" in params:
        f_val = params["folder"].lower()
        params["folder"] = _find_alias(FOLDERS, norm_ar(f_val)) or f_val
    return intent, params


_loaded = False              # True after the first answer: before that a call also pays the model load (~20-60 s on a CPU)
_down_until = 0.0            # after a failed call the LLM is skipped for 30 s (a dead server must not cost 20 s per sentence)
_on_thinking = None          # optional UI hook: fn(True) before a slow LLM call, fn(False) after it
_state = "off"               # off | starting | ready | thinking | down   (shown in the terminal and on the GUI)
_on_state = None             # optional hook: fn(state, detail) every time the state changes
STATE_TEXT = {"off": "OFF (rules only)", "starting": "starting...", "ready": "ready",
              "thinking": "thinking...", "down": "NOT available (rules only)"}


def set_state_callback(fn):
    global _on_state
    _on_state = fn


def _set_state(new, detail=""):
    global _state
    if new == _state and not detail:
        return
    _state = new
    try:
        if _on_state:
            _on_state(new, detail)
    except Exception:                                # a UI problem must never break the parser
        pass


def state():
    """Current LLM state: off | starting | ready | thinking | down."""
    return _state
_started = None              # the `ollama serve` process WE started (stopped again when main exits)


def set_thinking_callback(fn):
    """main.py registers a function here so the UI can show "thinking..." during the ~10 s LLM call."""
    global _on_thinking
    _on_thinking = fn


def _notify(active):
    try:
        if _on_thinking:
            _on_thinking(active)
    except Exception:                                # a UI problem must never break the parser
        pass


def _base():
    return URL[: -len("/api/generate")] if URL.endswith("/api/generate") else URL


def _tags():
    """Names of the pulled models, or None if Ollama does not answer."""
    try:
        with urllib.request.urlopen(_base() + "/api/tags", timeout=3) as r:
            return [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return None


def status():
    """(ok, message) - is Ollama reachable and is MODEL pulled? Used for a clear message at start-up."""
    names = _tags()
    if names is None:
        return False, f"Ollama is not reachable at {_base()} (start it with: ollama serve)"
    want = MODEL if ":" in MODEL else MODEL + ":latest"
    if want not in names:
        return False, f"Ollama is running but model {MODEL!r} is not pulled (run: ollama pull {MODEL})"
    return True, f"Ollama OK, model {MODEL}"


def _stop_started():
    if _started is not None and _started.poll() is None:
        _started.terminate()


def ensure_running(wait=25):
    """status(), but if Ollama is not running on THIS computer, start `ollama serve` first (and stop it at exit).
    Never pulls a model (3 GB download): a missing model is only reported."""
    global _started
    ok, msg = status()
    if ok or _tags() is not None:
        return ok, msg
    host = URL.split("//", 1)[-1].split("/")[0].rsplit(":", 1)[0]
    if host not in ("localhost", "127.0.0.1", "[::1]", "::1") or not shutil.which("ollama"):
        return ok, msg
    try:
        _started = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    start_new_session=True)
        atexit.register(_stop_started)
    except OSError:
        return ok, msg
    for _ in range(int(wait * 2)):
        time.sleep(0.5)
        if _tags() is not None:
            break
    return status()


def disable():
    """Called at start-up when Ollama/the model is not ready: the LLM is skipped for this run (rules only),
    so a dead server can never freeze a command. Start Ollama and restart main to get it back."""
    global _down_until
    _down_until = float("inf")
    _set_state("down")


def warm_up(wait=False):
    """Load the model into RAM so the first real LLM call is not slower (wait=False: in the background)."""
    if wait:
        ask_llm_ex("ارفع الصوت", quiet=True)
    else:
        threading.Thread(target=ask_llm_ex, args=("ارفع الصوت",), kwargs={"quiet": True}, daemon=True).start()


_CACHE: "OrderedDict[tuple, tuple]" = OrderedDict()
_CACHE_MAX = 128


def _cache_get(key):
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    return None


def _cache_put(key, val):
    _CACHE[key] = val
    _CACHE.move_to_end(key)
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


def _call_ollama(prompt_text: str, timeout: float) -> dict:
    body = json.dumps({
        "model": MODEL, "prompt": prompt_text,
        "stream": False, "format": "json",
        "think": False, "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": 64},
    }).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(json.loads(r.read())["response"])


def ask_llm_ex(text, timeout=None, quiet=False):
    """text -> ("ok", (intent, params)) | ("unknown", None) | ("error", None). Never raises.
    "error" = Ollama off / timeout / bad JSON, so the caller can keep its own answer."""
    global _down_until, _loaded
    if not isinstance(text, str) or not text.strip():
        return "unknown", None
    prompt_str = _prompt()
    cache_key = (MODEL, prompt_str, text.strip())
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    if time.time() < _down_until:
        return "error", None
    eff_timeout = timeout or (TIMEOUT if _loaded else max(TIMEOUT, 90))
    if not quiet:
        _notify(True)
        _set_state("thinking")
    try:
        answer = _call_ollama(prompt_str + json.dumps(text, ensure_ascii=False), eff_timeout)
        _loaded = True
    except Exception:
        _down_until = time.time() + 30
        _set_state("down", "Ollama did not answer; retrying in 30 s")
        return "error", None
    finally:
        if not quiet:
            _notify(False)
            if _state == "thinking":
                _set_state("ready")
    ok = _validate(answer)
    res = ("ok", ok) if ok else ("unknown", None)
    _cache_put(cache_key, res)
    return res


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
