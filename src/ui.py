"""دور 5: الواجهة والرد — بيوري المستخدم إيه اللي حصل.

بياخد : حالة النظام + رسالة النتيجة
بيطلّع: عرض على الشاشة + رد صوتي اختياري

حاليًا هيكل مؤقت بيطبع في الـ Terminal. دور 5 يضيف نافذة Tkinter بنفس الدوال.
"""
import shutil
import subprocess

STATES = {
    "listening": "🟢 بسمعك...",
    "thinking": "🟡 بفهم...",
    "done": "✅ تم",
    "error": "❌ حصل خطأ",
}


def show_status(state: str, message: str = "") -> None:
    print(f"{STATES.get(state, state)} {message}".strip())


def speak(message: str) -> None:
    """رد صوتي خفيف بـ espeak-ng لو متنصّب. من غير shell."""
    if shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-v", "ar", message], check=False)


if __name__ == "__main__":
    show_status("listening")
    show_status("done", "تجربة")
