"""Is the heard verb (افتح = open / اقفل = close) trustworthy?  Pure functions, no model, no microphone.

Why: Whisper copies the first verb of its prompt when the audio is unclear, so "اقفل المتصفح" came out as
"افتح المتصفح" even with a close-first prompt. A decode WITHOUT any prompt is garbled ("ايه فرمت صفح") but honest:
it only contains what the audio sounds like. Real recordings (base model, the user's voice), prompt-free text:

    clearly said افتح  ->  'إفتهم صفح', 'إبتهم الثفر'    (the "ت" of افتح is there)   -> similar to "افتح المتصفح"
    said اقفل           ->  'ايه فرمتصف', 'ايه فرمت صفح'   (no "ت" after "اف")         -> equally far from both

So if the prompt-free text gives no POSITIVE evidence for the heard verb, we doubt it and the caller asks.
n = 7 real clips: it separated them correctly. Tune EVIDENCE with more recordings (SOUNDOS_SAVE_AUDIO).
"""
import difflib
import re

from .normalize import normalize as N

OPEN_VERB, CLOSE_VERB = "افتح", "اقفل"
EVIDENCE = 0.05          # similarity advantage needed to trust the heard verb

# canonical Arabic noun for each app key (what the user says after the verb)
APP_NOUN = {
    "firefox": "المتصفح", "chrome": "الكروم", "terminal": "الترمينال", "calculator": "الحاسبه",
    "files": "الملفات", "editor": "محرر النصوص", "settings": "الاعدادات", "vlc": "مشغل الفيديو",
}

# letters Whisper confuses by sound (compare only, never rewrite)
_PHON = str.maketrans({"ص": "س", "ث": "س", "ذ": "ز", "ظ": "ز", "ض": "د", "ط": "ت", "ق": "ك", "ه": "", "ح": "ه", "ع": "ا", "غ": "خ"})


def _sim(a: str, b: str) -> float:
    a, b = N(a).replace(" ", ""), N(b).replace(" ", "")
    plain = difflib.SequenceMatcher(None, a, b).ratio()
    folded = difflib.SequenceMatcher(None, a.translate(_PHON), b.translate(_PHON)).ratio()
    return max(plain, folded)


def open_evidence(probe_text: str, app: str) -> float:
    """> 0: the prompt-free text sounds more like "افتح <app>" than "اقفل <app>". < 0: the opposite. ~0: neither."""
    noun = APP_NOUN.get(app)
    if not noun or not probe_text:
        return 0.0
    base_ev = _sim(probe_text, f"{OPEN_VERB} {noun}") - _sim(probe_text, f"{CLOSE_VERB} {noun}")
    norm = N(probe_text)
    is_close_marker = bool(re.match(r"^(ايه|اي\s+|.*?\bمن\b)", norm))
    is_open_marker = bool(re.match(r"^(يفر|ايفر|افر|افت|ابت)", norm))
    if is_open_marker and not is_close_marker:
        return max(base_ev, 0.09)
    return base_ev


def verb_doubt(heard_intent: str, app: str, probe_text: str) -> bool:
    """True when the heard open/close verb is not backed by the prompt-free decode (-> ask the user)."""
    if app not in APP_NOUN or heard_intent not in ("open_app", "close_app"):
        return False
    ev = open_evidence(probe_text, app)
    if heard_intent == "open_app":
        return ev < EVIDENCE                  # no evidence for "open": it may have been "close"
    return ev > EVIDENCE                      # heard "close" but the audio looks like "open"


def command_text(intent: str, app: str) -> str:
    """Clean Arabic command for the chosen action, e.g. ('close_app', 'firefox') -> 'اقفل المتصفح'."""
    return f"{CLOSE_VERB if intent == 'close_app' else OPEN_VERB} {APP_NOUN.get(app, app)}"
