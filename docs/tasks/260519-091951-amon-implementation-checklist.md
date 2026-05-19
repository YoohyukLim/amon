# amon Implementation Checklist

This checklist is the execution-facing view of
`260519-090729-amon-implementation-v2.md`. Use it from the
`feature/amon-implementation` worktree only.

## Ground Rules

- [x] Work only inside `.worktrees/amon-implementation`.
- [x] Keep `amon` as one executable Python file with stdlib imports only.
- [x] Keep tests in `tests/test_amon.py` and fixtures in `tests/fixtures/`.
- [x] Do not copy real Claude/Codex session contents into fixtures.
- [x] Run `python3 -m unittest tests.test_amon -v` at every task boundary.
- [x] Commit only after a green milestone, not after every tiny edit.

## Task 0: Preflight and Fixtures

- [x] Confirm `python3 --version`.
- [x] Confirm `lsof`, `pgrep`, and `xpanes` exist.
- [x] Confirm recent Claude JSONL exists.
- [x] Confirm recent Codex JSONL exists.
- [x] Create synthetic Claude fixture preserving observed assistant
  `message.content[]` text/tool_use shape.
- [x] Create synthetic Codex fixture preserving observed `response_item`
  message/function_call shape.
- [x] Create initial `tests/test_amon.py` loader harness.
- [x] Confirm fixture files parse as JSONL.
- [x] Confirm unittest currently fails only because `amon` does not exist yet.

Evidence:

- `python3 --version` -> `Python 3.13.0`.
- `lsof` -> `/usr/sbin/lsof`.
- `pgrep` -> `/usr/bin/pgrep`.
- `xpanes` -> `/opt/homebrew/bin/xpanes`.
- Recent Claude JSONL and Codex JSONL paths were found under the expected home
  directories.
- `python3 -m unittest tests.test_amon -v` currently raises `FileNotFoundError`
  for missing `amon`, which Task 1 is expected to create.

## Task 1: Skeleton and Test Harness

- [x] Create executable `amon` with `#!/usr/bin/env python3`.
- [x] Add minimal `main(argv=None) -> int`.
- [x] Ensure `tests/test_amon.py` imports extensionless `amon` via
  `SourceFileLoader`.
- [x] Add a basic import/smoke test.
- [x] Make `./amon --help` return successfully, even if help is minimal.
- [x] Run `chmod +x amon`.
- [x] Run `python3 -m unittest tests.test_amon -v`.
- [x] Run `./amon --help`.

## Task 2: Path and Session Resolution

- [x] Add `cwd_to_claude_slug`.
- [x] Test dotted usernames and dotfile directories.
- [x] Add `parse_lsof_cwd` using `split(None, 8)`.
- [x] Test `lsof` cwd paths containing spaces.
- [x] Add `pick_latest_jsonl`.
- [x] Test latest mtime and empty directory behavior.
- [x] Add `resolve_claude_session_path(pid)`.
- [x] Add `parse_lsof_codex_jsonls`.
- [x] Test `.codex/sessions/*.jsonl` inclusion and `.codex/log/*.log`
  exclusion.
- [x] Add `resolve_codex_session_paths(pid, all_sessions=False)`.
- [x] Filter non-existing Codex session paths before newest-mtime selection.
- [x] Test default newest selection and all-session mode.
- [x] Add deterministic `resolve_path_from_session_id`.
- [x] Test Claude exact filename match.
- [x] Test Codex newest matching filename behavior.
- [x] Run `python3 -m unittest tests.test_amon -v`.

## Task 3: Event Formatting

- [x] Add `_truncate` that collapses newlines and limits display length.
- [x] Add `_tool_detail` for `command`, `file_path`, `path`, and fallback keys.
- [x] Add `_format_claude_event` for assistant `message.content[]` text.
- [x] Add `_format_claude_event` for assistant `message.content[]` tool_use.
- [x] Keep legacy `attachment.tool_use` fallback.
- [x] Add `_format_codex_event` for assistant `output_text`.
- [x] Add `_format_codex_event` for function_call JSON string arguments.
- [x] Add `_colorize(kind, text, color)`.
- [x] Ignore Claude user/tool_result/file-history/permission/metadata events.
- [x] Ignore Codex reasoning/token/user/function_call_output events.
- [x] Add `format_event(ev, agent, sid_short, color="never")`.
- [x] Add `color="never"` no-ANSI tests.
- [x] Add `color="always"` ANSI-present tests.
- [x] Run `python3 -m unittest tests.test_amon -v`.

## Task 4: JSONL Tail Reader

- [x] Add `JsonlTail`.
- [x] Test initial read.
- [x] Test second read with no new data.
- [x] Test appended data.
- [x] Test malformed JSON line skip.
- [x] Test empty line skip.
- [x] Test truncation resets offset.
- [x] Test missing file returns empty list.
- [x] Run `python3 -m unittest tests.test_amon -v`.

## Task 5: Idle and Process State

- [x] Add `IdleStateMachine`.
- [x] Test no warning before threshold.
- [x] Test one warning at threshold.
- [x] Test no repeated warning.
- [x] Test touch re-arms warning.
- [x] Add `_pid_alive(pid)`.
- [x] Test `ProcessLookupError` means dead.
- [x] Test `PermissionError` means alive.
- [x] Decide and test fallback behavior for other `OSError`.
- [x] Run `python3 -m unittest tests.test_amon -v`.

## Task 6: Mode A Tail

- [x] Add `run_tail(session_path, agent, sid_short, idle_threshold, pid=None,
  poll_interval=1.0, color="never")`.
- [x] Prime tail once to avoid replaying existing history.
- [x] Print only useful formatted events.
- [x] Touch idle clock only when at least one formatted event was printed.
- [x] Print idle warning once after threshold.
- [x] Reset idle warning after new useful event.
- [x] Print `AGENT EXITED` when provided PID disappears.
- [x] Handle SIGINT and SIGTERM with exit 0.
- [x] Add loop tests only through simple injected clock/sleep/max-iteration
  seams if needed.
- [x] Run `python3 -m unittest tests.test_amon -v`.

## Task 7: Mode A Snapshot

- [x] Add `snapshot_status(...) -> tuple[int, str]`.
- [x] Add `run_snapshot(...) -> int`.
- [x] Pin snapshot output format as
  `HH:MM:SS [agent/sid] status={working|idle} idle=Ns last=<kind details>`.
- [x] Scan whole file for last useful formatted event.
- [x] Use file mtime for idle seconds.
- [x] Return exit 0 when working.
- [x] Return exit 2 when idle.
- [x] Return exit 1 when the session path is missing.
- [x] Test working status.
- [x] Test idle status.
- [x] Test no useful events.
- [x] Test malformed JSON before valid event.
- [x] Test color passthrough if snapshot uses colored formatting.
- [x] Run `python3 -m unittest tests.test_amon -v`.

## Task 8: Non-Interactive Discovery

- [x] Add `candidate_pids(patterns)`.
- [x] Add `process_command(pid)`.
- [x] Add `is_claude_noninteractive(cmdline)`.
- [x] Add `is_codex_exec(cmdline)`.
- [x] Add `discover_active_sessions(codex_all=False)`.
- [x] Use `pgrep` only for candidate PID collection.
- [x] Use `ps -o command= -p <pid>` as the authoritative argv source.
- [x] Deduplicate candidate PIDs.
- [x] Accept Claude `-p` and `--print`.
- [x] Reject Claude interactive and `--resume` without print.
- [x] Accept real vendor `codex exec`.
- [x] Match Codex exec only when `basename(argv[0]) == "codex"` and
  `argv[1] == "exec"` after `shlex.split`.
- [x] Reject Codex app-server and plain interactive `codex`.
- [x] Handle node wrapper `codex exec` deterministically.
- [x] Unit-test discovery by monkeypatching candidate/process/resolver helpers.
- [x] Run `python3 -m unittest tests.test_amon -v`.

## Task 9: Mode B Launcher

- [x] Add `encode_session_spec(session)`.
- [x] Add `decode_session_spec(spec)`.
- [x] Encode `{agent, pid, path}` as URL-safe base64 JSON.
- [x] Add `run_mode_b(idle_threshold, codex_all, color="always")`.
- [x] Exit 3 with error if `xpanes` is missing.
- [x] Exit 0 with message if no sessions are discovered.
- [x] Invoke xpanes with `--session-spec {}`.
- [x] Include `--idle-threshold N` in the xpanes template.
- [x] Force spawned pane color with `--color=always`.
- [x] Ensure spawned monitors decode `--session-spec` and run Mode A tail with
  PID tracking.
- [x] Preserve paths containing spaces through spec encoding.
- [x] Test encode/decode round trip.
- [x] Test missing xpanes behavior.
- [x] Test no-session behavior.
- [x] Test xpanes command shape.
- [x] Run `python3 -m unittest tests.test_amon -v`.

## Task 10: CLI Wiring

- [x] Add public `--session-id`.
- [x] Add public `--once`.
- [x] Add public `--idle-threshold`.
- [x] Add public `--codex-all-sessions`.
- [x] Add public `--color {always,never,auto}`.
- [x] Add internal `--session-path`.
- [x] Add internal `--session-spec`.
- [x] Add debug `--pid`.
- [x] No session args run Mode B.
- [x] `--session-id` resolves and runs Mode A.
- [x] `--session-path` runs Mode A directly.
- [x] `--session-spec` decodes agent/path/pid and runs Mode A.
- [x] `--once` chooses snapshot.
- [x] Direct Mode A defaults to `--color=never`.
- [x] Mode B spawned monitors use `--color=always`.
- [x] Test `main(["--help"])`.
- [x] Test missing `--session-id` exits 1.
- [x] Test `--session-path --once` calls snapshot.
- [x] Test `--session-spec` calls tail with decoded pid.
- [x] Test no-arg CLI calls Mode B.
- [x] Run `python3 -m unittest tests.test_amon -v`.
- [x] Run `./amon --help`.

## Task 11: README and Smoke Tests

- [x] Create root `README.md`.
- [x] Document install via copy or symlink.
- [x] Document Mode B `xpanes` requirement.
- [x] Document all public usage examples.
- [x] Document exit codes 0, 1, 2, and 3.
- [x] Document color policy.
- [x] Document idle false positives during long-running tools.
- [x] Document no dynamic pane addition after Mode B starts.
- [x] Run `python3 -m unittest tests.test_amon -v`.
- [x] Run `./amon --help`.
- [x] Run Claude snapshot smoke test against a recent session id.
- [x] Run Codex snapshot smoke test against a recent session path.
- [x] Check Mode B smoke precondition; skipped because no active
  non-interactive session was discovered.

## Milestone Commits

- [ ] Skipped: user requested no commits unless explicitly necessary; changes
  are left uncommitted for main-session review.

## Final Acceptance

- [x] All unittest tests pass.
- [x] `./amon --help` shows the three intended modes.
- [x] Claude snapshot does not produce `last=(no events)` for a session with
  assistant text/tool events.
- [x] Codex snapshot works for a recent Codex JSONL.
- [x] Mode B missing-xpanes unit scenario exits 3.
- [x] Mode B launcher uses encoded per-session specs.
- [x] No external Python packages are imported.
- [x] Repository still has one executable `amon`, tests, fixtures, README, and
  docs only.
