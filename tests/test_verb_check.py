"""verb_check: is the heard افتح / اقفل backed by the prompt-free decode?
The texts below are REAL prompt-free outputs (base model) of the user's own recordings."""
import pytest

from intent_parser.verb_check import verb_doubt, open_evidence, command_text, APP_NOUN

# clearly said "افتح المتصفح": the "ت" of افتح is audible
OPEN_LIKE = ["إفتهم صفح", "إبتهم الثفر"]
# said "اقفل المتصفح" (the wake decode of the first one correctly wrote اقفل المتصفح); no "ت" after "اف"
CLOSE_LIKE = ["ايه فرمتصف", "ايه فرمت صفح", "ايفر من صفح", "اي فرمت الثفر"]


@pytest.mark.parametrize("probe", OPEN_LIKE)
def test_audio_that_sounds_like_open_backs_the_open_verb(probe):
    assert open_evidence(probe, "firefox") >= 0.08
    assert verb_doubt("open_app", "firefox", probe) is False


@pytest.mark.parametrize("probe", CLOSE_LIKE)
def test_audio_without_evidence_for_open_makes_open_doubtful(probe):
    assert verb_doubt("open_app", "firefox", probe) is True


def test_a_clear_open_probe_makes_a_heard_close_doubtful():
    assert verb_doubt("close_app", "firefox", "افتح المتصفح") is True
    assert verb_doubt("close_app", "firefox", "اقفل المتصفح") is False
    assert verb_doubt("close_app", "firefox", "ايه فرمت صفح") is False          # neutral audio: believe the heard "close"


def test_an_exact_prompt_free_text_is_trusted():
    assert verb_doubt("open_app", "firefox", "افتح المتصفح") is False
    assert verb_doubt("open_app", "files", "افتح الملفات") is False
    assert verb_doubt("open_app", "firefox", "اقفل المتصفح") is True


def test_unknown_apps_other_intents_and_empty_text_never_raise():
    assert verb_doubt("open_app", "unknown-app", "x") is False
    assert verb_doubt("volume_up", "firefox", "x") is False
    assert open_evidence("", "firefox") == 0.0
    assert verb_doubt("open_app", "firefox", "") is True            # nothing heard without the prompt: unclear


def test_command_text_is_clean_arabic():
    assert command_text("close_app", "firefox") == "اقفل المتصفح"
    assert command_text("open_app", "files") == "افتح الملفات"
    assert set(APP_NOUN) >= {"firefox", "chrome", "terminal", "calculator", "files"}


def test_the_clean_commands_parse_back_to_the_same_intent():
    from intent_parser import parse
    for app in APP_NOUN:
        for intent in ("open_app", "close_app"):
            out = parse(command_text(intent, app))
            assert (out["intent"], out["params"]) == (intent, {"app": app}), (intent, app, out)
