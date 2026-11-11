"""Public API of the parser module (see CONTRACT.md). Import only from here."""
from .rules import parse, parse_yes_no

__all__ = ["parse", "parse_yes_no"]
