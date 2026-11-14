import json
import logging
import os
import time
from typing import Dict, Any, Callable, Optional

# إعداد سجل الأمان (Security Audit Log) لتوثيق كل قرار موافقة أو رفض
LOG_FILE = os.path.join(os.path.dirname(__file__), "security_audit.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# كلمات التأكيد والرفض المدعومة بالعامية المصرية والعربية والإنجليزية
YES_WORDS = {
    "نعم", "ايوه", "أيوة", "ايوا", "اه", "آه", "طبعا", "اكيد", "أكيد",
    "موافق", "نفذ", "تمام", "yes", "yeah", "yep", "sure", "confirm", "ok"
}
NO_WORDS = {
    "لا", "لأ", "لأه", "الغاء", "إلغاء", "كنسل", "وقف", "بلاش",
    "no", "nope", "cancel", "stop", "abort"
}

CANONICAL_FOLDERS = {
    "home", "downloads", "documents", "desktop", "pictures", "music", "videos",
    "الرئيسية", "التنزيلات", "التحميلات", "المستندات", "سطح المكتب", "الصور", "الموسيقى", "الفيديوهات"
}


class SafetyLayer:
    """
    Safety Layer (Stage 4 in Sound OS Pipeline):
    Owner: Antonius
    Enforces allowlist, confidence threshold, sandboxing, cooldown, and confirmation.
    Complies with CONTRACT.md v1.0.
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "allowlist.json")

        self.config = self._load_config(config_path)
        self.min_confidence: float = float(self.config.get("min_confidence", 0.65))
        self.confirmation_timeout: float = float(self.config.get("confirmation_timeout_sec", 5.0))
        self.cooldown_seconds: float = float(self.config.get("dangerous_cooldown_sec", 30.0))

        self.safe_intents = set(self.config.get("safe_intents", []))
        self.dangerous_intents = set(self.config.get("dangerous_intents", []))
        self.allowed_intents = self.safe_intents.union(self.dangerous_intents)
        self.allowed_apps = set(app.lower() for app in self.config.get("allowed_apps", []))

        raw_dirs = self.config.get(
            "safe_directories",
            ["~/Desktop", "~/Documents", "~/Downloads", "~/SoundOS_Files"]
        )
        self.safe_directories = [os.path.abspath(os.path.expanduser(d)) for d in raw_dirs]

        # قاموس لحفظ وقت آخر تنفيذ لكل أمر خطير لتطبيق الـ Cooldown
        self.last_dangerous_time: Dict[str, float] = {}

    @staticmethod
    def _load_config(path: str) -> Dict[str, Any]:
        """تحميل إعدادات الأمان من ملف allowlist.json أو استخدام قيم افتراضية آمنة."""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "min_confidence": 0.65,
            "confirmation_timeout_sec": 5.0,
            "dangerous_cooldown_sec": 30.0,
            "safe_intents": [
                "open_app", "close_app", "volume_up", "volume_down", "mute",
                "brightness_up", "brightness_down", "create_file", "open_folder",
                "web_search", "play_media"
            ],
            "dangerous_intents": ["shutdown", "delete_file"],
            "allowed_apps": [
                "firefox", "chrome", "terminal", "files", "calculator", "editor", "vlc", "settings",
                "google-chrome", "gnome-calculator", "kcalc", "nautilus", "thunar", "gedit",
                "mousepad", "code", "gnome-terminal", "xfce4-terminal", "x-terminal-emulator",
                "konsole", "mpv", "xfce4-settings-manager"
            ],
            "safe_directories": [
                "~/Desktop", "~/Documents", "~/Downloads", "~/Music", "~/Pictures", "~/Videos",
                "~/SoundOS_Files", "/tmp/sound_os_workspace"
            ]
        }

    def _is_safe_path(self, target_path: str) -> bool:
        """منع ثغرات Path Traversal (مثل ../../etc) وحصر التعامل داخل المجلدات والملفات الآمنة فقط."""
        if not target_path or ".." in target_path or "\\" in target_path:
            return False

        # 1. الأسماء البسيطة للملفات (تنفذ داخل ~/SoundOS_Files/ بأمان)
        clean_name = os.path.basename(target_path).strip()
        if clean_name == target_path.strip() and not os.path.isabs(target_path):
            return True

        # 2. المجلدات القياسية (canonical folder names)
        if target_path.strip().lower() in CANONICAL_FOLDERS:
            return True

        # 3. المسارات الكاملة داخل المجلدات الآمنة
        abs_target = os.path.abspath(os.path.expanduser(target_path))
        return any(
            abs_target == safe_dir or abs_target.startswith(safe_dir + os.sep)
            for safe_dir in self.safe_directories
        )

    def _validate_params(self, intent: str, params: Dict[str, Any]) -> tuple[bool, str]:
        """فحص الـ params الخاصة بكل أمر للتأكد من مطابقتها للـ Allowlist."""
        if not isinstance(params, dict):
            return False, "Invalid params structure (must be a JSON object)."

        # 1. فحص اسم البرنامج في أوامر الفتح والإغلاق
        if intent in {"open_app", "close_app"}:
            app = str(params.get("app", "")).strip().lower()
            if not app:
                return False, f"Missing 'app' parameter for intent '{intent}'."
            if app not in self.allowed_apps:
                return False, f"App '{app}' is blocked (not in allowed_apps)."

        # 2. فحص المسارات في أوامر الملفات والمجلدات
        elif intent in {"create_file", "delete_file", "open_folder"}:
            raw_path = str(
                params.get("name") or params.get("path") or params.get("folder") or params.get("filename") or ""
            ).strip()

            # create_file قد لا يحتوي على اسم ويأخذ اسماً افتراضياً طبقاً لـ CONTRACT.md
            if not raw_path and intent == "create_file":
                raw_path = "new_file.txt"

            if not raw_path:
                return False, f"Missing name/path parameter for intent '{intent}'."

            if not self._is_safe_path(raw_path):
                return False, f"Security violation: Path '{raw_path}' is outside safe directories."

        return True, "Parameters are valid and safe."

    def _ask_confirmation(
        self,
        intent: str,
        lang: str,
        speak_fn: Optional[Callable[[str, str], None]] = None,
        update_state_fn: Optional[Callable[[str, Optional[str]], None]] = None,
        listen_yes_no_fn: Optional[Callable[[float], Optional[str]]] = None,
    ) -> tuple[bool, str]:
        """طلب تأكيد صوتي من المستخدم خلال 5 ثوانٍ قبل تنفيذ الأوامر الخطيرة."""
        if listen_yes_no_fn is None:
            return False, "Dangerous command blocked: No confirmation handler provided."

        prompt_msg = (
            "You are about to execute a dangerous command. Are you sure?"
            if lang == "en"
            else "أنت على وشك تنفيذ أمر خطير. هل أنت متأكد؟"
        )

        if update_state_fn:
            update_state_fn("waiting_confirmation", prompt_msg)
        if speak_fn:
            speak_fn(prompt_msg, lang)

        t0 = time.monotonic()
        try:
            user_response = listen_yes_no_fn(self.confirmation_timeout)
        except Exception as exc:
            return False, f"Confirmation failed due to listener error: {exc}"

        elapsed = time.monotonic() - t0
        if elapsed > self.confirmation_timeout:
            return False, f"Confirmation timed out ({elapsed:.1f}s > {self.confirmation_timeout:.1f}s)."

        if not user_response:
            return False, "No confirmation heard within 5 seconds. Command cancelled."

        reply = str(user_response).strip().lower()
        tokens = set(reply.split())

        # أسبقية لكلمات الرفض (لو قال: "لأ مش موافق" يرفض فوراً)
        if tokens.intersection(NO_WORDS):
            return False, f"User explicitly rejected dangerous command '{intent}' (said: '{reply}')."

        if tokens.intersection(YES_WORDS):
            return True, f"User confirmed dangerous command '{intent}' within {elapsed:.1f}s."

        return False, f"Ambiguous confirmation response '{reply}'. Command cancelled for safety."

    def check(
        self,
        parsed_command: Dict[str, Any],
        speak_fn: Optional[Callable[[str, str], None]] = None,
        update_state_fn: Optional[Callable[[str, Optional[str]], None]] = None,
        listen_yes_no_fn: Optional[Callable[[float], Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """
        الدالة الأساسية لفحص الأمان:
        تستقبل JSON الأمر المفسر وترجع قرار الاعتماد أو الرفض أو طلب التأكيد.
        متوافقة تماماً مع CONTRACT.md v1.0.
        """
        if not isinstance(parsed_command, dict):
            return self._reject({}, "Invalid input: Expected a JSON dictionary.", "block")

        intent = str(parsed_command.get("intent", "")).strip()
        params = parsed_command.get("params", {})
        if not isinstance(params, dict):
            params = {}
        lang = str(parsed_command.get("lang", "en")).strip()
        raw_text = str(parsed_command.get("raw_text", "")).strip()
        confidence = float(parsed_command.get("confidence", 1.0))

        # الفلتر 1: حماية من تفعيل كلمة التنشيط بالخطأ (Accidental Wake Word Trigger)
        if "raw_text" in parsed_command and len(raw_text.strip()) < 2:
            msg = "Accidental wake word trigger (empty or noise input)."
            return self._reject(parsed_command, msg, "block")

        # الفلتر 2: حماية من الأوامر المسموعة خطأ (Confidence قليل)
        if confidence < self.min_confidence:
            msg = f"Low confidence score ({confidence:.2f} < {self.min_confidence}). Possible misheard speech."
            return self._reject(parsed_command, msg, "block")

        # الفلتر 3: فحص الـ Intent (unknown أو أمر غير مسجل)
        if intent == "unknown":
            msg = "I did not understand." if lang == "en" else "مفهمتش."
            return self._reject(parsed_command, msg, "block")

        if intent not in self.allowed_intents:
            msg = f"Unauthorized intent '{intent}' (not in allowlist)."
            return self._reject(parsed_command, msg, "block")

        # الفلتر 4: فحص سلامة البراميترز والمسارات الآمنة
        valid_params, param_msg = self._validate_params(intent, params)
        if not valid_params:
            return self._reject(parsed_command, param_msg, "block")

        # الفلتر 5 و 6: إجراءات الأوامر الخطيرة (shutdown, delete_file)
        if intent in self.dangerous_intents:
            now = time.monotonic()
            last_exec = self.last_dangerous_time.get(intent)

            # الفلتر 5: فحص الـ Cooldown
            if last_exec is not None and (now - last_exec) < self.cooldown_seconds:
                wait_left = int(self.cooldown_seconds - (now - last_exec))
                msg = f"Cooldown active for dangerous intent '{intent}'. Try again in {wait_left}s."
                return self._reject(parsed_command, msg, "block")

            # الفلتر 6: التحقق من التأكيد
            # أ) لو تم تمرير listen_yes_no_fn -> تأكيد تفاعلي فوري
            if listen_yes_no_fn is not None:
                confirmed, confirm_msg = self._ask_confirmation(
                    intent=intent,
                    lang=lang,
                    speak_fn=speak_fn,
                    update_state_fn=update_state_fn,
                    listen_yes_no_fn=listen_yes_no_fn,
                )
                if not confirmed:
                    return self._reject(parsed_command, confirm_msg, "block")

                self.last_dangerous_time[intent] = time.monotonic()
            else:
                # ب) معيار CONTRACT.md: إرجاع decision="confirm" لـ main.py ليسأل المستخدم
                confirm_prompt = "Are you sure?" if lang == "en" else "متأكد؟"
                logging.info(f"CONFIRM_REQUIRED | intent={intent} | prompt='{confirm_prompt}'")
                return {
                    "decision": "confirm",
                    "message": confirm_prompt,
                    "approved": False,
                    "reason": "Requires confirmation for dangerous command.",
                    "command": parsed_command,
                }

        # اعتماد الأمر وتجهيز الـ JSON النهائي
        approved_payload = {
            "intent": intent,
            "params": params,
            "lang": lang,
            "raw_text": raw_text,
        }
        logging.info(f"APPROVED | intent={intent} | params={params} | text='{raw_text}'")

        return {
            "decision": "allow",
            "message": "",
            "approved": True,
            "reason": "Command passed all safety checks.",
            "command": approved_payload,
        }

    @staticmethod
    def _reject(cmd: Dict[str, Any], reason: str, decision: str = "block") -> Dict[str, Any]:
        """تسجيل سبب الرفض في سجل الأمان وإرجاع كائن الرفض."""
        intent = cmd.get("intent", "unknown") if isinstance(cmd, dict) else "malformed"
        logging.warning(f"REJECTED | intent={intent} | reason={reason}")
        return {
            "decision": decision,
            "message": reason,
            "approved": False,
            "reason": reason,
            "command": cmd if isinstance(cmd, dict) else {},
        }
