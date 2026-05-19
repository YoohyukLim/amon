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
titles; non-UUID session filenames fall back to their full stem.

## Exit Codes

- `0`: ok, working snapshot status, no sessions found in Mode B, or tail ended.
- `1`: invalid input, unresolved session id, or missing direct session path.
- `2`: snapshot status is idle.
- `3`: `xpanes` is required but unavailable for Mode B.

## Notes

Idle detection is based on useful JSONL activity. Long-running tool calls may
look idle until the agent writes another useful event, so false positives are
possible during slow commands.

Mode B discovers sessions once when it starts. It does not dynamically add panes
for sessions that begin later; run `amon` again to pick up new sessions.
