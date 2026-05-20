from __future__ import annotations

from importlib import import_module


_EXPORT_MODULES = (
    "amon.constants",
    "amon.models",
    "amon.host",
    "amon.jsonl",
    "amon.text",
    "amon.agents.base",
    "amon.agents.claude",
    "amon.agents.codex",
    "amon.agents.registry",
    "amon.monitor.tail",
    "amon.monitor.snapshot",
    "amon.sessions.resolve",
    "amon.sessions.discovery",
    "amon.sessions.summary",
    "amon.ui.state",
    "amon.ui.render",
    "amon.ui.curses_view",
    "amon.modes.xpane",
    "amon.modes.sessions",
    "amon.cli",
)

for _module_name in _EXPORT_MODULES:
    _module = import_module(_module_name)
    for _name in dir(_module):
        if _name.startswith("__"):
            continue
        globals()[_name] = getattr(_module, _name)

__all__ = sorted(name for name in globals() if not name.startswith("__"))
