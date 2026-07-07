# Documentation Boundaries

Last reviewed: 2026-07-07

This file defines where new documentation and generated artifacts should go.
It is a boundary rule for future work; it does not require bulk-moving existing
historical files in one pass.

## Document Buckets

| Bucket | Intended use | Avoid storing |
| --- | --- | --- |
| `docs/architecture/` | Long-lived architecture notes, module boundaries, dependency rules, and design decisions that should remain useful after a refactor. | One-off command transcripts, screenshots, generated reports. |
| `docs/audits/` | Audit plans, traceability checks, release-gate evidence, and source-evidence records. | Temporary experiment logs or raw generated output. |
| `docs/refactor-records/` | Step-by-step refactor execution notes, validation summaries, and migration journals. | Product-facing documentation or binary artifacts. |
| `docs/visual_checks/` | Curated visual QA notes and selected image references. | Raw screenshot dumps or repeated failed render attempts. |
| `docs/migration_audit/` | Existing migration audit material. Keep using it for already-established migration audit threads until a later planned move. | New unrelated refactor journals. |
| `docs/visual_audit/` | Existing visual audit material. Keep using it for established visual audit threads until a later planned move. | General screenshots or temporary captures. |

## Generated Artifact Policy

Generated outputs should stay out of long-lived documentation paths unless they
are intentionally curated evidence.

Default generated or temporary locations:

- `.pytest_tmp/`
- `.codex_tmp*/`
- `artifacts/`
- `tmp_*/`
- `tests/output/`

These locations are local execution products and are not documentation sources
of truth. If a generated file becomes useful evidence, summarize it in a Markdown
record and link or describe the source command instead of copying large raw
outputs into `docs/`.

## New Document Routing

Use this routing for new files:

- Architecture rule or module boundary: `docs/architecture/`
- Audit trace or source-evidence record: `docs/audits/`
- Refactor execution log: `docs/refactor-records/`
- Visual QA summary: `docs/visual_checks/`
- Product or user-facing docs: keep in an explicit product-doc path chosen by the project owner.

If the target directory does not exist, create it with the first new document in
that category. Do not bulk-move legacy files without a dedicated migration pass.

## Cleanup Rule

Before deleting, moving, or ignoring an existing file, classify it as one of:

1. Source code, test, sample, or product asset.
2. Long-lived documentation.
3. Curated audit/refactor evidence.
4. Generated output or local scratch data.

Only category 4 is safe for automated cleanup, and only after confirming it is
not already tracked or intentionally referenced by tests, scripts, docs, or
release tooling.
