<!-- cairn-managed:start version=1 runtime=claude -->
Cairn maintains long-running project documentation.

Before project work, read the cairn rules below. If any referenced file is missing, run `cairn:doctor` or restart Claude Code with the cairn plugin enabled so project bootstrap can recreate `.cairn/rules/**`.

Core behavior:
- Keep atlas-managed docs current with code/config changes.
- When typed-dir AND-gates are met, write the `docs/{arch,bugs,analysis,impl,review,tests}/` artifact immediately; do not wait for handoff.
- Treat `.cairn/markers/*.tsv` as drift evidence, not verified fact.
- Use delegation rules for large or uncertain work.

Rules:
- .cairn/rules/core/cairn-core-persistence-layers.md
- .cairn/rules/core/cairn-core-atlas.md
- .cairn/rules/core/cairn-core-typed-dir-emission.md
- .cairn/rules/core/cairn-core-agent-delegation.md
- .cairn/rules/core/cairn-core-atlas-marker-rename.md
- .cairn/rules/claude/cairn-claude-runtime-paths.md
- .cairn/rules/claude/cairn-claude-agent-selection.md
- .cairn/rules/claude/cairn-claude-skill-entrypoints.md
- .cairn/rules/claude/cairn-claude-memory-boundary.md

When reading `.cairn/handoff/*.md`, also read:
- .cairn/rules/core/cairn-core-handoff-handling.md
<!-- cairn-managed:end -->

