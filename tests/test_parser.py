"""Runs every row of testdata/phrases.csv through the parser (owner: Kareem).
Add rows to the CSV - no code change needed.  Run: pytest -q"""
import csv
import pathlib

import pytest

from intent_parser import parse
from intent_parser.normalize import normalize as N

CSV = pathlib.Path(__file__).resolve().parent.parent / "testdata" / "phrases.csv"
ROWS = list(csv.DictReader(open(CSV, encoding="utf-8")))
EXACT = {"app"}                   # must match exactly; folder (if canonical) too; free text (query/name/other folder) must contain
CANONICAL_FOLDERS = {"home", "downloads", "documents", "desktop", "pictures", "music", "videos"}


def check_row(row):
    """Return '' if the parser output matches the CSV row, else a short reason."""
    out = parse(row["phrase"])
    if set(out) != {"intent", "params", "lang", "raw_text"}:
        return f"bad keys {sorted(out)}"
    if out["raw_text"] != row["phrase"]:
        return "raw_text changed"
    if out["intent"] != row["intent"]:
        return f"intent {out['intent']} != {row['intent']}"
    if out["lang"] != row["lang"]:
        return f"lang {out['lang']} != {row['lang']}"
    want = dict(p.split("=", 1) for p in row["params"].split(";") if p)
    for k, v in want.items():
        got = N(str(out["params"].get(k, "")))
        exact = k in EXACT or (k == "folder" and v in CANONICAL_FOLDERS)
        if (got != N(v)) if exact else (N(v) not in got):
            return f"param {k}: got {out['params'].get(k)!r}, want {v!r}"
    if not want and row["intent"] in {"open_app", "close_app", "open_folder", "delete_file"}:
        return "row has no expected params"
    return ""


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_phrase(row):
    assert check_row(row) == ""


def test_dangerous_never_from_llm():
    from intent_parser.llm_fallback import _validate
    assert _validate({"intent": "shutdown", "params": {}}) is None
    assert _validate({"intent": "delete_file", "params": {"name": "x"}}) is None
    assert _validate({"intent": "open_app", "params": {"app": "firefox"}}) == ("open_app", {"app": "firefox"})
    assert _validate({"intent": "open_app", "params": {"app": "rm -rf"}}) is None


def test_yes_no():
    from intent_parser import parse_yes_no
    assert parse_yes_no("ايوه") is True and parse_yes_no("yes please") is True
    assert parse_yes_no("لا") is False and parse_yes_no("no") is False
    assert parse_yes_no("banana") is None
