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


def _match_single(normalized: str) -> CommandMatch | None:
    """Try to match a single normalized phrase. Returns None if no match."""
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

    return None


def match(raw_text: str) -> CommandMatch:
    """Match text against commands (command mode).

    If the VAD grouped multiple sentences, split and try each one.
    Precedence per chunk: exact → parameterized → formatter → NATO → ignore.
    """
    # Preserve exact transcript text for explicit literal typing commands.
    m = re.match(r"^\s*(?:type|insert)\s+(?P<text>.+?)\s*$", raw_text, re.IGNORECASE)
    if m:
        text = m.group("text")
        log.info("Command [param-raw]: type_text → %r", text)
        return CommandMatch(name="type_text", handler=cmd_type_text, args={"text": text}, kind="parameterized")

    normalized = _normalize(raw_text)

    # Try full text first
    result = _match_single(normalized)
    if result:
        return result

    # Split on sentence boundaries and try each chunk
    # Parakeet adds punctuation (periods, commas, etc.) — treat as separators
    sentences = re.split(r'[.!?,;]+', raw_text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) > 1:
        handlers = []
        for sent in sentences:
            norm_sent = _normalize(sent)
            if not norm_sent:
                continue
            r = _match_single(norm_sent)
            if r:
                handlers.append(r)
            else:
                log.info("Ignored (no match): %r", sent)

        if handlers:
            def run_all():
                for h in handlers:
                    try:
                        if h.args and h.kind == "parameterized":
                            h.handler(**h.args)
                        else:
                            h.handler()
                    except Exception as e:
                        log.error("Command %r failed: %s", h.name, e)

            names = [h.name for h in handlers]
            log.info("Multi-command: %s", names)
            return CommandMatch(
                name=f"multi:{'+'.join(names)}",
                handler=run_all,
                args={},
                kind="exact",
            )

    # Dictation fallback (in command mode, engine will ignore this)
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

@exact("commands", dictation_safe=True)
def cmd_commands():
    if _engine:
        from vozctl.engine import State
        _engine.set_state(State.COMMAND)

@exact("dictation mode", dictation_safe=True)
def cmd_dictation_mode():
    if _engine:
        from vozctl.engine import State
        _engine.set_state(State.DICTATION)

@exact("typing", dictation_safe=True)
def cmd_typing():
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

@exact("slap")
def cmd_slap():
    actions.press_key("return")

@exact("enter")
def cmd_enter():
    actions.press_key("return")

@exact("stomp")
def cmd_stomp():
    actions.hotkey("return", "shift")

@exact("newline")
def cmd_newline():
    actions.hotkey("return", "shift")

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

@exact("head")
def cmd_head():
    actions.hotkey("left", "cmd")

@exact("go end")
def cmd_end():
    actions.press_key("end")

@exact("tail")
def cmd_tail():
    actions.hotkey("right", "cmd")

@exact("delete that")
def cmd_delete():
    actions.press_key("backspace")

@exact("delete")
def cmd_delete_single():
    actions.press_key("backspace")

@exact("backspace")
def cmd_backspace():
    actions.press_key("backspace")

@exact("delete word")
def cmd_delete_word():
    actions.hotkey("backspace", "alt")

@exact("option delete")
def cmd_option_delete():
    actions.hotkey("backspace", "alt")

@exact("tab")
def cmd_tab():
    actions.press_key("tab")

@exact("escape")
def cmd_escape():
    actions.press_key("escape")

@exact("space")
def cmd_space():
    actions.press_key("space")


# ── System navigation ──────────────────────────────────────

# Tabs
@exact("next tab")
def cmd_next_tab():
    actions.hotkey("]", "cmd", "shift")

@exact("previous tab")
def cmd_prev_tab():
    actions.hotkey("[", "cmd", "shift")

@exact("close tab")
def cmd_close_tab():
    actions.hotkey("w", "cmd")

# Windows
@exact("next window")
def cmd_next_window():
    actions.hotkey("`", "cmd")

# Apps
@exact("next app")
def cmd_next_app():
    actions.hotkey("tab", "cmd")

@exact("previous app")
def cmd_prev_app():
    actions.hotkey("tab", "cmd", "shift")

@exact("switch app")
def cmd_switch_app():
    actions.hotkey("tab", "cmd")

# Panes (Ghostty: Opt+hjkl)
# "pane"/"pain" unreliable in short segments — "focus" as reliable alias
@exact("pane left")
def cmd_pane_left():
    actions.hotkey("h", "alt")

@exact("pain left")
def cmd_pain_left():
    actions.hotkey("h", "alt")

@exact("focus left")
def cmd_focus_left():
    actions.hotkey("h", "alt")

@exact("pane down")
def cmd_pane_down():
    actions.hotkey("j", "alt")

@exact("pain down")
def cmd_pain_down():
    actions.hotkey("j", "alt")

@exact("focus down")
def cmd_focus_down():
    actions.hotkey("j", "alt")

@exact("pane up")
def cmd_pane_up():
    actions.hotkey("k", "alt")

@exact("pain up")
def cmd_pain_up():
    actions.hotkey("k", "alt")

@exact("focus up")
def cmd_focus_up():
    actions.hotkey("k", "alt")

@exact("pane right")
def cmd_pane_right():
    actions.hotkey("l", "alt")

@exact("pain right")
def cmd_pain_right():
    actions.hotkey("l", "alt")

@exact("focus right")
def cmd_focus_right():
    actions.hotkey("l", "alt")


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

    _CAP_PREFIXES = {"cap", "big", "tap", "hat", "hap"}
    result = []
    i = 0
    while i < len(words):
        if words[i] in _CAP_PREFIXES and i + 1 < len(words) and words[i + 1] in _NATO_WORDS:
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

# "<prefix> <nato>" for uppercase — multiple prefixes since Parakeet
# often mishears "cap" as "tap", "hat", or "hap"
for _prefix in ("cap", "big", "tap", "hat", "hap"):
    for _nato_word, _letter in _NATO.items():
        _EXACT[f"{_prefix} {_nato_word}"] = _make_nato_handler(_letter.upper())


# ── Number words for repeat counts ──

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "to": 2, "too": 2, "for": 4,  # common Parakeet misrecognitions
}


def _parse_count(s: str) -> int:
    """Parse a count from digit string or number word."""
    if s.isdigit():
        return int(s)
    return _NUMBER_WORDS.get(s.lower(), 1)


def _repeat_key(key: str, count: int, modifiers: list[str] | None = None) -> None:
    """Press a key multiple times."""
    for _ in range(count):
        actions.press_key(key, modifiers)


# ── Parameterized commands ──

# Word movement: "word left", "go 2 words left", "3 word right"
# MUST be before go_n_direction — otherwise "go word left" matches as go_n(count="word")
@parameterized(r"(?:go )?(?P<count>\w+ )?words? (?P<direction>left|right)", "word_move")
def cmd_word_move(count: str = "", direction: str = "left"):
    n = _parse_count(count.strip()) if count and count.strip() else 1
    mods = ["alt"]
    _repeat_key(direction, n, mods)

# Repeated movement: "go 3 left", "go two right", "go 5 up"
@parameterized(r"go (?P<count>\w+) (?P<direction>up|down|left|right)", "go_n_direction")
def cmd_go_n(count: str, direction: str):
    n = _parse_count(count)
    _repeat_key(direction, n)

# Word delete: "delete two words", "delete 3 words"
# MUST be before delete_n — otherwise "delete two words" matches as delete_n(count="two")
@parameterized(r"delete (?P<count>\w+ )?words?", "delete_words")
def cmd_delete_words(count: str = ""):
    n = _parse_count(count.strip()) if count and count.strip() else 1
    for _ in range(n):
        actions.hotkey("backspace", "alt")

# Repeated delete: "delete 3" or "delete three"
@parameterized(r"delete (?P<count>\w+)", "delete_n")
def cmd_delete_n(count: str):
    n = _parse_count(count)
    _repeat_key("backspace", n)

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
