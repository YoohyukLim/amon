<!-- cairn-managed:start version=1 runtime=claude -->
Cairn maintains long-running project documentation.

Before project work, read the cairn rules below. If any referenced file is missing, run `cairn:doctor` or restart Claude Code with the cairn plugin enabled so project bootstrap can refresh `~/.cairn/rules/v1/**`.

## Cairn Runtime Contract

This section is inlined as a quick contract. Claude also imports the detailed
always-read rules below with `@path`.

### Persistence

- Put team-shared durable knowledge in `docs/`.
- Put local session state in `.cairn/`.
- Do not duplicate one fact across layers.
- Use timestamped filenames for typed-dir artifacts.

### Atlas

- `docs/system/*.md`, `docs/README.md`, and `docs/_atlas-state.md` are maps,
  not ground truth.
- When consuming atlas-managed files, verify file paths and current-state
  claims against code before relying on them.
- When modifying atlas-managed files, first read:
  `~/.cairn/rules/v1/core/cairn-core-atlas-conventions.md`.
- On feature branches, prefer typed-dir drift evidence over editing
  atlas-managed files directly.

### Typed-Dir Emission

Create a typed-dir artifact only when the result is durable project knowledge,
not a transient status update. If unsure, do not emit.

Common requirements:
- The finding, decision, or result will help a future session.
- The artifact can name concrete repo paths, modules, commands, or workflows.
- The content adds durable value beyond the chat answer alone.

Category gates:
- `docs/bugs/`: root cause is explicit; fix direction is explicit; affected
  paths are named.
- `docs/arch/`: alternatives were considered; selected option and rationale
  are stated; scope is repository-level.
- `docs/analysis/`: exploration covered at least three files or modules; the
  finding helps future sessions.
- `docs/impl/`: implementation uses a non-obvious pattern; design intent is
  not clear from code alone; future maintainers would ask why.
- `docs/review/`: concrete issues were found; conclusion includes a pattern or
  system insight beyond one PR.
- `docs/tests/`: test strategy decision or meaningful result analysis exists;
  value goes beyond one command result.

Do not emit for:
- A simple command result.
- A one-file obvious fix.
- A temporary TODO or status note.
- Facts that belong only in the final response.

When emitting:
- Create `docs/{category}/{yymmdd-HHMMss}-{slug}.md`.
- Add or rely on registry automation for a `docs/_registry.md` Active entry.
- Mention the artifact path once, then continue the requested work.

### Delegation

- The main session owns design, decomposition, review, and final approval.
- Delegate large, structural, uncertain, or multi-module work.
- Before delegating mid-task, write a briefing under `.cairn/delegations/`.
- Verify delegated output before accepting it.

### Claude Runtime

- Prefer qualified skills: `cairn:doctor`, `cairn:pickup`, `cairn:handoff`,
  `cairn:atlas-init`, `cairn:atlas-sync`, and `cairn:atlas-extract`.
- Claude router imports detailed rule files with `@path`.
- Handoff handling remains conditional and is loaded only when reading
  `.cairn/handoff/*.md`.

Detailed rule sources:
- @~/.cairn/rules/v1/core/cairn-core-persistence-layers.md
- @~/.cairn/rules/v1/core/cairn-core-atlas.md
- @~/.cairn/rules/v1/core/cairn-core-typed-dir-emission.md
- @~/.cairn/rules/v1/core/cairn-core-agent-delegation.md
- @~/.cairn/rules/v1/core/cairn-core-atlas-marker-rename.md
- @~/.cairn/rules/v1/claude/cairn-claude-runtime-paths.md
- @~/.cairn/rules/v1/claude/cairn-claude-agent-selection.md
- @~/.cairn/rules/v1/claude/cairn-claude-skill-entrypoints.md
- @~/.cairn/rules/v1/claude/cairn-claude-memory-boundary.md

When reading `.cairn/handoff/*.md`, also read:
- ~/.cairn/rules/v1/core/cairn-core-handoff-handling.md
<!-- cairn-managed:end -->

