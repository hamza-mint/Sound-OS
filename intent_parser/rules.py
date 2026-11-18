"""Rule-based intent parser: Egyptian Arabic + English -> Sound OS JSON contract.

How it works:
  1. normalize()      folds Arabic spelling variants (see normalize.py).
  2. strip filler     "ممكن", "please", "can you" ...
  3. RULES run in a fixed order, first match wins. Dangerous intents are checked
     BEFORE harmless ones that share words (e.g. "اقفل الجهاز" vs "اقفل فايرفوكس").
To support a new phrasing: add the word to a list below. No regex skills needed.
NOTE: free-text params (name / query / folder) come from the normalized text,
so Arabic letters are folded (مدرسة -> مدرسه) and English is lowercase.
"""
import os
import re

from .normalize import normalize as N


# ------------------------------------------------------------------ helpers
_VOCAB = set()      # every word W() ever saw. fuzzy.py uses it to repair STT typos, so a word
                    # you add to a list below is automatically typo-tolerant too.
_VERBS = set()      # command verbs only (not fillers, not the thing being opened).
                    # fuzzy.py may repair a typo INTO these. It must not repair into
                    # shutdown/delete words: those stay exact-match only.


def W(*words):
    """Regex: any of `words` as whole words, spelling-normalized.
    Allows Egyptian imperative and dialect suffixes: افتح -> افتحي/افتحلي/افتحها."""
    norm = [N(w) for w in words]
    _VOCAB.update(norm)
    alts = sorted({re.escape(w) for w in norm}, key=len, reverse=True)
    return r"\b(?:" + "|".join(alts) + r")(?:ي|لي|ليا|لنا|ه|ها|هم)?\b"


def V(*words):
    """Same regex as W(), and the words are command verbs fuzzy.py is allowed to correct to."""
    for n in (N(w) for w in words):
        _VERBS.add(n)
        for tok in n.split():
            if len(tok) >= 3:
                _VERBS.add(tok)
    return W(*words)


def has(pattern, t):
    return re.search(pattern, t) is not None


def _alias_re(alias):
    return r"\b(?:ال)?" + re.escape(N(alias)) + r"\b"      # الكروم == كروم


def _find_alias(table, t):
    """Canonical key whose alias appears first in t (longest alias wins a tie)."""
    best = None
    for key, aliases in table.items():
        for a in aliases:
            m = re.search(_alias_re(a), t)
            if m and (best is None or (m.start(), -len(a)) < best[0]):
                best = ((m.start(), -len(a)), key)
    return best[1] if best else None


def _strip_lead(text, stop):
    """Drop leading filler tokens (also matches them with the ال prefix removed)."""
    toks = text.split()
    while toks and (toks[0] in stop or toks[0].removeprefix("ال") in stop):
        toks.pop(0)
    return " ".join(toks).strip(" .")


def _standalone(m, t):
    """True if the match is a whole word, not part of a file name like search.txt."""
    before = t[m.start() - 1:m.start()]
    after = t[m.end():m.end() + 1]
    return before in ("", " ") and after in ("", " ")


# ------------------------------------------------------------ vocabulary
APPS = {   # canonical name (what the executor receives) -> spoken aliases
    # "متصف", "مبصف", "لما تصف" = what whisper tiny/base really wrote for "المتصفح" (seen in tests)
    "firefox":    ["فايرفوكس", "فيرفوكس", "فيرفكس", "فايرفكس", "فاير فوكس", "فاير فكس", "firefox", "mozilla", "موزيلا",
                   "متصفح", "متصف", "مبصف", "لما تصف", "browser", "web browser", "براوزر", "البراوزر"],
    "chrome":     ["كروم", "chrome", "chromium", "جوجل كروم", "جوجل", "google"],
    "terminal":   ["تيرمينال", "ترمينال", "تيرمنال", "تيرمينل", "ترمنال", "ترمنل", "طرفيه", "terminal", "console", "command line"],
    "files":      ["مدير الملفات", "مدير ملفات", "ملفات", "فايلات", "file manager", "files", "thunar", "explorer"],
    "calculator": ["حاسبه", "الاله الحاسبه", "اله حاسبه", "كالكيوليتر", "كالكولاتور", "كالكوليتر", "كالكوليتور", "calculator",
                   "calc", "كلكيوليتر", "كالكو ليتر", "بنكا لكو ليتر"],
    "editor":     ["محرر النصوص", "محرر نصوص", "محرر", "نوت باد", "نوتباد", "text editor", "editor", "notepad", "gedit", "mousepad"],
    "vlc":        ["vlc", "فلك", "في ال سي", "مشغل الفيديو", "مشغل الميديا", "media player"],
    "settings":   ["اعدادات", "اعدادات النظام", "سيتنجز", "سيتنغز", "settings", "preferences"],

}
FOLDERS = {
    "home":      ["بيت", "هوم", "home", "رئيسيه"],
    "downloads": ["تحميلات", "تنزيلات", "downloads", "download"],
    "documents": ["مستندات", "مستنداتي", "وثائق", "documents", "docs"],
    "desktop":   ["سطح المكتب", "ديسكتوب", "desktop"],
    "pictures":  ["صور", "pictures", "photos", "images"],
    "music":     ["موسيقي", "موسيقا", "music"],
    "videos":    ["فيديوهات", "فيديوهاتي", "videos"],
}

NOISE = W("ممكن", "لو سمحت", "من فضلك", "يا ريت", "بالله عليك", "لو تكرمت", "عايز", "عاوز", "عايزه",
          "نفسي", "اريد", "محتاج", "يا ساوند", "يا ديف", "يا عم ديف", "ياعم ديف", "بعد اذنك", "لو سمحتلي",
          "عايزك", "عاوزك", "محتاجك", "يا ريس", "يا باشا",
          "بقي", "طيب", "طب", "يلا", "دلوقتي", "حالا", "بسرعه", "كده", "لو مش مشغول",   # Egyptian fillers
          "هل يمكنك", "هل تستطيع", "ارجوك", "رجاء", "تفضل",
          "please", "can you", "could you", "would you",
          "hey sound", "ok sound", "sound os", "hey dave", "ok dave", "dave",
          "i want you to", "i want to", "i need you to",
          "i would like to", "i'd like to", "i wanna", "kindly", "now")

OPEN_ANY = V("افتح", "فتح", "تفتح", "شغل", "تشغل", "وريني", "ودني", "وديني", "روح", "هات", "طلعلي",
             "ابدا", "ادخل علي", "اعرض", "اظهر", "open", "oven", "launch", "start", "run", "show", "bring up")
OPEN_NAV = V("افتح", "فتح", "تفتح", "وريني", "ودني", "وديني", "روح", "هات", "طلعلي", "ادخل علي", "اعرض", "اظهر",
             "open", "show", "go to", "take me to", "browse")          # no "شغل": that means play
CLOSE = V("اقفل", "قفل", "تقفل", "سكر", "تسكر", "اغلق", "تغلق", "وقف", "اخرج من", "اطفي", "طفي", "تطفي", "انهي",
          "سيب", "اطلع من", "close", "quit", "exit", "kill", "stop", "terminate")
PLAY = V("شغل", "تشغل", "اسمع", "سمعني", "تسمعني", "play", "put on", "listen to")
SEARCH = V("ابحث", "تبحث", "دور", "تدور", "سيرش", "بحث", "search", "google", "look up", "lookup")
SEND_MSG = W("ارسل", "ارسللي", "ابعت", "ابعتلي", "ابعث", "ابعثلي", "وصل", "send", "message", "text")
MAKE = W("اعمل", "اعملي", "اعمللي", "عمل", "تعمل", "انشي", "انشاء", "كريت", "اصنع", "جهز",
         "create", "make", "new", "generate")
DEL = W("امسح", "احذف", "حذف", "مسح", "شيل", "ازل", "تمسح", "تحذف", "delete", "remove", "erase", "trash")
FILE = r"\b(?:ال)?(?:ملف|فايل|file)\b"
FOLDER_WORD = W("مجلد", "فولدر", "folder", "directory")
DEVICE = W("جهاز", "الجهاز", "كمبيوتر", "الكمبيوتر", "لابتوب", "اللابتوب", "حاسوب", "الحاسوب",
           "السيستم", "سيستم", "النظام", "computer", "pc", "laptop", "system", "machine")
MEDIA = ["اغنيه", "اغاني", "اغنيات", "موسيقي", "موسيقا", "ميوزك", "فيديو", "فيديوهات", "فيلم", "افلام",
         "مسلسل", "قران", "بلايليست", "song", "songs", "music", "video", "videos", "movie", "playlist",
         "track", "tracks", "podcast"]
MEDIA_NOUN = r"\b(?:ال)?(?:" + "|".join(sorted({re.escape(N(w)) for w in MEDIA}, key=len, reverse=True)) + r")\b"   # allows الاغاني / القران

VOL_OBJ = W("الصوت", "صوت", "فوليوم", "الفوليوم", "السماعات", "السماعه", "volume", "sound", "audio")
BRI_OBJ = W("السطوع", "سطوع", "الاضاءه", "اضاءه", "الشاشه", "شاشه", "النور", "brightness", "backlight",
            "screen", "display")
UP_WORDS = ["علي", "اعلي", "ارفع", "رفع", "زود", "زيد", "زياده", "كبر", "اكتر", "اكثر", "عالي", "اعلا",
            "عليلي", "ارفعلي", "زودلي", "شد", "قوي", "كتر", "اكبر",
            "up", "raise", "increase", "louder", "higher", "more", "boost", "bump", "crank"]
DOWN_WORDS = ["وطي", "واطي", "اوطي", "اخفض", "خفض", "قلل", "نزل", "انقص", "نقص", "اقل", "خفف", "خففلي", "هدي", "هديلي", "اخفضلي",
              "down", "lower", "decrease", "reduce", "quieter", "softer", "less", "drop"]

# lead words dropped from free-text params
_COMMON = {"لي", "ليا", "for", "me", "the", "a", "an", "my", "some", "this", "that", "it", "شويه", "حاجه", "اي"}
NAME_LEAD = _COMMON | {N(w) for w in ["اسمه", "اسمها", "باسم", "اسم", "ده", "دا", "دي", "اللي", "جديد",
                                       "جديده", "فاضي", "فاضيه", "نصي", "نصيه", "named", "called", "name",
                                       "new", "empty", "text"]}
SEARCH_LEAD = _COMMON | {"عن", "علي", "في", "جوجل", "google", "انترنت", "نت", "ويب", "web", "internet",
                         "online", "for", "about", "on"}
PLAY_LEAD = _COMMON | {N(w) for w in MEDIA} | {"by", "of", "something"}


def _clean_name(rest):
    rest = re.sub(r"\s*\b(?:dot|نقطه)\b\s*", ".", rest)      # STT writes "notes dot txt"
    return _strip_lead(rest, NAME_LEAD)


# ------------------------------------------------------- volume / brightness
VOL = dict(
    obj=VOL_OBJ, up=V(*UP_WORDS), down=V(*DOWN_WORDS),
    too_high=W("عالي", "عاليه", "مرتفع", "جامد", "قوي"),
    too_low=W("واطي", "واطيه", "ضعيف", "خافت", "هادي", "هاديه"),
    stand_up=W("مش سامع", "مش سامعه") + r"|\blouder\b|\btoo (?:quiet|soft|low)\b|\bcan ?t hear\b",
    stand_down=r"\bquieter\b|\bsofter\b|\btoo (?:loud|noisy|high)\b",
)
BRI = dict(
    obj=BRI_OBJ, up=V(*UP_WORDS, "نور", "brighter"), down=V(*DOWN_WORDS, "ظلم", "عتم", "اعتم", "خفف", "dim", "dimmer"),
    too_high=W("منوره", "ساطعه", "مبهره", "عالي", "عاليه", "جامده"),
    too_low=W("ضلمه", "مضلمه", "معتمه", "ضعيفه", "خافته", "خافت"),
    stand_up=r"\bbrighter\b|\btoo (?:dark|dim)\b",
    stand_down=r"\bdimmer\b|\btoo bright\b",
)


def _adjust(t, c):
    """'up' / 'down' / None for one control (volume or brightness)."""
    if has(c["stand_up"], t):
        return "up"
    if has(c["stand_down"], t):
        return "down"
    if not has(c["obj"], t):
        return None
    # Egyptian complaints about state: "الصوت عالي" = "too loud" -> down. Not after "خلي" (make it).
    if not has(MAKE_IT, t):
        if has(c["obj"] + r"\s+(?:\S+\s+)?" + c["too_high"], t):
            return "down"
        if has(c["obj"] + r"\s+(?:\S+\s+)?" + c["too_low"], t):
            return "up"
    u, d = re.search(c["up"], t), re.search(c["down"], t)
    if u and d:
        return "up" if u.start() < d.start() else "down"       # ambiguous: first word wins
    return "up" if u else "down" if d else None


# ------------------------------------------------------------------- rules
# Each rule: text -> (intent, params) or None.
MAKE_IT = W("خلي", "يبقي", "خليه")
SHUTDOWN_NAME = W("شات داون", "shutdown", "shut down", "power off", "poweroff")
SHUTDOWN_VERB = W("اقفل", "قفل", "تقفل", "اطفي", "طفي", "تطفي", "اغلق", "سكر", "اوقف",
                  "اطفاء", "اغلاق", "ايقاف تشغيل", "turn off", "switch off", "power down")
MUTE_NAME = W("اكتم", "كتم", "تكتم", "اسكت", "mute", "silence", "من غير صوت", "بدون صوت")
MUTE_VERB = W("اقفل", "قفل", "تقفل", "سكر", "طفي", "اطفي", "وقف", "stop", "turn off", "switch off")
DANGEROUS = {"shutdown", "delete_file"}      # only an exact rule may return these, never the fuzzy pass

def r_web_search(t):
    for m in re.finditer(SEARCH, t):
        if _standalone(m, t):
            q = _strip_lead(t[m.end():], SEARCH_LEAD)
            return ("web_search", {"query": q}) if q else None
    return None


def r_shutdown(t):
    if (has(SHUTDOWN_NAME, t)
            or has(SHUTDOWN_VERB + r".*" + DEVICE, t)
            or has(r"\bturn (?:the )?(?:computer|pc|laptop|system|machine) off\b", t)):
        return ("shutdown", {})


def r_delete_file(t):
    m = re.search(DEL + r".*?" + FILE, t)
    if not m:
        return None
    name = _clean_name(t[m.end():])
    return ("delete_file", {"name": name}) if name else None     # no name -> unknown (safer)


def r_mute(t):
    if has(MUTE_NAME, t) or has(MUTE_VERB + r"\s+(?:\S+\s+)?" + VOL_OBJ, t):
        return ("mute", {})


def r_brightness(t):
    d = _adjust(t, BRI)
    return (f"brightness_{d}", {}) if d else None


def r_volume(t):
    d = _adjust(t, VOL)
    return (f"volume_{d}", {}) if d else None


def r_create_file(t):
    m = re.search(MAKE + r".*?" + FILE, t)
    if not m:
        return None
    name = _clean_name(t[m.end():])
    return ("create_file", {"name": name} if name else {})


def r_open_folder(t):
    if not has(OPEN_NAV, t):
        return None
    key = _find_alias(FOLDERS, t)
    if key:
        return ("open_folder", {"folder": key})
    m = re.search(FOLDER_WORD, t)                                # "open folder projects"
    if m:
        name = _strip_lead(t[m.end():], NAME_LEAD)
        if name:
            return ("open_folder", {"folder": name})


def r_play_media(t):
    m = re.search(PLAY, t)
    if not m:
        return None
    noun = has(MEDIA_NOUN, t)
    if _find_alias(APPS, t) and not noun:
        return None                                              # "شغل vlc" = open the app
    q = _strip_lead(t[m.end():], PLAY_LEAD)
    if not noun and not q:
        return None
    return ("play_media", {"query": q} if q else {})


def r_close_app(t):
    if has(CLOSE, t):
        app = _find_alias(APPS, t)
        if app:
            return ("close_app", {"app": app})
        # Generic close: "اقفل تطبيق", "اقفل التطبيق", "اقفل البرنامج", "close app", "close the app"
        if has(r"\b(?:تطبيق|التطبيق|البرنامج|برنامج|الابلكيشن|ابلكيشن|app|application|the app|the application|program|the program|current|this)\b", t) or t.strip() in {"اقفل", "اقفلي", "اغلق", "اغلقي", "سكر", "سكري", "طفي", "close"}:
            return ("close_app", {"app": "current"})


def r_send_message(t):
    if has(SEND_MSG, t):
        if has(r"\b(?:رساله|رسائل|مسج|message|msg)\b", t):
            return ("send_message", {})


_BARE_FILLER = {"the", "a", "an", "ya", "يا"}


def _only_entity(t, table):
    """Key when `t` is just that alias, optionally with the/a/يا.

    "firefox" and "the browser" open the app. "chrome is slow" and
    "browser history" do not: mentioning an app is not a command.
    """
    best = None
    for key, aliases in table.items():
        for a in aliases:
            m = re.search(_alias_re(a), t)
            if m and (best is None or (m.start(), -len(N(a))) < best[0]):
                best = ((m.start(), -len(N(a))), key, m)
    if not best:
        return None
    m = best[2]
    rest = f"{t[:m.start()]} {t[m.end():]}".split()
    if all(tok in _BARE_FILLER for tok in rest):
        return best[1]
    return None


def r_open_app(t):
    if has(CLOSE, t):
        return None
    app = _find_alias(APPS, t)
    if app and (has(OPEN_ANY, t) or len(t.split()) <= 3):
        return ("open_app", {"app": app})
    app = _only_entity(t, APPS)                                 # bare "firefox" / "the browser"
    if app:
        return ("open_app", {"app": app})


RULES = [r_web_search,       # strong, anchored verb; checked first so "search how to delete a file" is safe
         r_shutdown, r_delete_file,                              # dangerous before harmless
         r_mute, r_brightness, r_volume,
         r_create_file, r_open_folder, r_play_media,
         r_send_message, r_close_app, r_open_app]


# --------------------------------------------------------------- public API
def _prepare(raw):
    t = N(raw)
    t = re.sub(r"\bgoogle chrome\b", "chrome", t)                # not a web search
    t = re.sub(r"\bجوجل كروم\b", "كروم", t)
    # Common speech transliterations from English spoken in Arabic context
    t = re.sub(r"\b(?:او\s*بنكا|او\s*بن|اوبن)\b", "open", t)
    t = re.sub(r"\b(?:لكو\s*ليتر|كالكو\s*ليتر|كلكوليتر|كالكيوليتر)\b", "calculator", t)
    t = re.sub(r"\b(?:براوزر|البراوزر)\b", "browser", t)
    t = re.sub(NOISE, " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _detect_lang(raw, hint=None):
    words = re.findall(r"[A-Za-z]+|[\u0600-\u06FF]+", raw)
    if not words:
        return hint or "en"
    ar = sum(1 for w in words if "\u0600" <= w[0] <= "\u06FF")
    la = len(words) - ar
    if ar != la:
        return "ar" if ar > la else "en"
    return "ar" if "\u0600" <= words[0][0] <= "\u06FF" else "en"  # tie: first word decides


def _out(intent, params, lang, raw):
    return {"intent": intent, "params": params, "lang": lang, "raw_text": raw}


def parse(text, lang=None):
    """text -> {"intent", "params", "lang", "raw_text"}. Never raises.
    No rule matches -> a typo-tolerant second pass (fuzzy.py), then optional LLM,
    then intent "unknown" (safety layer must block it)."""
    raw = text if isinstance(text, str) else ""
    lang = _detect_lang(raw, lang)
    t = _prepare(raw)
    for rule in RULES:
        hit = rule(t)
        if hit:
            return _out(hit[0], hit[1], lang, raw)
    hit = _fuzzy_hit(t)
    if hit:
        return _out(hit[0], hit[1], lang, raw)
    if os.getenv("SOUNDOS_LLM") == "1":                          # OPTIONAL, see llm_fallback.py
        from .llm_fallback import ask_llm
        hit = ask_llm(raw)
        if hit:
            return _out(hit[0], hit[1], lang, raw)
    return _out("unknown", {}, lang, raw)


_fuzzy_warned = False


def _fuzzy_hit(t):
    """Second pass for STT spelling mistakes (المتصفح -> المبصف). Off with SOUNDOS_FUZZY=0.
    A dangerous intent is NEVER accepted from here: a misheard word must not shut the PC down."""
    if os.getenv("SOUNDOS_FUZZY", "1") == "0":
        return None
    try:
        from .fuzzy import variants
        for alt in variants(t):
            for rule in RULES:
                hit = rule(alt)
                if hit:
                    if hit[0] not in DANGEROUS:
                        return hit
                    break                                        # dangerous -> try the next variant
    except Exception as exc:                                     # parser must never raise ...
        global _fuzzy_warned
        if not _fuzzy_warned:                                    # ... but a broken fuzzy.py must not be silent
            _fuzzy_warned = True
            import sys
            print(f"[parser] fuzzy pass disabled by error: {exc!r}", file=sys.stderr)
    return None


YES = W("ايوه", "ايوا", "اه", "اكيد", "تمام", "ماشي", "موافق", "اوكي", "نعم",
        "طبعا", "نفذ", "كمل", "اوكيه", "صح", "ايوه متاكد",
        "yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "go ahead")
NO = W("لا", "لاء", "الغي", "الغاء", "بلاش", "مش عايز", "مش عاوز", "متعملش", "ماتعملش", "مش دلوقتي",
       "cancel", "no", "nope", "stop", "don't", "abort", "never mind")


def parse_yes_no(text):
    """Answer to a confirmation question: True (yes), False (no), None (unclear)."""
    t = N(text if isinstance(text, str) else "")
    y, n = has(YES, t), has(NO, t)
    return True if y and not n else False if n and not y else None
