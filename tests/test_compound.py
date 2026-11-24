"""Unit tests for compound command splitting and execution (Arabic & English)."""

import pytest
from intent_parser import parse, split_compound, parse_pipeline


def test_arabic_compound_actions():
    cases = [
        ("افتح المتصفح وعلي الصوت", ["افتح المتصفح", "علي الصوت"]),
        ("افتح فايرفوكس وافتح الاله الحاسبه", ["افتح فايرفوكس", "افتح الاله الحاسبه"]),
        ("افتح المتصفح وبعدين شغل موسيقى", ["افتح المتصفح", "شغل موسيقى"]),
        ("علي الصوت ووطي السطوع", ["علي الصوت", "وطي السطوع"]),
        ("اكتم الصوت واقفل الكروم", ["اكتم الصوت", "اقفل الكروم"]),
        ("افتح الترمينال ثم افتح الملفات", ["افتح الترمينال", "افتح الملفات"]),
        ("اقفل المتصفح، اعلي السطوع", ["اقفل المتصفح", "اعلي السطوع"]),
        ("اقفل الملفات، اعلي السطوع،", ["اقفل الملفات", "اعلي السطوع"]),
        ("افتح المتصفح، وعلي الصوت", ["افتح المتصفح", "علي الصوت"]),
    ]
    for text, expected in cases:
        parts = split_compound(text)
        assert parts == expected, f"Failed on {text}: got {parts}"


def test_english_compound_actions():
    cases = [
        ("open the browser and turn up the volume", ["open the browser", "turn up the volume"]),
        ("open terminal and open calculator", ["open terminal", "open calculator"]),
        ("mute and close firefox", ["mute", "close firefox"]),
        ("open files and then play music", ["open files", "play music"]),
        ("turn down brightness and increase volume", ["turn down brightness", "increase volume"]),
        ("open the browser, turn up volume", ["open the browser", "turn up volume"]),
    ]
    for text, expected in cases:
        parts = split_compound(text)
        assert parts == expected, f"Failed on {text}: got {parts}"


def test_search_and_query_never_split():
    # Queries with conjunctions must NOT be broken into subcommands
    queries = [
        "ابحث عن القطط والكلاب",
        "search for Tom and Jerry",
        "دور على توم وجيري",
        "ابحث عن احمد ومحمد",
    ]
    for q in queries:
        parts = split_compound(q)
        assert parts == [q], f"Query was incorrectly split: {q} -> {parts}"
        parsed = parse(q)
        assert parsed["intent"] == "web_search"


def test_single_commands_remain_intact():
    singles = [
        "افتح المتصفح",
        "علي الصوت",
        "open the browser",
        "mute",
        "اقفل الجهاز",
    ]
    for s in singles:
        parts = split_compound(s)
        assert parts == [s]


def test_parse_pipeline():
    res = parse_pipeline("افتح المتصفح وعلي الصوت")
    assert len(res) == 2
    assert res[0]["intent"] == "open_app"
    assert res[0]["params"]["app"] == "firefox"
    assert res[1]["intent"] == "volume_up"
