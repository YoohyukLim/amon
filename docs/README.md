# amon Documentation

**Version**: 3  |  **Last Updated**: 2026-05-20

<!-- atlas-managed: do not delete sections; edit content freely -->
<!-- atlas-version: 1 -->

## 1. Project Overview

`amon` is a Python standard-library CLI that monitors local Claude and Codex agent sessions by discovering running processes, resolving their JSONL session logs, and showing compact list/detail, snapshot, tail, and `xpanes` views. The public command remains `amon`, while the implementation is split into package modules under [`../src/amon`](../src/amon).

The checkout shim is [`../amon`](../amon), user-facing usage and install notes live in [`../README.md`](../README.md), regression tests live in [`../tests/test_amon.py`](../tests/test_amon.py), and operational install/build scripts live in [`../scripts`](../scripts).

## 2. Documentation Index

| Document | Purpose |
|---|---|
| [system/architecture.md](./system/architecture.md) | Current atlas map of the package-based amon CLI, adapter registry, session discovery/resolution, monitor runtime, terminal UI, xpanes launcher, install scripts, and tests |

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
3. [`../src/amon`](../src/amon) for the package implementation.
4. [`../scripts/install.sh`](../scripts/install.sh), [`../scripts/uninstall.sh`](../scripts/uninstall.sh), [`../scripts/install-claude-session-wrapper.sh`](../scripts/install-claude-session-wrapper.sh), and [`../scripts/uninstall-claude-session-wrapper.sh`](../scripts/uninstall-claude-session-wrapper.sh) for shell profile behavior.

### 3.4 Reading codebase for the first time

1. [`../README.md`](../README.md) for install and CLI usage.
2. [system/architecture.md](./system/architecture.md) for the implemented architecture.
3. [`../src/amon/cli.py`](../src/amon/cli.py) for mode dispatch.
4. [`../tests/test_amon.py`](../tests/test_amon.py) for behavior examples and edge cases.

### 3.5 Operations / Deployment

1. [`../README.md`](../README.md) install section for build, copy, and source-symlink usage.
2. [system/architecture.md](./system/architecture.md) integration points for host commands, process liveness, terminal UI, `xpanes`, and install scripts.
3. [Python stdlib ADR](./arch/260518-231929-python-stdlib.md) for dependency policy.
4. [`../scripts/build-standalone.sh`](../scripts/build-standalone.sh), [`../scripts/install.sh`](../scripts/install.sh), and [`../scripts/uninstall.sh`](../scripts/uninstall.sh) for operational commands.

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
- [Sessions mode checklist](./tasks/260519-211154-sessions-mode-checklist.md)
