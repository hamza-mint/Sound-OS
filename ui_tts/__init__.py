"""Sound OS - GUI package (notifications + audio feedback). Public functions never raise."""

import os
from pathlib import Path
import re
import subprocess


_AR_TO_EN = [
    (r"\bتم فتح\b", "Opened"),
    (r"\bتم إغلاق\b|\bتم قفل\b", "Closed"),
    (r"\bتم رفع الصوت\b", "Volume increased"),
    (r"\bتم خفض الصوت\b|\bتم تقليل الصوت\b", "Volume decreased"),
    (r"\bتم كتم الصوت\b", "Sound muted"),
    (r"\bتم رفع السطوع\b|\bتم زيادة السطوع\b", "Brightness increased"),
    (r"\bتم خفض السطوع\b|\bتم تقليل السطوع\b", "Brightness decreased"),
    (r"\bتم إنشاء الملف\b", "File created"),
    (r"\bتم حذف الملف\b", "File deleted"),
    (r"\bجاري البحث عن\b|\bبحث عن\b", "Searching for"),
    (r"\bجاري تشغيل الوسائط\b|\bتشغيل الوسائط\b", "Playing media"),
    (r"\bتم الإلغاء\b|\bتم الالغاء\b", "Cancelled"),
    (r"\bهل تريد إيقاف تشغيل الكمبيوتر\?.*", "Shut down computer? Say yes or no."),
    (r"\bأمر محظور\b|\bمحظور لدواعي الأمان\b", "Command blocked for safety."),
    (r"\bفشل\b", "Failed"),
    (r"\bتم\b", "Done"),
    (r"\s+و\s+", " and "),
]


def _to_english(text: str) -> str:
    """Translate known Sound OS Arabic response phrases into clean English."""
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
    """Say text out loud using fast English by default (or configured lang) via espeak-ng. Never raises."""
    if not text:
        return
    try:
        target_lang = os.environ.get("SOUNDOS_TTS_LANG", "en").lower().strip()
        speed = os.environ.get("SOUNDOS_TTS_SPEED", "240").strip()

        spoken_text = str(text)
        if target_lang == "en":
            spoken_text = _to_english(spoken_text)
            voice = os.environ.get("SOUNDOS_TTS_VOICE", "en-us")
        else:
            voice = "ar" if target_lang == "ar" else "en-us"

        print(f"[ui_tts.speak:{target_lang}] {spoken_text}")
        subprocess.run(
            ["espeak-ng", "-s", speed, "-v", voice, spoken_text],
            check=False,
            timeout=4,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def play_wake_ack() -> None:
    """Silenced: TTS speaks wake responses directly without playing static wav files."""
    pass


def play_done_sound() -> None:
    """Silenced: TTS speaks completion results directly without playing static wav files."""
    pass


def play_wake_sound() -> None:
    """Silenced: TTS handles speech feedback."""
    pass


# Export Dave voice UI bridge functions
try:
    from .dave_bridge import on_wake, on_heard, on_done, start, set_level
except Exception:
    pass


