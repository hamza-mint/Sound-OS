"""Sound OS - Backwards-compatibility wrapper for dave_bridge."""

from .dave_bridge import (
    start,
    stop,
    on_wake,
    on_heard,
    on_done,
    set_level,
    set_mouth,
    hush,
    say,
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
]
