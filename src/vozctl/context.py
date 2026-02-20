"""Frontmost application context capture (macOS)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppContext:
    """Snapshot of the frontmost application."""
    bundle_id: str
    app_name: str
    window_title: str


def _ax_window_title(pid: int) -> str:
    """Get focused window title via Accessibility API (requires Accessibility permission)."""
    try:
        from ApplicationServices import (
            AXUIElementCreateApplication,
            AXUIElementCopyAttributeValue,
        )
        app_ref = AXUIElementCreateApplication(pid)
        err, focused = AXUIElementCopyAttributeValue(app_ref, "AXFocusedWindow", None)
        if err == 0 and focused:
            err2, title = AXUIElementCopyAttributeValue(focused, "AXTitle", None)
            if err2 == 0 and title:
                return str(title)
    except Exception as e:
        log.debug("AX window title failed: %s", e)
    return ""


def _cg_window_title(pid: int) -> str:
    """Fallback: get window title from CGWindowList (misses some apps like Ghostty)."""
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
            kCGWindowListExcludeDesktopElements,
        )
        options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        if window_list:
            for w in window_list:
                if w.get("kCGWindowOwnerPID") == pid:
                    title = w.get("kCGWindowName", "")
                    if title:
                        return title
    except Exception as e:
        log.debug("CGWindowList title failed: %s", e)
    return ""


def get_frontmost_app() -> AppContext:
    """Return the frontmost app's bundle ID, name, and window title."""
    try:
        from AppKit import NSWorkspace

        ws = NSWorkspace.sharedWorkspace()
        active = ws.frontmostApplication()
        bundle_id = active.bundleIdentifier() or "unknown"
        app_name = active.localizedName() or "unknown"
        pid = active.processIdentifier()

        # AX API is reliable (gets Ghostty, VS Code, etc.), CGWindowList as fallback
        window_title = _ax_window_title(pid) or _cg_window_title(pid)

        return AppContext(
            bundle_id=bundle_id,
            app_name=app_name,
            window_title=window_title,
        )
    except Exception as e:
        log.warning("Failed to get frontmost app: %s", e)
        return AppContext(bundle_id="unknown", app_name="unknown", window_title="")
