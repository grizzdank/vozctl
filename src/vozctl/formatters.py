"""Text formatters for voice-driven coding — snake_case, camelCase, etc."""

from __future__ import annotations

import re
import logging

log = logging.getLogger(__name__)


def _words(text: str) -> list[str]:
    """Split text into lowercase words."""
    return text.lower().split()


def snake_case(text: str) -> str:
    """hello world → hello_world"""
    return "_".join(_words(text))


def camel_case(text: str) -> str:
    """hello world → helloWorld"""
    words = _words(text)
    if not words:
        return ""
    return words[0] + "".join(w.capitalize() for w in words[1:])


def pascal_case(text: str) -> str:
    """hello world → HelloWorld"""
    return "".join(w.capitalize() for w in _words(text))


def kebab_case(text: str) -> str:
    """hello world → hello-world"""
    return "-".join(_words(text))


def dot_case(text: str) -> str:
    """hello world → hello.world"""
    return ".".join(_words(text))


def slash_case(text: str) -> str:
    """hello world → hello/world"""
    return "/".join(_words(text))


def upper_case(text: str) -> str:
    """hello world → HELLO WORLD"""
    return text.upper()


def lower_case(text: str) -> str:
    """hello world → hello world"""
    return text.lower()


def title_case(text: str) -> str:
    """hello world → Hello World"""
    return text.title()


def constant_case(text: str) -> str:
    """hello world → HELLO_WORLD"""
    return "_".join(_words(text)).upper()


# Registry: formatter name → function
FORMATTERS: dict[str, callable] = {
    "snake": snake_case,
    "snake case": snake_case,
    "camel": camel_case,
    "camel case": camel_case,
    "pascal": pascal_case,
    "pascal case": pascal_case,
    "kebab": kebab_case,
    "kebab case": kebab_case,
    "dot": dot_case,
    "dot case": dot_case,
    "slash": slash_case,
    "slash case": slash_case,
    "upper": upper_case,
    "upper case": upper_case,
    "lower": lower_case,
    "lower case": lower_case,
    "title": title_case,
    "title case": title_case,
    "constant": constant_case,
    "constant case": constant_case,
    "all caps": constant_case,
}


def try_format(text: str) -> tuple[str, str] | None:
    """Check if text starts with a formatter prefix. Returns (formatted, formatter_name) or None."""
    text_lower = text.lower().strip()
    # Try longest prefix first to avoid "snake" matching before "snake case"
    for name in sorted(FORMATTERS, key=len, reverse=True):
        if text_lower.startswith(name + " "):
            remainder = text[len(name):].strip()
            if remainder:
                formatted = FORMATTERS[name](remainder)
                log.debug("Formatter %r: %r → %r", name, remainder, formatted)
                return formatted, name
    return None
