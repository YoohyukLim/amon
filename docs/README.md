# amon Documentation

**Version**: 1  |  **Last Updated**: 2026-05-19

<!-- atlas-managed: do not delete sections; edit content freely -->
<!-- atlas-version: 1 -->

## 1. Project Overview

`amon` is a planned command line monitor for non-interactive Claude and Codex agent sessions. It reads JSONL session logs, formats selected events into compact status lines, detects silent idle periods, and can use `xpanes` to show multiple active sessions in separate panes.

The project is currently specification-first: the accepted behavior lives in ADRs and the implementation plan, while the executable and tests are not yet present.

## 2. Documentation Index

| Document | Purpose |
|---|---|
| [system/architecture.md](./system/architecture.md) | Current atlas map of the planned amon architecture |

## 3. Reading Routes

### 3.1 Adding a new feature

1. [system/architecture.md](./system/architecture.md) to identify the affected layer.
2. [arch ADRs](./arch/) to preserve accepted trade-offs.
3. [tasks implementation plan](./tasks/260518-231933-amon-implementation.md) to place the change in the task sequence.

### 3.2 Fixing a bug

1. [system/architecture.md](./system/architecture.md) to locate the relevant flow.
2. Drift Snapshot below for known documentation or implementation gaps.
3. `docs/bugs/*` when bug reports exist.

### 3.3 Modifying an existing subsystem

1. [system/architecture.md](./system/architecture.md) for the current subsystem map.
2. [arch ADRs](./arch/) for the decisions that constrain design changes.
3. `docs/analysis/*` or `docs/impl/*` when later implementation notes exist.

### 3.4 Reading codebase for the first time

1. [README.md](./README.md) for the documentation entry point.
2. [system/architecture.md](./system/architecture.md) for the planned architecture.
3. [tasks implementation plan](./tasks/260518-231933-amon-implementation.md) for the executable and test roadmap.

### 3.5 Operations / Deployment

1. [system/architecture.md](./system/architecture.md) integration points.
2. [260518-231929-python-stdlib.md](./arch/260518-231929-python-stdlib.md) for packaging and dependency constraints.
3. `docs/sop/*` when operational procedures are written.

## 4. Drift Snapshot

(현재 발견된 어긋남 없음).

## 5. Related Documents

- [_atlas-state.md](./_atlas-state.md) — atlas managed state
- [_registry.md](./_registry.md) — typed-dir registry
- [_atlas-migration-260519-083708-aaa8.md](./_atlas-migration-260519-083708-aaa8.md) — migration audit
