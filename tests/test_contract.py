"""Every module's output must match CONTRACT.md. Works on stubs and on real code (owner: Kareem)."""
from audio import record_utterance
from executor import execute
from intent_parser import parse
from safety import check
from stt import transcribe


def test_pipeline_shapes():
    stt = transcribe(record_utterance())
    assert {"text", "lang", "confidence"} <= set(stt)
    parsed = parse(stt["text"])
    assert set(parsed) == {"intent", "params", "lang", "raw_text"}
    verdict = check(parsed)
    assert verdict["decision"] in {"allow", "confirm", "block"} and isinstance(verdict["message"], str)
    result = execute(parsed)
    assert set(result) == {"success", "message"} and isinstance(result["success"], bool)


def test_dangerous_needs_confirmation():
    for text in ("shut down", "delete file a.txt"):
        assert check(parse(text))["decision"] in {"confirm", "block"}


def test_unknown_is_blocked():
    assert check(parse("blah blah"))["decision"] == "block"
