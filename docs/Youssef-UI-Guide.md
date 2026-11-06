# 🎨 دليل يوسف علام — دور `ui_tts`
### Sound OS · Role 5 · UI/UX & Voice Feedback

> **لك وحدك.** الملف ده بيشرح دورك بالكامل خطوة بخطوة.
> مش محتاج تقرأ أي ملف تاني غير `CONTRACT.md` اللي في أصل الـ repo.

---

## أولاً — دورك في الصورة الكبيرة

```
🎙️  ميكروفون  →  🔔 Wake Word  →  🗣️ STT  →  🧠 Parser  →  🛡️ Safety  →  ⚙️ Executor
                                                                                    ↓
                                                             🔊 ui_tts  ←──────────┘
                                                           (أنت هنا)
```

الـ pipeline بيجيلك في **نهايته.** بعد ما الـ executor ينفّذ الأمر، `main.py` بيناديك بدالتين:

| الدالة | متى تُستدعى | مثال |
|---|---|---|
| `speak(text, lang)` | بعد كل أمر — ناجح أو فاشل | `speak("تم فتح المتصفح", "ar")` |
| `notify(title, body)` | نفس الوقت — إشعار سطح المكتب | `notify("Sound OS", "تم فتح المتصفح")` |

> **قاعدة ذهبية:** دورك مبيوقّفش المشروع أبدًا.
> لو حاجة عندك اتعطّلت (Piper, Coucou, notify-send) — اطبع خطأ وكمّل.

---

## 🚧 ثانياً — ما هي العوائق الحالية في غياب باقي الأدوار؟ وكيف تعمل بدونهم؟

> [!NOTE]
> **الوضع الفعلي للريبو الآن:**  
> موديول **محمود** (STT) وموديول **كيرلس** (Intent Parser) جاهزان ومدموجان في `main` بنجاح كامل.  
> لكن زملائك: **أبرام** (Audio/Wake Word) و **أنتونيوس** (Safety) و **ياسين** (Executor) لم ينتهوا بعد من تسليم عملهم.

### ❓ العوائق الثلاثة لو انتظرتهم:
1. **عائق الميكروفون وكلمة التنبيه (غياب موديول أبرام):**  
   لن تستطيع تجربة فتح الواجهة تلقائياً بسماع صوتك في المايك أو بكلمة التنبيه الحقيقية.
2. **عائق غياب المنفّذ الفعلي للأوامر (غياب موديول ياسين):**  
   لن تصلك رسائل ديناميكية ناتجة عن تشغيل برامج فعلية (مثل فتح نافذة فايرفوكس بالفعل)، والـ `message` التي تصل حالياً هي الـ Stub الثابتة (`"تم."`).
3. **عائق غياب ربط أحداث الـ UI في `main.py`:**  
   ملف `main.py` حالياً يستدعي `speak()` و `notify()` فقط في نهاية الأمر، ولا يستدعي `on_wake()` أو `on_heard()` بعد لأن كيرلس ينتظر أن تنهي ملف `coucou_bridge.py`.

---

### 🛡️ كيف تعمل الآن باستقلالية تامة 100%؟

معمارية المشروع مصممة بنظام **Stubs & Loose Coupling**، مما يعني أنك **لست معطلاً على الإطلاق!**  
كل ما عليك هو العمل داخل مجلدك `ui_tts/` فقط على 4 أجزاء مستقلة:

```
ui_tts/
├── __init__.py        ← إعداد speak() بـ Piper + espeak-ng و notify() و play_wake_sound()
├── replies.json       ← جدول الردود لكل الأوامر الـ 13 (عربي وإنجليزي)
├── coucou_bridge.py   ← جسر Coucou أو نافذة Tkinter البديلة
└── mock_runner.py     ← سكربت محاكاة تختبر بيه دورك كامل من أوله لآخره بدون مايك
```

**طريقة الاختبار بدون انتظار أحد:**
- **اختبار نطق الردود والإشعارات:** شغّل أمر الـ Pipeline بنص تجريبي عبر:
  ```bash
  python main.py --text "افتح فايرفوكس"
  ```
- **اختبار دورة الواجهة كاملة:** شغّل سكربت المحاكاة المباشر `mock_runner.py` (مشروح في الخطوة 5 أدناه).

---

## ثالثاً — مجلدك في الـ Repo

```
Sound-OS/
└── ui_tts/
    ├── __init__.py        ← ملفك الرئيسي (الـ stub موجود، أنت بتبني فوقه)
    ├── coucou_bridge.py   ← الجسر مع Coucou (تعمله في الخطوة 3)
    ├── replies.json       ← ردود النظام بالعربي والإنجليزي (تعمله في الخطوة 2)
    └── assets/
        └── wake.wav       ← صوت التنشيط (تسجّله في الخطوة 4)
```

> ⚠️ **لا تلمس** أي مجلد تاني — `intent_parser/`, `executor/`, `main.py` إلخ.
> لو محتاج تغيير في العقد، تكلّم كيرلس (دور 1) أولاً.

---

## ثالثاً — العقد اللي لازم تلتزم بيه (`CONTRACT.md`)

الملف المرجعي هو `CONTRACT.md` في أصل الـ repo.
الجزء الخاص بيك (القاعدة 7):

```python
# ui_tts/__init__.py — الـ stub الحالي موجود، أنت بتستبدل الجوّه بس

def speak(text: str, lang: str) -> None:
    """Say `text` out loud in "ar" or "en". Empty text = say nothing. Never raise."""
    ...

def notify(title: str, body: str) -> None:
    """Desktop notification. Never raise."""
    ...
```

**قواعد صارمة:**
- الدالتين **لا تعملان `raise`** تحت أي ظرف.
- `speak("")` = تتجاهل (متشغّلش TTS على نص فاضي).
- `lang` هيكون دايماً `"ar"` أو `"en"`.

---

## الخطوات العملية

---

### 🔵 الخطوة 1 — جهّز الـ replies.json

ابدأ بملف النصوص قبل أي كود.
الهدف: كل الردود في مكان واحد يقدر أي حد في الفريق يعدّله.

**أنشئ الملف:** `ui_tts/replies.json`

```json
{
  "_comment": "All system replies. {app}, {query}, {name} are placeholders filled at runtime.",

  "open_app":         { "ar": "تم فتح {app}",           "en": "{app} opened" },
  "close_app":        { "ar": "تم إغلاق {app}",          "en": "{app} closed" },
  "volume_up":        { "ar": "تم رفع الصوت",            "en": "Volume increased" },
  "volume_down":      { "ar": "تم خفض الصوت",            "en": "Volume decreased" },
  "mute":             { "ar": "تم كتم الصوت",             "en": "Muted" },
  "brightness_up":    { "ar": "تم رفع السطوع",           "en": "Brightness increased" },
  "brightness_down":  { "ar": "تم خفض السطوع",           "en": "Brightness decreased" },
  "create_file":      { "ar": "تم إنشاء الملف",           "en": "File created" },
  "open_folder":      { "ar": "تم فتح المجلد",            "en": "Folder opened" },
  "web_search":       { "ar": "جاري البحث عن {query}",   "en": "Searching for {query}" },
  "play_media":       { "ar": "جاري التشغيل",             "en": "Playing" },
  "shutdown":         { "ar": "جاري إيقاف الجهاز",        "en": "Shutting down" },
  "delete_file":      { "ar": "تم حذف الملف",             "en": "File deleted" },

  "unknown":          { "ar": "لم أفهم الأمر",            "en": "Command not understood" },
  "error":            { "ar": "حدث خطأ",                  "en": "An error occurred" },
  "cancelled":        { "ar": "تم الإلغاء",               "en": "Cancelled" },
  "confirm_shutdown": { "ar": "هل أنت متأكد من إيقاف الجهاز؟",  "en": "Are you sure you want to shut down?" },
  "confirm_delete":   { "ar": "هل أنت متأكد من حذف الملف؟",     "en": "Are you sure you want to delete this file?" }
}
```

---

### 🟢 الخطوة 2 — اكتب `speak()` بـ Piper + espeak-ng

**Piper** هو الموديل الصوتي الأساسي (offline). **espeak-ng** هو الـ fallback لو Piper ما شتغلش.

#### أ) نزّل Piper على الـ VM

```bash
# داخل الـ VM (Xubuntu)
pip install piper-tts
```

اختبره مباشرة من الـ terminal:
```bash
echo "تم فتح المتصفح" | piper --model ar_JO-kareem-medium --output_raw | aplay -r 22050 -f S16_LE -c 1
```

شغّل بالإنجليزي:
```bash
echo "Browser opened" | piper --model en_US-lessac-medium --output_raw | aplay -r 22050 -f S16_LE -c 1
```

> 🧪 لو `ar_JO-kareem-medium` مش موجود، جرّب `ar_JO-kareem-low`.
> لو Piper ما اشتغلش خالص، اكتب لكيرلس — هنقرّر نعتمد على espeak-ng بالكامل.

---

#### ب) اكتب `speak()` في `ui_tts/__init__.py`

```python
"""
ui_tts/__init__.py — Owner: Youssef Alam
Implements: speak(text, lang) and notify(title, body)
See CONTRACT.md Rule 7.
"""
import json
import subprocess
from pathlib import Path

# ── Load replies ──────────────────────────────────────────────────────────────
_REPLIES_PATH = Path(__file__).parent / "replies.json"
try:
    with open(_REPLIES_PATH, encoding="utf-8") as f:
        REPLIES = json.load(f)
except FileNotFoundError:
    REPLIES = {}

# ── Piper model paths ─────────────────────────────────────────────────────────
_PIPER_MODELS = {
    "ar": "ar_JO-kareem-medium",   # Arabic
    "en": "en_US-lessac-medium",   # English
}


def _speak_piper(text: str, lang: str) -> bool:
    """Try Piper TTS. Returns True on success, False on any failure."""
    model = _PIPER_MODELS.get(lang, _PIPER_MODELS["en"])
    try:
        piper = subprocess.Popen(
            ["piper", "--model", model, "--output_raw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        aplay = subprocess.Popen(
            ["aplay", "-r", "22050", "-f", "S16_LE", "-c", "1"],
            stdin=piper.stdout,
            stderr=subprocess.DEVNULL,
        )
        piper.stdin.write(text.encode("utf-8"))
        piper.stdin.close()
        piper.wait(timeout=10)
        aplay.wait(timeout=10)
        return True
    except Exception:
        return False


def _speak_espeak(text: str, lang: str) -> None:
    """Fallback: espeak-ng (always installed, lower quality)."""
    voice = "ar" if lang == "ar" else "en"
    try:
        subprocess.run(
            ["espeak-ng", "-v", voice, text],
            timeout=10,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass   # Never raise


def speak(text: str, lang: str) -> None:
    """Say `text` out loud. Tries Piper first, falls back to espeak-ng. Never raises."""
    if not text:
        return
    if not _speak_piper(text, lang):
        _speak_espeak(text, lang)


def notify(title: str, body: str) -> None:
    """Desktop notification via notify-send (Xfce/Ubuntu). Never raises."""
    try:
        subprocess.run(
            ["notify-send", title, body],
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
```

**اختبر من الـ terminal:**
```bash
cd /path/to/Sound-OS
python3 -c "from ui_tts import speak, notify; speak('تم فتح المتصفح', 'ar'); notify('Sound OS', 'Test')"
```

---

### 🟡 الخطوة 3 — اعمل `coucou_bridge.py` (الواجهة البصرية)

**Coucou** هو تطبيق لينكس بيعرض شريط صغير في أعلى الشاشة.
مشروعنا بيبعتله رسائل صغيرة — هو اللي بيعرضها.

```
Sound OS  ──بيبعت رسالة──▶  Coucou  ──بيعرض──▶  شريط في الشاشة
```

#### أ) نزّل Coucou على الـ VM

```bash
cd ~/Downloads
wget https://github.com/Louis-CFM/coucou/releases/download/linux-v0.5.1/Coucou-Linux-0.5.1-amd64.deb
sudo apt install ./Coucou-Linux-0.5.1-amd64.deb
```

> لو فشل، جرّب الـ AppImage:
> ```bash
> wget https://github.com/Louis-CFM/coucou/releases/download/linux-latest/Coucou-Linux-x86_64.AppImage
> chmod +x Coucou-Linux-x86_64.AppImage
> ./Coucou-Linux-x86_64.AppImage
> ```

#### ب) شغّل Coucou وجرّب يدوياً

1. افتح Coucou من قائمة البرامج.
2. المفروض تشوف شريط صغير في **أعلى الشاشة**.
3. دوّر على ملف `coucou-hook`:

```bash
find ~ /opt /usr -iname "coucou-hook*" 2>/dev/null
```

4. اكتب المسار اللي ظهر، وجرّب ابعت رسالة يدوياً:

```bash
echo '{"hook_event_name":"UserPromptSubmit","session_id":"t1","prompt":"افتح المتصفح","coucou_agent":"sound-os"}' \
  | /المسار/اللي/لقيته/coucou-hook --agent sound-os
```

✅ ظهر pill باسم `sound-os` وفيه النص → كمّل.
❌ ما ظهرش → ابعت screenshot لكيرلس وانتقل للخطة البديلة (آخر الملف).

#### ج) اكتب `ui_tts/coucou_bridge.py`

```python
"""
ui_tts/coucou_bridge.py — Coucou visual bridge (Owner: Youssef Alam)

Sends three events to the Coucou island:
  on_wake()         → show the pill  (SessionStart)
  on_heard(text)    → show the text  (UserPromptSubmit)
  on_done(success)  → show result    (Stop / StopFailure)

If Coucou is not running or coucou-hook is not found → silent no-op.
"""
import json
import os
import shutil
import subprocess

AGENT   = "sound-os"    # must match ^[a-z0-9-]{1,24}$
SESSION = "soundos-1"


def _find_hook() -> str | None:
    """Look for coucou-hook: first COUCOU_HOOK env var, then PATH."""
    path = os.environ.get("COUCOU_HOOK")
    if path and os.path.exists(path):
        return path
    return shutil.which("coucou-hook")


def _send(event: str, **fields) -> bool:
    hook = _find_hook()
    if not hook:
        return False
    payload = {"hook_event_name": event, "session_id": SESSION,
                "coucou_agent": AGENT, **fields}
    try:
        subprocess.run(
            [hook, "--agent", AGENT],
            input=json.dumps(payload, ensure_ascii=False) + "\n",
            text=True, timeout=1, check=False,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def on_wake() -> None:
    """Call when wake word is detected → show the pill."""
    _send("SessionStart")


def on_heard(text: str) -> None:
    """Call after STT → show the recognized text in the ticker."""
    _send("UserPromptSubmit", prompt=text)


def on_done(success: bool) -> None:
    """Call after executor → show 'done' or 'error' state."""
    _send("Stop" if success else "StopFailure")


# ── Quick test (no microphone needed) ────────────────────────────────────────
if __name__ == "__main__":
    import time
    print("Testing Coucou bridge...")
    on_wake();                   time.sleep(2)
    on_heard("افتح المتصفح");   time.sleep(2)
    on_done(True)
    print("Done. Check the Coucou island.")
```

**اختبر:**
```bash
cd /path/to/Sound-OS
export COUCOU_HOOK=/المسار/اللي/لقيته/coucou-hook
python3 -m ui_tts.coucou_bridge
```

المفروض تشوف: **pill يظهر → النص → حالة "خلّص"**

---

### 🟠 الخطوة 4 — سجّل صوت التنشيط

صوت Coucou حقوقه محفوظة — هنسجّل صوتنا بأنفسنا.

```bash
# داخل الـ VM — سجّل نص ثانية واحدة
mkdir -p ui_tts/assets
arecord -d 1 -f S16_LE -r 22050 ui_tts/assets/wake.wav
```

أو استخدم ملف صوتي قصير مجاني الرخصة (`.wav`).

**اختبره:**
```bash
paplay ui_tts/assets/wake.wav
```

ما سمعتش؟ افتح `pavucontrol` وتأكد إن الـ Audio Output مش مكتوم.

**كود تشغيل الصوت في `ui_tts/__init__.py`** — أضف الدالة دي:

```python
def play_wake_sound() -> None:
    """Play the wake word sound (non-blocking). Never raises."""
    try:
        wav = Path(__file__).parent / "assets" / "wake.wav"
        subprocess.Popen(["paplay", str(wav)], stderr=subprocess.DEVNULL)
    except Exception:
        pass
```

---

---

### 🟣 الخطوة 5 — اكتب سكربت المحاكاة المستقل `ui_tts/mock_runner.py`

بما أن باقي الفريق (أبرام، ياسين، أنتونيوس) لسه ما خلصوش، السكربت ده هو **سلاحك السري**!  
بيحاكي دورة حياة الأمر كاملة بالترتيب وبدون ما تحتاج مايك أو برامج حقيقية:

**أنشئ الملف:** `ui_tts/mock_runner.py`

```python
"""
ui_tts/mock_runner.py — Standalone Lifecycle Simulator (Owner: Youssef Alam)
اختبار دورة الواجهة كاملة بشكل مستقل دون انتظار الميكروفون أو الـ Executor:
    python3 -m ui_tts.mock_runner
"""
import time
from pathlib import Path
from ui_tts import speak, notify, play_wake_sound
from ui_tts.coucou_bridge import on_wake, on_heard, on_done


def simulate_pipeline(phrase: str, lang: str, response_text: str, success: bool = True):
    print("=" * 60)
    print(f"🎬 محاكاة أمر صوتي: '{phrase}' (اللغة: {lang})")
    print("=" * 60)

    # 1. التنبيه الصوتي والواجهة
    print("1️⃣ [Wake] تشغيل صوت التنبيه وإظهار الواجهة...")
    play_wake_sound()
    on_wake()
    time.sleep(1.2)

    # 2. عرض النص المنطوق
    print(f"2️⃣ [STT] عرض النص في الشريط: '{phrase}'...")
    on_heard(phrase)
    time.sleep(1.5)

    # 3. إظهار النتيجة في الواجهة
    print(f"3️⃣ [Result] تحديث حالة الواجهة: {'✅ نجاح' if success else '❌ خطأ'}...")
    on_done(success)
    time.sleep(0.5)

    # 4. إشعار سطح المكتب ونطق الرد
    print(f"4️⃣ [Feedback] إرسال الإشعار ونطق الرد: '{response_text}'...")
    notify("Sound OS", response_text)
    speak(response_text, lang)

    print("✨ اكتملت المحاكاة بنجاح!\n")


if __name__ == "__main__":
    print("🚀 بدء تجربة المحاكاة المستقلة لموديول الواجهة والصوت...\n")
    # تجربة أمر عربي ناجح
    simulate_pipeline("افتح المتصفح", "ar", "تم فتح المتصفح", success=True)
    time.sleep(2)

    # تجربة أمر رفع الصوت بالإنجليزي
    simulate_pipeline("volume up", "en", "Volume increased", success=True)
    time.sleep(2)

    # تجربة حالة خطأ
    simulate_pipeline("شغل حاجة غريبة", "ar", "لم أفهم الأمر", success=False)
```

**شغّل وجرّب بنفسك:**
```bash
python3 -m ui_tts.mock_runner
```
المفروض تسمع صوت التنبيه → الشريط يظهر فيه النص → تسمع الرد الصوتي بالعربي والإنجليزي → يظهر الإشعار!

---

### 🔴 الخطوة 6 — قل لكيرلس إنك جهزت

بعد ما تخلص الخطوات وتتأكد إن `mock_runner` شغال 100%، كيرلس هيضيف السطور دي في `main.py`:

```python
# main.py — هذا الكود لكيرلس، مش بتاعك
# موجود في main.py بالفعل — بس بتعرف إزاي بيناديك

from ui_tts import speak, notify            # دالتاك الرئيسيتان
from ui_tts.coucou_bridge import on_wake, on_heard, on_done  # الجسر البصري

# بعد wake word:
play_wake_sound()
on_wake()

# بعد STT:
on_heard(text)

# بعد executor:
result = execute(parsed)             # {"success": bool, "message": str}
speak(result["message"], lang)       # ✅ دي دالتك
notify("Sound OS", result["message"])  # ✅ دي دالتك
on_done(result["success"])           # ✅ ده bridge بتاعك
```

---

## خامساً — جدول اختبار QA (لدور 6 — Kirollos)

| # | الاختبار | المتوقع | نجح؟ |
|---|---|---|---|
| 1 | `speak("تم فتح المتصفح", "ar")` | الجهاز ينطق الجملة بالعربي | ⬜ |
| 2 | `speak("Browser opened", "en")` | الجهاز ينطق الجملة بالإنجليزي | ⬜ |
| 3 | `speak("", "ar")` | صمت تام (لا شيء) | ⬜ |
| 4 | `notify("Sound OS", "تم")` | إشعار يظهر على سطح المكتب | ⬜ |
| 5 | `python3 -m ui_tts.coucou_bridge` | pill → نص → خلّص | ⬜ |
| 6 | `python3 -m ui_tts.mock_runner` | دورة المحاكاة كاملة تعمل بسلاسة | ⬜ |
| 7 | `on_done(False)` | الـ pill يتحوّل لحالة خطأ | ⬜ |
| 8 | Coucou مقفول والمشروع شغال | المشروع يكمل بدون أي خطأ | ⬜ |
| 9 | `paplay ui_tts/assets/wake.wav` | صوت التنشيط يُسمع | ⬜ |
| 10 | `free -h` قبل وبعد Coucou | نسجّل الفرق في RAM | ⬜ |

---

## سادساً — لو Coucou ما اشتغلش (الخطة البديلة)

لو Coucou تقيل أو ما اشتغلش على أضعف جهاز في الفريق — **مش مشكلة.**

عدّل `coucou_bridge.py` تستبدل الدوال الثلاثة بـ Tkinter بسيطة:

```python
# الخطة البديلة — نافذة Tkinter بسيطة
import tkinter as tk

_root = None
_label = None

def _init():
    global _root, _label
    if _root: return
    _root = tk.Tk()
    _root.title("Sound OS")
    _root.geometry("400x80+600+0")
    _label = tk.Label(_root, text="...", font=("Arial", 16), fg="white", bg="#1a1a2e")
    _label.pack(expand=True)

def on_wake():
    _init(); _label.config(text="🎙️ بسمعك..."); _root.update()

def on_heard(text):
    _init(); _label.config(text=f"💬 {text}"); _root.update()

def on_done(success):
    _init()
    _label.config(text="✅ تم" if success else "❌ خطأ"); _root.update()
```

**الميزة:** باقي الفريق مش هيحس بأي فرق — نفس الدوال الثلاثة، نفس الاستدعاءات.

---

## سابعاً — 🤖 برومبت جاهز ليوسف (AI Assistant Prompt)

> [!TIP]
> **كيف تستخدم هذا البرومبت؟**  
> انسخ النص التالي بالكامل وضعه في محادثة مع أي مساعد ذكاء اصطناعي (مثل ChatGPT أو Claude أو Cursor) ليساعدك في بناء موديول `ui_tts` وتجربته فوراً:

```text
You are a senior Linux and Python systems developer pair-programming with me on an offline voice assistant project named "Sound OS" on Linux (Xubuntu/Ubuntu).
My role is Youssef Alam (Role 5: UI & TTS Feedback), and I am responsible ONLY for the directory: `ui_tts/`.

Context & Current Team State:
- Teammates handling upstream modules (Abram for Wake Word, Yassin for Command Executor, Antonius for Safety) have not finished their modules yet.
- However, our repository has a strict CONTRACT.md and fully working stubs, with 214 pytest tests passing.
- I must work 100% independently in standalone mode without waiting for them and without touching any files outside `ui_tts/` (do NOT edit main.py, executor/, intent_parser/, safety/, or stt/).

My Requirements:
1. CONTRACT.md Rule 7 Compliance:
   - `speak(text: str, lang: str) -> None`: Uses Piper TTS offline (`ar_JO-kareem-medium` for Arabic, `en_US-lessac-medium` for English) piped to `aplay -r 22050 -f S16_LE -c 1`. If Piper fails or is not installed, silently falls back to `espeak-ng -v <lang>`. Never raises exceptions. Empty text does nothing.
   - `notify(title: str, body: str) -> None`: Desktop notifications via `notify-send`. Never raises exceptions.
   - `play_wake_sound() -> None`: Non-blocking playback of `ui_tts/assets/wake.wav` via `paplay` or `aplay`. Never raises exceptions.
2. System Responses (`ui_tts/replies.json`):
   - A complete bilingual JSON dictionary (Egyptian Arabic & English) covering all 13 system intents: open_app, close_app, volume_up, volume_down, mute, brightness_up, brightness_down, create_file, open_folder, web_search, play_media, shutdown, delete_file, plus unknown, error, and confirmation queries.
3. Visual Bridge (`ui_tts/coucou_bridge.py`):
   - Integrates with the Coucou Linux island app via `coucou-hook` with functions `on_wake()`, `on_heard(text)`, and `on_done(success)`.
   - If Coucou is not installed, silently no-op (or fallback to a clean Tkinter window).
4. Standalone Simulator (`ui_tts/mock_runner.py`):
   - A test script that simulates a full cycle (wake sound -> on_wake -> on_heard -> speak -> notify -> on_done) so I can verify my entire UI and voice experience standalone without microphone or real executor.

Please write clean, robust, production-quality Python code for these files, and give me the exact bash commands to install dependencies (piper-tts, espeak-ng, alsa-utils) and test everything in my Linux VM.
```

---

## ثامناً — ملخص التسليم

```
ui_tts/
├── __init__.py          ✅ speak() + notify() + play_wake_sound()
├── coucou_bridge.py     ✅ on_wake() + on_heard() + on_done()
├── replies.json         ✅ كل ردود النظام بالعربي والإنجليزي
└── assets/
    └── wake.wav         ✅ صوت التنشيط (مسجّل أو مجاني الرخصة)
```

**اختبار نهائي سريع:**
```bash
cd /path/to/Sound-OS
python3 -c "
from ui_tts import speak, notify, play_wake_sound
from ui_tts.coucou_bridge import on_wake, on_heard, on_done
import time

play_wake_sound(); on_wake(); time.sleep(1)
on_heard('افتح المتصفح'); time.sleep(1)
speak('تم فتح المتصفح', 'ar')
notify('Sound OS', 'تم فتح المتصفح')
on_done(True)
print('All good ✅')
"
```

---

## 📚 المراجع

| المصدر | الرابط |
|---|---|
| مستودع Coucou | https://github.com/Louis-CFM/coucou |
| ربط الأدوات الخارجية بـ Coucou | https://github.com/Louis-CFM/coucou/blob/main/docs/AGENTS.md |
| إصدارات لينكس | https://github.com/Louis-CFM/coucou/releases/tag/linux-latest |
| رخصة أصول Coucou | https://github.com/Louis-CFM/coucou/blob/main/LICENSE-ASSETS.md |
| وثائق Piper TTS | https://github.com/rhasspy/piper |
| وثائق subprocess | https://docs.python.org/3/library/subprocess.html |

---

> **تنبيه ترخيص:** اسم Coucou وشخصية Mochi وأصواته حقوقها محفوظة.
> ✅ نشغّل التطبيق كما هو وننسب الواجهة له في التقرير.
> ❌ لا نرفع أصوات أو صور Coucou في الـ repo.
