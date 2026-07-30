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
- integer logical-pixel font sizes from `typography_policy.py`
- Qt FreeType as the production Windows text backend; DirectWrite remains a
  restart-only fallback
- native `PreferDefaultHinting`; application code must not force Full Hinting
- `Microsoft YaHei -> Microsoft YaHei UI -> Segoe UI` for ordinary CJK UI text
- `Segoe UI -> Microsoft YaHei -> Microsoft YaHei UI` for brand/explicit Latin text
- one shared tooltip controller for every non-empty `QWidget.toolTip()` by default
- no graphics effect on a tooltip popup, surface, or label that owns text
- one semantic `QFont` authority for shared Combo/Input/Spin controls; their
  QSS owns chrome and color, never default font size/family/weight
- explicit registration of the OS-installed YaHei Regular/Bold/Light TTC files
  under FreeType before application widgets are imported

These choices are part of the current visual contract. Do not tune individual
widgets around them with fractional font sizes, DPR multiplication, synthetic
bold, or local hinting overrides.

## Safe Fix Order

1. Verify whether the issue is global or local.
2. Prefer local fixes first:
   - remove unnecessary `Qt.RichText` / HTML labels
   - first verify whether a popup, tooltip, or shadow overlaps the text
   - verify resolved glyph runs, not only `QFontInfo.family()`; ordinary CJK UI
     should stay on a YaHei-primary run, while brand text uses Segoe UI
   - do not assume `font-weight: 500` produces a visible semibold on
     `Microsoft YaHei` / `Microsoft YaHei UI`; both commonly jump from
     `Regular` straight to `Bold`
   - prefer semantic text roles for titles, navigation, and button labels;
     selected may change 400 to a real 700 face, but must keep size, families,
     hinting, and geometry stable
   - avoid synthetic bold for small text
   - do not force `PreferFullHinting`; at 175% it can increase solid ink,
     distort corners, and change the physical glyph bounding box
   - check whether a widget is drawing text onto a transparent intermediate
     surface
   - only expose navigation tooltips when the visible text is actually elided,
     and anchor them to the navigation rail's right side
3. If the symptom is colored ClearType fringe at fractional DPR, verify the
   backend matrix before changing widget geometry. The production FreeType
   backend removes colored subpixels, but it does **not** promise exact pixels
   at every fractional origin.
4. Any shell-, backend-, or DPI-level change must be reviewed visually at
   100%, 125%, 150%, 175%, and 200%, including Regular CJK, real Bold CJK,
   Latin/CJK mixed text, elision, wrapping, and fixed-width controls.

## Review Checklist

- Is the complaint limited to one widget or one label family?
- Does the widget use `Qt.RichText` or inline HTML spans?
- Is the problematic text using `font-weight: 600` or `bold` at a small size?
- Does selected change only the intended semantic weight (400 -> 700)?
- Under FreeType, did the YaHei Bold glyph run resolve to the real `Bold` face,
  rather than `Regular` plus synthetic weight?
- Do size, families, hinting, and geometry remain stable across states?
- Does the font still use `PreferDefaultHinting`?
- Does ordinary CJK UI resolve to YaHei-primary and brand Latin to Segoe UI?
- Is any popup surface or shadow visually covering the text under review?
- Is a native tooltip bypassing the shared tooltip controller?
- Would the proposed fix alter `WA_TranslucentBackground` or `PassThrough`?
- Does any UI font size use point units, a decimal pixel value, or a value
  multiplied/divided by DPR?
- If yes, was the full main window visually compared before and after?

## Windows Font Backend Contract

Qt's [platform-specific argument documentation](https://doc.qt.io/qt-6/qguiapplication.html#platform-specific-arguments)
defines `fontengine=freetype` as the explicit Windows platform option.
DirectWrite is the native default and is selected by **omitting** `fontengine`;
`fontengine=directwrite` is not a supported project spelling. Multiple Windows
QPA options use Qt's canonical comma form, for example:

```text
windows:darkmode=2,fontengine=freetype
```

Production startup is configured before importing `src.qt_api` or constructing
`QApplication`. Frozen builds use the same policy from a PyInstaller runtime
hook. Overrides require a restart:

```powershell
python main.py --gui --font-engine freetype
python main.py --gui --font-engine directwrite
$env:ALAVETTE_FORM_FONT_ENGINE = "directwrite"
```

`--font-engine system` is a true opt-out: it leaves a host-provided QPA choice
untouched. Headless `offscreen`/`minimal` and non-Windows platforms are never
rewritten.

Under FreeType, `main.py` registers these existing Windows files before any UI
module is imported:

```text
%WINDIR%\Fonts\msyh.ttc
%WINDIR%\Fonts\msyhbd.ttc
%WINDIR%\Fonts\msyhl.ttc
```

The application references those OS files and never redistributes them. This
step is required because an unregistered FreeType database can resolve
`Microsoft YaHei` Regular but synthesize weight 700, changing a four-character
13px CJK advance from 52 to 56 logical pixels. With the TTC bridge, both
FreeType and DirectWrite resolve the real Bold face at 52 logical pixels.
If any required TTC is absent during pre-Qt startup, the application falls
back to DirectWrite before loading PySide6 instead of silently accepting a
synthetic-bold layout.

The reproducible evidence command is:

```powershell
python scripts/audit_windows_font_matrix.py
```

It writes the five-scale/two-backend PNG and JSON matrix to
`output/audits/windows_font_matrix_2026-07-12/`.

## Practical Rule

For this project, changing `WA_TranslucentBackground` or the high-DPI rounding
policy is a last-resort shell decision, not a routine text tuning step.
