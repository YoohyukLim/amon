from __future__ import annotations

import re


UUID_RE = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)
SCOPE_ALL = "all"
SCOPE_CURRENT = "current"
SESSION_STATUSES = ("failed", "running", "unknown", "exited")
STATUS_COUNT_DISPLAY_ORDER = ("running", "failed", "unknown", "exited")
STATUS_PRIORITY = {"failed": 3, "running": 2, "unknown": 1, "exited": 0}
UNICODE_STATUS_ICON_FRAMES = {
    "failed": ("●",),
    "running": ("✧", "✦", "✶", "✦", "✧"),
    "unknown": ("?",),
    "exited": ("○",),
}
ASCII_STATUS_ICON_FRAMES = {
    "failed": ("!",),
    "running": (".", "*", "X", "*", "."),
    "unknown": ("?",),
    "exited": ("o",),
}
UNICODE_STATIC_STATUS_ICONS = {
    "failed": "●",
    "running": "●",
    "unknown": "?",
    "exited": "○",
}
ASCII_STATIC_STATUS_ICONS = {
    "failed": "!",
    "running": "*",
    "unknown": "?",
    "exited": "o",
}
STATUS_ICONS = dict(UNICODE_STATIC_STATUS_ICONS)
STATUS_ICON_FRAME_SECONDS = 0.25
LIST_STATUS_GROUPS = (
    ("running", "Running"),
    ("failed", "Failed"),
    ("unknown", "Unknown"),
    ("exited", "Exited"),
)
SESSION_HIGHLIGHT_SECONDS = 3.0
DEFAULT_DETAIL_LINES = 200
DETAIL_DIRECT_EXIT_KEYS = ("q",)
DETAIL_LIST_DETAIL_EXIT_KEYS = ("q", "BACKSPACE", "ESC")
