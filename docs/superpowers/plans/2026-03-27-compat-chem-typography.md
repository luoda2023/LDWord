# 1.0 Chemistry Typography Compatibility Notes

Date: 2026-03-27

## Goal

Make 1.0 chemistry typography behavior no weaker than 0.2.1 for the current hot cases, while keeping the 1.0 module boundary cleaner than the old 0.2 monolith.

## Root cause found

The original 1.0 `src/modules/special/chem_typography.py` was only a placeholder:

- it used a very narrow paragraph-level regex;
- it only tried to set western font on matching runs;
- it did **not** split runs;
- it did **not** restore subscript / superscript marks at all.

So the real 1.0 failure mode was mainly **missing implementation**, not just a bad edge-case rule.

## Compatibility decisions locked in this round

1. **Roman oxidation states stay on baseline**
   - `Fe(IV)` / `Cr(VI)` / `Cr(III)` must not turn `(IV)/(VI)/(III)` into superscript.
   - These tokens are still treated as chemistry-like for formula/font detection.

2. **Common formula variants must recover subscripts**
   - `g-C3N4`
   - `α-Fe3O4`
   - `TiO2/In2S3`
   - `AgInS2/In2S3`
   - `1 O2`

3. **Roman-state oxo forms are chemistry tokens but not superscript cases**
   - `Fe(IV)=O` / spaced variant `Fe(IV) = O`
   - Keep chemistry/font recognition, but do not superscript the Roman numeral.

## Implementation approach

Instead of re-growing `chem_typography.py` into another giant rule file, the 0.2 LTS chemistry recognition core was extracted into a new shared engine:

- **New:** `src/shared/engine/chem_marks.py`
- **Updated:** `src/modules/special/chem_typography.py`

Module-layer responsibility is now only:

- route paragraphs / table-cell paragraphs by active chemistry scopes;
- call the shared chemistry engine;
- record tracker metrics.

Shared-engine responsibility is now:

- chemistry token detection;
- per-character font mask building;
- per-character super/subscript mark building;
- cross-run split/apply for paragraph runs.

This keeps 1.0 more modular while still preserving the tested 0.2.1 behavior model.

## Scope routing decision added later in the same slice

`chem_typography.scopes` existed in 1.0 config, but was not wired in the module at all.

The compatibility-safe rule now is:

- if **all chemistry scopes are false**, keep the current broad paragraph behavior for backward compatibility;
- if the user explicitly enables scopes, narrow handling to those scopes only;
- `tables=True` now also restores chemistry typography inside table-cell paragraphs.

This avoids the dangerous regression where “start honoring scopes” would accidentally disable chemistry recovery everywhere because the default scope map is all-false.

## Tests added

- **New:** `tests/test_phase3_chem_typography.py`

Locked cases:

- Roman oxidation state baseline behavior
- slash-composite formulas
- Greek / phase prefixes
- singlet oxygen notation
- cross-run paragraph application
- `Fe(IV)=O` font recognition without Roman superscript
- scope fallback when all scopes are false
- explicit body/reference/heading scope routing
- explicit table-cell scope routing

## Verification run

Passed:

- `python -m pytest tests/test_phase3_chem_typography.py -q`
- `python -m pytest tests/test_phase1_config.py tests/test_phase3_special.py tests/test_phase3_chem_typography.py tests/test_phase5_e2e.py -q`

## Follow-up guidance for later 1.0 refactor

If chemistry typography is rebuilt again in a more modular 1.0 style, keep these rules:

1. **Do not reintroduce the old Roman-oxidation superscript bug.**
2. **Keep the shared-engine split**: token recognition vs paragraph application.
3. **Keep the current regression corpus first**, then expand it.
4. If later refining `chem_typography.scopes`, preserve the current fallback rule: **all-false means compatibility-global, not no-op**.
