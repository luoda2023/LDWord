# 1.0 TOC + Three-Line Table Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make 1.0 match 0.2.1 for TOC refresh reliability and strict three-line table semantics before tackling chemistry typography.

**Architecture:** Reuse the existing 1.0 pipeline and module boundaries. Add a shared field-refresh helper so TOC can both mark fields for update-on-open and trigger a best-effort post-save Word refresh from the pipeline, then align table border semantics so outer lines share one width and the header separator uses the thinner line.

**Tech Stack:** Python 3, python-docx, lxml, pytest, Windows Word COM / PowerShell fallback (best effort)

---

### Task 1: TOC refresh compatibility

**Files:**
- Modify: `tests/test_phase3_structure.py`
- Create: `src/shared/engine/field_refresh.py`
- Modify: `src/modules/structure/toc.py`
- Modify: `src/pipeline/runner.py`

- [ ] Add a failing test for TOC update-on-open + post-save refresh wiring.
- [ ] Run the focused structure test(s) and confirm the new case fails for the current implementation.
- [ ] Implement a shared helper that detects TOC fields, marks document settings `w:updateFields`, and performs best-effort post-save Word field refresh with a 30s timeout.
- [ ] Re-run the focused structure test(s) and confirm they pass.

### Task 2: Three-line table semantics compatibility

**Files:**
- Modify: `tests/test_phase3_table.py`
- Modify: `src/modules/table/table_format.py`
- Modify: `src/shared/engine/table_builder.py`
- Modify: `src/config/template.py`

- [ ] Add a failing test for strict three-line border widths: top == bottom outer width, middle header separator == thinner inner width, and no vertical / interior grid lines.
- [ ] Run the focused table test(s) and confirm the new case fails for the current implementation.
- [ ] Implement the minimal production change to align helper + module behavior and clarify config semantics/comments.
- [ ] Re-run the focused table test(s) and confirm they pass.

### Task 3: Regression verification

**Files:**
- Modify: `docs/superpowers/plans/2026-03-27-compat-toc-table.md`

- [ ] Run the combined focused tests for structure + table.
- [ ] Run the relevant smoke/e2e subset if the focused tests pass.
- [ ] Update this plan file with completion notes if any deviations were needed.

## Execution Notes

- 2026-03-27: TOC refresh slice completed. Added `src/shared/engine/field_refresh.py`, marked `w:updateFields` on TOC docs, and wired a best-effort post-save Word refresh from `Pipeline._save_outputs()` with a 30s timeout.
- 2026-03-27: Three-line table slice completed. Unified both `src/modules/table/table_format.py` and `src/shared/engine/table_builder.py` to use strict semantics: top outer == bottom outer, header separator thinner, and no vertical / extra interior horizontal lines.
- Verified with: `python -m pytest tests/test_phase3_structure.py tests/test_phase3_table.py -q` and `python -m pytest tests/test_phase0_smoke.py tests/test_phase5_e2e.py -q`.
