"""
Sound OS - Safety Layer Module (Owner: Antonius)
Interface Contract: CONTRACT.md v1.0
Entry point: check(parsed: dict) -> dict
Output: {"decision": "allow" | "confirm" | "block", "message": str}
"""
from typing import Dict, Any, Optional, Callable
from .safety_layer import SafetyLayer, YES_WORDS, NO_WORDS

DANGEROUS = {"shutdown", "delete_file"}

_safety_instance: Optional[SafetyLayer] = None


def get_safety_layer() -> SafetyLayer:
    """Singleton getter for the SafetyLayer instance."""
    global _safety_instance
    if _safety_instance is None:
        _safety_instance = SafetyLayer()
    return _safety_instance


def check(
    parsed: Dict[str, Any],
    speak_fn: Optional[Callable[[str, str], None]] = None,
    update_state_fn: Optional[Callable[[str, Optional[str]], None]] = None,
    listen_yes_no_fn: Optional[Callable[[float], Optional[str]]] = None,
) -> Dict[str, Any]:
    """
    Evaluates parsed intent against the allowlist and safety rules.
    Fulfills CONTRACT.md specification:
        check(parsed) -> {"decision": "allow" | "confirm" | "block", "message": str}
    Never raises exceptions.
    """
    try:
        safety = get_safety_layer()
        return safety.check(
            parsed_command=parsed,
            speak_fn=speak_fn,
            update_state_fn=update_state_fn,
            listen_yes_no_fn=listen_yes_no_fn,
        )
    except Exception as exc:
        lang = parsed.get("lang", "en") if isinstance(parsed, dict) else "en"
        msg = f"Safety check error: {exc}" if lang == "en" else f"خطأ في فحص الأمان: {exc}"
        return {
            "decision": "block",
            "message": msg,
            "approved": False,
            "reason": str(exc),
            "command": parsed if isinstance(parsed, dict) else {},
        }


__all__ = ["check", "SafetyLayer", "DANGEROUS", "YES_WORDS", "NO_WORDS", "get_safety_layer"]
