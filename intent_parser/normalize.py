"""Arabic/English text normalization. Run BEFORE any rule so each word is written once.

What it folds:
  - diacritics (tashkeel) and tatweel:   عَلِّي  -> علي
  - alef variants  أ إ آ ٱ  ->  ا
  - taa marbuta    ة -> ه        (الشاشة -> الشاشه)
  - alef maqsura   ى -> ي        (على -> علي)
  - hamza on waw/yaa  ؤ -> و , ئ -> ي
  - Persian/Urdu/extended letters Whisper sometimes emits: ک -> ك , ی -> ي ,
    ڤ -> ف , پ -> ب , گ -> ج , ھ -> ه
  - invisible direction marks (RLM/LRM/ZWNJ...) are DELETED, not replaced by a space,
    so a word is never cut in the middle
  - stretched letters:  عاااالي -> عالي   (3+ repeats -> 1; a normal double letter is kept)
  - Arabic-Indic digits -> 0-9, lowercase Latin, punctuation -> space
Dots, dashes and underscores are kept so file names like notes.txt survive.
"""
import re
import unicodedata

_MARKS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")  # tashkeel + tatweel
_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")      # ZW*, LRM/RLM, bidi controls, BOM
_STRETCH = re.compile(r"([\u0621-\u064A])\1{2,}")                              # 3+ same Arabic letter in a row
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
                          "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي",
                          "ک": "ك", "ی": "ي", "ې": "ي", "ڤ": "ف", "پ": "ب",
                          "گ": "ج", "ھ": "ه", "ە": "ه"})


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    t = _INVISIBLE.sub("", t)
    t = _MARKS.sub("", t).translate(_DIGITS).translate(_LETTERS)
    t = _STRETCH.sub(r"\1", t)
    t = re.sub(r"[^\w\s.\-_/]", " ", t)            # drop punctuation (؟ ، ! , ' ...)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .-_/")


if __name__ == "__main__":
    print(normalize("أَطْفِئ الشَّاشَةَ، ٣ مرّات!"))   # -> اطفي الشاشه 3 مرات
