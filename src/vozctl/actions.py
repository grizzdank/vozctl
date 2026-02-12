"""macOS keyboard injection via CGEvents (Quartz)."""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

# Lazy-loaded Quartz bindings
_CG = None


def _init_cg():
    """Lazy-load Quartz CGEvent functions."""
    global _CG
    if _CG is not None:
        return _CG

    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        CGEventSourceCreate,
        CGEventSourceStateID,
        kCGEventFlagMaskShift,
        kCGEventFlagMaskControl,
        kCGEventFlagMaskAlternate,
        kCGEventFlagMaskCommand,
        kCGHIDEventTap,
    )

    _CG = {
        "create_kb": CGEventCreateKeyboardEvent,
        "post": CGEventPost,
        "set_flags": CGEventSetFlags,
        "source_create": CGEventSourceCreate,
        "source_state": CGEventSourceStateID,
        "tap": kCGHIDEventTap,
        "shift": kCGEventFlagMaskShift,
        "ctrl": kCGEventFlagMaskControl,
        "alt": kCGEventFlagMaskAlternate,
        "cmd": kCGEventFlagMaskCommand,
    }
    return _CG


def check_accessibility() -> bool:
    """Check if this process has macOS Accessibility permissions."""
    try:
        from ApplicationServices import AXIsProcessTrusted
        trusted = AXIsProcessTrusted()
        if not trusted:
            log.error(
                "Accessibility permission required.\n"
                "  System Settings → Privacy & Security → Accessibility\n"
                "  Add your terminal app (Terminal, iTerm2, etc.)"
            )
        return trusted
    except ImportError:
        log.warning("Could not check accessibility (ApplicationServices unavailable)")
        return False


# macOS virtual keycodes for common keys
_KEYCODES: dict[str, int] = {
    "return": 0x24, "enter": 0x24,
    "tab": 0x30,
    "space": 0x31,
    "delete": 0x33, "backspace": 0x33,
    "escape": 0x35, "esc": 0x35,
    "left": 0x7B, "right": 0x7C,
    "down": 0x7D, "up": 0x7E,
    "home": 0x73, "end": 0x77,
    "pageup": 0x74, "pagedown": 0x79,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76,
    "f5": 0x60, "f6": 0x61, "f7": 0x62, "f8": 0x64,
    "f9": 0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
    # Letters (lowercase)
    **{chr(c): c - ord("a") for c in range(ord("a"), ord("z") + 1)},
    # Digits
    **{str(i): [0x1D, 0x12, 0x13, 0x14, 0x15, 0x17, 0x16, 0x1A, 0x1C, 0x19][i] for i in range(10)},
    # Punctuation
    "-": 0x1B, "=": 0x18,
    "[": 0x21, "]": 0x1E,
    ";": 0x29, "'": 0x27,
    ",": 0x2B, ".": 0x2F,
    "/": 0x2C, "\\": 0x2A,
    "`": 0x32,
}

# Characters that require shift
_SHIFT_CHARS = set('~!@#$%^&*()_+{}|:"<>?ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def _post_key(keycode: int, flags: int = 0, key_down: bool = True) -> None:
    """Post a single key event."""
    cg = _init_cg()
    source = cg["source_create"](0)  # kCGEventSourceStatePrivate
    event = cg["create_kb"](source, keycode, key_down)
    if flags:
        cg["set_flags"](event, flags)
    cg["post"](cg["tap"], event)


def press_key(key: str, modifiers: list[str] | None = None) -> None:
    """Press and release a key with optional modifiers."""
    cg = _init_cg()

    keycode = _KEYCODES.get(key.lower())
    if keycode is None:
        log.warning("Unknown key: %r", key)
        return

    flags = 0
    for mod in (modifiers or []):
        mod_lower = mod.lower()
        if mod_lower in ("shift", "shft"):
            flags |= cg["shift"]
        elif mod_lower in ("ctrl", "control"):
            flags |= cg["ctrl"]
        elif mod_lower in ("alt", "option", "opt"):
            flags |= cg["alt"]
        elif mod_lower in ("cmd", "command", "super"):
            flags |= cg["cmd"]

    _post_key(keycode, flags, key_down=True)
    _post_key(keycode, flags, key_down=False)


def type_text(text: str, interval: float = 0.008) -> None:
    """Type a string by posting individual key events."""
    cg = _init_cg()

    for ch in text:
        flags = 0
        if ch == " ":
            keycode = _KEYCODES["space"]
        elif ch == "\n":
            keycode = _KEYCODES["return"]
        elif ch == "\t":
            keycode = _KEYCODES["tab"]
        elif ch.lower() in _KEYCODES:
            keycode = _KEYCODES[ch.lower()]
            if ch in _SHIFT_CHARS:
                flags = cg["shift"]
        else:
            log.debug("Skipping unmapped char: %r", ch)
            continue

        _post_key(keycode, flags, key_down=True)
        _post_key(keycode, flags, key_down=False)
        time.sleep(interval)


def hotkey(key: str, *modifiers: str) -> None:
    """Press a hotkey combination (e.g., hotkey('s', 'cmd'))."""
    press_key(key, list(modifiers))
