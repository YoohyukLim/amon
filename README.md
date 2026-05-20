# amon

`amon` monitors Claude and Codex agent sessions by tailing their JSONL session
files. It is a single executable Python script and uses only the Python standard
library.

## Install

Copy or symlink the `amon` file somewhere on your `PATH`:

```bash
cp ./amon ~/bin/amon
chmod +x ~/bin/amon
```

or:

```bash
ln -s "$(pwd)/amon" ~/bin/amon
```

To make new Claude sessions discoverable even when `claude` is launched
without an explicit session id, install the shell wrapper:

```bash
./scripts/install-claude-session-wrapper.sh --profile ~/.bash_profile
source ~/.bash_profile
```

Remove it with:

```bash
./scripts/uninstall-claude-session-wrapper.sh --profile ~/.bash_profile
source ~/.bash_profile
```

The wrapper is a shell function, not a plain alias, so every invocation gets a
fresh lowercase UUID from `uuidgen | tr '[:upper:]' '[:lower:]'`. Calls that
already pass `--session-id`, `--resume`, or `--continue` are forwarded
unchanged.

## Usage

List active Claude and Codex agent sessions:

```bash
amon
```

The default view is a sessions TUI. It refreshes discovery every second, groups
rows by session id, and opens a session detail log with `Enter`. Use `/` to
filter, `i` to toggle Inline only, `r` to hide visible finished sessions for the
current run, and `q` to quit. On terminals with color support, the sessions TUI
and detail views color statuses and tool lines by default; pass `--color=never`
to keep them plain.

Limit discovery to sessions whose process cwd is under the current directory:

```bash
amon --current
```

Show only inline (non-interactive) sessions in discovery views:

```bash
amon -i
amon --inline-only
```

Open one resolved session detail view:

```bash
amon <session-id>
```

`amon --session-id <session-id>` is also accepted. Session id lookup is global,
not limited by `--current`. The detail view loads the most recent 200 log
events by default. Running sessions tail live; exited and failed sessions open
as a static log. In the sessions list, detail `q` returns to the list. In direct
session detail, `q` exits.

Change the number of recent log events loaded by detail views:

```bash
amon --lines 500
amon --lines 500 <session-id>
```

`--lines N` must be a positive integer and applies both to detail views opened
from the sessions list and to direct session detail.

Open the existing xpanes view:

```bash
amon xpane
amon xpane --current
amon xpane -i
```

`amon xpane` launches one pane per discovered session in the all scope.
`amon xpane --current` applies the same cwd scope as `amon --current`. The
`-i` / `--inline-only` option limits panes to inline sessions. The
sessions TUI is the dynamic default; the xpane launcher builds its pane set when
it starts.

Print one status line and exit:

```bash
amon --session-id <session-id> --once
```

Snapshot output includes `process=alive|exited|unknown`. When a PID is known,
the line also includes `pid=N`. Snapshot output is always plain text, even when
`--color=always` is supplied.

## Flags

- `--current` limits discovery views to sessions under the current cwd.
- `-i, --inline-only` shows only inline (non-interactive) agent sessions in
  discovery views.
- `--lines N` sets recent log lines loaded in session detail views.
- `--session-id <id>` resolves a Claude or Codex session id.
- `--once` prints a snapshot instead of opening the detail view.
- `--idle-threshold N` sets the idle warning/status threshold in seconds.
- `--codex-all-sessions` includes all open Codex session JSONLs per discovered
  Codex process in discovery views.
- `--color {always,never,auto}` controls color for TUI views and direct tail
  output. `--once` snapshots ignore it and stay plain.

`amon xpane` requires `xpanes`. If `xpanes` is missing, it exits with code `3`.
The xpane launcher starts spawned monitor panes with `--color=always`, labels
pane borders as `{runtime}/{session-uuid}` when `tmux` supports pane titles, and
keeps pane shells open after a monitor exits so the final output remains
visible.

## Exit Codes

- `0`: ok, working snapshot status, no sessions found in a discovery view, or
  tail ended.
- `1`: invalid input, unresolved session id, or missing direct session path.
- `2`: snapshot status is idle.
- `3`: `xpanes` is required but unavailable for `amon xpane`.
- `4`: snapshot status is exited because the session process is no longer alive.

## Notes

Idle detection is based on useful JSONL activity. Long-running tool calls may
look idle until the agent writes another useful event, so false positives are
possible during slow commands.

Snapshot status checks process liveness when a PID is supplied or when the
session JSONL can be matched to a currently discovered active session. If no
matching process is found, the snapshot reports `status=exited`; without enough
process information it reports `process=unknown` and falls back to mtime-based
working/idle status.

Direct tail mode also checks process liveness. If a resolved session has no
matching live process at startup, the known process exits while being monitored,
or a supported agent-exit event appears in the JSONL stream, `amon` prints
`AGENT EXITED` and exits.

Claude discovery prefers the `--session-id` in the running process command
line. If it is unavailable, `amon` falls back to the newest JSONL under the
process cwd's Claude project directory.

The sessions TUI refreshes discovery while it runs. The xpane launcher discovers
sessions once when it starts; run `amon xpane` again to build a new pane layout.
