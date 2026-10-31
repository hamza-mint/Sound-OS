"""STUB - Yassin replaces the body, keeps the signature (see CONTRACT.md)."""
import os


def execute(parsed: dict) -> dict:
    """parsed -> {"success": bool, "message": str}. Message is in parsed["lang"].
    Must honour SOUNDOS_DRY_RUN=1 (log only, change nothing). Never raise."""
    dry = os.getenv("SOUNDOS_DRY_RUN") == "1"
    print(f"[executor{' DRY-RUN' if dry else ''}] {parsed['intent']} {parsed['params']}")
    return {"success": True, "message": "Done." if parsed["lang"] == "en" else "تم."}
