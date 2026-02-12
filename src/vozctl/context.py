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


def get_frontmost_app() -> AppContext:
    """Return the frontmost app's bundle ID, name, and window title."""
    try:
        from AppKit import NSWorkspace
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
            kCGWindowListExcludeDesktopElements,
        )

        ws = NSWorkspace.sharedWorkspace()
        active = ws.frontmostApplication()
        bundle_id = active.bundleIdentifier() or "unknown"
        app_name = active.localizedName() or "unknown"

        # Get window title from CGWindowList
        window_title = ""
        options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        if window_list:
            pid = active.processIdentifier()
            for w in window_list:
                if w.get("kCGWindowOwnerPID") == pid:
                    title = w.get("kCGWindowName", "")
                    if title:
                        window_title = title
                        break

        return AppContext(
            bundle_id=bundle_id,
            app_name=app_name,
            window_title=window_title,
        )
    except Exception as e:
        log.warning("Failed to get frontmost app: %s", e)
        return AppContext(bundle_id="unknown", app_name="unknown", window_title="")
