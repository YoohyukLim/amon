# amon Implementation Plan v2

## Purpose

This document reviews `docs/tasks/260518-231933-amon-implementation.md` and
turns it into the execution plan to use before writing code.

The original plan remains useful as a task-by-task skeleton, but several details
must be corrected before implementation:

- Real Claude JSONL events do not primarily use the planned
  `attachment.type == "tool_use"` shape.
- Mode B must pass PID information into spawned monitors, otherwise
  `AGENT EXITED` cannot work in xpanes panes.
- Process discovery should treat `pgrep` as candidate discovery only and verify
  the actual command line with `ps`.
- The `--color` flag needs an implementation decision, not only parser wiring.

## Sources Reviewed

- `docs/arch/260518-231927-single-command-flags.md`
- `docs/arch/260518-231928-mode-b-xpanes-spawn.md`
- `docs/arch/260518-231929-python-stdlib.md`
- `docs/arch/260518-231930-stuck-silent-threshold.md`
- `docs/arch/260518-231931-codex-multi-jsonl-default.md`
- `docs/arch/260518-231932-discovery-noninteractive-only.md`
- `docs/tasks/260518-231933-amon-implementation.md`
- Recent local Claude and Codex JSONL files, inspected only for structure and
  field names.

## Current Environment Notes

- Python is available as `/opt/homebrew/bin/python3`; observed version:
  `Python 3.14.5`.
- `lsof` is available at `/usr/sbin/lsof`.
- `pgrep` is available at `/usr/bin/pgrep`.
- `xpanes` is available at `/opt/homebrew/bin/xpanes`.
- Recent Claude JSONL exists under `~/.claude/projects/*/*.jsonl`.
- Recent Codex JSONL exists under `~/.codex/sessions/YYYY/MM/DD/*.jsonl`.

Do not copy real session contents into repository fixtures. Create small
synthetic fixtures that preserve only the observed schema shape.

## Review Findings

### 1. Claude Formatter Schema Must Change

The original Task 5 assumes this fixture shape:

```json
{"type":"attachment","attachment":{"type":"tool_use","tool_name":"Edit"}}
```

Recent local Claude JSONL instead showed assistant events like:

```json
{
  "type": "assistant",
  "message": {
    "role": "assistant",
    "content": [
      {"type": "text", "text": "..."},
      {"type": "tool_use", "name": "Bash", "input": {"command": "..."}}
    ]
  }
}
```

Plan change:

- Implement Claude formatting from `type == "assistant"` and
  `message.content[]`.
- Emit `Tool <name>` for content objects with `type == "tool_use"`.
- Emit `Msg <first line>` for content objects with `type == "text"`.
- Keep the old `attachment.tool_use` branch as a compatibility fallback only.

### 2. Mode B Needs a Per-Pane Session Spec

The original Task 8 ultimately launches xpanes with only `session_path`.
That loses `agent` and `pid`, so spawned panes cannot:

- report `AGENT EXITED`;
- avoid weak path-based agent inference;
- support future formatter differences cleanly.

Plan change:

- Introduce an internal `--session-spec` flag.
- Encode each discovered session as URL-safe base64 JSON:
  `{"agent":"claude","pid":123,"path":"/.../session.jsonl"}`.
- Launch xpanes with `amon --session-spec {}`.
- Decode the spec in `main()` and call `run_tail(..., pid=pid)`.
- Keep `--session-path` as an internal debugging escape hatch.

This stays stdlib-only via `json` and `base64`.

### 3. Process Discovery Should Use `ps` After `pgrep`

Local `pgrep -fl` output can include wrapper shells or command lines that merely
contain the search word. The plan text already says to inspect `ps`, but the
sample code filters directly on the `pgrep` output.

Plan change:

- Use `pgrep` only to find candidate PIDs.
- For every candidate PID, run `ps -o command= -p <pid>`.
- Apply `is_claude_noninteractive()` and `is_codex_exec()` to the `ps` command
  line.
- Deduplicate PIDs from overlapping candidate searches.
- Prefer anchored candidate patterns when available, but keep filtering as the
  authoritative gate.

### 4. `_pid_alive` Must Treat Permission Denial As Alive

`os.kill(pid, 0)` may raise `PermissionError` for a process that exists but is
not signalable by the current user.

Plan change:

- `ProcessLookupError` means dead.
- `PermissionError` means alive.
- Other `OSError` values should be treated conservatively as dead only when
  tests pin that behavior.

### 5. `--color` Needs Real Behavior

The ADR says Mode A defaults to plain output and Mode B forces color. The
original plan parses `--color` but never colors output.

Plan change:

- Add a tiny ANSI helper:
  - `Tool` dim/cyan or plain depending on color mode.
  - `Msg` plain.
  - idle warning yellow.
  - `AGENT EXITED` dim.
- `--color=never` emits no ANSI.
- `--color=always` emits ANSI.
- `--color=auto` emits ANSI only when stdout is a TTY.
- Mode B passes `--color=always` in the xpanes template.

Keep tests focused on "never has no ANSI" and "always contains ANSI" rather
than exact color choices.

### 6. Session ID Resolution Should Be Deterministic

The original Codex session lookup returns the first `rglob()` match containing
the session id substring. That can be nondeterministic if several files match.

Plan change:

- For Claude: exact filename stem match first.
- For Codex: collect matching files, then pick newest mtime by default.
- If direct `--session-path` is provided, bypass id search.
- If no match exists, exit 1 with a specific error.

## Implementation Plan

Implementation should happen in a worktree, not directly on `master`, because
this is multi-file, nontrivial work.

Suggested branch:

```bash
git worktree add .worktrees/amon-implementation -b feature/amon-implementation
cd .worktrees/amon-implementation
```

All paths below are relative to that worktree after creation.

### Task 0: Preflight and Fixtures

Goal: lock down external assumptions before writing application logic.

Files:

- create `tests/fixtures/claude_session.jsonl`
- create `tests/fixtures/codex_session.jsonl`
- create `tests/test_amon.py`

Steps:

1. Confirm `python3 --version`.
2. Confirm `command -v lsof`, `command -v pgrep`, and `command -v xpanes`.
3. Inspect one recent Claude JSONL structurally and write a synthetic fixture
   with:
   - assistant text content;
   - assistant tool_use content with `name` and `input.command`;
   - assistant tool_use content with `input.file_path`;
   - user tool_result event that should be ignored.
4. Inspect one recent Codex JSONL structurally and write a synthetic fixture
   with:
   - `response_item` message, role assistant, `output_text`;
   - `response_item` function_call with JSON string arguments;
   - ignored reasoning and function_call_output events.
5. Add the test import loader for the future executable `amon`.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

Expected at this point: import failure or missing file failure until Task 1
creates `amon`.

### Task 1: Skeleton and Test Harness

Goal: create a runnable single-file script and a stable test harness.

Files:

- create `amon`
- modify `tests/test_amon.py`

Functions to add:

- `main()`
- placeholder public helpers referenced by tests only when needed.

Test coverage:

- script imports cleanly through `importlib.util.spec_from_file_location`;
- `main([])` style parsing is possible by allowing an optional argv parameter;
- `./amon --help` works once argparse is added later.

Implementation notes:

- Prefer `def main(argv: Optional[list] = None) -> int` to make CLI tests
  easy without patching `sys.argv`.
- Use `#!/usr/bin/env python3`.
- Run `chmod +x amon`.

Verification:

```bash
python3 -m unittest tests.test_amon -v
./amon --help
```

The help command can be minimal until CLI wiring is complete.

### Task 2: Path and Session Resolution

Goal: resolve concrete JSONL paths from process and session identifiers.

Functions to add:

- `cwd_to_claude_slug(cwd: str) -> str`
- `parse_lsof_cwd(output: str) -> Optional[str]`
- `pick_latest_jsonl(directory: str) -> Optional[str]`
- `resolve_claude_session_path(pid: int) -> Optional[str]`
- `parse_lsof_codex_jsonls(output: str) -> list[str]`
- `resolve_codex_session_paths(pid: int, all_sessions: bool = False) -> list[str]`
- `resolve_path_from_session_id(sid: str) -> Optional[str]`

Test coverage:

- dotted usernames and dotfile directories in Claude slug conversion;
- `lsof cwd` output where the path contains spaces;
- latest JSONL selection;
- Codex `lsof` parser excludes `.codex/log/*.log`;
- Codex default picks newest existing JSONL;
- `all_sessions=True` returns all parsed session JSONLs;
- session id search is exact for Claude and newest-match for Codex.

Implementation notes:

- Use `line.split(None, 8)` for `lsof` parsing so paths with spaces survive.
- Filter non-existing Codex paths before newest-mtime selection when possible.
- Never shell out through `shell=True`.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

### Task 3: Event Formatting

Goal: render only useful agent activity into one-line status output.

Functions to add:

- `format_event(ev: dict, agent: str, sid_short: str, color: str = "never")`
- `_format_claude_event(ev: dict) -> Optional[tuple[str, str]]`
- `_format_codex_event(ev: dict) -> Optional[tuple[str, str]]`
- `_tool_detail(data: object) -> str`
- `_truncate(s: str, n: int = 80) -> str`
- `_colorize(kind: str, text: str, color: str) -> str`

Claude behavior:

- `type == "assistant"` and content item `type == "tool_use"`:
  `Tool <name> <detail>`.
- `type == "assistant"` and content item `type == "text"`:
  `Msg <first line>`.
- legacy `type == "attachment"` with `attachment.type == "tool_use"`:
  compatibility fallback.
- ignore user/tool_result/file-history/permission/metadata events.

Codex behavior:

- `type == "response_item"`, `payload.type == "function_call"`:
  `Tool <name> <detail>`.
- `type == "response_item"`, `payload.type == "message"`,
  `payload.role == "assistant"`:
  `Msg <first line>`.
- ignore reasoning, token_count, user messages, and function_call_output.

Test coverage:

- synthetic Claude fixture emits both Tool and Msg lines;
- synthetic Codex fixture emits both Tool and Msg lines;
- ignored events return `None`;
- newline text is collapsed to one display line;
- truncation is deterministic;
- `color="never"` has no ANSI;
- `color="always"` contains ANSI for warning/tool cases.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

### Task 4: JSONL Tail Reader

Goal: read appended JSONL safely with offset tracking.

Class to add:

- `JsonlTail`

Behavior:

- first `read_new_lines()` reads from the current offset;
- caller can choose whether to prime by reading once and discarding;
- malformed JSON lines are skipped;
- empty lines are skipped;
- truncation or rotation resets offset to zero when file size is smaller than
  the stored offset;
- missing file returns an empty list rather than crashing.

Test coverage:

- initial read;
- second read with no new data;
- appended data;
- malformed line followed by valid line;
- truncation;
- missing file.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

### Task 5: Idle and Process State

Goal: make time and PID behavior testable before wiring the live loop.

Classes/functions to add:

- `IdleStateMachine`
- `_pid_alive(pid: int) -> bool`
- optionally `format_idle_line(...)`
- optionally `format_exit_line(...)`

Behavior:

- one idle warning after threshold;
- no repeated warning until new event touch;
- touch resets the warning;
- `ProcessLookupError` means process is gone;
- `PermissionError` means process exists.

Test coverage:

- no warning before threshold;
- one warning at threshold;
- no repeat warning;
- re-arm after touch;
- pid-alive helper behavior via monkeypatched `os.kill`.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

### Task 6: Mode A Tail

Goal: stream a single session from EOF and print future useful events.

Function to add:

- `run_tail(session_path, agent, sid_short, idle_threshold, pid=None,
  poll_interval=1.0, color="never") -> int`

Behavior:

- prime `JsonlTail` once to avoid replaying historical events;
- print formatted lines for new events;
- touch idle clock only when at least one useful formatted event appears;
- print idle warning once after threshold;
- print `AGENT EXITED` and return 0 when a provided PID disappears;
- handle SIGINT/SIGTERM by exiting 0.

Test coverage:

- avoid long live-loop tests where possible;
- test pure helpers from Task 5;
- for `run_tail`, use a small max-iteration or injectable clock/sleep only if
  the implementation stays simple.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

### Task 7: Mode A Snapshot

Goal: emit one status line and exit with a script-friendly code.

Functions to add:

- `snapshot_status(...) -> tuple[int, str]`
- `run_snapshot(...) -> int`

Output:

```text
HH:MM:SS [agent/sid] status={working|idle} idle=Ns last=<kind details>
```

Behavior:

- scan the whole file for the last useful formatted event;
- idle seconds use file mtime as the last-write approximation;
- exit 0 when `idle < threshold`;
- exit 2 when `idle >= threshold`;
- malformed lines are ignored;
- missing file exits 1 with an error.

Test coverage:

- working status;
- idle status;
- no useful events;
- malformed JSON before valid event;
- color never/always if snapshot reuses formatting.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

### Task 8: Non-Interactive Discovery

Goal: find active Claude and Codex non-interactive sessions.

Functions to add:

- `candidate_pids(patterns: list[str]) -> list[int]`
- `process_command(pid: int) -> str`
- `is_claude_noninteractive(cmdline: str) -> bool`
- `is_codex_exec(cmdline: str) -> bool`
- `discover_active_sessions(codex_all: bool = False) -> list[dict]`

Behavior:

- `claude` is included only when argv contains `-p` or `--print`.
- `codex` is included only when basename is `codex` and first sub-arg is
  `exec`.
- interactive Claude/Codex app servers are excluded.
- candidate PID collection may overmatch; command-line filters are the
  authoritative gate.
- for Codex, default is newest JSONL per PID; `codex_all=True` includes all.

Test coverage:

- direct Claude print mode accepted;
- Claude interactive and `--resume` without print rejected;
- direct Codex `exec` accepted;
- node wrapper command with `codex exec` should be decided explicitly:
  prefer accepting the real vendor `codex exec` process and ignoring the node
  wrapper if both appear;
- app-server and plain `codex` rejected;
- discovery can be unit-tested by monkeypatching candidate/process/resolver
  helpers.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

### Task 9: Mode B Launcher

Goal: spawn one independent single-session monitor per discovered session.

Functions to add:

- `encode_session_spec(session: dict) -> str`
- `decode_session_spec(spec: str) -> dict`
- `run_mode_b(idle_threshold: int, codex_all: bool, color: str = "always") -> int`

Behavior:

- if `xpanes` is missing, print an error and exit 3;
- if no sessions are discovered, print a short stderr message and exit 0;
- encode `{agent, pid, path}` into URL-safe base64 JSON;
- call xpanes with a template equivalent to:

```bash
amon --session-spec {} --idle-threshold N --color=always
```

- spawned monitor decodes the spec and runs Mode A tail with PID tracking.

Test coverage:

- encode/decode round trip;
- missing xpanes exit code 3 via monkeypatched `shutil.which`;
- no sessions exit 0;
- xpanes command includes `--session-spec`, `--idle-threshold`, and
  `--color=always`;
- session path with spaces survives because the xpanes argument is base64, not
  the raw path.

Verification:

```bash
python3 -m unittest tests.test_amon -v
```

### Task 10: CLI Wiring

Goal: expose the agreed single-command + flag interface.

Public flags:

- `--session-id <id>`
- `--once`
- `--idle-threshold N`
- `--codex-all-sessions`
- `--color {always,never,auto}`

Internal/debug flags:

- `--session-path <path>`
- `--session-spec <base64-json>`
- `--pid <pid>` only for direct debugging; Mode B should prefer
  `--session-spec`.

Behavior:

- no session args means Mode B;
- `--session-id` means Mode A path resolution;
- `--session-path` means Mode A direct path;
- `--session-spec` means Mode A direct path + agent + pid from decoded spec;
- `--once` chooses snapshot instead of tail;
- direct Mode A defaults to `--color=never`;
- Mode B forces spawned panes to `--color=always`.

Test coverage:

- `main(["--help"])` exits through argparse as expected;
- `--session-id` not found exits 1;
- `--session-path --once` calls snapshot;
- `--session-spec` calls tail with decoded pid;
- no args calls Mode B.

Verification:

```bash
python3 -m unittest tests.test_amon -v
./amon --help
```

### Task 11: README and Smoke Tests

Goal: document actual behavior and verify against local reality.

Files:

- create root `README.md`

README must cover:

- install by copying or symlinking the `amon` file;
- Mode B requires xpanes;
- public usage examples;
- exit codes:
  - `0`: ok / working / tail completed;
  - `1`: invalid or unresolved session;
  - `2`: snapshot idle;
  - `3`: xpanes missing for Mode B;
- color policy;
- known idle false positives for long-running tools;
- no dynamic pane addition after Mode B starts.

Smoke tests:

```bash
python3 -m unittest tests.test_amon -v
./amon --help
./amon --session-id <recent-claude-session-id> --once
./amon --session-path <recent-codex-jsonl> --once
```

Mode B smoke test:

```bash
./amon
```

Run Mode B only when at least one non-interactive Claude or Codex process is
active, because otherwise the correct result is "no active sessions".

## Commit Strategy

In the worktree, commit after each green milestone:

1. skeleton + fixtures
2. session resolution
3. event formatting
4. tail/snapshot runtime
5. discovery + xpanes launcher
6. CLI + README + smoke fixes

Use the existing project style for commit messages, for example:

```bash
git commit -m "feat(amon): add session resolution"
```

## Acceptance Criteria

- `python3 -m unittest tests.test_amon -v` passes.
- `./amon --help` shows the three intended modes.
- Snapshot mode works for a recent Claude JSONL and does not report
  `last=(no events)` when the file contains assistant text/tool events.
- Snapshot mode works for a recent Codex JSONL.
- Mode B exits 3 when xpanes is unavailable in a monkeypatched/unit scenario.
- Mode B launches xpanes with encoded per-session specs when xpanes is
  available and sessions are discovered.
- No external Python packages are imported.
- Implementation stays a single executable `amon` plus tests and README.

## Supersedes

Use this plan as the implementation guide. The original
`260518-231933-amon-implementation.md` remains a useful historical plan, but
Task 5, Task 8, and Task 9 should not be followed verbatim.
