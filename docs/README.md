# amon Documentation

**Version**: 3  |  **Last Updated**: 2026-05-20

<!-- atlas-managed: do not delete sections; edit content freely -->
<!-- atlas-version: 1 -->

## 1. Project Overview

`amon` is a single-file Python CLI that monitors Claude and Codex agent sessions by tailing their JSONL session files. It supports direct tailing with exit reporting, one-shot snapshots with process state, a default sessions TUI, and an `xpanes` discovery mode. Discovery includes all agent sessions by default and can be narrowed to inline (non-interactive) sessions with `-i` / `--inline-only`.

The implementation is now present in [`../amon`](../amon), with user-facing usage in [`../README.md`](../README.md), regression tests in [`../tests/test_amon.py`](../tests/test_amon.py), and Claude wrapper setup/cleanup in [`install-claude-session-wrapper.sh`](../scripts/install-claude-session-wrapper.sh) and [`uninstall-claude-session-wrapper.sh`](../scripts/uninstall-claude-session-wrapper.sh).

## 2. Documentation Index

| Document | Purpose |
|---|---|
| [system/architecture.md](./system/architecture.md) | Current atlas map of the implemented amon CLI, session resolution, lifecycle checks, xpanes launcher, wrapper scripts, and tests |

## 3. Reading Routes

### 3.1 Adding a new feature

1. [system/architecture.md](./system/architecture.md) to identify the affected runtime layer.
2. [arch ADRs](./arch/) to preserve accepted command, discovery, packaging, and idle-behavior trade-offs.
3. [implementation checklist](./tasks/260519-091951-amon-implementation-checklist.md) for previously completed scope boundaries.
4. [`../tests/test_amon.py`](../tests/test_amon.py) to extend regression coverage.

### 3.2 Fixing a bug

1. [system/architecture.md](./system/architecture.md) for the relevant data flow or integration point.
2. Drift Snapshot below for known documentation or implementation gaps.
3. [`../tests/test_amon.py`](../tests/test_amon.py) to locate the nearest behavior test.
4. `docs/bugs/*` when bug reports exist.

### 3.3 Modifying an existing subsystem

1. [system/architecture.md](./system/architecture.md) for current responsibilities and dependency direction.
2. [arch ADRs](./arch/) for constraints that still shape the design.
3. [`../amon`](../amon) for the single-file implementation.
4. [`../scripts/install-claude-session-wrapper.sh`](../scripts/install-claude-session-wrapper.sh) and [`../scripts/uninstall-claude-session-wrapper.sh`](../scripts/uninstall-claude-session-wrapper.sh) for shell profile behavior.

### 3.4 Reading codebase for the first time

1. [`../README.md`](../README.md) for install and CLI usage.
2. [system/architecture.md](./system/architecture.md) for the implemented architecture.
3. [`../amon`](../amon) for runtime code.
4. [`../tests/test_amon.py`](../tests/test_amon.py) for behavior examples and edge cases.

### 3.5 Operations / Deployment

1. [`../README.md`](../README.md) install section for copy/symlink usage.
2. [system/architecture.md](./system/architecture.md) integration points for host command, process liveness, and `xpanes` dependencies.
3. [Python stdlib ADR](./arch/260518-231929-python-stdlib.md) for dependency policy.
4. Shell wrapper scripts when Claude process discoverability needs explicit session ids.

## 4. Drift Snapshot

(현재 발견된 어긋남 없음 — sync 기준 2026-05-20)

## 5. Related Documents

- [_atlas-state.md](./_atlas-state.md) — atlas managed state
- [_registry.md](./_registry.md) — typed-dir registry
- [_atlas-migration-260519-083708-aaa8.md](./_atlas-migration-260519-083708-aaa8.md) — migration audit
- [Root README](../README.md) — install and usage surface
- [Initial implementation task](./tasks/260518-231933-amon-implementation.md)
- [Implementation v2 task](./tasks/260519-090729-amon-implementation-v2.md)
- [Implementation checklist](./tasks/260519-091951-amon-implementation-checklist.md)
