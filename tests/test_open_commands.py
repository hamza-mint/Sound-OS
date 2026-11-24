"""'open downloads', 'open documents', 'create file notes.txt', 'open settings'.
The typed commands always worked (parser + executor). By VOICE they failed because Whisper tiny writes
'open downloads' as 'Hoping down loads' / 'Oben downloads' (seen in a real session log).
Run: pytest -q tests/test_open_commands.py
"""
import pytest

from intent_parser import parse, clear_fuzzy_cache


@pytest.mark.parametrize("phrase,folder", [
    ("open downloads", "downloads"), ("open the downloads", "downloads"), ("opening downloads", "downloads"),
    ("hoping down loads", "downloads"), ("oben downloads", "downloads"), ("open down loads", "downloads"),
    ("downloads", "downloads"), ("down loads", "downloads"), ("افتح التحميلات", "downloads"),
    ("افتح الداونلودز", "downloads"),
    ("open documents", "documents"), ("open my documents", "documents"), ("opening documents", "documents"),
    ("obing documents", "documents"), ("oben document", "documents"), ("documents", "documents"),
    ("افتح المستندات", "documents"), ("افتح الدوكيومنتس", "documents"), ("المستندات", "documents"),
])
def test_open_folder_phrases_and_mishearings(phrase, folder):
    out = parse(phrase)
    assert (out["intent"], out["params"]) == ("open_folder", {"folder": folder})


@pytest.mark.parametrize("phrase", ["open settings", "opening settings", "oben settings", "hoping settings",
                                    "settings", "افتح الاعدادات", "افتح الإعدادات", "open system settings"])
def test_open_settings(phrase):
    out = parse(phrase)
    assert (out["intent"], out["params"]) == ("open_app", {"app": "settings"})


@pytest.mark.parametrize("phrase,name", [
    ("create file notes.txt", "notes.txt"), ("create file notes dot txt", "notes.txt"),
    ("make a file notes.txt", "notes.txt"), ("new file notes.txt", "notes.txt"),
    ("اعمل ملف notes.txt", "notes.txt"),
])
def test_create_file(phrase, name):
    out = parse(phrase)
    assert (out["intent"], out["params"]) == ("create_file", {"name": name})


@pytest.mark.parametrize("phrase,name", [
    # bare filename with known extension (no "file" word needed)
    ("create hamza.txt", "hamza.txt"),
    ("Create Hamza.dxt", "hamza.txt"),
    ("create script.py", "script.py"),
    ("create readme.md", "readme.md"),
    ("create report.docx", "report.docx"),
    ("create data.csv", "data.csv"),
    ("create main.py", "main.py"),
    ("make todo.txt", "todo.txt"),
    ("new config.json", "config.json"),
    # type keywords → default extension
    ("create excel sheet", "new_file.xlsx"),
    ("excel sheet", "new_file.xlsx"),
    ("create word document", "new_file.docx"),
    ("create python file", "new_file.py"),
    ("create markdown file", "new_file.md"),
    # type keyword + custom name → name.ext ("create <type> file <name>")
    ("create excel sheet budget", "budget.xlsx"),
    ("create excel file budget", "budget.xlsx"),
    ("create word document report", "report.docx"),
    ("create word file report", "report.docx"),
    ("create python file test", "test.py"),
    ("create python file hamza", "hamza.py"),
    ("create txt file hamza", "hamza.txt"),
    ("create text file notes", "notes.txt"),
    ("create text file", "new_file.txt"),
    ("create empty text file", "new_file.txt"),
    ("create markdown file readme", "readme.md"),
    ("create json file config", "config.json"),
    ("create csv file data", "data.csv"),
    ("اعمل ملف نصي hamza", "hamza.txt"),
    # Real-session Whisper mishearings for "create python/word/json file"
    ("قرية بيسون فائل.", "new_file.py"),
    ("قريد بيسون في الحمزة.", "حمزه.py"),
    ("Create BisonFile.", "new_file.py"),
    ("Create by some file,", "new_file.py"),
    ("Create word file, hamzaq.", "hamzaq.docx"),
    ("Create JSON file, hamza.", "hamza.json"),
    ("كريات جيسٌ فائل حمز", "حمز.json"),
    ("كريد بلسن فائل حمصة", "حمصه.py"),
    ("وردفائي الحمزك", "الحمزك.docx"),
    ("كريد باي سنفائل،", "new_file.py"),
    ("Jason Fail Hamzen.", "hamzen.json"),
    # "file.ext" (the word "file" IS the filename) and spoken dot/phonetic variants
    ("create file.txt", "file.txt"),
    ("create file.py", "file.py"),
    ("create file.md", "file.md"),
    ("create file dot py", "file.py"),
    ("create file .py", "file.py"),
    ("create file dot pi", "file.py"),
    ("create file.pi", "file.py"),
    ("create file py", "file.py"),
    ("create file dot md", "file.md"),
    # document/sheet/script as generic FILE word
    ("create document notes.docx", "notes.docx"),
    ("create script test.py", "test.py"),
    # Arabic with type keywords
    ("اعمل ملف اكسل بيانات", "بيانات.xlsx"),
    ("اعمل شيت بيانات", "بيانات.xlsx"),
    ("اعمل ملف بايثون", "new_file.py"),
    # Whisper phonetic variations from real sessions
    ("اعمل الشيط أكسال،", "new_file.xlsx"),
    ("ملي شيط إكسل", "new_file.xlsx"),
    ("امل شد اكسل", "new_file.xlsx"),
    ("ام اللي شد اكسل", "new_file.xlsx"),
    ("شد أكسل،", "new_file.xlsx"),
    ("شيت إكسل", "new_file.xlsx"),
])
def test_create_file_extended(phrase, name):
    out = parse(phrase)
    assert (out["intent"], out["params"]) == ("create_file", {"name": name})


def test_the_new_bare_folder_and_verb_repair_rules_do_not_steal_other_commands():
    assert parse("play music")["intent"] == "play_media"         # not "open the music folder"
    assert parse("انشئ ملفات")["intent"] == "create_file"       # not open_app(files)
    assert parse("open files")["intent"] == "open_app"
    assert parse("volume down")["intent"] == "volume_down"
    assert parse("hoping for the best")["intent"] == "unknown"
    assert parse("opening hours")["intent"] == "unknown"
    assert parse("i am opening a shop")["intent"] == "unknown"


def test_a_mis_heard_open_can_never_close_or_shut_down():
    """The 'open' repair may only open things."""
    for phrase in ["hoping the computer", "oben the device", "obing the system"]:
        assert parse(phrase)["intent"] not in ("shutdown", "close_app", "delete_file", "send_message")


def test_send_message_parameter_extraction_english():
    """send_message should extract recipient and message body when present."""
    # Full command: "send message to john saying hello"
    out = parse("send message to john saying hello")
    assert out["intent"] == "send_message"
    assert out["params"].get("recipient") == "john"
    assert out["params"].get("message") == "hello"

    # With "with text"
    out = parse("send message to alice with text meeting at 5")
    assert out["params"].get("recipient") == "alice"
    assert out["params"].get("message") == "meeting at 5"

    # Body only
    out = parse("send message saying hello world")
    assert "recipient" not in out["params"]
    assert out["params"].get("message") == "hello world"

    # Bare command - empty params allowed
    out = parse("send message")
    assert out["intent"] == "send_message"
    assert out["params"] == {}


def test_send_message_parameter_extraction_arabic():
    """send_message should extract recipient and message in Egyptian Arabic."""
    # "ابعت رسالة لأحمد بتقول السلام عليكم"
    out = parse("ابعت رسالة لاحمد بتقول السلام عليكم")
    assert out["intent"] == "send_message"
    assert out["params"].get("recipient") == "احمد"
    assert out["params"].get("message") == "السلام عليكم"

    # With "الي"
    out = parse("ابعث رسالة الي ساره نصها تعالي")
    assert out["params"].get("recipient") == "ساره"
    assert out["params"].get("message") == "تعالي"

    # Body only "ابعت رسالة بتقول مرحبا"
    out = parse("ارسل رسالة بتقول مرحبا")
    assert "recipient" not in out["params"]
    assert out["params"].get("message") == "مرحبا"

    # Prefixed lam "لحسام بتقول تمام"
    out = parse("ابعت رساله لحسام بتقول تمام")
    assert out["params"].get("recipient") == "حسام"
    assert out["params"].get("message") == "تمام"

    # Bare Arabic
    out = parse("ابعت رسالة")
    assert out["intent"] == "send_message"
    assert out["params"] == {}


def test_clear_fuzzy_cache():
    """clear_fuzzy_cache should invalidate internal caches without error."""
    # Just ensure it's callable and doesn't raise
    clear_fuzzy_cache()
    # Subsequent parse should still work
    out = parse("open downloads")
    assert out["intent"] == "open_folder"
    assert out["params"]["folder"] == "downloads"
