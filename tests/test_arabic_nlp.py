"""Arabic NLP quality tests: spelling normalization, STT-typo repair (fuzzy pass), dialect words.
No microphone and no model needed.   Run: pytest -q tests/test_arabic_nlp.py
"""
import time

import pytest

from intent_parser import parse, parse_yes_no
from intent_parser.normalize import normalize as N


# --------------------------------------------------------------- normalize
@pytest.mark.parametrize("raw,want", [
    ("أَطْفِئ الشَّاشَةَ، ٣ مرّات!", "اطفي الشاشه 3 مرات"),
    ("افتح\u200fالمتصفح", "افتحالمتصفح"),            # RLM is deleted, a word is not cut in two
    ("عاااالي الصوت اوووي", "عالي الصوت اوي"),         # stretched letters
    ("مرة", "مره"),                                    # a normal word is untouched
    ("کروم", "كروم"),                                  # Persian kaf
    ("ڤي ال سي", "في ال سي"),                          # ڤ -> ف
    ("افتح notes.txt", "افتح notes.txt"),              # file names survive
    ("", ""),
])
def test_normalize(raw, want):
    assert N(raw) == want


def test_normalize_keeps_digits_after_stretch_rule():
    assert N("الصوت 1000") == "الصوت 1000"            # 000 is NOT an Arabic stretch


# ------------------------------------------------- what whisper really wrote
# Seen by running faster-whisper (tiny / base / small, int8) on stt/ar_open.wav ("افتح المتصفح").
@pytest.mark.parametrize("heard", [
    "افتح المتصفح، افتح المتصفح،",   # tiny, with the prompt
    "افتح المبصف",                    # tiny, no prompt
    "افتح لما تصف",                   # base, no prompt
    "افتح المتصف",                    # small, no prompt
    "إفتح المبصف",
])
def test_real_whisper_outputs_for_open_browser(heard):
    out = parse(heard)
    assert (out["intent"], out["params"]) == ("open_app", {"app": "firefox"})


# ------------------------------------------------------------ fuzzy repair
@pytest.mark.parametrize("phrase,intent,params", [
    ("افتح الكرم", "open_app", {"app": "chrome"}),
    ("افتح الكالكوليتير", "open_app", {"app": "calculator"}),
    ("اقفل التيرمنل", "close_app", {"app": "terminal"}),
    ("افتح مدير الملقات", "open_app", {"app": "files"}),
    ("open the brouser", "open_app", {"app": "firefox"}),
    ("close firefx", "close_app", {"app": "firefox"}),
    ("open calculater", "open_app", {"app": "calculator"}),
])
def test_fuzzy_repairs_spelling(phrase, intent, params):
    out = parse(phrase)
    assert (out["intent"], out["params"]) == (intent, params)


def test_fuzzy_never_changes_a_sentence_the_rules_already_understand():
    # exact rule wins; the fuzzy pass only runs on "unknown"
    assert parse("افتح كروم")["params"] == {"app": "chrome"}
    assert parse("ابحث عن فايرفكس")["intent"] == "web_search"


# Everyday sentences that are NOT commands. A false positive here = the PC does something unasked.
NOT_COMMANDS = [
    "الساعه كام", "احكيلي نكته", "عامل ايه", "ايه الاخبار", "افتح الباب", "افتح الحساب", "افتح الشباك",
    "اقفل الباب", "اقفل الشباك", "اقفل النور", "شكرا ليك", "صباح الخير", "انا جعان", "هو فين",
    "what time is it", "tell me a joke", "open the door", "close the window", "how are you",
    "good morning", "thank you", "where is my phone", "what is the capital of france",
]


@pytest.mark.parametrize("phrase", NOT_COMMANDS)
def test_no_false_positives(phrase):
    assert parse(phrase)["intent"] == "unknown"


@pytest.mark.parametrize("phrase", ["اطفي الجهار", "اقفل الجهار", "اطفي الجهز", "shut dwn", "امسح ملف", "امسح الملف"])
def test_misspelled_dangerous_command_is_never_executed(phrase):
    """A misheard word must NOT shut the computer down / delete a file. Exact rules only."""
    assert parse(phrase)["intent"] == "unknown"


def test_exact_dangerous_commands_still_work():
    assert parse("اقفل الجهاز")["intent"] == "shutdown"
    assert parse("اطفاء الجهاز")["intent"] == "shutdown"
    assert parse("امسح ملف test.txt")["intent"] == "delete_file"


def test_fuzzy_can_be_switched_off(monkeypatch):
    assert parse("open the brouser")["intent"] == "open_app"
    monkeypatch.setenv("SOUNDOS_FUZZY", "0")
    assert parse("open the brouser")["intent"] == "unknown"
    assert parse("افتح فايرفوكس")["intent"] == "open_app"       # exact rules are not affected


def test_fuzzy_module_is_importable():
    # rules.parse hides fuzzy errors on purpose (it must never raise), so guard the import here
    import intent_parser.fuzzy as fuzzy
    words, aliases = fuzzy._tables()
    assert "متصفح" in words and aliases["متصفح"] == "firefox"


def test_fuzzy_is_fast_enough():
    """CONTRACT section 3 rule 7: the parser must stay under 50 ms (worst case = unknown sentence)."""
    parse("الساعه كام")                                          # warm the vocabulary cache
    t = time.perf_counter()
    for phrase in NOT_COMMANDS:
        parse(phrase)
    per_call_ms = (time.perf_counter() - t) * 1000 / len(NOT_COMMANDS)
    assert per_call_ms < 50, f"{per_call_ms:.1f} ms per call"


def test_parser_never_raises_on_garbage():
    for junk in ["", "   ", None, 123, "؟؟؟", "\u200f\u200f", "a" * 5000, "افتح " + "ب" * 3000]:
        out = parse(junk)
        assert set(out) == {"intent", "params", "lang", "raw_text"}


# ------------------------------------------------------------ dialect words
@pytest.mark.parametrize("phrase,intent", [
    ("يلا افتح المتصفح بقى", "open_app"),
    ("طيب اقفل الكروم", "close_app"),
    ("اقفل تطبيق", "close_app"),
    ("اقفل التطبيق", "close_app"),
    ("اقفلي التطبيق", "close_app"),
    ("اقفل البرنامج", "close_app"),
    ("اقفلي المتصفح", "close_app"),
    ("طفي المتصفح", "close_app"),
    ("اقفل تطبيق المتصفح", "close_app"),
    ("اقفلي تطبيق كروم", "close_app"),
    ("اوطي الصوت شوية", "volume_down"),
    ("كتر الصوت", "volume_up"),
    ("نقص الصوت", "volume_down"),
    ("اعرض الصور", "open_folder"),
    ("اظهر سطح المكتب", "open_folder"),
    ("ايقاف تشغيل الجهاز", "shutdown"),
])
def test_egyptian_dialect(phrase, intent):
    assert parse(phrase)["intent"] == intent


@pytest.mark.parametrize("answer,want", [
    ("ايوه", True), ("اكيد", True), ("طبعا", True), ("نفذ", True), ("yes", True),
    ("لا", False), ("الغي", False), ("مش عايز", False), ("متعملش", False), ("no", False),
    ("لا تمام", None),        # both words -> unclear -> the caller cancels (safe default)
    ("ممكن", None), ("", None), ("banana", None),
])
def test_yes_no_dialect(answer, want):
    assert parse_yes_no(answer) is want
