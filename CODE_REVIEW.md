# Lark-Formatter V1.0 Current Review Status

> Scope: current `src/` workspace state, spot-checked against `tests/` and active CLI/UI paths  
> Updated: 2026-04-13

## Summary

The old 2026-03-24 review is no longer a reliable task list. In the current tree, the previously reported architectural and migration issues that were rechecked in this thread are already fixed:

- pipeline validation hooks execute
- tracker/report extraction uses `result.tracker`
- registry lookups use class-level `meta`
- `validate/` modules exist
- `font_resolver` is no longer a stub
- TOC detection/dirty-marking is scoped correctly
- `table_format` hidden strategies are restored
- optional context dependencies use `soft_consumes`, and dirty propagation can seed from dirty modules
- broken scene configs surface as unavailable descriptors instead of silently disappearing
- stale source backup under `src/` has been removed
- stale module-count comments in active tests were cleaned

## Current state

No active P0/P1/P2 item was reconfirmed in the latest pass.

This does **not** mean the codebase is bug-free; it means there is no remaining reviewed backlog item currently confirmed and ready for immediate execution from the prior review stream.

## Recommended next move

If we keep going, the next useful step is a fresh targeted audit rather than continuing from historical cleanup notes. Good candidates:

1. scan UI panels for broad `except Exception: pass` paths that hide recoverable state problems
2. review workbench execution/runtime paths for user-visible diagnostics consistency
3. audit remaining mojibake/encoding damage in comments and user-facing strings

## 2026-04-13 Targeted Audit

### Resolved in current working tree

1. shared chapter numbering now derives chapter ranges from body-scoped H1 anchors when `doc_tree` is available
2. formula detail pane now round-trips non-dot equation numbering formats instead of coercing them back to `chapter.seq`
3. `equation_table_format` now skips chapter-aware renumbering when heading context is missing, instead of silently degrading to global numbering

### Next watch items

1. scan UI panels for broad `except Exception: pass` paths that still hide recoverable state problems
2. review workbench execution/runtime paths for user-visible diagnostics consistency
3. continue auditing mojibake/encoding damage in comments and user-facing strings
