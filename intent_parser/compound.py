"""
intent_parser/compound.py - Split compound / multi-action utterances into distinct commands.

Examples:
    "افتح المتصفح وعلي الصوت" -> ["افتح المتصفح", "علي الصوت"]
    "افتح فايرفوكس وافتح الاله الحاسبه" -> ["افتح فايرفوكس", "افتح الاله الحاسبه"]
    "open the browser and turn up the volume" -> ["open the browser", "turn up the volume"]
    "mute and close firefox" -> ["mute", "close firefox"]
    "ابحث عن توم وجيري" -> ["ابحث عن توم وجيري"] (query not broken)
"""

import re
from typing import List


# Conjunction patterns ordered from most explicit to least explicit
_CONJUNCTION_PATTERNS = [
    r"\s+(?:ثم|وبعدين|بعدين|وبعدها|بعدها|وكمان|كمان|وبعد ذلك)\s+",
    r"\s+(?:and then|then|and also)\s+",
    r"\s+و(?=[\u0621-\u064A])",  # Arabic 'و' attached to following word (e.g. وعلي, وافتح)
    r"\s+و\s+",                  # Standalone Arabic 'و'
    r"\s+and\s+",                # English 'and'
]


def split_compound(text: str) -> List[str]:
    """
    Split a sentence into individual command strings if each piece parses to a known intent.
    Never raises. Returns [text] if no valid split is found.
    """
    try:
        if not isinstance(text, str):
            return [""]
        clean = text.strip()
        if not clean:
            return [""]

        # Local import to avoid circular dependency
        from .rules import parse

        for pat in _CONJUNCTION_PATTERNS:
            parts = re.split(pat, clean)
            if len(parts) > 1:
                subparts = [p.strip() for p in parts if p.strip()]
                if len(subparts) > 1:
                    # Recursively verify each subpart
                    valid = True
                    collected: List[str] = []
                    for sp in subparts:
                        # If a subpart itself contains further conjunctions, resolve it
                        sub_resolved = split_compound(sp) if any(re.search(p, sp) for p in _CONJUNCTION_PATTERNS) else [sp]
                        for item in sub_resolved:
                            p_res = parse(item)
                            if p_res.get("intent") == "unknown":
                                valid = False
                                break
                            collected.append(item)
                        if not valid:
                            break
                    if valid and len(collected) > 1:
                        return collected
        return [clean]
    except Exception:
        return [text] if isinstance(text, str) else [""]


def parse_pipeline(text: str, lang: str = None) -> List[dict]:
    """
    Parse one or more commands in text into a list of parsed intent dicts.
    Returns at least one element (even if unknown).
    """
    try:
        from .rules import parse
        parts = split_compound(text)
        if not parts:
            return [parse(text, lang=lang)]
        return [parse(p, lang=lang) for p in parts]
    except Exception:
        from .rules import parse
        return [parse(text, lang=lang)]
