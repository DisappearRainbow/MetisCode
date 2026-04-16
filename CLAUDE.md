# CLAUDE.md

Instructions for coding agents live in [`AGENTS.md`](./AGENTS.md). Read that file first.

Everything in `AGENTS.md` applies to Claude Code as well. Where it refers to Codex-specific mechanics (approval modes, `~/.codex/config.toml`, patch format), apply the Claude Code equivalents:

- **Approval**: Claude Code's default tool-confirmation flow plays the role of Codex's `suggest` mode. Keep it on while `processor.py`, `edit.py`, and `permission/` are still being built.
- **Sandbox**: none on Windows; compensate by committing per slice.
- **Patches**: Claude Code's `str_replace` expects uniquely matching snippets — prefer replacing a whole function body in one call over multiple micro-edits in the same file.
- **Todos**: use Claude Code's TodoWrite tool to track the slice plan described in AGENTS.md §8.

Everything else — environment, directory layout, porting discipline, coding conventions, acceptance checks — is identical.

## Slice Plan

The detailed development plan lives in `plans/` (52 slices across 5 phases). When working on a slice:

1. **State the slice ID** at the start (e.g., "Starting P2-S10: edit.py core"). This lets the user confirm the right task.
2. **Check dependencies** in `plans/dependency-graph.md` before starting.
3. **Follow the slice's test plan** — each slice specifies exact tests to write.
4. **Update the slice marker** from `[ ]` to `[~]` (in progress) then `[x]` (done) in the phase file.
5. After completing a slice, state which slice is next based on the dependency graph.
