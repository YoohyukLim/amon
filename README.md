# amon

`amon` monitors non-interactive Claude and Codex sessions by tailing their JSONL
session files. It is a single executable Python script and uses only the Python
standard library.

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

## Modes

Open one pane per discovered non-interactive Claude or Codex session:

```bash
amon
```

Tail one resolved session by id:

```bash
amon --session-id <session-id>
```

Print one status line and exit:

```bash
amon --session-id <session-id> --once
```

Snapshot output includes `process=alive|exited|unknown`. When a PID is known,
the line also includes `pid=N`.

Monitor every JSONL currently held by a `codex exec` process instead of only
the newest per process:

```bash
amon --codex-all-sessions
```

## Flags

- `--session-id <id>` resolves a Claude or Codex session id and runs Mode A.
- `--once` prints a snapshot instead of tailing.
- `--idle-threshold N` sets the idle warning/status threshold in seconds.
- `--codex-all-sessions` includes all open Codex session JSONLs during Mode B.
- `--color {always,never,auto}` controls color for direct single-session output.

Mode B requires `xpanes`. If `xpanes` is missing, `amon` exits with code `3`.
Mode B always starts spawned monitor panes with `--color=always`; direct Mode A
defaults to `--color=never` unless you pass a color flag. Mode B also labels
each pane border as `{runtime}/{session-uuid}` when `tmux` supports pane
titles; non-UUID session filenames fall back to their full stem. Panes keep
their shell open after a monitor exits so the final output remains visible.

## Exit Codes

- `0`: ok, working snapshot status, no sessions found in Mode B, or tail ended.
- `1`: invalid input, unresolved session id, or missing direct session path.
- `2`: snapshot status is idle.
- `3`: `xpanes` is required but unavailable for Mode B.
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

Tail mode also checks process liveness. If a resolved session has no matching
live process at startup, the known process exits while being monitored, or a
supported agent-exit event appears in the JSONL stream, `amon` prints
`AGENT EXITED` and exits.

Claude discovery prefers the `--session-id` in the running process command
line. If it is unavailable, `amon` falls back to the newest JSONL under the
process cwd's Claude project directory.

Mode B discovers sessions once when it starts. It does not dynamically add panes
for sessions that begin later; run `amon` again to pick up new sessions.
