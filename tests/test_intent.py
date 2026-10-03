import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from intent import parse_intent
from execution import run_intent


def test_basic_phrases():
    assert parse_intent("افتح المتصفح")["intent"] == "open_browser"
    assert parse_intent("شغّل المتصفح")["intent"] == "open_browser"
    assert parse_intent("ارفع الصوت")["intent"] == "volume_up"
    assert parse_intent("علّي الصوت")["intent"] == "volume_up"
    assert parse_intent("اطفي الجهاز")["intent"] == "shutdown"


def test_tashkeel_and_hamza():
    assert parse_intent("إفْتَحْ المُتَصَفِّحَ")["intent"] == "open_browser"


def test_unknown_not_guessed():
    assert parse_intent("كلام عشوائي")["intent"] == "unknown"
    assert parse_intent("")["intent"] == "unknown"
    assert parse_intent("اقفل المتصفح")["intent"] == "unknown"


def test_shutdown_needs_confirm():
    assert run_intent("shutdown", confirmed=False, dry_run=True)["ok"] is False
    assert run_intent("shutdown", confirmed=True, dry_run=True)["ok"] is True


def test_not_allowed_rejected():
    assert run_intent("rm -rf /", dry_run=True)["ok"] is False
