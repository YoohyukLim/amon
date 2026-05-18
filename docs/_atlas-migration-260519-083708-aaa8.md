# Atlas Migration Audit

**Version**: 1  |  **Last Updated**: 2026-05-19

<!-- atlas-managed: do not delete sections; edit content freely -->
<!-- atlas-version: 1 -->

## 1. Overview

Snapshot of every divergence atlas detected during the `260519-083708-aaa8` migration run, organized by source file. Divergences from Keep/Absorb files are also seeded into the corresponding new file's Drift Watch; divergences from Skip-classified files are recorded here only.

## 2. Coverage

Anchor-based fact-check covers file-path links, CamelCase/initialism domain nouns, and backticked single-token strings. Paragraph-level prose claims are not covered; spot-check those manually.

## 3. Divergences by source file

### 3.1 docs/_registry.md (Skip)

(현재 발견된 어긋남 없음 — 1차 init 기준)

### 3.2 docs/arch/260518-231927-single-command-flags.md (Skip)

- `CI` — not found in code
- `--help` — not found in code

### 3.3 docs/arch/260518-231928-mode-b-xpanes-spawn.md (Skip)

(현재 발견된 어긋남 없음 — 1차 init 기준)

### 3.4 docs/arch/260518-231929-python-stdlib.md (Skip)

- `darwin-arm64` — not found in code
- `linux-amd64` — not found in code
- `python3` — not found in code
- `lsof` — not found in code
- `pgrep` — not found in code
- `setup.py` — not found in code

### 3.5 docs/arch/260518-231930-stuck-silent-threshold.md (Skip)

- `API` — not found in code
- `LLM` — not found in code
- `tool_running_for` — not found in code
- `awaiting_llm_for` — not found in code
- `--idle-threshold` — not found in code
- `function_call` — not found in code

### 3.6 docs/arch/260518-231931-codex-multi-jsonl-default.md (Skip)

- `lsof` — not found in code
- `OK` — not found in code

### 3.7 docs/arch/260518-231932-discovery-noninteractive-only.md (Skip)

- `--include-interactive` — not found in code

### 3.8 docs/tasks/260518-231933-amon-implementation.md (Skip)

- `REQUIRED` — not found in code
- `SUB` — not found in code
- `SKILL` — not found in code
- `tests/fixtures/claude_session.jsonl` — not found in code
- `tests/fixtures/codex_session.jsonl` — not found in code
- `~/.local/bin/` — not found in code
- `NotImplementedError` — not found in code
- `ArgumentParser` — not found in code
- `TestCwdToClaudeSlug` — not found in code
- `TestCase` — not found in code
- `OK` — not found in code
- `resolve_claude_session_path` — not found in code
- `~/.claude/projects/<slug>/*.jsonl` — not found in code
- `TestParseLsofCwd` — not found in code
- `COMMAND` — not found in code
- `USER` — not found in code
- `FD` — not found in code
- `TYPE` — not found in code
- `DEVICE` — not found in code
- `SIZE` — not found in code
- `OFF` — not found in code
- `NODE` — not found in code
- `NAME` — not found in code
- `DIR` — not found in code
- `TestPickLatestJsonl` — not found in code
- `TemporaryDirectory` — not found in code
- `AttributeError` — not found in code
- `resolve_codex_session_paths` — not found in code
- `TestParseLsofJsonl` — not found in code
- `SAMPLE` — not found in code
- `REG` — not found in code
- `JsonlTail` — not found in code
- `tests/fixtures/sample.jsonl` — not found in code
- `EOF` — not found in code
- `TestJsonlTail` — not found in code

## 4. Drift Watch

- §3: this audit file itself is a snapshot of `260519-083708-aaa8` migration findings — verify entries on next `cairn:atlas-sync` and prune those that have since been addressed in code.

## 5. Related Documents

- [_atlas-state.md](./_atlas-state.md)
- [README.md](./README.md)
- Snapshot: `.cairn/snapshots/260519-083708-aaa8/SNAPSHOT.json`
