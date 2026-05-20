# amon

`amon` monitors local Claude and Codex agent sessions by discovering their
running processes, resolving their JSONL session logs, and showing compact
status/detail views.

It is built for the workflow where several agents may be running at once and
you need a quick answer to:

- which agent sessions are active
- which project each session belongs to
- whether a session is still producing useful activity
- what the latest assistant/tool activity looks like
- whether an agent process has exited or failed

The public command stays simple (`amon`), while the implementation is split into
a Python standard-library-only package. Claude and Codex support live behind
agent adapters, so future agents can be added by implementing a new adapter
instead of rewriting the monitor, TUI, or xpanes launcher.

## Quick Start

Install and run with two commands from a fresh checkout:

```bash
./scripts/install.sh
amon
```

`scripts/install.sh` builds `dist/amon`, copies it to `/usr/local/bin/amon`, and
installs the Claude session wrapper into `~/.bash_profile`. Running `amon` then
opens the sessions TUI for any active Claude or Codex agent sessions. See
[Install Guide](#install-guide) and [Usage Guide](#usage-guide) for options.

## Requirements

- Python 3
- Standard host tools used for discovery: `pgrep`, `ps`, and `lsof`
- Optional: `xpanes` for `amon xpane`

No third-party Python package is required.

## Project Layout

```text
amon                         # checkout shim
src/amon/                    # package implementation
src/amon/agents/             # Claude/Codex adapter implementations
src/amon/sessions/           # discovery, resolution, aggregation
src/amon/monitor/            # tail and snapshot runtime
src/amon/ui/                 # TUI state, rendering, curses driver
src/amon/modes/              # sessions view and xpanes launcher
scripts/build-standalone.sh  # builds dist/amon with stdlib zipapp
scripts/install.sh           # installs amon and the Claude wrapper
scripts/uninstall.sh         # removes amon and the Claude wrapper
tests/                       # unittest regression coverage
```

## Build Guide

Run tests from the repository root:

```bash
python3 -m unittest
```

Run the command directly from a checkout:

```bash
./amon --help
```

Run the package module directly:

```bash
PYTHONPATH=src python3 -m amon --help
```

Build a standalone executable:

```bash
./scripts/build-standalone.sh
```

The build script creates `dist/amon` using Python's stdlib `zipapp`. The
generated file contains the `amon` package and can be copied as a single
executable.

Smoke-test the artifact:

```bash
dist/amon --help
```

## Install Guide

Install all local integration points with one command:

```bash
./scripts/install.sh
```

By default this:

- builds `dist/amon`
- copies it to `/usr/local/bin/amon`
- installs the Claude session wrapper into `~/.bash_profile`

If `/usr/local/bin` is not writable, either choose a user-writable directory or
run only the command install with elevated privileges. Avoid installing the
Claude wrapper through `sudo`, because that can target root's shell profile.

Use explicit paths when needed:

```bash
./scripts/install.sh --bin-dir ~/.local/bin --profile ~/.zshrc
```

Skip the Claude wrapper if you only want the `amon` command:

```bash
./scripts/install.sh --no-claude-wrapper
```

For a source-checkout installation, install a symlink to the root shim instead
of copying the standalone artifact:

```bash
./scripts/install.sh --source-symlink
```

Do not copy the root `amon` shim by itself. If you want a copied single file,
copy `dist/amon` or use the default `scripts/install.sh` mode.

### Manual Install

For manual copy-style installation, build the standalone executable and copy it
onto your `PATH`:

```bash
./scripts/build-standalone.sh
cp ./dist/amon /usr/local/bin/amon
chmod +x /usr/local/bin/amon
```

For a source-checkout installation, symlink the root shim so it can still find
the checkout's `src/` package:

```bash
ln -s "$(pwd)/amon" /usr/local/bin/amon
```

### Claude Session Wrapper

Claude discovery is most precise when Claude is launched with an explicit
`--session-id`. The wrapper below injects a fresh lowercase UUID for new Claude
runs while leaving `--session-id`, `--resume`, and `--continue` calls unchanged:

```bash
./scripts/install-claude-session-wrapper.sh --profile ~/.bash_profile
source ~/.bash_profile
```

Remove it with:

```bash
./scripts/uninstall-claude-session-wrapper.sh --profile ~/.bash_profile
source ~/.bash_profile
```

The wrapper is a managed shell function named `claude`, not a plain alias.

## Uninstall Guide

Remove all local integration points with one command:

```bash
./scripts/uninstall.sh
```

By default this removes `/usr/local/bin/amon` when it can identify that file as an
`amon` executable, then removes the managed Claude wrapper block from
`~/.bash_profile`.

Use the same custom paths you used during installation:

```bash
./scripts/uninstall.sh --bin-dir ~/.local/bin --profile ~/.zshrc
```

Skip Claude wrapper removal when needed:

```bash
./scripts/uninstall.sh --no-claude-wrapper
```

If the command path exists but cannot be identified as `amon`, the script
refuses to remove it. Use `--force` only when you intentionally want to delete
that path.

## Usage Guide

List active Claude and Codex sessions:

```bash
amon
```

The default view is a sessions TUI. It refreshes discovery every second, groups
rows by session status, and opens a detail log with `Enter`.

Useful keys:

- `/`: filter sessions
- `i`: toggle inline-only sessions
- `r`: hide visible exited/failed sessions for the current run
- `Enter`: open selected session detail
- `q`: quit, or return from list-opened detail view

Limit discovery to sessions whose process cwd is under the current directory:

```bash
amon --current
```

Show only inline, non-interactive agent sessions:

```bash
amon -i
amon --inline-only
```

Open one resolved session detail view:

```bash
amon <session-id>
amon --session-id <session-id>
```

Session id lookup is global, not limited by `--current`. Running sessions tail
live; exited and failed sessions open as a static log.

Change the number of recent log events loaded by detail views:

```bash
amon --lines 500
amon --lines 500 <session-id>
```

Open one pane per discovered session with `xpanes`:

```bash
amon xpane
amon xpane --current
amon xpane -i
```

`amon xpane` discovers sessions once when it starts. Re-run it to build a new
pane layout after additional agents start.

Print one status line and exit:

```bash
amon --session-id <session-id> --once
```

Snapshot output includes `status=working|idle|exited`,
`process=alive|exited|unknown`, and `pid=N` when a PID is known. Snapshot output
is always plain text.

## Flags

- `--current`: limit discovery views to sessions under the current cwd.
- `-i`, `--inline-only`: show only inline, non-interactive sessions in
  discovery views.
- `--lines N`: set recent log lines loaded in detail views.
- `--session-id <id>`: resolve a Claude or Codex session id.
- `--once`: print a snapshot instead of opening the detail view.
- `--idle-threshold N`: set the idle warning/status threshold in seconds.
- `--codex-all-sessions`: include all open Codex JSONLs per discovered Codex
  process.
- `--color {always,never,auto}`: control color for TUI views and direct tail
  output. Snapshots ignore color and stay plain.

## Exit Codes

- `0`: ok, working snapshot status, no sessions found in a discovery view, or
  tail ended.
- `1`: invalid input, unresolved session id, or missing direct session path.
- `2`: snapshot status is idle.
- `3`: `xpanes` is required but unavailable for `amon xpane`.
- `4`: snapshot status is exited because the session process is no longer
  alive.

## Behavior Notes

Idle detection is based on useful JSONL activity. Long-running tool calls may
look idle until the agent writes another useful event, so false positives are
possible during slow commands.

Direct tail mode checks process liveness. If a resolved session has no matching
live process at startup, the known process exits while being monitored, or a
supported agent-exit event appears in the JSONL stream, `amon` prints
`AGENT EXITED` and exits.

Claude discovery prefers the `--session-id` in the running process command
line. If it is unavailable, `amon` falls back to the newest JSONL under the
process cwd's Claude project directory.

Codex discovery resolves JSONL files held open by the Codex process. By default
it chooses the newest file per PID; pass `--codex-all-sessions` when a single
Codex process is holding multiple active session logs.
