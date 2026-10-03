"""دور 4: التنفيذ على لينكس — بيخلّي الأمر يتنفذ فعليًا.

بياخد : اسم الأمر (intent)
بيطلّع: {"ok": True/False, "message": "..."}

قواعد الأمان:
- Allowlist: أي أمر برّا القايمة بيتم رفضه.
- ممنوع shell=True. الأوامر قوايم ثابتة.
- الإطفاء لازم تأكيد صريح.
- SOUNDOS_DRY_RUN=1 بيطبع الأمر من غير ما ينفّذه (آمن للتجربة).
"""
import os
import subprocess

# كل أمر مربوط بأمر لينكس ثابت. اتأكد من كل أمر على جهاز الفريق (X11/Wayland، PulseAudio/PipeWire).
ALLOWED = {
    "open_browser": (["xdg-open", "https://www.google.com"], "تم فتح المتصفح"),
    "volume_up": (["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"], "تم رفع الصوت"),
    "shutdown": (["systemctl", "poweroff"], "جاري إطفاء الجهاز"),
}
NEEDS_CONFIRM = {"shutdown"}


def run_intent(intent: str, confirmed: bool = False, dry_run=None) -> dict:
    if dry_run is None:
        dry_run = os.environ.get("SOUNDOS_DRY_RUN", "1") == "1"
    if intent not in ALLOWED:
        return {"ok": False, "message": "أمر غير مسموح أو غير مفهوم"}
    if intent in NEEDS_CONFIRM and not confirmed:
        return {"ok": False, "message": "محتاج تأكيد"}
    cmd, success_msg = ALLOWED[intent]
    if dry_run:
        return {"ok": True, "message": f"[تجربة] كان هيتنفذ: {' '.join(cmd)}"}
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"ok": False, "message": "تعذر تنفيذ الأمر على الجهاز ده"}
    if result.returncode != 0:
        return {"ok": False, "message": "فشل تنفيذ الأمر"}
    return {"ok": True, "message": success_msg}


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "volume_up"
    print(run_intent(name, confirmed=("--yes" in sys.argv)))
