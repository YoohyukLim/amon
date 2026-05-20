# ADR: Discovery default = all agent sessions with inline filter

- Date: 2026-05-20
- Status: Accepted
- Supersedes: [260518-231932-discovery-noninteractive-only.md](./260518-231932-discovery-noninteractive-only.md)

## Context

`amon` previously discovered only non-interactive Claude and Codex sessions. The sessions TUI is now the default view, so users need one place to see every active agent process and then narrow to inline work when desired.

## Options considered

- **(A) Keep non-interactive only** — preserves the original automation-focused behavior but hides interactive sessions from the default session list.
- **(B) Discover all agent sessions and add an inline filter** — include interactive and non-interactive sessions by default; expose `-i` / `--inline-only` and an `i` TUI toggle.
- **(C) Split interactive and non-interactive into separate modes** — explicit but adds mode complexity and makes the default less useful.

## Decision

**(B) Discover all agent sessions and add an inline filter** 채택.

## Rationale

- The default `amon` sessions view should answer "what agent work is running?" without requiring users to know whether a process is interactive.
- Inline-only remains important for automation-focused monitoring, so it is a first-class filter rather than removed behavior.
- Session-id mode already names a concrete session, so `-i` / `--inline-only` is rejected there instead of being ignored.

## Consequences

- `discover_active_sessions()` records inline status per session record.
- `amon` and `amon xpane` default to all agent sessions, while utility commands such as `claude doctor` and `codex app-server` remain excluded.
- `amon -i`, `amon --inline-only`, and `amon xpane -i` limit discovery views to inline sessions.
- The sessions TUI `i` key toggles Inline only on/off while preserving the selected session when it remains visible.
