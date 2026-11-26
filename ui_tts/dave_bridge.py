"""Sound OS - Dave bridge (forwarding to dave_desktop). Never raises (CONTRACT Rule 7)."""

from .dave_desktop import (
    start,
    stop,
    on_wake,
    on_heard,
    on_done,
    set_level,
    set_mouth,
    hush,
    say,
    set_llm_state,
)

__all__ = [
    "start",
    "stop",
    "on_wake",
    "on_heard",
    "on_done",
    "set_level",
    "set_mouth",
    "hush",
    "say",
    "set_llm_state",
]
