from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .constants import DEFAULT_DETAIL_LINES, SCOPE_ALL, SCOPE_CURRENT
from .modes.sessions import run_session_detail_path, run_sessions_mode
from .modes.xpane import run_mode_b
from .monitor.snapshot import run_snapshot
from .monitor.tail import _format_exit_line, run_tail
from .sessions.resolve import decode_session_spec, infer_agent_from_path, resolve_path_from_session_id, resolve_session_pid, session_title, short_session_id


class AmonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = AmonArgumentParser(
        prog="amon",
        description="Monitor active Claude and Codex automation sessions.",
        epilog=(
            "Modes:\n"
            "  amon                         list active agent sessions\n"
            "  amon --current               list sessions under the current cwd\n"
            "  amon -i                      list inline (non-interactive) sessions\n"
            "  amon xpanes                  open the existing xpanes view\n"
            "  amon xpanes -i               open xpanes for inline sessions\n"
            "  amon xpanes --current        open xpanes for sessions under the current cwd\n"
            "  amon ID                      open one resolved session detail view"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("targets", nargs="*", help="session id to monitor, or 'xpanes'")
    parser.add_argument(
        "--current",
        action="store_true",
        help="limit discovery modes to sessions whose process cwd is under this cwd",
    )
    parser.add_argument("--session-id", help="Claude or Codex session id to monitor")
    parser.add_argument("--once", action="store_true", help="print one snapshot line and exit")
    parser.add_argument(
        "--idle-threshold",
        type=float,
        default=60.0,
        help="seconds without useful activity before the session is idle",
    )
    parser.add_argument(
        "--codex-all-sessions",
        action="store_true",
        help="monitor every Codex JSONL held by a discovered Codex process",
    )
    parser.add_argument(
        "-i",
        "--inline-only",
        action="store_true",
        help="show only inline (non-interactive) agent sessions in discovery modes",
    )
    parser.add_argument(
        "--lines",
        type=positive_int,
        default=DEFAULT_DETAIL_LINES,
        help=f"recent log lines to load in session detail views (default: {DEFAULT_DETAIL_LINES})",
    )
    parser.add_argument(
        "--color",
        choices=("always", "never", "auto"),
        default=None,
        help="color policy for TUI and direct tail output; --once snapshots stay plain",
    )
    parser.add_argument("--session-path", help=argparse.SUPPRESS)
    parser.add_argument("--session-spec", help=argparse.SUPPRESS)
    parser.add_argument("--session-title", help=argparse.SUPPRESS)
    parser.add_argument("--pid", type=int, help=argparse.SUPPRESS)
    return parser


def _direct_session_args(args) -> bool:
    return bool(args.session_id or args.session_path or args.session_spec)


def _scope_from_args(args) -> str:
    return SCOPE_CURRENT if args.current else SCOPE_ALL


def _print_unknown_target_error(target: str, error=None) -> None:
    err = error or sys.stderr
    print(f"amon: unknown session id or mode: {target}", file=err)
    print("amon: use 'amon xpanes ...' for the existing xpanes pane mode", file=err)


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    scope = _scope_from_args(args)
    targets = args.targets

    if targets and _direct_session_args(args):
        parser.error("positional target cannot be combined with direct session options")
    if args.inline_only:
        if _direct_session_args(args):
            parser.error("--inline-only cannot be combined with direct session options")
        if targets and not (len(targets) == 1 and targets[0] == "xpanes"):
            parser.error("--inline-only cannot be used with session id mode")

    if args.session_title:
        try:
            print(session_title(decode_session_spec(args.session_title)))
        except ValueError as exc:
            print(f"amon: {exc}", file=sys.stderr)
            return 1
        return 0

    if len(targets) == 1 and targets[0] == "xpanes":
        return run_mode_b(
            args.idle_threshold,
            codex_all=args.codex_all_sessions,
            color="always",
            scope=scope,
            inline_only=args.inline_only,
        )

    tui_color = args.color or "auto"
    tail_color = args.color or "never"
    pid = args.pid
    use_detail_view = False
    if targets:
        target = " ".join(targets)
        if len(targets) != 1:
            _print_unknown_target_error(target)
            return 1
        session_path = resolve_path_from_session_id(target)
        if not session_path:
            _print_unknown_target_error(target)
            return 1
        agent = infer_agent_from_path(session_path)
        use_detail_view = True
    elif not _direct_session_args(args):
        return run_sessions_mode(
            args.idle_threshold,
            codex_all=args.codex_all_sessions,
            scope=scope,
            lines=args.lines,
            color=tui_color,
            inline_only=args.inline_only,
        )
    elif args.session_spec:
        try:
            spec = decode_session_spec(args.session_spec)
        except ValueError as exc:
            print(f"amon: {exc}", file=sys.stderr)
            return 1
        agent = spec["agent"]
        session_path = spec["path"]
        pid = spec.get("pid")
    elif args.session_path:
        session_path = args.session_path
        agent = infer_agent_from_path(session_path)
    else:
        session_path = resolve_path_from_session_id(args.session_id)
        if not session_path:
            print(f"amon: session id not found: {args.session_id}", file=sys.stderr)
            return 1
        agent = infer_agent_from_path(session_path)
        use_detail_view = True

    sid_short = short_session_id(session_path)
    if args.once:
        process_state = None
        if pid is None and Path(session_path).exists():
            pid = resolve_session_pid(session_path, agent)
            process_state = "alive" if pid is not None else "exited"
        return run_snapshot(
            session_path,
            agent,
            sid_short,
            args.idle_threshold,
            color="never",
            pid=pid,
            process_state=process_state,
        )

    if use_detail_view:
        return run_session_detail_path(session_path, agent, lines=args.lines, color=tui_color)

    if not Path(session_path).exists():
        print(f"amon: session path missing: {session_path}", file=sys.stderr)
        return 1
    if pid is None:
        pid = resolve_session_pid(session_path, agent)
        if pid is None:
            print(_format_exit_line(agent, sid_short, tail_color))
            return 0
    return run_tail(
        session_path,
        agent,
        sid_short,
        args.idle_threshold,
        pid=pid,
        color=tail_color,
    )


if __name__ == "__main__":
    raise SystemExit(main())
