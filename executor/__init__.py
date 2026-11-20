"""
Sound OS - Command Executor Module (Owner: Yassin)
Interface Contract: CONTRACT.md v1.0
Entry point: execute(command: dict) -> dict
Output: {"success": bool, "message": str}
"""
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, Tuple

from executor import actions

logger = logging.getLogger("soundos.executor")

# CONTRACT.md §7: executor must complete under 1 second
_MAX_EXECUTION_SECS = 1.0

CONFIG_PATH = Path(__file__).parent / "apps.json"
_SAFE_BINARY = re.compile(r"[a-z0-9][a-z0-9._+-]{0,40}")

# Load application and folder configurations
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        APP_CONFIG = json.load(f)
except Exception:
    APP_CONFIG = {"apps": {}, "folders": {}}


def _find_app(app_name: str) -> Tuple[str, Dict[str, Any]] | None:
    """Finds app config by canonical name or alias (Arabic/English)."""
    if not app_name:
        return None
    app_clean = app_name.strip().lower()

    # Exact canonical match
    apps = APP_CONFIG.get("apps", {})
    if app_clean in apps:
        return app_clean, apps[app_clean]

    # Search in aliases
    for canonical, details in apps.items():
        aliases = [a.lower() for a in details.get("aliases", [])]
        if app_clean in aliases:
            return canonical, details

    # Fallback: run the name as a program (needed for allowlisted apps such as "telegram") but ONLY if it
    # looks like a plain program name. No path ("/x/y"), no flag ("--help"), no spaces: defense in depth in
    # case execute() is ever called without the safety layer in front of it.
    if not _SAFE_BINARY.fullmatch(app_clean):
        return None
    return app_clean, {
        "cmd": [app_clean],
        "process": app_clean,
        "aliases": [app_clean]
    }


def _resolve_folder(folder_name: str) -> str:
    """Maps folder name or alias to directory path string. Returns "" for an unsafe custom name."""
    folder_clean = (folder_name or "").strip().lower()
    folders = APP_CONFIG.get("folders", {})
    if folder_clean in folders:
        return folders[folder_clean]
    if not folder_clean:
        return "~"
    # Custom name -> a sub-folder of home. Never a path that climbs out of it.
    if ".." in folder_clean or "/" in folder_clean or "\\" in folder_clean or os.path.isabs(folder_clean) \
            or folder_clean.startswith("~"):
        return ""
    return f"~/{folder_name.strip()}"


# ---------------------------------------------------------------------------
# Handlers for Dispatch Table
# ---------------------------------------------------------------------------
def _handle_open_app(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    app_name = (params.get("app") or "").strip()
    if not app_name:
        msg = "No application specified." if lang == "en" else "لم يتم تحديد التطبيق."
        return False, msg

    app_info = _find_app(app_name)
    if not app_info:
        msg = f"Unknown application: '{app_name}'" if lang == "en" else f"تطبيق غير معروف: '{app_name}'"
        return False, msg

    canonical, cfg = app_info
    if dry_run:
        msg = f"[DRY-RUN] Opening {canonical}" if lang == "en" else f"[تجربة] فتح تطبيق {canonical}"
        return True, msg

    ok, err = actions.launch_app(cfg)
    if ok:
        msg = f"Opened {canonical}." if lang == "en" else f"تم فتح {canonical}."
    else:
        msg = f"Failed to open {canonical}: {err}" if lang == "en" else f"فشل فتح {canonical}: {err}"
    return ok, msg


def _handle_close_app(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    app_name = (params.get("app") or "").strip()
    if not app_name:
        app_name = "current"

    app_info = _find_app(app_name)
    if not app_info:
        msg = f"Unknown application: '{app_name}'" if lang == "en" else f"تطبيق غير معروف: '{app_name}'"
        return False, msg

    canonical, cfg = app_info
    if dry_run:
        if canonical == "current":
            msg = "[DRY-RUN] Closing active window." if lang == "en" else "[تجربة] إغلاق النافذة الحالية."
        else:
            msg = f"[DRY-RUN] Closing {canonical}" if lang == "en" else f"[تجربة] إغلاق تطبيق {canonical}"
        return True, msg

    ok, err = actions.terminate_app(cfg)
    if ok:
        if canonical == "current":
            msg = "Closed active application." if lang == "en" else "تم إغلاق التطبيق الحالي."
        else:
            msg = f"Closed {canonical}." if lang == "en" else f"تم إغلاق {canonical}."
    else:
        msg = f"Could not close {canonical}: {err}" if lang == "en" else f"تعذر إغلاق {canonical}: {err}"
    return ok, msg


def _handle_volume_up(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "[DRY-RUN] Volume increased." if lang == "en" else "[تجربة] تم رفع الصوت."
    ok, err = actions.adjust_volume("up")
    msg = ("Volume increased." if ok else f"Volume error: {err}") if lang == "en" else ("تم رفع الصوت." if ok else f"خطأ في الصوت: {err}")
    return ok, msg


def _handle_volume_down(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "[DRY-RUN] Volume decreased." if lang == "en" else "[تجربة] تم خفض الصوت."
    ok, err = actions.adjust_volume("down")
    msg = ("Volume decreased." if ok else f"Volume error: {err}") if lang == "en" else ("تم خفض الصوت." if ok else f"خطأ في الصوت: {err}")
    return ok, msg


def _handle_mute(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "[DRY-RUN] Muted." if lang == "en" else "[تجربة] تم كتم الصوت."
    ok, err = actions.set_mute()
    msg = ("Sound muted." if ok else f"Mute error: {err}") if lang == "en" else ("تم كتم الصوت." if ok else f"خطأ في كتم الصوت: {err}")
    return ok, msg


def _handle_brightness_up(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "[DRY-RUN] Brightness increased." if lang == "en" else "[تجربة] زيادة السطوع."
    ok, err = actions.adjust_brightness("up")
    msg = ("Brightness increased." if ok else f"Brightness error: {err}") if lang == "en" else ("تمت زيادة السطوع." if ok else f"خطأ في السطوع: {err}")
    return ok, msg


def _handle_brightness_down(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "[DRY-RUN] Brightness decreased." if lang == "en" else "[تجربة] خفض السطوع."
    ok, err = actions.adjust_brightness("down")
    msg = ("Brightness decreased." if ok else f"Brightness error: {err}") if lang == "en" else ("تم تقليل السطوع." if ok else f"خطأ في السطوع: {err}")
    return ok, msg


def _handle_open_folder(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    folder_raw = params.get("folder") or "home"
    target_path = _resolve_folder(folder_raw)
    if not target_path:
        msg = "Invalid folder name." if lang == "en" else "اسم مجلد غير صالح."
        return False, msg
    if dry_run:
        return True, f"[DRY-RUN] Opening folder {target_path}" if lang == "en" else f"[تجربة] فتح مجلد {target_path}"
    ok, err = actions.open_directory(target_path)
    msg = (f"Opened folder." if ok else f"Folder error: {err}") if lang == "en" else ("تم فتح المجلد." if ok else f"خطأ في فتح المجلد: {err}")
    return ok, msg


def _handle_create_file(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    fname = params.get("name") or "new_file.txt"
    if "/" in fname or "\\" in fname or ".." in fname or os.path.isabs(fname):
        msg = "Invalid filename: path traversal is not permitted." if lang == "en" else "اسم ملف غير صالح: غير مسموح بالمسارات المتداخلة."
        return False, msg
    if dry_run:
        return True, f"[DRY-RUN] Creating file {fname}" if lang == "en" else f"[تجربة] إنشاء ملف {fname}"
    ok, err = actions.create_user_file(fname)
    msg = (f"File '{fname}' created." if ok else f"Create failed: {err}") if lang == "en" else (f"تم إنشاء الملف '{fname}'." if ok else f"فشل إنشاء الملف: {err}")
    return ok, msg


def _handle_delete_file(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    fname = params.get("name", "")
    if not fname:
        return False, "No file specified." if lang == "en" else "لم يتم تحديد اسم الملف."
    if "/" in fname or "\\" in fname or ".." in fname or os.path.isabs(fname):
        msg = "Invalid filename: path traversal is not permitted." if lang == "en" else "اسم ملف غير صالح: غير مسموح بالمسارات المتداخلة."
        return False, msg
    ok, err = actions.delete_user_file(fname, dry_run=dry_run)
    msg = (f"File '{fname}' deleted." if ok else f"Delete failed: {err}") if lang == "en" else (f"تم حذف الملف '{fname}'." if ok else f"فشل حذف الملف: {err}")
    return ok, msg


def _handle_web_search(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    query = (params.get("query") or "").strip()
    if not query:
        msg = "Empty search query." if lang == "en" else "استعلام البحث فارغ."
        return False, msg
    if dry_run:
        return True, f"[DRY-RUN] Searching web for: {query}" if lang == "en" else f"[تجربة] بحث ويب عن: {query}"
    ok, err = actions.search_web(query)
    if not ok and (err == "offline" or "No internet" in err):
        msg = "No internet connection available." if lang == "en" else "لا يوجد اتصال بالإنترنت حالياً."
        return False, msg
    msg = (f"Searching for '{query}'." if ok else f"Search error: {err}") if lang == "en" else (f"جاري البحث عن '{query}'." if ok else f"خطأ في البحث: {err}")
    return ok, msg


def _handle_play_media(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    query = (params.get("query") or "").strip()
    if dry_run:
        return True, "[DRY-RUN] Playing media." if lang == "en" else "[تجربة] تشغيل الوسائط."
    ok, err = actions.play_media_content(query)
    if not ok and (err == "offline" or "No internet" in err):
        msg = "No internet connection to stream media." if lang == "en" else "لا يوجد اتصال بالإنترنت لتشغيل الوسائط."
        return False, msg
    msg = ("Playing media." if ok else f"Media error: {err}") if lang == "en" else ("جاري تشغيل الوسائط." if ok else f"خطأ في الوسائط: {err}")
    return ok, msg


def _handle_shutdown(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        msg = "[DRY-RUN] Shutdown simulated." if lang == "en" else "[تجربة] تم محاكاة إيقاف التشغيل."
        return True, msg
    ok, err = actions.system_shutdown(dry_run=False)
    msg = ("Shutting down system." if ok else f"Shutdown error: {err}") if lang == "en" else ("جاري إيقاف تشغيل الجهاز." if ok else f"خطأ في إيقاف التشغيل: {err}")
    return ok, msg


def _handle_send_message(params: dict, lang: str, dry_run: bool) -> Tuple[bool, str]:
    """Generic send_message handler: open the system mail client or messaging app."""
    recipient = (params.get("recipient") or params.get("contact") or "").strip()
    msg_text = (params.get("message") or params.get("text") or "").strip()
    if dry_run:
        return True, (f"[DRY-RUN] Send message to {recipient or 'contact'}" if lang == "en"
                      else f"[تجربة] إرسال رسالة إلى {recipient or 'جهة الاتصال'}")
    # Open the default messaging app via xdg-open mailto: (works across distros)
    import urllib.parse
    target = f"mailto:{urllib.parse.quote(recipient)}" if recipient else "mailto:"
    if msg_text:
        target += f"?body={urllib.parse.quote(msg_text)}"
    ok, err = actions.launch_app({"cmd": ["xdg-open", target], "process": "", "aliases": []})
    if ok:
        msg = (f"Message ready for {recipient}." if recipient else "Messaging app opened.") if lang == "en" \
              else (f"جاهز للإرسال إلى {recipient}." if recipient else "فُتح تطبيق الرسائل.")
    else:
        msg = (f"Failed to open messaging app: {err}" if lang == "en"
               else f"فشل فتح تطبيق الرسائل: {err}")
    return ok, msg


# ---------------------------------------------------------------------------
# Dispatch Table
# ---------------------------------------------------------------------------
DISPATCH_TABLE = {
    "open_app": _handle_open_app,
    "close_app": _handle_close_app,
    "volume_up": _handle_volume_up,
    "volume_down": _handle_volume_down,
    "mute": _handle_mute,
    "brightness_up": _handle_brightness_up,
    "brightness_down": _handle_brightness_down,
    "open_folder": _handle_open_folder,
    "create_file": _handle_create_file,
    "delete_file": _handle_delete_file,
    "web_search": _handle_web_search,
    "play_media": _handle_play_media,
    "send_message": _handle_send_message,
    "shutdown": _handle_shutdown,
}


def execute(command: dict) -> dict:
    """
    Main entry point for command execution.
    Complies with CONTRACT.md:
    - Never raises exceptions.
    - Honours SOUNDOS_DRY_RUN=1 environment variable.
    - Enforces direct approval on dangerous intents (Slide 7 & 9).
    - Returns format: {"success": bool, "message": str} in the requested lang.
    - Logs a warning if execution exceeds 1 second (CONTRACT.md §7).
    """
    t0 = time.monotonic()
    try:
        if not isinstance(command, dict):
            return {"success": False, "message": "Invalid command format."}

        intent = command.get("intent")
        params = command.get("params") or {}
        if not isinstance(params, dict):
            params = {}

        lang = command.get("lang") or "en"
        dry_run = os.getenv("SOUNDOS_DRY_RUN") == "1"

        # Direct approval enforcement for dangerous commands (Slide 7 & 9)
        # Bypassed if in dry-run mode or explicitly approved
        if intent in ("shutdown", "delete_file") and not dry_run:
            if not command.get("approved"):
                msg = "Direct approval required for dangerous action." if lang == "en" else "يتطلب هذا الإجراء موافقة صريحة للأمان."
                return {"success": False, "message": msg}

        handler = DISPATCH_TABLE.get(intent)
        if not handler:
            msg = f"Unknown or unsupported intent: '{intent}'" if lang == "en" else f"أمر غير مدعوم أو غير معروف: '{intent}'"
            return {"success": False, "message": msg}

        success, message = handler(params, lang, dry_run)
        return {"success": bool(success), "message": message}

    except Exception as exc:
        # Guarantee: Never crash or raise an unhandled exception
        logger.exception("Unexpected error in execute")
        lang = "en"
        if isinstance(command, dict) and command.get("lang"):
            lang = str(command["lang"])
        err_msg = f"Execution error: {exc}" if lang == "en" else f"خطأ في التنفيذ: {exc}"
        return {"success": False, "message": err_msg}
    finally:
        elapsed = time.monotonic() - t0
        intent_label = command.get("intent", "?") if isinstance(command, dict) else "?"
        logger.debug("execute(%s) took %.3f s", intent_label, elapsed)
        if elapsed > _MAX_EXECUTION_SECS:
            logger.warning(
                "execute(%s) exceeded 1 s target: %.3f s",
                intent_label, elapsed,
            )
