# amon Architecture

**Version**: 3  |  **Last Updated**: 2026-05-20

<!-- atlas-managed: do not delete sections; edit content freely -->
<!-- atlas-version: 1 -->

## 1. Overview

`amon` is an implemented single-file command line monitor for Claude and Codex agent sessions. The executable at [`amon`](../../amon) tails JSONL session logs, formats selected assistant/tool activity into compact status lines, detects idle and exited sessions, and can launch one monitor pane per active session through `xpanes`.

The public usage contract is summarized in the root [`README.md`](../../README.md). Regression coverage lives in [`tests/test_amon.py`](../../tests/test_amon.py) with Claude and Codex JSONL fixtures in [`claude_session.jsonl`](../../tests/fixtures/claude_session.jsonl) and [`codex_session.jsonl`](../../tests/fixtures/codex_session.jsonl).

## 2. Tech Stack

| Area | Decision | Notes |
|---|---|---|
| Language | Python 3 stdlib | [`amon`](../../amon) has no runtime package dependency |
| Packaging | Extensionless executable | User copies or symlinks the file onto `PATH` |
| Session source | JSONL logs | Claude project logs and Codex session logs use different event shapes |
| Process discovery / liveness | Host commands + PID probe | Uses `pgrep`, `ps`, `lsof`, and `os.kill(pid, 0)` from [`amon`](../../amon) |
| Multi-session display | `xpanes` | Required only for Mode B discovery launch |
| Shell integration | Bash profile function | Managed by [`scripts/install-claude-session-wrapper.sh`](../../scripts/install-claude-session-wrapper.sh) and [`scripts/uninstall-claude-session-wrapper.sh`](../../scripts/uninstall-claude-session-wrapper.sh) |
| Tests | `unittest` | Fixtures: [`claude_session.jsonl`](../../tests/fixtures/claude_session.jsonl), [`codex_session.jsonl`](../../tests/fixtures/codex_session.jsonl) |
| Repo-local state | Git ignore rules | Local cairn, Claude state, worktrees, and bytecode are excluded by [`.gitignore`](../../.gitignore) |

## 3. Layer Architecture

| Layer | Responsibility | Dependency Direction |
|---|---|---|
| CLI parsing | `build_parser()` and `main()` select direct monitoring, snapshot, hidden pane worker mode, or Mode B launcher in [`amon`](../../amon) | Calls resolvers, snapshot/tail runtime, or launcher |
| Session discovery | `candidate_pids()`, `process_command()`, `is_claude_agent()`, `is_codex_agent()`, `is_inline_agent_command()`, and `discover_active_sessions()` find active agent sessions and mark inline sessions | Feeds PID, path, command context, and inline status to resolvers and list filters |
| Session resolution | `resolve_claude_session_path()`, `resolve_codex_session_paths()`, `resolve_path_from_session_id()`, and `resolve_session_pid()` map processes, ids, or paths to JSONL paths and live PIDs | Feeds concrete paths and lifecycle context to tail/snapshot |
| Event formatting | `_format_claude_event()`, `_format_codex_event()`, `_tool_detail()`, `is_agent_exit_event()`, and `format_event()` normalize runtime-specific JSONL records | Keeps display rendering and exit-event detection separate from tail policy |
| JSONL tailing | `JsonlTail` tracks offsets, skips malformed lines, and resets on truncation | Feeds parsed events to formatting |
| Idle and lifecycle | `IdleStateMachine`, `_pid_alive()`, `_process_state()`, `run_tail()`, and `snapshot_status()` decide idle warnings, process fields, snapshot exit codes, and exit output | Uses tail events and optional discovered PID |
| Mode B launcher | `encode_session_spec()`, `decode_session_spec()`, `session_title()`, and `run_mode_b()` pass compact session specs to `xpanes` | Spawns independent single-session monitor processes |
| Claude wrapper scripts | Install/remove a managed shell function that injects a UUID `--session-id` for new Claude runs | Improves discovery precision before `amon` starts |
| Test harness | [`tests/test_amon.py`](../../tests/test_amon.py) imports the extensionless executable and verifies CLI, discovery, formatting, tailing, snapshot, launcher, and wrapper scripts | Guards the single-file implementation |

The core architectural constraint remains that a monitor instance owns exactly one session stream. Mode B is a launcher around single-session monitors rather than an in-process multiplexer.

## 4. Integration Points

| Integration | Purpose | Current Contract |
|---|---|---|
| Claude JSONL logs | Mode A and Mode B session input | Resolve from `$HOME/.claude/projects/{cwd-slug}/{session-id}.jsonl`; if the command line contains `--session-id`, that exact file is required |
| Codex JSONL logs | Mode A and Mode B session input | Resolve from open `.codex/sessions/**/*.jsonl` files reported by `lsof`; default to newest per PID unless `--codex-all-sessions` is set |
| Host process table | Discovery and lifecycle checks | `pgrep -f` collects candidates; `ps -o command=` identifies Claude/Codex agent processes; `--inline-only` narrows discovery views to Claude `-p` / `--print` and direct `codex exec`; PID probes detect exits |
| `xpanes` | Visual separation for multiple monitors | Required for no-argument Mode B; missing dependency exits with code `3` |
| Terminal pane title | Identify sessions in Mode B | `run_mode_b()` sets each pane title to `{runtime}/{session-uuid}` via `--session-title`; non-UUID stems fall back to the full filename stem |
| Pane retention | Keep final output visible | The `xpanes` command template runs a normal shell command instead of `exec`, so completed monitors leave their pane shell visible |
| Shell profile | Claude session-id injection | The installer writes a managed `claude()` function to `~/.bash_profile` by default; calls with `--session-id`, `--resume`, or `--continue` bypass injection |
| Local agent instructions | Runtime collaboration rules | [`CLAUDE.md`](../../CLAUDE.md) and [`AGENTS.md`](../../AGENTS.md) describe local project-agent workflow outside the CLI runtime |

## 5. Data Flow Examples

### 5.1 Mode A Tail

1. User runs `amon --session-id <id>` or a hidden pane worker command with `--session-spec`.
2. CLI resolves the id/spec to a concrete JSONL path, runtime, and optional PID.
3. `run_tail()` primes `JsonlTail` at current EOF to avoid replaying history.
4. New JSONL records are parsed, normalized by runtime-specific formatters, and printed as `[runtime/session] Msg ...` or `[runtime/session] Tool ...`.
5. `IdleStateMachine` emits one idle warning after the configured silence threshold and rearms after useful activity.
6. When a discovered PID disappears or a supported agent-exit record appears, the monitor prints `AGENT EXITED` and returns success.

### 5.2 Mode A Snapshot

1. User runs `amon --session-id <id> --once`.
2. CLI resolves the session path and, when no PID was supplied, tries to match the path to an active discovered process.
3. `snapshot_status()` scans the file for the last useful formatted event, compares file mtime with `--idle-threshold`, and resolves `process=alive|exited|unknown`.
4. Command prints one status line and exits `0` for working, `2` for idle, `4` for exited, or `1` when the path is missing.

### 5.3 Discovery Views

1. User runs `amon` with no session flags or `amon xpane`.
2. Discovery accepts active Claude/Codex agent processes and records whether each is inline.
3. `--inline-only` or the sessions TUI `i` toggle limits the displayed set to inline sessions.
4. Resolvers convert each surviving process into one or more session paths.
5. The default sessions TUI aggregates rows by session id and opens a detail log with `Enter`.
6. `run_mode_b()` base64-encodes each session spec so shell quoting does not leak paths with spaces.
7. `xpanes -t -c` starts one independent monitor per spec and sets the pane title to `session_title()`.

### 5.4 Claude Wrapper Install / Cleanup

1. User runs [`scripts/install-claude-session-wrapper.sh`](../../scripts/install-claude-session-wrapper.sh) with an optional `--profile PATH`.
2. The installer replaces any prior managed block and writes a shell function named `claude`.
3. New Claude invocations receive `--session-id "$(uuidgen | tr '[:upper:]' '[:lower:]')"` unless the user already supplied a session/resume flag.
4. [`scripts/uninstall-claude-session-wrapper.sh`](../../scripts/uninstall-claude-session-wrapper.sh) removes only the managed block and is a no-op when nothing is installed.

## 6. Configuration System

| Surface | Meaning | Default |
|---|---|---|
| `--session-id` | Monitor one known Claude or Codex session id | unset |
| `--once` | Emit one snapshot line with idle and process state, then exit | false |
| `--idle-threshold` | Seconds without useful activity before idle warning/status | `60.0` |
| `--codex-all-sessions` | Include every open Codex JSONL for a PID in discovery views | false |
| `-i`, `--inline-only` | Show only inline (non-interactive) agent sessions in discovery views | false |
| `--color` | Control color for direct single-session output | `never` |
| `--session-path` | Hidden direct path worker entrypoint | unset |
| `--session-spec` | Hidden Mode B encoded worker entrypoint | unset |
| `--session-title` | Hidden title renderer for `xpanes` pane labels | unset |
| `--pid` | Hidden PID lifecycle monitor for direct worker calls and Mode B panes | unset |
| Installer `--profile` | Shell profile path to edit | `~/.bash_profile` |
| Installer `--print` | Print the managed wrapper block without editing | false |

Mode B forces `--color=always` for spawned panes, while direct Mode A remains plain unless the caller passes `--color`.

## 7. Drift Watch

(현재 발견된 어긋남 없음 — 2026-05-20 discovery policy update 기준)

## 8. Related Documents

- [Root README](../../README.md)
- [Docs README](../README.md)
- [Single command flags ADR](../arch/260518-231927-single-command-flags.md)
- [Mode B xpanes ADR](../arch/260518-231928-mode-b-xpanes-spawn.md)
- [Python stdlib ADR](../arch/260518-231929-python-stdlib.md)
- [Idle threshold ADR](../arch/260518-231930-stuck-silent-threshold.md)
- [Codex multi-jsonl ADR](../arch/260518-231931-codex-multi-jsonl-default.md)
- [Discovery noninteractive ADR (superseded)](../arch/260518-231932-discovery-noninteractive-only.md)
- [Discovery all agents ADR](../arch/260520-093830-discovery-all-agents-inline-filter.md)
- [Initial implementation task](../tasks/260518-231933-amon-implementation.md)
- [Implementation v2 task](../tasks/260519-090729-amon-implementation-v2.md)
- [Implementation checklist](../tasks/260519-091951-amon-implementation-checklist.md)
