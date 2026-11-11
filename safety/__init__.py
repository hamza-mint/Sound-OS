"""STUB - Antonius replaces the body, keeps the signature (see CONTRACT.md)."""

DANGEROUS = {"shutdown", "delete_file"}


def check(parsed: dict) -> dict:
    """parsed (parser output) -> {"decision": "allow" | "confirm" | "block", "message": str}.
    The message is spoken to the user, in parsed["lang"]."""
    lang = parsed["lang"]
    if parsed["intent"] == "unknown":
        return {"decision": "block", "message": "I did not understand." if lang == "en" else "مفهمتش."}
    if parsed["intent"] in DANGEROUS:
        return {"decision": "confirm", "message": "Are you sure?" if lang == "en" else "متأكد؟"}
    return {"decision": "allow", "message": ""}
