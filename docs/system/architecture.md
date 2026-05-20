# amon Architecture

**Version**: 3  |  **Last Updated**: 2026-05-20

<!-- atlas-managed: do not delete sections; edit content freely -->
<!-- atlas-version: 1 -->

## 1. Overview

`amon` is a Python standard-library CLI for monitoring local Claude and Codex agent sessions. The checkout command shim at [`amon`](../../amon) loads the package under [`src/amon`](../../src/amon), where agent-specific adapters discover running processes, resolve JSONL session logs, summarize session status, render list/detail terminal views, and launch one monitor pane per session through `xpanes`.

The public usage contract is summarized in the root [`README.md`](../../README.md). Regression coverage lives in [`tests/test_amon.py`](../../tests/test_amon.py), with package import coverage initialized by [`tests/__init__.py`](../../tests/__init__.py).

## 2. Tech Stack

| Area | Decision | Notes |
|---|---|---|
| Language | Python 3 stdlib | Package code lives under [`src/amon`](../../src/amon); no third-party Python dependency is required |
| Command entry | Checkout shim plus module entry | [`amon`](../../amon) injects the source directory onto `sys.path`; [`src/amon/__main__.py`](../../src/amon/__main__.py) supports `python -m amon` |
| CLI parsing | `argparse` | [`src/amon/cli.py`](../../src/amon/cli.py) owns user-facing flags, positional session-id mode, direct tail/snapshot dispatch, and sessions/xpanes mode dispatch |
| Agent support | Adapter registry | [`src/amon/agents/base.py`](../../src/amon/agents/base.py), [`src/amon/agents/claude.py`](../../src/amon/agents/claude.py), [`src/amon/agents/codex.py`](../../src/amon/agents/codex.py), and [`src/amon/agents/registry.py`](../../src/amon/agents/registry.py) isolate runtime-specific command, path, event, and inline-session behavior |
| Session source | JSONL logs | [`src/amon/jsonl.py`](../../src/amon/jsonl.py) tails and reads recent JSONL records while tolerating malformed lines and truncation |
| Process discovery / liveness | Host commands + PID probe | [`src/amon/host.py`](../../src/amon/host.py) wraps `pgrep`, `ps`, `lsof`, cwd parsing, path scope checks, and `os.kill(pid, 0)` liveness checks |
| Terminal UI | Curses or plain stdout fallback | [`src/amon/ui/state.py`](../../src/amon/ui/state.py), [`src/amon/ui/render.py`](../../src/amon/ui/render.py), and [`src/amon/ui/curses_view.py`](../../src/amon/ui/curses_view.py) separate state transitions, line rendering, and curses drawing |
| Multi-session display | `xpanes` | [`src/amon/modes/xpane.py`](../../src/amon/modes/xpane.py) discovers sessions once and passes encoded specs to independent monitor commands |
| Build / install | Shell scripts plus stdlib zipapp | [`scripts/build-standalone.sh`](../../scripts/build-standalone.sh) creates a standalone executable; [`scripts/install.sh`](../../scripts/install.sh) installs the command and optional Claude wrapper; [`scripts/uninstall.sh`](../../scripts/uninstall.sh) removes them safely |
| Shell integration | Bash profile function | [`scripts/install-claude-session-wrapper.sh`](../../scripts/install-claude-session-wrapper.sh) and [`scripts/uninstall-claude-session-wrapper.sh`](../../scripts/uninstall-claude-session-wrapper.sh) manage the Claude session-id wrapper used by install/uninstall |
| Shared constants and models | Lightweight classes | [`src/amon/constants.py`](../../src/amon/constants.py) centralizes status/scope/default values; [`src/amon/models.py`](../../src/amon/models.py) carries session summaries, list entries, and rendered lines |
| Text formatting | Width-aware helpers | [`src/amon/text.py`](../../src/amon/text.py) handles truncation, tool-detail extraction, display width, and styled segment fitting |
| Tests | `unittest` | [`tests/test_amon.py`](../../tests/test_amon.py) covers adapters, CLI wiring, discovery, aggregation, rendering, tailing, snapshots, install scripts, and xpanes launch |
| Repo-local state | Git ignore rules | Local cairn, Claude state, worktrees, bytecode, build artifacts, and distribution output are excluded by [`.gitignore`](../../.gitignore) |

## 3. Layer Architecture

| Layer | Responsibility | Dependency Direction |
|---|---|---|
| Entry and CLI | [`amon`](../../amon), [`src/amon/__init__.py`](../../src/amon/__init__.py), [`src/amon/__main__.py`](../../src/amon/__main__.py), and [`src/amon/cli.py`](../../src/amon/cli.py) expose the `amon` command, parse flags, choose list/detail/snapshot/tail/xpanes mode, and enforce incompatible flag combinations | Calls mode, monitor, and session-resolution APIs |
| Agent adapters | [`src/amon/agents/__init__.py`](../../src/amon/agents/__init__.py), [`src/amon/agents/base.py`](../../src/amon/agents/base.py), [`src/amon/agents/claude.py`](../../src/amon/agents/claude.py), [`src/amon/agents/codex.py`](../../src/amon/agents/codex.py), and [`src/amon/agents/registry.py`](../../src/amon/agents/registry.py) define runtime-specific command detection, inline detection, session-path lookup, event formatting, metadata extraction, and terminal status inference | Feeds discovery, resolution, summary, and monitor formatting without those modules branching on raw runtime shapes |
| Host process utilities | [`src/amon/host.py`](../../src/amon/host.py) wraps shell process discovery, process cwd lookup, command lookup, liveness checks, command splitting, realpath normalization, and current-directory scope matching | Used by adapters, discovery, resolution, snapshots, and detail views |
| Session discovery / resolution | [`src/amon/sessions/__init__.py`](../../src/amon/sessions/__init__.py), [`src/amon/sessions/discovery.py`](../../src/amon/sessions/discovery.py), and [`src/amon/sessions/resolve.py`](../../src/amon/sessions/resolve.py) convert live processes or session ids into session records, active PIDs, encoded xpanes specs, and stable display titles | Produces concrete session records for list/detail/tail/snapshot consumers |
| Session summarization | [`src/amon/sessions/summary.py`](../../src/amon/sessions/summary.py) reads log metadata, infers running/failed/exited/unknown status, aggregates multiple paths/PIDs into one session row, assigns project labels, filters searches, and groups rows by status | Feeds UI state with display-ready `SessionEntry` values from [`src/amon/models.py`](../../src/amon/models.py) |
| Monitor runtime | [`src/amon/jsonl.py`](../../src/amon/jsonl.py), [`src/amon/monitor/__init__.py`](../../src/amon/monitor/__init__.py), [`src/amon/monitor/tail.py`](../../src/amon/monitor/tail.py), and [`src/amon/monitor/snapshot.py`](../../src/amon/monitor/snapshot.py) implement incremental tailing, direct event formatting, idle warnings, process-end detection, recent detail lines, and one-shot snapshot status/exit codes | Consumes resolved session paths and adapter formatting; has no discovery UI responsibility |
| Sessions mode | [`src/amon/modes/__init__.py`](../../src/amon/modes/__init__.py) and [`src/amon/modes/sessions.py`](../../src/amon/modes/sessions.py) choose curses when stdout is interactive and plain rendered lines when output is captured, then bridge discovery, state, rendering, and direct detail views | Keeps CLI thin while allowing tests to use non-curses output paths |
| Xpanes mode | [`src/amon/modes/xpane.py`](../../src/amon/modes/xpane.py) validates the `xpanes` dependency, discovers sessions, encodes session specs, sets terminal titles, and starts one independent monitor command per session | Reuses direct monitor entrypoints instead of multiplexing JSONL streams in-process |
| UI state and rendering | [`src/amon/ui/__init__.py`](../../src/amon/ui/__init__.py), [`src/amon/ui/state.py`](../../src/amon/ui/state.py), [`src/amon/ui/render.py`](../../src/amon/ui/render.py), and [`src/amon/ui/curses_view.py`](../../src/amon/ui/curses_view.py) manage list/detail selection, search, inline toggling, hidden finished sessions, live detail tailing, width-aware rows, status icons, colors, and curses key handling | Depends on summary and monitor APIs; does not discover processes directly except through mode callbacks |
| Install / build scripts | [`scripts/build-standalone.sh`](../../scripts/build-standalone.sh), [`scripts/install.sh`](../../scripts/install.sh), [`scripts/uninstall.sh`](../../scripts/uninstall.sh), [`scripts/install-claude-session-wrapper.sh`](../../scripts/install-claude-session-wrapper.sh), and [`scripts/uninstall-claude-session-wrapper.sh`](../../scripts/uninstall-claude-session-wrapper.sh) build the zipapp, copy or symlink the command, and install/remove the managed Claude wrapper block | Operational shell layer around the Python package |
| Test harness | [`tests/__init__.py`](../../tests/__init__.py) and [`tests/test_amon.py`](../../tests/test_amon.py) exercise the package through imported modules, fixture-like temporary JSONL files, host-command mocks, curses-free renderers, and shell-script subprocesses | Guards both package internals and command/install behavior |

The core architectural constraint remains that a live monitor instance owns exactly one session stream. The default sessions view is an index/detail controller around session records, and Mode B is a launcher around independent single-session monitors rather than an in-process multiplexer.

## 4. Integration Points

| Integration | Purpose | Current Contract |
|---|---|---|
| Claude JSONL logs | Session input for list, detail, tail, snapshot, and xpanes modes | [`src/amon/agents/claude.py`](../../src/amon/agents/claude.py) resolves `$HOME/.claude/projects/{cwd-slug}/{session-id}.jsonl` when `--session-id` is present, otherwise chooses the newest JSONL under the process cwd's Claude project directory |
| Codex JSONL logs | Session input for list, detail, tail, snapshot, and xpanes modes | [`src/amon/agents/codex.py`](../../src/amon/agents/codex.py) parses `lsof` output for open `.codex/sessions/**/*.jsonl` files and picks the newest per PID unless `--codex-all-sessions` is set |
| Host process table | Discovery, cwd scoping, inline detection, and lifecycle checks | [`src/amon/sessions/discovery.py`](../../src/amon/sessions/discovery.py) asks adapter patterns for candidate PIDs, filters non-agent commands, applies `--current` cwd scope, and passes inline state into session records |
| Terminal UI | Interactive session list/detail and non-interactive output | [`src/amon/modes/sessions.py`](../../src/amon/modes/sessions.py) uses curses only when stdout is a TTY; captured output receives rendered plain lines from [`src/amon/ui/render.py`](../../src/amon/ui/render.py) |
| `xpanes` | Visual separation for multiple monitors | [`src/amon/modes/xpane.py`](../../src/amon/modes/xpane.py) requires `xpanes`; missing dependency exits with code `3` |
| Shell profile | Claude session-id injection | [`scripts/install-claude-session-wrapper.sh`](../../scripts/install-claude-session-wrapper.sh) writes a managed `claude()` function to `~/.bash_profile` by default; calls with `--session-id`, `--resume`, or `--continue` bypass injection |
| Standalone artifact | Copy-style command installation | [`scripts/build-standalone.sh`](../../scripts/build-standalone.sh) copies [`src/amon`](../../src/amon) into a temporary zipapp build tree and emits the standalone command artifact |
| Local agent instructions | Runtime collaboration rules | [`CLAUDE.md`](../../CLAUDE.md) and [`AGENTS.md`](../../AGENTS.md) describe local project-agent workflow outside the CLI runtime |

## 5. Data Flow Examples

### 5.1 Default Sessions View

1. User runs `amon`, `amon --current`, or `amon -i`.
2. [`src/amon/cli.py`](../../src/amon/cli.py) dispatches to `run_sessions_mode()` in [`src/amon/modes/sessions.py`](../../src/amon/modes/sessions.py).
3. [`src/amon/sessions/discovery.py`](../../src/amon/sessions/discovery.py) finds Claude/Codex processes, applies current-directory and inline filters, and resolves JSONL paths through the adapter registry.
4. [`src/amon/sessions/summary.py`](../../src/amon/sessions/summary.py) reads each log, extracts metadata/command summaries, infers terminal status, aggregates duplicate session ids, and assigns project labels.
5. [`src/amon/ui/state.py`](../../src/amon/ui/state.py) merges new rows into the list state, preserves disappeared running sessions as exited, applies search/hidden/inline filters, and tracks selection.
6. [`src/amon/ui/render.py`](../../src/amon/ui/render.py) renders grouped rows and status counts; [`src/amon/ui/curses_view.py`](../../src/amon/ui/curses_view.py) draws them interactively when available.

### 5.2 Session Detail, Tail, And Snapshot

1. User runs `amon <session-id>`, `amon --session-id <id>`, or `amon --session-id <id> --once`.
2. [`src/amon/sessions/resolve.py`](../../src/amon/sessions/resolve.py) asks the adapter registry to resolve the id to the newest matching Claude or Codex JSONL path.
3. Detail mode builds a `SessionEntry` through [`src/amon/ui/state.py`](../../src/amon/ui/state.py), loads recent lines from [`src/amon/monitor/tail.py`](../../src/amon/monitor/tail.py), and tails live records only while the session is running or unknown.
4. Direct tail mode primes [`src/amon/jsonl.py`](../../src/amon/jsonl.py) at EOF, emits formatted assistant/tool activity, prints one idle warning after the configured threshold, and exits when the PID disappears or an adapter-recognized terminal event arrives.
5. Snapshot mode in [`src/amon/monitor/snapshot.py`](../../src/amon/monitor/snapshot.py) scans the last useful event, compares file mtime with `--idle-threshold`, resolves `process=alive|exited|unknown`, and returns exit codes `0`, `1`, `2`, or `4`.

### 5.3 Xpanes Launch

1. User runs `amon xpane`, `amon xpane --current`, or `amon xpane -i`.
2. [`src/amon/modes/xpane.py`](../../src/amon/modes/xpane.py) verifies `xpanes`, discovers sessions once, and base64-url encodes `{agent,pid,path}` specs through [`src/amon/sessions/resolve.py`](../../src/amon/sessions/resolve.py).
3. The xpanes command template sets each pane title by calling `amon --session-title {spec}`.
4. Each pane runs the same command entrypoint with `--session-spec`, `--idle-threshold`, and forced color, so every pane owns a single session stream.

### 5.4 Build, Install, And Cleanup

1. User runs [`scripts/build-standalone.sh`](../../scripts/build-standalone.sh), which copies [`src/amon`](../../src/amon) into a temporary build tree and uses `python3 -m zipapp` to create the standalone command artifact.
2. User runs [`scripts/install.sh`](../../scripts/install.sh), which either copies the standalone artifact into the selected bin directory or creates a symlink to [`amon`](../../amon) when `--source-symlink` is set.
3. Unless `--no-claude-wrapper` is set, [`scripts/install.sh`](../../scripts/install.sh) delegates wrapper installation to [`scripts/install-claude-session-wrapper.sh`](../../scripts/install-claude-session-wrapper.sh).
4. [`scripts/uninstall.sh`](../../scripts/uninstall.sh) removes the installed command only when it can identify it as `amon` or when `--force` is supplied, then delegates wrapper cleanup to [`scripts/uninstall-claude-session-wrapper.sh`](../../scripts/uninstall-claude-session-wrapper.sh).

## 6. Configuration System

| Surface | Meaning | Default |
|---|---|---|
| `amon` | Open the default sessions TUI/list output | sessions mode |
| `amon xpane` | Open one xpanes pane per discovered session | requires `xpanes` |
| Positional `<session-id>` | Resolve a Claude or Codex id and open one detail view | unset |
| `--current` | Limit discovery modes to processes whose cwd is under the current directory | false |
| `--session-id` | Resolve one known Claude or Codex session id | unset |
| `--once` | Emit one snapshot line with idle and process state, then exit | false |
| `--idle-threshold` | Seconds without useful activity before idle warning/status | `60.0` |
| `--codex-all-sessions` | Include every open Codex JSONL for a PID in discovery views | false |
| `-i`, `--inline-only` | Show only inline Claude `-p` / `--print` and direct `codex exec` sessions in discovery modes | false |
| `--lines` | Recent log lines loaded in detail views | `200` |
| `--color` | Control color for TUI and direct tail output; snapshots stay plain | auto for TUI, never for tail |
| `--session-path` | Hidden direct path worker entrypoint | unset |
| `--session-spec` | Hidden xpanes worker entrypoint | unset |
| `--session-title` | Hidden title renderer for xpanes pane labels | unset |
| `--pid` | Hidden PID lifecycle monitor for direct worker calls and xpanes panes | unset |
| Installer `--bin-dir` / `AMON_BIN_DIR` | Command install directory | `/usr/local/bin` |
| Installer `--name` / `AMON_COMMAND_NAME` | Installed command name | `amon` |
| Installer `--profile` / `AMON_CLAUDE_PROFILE` | Shell profile path for Claude wrapper install/removal | `~/.bash_profile` |
| Installer `--source-symlink` | Install a symlink to the checkout shim instead of copied zipapp | false |
| Installer `--no-claude-wrapper` | Skip Claude wrapper install/removal | false |
| Uninstaller `--force` | Remove command path even if it cannot be identified as `amon` | false |
| `AMON_ASCII_ICONS` | Force ASCII status icons in render output | unset |

## 7. Drift Watch

(현재 발견된 어긋남 없음 — sync 기준 2026-05-20)

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
- [Sessions mode checklist](../tasks/260519-211154-sessions-mode-checklist.md)
