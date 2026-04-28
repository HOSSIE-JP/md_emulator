# Codex Instructions

This repository also contains GitHub Copilot guidance under `.github/`.
Codex can use that material only when it is explicitly referenced or when this
file points to it. Treat this file as the Codex entry point for repository
guidance.

## Always Read First

- Read `.github/copilot-instructions.md` before changing emulator core,
  API, WASM, frontend integration, or documentation.
- Follow its public API documentation rule: when public APIs change, update
  the relevant files under `docs/` in the same pass.
- Follow its license safety rule: do not copy code from external repositories.
  Use external sources only to understand behavior and then implement original
  code.

## Task-Specific Guidance

- For MD Game Editor plugin work, read:
  - `.github/skills/md-game-editor-plugin/SKILL.md`
  - `.github/skills/md-game-editor-plugin/instructions.md`
  - `electron/PLUGIN.md`
- For emulator debugging or diagnosis work, read:
  - `.github/skills/md-emulator-debug/SKILL.md`
- For Mega Drive emulator architecture or core implementation work, read:
  - `.github/skills/mega-drive-emulator-develop/SKILL.md`

## Codex Skill Notes

- The `.github/skills/**/SKILL.md` files are repository-local references.
  They are not automatically discovered as Codex skills unless copied or
  installed into a Codex skill directory such as `~/.codex/skills`.
- The repository-local `SKILL.md` files should still keep Codex-compatible YAML
  frontmatter (`name` and `description`) so they can be installed later without
  rewriting.

## Current Project Practices

- Prefer existing project patterns over new abstractions.
- Keep Electron renderer, preload, and main-process responsibilities separated.
- Keep filesystem IPC scoped to the current project and reject traversal out of
  the project root.
- When editing generated or sample project files, preserve unrelated user
  changes.
- Write commit messages in Japanese.
