"""STUB - Abram replaces the bodies, keeps the signatures (see CONTRACT.md)."""


def wait_for_wake_word() -> None:
    """Block until the wake word is heard."""
    return None


def record_utterance(max_seconds: float = 6.0) -> str:
    """Record until silence (or max_seconds). Return the path of a 16 kHz mono WAV."""
    return "tests/fixtures/sample.wav"
