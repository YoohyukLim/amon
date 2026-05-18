# amon Architecture

**Version**: 1  |  **Last Updated**: 2026-05-19

<!-- atlas-managed: do not delete sections; edit content freely -->
<!-- atlas-version: 1 -->

## 1. Overview

`amon` is a planned single-file command line monitor for non-interactive Claude and Codex agent sessions. It reads the JSONL session logs those tools append to disk, formats selected events into short status lines, detects silent idle periods, and can launch one monitor per active session through `xpanes`.

The repository is currently at the specification stage. The accepted behavior is captured in ADRs under [docs/arch](../arch/) and the implementation sequence is captured in [260518-231933-amon-implementation.md](../tasks/260518-231933-amon-implementation.md); the executable and tests have not been created yet.

## 2. Tech Stack

| Area | Decision | Notes |
|---|---|---|
| Language | Python 3 | Standard library only |
| Packaging | Single executable file | No package manager or install metadata planned |
| Session source | JSONL logs | Claude and Codex use different event shapes |
| Process discovery | Host process inspection | Uses platform commands from the implementation plan |
| Multi-session display | `xpanes` | Runtime dependency for Mode B only |
| Tests | `unittest` | Planned alongside the single executable |

## 3. Layer Architecture

| Layer | Responsibility | Dependency Direction |
|---|---|---|
| CLI parsing | Select Mode A tail, Mode A snapshot, or Mode B discovery from flags | Calls launcher or single-session monitor |
| Process discovery | Find active non-interactive Claude and Codex processes | Feeds PID and session candidates to resolvers |
| Session resolution | Map a process or session id to the relevant JSONL file | Feeds a concrete path to the monitor |
| JSONL tailing | Track file offsets, parse appended JSON lines, tolerate malformed lines | Feeds normalized event dictionaries upward |
| Event formatting | Render tool calls and assistant messages into one-line output | Avoids lifecycle policy decisions |
| Idle detection | Mark silence after the configured threshold | Uses the same tail loop clock |
| Mode B launcher | Spawn one single-session monitor per discovered session with `xpanes` | Does not multiplex events in-process |

The core architectural constraint is that a monitor instance owns exactly one session stream. Mode B is a launcher, not a separate multi-tail runtime.

## 4. Integration Points

| Integration | Purpose | Current Contract |
|---|---|---|
| Claude JSONL logs | Mode A and Mode B session input | Resolved from project directory slug and latest session file |
| Codex JSONL logs | Mode A and Mode B session input | Resolved from open session files, defaulting to newest per PID |
| Host process table | Mode B discovery | Includes non-interactive sessions only |
| `xpanes` | Visual separation for multiple monitors | Required for Mode B; no fallback |
| Shell install path | User-local command availability | Planned manual copy or symlink by user |

## 5. Data Flow Examples

### 5.1 Mode A Tail

1. User runs `amon --session-id <id>`.
2. CLI resolves the id to a JSONL session path.
3. Tail loop starts at current EOF to avoid replaying history.
4. New JSONL records are parsed and passed to the formatter.
5. Formatter prints selected tool/message events.
6. Idle detector prints a warning if no event arrives before the threshold.

### 5.2 Mode A Snapshot

1. User runs `amon --session-id <id> --once`.
2. CLI resolves the session path and scans the file for the last meaningful event.
3. Snapshot compares file mtime with the idle threshold.
4. Command prints one status line and exits with success or idle status.

### 5.3 Mode B Discovery

1. User runs `amon` with no session flags.
2. Discovery filters Claude and Codex processes to non-interactive invocations.
3. Resolvers convert each surviving process into one or more session paths.
4. Launcher invokes `xpanes` with a single-session `amon` command template.
5. Each pane runs an independent Mode A tail.

## 6. Configuration System

The planned public configuration surface is flag-based:

| Flag | Meaning | Default |
|---|---|---|
| `--session-id` | Monitor one known session id | unset |
| `--once` | Emit one snapshot line and exit | false |
| `--idle-threshold` | Seconds of silence before idle warning/status | 60 |
| `--codex-all-sessions` | Include every open Codex JSONL for a PID in Mode B | false |
| `--color` | Control output color | never |

Mode B forces color for spawned panes while direct Mode A remains plain by default.

## 7. Drift Watch

(현재 발견된 어긋남 없음 — 1차 init 기준)

## 8. Related Documents

- [260518-231927-single-command-flags.md](../arch/260518-231927-single-command-flags.md)
- [260518-231928-mode-b-xpanes-spawn.md](../arch/260518-231928-mode-b-xpanes-spawn.md)
- [260518-231929-python-stdlib.md](../arch/260518-231929-python-stdlib.md)
- [260518-231930-stuck-silent-threshold.md](../arch/260518-231930-stuck-silent-threshold.md)
- [260518-231931-codex-multi-jsonl-default.md](../arch/260518-231931-codex-multi-jsonl-default.md)
- [260518-231932-discovery-noninteractive-only.md](../arch/260518-231932-discovery-noninteractive-only.md)
- [260518-231933-amon-implementation.md](../tasks/260518-231933-amon-implementation.md)
