from __future__ import annotations

import signal
import sys
import threading
import time
from typing import Optional

from ..agents.registry import get_agent
from ..host import _pid_alive
from ..jsonl import JsonlTail, read_recent_jsonl_events


_TAIL_STOP = False


def is_agent_exit_event(ev: dict, agent: str) -> bool:
    return get_agent(agent).is_exit_event(ev)


def _use_color(color: str) -> bool:
    if color == "always":
        return True
    if color == "auto":
        return sys.stdout.isatty()
    return False


def _colorize(kind: str, text: str, color: str) -> str:
    if not _use_color(color):
        return text
    codes = {
        "Tool": "36",
        "WARN": "33",
        "EXIT": "2",
    }
    code = codes.get(kind)
    if not code:
        return text
    return f"\033[{code}m{text}\033[0m"


def _format_event_detail(ev: dict, agent: str, color: str = "never") -> Optional[str]:
    formatted = get_agent(agent).format_event(ev)
    if not formatted:
        return None
    kind, detail = formatted
    return f"{_colorize(kind, kind, color)} {detail}".rstrip()


def format_event(ev: dict, agent: str, sid_short: str, color: str = "never") -> Optional[str]:
    detail = _format_event_detail(ev, agent, color=color)
    if not detail:
        return None
    return f"[{agent}/{sid_short}] {detail}".rstrip()


class IdleStateMachine:
    def __init__(self, threshold: float, now: Optional[float] = None):
        self.threshold = threshold
        self.last_touch = time.monotonic() if now is None else now
        self.warned = False

    def touch(self, now: Optional[float] = None) -> None:
        self.last_touch = time.monotonic() if now is None else now
        self.warned = False

    def idle_seconds(self, now: Optional[float] = None) -> float:
        current = time.monotonic() if now is None else now
        return max(0.0, current - self.last_touch)

    def should_warn(self, now: Optional[float] = None) -> bool:
        if self.warned:
            return False
        if self.idle_seconds(now) >= self.threshold:
            self.warned = True
            return True
        return False


def _format_idle_line(agent: str, sid_short: str, idle_seconds: float, color: str) -> str:
    label = _colorize("WARN", "IDLE", color)
    return f"[{agent}/{sid_short}] {label} idle={int(idle_seconds)}s"


def _format_exit_line(agent: str, sid_short: str, color: str) -> str:
    label = _colorize("EXIT", "AGENT EXITED", color)
    return f"[{agent}/{sid_short}] {label}"


def _install_tail_signal_handlers():
    if threading.current_thread() is not threading.main_thread():
        return None

    previous = {}

    def stop_handler(_signum, _frame):
        global _TAIL_STOP
        _TAIL_STOP = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.getsignal(sig)
        signal.signal(sig, stop_handler)
    return previous


def _restore_tail_signal_handlers(previous) -> None:
    if not previous:
        return
    for sig, handler in previous.items():
        signal.signal(sig, handler)


def run_tail(
    session_path: str,
    agent: str,
    sid_short: str,
    idle_threshold: float,
    pid: Optional[int] = None,
    poll_interval: float = 1.0,
    color: str = "never",
    *,
    max_iterations: Optional[int] = None,
    now_func=None,
    sleep_func=None,
    output=None,
) -> int:
    global _TAIL_STOP
    _TAIL_STOP = False
    now = now_func or time.monotonic
    sleep = sleep_func or time.sleep
    stream = output or sys.stdout
    tail = JsonlTail(session_path)
    tail.read_new_lines()
    idle = IdleStateMachine(idle_threshold, now=now())
    iterations = 0
    previous_handlers = _install_tail_signal_handlers()

    try:
        while not _TAIL_STOP:
            if pid is not None and not _pid_alive(pid):
                print(_format_exit_line(agent, sid_short, color), file=stream, flush=True)
                return 0

            printed = False
            agent_exited = False
            for event in tail.read_new_lines():
                if is_agent_exit_event(event, agent):
                    agent_exited = True
                    continue
                line = format_event(event, agent, sid_short, color=color)
                if line:
                    print(line, file=stream, flush=True)
                    printed = True
            if agent_exited:
                print(_format_exit_line(agent, sid_short, color), file=stream, flush=True)
                return 0
            if printed:
                idle.touch(now=now())
            elif idle.should_warn(now=now()):
                print(
                    _format_idle_line(agent, sid_short, idle.idle_seconds(now=now()), color),
                    file=stream,
                    flush=True,
                )

            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                return 0
            sleep(poll_interval)
    except KeyboardInterrupt:
        return 0
    finally:
        _restore_tail_signal_handlers(previous_handlers)
    return 0


def _event_terminal_status(ev: dict, agent: str) -> Optional[str]:
    return get_agent(agent).terminal_status_from_event(ev)


def _format_detail_event(ev: dict, agent: str, sid_short: str, color: str = "never") -> Optional[str]:
    if is_agent_exit_event(ev, agent):
        terminal_status = _event_terminal_status(ev, agent)
        if terminal_status == "failed":
            label = _colorize("WARN", "AGENT FAILED", color)
            return f"[{agent}/{sid_short}] {label}"
        return _format_exit_line(agent, sid_short, color)
    return format_event(ev, agent, sid_short, color=color)


def read_recent_log_lines(
    session_path: str,
    agent: str,
    sid_short: str,
    line_count: int,
    color: str = "never",
) -> list[str]:
    lines: list[str] = []
    for event in read_recent_jsonl_events(session_path, line_count):
        line = _format_detail_event(event, agent, sid_short, color=color)
        if line:
            lines.append(line)
    return lines
