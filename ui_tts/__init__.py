"""Sound OS - Dave's UI and voice. Public functions never raise (CONTRACT Rule 7)."""

import collections
import difflib
import os
import re
import subprocess
import threading
import time

def _background_warmup():
    """Load Piper in-memory in the background and warm up common responses."""
    try:
        from . import dave_voice
        from .dave_character import GREETING
        from .dave_desktop import CLICK_LINES
        model = dave_voice.find_voice("en_US-lessac-medium")
        if model:
            dave_voice.get_piper_voice(model)
        phrases = (GREETING,) + CLICK_LINES + getattr(dave_voice, "COMMON_PHRASES", ())
        for p in phrases:
            dave_voice.warm(p, "en")
    except Exception:
        pass

try:
    threading.Thread(target=_background_warmup, daemon=True).start()
except Exception:
    pass

# What Dave said lately. The microphone hears the speakers, so without this his own "Yes?" /
# "I did not understand" came back as if the user had said it (seen in a real session log).
_RECENT = collections.deque(maxlen=8)          # (normalized words, time.monotonic())
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


_AR_TO_EN = [
    (r"\[تجربة\]|\[DRY-RUN\]", ""),
    (r"✅|❌", ""),
    # Negative / Failure patterns
    (r"\bتعذر إغلاق التطبيق الحالي.*|\bفشل إغلاق التطبيق الحالي.*", "Could not close active window"),
    (r"\bتعذر إغلاق\b|\bفشل إغلاق\b", "Could not close"),
    (r"\bتعذر فتح\b|\bفشل فتح\b", "Could not open"),
    (r"\bلم يتم العثور على نافذة أو تطبيق مفتوح\b", "no running window found"),
    # Success patterns
    (r"\bمفتوح بالفعل\b", "is already open"),
    (r"\bتم إظهار تطبيق\b|\bتم إظهار\b", "Focused"),
    (r"\bتم فتح تطبيق\b|\bتم فتح\b|\bفتح تطبيق\b", "Opened"),
    (r"\bتم إغلاق التطبيق الحالي\b|\bإغلاق التطبيق الحالي\b", "Closed current window"),
    (r"\bتم إغلاق النافذة الحالية\b|\bإغلاق النافذة الحالية\b", "Closed current window"),
    (r"\bتم إغلاق تطبيق\b|\bتم إغلاق\b|\bتم قفل\b|\bإغلاق تطبيق\b", "Closed"),
    (r"\bتم رفع الصوت\b|\bرفع الصوت\b", "Volume increased"),
    (r"\bتم خفض الصوت\b|\bتم تقليل الصوت\b|\bخفض الصوت\b", "Volume decreased"),
    (r"\bتم كتم الصوت\b|\bكتم الصوت\b", "Sound muted"),
    (r"\bتم رفع السطوع\b|\bتم زيادة السطوع\b|\bرفع السطوع\b", "Brightness increased"),
    (r"\bتم خفض السطوع\b|\bتم تقليل السطوع\b|\bخفض السطوع\b", "Brightness decreased"),
    (r"\bتم إنشاء الملف\b|\bإنشاء الملف\b", "File created"),
    (r"\bتم حذف الملف\b|\bحذف الملف\b", "File deleted"),
    (r"\bجاري البحث عن\b|\bبحث عن\b", "Searching for"),
    (r"\bجاري تشغيل الوسائط\b|\bتشغيل الوسائط\b", "Playing media"),
    (r"\bتم الإلغاء\b|\bتم الالغاء\b", "Cancelled"),
    (r"\bهل تريد إيقاف تشغيل الكمبيوتر\?.*", "Shut down computer? Say yes or no."),
    (r"\bأمر محظور\b|\bمحظور لدواعي الأمان\b", "Command blocked for safety."),
    (r"\bمفهمتش\b|\bلم أفهم\b", "Sorry, I did not understand that"),
    (r"\bفشل\b", "Failed"),
    (r"\bتم\b", "Done"),
    # App & entity names
    (r"\bالمتصفح\b", "browser"),
    (r"\bالتطبيق الحالي\b|\bالنافذة الحالية\b", "current window"),
    (r"\bالتطبيق\b|\bالبرنامج\b", "application"),
    (r"\bالحاسبة\b|\bالاله الحاسبه\b|\bالآلة الحاسبة\b", "calculator"),
    (r"\bالطرفية\b|\bالترمينال\b", "terminal"),
    (r"\bالمحرر\b", "editor"),
    (r"\bالإعدادات\b|\bالاعدادات\b|\bالضبط\b", "settings"),
    (r"\bالتحميلات\b|\bالتنزيلات\b", "downloads"),
    (r"\bالمستندات\b", "documents"),
    (r"\bسطح المكتب\b", "desktop"),
    (r"\bالموسيقى\b|\bالميوزك\b", "music"),
    (r"\s+و\s+", " and "),
]


def _to_english(text: str) -> str:
    """Translate Sound OS Arabic phrases into clean English for voice playback."""
    res = text
    for pat, rep in _AR_TO_EN:
        res = re.sub(pat, rep, res)
    return res.strip()


def notify(title: str, body: str) -> None:
    """Show a desktop notification via notify-send. Never raises."""
    try:
        subprocess.run(
            ["notify-send", str(title), str(body)],
            check=False,
            timeout=3,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def speak(text: str, lang: str = "en") -> None:
    """Dave says `text` out loud, and in his speech bubble. Returns at once; the speech
    plays in the background with near-zero latency. Never raises.
    """
    if not text:
        return
    try:
        print(f"[ui_tts.speak:{lang}] {text}", flush=True)
    except Exception:
        pass
    try:
        from . import dave_voice
        target_text = str(text).strip()
        voice_lang = (lang or "en").lower()

        # If Arabic response phrase, translate so Piper can speak it out loud
        if voice_lang == "ar" or re.search(r"[\u0600-\u06FF]", target_text):
            english_equiv = _to_english(target_text)
            if re.search(r"[\u0600-\u06FF]", english_equiv):
                # Fallback to simple acknowledgment if any Arabic characters remain
                if "Opened" in english_equiv or "Closed" in english_equiv or "increased" in english_equiv or "decreased" in english_equiv or "muted" in english_equiv:
                    english_equiv = "Command executed."
                else:
                    english_equiv = "Done."
            target_text = english_equiv
            voice_lang = "en"

        if dave_voice.speak(target_text, voice_lang):
            _RECENT.append((_norm_words(target_text), time.monotonic()))     # what is REALLY played
            return
    except Exception:
        pass


def _norm_words(text):
    """Lower-case words without punctuation / tashkeel, Arabic letters folded (أ إ آ -> ا ...)."""
    t = str(text).lower()
    t = re.sub(r"[\u064B-\u0652\u0640]", "", t)
    t = t.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))
    return _WORD.findall(t)


def wait_until_silent(timeout: float = 8.0, tail: float = 0.12) -> None:
    """Block until Dave has finished speaking (+ `tail` s for the room echo to die), so the
    microphone never records his own voice. Never raises, never waits more than `timeout`."""
    try:
        from . import dave_voice
        time.sleep(0.05)                       # let a speak() that was just queued start
        t0 = time.monotonic()
        while dave_voice.is_speaking() and time.monotonic() - t0 < timeout:
            time.sleep(0.05)
        time.sleep(tail)
    except Exception:
        pass


def strip_own_speech(text: str, window: float = 10.0) -> str:
    """Remove Dave's own recent words from what the microphone heard.
    "Yes? Open files." -> "Open files."    "I did not understand." -> ""   Never raises."""
    try:
        pairs = [(w, n) for w, n in ((t, _norm_words(t)) for t in str(text).split()) if n]
        now = time.monotonic()
        for spoken, ts in reversed(_RECENT):
            if not spoken or now - ts > window or not pairs:
                continue
            heard = [x for _, n in pairs for x in n]
            if heard[:len(spoken)] == spoken:                       # his words at the start
                k = 0
                for i, (_, n) in enumerate(pairs):
                    k += len(n)
                    if k >= len(spoken):
                        pairs = pairs[i + 1:]
                        break
            heard = [x for _, n in pairs for x in n]
            if heard and difflib.SequenceMatcher(None, heard, spoken).ratio() >= 0.8:
                pairs = []                                           # the whole thing is his echo
        return " ".join(w for w, _ in pairs)
    except Exception:
        return text


def play_wake_ack() -> None:
    """Silenced: Dave UI and voice handle wake feedback directly."""
    pass


def play_done_sound() -> None:
    """Silenced: Dave UI and voice handle completion feedback directly."""
    pass


def play_wake_sound() -> None:
    """Silenced: Dave UI and voice handle wake feedback directly."""
    pass


# Export Dave desktop & bridge API
try:
    from .dave_desktop import (
        start,
        stop,
        on_wake,
        on_heard,
        on_done,
        say,
        hush,
        set_level,
        set_mouth,
    )
except Exception:
    pass

__all__ = [
    "notify",
    "speak",
    "play_wake_ack",
    "play_done_sound",
    "play_wake_sound",
    "start",
    "stop",
    "on_wake",
    "on_heard",
    "on_done",
    "say",
    "hush",
    "set_level",
    "set_mouth",
]
