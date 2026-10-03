"""دور 3: NLU — بياخد نص ويطلّع اسم الأمر.

بياخد : نص (مثلًا "افتح المتصفح")
بيطلّع: {"intent": "open_browser", "args": {}}
        أو {"intent": "unknown", "args": {}} لو مش فاهم (بدل ما يخمّن).
"""
import re
from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz  # مطابقة تقريبية (اختياري)
except ImportError:  # لو المكتبة مش متنصّبة نستخدم difflib الجاهزة في بايثون
    fuzz = None

# الجمل المقبولة لكل أمر. أضف مرادفات هنا.
PHRASES = {
    "open_browser": ["افتح المتصفح", "شغل المتصفح", "افتح متصفح", "open browser"],
    "volume_up": ["ارفع الصوت", "علي الصوت", "زود الصوت", "volume up"],
    "shutdown": ["اطفي الجهاز", "اقفل الجهاز", "اطفي الكمبيوتر", "shutdown"],
}

# أقل نسبة تشابه (0-100). عالية عن قصد: "اقفل المتصفح" مينفعش تتفهم "افتح المتصفح".
CUTOFF = 90


def normalize_arabic(text: str) -> str:
    """تنظيف النص العربي: تشكيل، همزات، ة/ه، ى/ي، مسافات."""
    text = text.lower()
    text = re.sub(r"[\u064B-\u0652\u0640]", "", text)  # التشكيل والتطويل
    text = re.sub(r"[أإآ]", "ا", text)
    text = text.replace("ة", "ه").replace("ى", "ي")
    text = re.sub(r"[^\w\s]", " ", text)  # علامات الترقيم
    return re.sub(r"\s+", " ", text).strip()


def _score(a: str, b: str) -> float:
    if fuzz is not None:
        return fuzz.ratio(a, b)
    return SequenceMatcher(None, a, b).ratio() * 100


# جدول بحث جاهز بعد التنظيف
_TABLE = [(normalize_arabic(p), intent) for intent, ps in PHRASES.items() for p in ps]


def parse_intent(text: str) -> dict:
    clean = normalize_arabic(text or "")
    if not clean:
        return {"intent": "unknown", "args": {}}
    best_intent, best_score = "unknown", 0.0
    for phrase, intent in _TABLE:
        s = _score(clean, phrase)
        if s > best_score:
            best_intent, best_score = intent, s
    if best_score >= CUTOFF:
        return {"intent": best_intent, "args": {}}
    return {"intent": "unknown", "args": {}}


if __name__ == "__main__":
    import sys
    sample = " ".join(sys.argv[1:]) or "افتح المتصفح"
    print(parse_intent(sample))
