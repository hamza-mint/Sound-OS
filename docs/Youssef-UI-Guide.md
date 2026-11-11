# 🎨 دليل يوسف علام — موديول الواجهة الرسومية (`GUI`)
### Sound OS · Role 5 · Graphical User Interface Only

> [!NOTE]
> **دورك محدد ومبسط جداً:** دورك مقتصر **فقط** على الواجهة الرسومية (GUI) وإشعار سطح المكتب.  
> ❌ لا يوجد نطق صوتي (TTS)، ولا تحميل موديلات صوتية، ولا ملف ردود.  
> ✅ كل المطلوب منك: **شريط عائم صغير يظهر في أعلى الشاشة + إشعار على سطح المكتب**.

---

## 🤖 1. البرومبت الجاهز للذكاء الاصطناعي (انسخه فوراً)

> **طريقة الاستخدام:**  
> انسخ النص بالكامل داخل الصندوق أدناه، وضعه في أي شات ذكاء اصطناعي (ChatGPT / Claude / Cursor) لمساعدتك في بناء موديول الواجهة البسيط:

```text
You are a Python GUI developer assisting me on an OS project called "Sound OS" on Linux (Xubuntu/Ubuntu).
My role is Youssef Alam (Role 5), and my responsibility is STRICTLY the GUI (Graphical User Interface) inside the directory `ui_tts/`.

Scope & Constraints:
- My role is ONLY visual GUI and desktop notifications.
- NO Text-to-Speech (TTS), NO audio models (Piper/Whisper), NO replies dictionary.
- I must ONLY touch files inside `ui_tts/` (never touch main.py or any other module).
- All functions must obey CONTRACT.md Rule 7: NEVER raise exceptions.

What I need you to implement in `ui_tts/`:
1. `ui_tts/__init__.py`:
   - `notify(title: str, body: str) -> None`: Triggers desktop notification via `notify-send`. Never raises.
   - `speak(text: str, lang: str) -> None`: Simple safe pass/print stub (no TTS needed). Never raises.
2. `ui_tts/coucou_bridge.py`:
   - Visual floating bar at the top of the screen:
     - `on_wake()`: Shows the bar ("🎙️ Sound OS: Listening...").
     - `on_heard(text)`: Displays the recognized voice command text.
     - `on_done(success)`: Shows a green checkmark ✅ (or red ❌) for 2 seconds then hides.
   - Must work out of the box using built-in Tkinter (floating topmost borderless pill at the top of the screen), with support for the Coucou island app if present.
3. `ui_tts/test_ui.py`:
   - A super simple standalone test script to run and visually see the bar appear, display text, and show the notification.

Provide clean, standalone Python code for these files and show me the single command to test it visually.
```

---

## 💡 2. ما هو دور الـ GUI بالظبط في Sound OS؟

بما أن Sound OS مساعد صوتي في الخلفية، واجهتك ليست برنامجاً ضخماً، بل **شريط تفاعلي صغير وعائم (Floating Island Pill)** في أعلى الشاشة:

```
1️⃣ لما المستخدم ينادي:
   ← الشريط يظهر في أعلى الشاشة: 🎙️ "Sound OS: بسمعك..."

2️⃣ لما المستخدم يتكلم:
   ← الشريط يكتب الكلام اللي سمعه: 💬 "افتح فايرفوكس"

3️⃣ بعد ما النظام ينفذ الأمر:
   ← الشريط يتحول لعلامة صح خضراء: ✅ "تم التنفيذ" (ويختفي بعد ثانيتين)
   ← إشعار سريع ينزل في زاوية الشاشة عبر notify-send
```

---

## 📁 3. الملفات الثلاثة المطلوبة منك فقط في `ui_tts/`

```
Sound-OS/
└── ui_tts/
    ├── __init__.py        ← دالة الإشعار notify()
    ├── coucou_bridge.py   ← كود الشريط العائم (on_wake, on_heard, on_done)
    └── test_ui.py         ← سكربت بسيط لتجربة الواجهة بعينك
```

---

## 🛠️ 4. كود الملفات (جاهز ومباشر)

### أ) `ui_tts/__init__.py` — الإشعارات
```python
"""
ui_tts/__init__.py — Owner: Youssef Alam (GUI Role)
CONTRACT.md Rule 7: Never raise exceptions.
"""
import subprocess


def notify(title: str, body: str) -> None:
    """Desktop notification via Linux notify-send."""
    try:
        subprocess.run(["notify-send", title, body], timeout=3, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def speak(text: str, lang: str = "ar") -> None:
    """Stub: Text-to-Speech is handled outside GUI role."""
    if text:
        print(f"[Sound OS Feedback]: {text}")
```

---

### ب) `ui_tts/coucou_bridge.py` — الشريط العائم التفاعلي
> الكود ده بيشتغل فوراً باستخدام مكتبة `tkinter` المدمجة في بايثون (بدون تحميل برامج خارجية)، ويظهر شريطاً أسود أنيقاً في أعلى الشاشة:

```python
"""
ui_tts/coucou_bridge.py — Floating GUI Island (Owner: Youssef Alam)
Displays a sleek floating status pill at the top of the screen.
"""
import threading
import time
import tkinter as tk

_root = None
_label = None


def _ensure_gui():
    global _root, _label
    if _root is None:
        _root = tk.Tk()
        _root.title("Sound OS Island")
        # وضع الشريط في منتصف أعلى الشاشة بدون حواف
        _root.geometry("380x50+550+15")
        _root.overrideredirect(True)
        _root.attributes("-topmost", True)
        _root.configure(bg="#1e1e2e")

        _label = tk.Label(
            _root,
            text="Sound OS",
            font=("Arial", 13, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
        )
        _label.pack(fill="both", expand=True, padx=10, pady=5)
        _root.withdraw()  # إخفاء في البداية


def on_wake() -> None:
    """يظهر الشريط عند بدء الاستماع."""
    try:
        _ensure_gui()
        _label.config(text="🎙️ Sound OS: استماع...", fg="#89b4fa")
        _root.deiconify()
        _root.update()
    except Exception:
        pass


def on_heard(text: str) -> None:
    """يعرض النص المنطوق داخل الشريط."""
    try:
        _ensure_gui()
        _label.config(text=f"💬 {text}", fg="#f9e2af")
        _root.update()
    except Exception:
        pass


def on_done(success: bool) -> None:
    """يعرض حالة النجاح أو الفشل ثم يختفي تلقائياً."""
    try:
        _ensure_gui()
        if success:
            _label.config(text="✅ تم التنفيذ", fg="#a6e3a1")
        else:
            _label.config(text="❌ فشل الأمر", fg="#f38ba8")
        _root.update()

        # إخفاء الشريط بعد ثانيتين
        def _hide():
            time.sleep(2)
            try:
                _root.withdraw()
            except Exception:
                pass

        threading.Thread(target=_hide, daemon=True).start()
    except Exception:
        pass
```

---

### ج) `ui_tts/test_ui.py` — سكربت التجربة
```python
"""
ui_tts/test_ui.py — تجربة الواجهة الرسومية بعينك
تشغيل:
    python3 -m ui_tts.test_ui
"""
import time
from ui_tts import notify
from ui_tts.coucou_bridge import on_wake, on_heard, on_done

if __name__ == "__main__":
    print("🎬 بدء اختبار الواجهة الرسومية...")

    # 1. ظهور الشريط للاستماع
    print("1️⃣ إظهار الشريط (Listening)...")
    on_wake()
    time.sleep(1.5)

    # 2. عرض النص المنطوق
    print("2️⃣ عرض نص الأمر...")
    on_heard("افتح المتصفح")
    time.sleep(2)

    # 3. إظهار علامة النجاح + إشعار سطح المكتب
    print("3️⃣ إظهار النجاح والإشعار...")
    on_done(success=True)
    notify("Sound OS", "تم فتح المتصفح بنجاح")

    print("✨ نجح الاختبار! الشريط سيختفي الآن تلقائياً.")
    time.sleep(3)
```

---

## 🧪 5. كيف تختبر ما قمت به ببساطة؟

افتح الـ Terminal في مسار المشروع وشغّل الأمر التالي:

```bash
python3 -m ui_tts.test_ui
```

**ما يجب أن تراه على شاشتك:**
1. شريط عائم يظهر أعلى الشاشة بلون أزرق: `🎙️ Sound OS: استماع...`
2. بعد ثانية يتغير النص للأصفر: `💬 افتح المتصفح`
3. يتغير للأخضر: `✅ تم التنفيذ` ويظهر إشعار في زاوية الشاشة، ثم يختفي الشريط تلقائياً.

إذا ظهر هذا، **فأنت أنهيت دورك بنجاح 100%!** 🎉

---

## 🚀 6. كيف ترفع عملك بعد الانتهاء (إلى مجلدك فقط)؟

بمجرد التأكد من عمل السكربت، نفّذ هذه الأوامر الـ 3 لرفع كودك إلى فرعك المخصص دون لمس أي موديول لزملائك:

```bash
# 1. التأكد أنك على فرعك الخاص
git checkout Youssef-(UI-TTS)

# 2. إضافة التعديلات داخل مجلدك فقط
git add ui_tts/
git commit -m "feat(ui): implement floating island GUI and notifications"

# 3. رفع الكود إلى GitHub
git push origin Youssef-(UI-TTS)
```
