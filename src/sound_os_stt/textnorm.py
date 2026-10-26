"""textnorm.py - text normalization shared by the STT evaluation and the intent parser.

Whisper may spell the same Arabic word differently between runs
(إفتح / افتح). Normalizing both sides makes them comparable.
It does NOT fix missing/wrong letters (المتصف vs المتصفح): that is the
job of fuzzy matching in the intent parser.
"""
import re

_DIAC = re.compile(r"[\u064B-\u0652\u0640]")            # tashkeel + tatweel
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")      # Arabic-Indic -> ASCII digits


def normalize(text: str) -> str:
    t = (text or "").lower().translate(_DIGITS)
    t = _DIAC.sub("", t)                    # remove diacritics
    t = re.sub("[أإآ]", "ا", t)             # unify alef forms
    t = t.replace("ى", "ي").replace("ة", "ه")   # unify ya / ta-marbuta
    t = re.sub(r"[^\w\s]", " ", t)          # drop punctuation (، ؟ . ,)
    return re.sub(r"\s+", " ", t).strip()
