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
    "downloads": ["تحميلات", "تنزيلات", "داونلودز", "داونلود", "downloads", "download", "down loads"],
    "documents": ["مستندات", "مستنداتي", "وثائق", "دوكيومنتس", "دوكيومنت", "documents", "document", "docs"],
    "desktop":   ["سطح المكتب", "ديسكتوب", "desktop"],
    "pictures":  ["صور", "pictures", "photos", "images"],
    "music":     ["موسيقي", "موسيقا", "music"],
    "videos":    ["فيديوهات", "فيديوهاتي", "videos"],
}

NOISE = W("ممكن", "لو سمحت", "من فضلك", "يا ريت", "بالله عليك", "لو تكرمت", "عايز", "عاوز", "عايزه",
          "نفسي", "اريد", "محتاج", "يا ساوند", "يا ديف", "يا عم ديف", "ياعم ديف", "بعد اذنك", "لو سمحتلي",
          "عايزك", "عاوزك", "محتاجك", "يا ريس", "يا باشا",
          "بقي", "طيب", "طب", "يلا", "دلوقتي", "حالا", "بسرعه", "كده", "خلاص", "كفايه", "لو مش مشغول",   # Egyptian fillers
          "هل يمكنك", "هل تستطيع", "ارجوك", "رجاء", "تفضل",
          "please", "can you", "could you", "would you",
          "hey sound", "ok sound", "sound os", "hey dave", "ok dave", "dave",
          "i want you to", "i want to", "i need you to",
          "i would like to", "i'd like to", "i wanna", "kindly", "now")

OPEN_ANY = V("افتح", "فتح", "تفتح", "شغل", "تشغل", "وريني", "ودني", "وديني", "روح", "هات", "طلعلي",
             "ابدا", "ادخل علي", "اعرض", "اظهر", "open", "oven", "launch", "start", "run", "show", "bring up")
OPEN_NAV = V("افتح", "فتح", "تفتح", "وريني", "ودني", "وديني", "روح", "هات", "طلعلي", "ادخل علي", "اعرض", "اظهر",
             "open", "opening", "show", "go to", "take me to", "browse")          # no "شغل": that means play
CLOSE = V("اقفل", "قفل", "تقفل", "سكر", "تسكر", "اغلق", "تغلق", "وقف", "اخرج من", "اطفي", "طفي", "تطفي", "انهي",
          "اغلاق", "انهاء", "اقفال",          # noun forms: "اغلاق المتصفح" used to OPEN the browser
          "سيب", "اطلع من", "close", "quit", "exit", "kill", "stop", "terminate")
PLAY = V("شغل", "تشغل", "اسمع", "سمعني", "تسمعني", "play", "put on", "listen to")
SEARCH = V("ابحث", "تبحث", "دور", "تدور", "سيرش", "بحث", "search", "google", "look up", "lookup")
SEND_MSG = W("ارسل", "ارسللي", "ابعت", "ابعتلي", "ابعث", "ابعثلي", "وصل", "send", "message", "text")
MAKE = W("اعمل", "اعملي", "اعمللي", "عمل", "تعمل", "انشي", "انشاء", "كريت", "كريد", "كرييت",
         "قريد", "قريت", "قريط", "اصنع", "جهز", "create", "make", "new", "generate")
DEL = W("امسح", "احذف", "حذف", "مسح", "شيل", "ازل", "تمسح", "تحذف", "delete", "remove", "erase", "trash")
FILE = r"\b(?:ال)?(?:ملف|ملفات|فايل|file|files|document|مستند|وثيقه|sheet|شيت|spreadsheet|script|سكريبت)\b"

# Known file extensions for detecting bare filenames like "create hamza.txt"
_KNOWN_EXT = frozenset({
    "txt", "py", "md", "csv", "json", "xml", "html", "htm", "css", "js", "ts",
    "sh", "yml", "yaml", "toml", "cfg", "ini", "log", "sql", "rb", "rs", "go",
    "java", "c", "cpp", "h", "hpp", "docx", "xlsx", "pptx", "pdf", "doc",
    "xls", "ppt", "rtf",
})
_HAS_EXT = re.compile(r"\.(" + "|".join(sorted(_KNOWN_EXT, key=len, reverse=True)) + r")$", re.I)

# "create excel sheet data" / "create python file main" / "create txt file notes" → name.ext
_TYPE_EXT = {
    "excel": ".xlsx", "اكسل": ".xlsx", "spreadsheet": ".xlsx", "sheet": ".xlsx", "شيت": ".xlsx",
    "word": ".docx", "وورد": ".docx",
    "python": ".py", "بايثون": ".py",
    "text": ".txt", "txt": ".txt", "تيكست": ".txt", "تكست": ".txt", "نصي": ".txt", "نص": ".txt",
    "markdown": ".md", "md": ".md", "ماركداون": ".md",
    "powerpoint": ".pptx", "بوربوينت": ".pptx", "presentation": ".pptx",
    "json": ".json", "جيسون": ".json",
    "csv": ".csv",
    "html": ".html",
    "css": ".css",
    "javascript": ".js", "js": ".js",
    "bash": ".sh", "shell": ".sh",
    "yaml": ".yaml", "yml": ".yml",
    "pdf": ".pdf",
}
# Filler words stripped AFTER a type keyword is consumed
_TYPE_FILLER = {N(w) for w in [
    "file", "files", "ملف", "ملفات", "فايل", "document", "مستند", "وثيقه", "sheet", "شيت",
    "script", "سكريبت", "spreadsheet", "new", "جديد", "جديده", "empty", "فاضي", "فاضيه",
    "a", "an", "the", "named", "called", "اسمه", "اسمها", "باسم", "في",
]}
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
    m_make = re.search(MAKE, t)
    after = t[m_make.end():].strip() if m_make else t.strip()
    after = re.sub(
        r"\s*\b(?:dot|نقطه)\s+(" + "|".join(sorted(_KNOWN_EXT, key=len, reverse=True)) + r")\b",
        r".\1",
        after,
    )

    # Path 1: type keyword (excel/word/python/text/markdown…) → default extension
    for kw, ext in sorted(_TYPE_EXT.items(), key=lambda x: len(x[0]), reverse=True):
        pat_kw = r"(?<!\.)\b" + re.escape(kw) + r"\b"
        if re.search(pat_kw, after):
            if not m_make and not re.search(r"\b(?:sheet|شيت|file|ملف|فايل|document|مستند|جدول)\b", after):
                continue
            rest = re.sub(pat_kw, " ", after, count=1)
            rest = re.sub(r"\bفي\s+ال(?=\w)", " ", rest)     # Whisper hears "file <name>" as "في ال<name>"
            for fw in _TYPE_FILLER:
                rest = re.sub(r"\b" + re.escape(fw) + r"\b", " ", rest)
            name = _clean_name(re.sub(r"\s+", " ", rest).strip())
            if name and not _HAS_EXT.search(name):
                name += ext
            elif not name:
                name = "new_file" + ext
            return ("create_file", {"name": name})

    if not m_make:
        return None

    # Path 2: MAKE + FILE/document word + optional name
    m = re.search(FILE, after)
    if m:
        rest = after[m.end():]
        # Reattach spoken "dot <ext>" / "نقطه <ext>" / " .<ext>" (e.g. "create file dot py" -> "file.py")
        rest_dot = re.sub(r"^\s*(?:dot|نقطه|\.)\s*", ".", rest)
        # "file" consumed from "file.txt" → reconstruct the full filename
        if rest_dot.startswith("."):
            tok = rest_dot.split()[0]                       # ".txt" or ".py …"
            ext_part = tok[1:].lower()
            ext_part = {"pi": "py", "pie": "py", "dxt": "txt"}.get(ext_part, ext_part)
            if ext_part in _KNOWN_EXT:
                matched = after[m.start():m.end()]
                return ("create_file", {"name": matched + "." + ext_part})
        name = _clean_name(rest)
        if name and name.lower() in _KNOWN_EXT and m.start() == 0:
            matched = after[m.start():m.end()]
            return ("create_file", {"name": matched + "." + name.lower()})
        return ("create_file", {"name": name} if name else {})

    # Path 3: bare filename with known extension (e.g., "create hamza.txt")
    name = _clean_name(after)
    if name and _HAS_EXT.search(name):
        return ("create_file", {"name": name})

    return None


def r_open_folder(t):
    if not has(OPEN_NAV, t):
        # a folder name said ALONE ("downloads", "the documents", "المستندات") opens it, like a bare app name does.
        # Exact match only: "play music" must stay play_media, not "open the music folder".
        for key, names in FOLDERS.items():
            if key != "home" and any(re.fullmatch(r"(?:the |my |ال)?" + re.escape(N(a)), t) for a in names):
                return ("open_folder", {"folder": key})
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


# "close <this>": a noun that means the current program/window, or a pointing word (ده / it / اللي شغال).
# Pointing words count ONLY when nothing else is said: "اقفل ده" yes, "اقفل الباب ده" (a real door) no.
CURRENT_NOUN = (r"\b(?:تطبيق|التطبيق|البرنامج|برنامج|الابلكيشن|ابلكيشن|النافذه|نافذه|الويندو|ويندو|"
                r"الصفحه|صفحه|app|application|the app|the application|program|the program|current|this)\b"
                r"|(?<!\bthe )\bwindow\b")                      # "close window" yes, "close the window" (a real one) no
_CLOSE_VERB = r"(?:اقفل|اقفلي|قفل|سكر|سكري|اغلق|اغلقي|انهي|طفي|close|quit|exit|kill|terminate)(?:لي|ليا|لنا|ه|ها)?"
_POINTING = (r"(?:ده|دا|دي|ديه|هذا|هذه|الحالي|الحاليه|الشغال|المفتوح|المفتوحه|"
             r"(?:اللي|الي) (?:شغال|قدامي|فاتح|مفتوح|معايا)|it|that|this one|that one|this)")


def r_close_app(t):
    if not has(CLOSE, t):
        return None
    # Explicit close-app patterns: "اقفل المتصفح", "close browser", "قفل الفايرفوكس", etc.
    # Match close verb + app name (with optional "ال" prefix)
    explicit_close = re.search(
        _CLOSE_VERB + r"\s+(?:ال)?\s*(" + "|".join(sorted(_flatten_app_aliases(), key=len, reverse=True)) + r")\b",
        t
    )
    if explicit_close:
        # Find which app was matched
        matched = explicit_close.group(1)
        for key, aliases in APPS.items():
            if any(re.fullmatch(_alias_re(a), matched) for a in aliases):
                return ("close_app", {"app": key})
    # Generic app alias anywhere after close verb
    app = _find_alias(APPS, t)
    if app:
        return ("close_app", {"app": app})
    # "close this/that/current window" etc.
    if has(CURRENT_NOUN, t) or re.fullmatch(_CLOSE_VERB + r"(?:\s+" + _POINTING + r")?", t.strip()):
        return ("close_app", {"app": "current"})


def _flatten_app_aliases():
    """All app aliases as a flat list for regex."""
    out = []
    for aliases in APPS.values():
        out.extend(aliases)
    return out


def r_send_message(t):
    if not (has(SEND_MSG, t) and has(r"\b(?:رساله|رسائل|مسج|message|msg)\b", t)):
        return None

    params = {}
    # English extraction: "send message to <recipient> saying <body text>"
    m_en = re.search(r"\b(?:to)\s+([a-z0-9_-]+)(?:\s+(?:saying|with text|that)\s+(.+))?$", t, re.IGNORECASE)
    if m_en:
        recipient = m_en.group(1).strip()
        body = (m_en.group(2) or "").strip()
        if recipient:
            params["recipient"] = recipient
        if body:
            params["message"] = body
    else:
        m_en_body_only = re.search(r"\b(?:saying|with text)\s+(.+)$", t, re.IGNORECASE)
        if m_en_body_only:
            params["message"] = m_en_body_only.group(1).strip()

    # Arabic extraction: "ابعت رساله ل/الي <recipient> بتقول/نصها <body text>"
    if not params:
        m_ar = re.search(r"\b(?:ل|الي|لي)\s+([^\s]+)(?:\s+(?:بتقول|نصها|فيها|محتواها|ان|انو|انه)\s+(.+))?$", t)
        if m_ar:
            recipient = m_ar.group(1).strip()
            body = (m_ar.group(2) or "").strip()
            if recipient and recipient not in ("بتقول", "نصها", "فيها", "محتواها"):
                params["recipient"] = recipient
            if body:
                params["message"] = body
        else:
            # Prefixed lam e.g. "لاحمد"
            m_ar_prefix = re.search(r"\bل([^\s]{3,})(?:\s+(?:بتقول|نصها|فيها|محتواها|ان|انو|انه)\s+(.+))?$", t)
            if m_ar_prefix:
                cand = m_ar_prefix.group(1).strip()
                if cand not in ("ازم", "كن", "كل", "حد", "احد"):
                    params["recipient"] = cand
                    body = (m_ar_prefix.group(2) or "").strip()
                    if body:
                        params["message"] = body

        if "message" not in params:
            m_ar_body = re.search(r"\b(?:بتقول|نصها|فيها|محتواها)\s+(.+)$", t)
            if m_ar_body:
                params["message"] = m_ar_body.group(1).strip()

    return ("send_message", params)


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

    # Acoustic Whisper mishearings: "dot txt" -> ".dxt", "dot py" -> ".pi" / ".pie"
    t = re.sub(r"\s*\b(?:dot|\.)\s*(?:dxt|txt)\b", ".txt", t)
    t = re.sub(r"\.(?:dxt|d\s*xt)\b", ".txt", t)
    t = re.sub(r"(?:\s*\b(?:dot|نقطه)\s*|\s*\.\s*)(?:pi|pie)\b", ".py", t)
    # Spoken English "create python file" misheard by Whisper in Arabic/English
    t = re.sub(r"\b(?:bison|by\s*some|pyson|pysan)\s*files?\b", "python file", t)
    t = re.sub(r"\b(?:bison|by\s*some|pyson|pysan)\b", "python", t)
    t = re.sub(r"\b(?:بيسون|بايسون|بيشن|بيثون)\b", "python", t)
    t = re.sub(r"\b(?:فائل|فايل)\b", "file", t)
    t = re.sub(
        r"\b(?:قريه|تريد)\s+(?=(?:python|file|ملف|ملفات|جيسون|وورد|ورد|اكسل|تيكست|تكست|json|word|excel|text)\b)",
        "create ",
        t,
    )
    # Egyptian Arabic spoken mishearings for excel/sheet commands
    t = re.sub(r"\b(?:ام\s*اللي|املي|ملي|امل)\b", "اعملي", t)
    t = re.sub(r"\b(?:الشيط|شيط|شيث|شد)\b", "شيت", t)
    t = re.sub(r"\b(?:اكسال|اكسيل|إكسيل|إكسال)\b", "اكسل", t)

    # NOTE: We previously had a _repair_whisper_close_open_mishearing() function here
    # that tried to convert "افتح المتصفح" -> "اقفل المتصفح" assuming Whisper mishears
    # "اقفل" as "افتح". However, test data shows "افتح المتصفح" (clean spelling) is a
    # LEGITIMATE open command (user said "open browser" and Whisper got it right).
    # The fuzzy pass already handles typos like "المبصف" -> "المتصفح".
    # Removing the mishearing repair to avoid false positives on legitimate open commands.

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


# A NEGATED command must never run: "متفتحش الكروم" (don't open chrome) used to OPEN chrome.
# Egyptian ما/م + ت... + ش,  "لا تفتح", "بلاش", "مش عايز ...", English don't / do not / never.
NEGATED = re.compile(r"\bما ?ت\w+ش\b|\bمت\w+ش\b|\bلا ?ت\w+\b|\bبلاش\b|\bمش (?:عايز|عاوز|محتاج)\b|"
                     r"\b(?:don ?t|do not|never|no need to)\b")          # N() turns don't into "don t"


def parse(text, lang=None):
    """text -> {"intent", "params", "lang", "raw_text"}. Never raises.
    No rule matches -> a typo-tolerant second pass (fuzzy.py), then optional LLM,
    then intent "unknown" (safety layer must block it)."""
    raw = text if isinstance(text, str) else ""
    lang = _detect_lang(raw, lang)
    if NEGATED.search(N(raw)):
        return _out("unknown", {}, lang, raw)
    t = _prepare(raw)
    for rule in RULES:
        hit = rule(t)
        if hit:
            return _out(hit[0], hit[1], lang, raw)
    hit = _fuzzy_hit(t)
    if hit:
        return _out(hit[0], hit[1], lang, raw)
    hit = _first_clause_hit(raw)
    if hit:
        return _out(hit[0], hit[1], lang, raw)
    if os.getenv("SOUNDOS_LLM") == "1":                          # OPTIONAL, see llm_fallback.py
        from .llm_fallback import ask_llm
        hit = ask_llm(raw)
        if hit:
            return _out(hit[0], hit[1], lang, raw)
    return _out("unknown", {}, lang, raw)


_fuzzy_warned = False
_CLAUSE_SPLIT = re.compile(r"[\u060c,.\u061f?!;\u061b]+")


def _first_clause_hit(raw):
    """Whisper often says the real command and then keeps going with junk ("اقفل، ابح عاماج." / "افتح المتصفح، افضح،").
    When the whole sentence is unknown, the FIRST clause alone is tried. Never for a dangerous intent."""
    clauses = [c.strip() for c in _CLAUSE_SPLIT.split(raw) if c.strip()]
    if len(clauses) < 2:
        return None
    first = parse(clauses[0])
    if first["intent"] == "unknown" or first["intent"] in DANGEROUS:
        return None
    return first["intent"], first["params"]


def _fuzzy_hit(t):
    """Second pass for STT spelling mistakes (المتصفح -> المبصف). Off with SOUNDOS_FUZZY=0.
    A dangerous intent is NEVER accepted from here: a misheard word must not shut the PC down."""
    if os.getenv("SOUNDOS_FUZZY", "1") == "0":
        return None
    try:
        from .fuzzy import variants, repair_open_verb
        for alt in variants(t):
            for rule in RULES:
                hit = rule(alt)
                if hit:
                    if hit[0] not in DANGEROUS:
                        return hit
                    break                                        # dangerous -> try the next variant
        # "hoping down loads" / "oben documents": the English verb "open" came out as gibberish. Only OPENING
        # something may be guessed this way (never close / shutdown / send ...).
        fixed = repair_open_verb(t)
        if fixed:
            for alt in [fixed] + variants(fixed):
                for rule in RULES:
                    hit = rule(alt)
                    if hit:
                        if hit[0] in ("open_app", "open_folder"):
                            return hit
                        break
    except Exception as exc:                                     # parser must never raise ...
        global _fuzzy_warned
        if not _fuzzy_warned:                                    # ... but a broken fuzzy.py must not be silent
            _fuzzy_warned = True
            import sys
            print(f"[parser] fuzzy pass disabled by error: {exc!r}", file=sys.stderr)
    return None


YES = W("ايوه", "ايوا", "اه", "اكيد", "تمام", "ماشي", "موافق", "اوكي", "نعم",
        "طبعا", "نفذ", "كمل", "اوكيه", "صح", "ايوه متاكد",
        "عيوه", "عيوا", "ياس", "يس", "yas", "yass", "yus",          # real STT output for "ايوه / yes": 'عيوة، ياس'
        "yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "go ahead")
NO = W("لا", "لاء", "الغي", "الغاء", "بلاش", "مش عايز", "مش عاوز", "متعملش", "ماتعملش", "مش دلوقتي",
       "cancel", "no", "nope", "stop", "don't", "abort", "never mind")


MAX_ANSWER_WORDS = 4      # "yes", "ايوه اكيد", "yes go ahead". A long transcript is noise or leaked prompt, not an answer


def parse_yes_no(text):
    """Answer to a confirmation question: True (yes), False (no), None (unclear).
    Guards the shutdown/delete confirmation: only a SHORT answer counts, so a long garbled
    transcript that happens to contain "صح" or "ok" can never confirm a dangerous action."""
    t = N(text if isinstance(text, str) else "")
    if len(t.split()) > MAX_ANSWER_WORDS:
        return None
    y, n = has(YES, t), has(NO, t)
    return True if y and not n else False if n and not y else None
