"""Sound OS - Backwards-compatibility wrapper for dave_bridge."""

try:
    from .dave_bridge import (
        start,
        set_level,
        on_wake,
        on_heard,
        on_done,
    )
except ImportError:
    from dave_bridge import (
        start,
        set_level,
        on_wake,
        on_heard,
        on_done,
    )

__all__ = ["start", "set_level", "on_wake", "on_heard", "on_done"]
