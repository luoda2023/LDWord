# Windows Text Rendering Change Guardrails

## Goal

Reduce the chance of introducing app-wide text rendering regressions while
trying to fix a local sharpness problem.

The main lesson from this repository is that text rendering bugs often tempt us
to change global shell or DPI behavior, but those changes can easily break:

- perceived 125% / 150% / 175% scaling
- frameless window chrome and border appearance
- rounded-corner shadow composition
- spacing density across the full application

## Current Project Baseline

At the time of writing, this project intentionally keeps:

- a translucent frameless top-level main window
- `HighDpiScaleFactorRoundingPolicy.PassThrough`
- an internally painted rounded shell via `RoundedSurfaceFrame`

These choices are part of the current visual contract. Do not change them as a
first response to a local text sharpness complaint.

## Safe Fix Order

1. Verify whether the issue is global or local.
2. Prefer local fixes first:
   - remove unnecessary `Qt.RichText` / HTML labels
   - verify the chosen Windows CJK UI font first; `Microsoft YaHei UI` can
     look harsher than `Microsoft YaHei` for some small Chinese glyphs
   - do not assume `font-weight: 500` produces a visible semibold on
     `Microsoft YaHei` / `Microsoft YaHei UI`; both commonly jump from
     `Regular` straight to `Bold`
   - prefer a dedicated emphasis token for titles, selected navigation, and
     button labels when real hierarchy must remain visible
   - avoid synthetic bold for small text
   - check whether a widget is drawing text onto a transparent intermediate
     surface
3. Only after local fixes fail should we experiment with app-level shell or DPI
   policy changes.
4. Any shell-level or DPI-level change must be reviewed visually on at least
   100%, 125%, 150%, and 200% scale factors before landing.

## Review Checklist

- Is the complaint limited to one widget or one label family?
- Does the widget use `Qt.RichText` or inline HTML spans?
- Is the problematic text using `font-weight: 600` or `bold` at a small size?
- Would the proposed fix alter `WA_TranslucentBackground` or `PassThrough`?
- If yes, was the full main window visually compared before and after?

## Practical Rule

For this project, changing `WA_TranslucentBackground` or the high-DPI rounding
policy is a last-resort shell decision, not a routine text tuning step.
