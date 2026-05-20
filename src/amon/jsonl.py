from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Optional


def pick_latest_jsonl(directory: str) -> Optional[str]:
    root = Path(directory)
    if not root.is_dir():
        return None
    paths = [path for path in root.iterdir() if path.is_file() and path.suffix == ".jsonl"]
    if not paths:
        return None
    return str(max(paths, key=lambda path: (path.stat().st_mtime, str(path))))


class JsonlTail:
    def __init__(self, path: str):
        self.path = Path(path)
        self.offset = 0

    def read_new_lines(self) -> list[dict]:
        if not self.path.exists():
            return []
        size = self.path.stat().st_size
        if size < self.offset:
            self.offset = 0

        events: list[dict] = []
        with self.path.open("r", encoding="utf-8") as handle:
            handle.seek(self.offset)
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    event = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    events.append(event)
            self.offset = handle.tell()
        return events


def read_recent_jsonl_events(session_path: str, line_count: int) -> list[dict]:
    if line_count <= 0:
        raise ValueError("line_count must be positive")

    path = Path(session_path)
    if not path.exists():
        return []

    recent: deque[str] = deque(maxlen=line_count)
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError:
        return []

    with handle:
        for line in handle:
            if line.strip():
                recent.append(line)

    events: list[dict] = []
    for line in recent:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events
