"""Command registry and matching — ~20 hardcoded commands for Phase 0."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

from vozctl.formatters import try_format

log = logging.getLogger(__name__)

# Set by engine.py at startup for mode-switching commands
_engine = None


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

# ── Commands that work in dictation mode too ────────────────
_DICTATION_SAFE: set[str] = set()


def exact(name: str, dictation_safe: bool = False):
    """Decorator to register an exact command. dictation_safe=True means it works in dictation mode."""
    def decorator(fn: Callable):
        _EXACT[name] = fn
        if dictation_safe:
            _DICTATION_SAFE.add(name)
        return fn
    return decorator


def parameterized(pattern: str, name: str):
    """Decorator to register a parameterized command."""
    def decorator(fn: Callable):
        _PARAMETERIZED.append((re.compile(pattern), name, fn))
        return fn
    return decorator


def match(raw_text: str) -> CommandMatch:
    """Match text against commands (command mode). Precedence: exact → parameterized → formatter → dictation fallback."""
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

    # 4. NATO sequence — "sierra alpha" → "sa", "cap bravo charlie" → "Bc"
    nato_result = _try_nato_sequence(normalized)
    if nato_result:
        log.info("Command [nato]: %r → %r", normalized, nato_result)
        text_to_type = nato_result
        return CommandMatch(
            name="nato_sequence",
            handler=lambda: _type_formatted(text_to_type),
            args={"text": text_to_type},
            kind="exact",
        )

    # 5. Dictation fallback (in command mode, engine will ignore this)
    log.info("Dictation: %r", raw_text)
    return CommandMatch(
        name="dictation",
        handler=lambda: _type_dictation(raw_text),
        args={"text": raw_text},
        kind="dictation",
    )


def match_dictation_mode(raw_text: str) -> CommandMatch:
    """Match in dictation mode: only dictation-safe commands, everything else is typed."""
    normalized = _normalize(raw_text)

    # Only check dictation-safe commands (mode switches, scratch)
    if normalized in _EXACT and normalized in _DICTATION_SAFE:
        log.info("Command [dictation-safe]: %s", normalized)
        return CommandMatch(name=normalized, handler=_EXACT[normalized], args={}, kind="exact")

    # Everything else is dictation
    log.info("Dictation: %r", raw_text)
    return CommandMatch(
        name="dictation",
        handler=lambda: _type_dictation(raw_text),
        args={"text": raw_text},
        kind="dictation",
    )


_last_typed_len: int = 0


def _type_formatted(text: str) -> None:
    global _last_typed_len
    from vozctl.actions import type_text
    type_text(text)
    _last_typed_len = len(text)


def _type_dictation(text: str) -> None:
    global _last_typed_len
    from vozctl.actions import type_text
    output = text + " "
    type_text(output)
    _last_typed_len = len(output)


def _scratch_last() -> None:
    """Delete the last typed text by sending backspaces."""
    global _last_typed_len
    if _last_typed_len > 0:
        from vozctl.actions import press_key
        for _ in range(_last_typed_len):
            press_key("backspace")
        log.info("Scratched %d characters", _last_typed_len)
        _last_typed_len = 0


# ──────────────────────────────────────────────────────────────
# Register Phase 0 commands
# ──────────────────────────────────────────────────────────────

from vozctl import actions


# ── Mode switching (work in both modes) ──

@exact("command mode", dictation_safe=True)
def cmd_command_mode():
    if _engine:
        from vozctl.engine import State
        _engine.set_state(State.COMMAND)

@exact("dictation mode", dictation_safe=True)
def cmd_dictation_mode():
    if _engine:
        from vozctl.engine import State
        _engine.set_state(State.DICTATION)

# ── Safety commands (work in both modes) ──

@exact("scratch that", dictation_safe=True)
def cmd_scratch():
    _scratch_last()

@exact("scratch", dictation_safe=True)
def cmd_scratch_alt():
    _scratch_last()

# ── Standard commands (command mode only) ──

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

@exact("space")
def cmd_space():
    actions.press_key("space")


# ── NATO alphabet (command mode — type single letters) ──

_NATO_WORDS: set[str] = set()  # populated below


def _try_nato_sequence(normalized: str) -> str | None:
    """Parse a multi-word NATO sequence. Returns typed string or None.

    'sierra alpha' → 'sa'
    'cap bravo charlie' → 'Bc'
    'cap alpha cap bravo' → 'AB'
    """
    words = normalized.split()
    if len(words) < 2:
        return None  # single words handled by exact match

    result = []
    i = 0
    while i < len(words):
        if words[i] == "cap" and i + 1 < len(words) and words[i + 1] in _NATO_WORDS:
            result.append(_NATO[words[i + 1]].upper())
            i += 2
        elif words[i] in _NATO_WORDS:
            result.append(_NATO[words[i]])
            i += 1
        else:
            return None  # non-NATO word found, not a NATO sequence

    return "".join(result) if result else None


_NATO = {
    "alpha": "a", "bravo": "b", "charlie": "c", "delta": "d",
    "echo": "e", "foxtrot": "f", "golf": "g", "hotel": "h",
    "india": "i", "juliet": "j", "kilo": "k", "lima": "l",
    "mike": "m", "november": "n", "oscar": "o", "papa": "p",
    "quebec": "q", "romeo": "r", "sierra": "s", "tango": "t",
    "uniform": "u", "victor": "v", "whiskey": "w", "xray": "x",
    "yankee": "y", "zulu": "z",
}

_NATO_WORDS.update(_NATO.keys())


def _make_nato_handler(letter: str):
    def handler():
        actions.type_text(letter)
    return handler

for _nato_word, _letter in _NATO.items():
    _EXACT[_nato_word] = _make_nato_handler(_letter)

# "cap <nato>" for uppercase
for _nato_word, _letter in _NATO.items():
    _EXACT[f"cap {_nato_word}"] = _make_nato_handler(_letter.upper())


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
