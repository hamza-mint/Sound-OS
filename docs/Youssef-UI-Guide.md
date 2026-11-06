# 🎨 دليل يوسف علام — موديول الواجهة والصوت (`ui_tts`)
### Sound OS · Role 5 · UI/UX & Voice Feedback

> [!IMPORTANT]
> **مختصر ومباشر:** هذا الملف صُمم لتبدأ فوراً.  
> يبدأ بالبرومبت الجاهز للذكاء الاصطناعي، يليه شرح مركز لدور الواجهة، وكود الملفات المطلوبة منك فقط داخل مجلد `ui_tts/`.

---

## 🤖 1. البرومبت الجاهز للذكاء الاصطناعي (انسخه فوراً)

> **كيف تستخدمه؟**  
> انسخ النص التالي وضعه مباشرة في (ChatGPT / Claude / Cursor) ليولد لك ملفات موديولك بالكامل متوافقة مع العقد وبوضع العمل المستقل:

```text
You are a senior Linux and Python developer pair-programming with me on an offline voice assistant for Linux (Sound OS).
My role is Youssef Alam (Role 5 / ui_tts). I am responsible ONLY for the directory `ui_tts/`.

Context & Constraints:
- Teammates (Abram for mic/wake-word, Yassin for executor, Antonius for safety) have NOT finished their real modules yet.
- The repo has a strict interface contract (`CONTRACT.md`), working stubs, and 214 passing pytest tests.
- I must work 100% standalone inside `ui_tts/` only. Never edit any files outside `ui_tts/` (do NOT touch main.py, executor/, intent_parser/, safety/, stt/).
- CONTRACT.md Rule 7: Functions must NEVER raise exceptions. If anything fails (TTS missing, audio device busy), fail silently and gracefully. Empty text does nothing.

Please implement the following 4 files in `ui_tts/`:
1. `ui_tts/replies.json`:
   - Bilingual dictionary (Egyptian Arabic & English) for system replies covering: open_app, close_app, volume_up, volume_down, mute, brightness_up, brightness_down, create_file, open_folder, web_search, play_media, shutdown, delete_file, unknown, error, cancelled, and confirmations.
2. `ui_tts/__init__.py`:
   - `speak(text: str, lang: str) -> None`: Offline TTS using Piper (`ar_JO-kareem-medium` for Arabic, `en_US-lessac-medium` for English) piped to `aplay -r 22050 -f S16_LE -c 1`. If Piper fails, silently fall back to `espeak-ng -v <lang>`. Empty text does nothing. Never raises.
   - `notify(title: str, body: str) -> None`: Desktop notification via `notify-send`. Never raises.
   - `play_wake_sound() -> None`: Non-blocking playback of `ui_tts/assets/wake.wav` via `paplay` or `aplay`.
3. `ui_tts/coucou_bridge.py`:
   - Send JSON events via `coucou-hook --agent sound-os` (`on_wake()`, `on_heard(text)`, `on_done(success)`).
   - If Coucou is not installed, fail silently or fallback to a tiny Tkinter floating bar.
4. `ui_tts/mock_runner.py`:
   - Standalone lifecycle test script to simulate: wake sound -> on_wake -> on_heard -> speak -> notify -> on_done.

Provide the complete code for these files and the bash commands to install dependencies (`piper-tts`, `espeak-ng`) and test it in my Linux terminal.
```

---

## 💡 2. ما هو دور الـ UI بالظبط؟ (شرح بسيط ومباشر)

> **هل الـ UI نافذة برنامج تفتح عند تشغيل `main.py`؟**  
> **لا!** مشروع **Sound OS** هو مساعد صوتي (مثل Siri أو Google Assistant) يعمل كخدمة خلفية في النظام.  
> ليس له نافذة عادية تظل مفتوحة، بل يقدم **3 ردود فعل ذكية وخفيفة تظهر وتختفي تلقائياً**:

```
🎙️ تنبيه المستخدم      💬 سماع النص        ⚙️ بعد التنفيذ
      ↓                     ↓                     ↓
🔔 صوت تنبيه + شريط    📝 ظهور النص المنطوق   🔊 نطق الرد (Piper TTS)
  (on_wake)              (on_heard)        + 🔔 إشعار (notify-send)
                                           + ✅ حالة النجاح (on_done)
```

1. **الشريط العائم الجزيرة (Coucou / Mochi Island):**  
   شريط صغير أنيق يطفو في أعلى الشاشة: يظهر عند التنبيه، يعرض الكلمات التي نطقها المستخدم، ثم يتحول لعلامة نجاح ✅ أو خطأ ❌ ويختفي.
2. **الرد الصوتي (Voice TTS):**  
   نطق رد النظام في السماعات عبر محرك Piper TTS أوفلاين (مثال: *"تم فتح المتصفح"* أو *"Volume increased"*).
3. **إشعار سطح المكتب (Desktop Notification):**  
   إشعار نظام لينكس التقليدي عبر `notify-send`.

---

## ⚡ 3. وضعك الحالي: أنت مستقل 100% (بدون انتظار باقي الفريق)

- **أبرام** (المايك) و **ياسين** (المنفّذ) لم ينتهيا بعد، لكنك **غير معطّل تماماً**:
  - لا تحتاج للميكروفون لتجربة الواجهة.
  - لا تحتاج لتنفيذ أوامر لينكس الحقيقية لتجربة الصوت والإشعار.
- **كيف تتأكد إن شغلك ممتاز؟**
  1. تشغيل المحاكي المستقل: `python3 -m ui_tts.mock_runner`
  2. تشغيل الـ Pipeline التجريبي: `python3 main.py --text "افتح فايرفوكس"`

---

## 📁 4. ملفاتك الأربعة المطلوبة في `ui_tts/`

```
Sound-OS/
└── ui_tts/
    ├── replies.json       ← 1. نصوص الردود عربي وإنجليزي
    ├── __init__.py        ← 2. دوال speak() و notify() و play_wake_sound()
    ├── coucou_bridge.py   ← 3. شريط Coucou أو بديل Tkinter
    ├── mock_runner.py     ← 4. سكربت المحاكاة لتجربة كل شيء
    └── assets/wake.wav    ← 5. ملف صوت التنبيه (0.5 ثانية)
```

> ⚠️ **قاعدة ذهبية:** لا تعدل أي ملف خارج مجلد `ui_tts/`. دوالك لا ترفع استثناءات أبدًا (`Never raise`).

---

## 🛠️ 5. الكود المباشر للملفات

### أ) `ui_tts/replies.json` — قاموس الردود
```json
{
  "open_app":        { "ar": "تم فتح {app}",          "en": "{app} opened" },
  "close_app":       { "ar": "تم إغلاق {app}",         "en": "{app} closed" },
  "volume_up":       { "ar": "تم رفع الصوت",           "en": "Volume increased" },
  "volume_down":     { "ar": "تم خفض الصوت",           "en": "Volume decreased" },
  "mute":            { "ar": "تم كتم الصوت",            "en": "Muted" },
  "brightness_up":   { "ar": "تم رفع السطوع",          "en": "Brightness increased" },
  "brightness_down": { "ar": "تم خفض السطوع",          "en": "Brightness decreased" },
  "create_file":     { "ar": "تم إنشاء الملف",          "en": "File created" },
  "open_folder":     { "ar": "تم فتح المجلد",           "en": "Folder opened" },
  "web_search":      { "ar": "جاري البحث عن {query}",  "en": "Searching for {query}" },
  "play_media":      { "ar": "جاري التشغيل",            "en": "Playing" },
  "shutdown":        { "ar": "جاري إيقاف الجهاز",       "en": "Shutting down" },
  "delete_file":     { "ar": "تم حذف الملف",            "en": "File deleted" },
  "unknown":         { "ar": "لم أفهم الأمر",           "en": "Command not understood" },
  "error":           { "ar": "حدث خطأ",                 "en": "An error occurred" },
  "cancelled":       { "ar": "تم الإلغاء",              "en": "Cancelled" }
}
```

---

### ب) `ui_tts/__init__.py` — الصوت والإشعارات
```python
"""
ui_tts/__init__.py — Owner: Youssef Alam
Implements: speak(text, lang), notify(title, body), play_wake_sound()
CONTRACT.md Rule 7: Never raise exceptions.
"""
import json
import subprocess
from pathlib import Path

# تحميل الردود
_REPLIES_PATH = Path(__file__).parent / "replies.json"
try:
    with open(_REPLIES_PATH, encoding="utf-8") as f:
        REPLIES = json.load(f)
except Exception:
    REPLIES = {}

# موديلات Piper
_PIPER_MODELS = {
    "ar": "ar_JO-kareem-medium",
    "en": "en_US-lessac-medium",
}


def speak(text: str, lang: str = "ar") -> None:
    """Say `text` out loud using Piper TTS, with silent fallback to espeak-ng."""
    if not text:
        return

    # 1. محاولة استخدام Piper
    model = _PIPER_MODELS.get(lang, _PIPER_MODELS["en"])
    try:
        p1 = subprocess.Popen(
            ["piper", "--model", model, "--output_raw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        p2 = subprocess.Popen(
            ["aplay", "-r", "22050", "-f", "S16_LE", "-c", "1"],
            stdin=p1.stdout,
            stderr=subprocess.DEVNULL,
        )
        p1.stdin.write(text.encode("utf-8"))
        p1.stdin.close()
        p1.wait(timeout=8)
        p2.wait(timeout=8)
        return
    except Exception:
        pass

    # 2. البديل الجاهز دائماً: espeak-ng
    try:
        voice = "ar" if lang == "ar" else "en"
        subprocess.run(["espeak-ng", "-v", voice, text], timeout=6, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def notify(title: str, body: str) -> None:
    """Desktop notification via notify-send. Never raises."""
    try:
        subprocess.run(["notify-send", title, body], timeout=3, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def play_wake_sound() -> None:
    """Play wake sound non-blocking. Never raises."""
    try:
        wav = Path(__file__).parent / "assets" / "wake.wav"
        if wav.exists():
            subprocess.Popen(["paplay", str(wav)], stderr=subprocess.DEVNULL)
    except Exception:
        pass
```

---

### ج) `ui_tts/coucou_bridge.py` — شريط الواجهة العائم
```python
"""
ui_tts/coucou_bridge.py — Coucou visual bridge (Owner: Youssef Alam)
Sends events to Coucou island (or Tkinter fallback). Never raises.
"""
import json
import os
import shutil
import subprocess

AGENT = "sound-os"
SESSION = "soundos-1"


def _send(event: str, **fields) -> bool:
    hook = os.environ.get("COUCOU_HOOK") or shutil.which("coucou-hook")
    if not hook:
        return False
    payload = {"hook_event_name": event, "session_id": SESSION, "coucou_agent": AGENT, **fields}
    try:
        subprocess.run([hook, "--agent", AGENT], input=json.dumps(payload, ensure_ascii=False) + "\n", text=True, timeout=1, check=False)
        return True
    except Exception:
        return False


def on_wake() -> None:
    """إظهار الشريط عند سماع كلمة التنبيه."""
    _send("SessionStart")


def on_heard(text: str) -> None:
    """عرض النص المنطوق في الشريط."""
    _send("UserPromptSubmit", prompt=text)


def on_done(success: bool) -> None:
    """عرض حالة اكتمال التنفيذ أو الخطأ."""
    _send("Stop" if success else "StopFailure")
```

> **لو Coucou مش موجود على جهازك؟**  
> الكود مصمم يتجاهل الأمر بدون أي خطأ (`silent no-op`)، أو يمكنك استبداله بكود Tkinter الخفيف الموجود في نهاية هذا الملف.

---

### د) `ui_tts/mock_runner.py` — سكربت المحاكاة المستقل
```python
"""
ui_tts/mock_runner.py — Standalone Lifecycle Simulator
تشغيل واختبار دورة الواجهة كاملة بدون مايك:
    python3 -m ui_tts.mock_runner
"""
import time
from ui_tts import speak, notify, play_wake_sound
from ui_tts.coucou_bridge import on_wake, on_heard, on_done


def run_test(phrase: str, lang: str, reply: str, success: bool = True):
    print(f"🎬 محاكاة: '{phrase}' ({lang})")
    play_wake_sound()
    on_wake()
    time.sleep(1)
    on_heard(phrase)
    time.sleep(1.5)
    on_done(success)
    notify("Sound OS", reply)
    speak(reply, lang)
    print("✅ تم بنجاح!\n")


if __name__ == "__main__":
    print("🚀 بدء تجربة موديول الواجهة والصوت...\n")
    run_test("افتح المتصفح", "ar", "تم فتح المتصفح", success=True)
    time.sleep(1)
    run_test("volume up", "en", "Volume increased", success=True)
```

---

## 🧪 6. أوامر التجربة في الـ Terminal

```bash
# 1. تثبيت المتطلبات (في بيئة لينكس)
sudo apt update && sudo apt install -y espeak-ng pulseaudio-utils libnotify-bin
pip install piper-tts

# 2. تسجيل صوت تنبيه بسيط (نصف ثانية)
mkdir -p ui_tts/assets
arecord -d 1 -f S16_LE -r 22050 ui_tts/assets/wake.wav

# 3. تجربة الواجهة والصوت بمحاكي يوسف المستقل
python3 -m ui_tts.mock_runner

# 4. تجربة سريان الـ Pipeline بالكامل عبر main.py
python3 main.py --text "افتح فايرفوكس"
```

---

## 🪟 بديل Tkinter البسيط (لو Coucou غير متوفر)

لو أردت واجهة رسومية بسيطة جداً بدون Coucou، ضع هذا في `coucou_bridge.py`:

```python
import tkinter as tk

_root, _label = None, None

def _get_ui():
    global _root, _label
    if not _root:
        _root = tk.Tk()
        _root.title("Sound OS")
        _root.geometry("380x60+500+10")
        _root.attributes("-topmost", True)
        _label = tk.Label(_root, text="Sound OS", font=("Arial", 14), bg="#1a1a2e", fg="white")
        _label.pack(fill="both", expand=True)
    return _root, _label

def on_wake():
    r, l = _get_ui(); l.config(text="🎙️ استماع..."); r.update()

def on_heard(text):
    r, l = _get_ui(); l.config(text=f"💬 {text}"); r.update()

def on_done(success):
    r, l = _get_ui(); l.config(text="✅ تم" if success else "❌ خطأ"); r.update()
```
