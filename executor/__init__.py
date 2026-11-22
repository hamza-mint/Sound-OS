"""
Sound OS - Command Executor Module (Owner: Yassin)
Interface Contract: CONTRACT.md v1.0
Entry point: execute(command: dict) -> dict
Output: {"success": bool, "message": str}

v3 Hardening: Strict param validation, threading-based timeout enforcement.
"""
import json
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Dict, Any, Tuple

from executor import actions

logger = logging.getLogger("soundos.executor")

# CONTRACT.md §7: executor must complete under 1 second
_MAX_EXECUTION_SECS = 1.0

CONFIG_PATH = Path(__file__).parent / "apps.json"

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

    # Fallback to direct app name as binary if no alias matched
    return app_clean, {
        "cmd": [app_clean],
        "process": app_clean,
        "aliases": [app_clean]
    }


def _resolve_folder(folder_name: str) -> str:
    """Maps folder name or alias to directory path string."""
    folder_clean = (folder_name or "").strip().lower()
    folders = APP_CONFIG.get("folders", {})
    if folder_clean in folders:
        return folders[folder_clean]
    # Default to home subdirectory if custom name
    return f"~/{folder_name}" if folder_name else "~"


# ---------------------------------------------------------------------------
# v3: Strict per-intent parameter validation
# ---------------------------------------------------------------------------
def _validate_params(intent: str, params: dict, lang: str) -> Tuple[bool, str]:
    """
    Validate params per intent rules. Returns (is_valid, error_message).
    On success: (True, ""). On failure: (False, localised_error).
    """
    if not isinstance(params, dict):
        return False, ("Invalid parameters: must be an object."
                       if lang == "en" else "معاملات غير صالحة: يجب أن تكون كائناً.")

    def _require_str(field: str, allow_empty: bool = False) -> Tuple[bool, str]:
        val = params.get(field)
        if val is None and allow_empty:
            return True, ""  # optional field, absent is fine
        if not isinstance(val, str):
            return False, (f"Parameter '{field}' must be a text string."
                           if lang == "en"
                           else f"المعامل '{field}' يجب أن يكون نصاً.")
        if not allow_empty and not val.strip():
            return False, (f"Parameter '{field}' must not be empty."
                           if lang == "en"
                           else f"المعامل '{field}' لا يجب أن يكون فارغاً.")
        return True, ""

    def _no_path_traversal(field: str) -> Tuple[bool, str]:
        val = params.get(field)
        if val is None:
            return True, ""
        if not isinstance(val, str):
            return False, (f"Parameter '{field}' must be a text string."
                           if lang == "en"
                           else f"المعامل '{field}' يجب أن يكون نصاً.")
        if "/" in val or "\\" in val or ".." in val or os.path.isabs(val):
            return False, ("Invalid filename: path traversal is not permitted."
                           if lang == "en"
                           else "اسم ملف غير صالح: غير مسموح بالمسارات المتداخلة.")
        return True, ""

    def _optional_str(field: str) -> Tuple[bool, str]:
        val = params.get(field)
        if val is None:
            return True, ""
        if not isinstance(val, str):
            return False, (f"Parameter '{field}' must be a text string."
                           if lang == "en"
                           else f"المعامل '{field}' يجب أن يكون نصاً.")
        return True, ""

    rules = {
        "open_app":    [lambda: _require_str("app")],
        "close_app":   [lambda: _optional_str("app")],
        "web_search":  [lambda: _require_str("query")],
        "create_file": [lambda: _optional_str("name"),
                        lambda: _no_path_traversal("name")],
        "delete_file": [lambda: _require_str("name"),
                        lambda: _no_path_traversal("name")],
        "open_folder": [lambda: _optional_str("folder")],
        "play_media":  [lambda: _optional_str("query")],
        "send_message": [lambda: _optional_str("recipient"),
                         lambda: _optional_str("message")],
    }

    checks = rules.get(intent, [])
    for check in checks:
        ok, msg = check()
        if not ok:
            return False, msg

    return True, ""


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
        msg = "No application specified." if lang == "en" else "لم يتم تحديد التطبيق."
        return False, msg

    app_info = _find_app(app_name)
    if not app_info:
        msg = f"Unknown application: '{app_name}'" if lang == "en" else f"تطبيق غير معروف: '{app_name}'"
        return False, msg

    canonical, cfg = app_info
    if dry_run:
        msg = f"[DRY-RUN] Closing {canonical}" if lang == "en" else f"[تجربة] إغلاق تطبيق {canonical}"
        return True, msg

    ok, err = actions.terminate_app(cfg)
    if ok:
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
    "shutdown": _handle_shutdown,
}


def execute(command: dict) -> dict:
    """
    Main entry point for command execution.
    Complies with CONTRACT.md:
    - Never raises exceptions.
    - Honours SOUNDOS_DRY_RUN=1 environment variable.
    - Returns format: {"success": bool, "message": str} in the requested lang.
    - v3: Strict param validation BEFORE dispatch.
    - v3: Hard timeout enforcement via threading (1s max).
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

        handler = DISPATCH_TABLE.get(intent)
        if not handler:
            msg = f"Unknown or unsupported intent: '{intent}'" if lang == "en" else f"أمر غير مدعوم أو غير معروف: '{intent}'"
            return {"success": False, "message": msg}

        # --- v3: Strict per-intent param validation ---
        valid, err_msg = _validate_params(intent, params, lang)
        if not valid:
            return {"success": False, "message": err_msg}

        # --- v3: Execute handler with hard timeout via threading ---
        result_queue: queue.Queue = queue.Queue()

        def _worker():
            try:
                success, message = handler(params, lang, dry_run)
                result_queue.put({"success": bool(success), "message": message})
            except Exception as exc:
                err = f"Execution error: {exc}" if lang == "en" else f"خطأ في التنفيذ: {exc}"
                result_queue.put({"success": False, "message": err})

        worker_thread = threading.Thread(target=_worker, daemon=True)
        worker_thread.start()

        # Wait for remaining budget (never more than 1s total)
        elapsed_so_far = time.monotonic() - t0
        budget = max(0.01, _MAX_EXECUTION_SECS - elapsed_so_far)
        worker_thread.join(timeout=budget)

        if not result_queue.empty():
            return result_queue.get_nowait()

        # Timeout: handler didn't finish in time
        timeout_msg = ("Command execution timed out."
                       if lang == "en"
                       else "انتهت مهلة تنفيذ الأمر.")
        return {"success": False, "message": timeout_msg}

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
