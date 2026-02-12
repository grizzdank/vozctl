"""Command registry and matching — ~20 hardcoded commands for Phase 0."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

from vozctl.formatters import try_format

log = logging.getLogger(__name__)


@dataclass
class CommandMatch:
    """Result of command matching."""
    name: str
    handler: Callable
    args: dict
    kind: str  # "exact", "parameterized", "formatter", "dictation"


def _normalize(text: str) -> str:
    """Normalize text for matching: lowercase, strip, collapse whitespace, remove punctuation."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


# ── Exact commands ──────────────────────────────────────────
# name → handler (called with no args)
_EXACT: dict[str, Callable] = {}

# ── Parameterized commands ──────────────────────────────────
# (compiled_regex, name, handler)
# handler is called with regex match groups as kwargs
_PARAMETERIZED: list[tuple[re.Pattern, str, Callable]] = []


def exact(name: str):
    """Decorator to register an exact command."""
    def decorator(fn: Callable):
        _EXACT[name] = fn
        return fn
    return decorator


def parameterized(pattern: str, name: str):
    """Decorator to register a parameterized command."""
    def decorator(fn: Callable):
        _PARAMETERIZED.append((re.compile(pattern), name, fn))
        return fn
    return decorator


def match(raw_text: str) -> CommandMatch:
    """Match text against commands. Precedence: exact → parameterized → formatter → dictation."""
    normalized = _normalize(raw_text)

    # 1. Exact match
    if normalized in _EXACT:
        log.info("Command [exact]: %s", normalized)
        return CommandMatch(name=normalized, handler=_EXACT[normalized], args={}, kind="exact")

    # 2. Parameterized match
    for pattern, name, handler in _PARAMETERIZED:
        m = pattern.match(normalized)
        if m:
            args = m.groupdict()
            log.info("Command [param]: %s → %s", name, args)
            return CommandMatch(name=name, handler=handler, args=args, kind="parameterized")

    # 3. Formatter match
    fmt_result = try_format(normalized)
    if fmt_result:
        formatted, fmt_name = fmt_result
        log.info("Command [formatter]: %s → %r", fmt_name, formatted)
        return CommandMatch(
            name=f"format:{fmt_name}",
            handler=lambda: _type_formatted(formatted),
            args={"text": formatted},
            kind="formatter",
        )

    # 4. Dictation fallback
    log.info("Dictation: %r", raw_text)
    return CommandMatch(
        name="dictation",
        handler=lambda: _type_dictation(raw_text),
        args={"text": raw_text},
        kind="dictation",
    )


def _type_formatted(text: str) -> None:
    from vozctl.actions import type_text
    type_text(text)


def _type_dictation(text: str) -> None:
    from vozctl.actions import type_text
    type_text(text + " ")


# ──────────────────────────────────────────────────────────────
# Register Phase 0 commands
# ──────────────────────────────────────────────────────────────

from vozctl import actions


@exact("undo")
def cmd_undo():
    actions.hotkey("z", "cmd")

@exact("redo")
def cmd_redo():
    actions.hotkey("z", "cmd", "shift")

@exact("copy")
def cmd_copy():
    actions.hotkey("c", "cmd")

@exact("cut")
def cmd_cut():
    actions.hotkey("x", "cmd")

@exact("paste")
def cmd_paste():
    actions.hotkey("v", "cmd")

@exact("save")
def cmd_save():
    actions.hotkey("s", "cmd")

@exact("select all")
def cmd_select_all():
    actions.hotkey("a", "cmd")

@exact("new line")
def cmd_new_line():
    actions.press_key("return")

@exact("go up")
def cmd_up():
    actions.press_key("up")

@exact("go down")
def cmd_down():
    actions.press_key("down")

@exact("go left")
def cmd_left():
    actions.press_key("left")

@exact("go right")
def cmd_right():
    actions.press_key("right")

@exact("page up")
def cmd_page_up():
    actions.press_key("pageup")

@exact("page down")
def cmd_page_down():
    actions.press_key("pagedown")

@exact("go home")
def cmd_home():
    actions.press_key("home")

@exact("go end")
def cmd_end():
    actions.press_key("end")

@exact("delete that")
def cmd_delete():
    actions.press_key("backspace")

@exact("tab")
def cmd_tab():
    actions.press_key("tab")

@exact("escape")
def cmd_escape():
    actions.press_key("escape")


# ── Parameterized commands ──

@parameterized(r"go to line (?P<number>\d+)", "go_to_line")
def cmd_go_to_line(number: str):
    """Jump to a line number (Cmd+G style or Ctrl+G for VS Code)."""
    actions.hotkey("g", "ctrl")
    import time
    time.sleep(0.1)
    actions.type_text(number)
    actions.press_key("return")

@parameterized(r"select line (?P<number>\d+)", "select_line")
def cmd_select_line(number: str):
    """Go to line then select it."""
    cmd_go_to_line(number)
    actions.hotkey("l", "cmd")

@parameterized(r"(?:type|insert) (?P<text>.+)", "type_text")
def cmd_type_text(text: str):
    """Explicitly type arbitrary text."""
    actions.type_text(text)
