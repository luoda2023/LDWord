"""Embedded MarkText (Muya) editor using QWebEngineView + QWebChannel.

This is the right-side editor surface.  It loads the real MarkText editor
kernel (``@marktext/muyajs``, the legacy MarkText v1 editor) bundled into a
self-contained browser IIFE, so QWebEngineView can run the genuine editor
without a Node runtime or a separate Electron window.

The bundle is produced by ``marktext-develop/packages/muyajs/build_muya.sh``
into ``src/assistant/ui/web/`` (``muya.bundle.js`` + ``muya.bundle.css``) and
is loaded via a ``baseUrl`` pointing at that directory.  The page talks back
to the Qt shell through a :class:`MarkTextBridge` exposed over QWebChannel.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from src.qt_api import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QObject,
    QProgressBar,
    QPushButton,
    QThread,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.assistant.ui.marktext_bridge import MarkTextBridge
from src.shared.ui.theme import bind_theme, get_theme, theme_rgba

_WEB_DIR = Path(__file__).resolve().parent / "web"
_BUNDLE_JS = _WEB_DIR / "muya.bundle.js"
_BUNDLE_CSS = _WEB_DIR / "muya.bundle.css"
_BUNDLE_MANIFEST = _WEB_DIR / "muya.bundle.manifest.json"

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}

# Non-image files are rejected outright (the cursor shows the forbidden glyph),
# so Qt stops routing the drag to us and never sends a DragLeave to hide the
# "仅支持图片文件" notice.  A one-shot timer auto-hides it after this delay.
_DROP_REJECT_HINT_MS = 1600


def _is_image_url(url) -> bool:
    """Return whether a dropped QUrl points at a local image file."""
    if not url.isLocalFile():
        return False
    return Path(url.toLocalFile()).suffix.casefold() in _IMAGE_SUFFIXES


def _muyajs_source_root() -> Path | None:
    """Return the muyajs source root, or ``None`` when unavailable.

    In a frozen distribution the ``marktext-develop`` checkout is not shipped,
    so there is nothing to fingerprint; the pre-built, shipped bundle is
    trusted as-is.
    """
    repo_root = Path(__file__).resolve().parents[3]
    muyajs = repo_root / "marktext-develop" / "packages" / "muyajs"
    return muyajs if (muyajs / "lib").is_dir() else None


def _muyajs_source_fingerprint() -> str | None:
    """Content hash of the muyajs sources that feed the bundle.

    Hashes the editor kernel sources (``lib/``, ``themes/``, ``shims/``), the
    build script, and the package manifest in a stable, path-sorted order, so
    any edit to the muyajs source — even without a version bump — changes the
    fingerprint and triggers a rebuild.
    """
    muyajs = _muyajs_source_root()
    if muyajs is None:
        return None
    build_script = muyajs / "build_muya.mjs"
    tracked: list[Path] = []
    for sub in ("lib", "themes", "shims"):
        for path in sorted((muyajs / sub).rglob("*")):
            if path.is_file():
                tracked.append(path)
    for path in (build_script, muyajs / "package.json"):
        if path.is_file():
            tracked.append(path)
    if not tracked:
        return None
    digest = hashlib.sha256()
    for path in sorted(tracked, key=lambda p: p.as_posix()):
        rel = path.relative_to(muyajs).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            continue
        digest.update(b"\0")
    return digest.hexdigest()


def _muyajs_version() -> str:
    """Read the muyajs package version (best-effort)."""
    muyajs = _muyajs_source_root()
    if muyajs is None:
        return ""
    package_json = muyajs / "package.json"
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
        return str(payload.get("version") or "")
    except (OSError, ValueError, json.JSONDecodeError):
        return ""


def _read_manifest() -> dict:
    try:
        return json.loads(_BUNDLE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _write_manifest() -> None:
    payload = {
        "version": _muyajs_version(),
        "fingerprint": _muyajs_source_fingerprint() or "",
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _BUNDLE_MANIFEST.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _muya_bundle_needs_rebuild() -> bool:
    """Return True when the bundle is missing or its source fingerprint drifted.

    This is a fast, non-building check; it lets the UI decide whether to show a
    progress dialog before shelling out to ``node``.
    """
    if not (_BUNDLE_JS.is_file() and _BUNDLE_CSS.is_file()):
        return True
    fingerprint = _muyajs_source_fingerprint()
    if fingerprint is None:
        # Frozen distribution (no sources): trust the shipped bundle.
        return False
    manifest = _read_manifest()
    return manifest.get("fingerprint") != fingerprint


def _rebuild_muya_bundle() -> bool:
    """Run ``node build_muya.mjs`` and record the manifest on success."""
    muyajs = _muyajs_source_root()
    if muyajs is None:
        return False
    build_script = muyajs / "build_muya.mjs"
    if not build_script.is_file():
        return False
    import subprocess
    import logging

    try:
        subprocess.run(
            ["node", str(build_script)],
            cwd=str(build_script.parent),
            check=True,
            capture_output=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # Build is best-effort: the view degrades gracefully if it cannot run
        # (e.g. node unavailable in a frozen distribution).
        logging.getLogger(__name__).warning(
            "Muya bundle build failed (node/build_muya.mjs): %s", exc
        )
        return False
    if not (_BUNDLE_JS.is_file() and _BUNDLE_CSS.is_file()):
        return False
    _write_manifest()
    return True


class _MuyaBuildWorker(QObject):
    """Run the Muya bundle build on a background thread.

    The build shells out to ``node build_muya.mjs`` and can take tens of
    seconds on first run, so it must never run on the GUI thread.  The worker
    emits ``finished`` with the success flag; the owner shows a progress
    dialog meanwhile and reloads the editor on completion.
    """

    finished = Signal(bool)

    def run(self) -> None:
        try:
            ok = _rebuild_muya_bundle()
        except Exception:  # noqa: BLE001 - worker boundary
            ok = False
        self.finished.emit(ok)


def _theme_css_vars() -> str:
    """Render the theme-derived CSS variables injected into the page.

    The embedded editor keeps MarkText's native dark chrome, but its brand
    color (links, list markers, blockquote borders, toolbar active/focus)
    now follows the active Qt theme instead of a hard-coded ``#409eff``, so
    the right-side editor stays visually consistent with the rest of LDWord
    across theme switches.
    """
    theme = get_theme()
    primary = str(getattr(theme, "primary", "#409eff") or "#409eff")
    pressed = str(
        getattr(theme, "primary_pressed", "") or getattr(theme, "primary_hover", "") or primary
    )
    # Status accents resolved from the SAME theme the left workbench toast uses
    # (left success = theme.primary, warning = theme.warning, error =
    # theme.error), so the two panes never drift in colour.
    warning = str(getattr(theme, "warning", "#FAAD14") or "#FAAD14")
    error = str(getattr(theme, "error", "#FF4D4F") or "#FF4D4F")
    return (
        ":root {"
        f" --ldword-brand: {primary};"
        f" --ldword-brand-pressed: {pressed};"
        f" --ldword-brand-30: {theme_rgba(primary, 0.30)};"
        f" --ldword-brand-60: {theme_rgba(primary, 0.60)};"
        f" --ldword-success: {primary};"
        f" --ldword-warning: {warning};"
        f" --ldword-error: {error};"
        " }"
    )

_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<link rel="stylesheet" href="muya.bundle.css">
<!-- __LDWORD_STATUS_MSGS__ injected by the Qt shell (single source of truth). -->
<script>
window.__err = null;
window.onerror = function(msg, src, line, col, err) {
  window.__err = msg + ' @' + line + (err && err.stack ? '\n' + err.stack : '');
};
</script>
<style>
  /* __LDWORD_THEME_VARS__ injected by the Qt shell from get_theme(). */
  /* Dark theme CSS variables for the Muya editor core. Muya's default.css
     consumes var(--editorColor) etc. but never defines them (the desktop
     shell normally injects these), so without this block the editor falls
     back to light-on-white. These values mirror MarkText's dark.theme.css
     and match LDWord's existing dark chrome. */
  :root {
    --themeColor: var(--ldword-brand, #409eff);
    --themeColor30: var(--ldword-brand-30, rgba(64, 158, 255, 0.3));
    --highlightColor: var(--ldword-brand-60, rgba(102, 177, 255, 0.6));
    --selectionColor: var(--ldword-brand-30, rgba(102, 177, 255, 0.3));
    --editorColor: rgba(255, 255, 255, 0.7);
    --editorColor80: rgba(255, 255, 255, 0.8);
    --editorColor60: rgba(255, 255, 255, 0.6);
    --editorColor50: rgba(255, 255, 255, 0.5);
    --editorColor40: rgba(255, 255, 255, 0.4);
    --editorColor30: rgba(255, 255, 255, 0.3);
    --editorColor10: rgba(255, 255, 255, 0.1);
    --editorColor04: rgba(255, 255, 255, 0.04);
    --editorBgColor: #1f2226;
    --deleteColor: var(--ldword-brand, #409eff);
    --iconColor: rgba(255, 255, 255, 0.56);
    --codeBgColor: #424344;
    --codeBlockBgColor: #282c30;
    --footnoteBgColor: rgba(66, 67, 68, 0.3);
    --inputBgColor: #2f3336;
    --focusColor: var(--themeColor);
    --buttonFontColor: rgba(255, 255, 255, 0.6);
    --buttonBgColor: #424344;
    --buttonBorder: 1px solid rgba(0, 0, 0, 0.2);
    --buttonFontColorHover: var(--buttonFontColor);
    --buttonBgColorHover: #4f5051;
    --buttonFontColorActive: var(--buttonFontColor);
    --buttonBgColorActive: #333434;
    --tableBorderColor: #363839;
    --headingColor: rgba(255, 255, 255, 0.8);
    --h1Color: var(--editorColor80);
    --h2Color: var(--editorColor80);
    --h3Color: var(--editorColor80);
    --h4Color: var(--editorColor80);
    --h5Color: var(--editorColor80);
    --h6Color: var(--editorColor80);
    --blockquoteTextColor: rgba(255, 255, 255, 0.5);
    --blockquoteBorderColor: var(--ldword-brand, #409eff);
    --hrColor: rgba(255, 255, 255, 0.1);
    --linkColor: var(--ldword-brand, #409eff);
    --strongColor: rgba(255, 255, 255, 0.8);
    --emColor: var(--ldword-brand-60, #66b1ff);
    --listMarkerColor: var(--ldword-brand, #409eff);
    --floatFontColor: rgba(255, 255, 255, 0.7);
    --floatBgColor: #3f3f3f;
    --floatHoverColor: rgba(255, 255, 255, 0.04);
    --floatBorderColor: rgba(0, 0, 0, 0.05);
    --floatShadow: rgba(0, 0, 0, 0.2);
    --maskColor: rgba(0, 0, 0, 0.7);
    --editorAreaWidth: 750px;
  }
  html,body { margin:0; height:100%; background:#1f2226; color:#e6e6e6;
    font-family:"Microsoft YaHei UI", -apple-system, "Segoe UI", sans-serif; }
  #toolbar { display:flex; gap:4px; padding:6px 12px 6px 4px; border-bottom:1px solid #3a3f46;
    background:#24272b; flex-wrap:nowrap; align-items:center; position:relative;
    overflow-x:auto; overflow-y:hidden; scrollbar-width:none; }
  #toolbar::-webkit-scrollbar { display:none; }
  #toolbar .spine { width:4px; align-self:stretch; border-radius:2px; background:#3a3f46;
    margin:0 6px 0 0; transition:background 120ms ease; flex-shrink:0; }
  #toolbar .spine.writing { background:#f7b955; }
  #toolbar .spine.saved { background:#7ee787; }
  #toolbar .spine.exported { background:var(--ldword-brand, #409eff); }
  #toolbar .spine.failed { background:#ff7b72; }
  #toolbar .group { display:flex; gap:4px; align-items:center; padding:0 8px;
    border-left:1px solid #2e3237; flex-shrink:0; }
  #toolbar .group:first-of-type { border-left:none; padding-left:0; }
  #toolbar button { background:#2e3237; color:#e6e6e6; border:1px solid #3a3f46;
    border-radius:6px; padding:4px 9px; cursor:pointer; font-size:13px; line-height:1.4;
    transition:background 120ms ease, border-color 120ms ease; }
  #toolbar button:hover { background:#3a3f46; }
  #toolbar button:focus-visible { outline:2px solid var(--ldword-brand, #409eff); outline-offset:1px; }
  #toolbar button:disabled { background:#23262b; color:#5a6068; border-color:#2e3237;
    cursor:not-allowed; opacity:0.55; }
  #toolbar button:disabled:hover { background:#23262b; }
  #toolbar button.active { background:var(--ldword-brand-pressed, #2c5f8a); border-color:var(--ldword-brand, #409eff); color:#ffffff; }
  #toolbar button.fmt { font-weight:600; min-width:26px; }
  #toolbar button.icon { display:inline-flex; align-items:center; justify-content:center;
    min-width:30px; height:28px; padding:3px 6px; }
  #toolbar button.icon svg { width:16px; height:16px; display:block;
    fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round;
    stroke-linejoin:round; }
  /* Undo/redo buttons are wrapped so a step-count badge can overlay each */
  #toolbar .histwrap { position:relative; display:inline-flex; }
  #toolbar .histbadge { position:absolute; top:-6px; right:-6px; min-width:14px;
    height:14px; border-radius:8px; padding:0 3px; font-size:9px; font-weight:700;
    line-height:14px; text-align:center; color:#fff; display:none;
    background:var(--ldword-brand, #409eff); pointer-events:none;
    box-shadow:0 0 0 2px var(--toolbarBgColor, #24272b); }
  #toolbar .histbadge.on { display:block; }
  #toolbar .histbadge.dim { display:block; opacity:0.35; background:#565b63;
    box-shadow:none; color:#c8cdd4; }
  #toolbar .histbadge.redo { background:#6b7280; }
  /* heading buttons read as a hierarchy scale, not six equal buttons */
  #toolbar button.fmt[data-para^="heading"] { min-width:24px; padding:4px 6px; }
  #toolbar button.fmt[data-para="heading 1"] { font-size:15px; }
  #toolbar button.fmt[data-para="heading 2"] { font-size:14px; }
  #toolbar button.fmt[data-para="heading 3"] { font-size:13px; }
  #toolbar button.fmt[data-para="heading 4"] { font-size:12px; }
  #toolbar button.fmt[data-para="heading 5"] { font-size:11px; }
  #toolbar button.fmt[data-para="heading 6"] { font-size:10px; }
  #toolbar button.primary { border-color:var(--ldword-brand, #409eff); color:#66b1ff; }
  #toolbar button.primary:hover { background:var(--ldword-brand-pressed, #2c5f8a); color:#ffffff; }
  #toolbar select { background:#2e3237; color:#e6e6e6; border:1px solid #3a3f46;
    border-radius:6px; padding:5px 8px; }
  @media (prefers-reduced-motion: reduce) {
    #toolbar .spine, #toolbar button { transition:none; }
  }
  #statusbar { display:flex; align-items:center; gap:10px; height:26px; padding:0 12px;
    background:#1f2226; border-bottom:1px solid #3a3f46; }
  #status { margin-left:auto; color:#9aa0a6; font-size:12px; white-space:nowrap; }
  #blockhint { color:var(--ldword-brand, #409eff); font-size:12px;
    white-space:nowrap; padding:1px 8px; border:1px solid var(--ldword-brand, #409eff);
    border-radius:4px; display:none; }
  #wordcount { color:#7ee787; font-size:12px; white-space:nowrap; }
  #main { display:flex; height:calc(100% - 41px - 26px); }
  #outline { width:220px; border-right:1px solid #3a3f46; overflow:auto; padding:8px;
    background:#1f2226; }
  #outline .item { padding:6px 8px; border-radius:6px; cursor:pointer; color:#e6e6e6; }
  #outline .item:hover { background:#2e3237; }
  #outline .item.active { background:#3a3f46; }
  #outline .item.failed { color:#ff7b72; }
  #outline .item.failed.active { background:#4a3030; }
  #editor-host { flex:1; overflow:auto; }
  #editor { min-height:100%; padding:16px 20px; box-sizing:border-box; }
  /* dark-editor tune: keep Muya's own styles but fit our dark chrome */
  #editor-host .muya-container { border:none; }
  /* more-format dropdown menu */
  #format-menu { position:fixed; z-index:1002; display:none; background:#2e3237;
    border:1px solid #3a3f46; border-radius:8px; padding:4px 0; min-width:170px;
    box-shadow:0 6px 18px rgba(0,0,0,0.45); }
  #format-menu .mi { display:flex; align-items:center; justify-content:space-between;
    gap:14px; padding:6px 14px; cursor:pointer; color:#e6e6e6; font-size:13px; }
  #format-menu .mi:hover { background:#3a3f46; }
  #format-menu .mi .kbd { color:#9aa0a6; font-size:12px; }
  #format-menu .divider { height:1px; background:#3a3f46; margin:3px 0; }
  /* table & image context menu */
  #table-menu, #image-menu { position:fixed; z-index:1000; display:none; background:#2e3237;
    border:1px solid #3a3f46; border-radius:8px; padding:4px 0; min-width:150px;
    box-shadow:0 6px 18px rgba(0,0,0,0.45); }
  #table-menu .mi, #image-menu .mi { padding:6px 14px; cursor:pointer; color:#e6e6e6; font-size:13px; }
  #table-menu .mi:hover, #image-menu .mi:hover { background:#3a3f46; }
  #table-menu .mi.danger { color:#ff7b72; }
  #table-menu .divider { height:1px; background:#3a3f46; margin:3px 0; }
  /* table size picker (drag to select N×M) */
  #table-picker { position:fixed; z-index:1001; display:none; background:#2e3237;
    border:1px solid #3a3f46; border-radius:8px; padding:8px;
    box-shadow:0 6px 18px rgba(0,0,0,0.45); user-select:none; }
  #table-picker .grid { display:grid; gap:2px; }
  #table-picker .cell { width:18px; height:18px; border:1px solid #4a5058;
    border-radius:3px; cursor:pointer; }
  #table-picker .cell.hot { background:var(--ldword-brand, #409eff); border-color:var(--ldword-brand, #409eff); }
  #table-picker .label { margin-top:6px; text-align:center; color:#9aa0a6;
    font-size:12px; }
  #table-picker .custom { display:flex; align-items:center; justify-content:center;
    gap:6px; margin-top:8px; padding-top:8px; border-top:1px solid #3a3f46; }
  #table-picker .custom input { width:48px; background:#1f2226; color:#e6e6e6;
    border:1px solid #3a3f46; border-radius:4px; padding:3px 5px; font-size:12px;
    text-align:center; }
  #table-picker .custom input:focus { border-color:var(--ldword-brand, #409eff); outline:none; }
  #table-picker .custom .x { color:#9aa0a6; font-size:12px; }
  #table-picker .custom button { background:#2e3237; color:#e6e6e6;
    border:1px solid var(--ldword-brand, #409eff); border-radius:4px; padding:3px 10px;
    font-size:12px; cursor:pointer; }
  #table-picker .custom button:hover { background:var(--ldword-brand-pressed, #2c5f8a); color:#ffffff; }

  /* Dark Prism syntax theme — Muya bundles prismjs/light.theme.css by
     default, so override its token colors here to keep code blocks dark. */
  code[class*="language-"],
  pre.ag-paragraph {
    color: #d4d4d4;
  }
  .token.comment, .token.prolog, .token.doctype, .token.cdata {
    color: #7a848e;
  }
  .token.punctuation { color: #9aa0a6; }
  .token.property, .token.tag, .token.boolean, .token.number,
  .token.constant, .token.symbol {
    color: #f78c6c;
  }
  .token.selector, .token.attr-name, .token.string, .token.char,
  .token.builtin {
    color: #7ec699;
  }
  .token.operator, .token.entity, .token.url,
  .language-css .token.string, .style .token.string {
    color: #d19a66;
  }
  .token.atrule, .token.attr-value, .token.keyword {
    color: #79b8ff;
  }
  .token.function, .token.class-name { color: #e5a07b; }
  .token.regex, .token.important, .token.variable { color: #f78c6c; }
  .token.inserted { color: #7ec699; background: transparent; }
  .token.deleted { color: #ff7b72; background: transparent; }
  pre.ag-paragraph, pre.mu-code-block {
    background: var(--codeBlockBgColor);
  }
  #toast {
    position: fixed;
    left: 50%;
    top: 48px;
    transform: translateX(-50%) translateY(-8px);
    background: var(--toolbarBgColor, #24272b);
    color: var(--editorTextColor, #e6e6e6);
    border: 1px solid var(--borderColor, #3a3f46);
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 13px;
    line-height: 1.4;
    box-shadow: 0 6px 20px rgba(0,0,0,0.35);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.18s ease, transform 0.18s ease;
    z-index: 1000;
    white-space: nowrap;
  }
  #toast.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
  /* Status variants — an accent left bar so success / warning / error toasts
     are distinguishable at a glance.  The accent colours come from the SAME
     active theme variables as the left workbench toast (success = brand,
     warning = theme warning, error = theme error), so the two panes never
     drift apart in colour. */
  #toast.success {
    border: 1px solid var(--ldword-success, #409eff);
    box-shadow: 0 6px 20px rgba(0,0,0,0.35), inset 3px 0 0 var(--ldword-success, #409eff);
  }
  #toast.warning {
    border: 1px solid var(--ldword-warning, #fbbf24);
    box-shadow: 0 6px 20px rgba(0,0,0,0.35), inset 3px 0 0 var(--ldword-warning, #fbbf24);
  }
  #toast.error {
    border: 1px solid var(--ldword-error, #f87171);
    box-shadow: 0 6px 20px rgba(0,0,0,0.35), inset 3px 0 0 var(--ldword-error, #f87171);
  }
</style>
</head>
<body>
  <div id="toolbar">
    <span class="spine" id="spine"></span>
    <div class="group">
      <span class="histwrap">
        <button class="fmt" id="undo-btn" title="撤销 (Ctrl+Z)">↶</button>
        <span class="histbadge" id="undo-count" aria-hidden="true"></span>
      </span>
      <span class="histwrap">
        <button class="fmt" id="redo-btn" title="重做 (Ctrl+Shift+Z / Ctrl+Y)">↷</button>
        <span class="histbadge redo" id="redo-count" aria-hidden="true"></span>
      </span>
    </div>
    <div class="group">
      <button class="fmt icon" data-fmt="strong" title="加粗"><svg viewBox="0 0 24 24"><path d="M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8"/></svg></button>
      <button class="fmt icon" data-fmt="em" title="斜体"><svg viewBox="0 0 24 24"><line x1="19" x2="10" y1="4" y2="4"/><line x1="14" x2="5" y1="20" y2="20"/><line x1="15" x2="9" y1="4" y2="20"/></svg></button>
      <button class="fmt icon" data-fmt="del" title="删除线"><svg viewBox="0 0 24 24"><path d="M16 4H9a3 3 0 0 0-2.83 4"/><path d="M14 12a4 4 0 0 1 0 8H6"/><line x1="4" x2="20" y1="12" y2="12"/></svg></button>
      <button class="fmt icon" data-fmt="u" title="下划线"><svg viewBox="0 0 24 24"><path d="M6 4v6a6 6 0 0 0 12 0V4"/><line x1="4" x2="20" y1="20" y2="20"/></svg></button>
      <button class="fmt icon" data-fmt="inline_code" title="行内代码"><svg viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></button>
      <button class="fmt icon" data-fmt="inline_math" title="行内数学公式"><svg viewBox="0 0 24 24"><path d="M18 7V4H6l6 8-6 8h12v-3"/></svg></button>
      <button class="fmt icon" data-fmt="link" title="链接"><svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg></button>
      <button class="fmt icon" id="more-btn" title="更多格式"><svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg></button>
    </div>
    <div class="group">
      <button class="fmt" data-para="heading 1" title="一级标题">H1</button>
      <button class="fmt" data-para="heading 2" title="二级标题">H2</button>
      <button class="fmt" data-para="heading 3" title="三级标题">H3</button>
      <button class="fmt" data-para="heading 4" title="四级标题">H4</button>
      <button class="fmt" data-para="heading 5" title="五级标题">H5</button>
      <button class="fmt" data-para="heading 6" title="六级标题">H6</button>
      <button class="fmt" data-para="blockquote" title="引用">❝</button>
    </div>
    <div class="group">
      <button class="fmt icon" data-para="ul" title="无序列表"><svg viewBox="0 0 24 24"><line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/><line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/><line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/></svg></button>
      <button class="fmt icon" data-para="ol" title="有序列表"><svg viewBox="0 0 24 24"><line x1="10" x2="21" y1="6" y2="6"/><line x1="10" x2="21" y1="12" y2="12"/><line x1="10" x2="21" y1="18" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/></svg></button>
      <button class="fmt icon" data-para="pre" title="代码块"><svg viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></button>
      <button class="fmt icon" id="table-btn" title="插入表格"><svg viewBox="0 0 24 24"><path d="M12 3v18"/><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/></svg></button>
      <button class="fmt icon" data-para="mathblock" title="块级数学公式"><svg viewBox="0 0 24 24"><path d="M4 21V3"/><path d="M4 3h16"/><path d="M20 3l-8 18"/><path d="M16 21h4"/></svg></button>
      <button class="fmt icon" id="image-btn" title="插入图片"><svg viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg></button>
    </div>
    <div class="group">
      <select id="chapters"><option value="__all__">全文（预览）</option></select>
      <button class="primary" id="save">保存</button>
      <button class="primary" id="export">导出 DOCX</button>
    </div>
  </div>
  <div id="statusbar">
    <span id="blockhint"></span>
    <span id="wordcount"></span>
    <span id="status"></span>
  </div>
  <div id="main">
    <div id="outline"></div>
    <div id="editor-host"><div id="editor"></div></div>
  </div>
  <div id="toast" role="status" aria-live="polite"></div>
  <div id="format-menu">
    <div class="mi" data-fmt="sub">下标 <span class="kbd">X₂</span></div>
    <div class="mi" data-fmt="sup">上标 <span class="kbd">X²</span></div>
    <div class="mi" data-fmt="mark">高亮 <span class="kbd">标记</span></div>
    <div class="divider"></div>
    <div class="mi" data-para="html">HTML 标签块</div>
  </div>
  <div id="table-menu">
    <div class="mi" data-loc="previous" data-action="insert" data-target="row">在上方插入行</div>
    <div class="mi" data-loc="next" data-action="insert" data-target="row">在下方插入行</div>
    <div class="mi danger" data-loc="current" data-action="remove" data-target="row">删除行</div>
    <div class="divider"></div>
    <div class="mi" data-loc="left" data-action="insert" data-target="column">在左侧插入列</div>
    <div class="mi" data-loc="right" data-action="insert" data-target="column">在右侧插入列</div>
    <div class="mi danger" data-loc="current" data-action="remove" data-target="column">删除列</div>
  </div>
  <div id="image-menu">
    <div class="mi" data-field="title">编辑图注…</div>
    <div class="mi" data-field="alt">编辑替代文字…</div>
  </div>
  <div id="table-picker" tabindex="0">
    <div class="grid"></div>
    <div class="label">1 × 1</div>
    <div class="custom">
      <input id="picker-rows" type="number" min="1" max="100" value="8" title="行数">
      <span class="x">×</span>
      <input id="picker-cols" type="number" min="1" max="100" value="8" title="列数">
      <button id="picker-insert" type="button">插入</button>
    </div>
  </div>
<script src="muya.bundle.js"></script>
<script>
  let bridge = null;
  let outline = [];
  let activeChapter = 0;       // 0 = whole document preview, N = editing chapter N
  let wholeMarkdown = '';      // concatenated preview text
  let chapterMarkdown = {};    // index -> markdown body
  let muya = null;
  let suppressChange = false;
  let dirty = false;
  let saveTimer = null;
  let pendingChapter = 0;
  let lastEditDescription = ''; // what the most recent real edit did (for the undo tooltip)
  // Streaming frame-merge state: deltas accumulate per chapter and are flushed
  // to the editor once per animation frame, so a burst of tokens triggers a
  // single DOM rebuild instead of one rebuild per token.
  let streamRenderScheduled = false;
  let failedChapters = {};       // index -> true, marked when a run fails
  let selectedImageInfo = null;  // { key, token, imageId, absoluteImagePath } from Muya

  function currentMarkdown() {
    return activeChapter === 0 ? wholeMarkdown : (chapterMarkdown[activeChapter] || '');
  }

  function countChars(md) {
    // Count visible characters, ignoring markdown markup, whitespace, and
    // the table separator row so the badge tracks real written content.
    let text = (md || '')
      .replace(/```[\s\S]*?```/g, ' ')
      .replace(/`[^`]*`/g, ' ')
      .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
      .replace(/\[[^\]]*\]\([^)]*\)/g, '$1')
      .replace(/^\s*\|?\s*:?-{3,}.*$/gm, ' ')
      .replace(/\|/g, ' ')
      .replace(/[#*_>~\-]/g, ' ')
      .replace(/\s+/g, '');
    return text.length;
  }

  function updateWordCount() {
    const wc = document.getElementById('wordcount');
    if (!wc) return;
    const md = currentMarkdown();
    const n = countChars(md);
    if (activeChapter === 0) {
      wc.textContent = n > 0 ? ('全文 ' + n + ' 字') : '';
    } else {
      wc.textContent = n + ' 字';
    }
  }

  // The spine is a thin colored strip at the toolbar's left edge that encodes
  // the current chapter's state: idle, writing, saved, exported, or failed.
  function setStatus(text, spineState) {
    const st = document.getElementById('status');
    if (st) st.textContent = text;
    const sp = document.getElementById('spine');
    if (!sp) return;
    sp.className = 'spine' + (spineState ? ' ' + spineState : '');
  }

  // Transient toast for undo-baseline changes (save / export / chapter switch)
  // so the user knows the undo stack was reset rather than silently emptied.
  let toastTimer = null;
  // kind: '' (neutral), 'success', 'warning' or 'error' — picks the accent.
  function showToast(text, ms, kind) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = text;
    const k = (kind === 'success' || kind === 'warning' || kind === 'error') ? kind : '';
    el.classList.remove('success', 'warning', 'error');
    if (k) el.classList.add(k);
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function() {
      el.classList.remove('show');
    }, ms || 2200);
  }

  function initMuya(markdown) {
    if (muya) {
      suppressChange = true;
      muya.setMarkdown(markdown || '');
      suppressChange = false;
      // A fresh chapter starts with an empty undo/redo history so the buttons
      // grey out until the user actually edits this chapter.
      resetUndoHistory();
      showStatusToast('chapter_reset');
      return;
    }
    const MuyaClass = MuyaBundle.default || MuyaBundle;
    const host = document.getElementById('editor');
    muya = new MuyaClass(host, {
      markdown: markdown || '',
      spellcheckEnabled: false,
      // Persist pasted/dropped images into the workbench directory and return
      // a markdown-relative path; pick files through the shell dialog; read
      // pasted images from the OS clipboard via the shell.
      imageAction: function(path, id) {
        if (bridge) return bridge.requestSaveImage(path);
        return Promise.resolve(path);
      },
      imagePathPicker: function() {
        if (bridge) return bridge.requestPickImage();
        return Promise.resolve('');
      },
      clipboardFilePath: function() {
        if (bridge) return bridge.requestClipboardImagePath();
        return '';
      }
    });
    // Ctrl/Cmd+Z (undo) and Ctrl+Shift+Z / Ctrl+Y (redo) are handled here so
    // the browser's native contenteditable undo/redo does not desync Muya's
    // block model from the DOM. preventDefault stops the native path.
    host.addEventListener('keydown', function(ev) {
      if (activeChapter === 0) return;
      const mod = ev.ctrlKey || ev.metaKey;
      if (!mod) return;
      const key = (ev.key || '').toLowerCase();
      const isUndo = key === 'z' && !ev.shiftKey;
      const isRedo = (key === 'z' && ev.shiftKey) || key === 'y';
      if (!isUndo && !isRedo) return;
      ev.preventDefault();
      if (isUndo) {
        applyUndo();
      } else {
        applyRedo();
      }
    });
    muya.on('change', function(data) {
      // Name the edit before overwriting the chapter buffer so the undo
      // tooltip can say what it will restore.
      if (!suppressChange && activeChapter !== 0) {
        const prev = chapterMarkdown[activeChapter] || '';
        const desc = describeEdit(prev, data.markdown);
        if (desc) lastEditDescription = desc;
      }
      updateUndoRedoState(data.history);
      if (suppressChange || activeChapter === 0) return;
      chapterMarkdown[activeChapter] = data.markdown;
      dirty = true;
      pendingChapter = activeChapter;
      setStatus('编辑第 ' + activeChapter + ' 章 · 未保存', 'writing');
      updateWordCount();
      // Real-time sync to the left workbench editor (no debounce, no disk
      // write) so both panes stay in lock-step while typing.
      if (bridge) bridge.requestLiveEdit(activeChapter, data.markdown);
      // Debounced disk write; flush() forces an immediate save on switch,
      // export, or close.
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function() { flush(); }, 800);
    });
    muya.on('selectionFormats', function(formats) {
      // `formats` is a list of inline-format tokens at the caret. A token's
      // `type` is one of strong/em/del/inline_code/inline_math, and an
      // underline is reported as type 'html_tag' with tag 'u'.
      const active = {};
      (formats || []).forEach(function(t) {
        if (t && t.type === 'html_tag' && t.tag === 'u') {
          active['u'] = true;
        } else if (t && t.type) {
          active[t.type] = true;
        }
      });
      currentInlineFormats = active;
      updateToolbarState();
    });
    muya.on('selectionChange', function(sel) {
      if (!sel || !sel.start) return;
      let type = sel.start.type || 'p';
      // A table cell's leaf block is a 'span' with functionType 'cellContent',
      // and a code block's leaf is a 'span' with 'codeContent'. Detect these
      // container contexts first so the table / code buttons highlight and the
      // hint reads "表格" / "代码块".
      const leaf = sel.start.block;
      if (leaf && leaf.functionType === 'cellContent') {
        type = 'table';
      } else if (leaf && leaf.functionType === 'codeContent' && leaf.lang !== 'latex') {
        type = 'pre';
      } else {
        // Inside a list the leaf block is 'li'/'p'; the owning ul/ol appears in
        // `affiliation` (the shared paragraph ancestors). Prefer the list parent
        // so the •/1. toolbar buttons highlight correctly.
        const parents = sel.affiliation || [];
        for (let i = 0; i < parents.length; i++) {
          const p = parents[i];
          if (p && (p.type === 'ul' || p.type === 'ol')) {
            type = p.type;
            break;
          }
        }
      }
      currentBlockType = type;
      updateToolbarState();
    });
    muya.on('select-image', function(imageInfo) {
      // Muya emits this when an image is clicked/selected; keep the info so
      // the right-click menu can edit its caption / alt text.
      selectedImageInfo = imageInfo || null;
    });
  }

  function flush() {
    if (!dirty || pendingChapter === 0) return;
    clearTimeout(saveTimer);
    saveTimer = null;
    let md = chapterMarkdown[pendingChapter] || '';
    if (muya && activeChapter === pendingChapter) {
      md = muya.getMarkdown() || '';
      chapterMarkdown[pendingChapter] = md;
    }
    if (bridge) bridge.requestSaveChapter(pendingChapter, md);
    dirty = false;
    setStatus('已保存第 ' + pendingChapter + ' 章', 'saved');
    // Saving snapshots the history instead of clearing it, so the user can
    // still undo back past this save point.
    preserveUndoHistory();
    showStatusToast('saved_kept');
  }

  // ---- toolbar state feedback (highlight active format) ---------------
  // Current paragraph type (e.g. 'h2', 'blockquote', 'ul', 'ol', 'p') and the
  // set of inline formats at the caret (e.g. 'strong', 'em', 'u').
  let currentBlockType = 'p';
  let currentInlineFormats = {};

  const BLOCK_BUTTON_MAP = {
    h1: 'heading 1', h2: 'heading 2', h3: 'heading 3',
    h4: 'heading 4', h5: 'heading 5', h6: 'heading 6',
    blockquote: 'blockquote', ul: 'ul', ol: 'ol',
    mathblock: 'mathblock', pre: 'pre', table: 'table'
  };
  // Human-readable Chinese label for the current block type, shown in the
  // status bar for explicit feedback.
  const BLOCK_HINT_MAP = {
    p: '正文',
    h1: '一级标题', h2: '二级标题', h3: '三级标题',
    h4: '四级标题', h5: '五级标题', h6: '六级标题',
    blockquote: '引用', ul: '无序列表', ol: '有序列表',
    mathblock: '块级公式', pre: '代码块', table: '表格'
  };

  function updateToolbarState() {
    if (activeChapter === 0) return;
    document.querySelectorAll('#toolbar button[data-para]').forEach(function(btn) {
      btn.classList.toggle('active', btn.getAttribute('data-para') === BLOCK_BUTTON_MAP[currentBlockType]);
    });
    document.querySelectorAll('#toolbar button[data-fmt]').forEach(function(btn) {
      const fmt = btn.getAttribute('data-fmt');
      btn.classList.toggle('active', !!currentInlineFormats[fmt]);
    });
    // The table button is a special `#table-btn` (opens the row/col picker),
    // so it is not part of the `data-para` sweep. Highlight it separately.
    const tableBtn = document.getElementById('table-btn');
    if (tableBtn) {
      tableBtn.classList.toggle('active', BLOCK_BUTTON_MAP[currentBlockType] === 'table');
    }
    // Context hint (e.g. "二级标题" / "无序列表" / "表格") in the status bar.
    const hint = document.getElementById('blockhint');
    if (hint) {
      const label = BLOCK_HINT_MAP[currentBlockType] || '';
      hint.textContent = label;
      hint.style.display = label ? '' : 'none';
    }
  }

  // ---- streaming frame merge (rAF throttle) ---------------------------
  // Tracks whether the reader is parked near the bottom of the editor so the
  // incoming batches auto-scroll into view (typewriter feel). Any deliberate
  // scroll-up pauses the follow; scrolling back near the bottom resumes it.
  var streamFollowBottom = true;
  function bindStreamFollow() {
    const host = document.getElementById('editor-host');
    if (!host || host.dataset.followBound) return;
    host.dataset.followBound = '1';
    host.addEventListener('scroll', function() {
      const near = host.scrollHeight - host.scrollTop - host.clientHeight;
      streamFollowBottom = near < 80;
    });
  }
  function followStreamTail() {
    if (!streamFollowBottom) return;
    const host = document.getElementById('editor-host');
    if (!host) return;
    host.scrollTop = host.scrollHeight;
  }
  function scheduleStreamRender() {
    if (streamRenderScheduled) return;
    streamRenderScheduled = true;
    requestAnimationFrame(function() {
      streamRenderScheduled = false;
      bindStreamFollow();
      // Only re-render when the user is parked on the chapter being streamed;
      // otherwise the accumulated buffer is simply kept for later.
      if (activeChapter === 0 || !muya) return;
      suppressChange = true;
      muya.setMarkdown(chapterMarkdown[activeChapter] || '');
      suppressChange = false;
      // Newly arrived batch: keep the latest text visible, like a typewriter,
      // instead of letting content grow silently below the fold.
      followStreamTail();
    });
  }

  function rebuildOutline() {
    const oc = document.getElementById('outline');
    oc.innerHTML = '';
    const all = document.createElement('div');
    all.className = 'item' + (activeChapter === 0 ? ' active' : '');
    all.textContent = '全文预览';
    all.onclick = () => selectChapter(0);
    oc.appendChild(all);
    outline.forEach(ch => {
      const div = document.createElement('div');
      let cls = 'item';
      if (activeChapter === ch.index) cls += ' active';
      if (failedChapters[ch.index]) cls += ' failed';
      div.className = cls;
      div.textContent = (failedChapters[ch.index] ? '⚠ ' : '') + ch.index + '. ' + ch.title;
      div.onclick = () => selectChapter(ch.index);
      oc.appendChild(div);
    });
    const sel = document.getElementById('chapters');
    sel.innerHTML = '<option value="__all__">全文（预览）</option>' +
      outline.map(ch => '<option value="' + ch.index + '">' + ch.index + '. ' + ch.title + '</option>').join('');
    sel.value = activeChapter === 0 ? '__all__' : String(activeChapter);
  }

  function render() {
    initMuya(currentMarkdown());
    setStatus(
      activeChapter === 0 ? '预览模式' : '编辑第 ' + activeChapter + ' 章',
      activeChapter === 0 ? '' : 'writing'
    );
    rebuildOutline();
    updateWordCount();
    bindStreamFollow();
  }

  function selectChapter(index) {
    // Re-selecting the chapter already being edited keeps its content and undo
    // stack intact (a stray click should never wipe what the user can undo).
    // This mirrors the left workbench navigator's same-chapter behaviour.
    if (index !== 0 && index === activeChapter && (index in chapterMarkdown)) {
      return;
    }
    // Force-save any pending edits before switching away from the current chapter.
    if (index !== activeChapter) { flush(); }
    activeChapter = index;
    if (bridge) bridge.requestChapter(index);
    if (index === 0 && bridge) {
      bridge.getContent().then(function(md) {
        wholeMarkdown = md;
        render();
      });
    } else if (index !== 0 && !(index in chapterMarkdown) && bridge) {
      bridge.getChapterContent(index).then(function(md) {
        chapterMarkdown[index] = md;
        render();
      });
    } else {
      render();
    }
  }

  // ---- formatting toolbar --------------------------------------------
  function applyFormat(type) {
    if (!muya || activeChapter === 0) return;
    muya.focus();
    try { muya.format(type); } catch (e) { /* ignore */ }
  }
  function applyParagraph(type) {
    if (!muya || activeChapter === 0) return;
    muya.focus();
    // Toggle: Muya's list/quote/code-block handlers already toggle off when the
    // caret is inside that block type, but headings do not. If the caret is
    // already in the heading being clicked, demote back to a plain paragraph.
    const mapped = BLOCK_BUTTON_MAP[currentBlockType];
    if (mapped && mapped === type && /^heading [1-6]$/.test(type)) {
      try { muya.updateParagraph('paragraph'); } catch (e) { /* ignore */ }
      return;
    }
    try { muya.updateParagraph(type); } catch (e) { /* ignore */ }
  }
  function insertTableAt(rows, columns) {
    if (!muya || activeChapter === 0) return;
    muya.focus();
    try { muya.createTable({ rows: rows, columns: columns }); } catch (e) { /* ignore */ }
  }
  function applyUndo() {
    if (!muya || activeChapter === 0) return;
    // Respect the same lastEditIndex gate the button uses, so the shortcut
    // behaves identically to a click and never undoes a pure caret move.
    const btn = document.getElementById('undo-btn');
    if (btn && btn.disabled) return;
    muya.focus();
    try { muya.undo(); } catch (e) { /* ignore */ }
  }
  function applyRedo() {
    if (!muya || activeChapter === 0) return;
    const btn = document.getElementById('redo-btn');
    if (btn && btn.disabled) return;
    muya.focus();
    try { muya.redo(); } catch (e) { /* ignore */ }
  }
  function describeEdit(prev, next) {
    // Coarse diff between two markdown snapshots to name what the edit did.
    // This is a best-effort hint for the undo tooltip, not an exact op log.
    if (prev === next) return '';
    const countImg = function(s) {
      const m = s.match(/!\[[^\]]*\]\([^)]*\)/g);
      return m ? m.length : 0;
    };
    const imgDelta = countImg(next) - countImg(prev);
    if (imgDelta > 0) return '插入图片';
    if (imgDelta < 0) return '删除图片';
    const countTable = function(s) {
      const m = s.match(/^\s*\|.*\|\s*$/gm);
      return m ? m.length : 0;
    };
    if (countTable(next) !== countTable(prev)) return '调整表格';
    const lenDelta = next.length - prev.length;
    if (lenDelta > 0) return '输入内容';
    if (lenDelta < 0) return '删除内容';
    return '调整格式';
  }
  function updateUndoRedoState(history) {
    // Muya's history is { stack, index, lastEditIndex }. ``index`` advances on
    // every push — including pure cursor moves — but ``lastEditIndex`` points
    // at the most recent *content* edit. Gate undo on lastEditIndex so moving
    // the caret alone never lights the undo button; only a real edit does.
    const stack = history && Array.isArray(history.stack) ? history.stack : [];
    const index = history && typeof history.index === 'number' ? history.index : -1;
    const lastEditIndex =
      history && typeof history.lastEditIndex === 'number'
        ? history.lastEditIndex
        : -1;
    const canUndo = activeChapter !== 0 && lastEditIndex > 0;
    const canRedo = activeChapter !== 0 && index >= 0 && index < stack.length - 1;
    const undoBtn = document.getElementById('undo-btn');
    const redoBtn = document.getElementById('redo-btn');
    if (undoBtn) undoBtn.disabled = !canUndo;
    if (redoBtn) redoBtn.disabled = !canRedo;
    // Surface what the next undo would restore, so the user knows what they
    // are rolling back before clicking (or pressing Ctrl+Z).
    if (undoBtn) {
      const hint = canUndo && lastEditDescription
        ? ('撤销：' + lastEditDescription + '（Ctrl+Z）')
        : '撤销（Ctrl+Z）';
      undoBtn.title = hint;
    }
    // Show how many steps can still be undone/redone. ``lastEditIndex`` is the
    // number of content-edit snapshots at or below the caret, i.e. the undo
    // depth (every entry beyond the baseline is an edit); redo depth is the
    // number of snapshots ahead of the caret up to the top of the stack.
    const undoSteps = canUndo ? Math.max(0, lastEditIndex) : 0;
    const redoSteps = canRedo ? Math.max(0, stack.length - 1 - index) : 0;
    // Undo/redo step badges follow the button's disabled look. In the
    // whole-document preview (read-only, activeChapter === 0) the badges hide
    // entirely rather than showing a pointless "0"; in an editable chapter
    // with no steps left they dim to a translucent grey to match the disabled
    // button instead of lingering as a lit number.
    const previewOnly = activeChapter === 0;
    const undoBadge = document.getElementById('undo-count');
    const redoBadge = document.getElementById('redo-count');
    function paintHist(el, steps, isRedo) {
      if (!el) return;
      if (previewOnly) {
        el.textContent = '';
        el.classList.remove('on', 'dim');
        el.title = '';
        return;
      }
      const shown = steps > 0;
      el.textContent = shown ? String(steps > 99 ? 99 : steps) : '';
      el.classList.toggle('on', shown);
      el.classList.toggle('dim', !shown);
      el.title = shown ? ((isRedo ? '可重做 ' : '可撤销 ') + steps + ' 步') : '';
    }
    paintHist(undoBadge, undoSteps, false);
    paintHist(redoBadge, redoSteps, true);
  }
  function preserveUndoHistory() {
    // Snapshot the history on save instead of clearing it: re-assigning the
    // current stack via setHistory commits any pending entry while keeping the
    // undo chain intact, so the user can still Ctrl+Z back past the save.
    if (!muya) return;
    try {
      muya.setHistory(muya.getHistory());
    } catch (e) { /* ignore */ }
    if (muya.getHistory) {
      try { updateUndoRedoState(muya.getHistory()); } catch (e) { /* ignore */ }
    }
  }
  function resetUndoHistory() {
    // Truly clear Muya's undo/redo stack — used only on chapter switch, where
    // a stack from another chapter would otherwise bleed into this one.
    if (!muya) return;
    try { muya.clearHistory(); } catch (e) { /* ignore */ }
    updateUndoRedoState({ stack: [], index: -1 });
  }
  function insertImageFromPicker() {
    if (!muya || activeChapter === 0) return;
    muya.focus();
    if (!bridge) return;
    bridge.requestPickImage().then(function(src) {
      if (!src) return;
      try { muya.insertImage({ alt: '', src: src, title: '' }); } catch (e) { /* ignore */ }
    });
  }
  document.getElementById('undo-btn').addEventListener('mousedown', function(ev) { ev.preventDefault(); });
  document.getElementById('undo-btn').addEventListener('click', applyUndo);
  document.getElementById('redo-btn').addEventListener('mousedown', function(ev) { ev.preventDefault(); });
  document.getElementById('redo-btn').addEventListener('click', applyRedo);
  document.getElementById('image-btn').addEventListener('mousedown', function(ev) { ev.preventDefault(); });
  document.getElementById('image-btn').addEventListener('click', insertImageFromPicker);
  document.querySelectorAll('#toolbar button[data-fmt]').forEach(function(btn) {
    btn.addEventListener('mousedown', function(ev) { ev.preventDefault(); });
    btn.addEventListener('click', function() { applyFormat(btn.getAttribute('data-fmt')); });
  });
  document.querySelectorAll('#toolbar button[data-para]').forEach(function(btn) {
    btn.addEventListener('mousedown', function(ev) { ev.preventDefault(); });
    btn.addEventListener('click', function() { applyParagraph(btn.getAttribute('data-para')); });
  });

  // ---- table size picker (drag to select N×M) -------------------------
  const tablePicker = document.getElementById('table-picker');
  const tablePickerGrid = tablePicker.querySelector('.grid');
  const tablePickerLabel = tablePicker.querySelector('.label');
  const PICKER_MAX = 8;
  let pickerCells = [];
  let pickerRow = 0;
  let pickerCol = 0;

  function buildTablePicker() {
    tablePickerGrid.innerHTML = '';
    tablePickerGrid.style.gridTemplateColumns = 'repeat(' + PICKER_MAX + ', 18px)';
    pickerCells = [];
    for (let r = 0; r < PICKER_MAX; r++) {
      for (let c = 0; c < PICKER_MAX; c++) {
        const cell = document.createElement('div');
        cell.className = 'cell';
        cell.dataset.row = r;
        cell.dataset.col = c;
        tablePickerGrid.appendChild(cell);
        pickerCells.push(cell);
      }
    }
  }

  function paintPicker(row, col) {
    pickerRow = row;
    pickerCol = col;
    pickerCells.forEach(function(cell) {
      const hot = cell.dataset.row <= row && cell.dataset.col <= col;
      cell.classList.toggle('hot', hot);
    });
    tablePickerLabel.textContent = (row + 1) + ' × ' + (col + 1);
  }

  function commitPicker() {
    hideTablePicker();
    insertTableAt(pickerRow + 1, pickerCol + 1);
  }

  function movePicker(dRow, dCol) {
    const row = Math.max(0, Math.min(PICKER_MAX - 1, pickerRow + dRow));
    const col = Math.max(0, Math.min(PICKER_MAX - 1, pickerCol + dCol));
    paintPicker(row, col);
  }

  function showTablePicker() {
    if (!muya || activeChapter === 0) return;
    const btn = document.getElementById('table-btn');
    const rect = btn.getBoundingClientRect();
    tablePicker.style.display = 'block';
    // Position below the button, clamped to the viewport.
    const left = Math.max(4, rect.left);
    const top = rect.bottom + 4;
    tablePicker.style.left = left + 'px';
    tablePicker.style.top = top + 'px';
    paintPicker(0, 0);
    // Focus so arrow keys / Enter / Esc work without a mouse.
    tablePicker.focus();
  }

  function hideTablePicker() {
    tablePicker.style.display = 'none';
  }

  // Custom N×M entry for tables larger than the 8×8 grid.
  const pickerRowsInput = document.getElementById('picker-rows');
  const pickerColsInput = document.getElementById('picker-cols');
  const pickerInsertBtn = document.getElementById('picker-insert');
  const PICKER_CUSTOM_MAX = 100;

  function clampCustomSize(value) {
    const n = parseInt(value, 10);
    if (!Number.isFinite(n)) return 1;
    return Math.max(1, Math.min(PICKER_CUSTOM_MAX, n));
  }
  function insertCustomTable() {
    const rows = clampCustomSize(pickerRowsInput.value);
    const cols = clampCustomSize(pickerColsInput.value);
    hideTablePicker();
    insertTableAt(rows, cols);
  }
  pickerInsertBtn.addEventListener('click', insertCustomTable);
  pickerRowsInput.addEventListener('keydown', function(ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); insertCustomTable(); }
  });
  pickerColsInput.addEventListener('keydown', function(ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); insertCustomTable(); }
  });
  // Prevent clicks inside the custom inputs from bubbling to the grid/picker
  // handlers (they are outside the grid, but keep the picker open while typing).
  [pickerRowsInput, pickerColsInput].forEach(function(input) {
    input.addEventListener('mousedown', function(ev) { ev.stopPropagation(); });
    input.addEventListener('click', function(ev) { ev.stopPropagation(); });
  });

  buildTablePicker();
  // Drag-to-select: hovering paints the preview live; a mouse-down on a cell
  // arms the picker, and mouse-up (either a plain click or after sweeping
  // across cells) commits the chosen N×M size.
  let pickerArmed = false;
  tablePickerGrid.addEventListener('mouseover', function(ev) {
    const cell = ev.target.closest('.cell');
    if (!cell) return;
    paintPicker(Number(cell.dataset.row), Number(cell.dataset.col));
  });
  tablePickerGrid.addEventListener('mousedown', function(ev) {
    const cell = ev.target.closest('.cell');
    if (!cell) return;
    ev.preventDefault();
    pickerArmed = true;
    paintPicker(Number(cell.dataset.row), Number(cell.dataset.col));
  });
  tablePickerGrid.addEventListener('mouseup', function(ev) {
    if (!pickerArmed) return;
    pickerArmed = false;
    const cell = ev.target.closest('.cell');
    if (!cell) return;
    paintPicker(Number(cell.dataset.row), Number(cell.dataset.col));
    commitPicker();
  });
  // Keyboard navigation: arrows move the selection, Enter commits, Esc cancels.
  tablePicker.addEventListener('keydown', function(ev) {
    if (ev.key === 'ArrowLeft') { ev.preventDefault(); movePicker(0, -1); }
    else if (ev.key === 'ArrowRight') { ev.preventDefault(); movePicker(0, 1); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); movePicker(-1, 0); }
    else if (ev.key === 'ArrowDown') { ev.preventDefault(); movePicker(1, 0); }
    else if (ev.key === 'Enter') { ev.preventDefault(); commitPicker(); }
    else if (ev.key === 'Escape') { ev.preventDefault(); hideTablePicker(); }
  });
  // If the pointer is released outside the grid after arming, disarm without
  // inserting (the document-level mousedown already closes the picker).
  document.addEventListener('mouseup', function() {
    pickerArmed = false;
  });
  document.addEventListener('mousedown', function(ev) {
    if (tablePicker.style.display === 'block' && !tablePicker.contains(ev.target)
        && ev.target.id !== 'table-btn') {
      hideTablePicker();
    }
  });
  document.getElementById('table-btn').addEventListener('mousedown', function(ev) { ev.preventDefault(); });
  document.getElementById('table-btn').addEventListener('click', function(ev) {
    ev.stopPropagation();
    if (tablePicker.style.display !== 'block') { showTablePicker(); }
    else { hideTablePicker(); }
  });

  // ---- more-format dropdown (sub / sup / mark / html) --------------------
  const formatMenu = document.getElementById('format-menu');
  const moreBtn = document.getElementById('more-btn');

  function showFormatMenu() {
    if (!muya || activeChapter === 0) return;
    const rect = moreBtn.getBoundingClientRect();
    formatMenu.style.display = 'block';
    const left = Math.max(4, rect.left);
    const top = rect.bottom + 4;
    formatMenu.style.left = left + 'px';
    formatMenu.style.top = top + 'px';
  }
  function hideFormatMenu() {
    formatMenu.style.display = 'none';
  }
  moreBtn.addEventListener('mousedown', function(ev) { ev.preventDefault(); });
  moreBtn.addEventListener('click', function(ev) {
    ev.stopPropagation();
    if (formatMenu.style.display !== 'block') { showFormatMenu(); }
    else { hideFormatMenu(); }
  });
  formatMenu.addEventListener('click', function(ev) {
    const item = ev.target.closest('.mi');
    if (!item) return;
    hideFormatMenu();
    const fmt = item.getAttribute('data-fmt');
    const para = item.getAttribute('data-para');
    if (fmt) { applyFormat(fmt); }
    else if (para) { applyParagraph(para); }
  });
  document.addEventListener('mousedown', function(ev) {
    if (formatMenu.style.display === 'block' && !formatMenu.contains(ev.target)
        && ev.target.id !== 'more-btn') {
      hideFormatMenu();
    }
  });

  // ---- table context menu (insert/remove row & column) ------------------
  const tableMenu = document.getElementById('table-menu');
  let tableCellKey = null;

  function cellContentKey(target) {
    // Each Muya block renders with its key as the element id; the cell
    // content span carries functionType 'cellContent', so walk up to it.
    let node = target;
    while (node && node !== document.getElementById('editor-host')) {
      if (node.tagName === 'SPAN' && node.id && node.classList.contains('ag-cell-content')) {
        return node.id;
      }
      if (node.tagName === 'TH' || node.tagName === 'TD') {
        const span = node.querySelector('span.ag-cell-content[id]');
        if (span) return span.id;
      }
      node = node.parentElement;
    }
    return null;
  }

  function isInTable(target) {
    return !!(target && target.closest && target.closest('th, td'));
  }

  function showTableMenu(x, y) {
    tableMenu.style.display = 'block';
    tableMenu.style.left = x + 'px';
    tableMenu.style.top = y + 'px';
  }

  function hideTableMenu() {
    tableMenu.style.display = 'none';
    tableCellKey = null;
  }

  document.getElementById('editor-host').addEventListener('contextmenu', function(ev) {
    if (activeChapter === 0) return;
    if (isOnImage(ev.target)) {
      hideTableMenu();
      ev.preventDefault();
      ev.stopPropagation();
      showImageMenu(ev.clientX, ev.clientY);
      return;
    }
    if (!isInTable(ev.target)) { hideTableMenu(); hideImageMenu(); return; }
    ev.preventDefault();
    ev.stopPropagation();
    tableCellKey = cellContentKey(ev.target);
    showTableMenu(ev.clientX, ev.clientY);
  });

  tableMenu.addEventListener('mousedown', function(ev) { ev.preventDefault(); });
  tableMenu.addEventListener('click', function(ev) {
    const item = ev.target.closest('.mi');
    if (!item || !muya) return;
    const payload = {
      location: item.getAttribute('data-loc'),
      action: item.getAttribute('data-action'),
      target: item.getAttribute('data-target')
    };
    try {
      muya.editTable(payload, tableCellKey);
    } catch (e) {
      setStatus('无法编辑表格：' + e.message, 'failed');
    }
    hideTableMenu();
  });

  document.addEventListener('mousedown', function(ev) {
    if (tableMenu.style.display !== 'none' && !tableMenu.contains(ev.target)) {
      hideTableMenu();
    }
    if (imageMenu.style.display !== 'none' && !imageMenu.contains(ev.target)) {
      hideImageMenu();
    }
  });
  window.addEventListener('scroll', hideTableMenu, true);
  window.addEventListener('scroll', hideImageMenu, true);

  // ---- image context menu (edit caption / alt text) ---------------------
  const imageMenu = document.getElementById('image-menu');

  function isOnImage(target) {
    return !!(target && target.closest && target.closest('.ag-image-container, .ag-empty-image, .ag-image-fail'));
  }

  function showImageMenu(x, y) {
    imageMenu.style.display = 'block';
    imageMenu.style.left = x + 'px';
    imageMenu.style.top = y + 'px';
  }

  function hideImageMenu() {
    imageMenu.style.display = 'none';
  }

  function editImageField(field) {
    if (!muya || !selectedImageInfo) return;
    const token = selectedImageInfo.token;
    if (!token) return;
    const attrs = token.attrs || {};
    // Prefer the raw (unencoded) token fields where present so replaceImage
    // rebuilds the exact markdown; `attrs` carries render-encoded values.
    const alt = attrs.alt || '';
    const src = token.src || attrs.src || '';
    const title = token.title || attrs.title || '';
    const current = field === 'title' ? title : alt;
    const label = field === 'title' ? '图注（标题）' : '替代文字（alt）';
    const value = window.prompt('编辑' + label + '：', current);
    if (value === null) return; // cancelled
    const next = { alt: alt, src: src, title: title };
    if (field === 'title') {
      next.title = value;
    } else {
      next.alt = value;
    }
    try {
      muya.contentState.replaceImage(
        { key: selectedImageInfo.key, token: token },
        next
      );
    } catch (e) {
      setStatus('无法更新图片：' + e.message, 'failed');
    }
    hideImageMenu();
  }

  imageMenu.addEventListener('mousedown', function(ev) { ev.preventDefault(); });
  imageMenu.addEventListener('click', function(ev) {
    const item = ev.target.closest('.mi');
    if (!item) return;
    const field = item.getAttribute('data-field');
    if (field) editImageField(field);
  });

  document.getElementById('save').onclick = () => {
    flush();
    const md = currentMarkdown();
    // The keep-vs-clear decision for the editor's undo stack is made Qt-side
    // after the .md is actually written (see preserve_history_after_save /
    // clear_history_after_save), mirroring the export flow — so cancelling the
    // file dialog never falsely snapshots or clears history.
    if (bridge) bridge.requestSaveMarkdown(md);
  };
  document.getElementById('export').onclick = () => {
    flush();
    const md = currentMarkdown();
    setStatus('正在导出 DOCX…', 'exported');
    // Undo history is snapshotted (not cleared) Qt-side after a successful
    // export (see preserveUndoHistory via preserve_undo_history), so the user
    // can still undo back past the export.
    if (bridge) bridge.requestExportDocx(md);
  };
  document.getElementById('chapters').onchange = (e) => {
    if (e.target.value === '__all__') { selectChapter(0); return; }
    selectChapter(parseInt(e.target.value, 10));
  };

  new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.ldword;
    bridge.outline_changed.connect(function(json) {
      outline = JSON.parse(json);
      rebuildOutline();
    });
    bridge.content_changed.connect(function(md) {
      wholeMarkdown = md;
      if (activeChapter === 0) render();
    });
    bridge.active_chapter_changed.connect(function(index) {
      activeChapter = index;
      render();
    });
    bridge.images_dropped.connect(async function(paths) {
      // Local image files were dropped Qt-side. Insert each through Muya's
      // imageAction so it is persisted via requestSaveImage — the same chain
      // used by paste and the toolbar picker — and await one at a time so the
      // files land in the drag order (each insert settles before the next).
      if (!paths || !paths.length || !muya || activeChapter === 0) return;
      muya.focus();
      for (const p of paths) {
        if (!p) continue;
        try {
          await muya.pasteImage(String(p));
        } catch (e) { /* ignore a single bad file, keep inserting the rest */ }
      }
    });
    bridge.chapter_delta.connect(function(index, delta) {
      chapterMarkdown[index] = (chapterMarkdown[index] || '') + delta;
      if (activeChapter === index) {
        // Word count is cheap (pure string op) — update it on every token so
        // the badge tracks the live stream in real time.
        updateWordCount();
        scheduleStreamRender();
      }
    });
    bridge.chapter_started.connect(function(index) {
      chapterMarkdown[index] = '';
      delete failedChapters[index];
      if (activeChapter === index) render();
    });
    bridge.chapter_failed.connect(function(index) {
      failedChapters[index] = true;
      rebuildOutline();
      if (activeChapter === index) {
        setStatus('第 ' + index + ' 章写作中断 · 已保留已写部分', 'failed');
      }
    });
    bridge.chapter_content_set.connect(function(index, md) {
      // A chapter's final body replaced the streamed buffer (inline data-URL
      // images have been materialised to relative paths). Overwrite the live
      // buffer and re-render so the relative-path image shows immediately.
      chapterMarkdown[index] = md || '';
      updateWordCount();
      if (activeChapter === index) render();
    });
    bridge.getOutline().then(function(json) {
      outline = JSON.parse(json);
      return bridge.getContent();
    }).then(function(md) {
      wholeMarkdown = md;
      return bridge.getActiveChapter();
    }).then(function(index) {
      activeChapter = index;
      if (activeChapter !== 0) {
        return bridge.getChapterContent(activeChapter).then(function(md) {
          chapterMarkdown[activeChapter] = md;
        });
      }
    }).then(function() {
      render();
    });
  });

  // Force-flush pending edits when the page is about to be torn down.
  window.addEventListener('beforeunload', function(event) {
    if (dirty) {
      flush();
      event.preventDefault();
      event.returnValue = '';
    }
  });
</script>
</body>
</html>
"""


class EmbeddedMarkTextView(QWidget):
    """Right-side embedded MarkText (Muya) editor with QWebChannel back to Qt."""

    # Emitted when the user clicks the header's 收起/关闭 control so the
    # owning panel can collapse the right-side editor surface.
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.bridge = MarkTextBridge(self)
        self._view = QWebEngineView(self)
        self._channel = QWebChannel(self._view.page())
        self._channel.registerObject("ldword", self.bridge)
        self._view.page().setWebChannel(self._channel)
        # Intercept image files dropped onto the editor: QWebEngine's chromium
        # layer cannot expose a File's local path (and Muya expects Electron's
        # `window.electron.webUtils.getPathForFile`), so we resolve the path
        # Qt-side and push it to the page via a signal.
        self._view.setAcceptDrops(True)
        self._view.installEventFilter(self)
        self._build_worker = None
        self._build_thread = None
        self._build_dialog = None
        self._bundle_ready = False
        if _muya_bundle_needs_rebuild():
            self._start_async_bundle_build()
        else:
            self._bundle_ready = True
            self._load_editor_html()
        # Follow theme switches so the embedded editor's brand color stays in
        # sync with the rest of LDWord (deferred to visible to avoid reloading
        # a hidden view on every theme toggle).
        bind_theme(self, self._reload_editor_html_on_theme)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header_bar())
        layout.addWidget(self._view)

        # Overlay that shows “松开插入图片” while image files are dragged over
        # the editor.  It is drawn on top of the web view but ignores mouse
        # input, so it never steals the drop that Qt still routes to ``_view``.
        self._drop_hint = QLabel(self)
        self._drop_hint.setObjectName("marktext_drop_hint")
        self._drop_hint.setAlignment(Qt.AlignCenter)
        self._drop_hint.setWordWrap(True)
        self._drop_hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._drop_hint.hide()
        # Auto-hides the rejection notice after a short delay.  Non-image files
        # are rejected outright so Qt never delivers a DragLeave to hide it;
        # a one-shot timer guarantees the notice cannot linger.
        self._drop_hint_timer = QTimer(self)
        self._drop_hint_timer.setSingleShot(True)
        self._drop_hint_timer.setInterval(_DROP_REJECT_HINT_MS)
        self._drop_hint_timer.timeout.connect(self._auto_hide_drop_hint)

    def _build_header_bar(self) -> QWidget:
        """A slim header above the editor so the panel is always dismissible.

        The right-side MarkText surface is shown automatically while authoring
        chapters, and previously offered no visible close control.  This small
        bar titles it and gives an unmistakable 收起 (×) button that collapses
        the whole surface.
        """
        theme = get_theme()
        bg = str(getattr(theme, "panel", "#1f2226") or "#1f2226")
        fg = str(getattr(theme, "text_secondary", "#b8bec6") or "#b8bec6")
        border = str(getattr(theme, "divider", "#3a3f46") or "#3a3f46")
        bar = QWidget(self)
        bar.setObjectName("marktext_header_bar")
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"QWidget#marktext_header_bar {{ background:{bg}; }}"
            f"QLabel {{ color:{fg}; font-size:12px; }}"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 0, 8, 0)
        row.setSpacing(8)
        title = QLabel("实时排版预览", bar)
        row.addWidget(title)
        row.addStretch(1)
        close_btn = QPushButton("收起 ×", bar)
        close_btn.setObjectName("marktext_close_btn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("收起右侧实时排版视图")
        close_btn.setFixedHeight(24)
        close_btn.setStyleSheet(
            f"QPushButton#marktext_close_btn {{"
            f"  background:{bg}; color:{fg}; border:1px solid {border};"
            f"  border-radius:4px; padding:0 10px; font-size:12px;"
            f"}}"
            f"QPushButton#marktext_close_btn:hover {{"
            f"  background:{border}; color:#ffffff;"
            f"}}"
        )
        close_btn.clicked.connect(self.close_requested)
        row.addWidget(close_btn)
        self._marktext_close_button = close_btn
        return bar

    def _auto_hide_drop_hint(self) -> None:
        self._show_drop_hint(False)

    def _start_drop_hint_auto_hide(self) -> None:
        """(Re)arm the one-shot timer that hides the rejection notice."""
        timer = getattr(self, "_drop_hint_timer", None)
        if timer is None:
            return
        timer.stop()
        timer.start()

    def _stop_drop_hint_auto_hide(self) -> None:
        """Cancel a pending auto-hide (image drag still hovering or drag ended)."""
        timer = getattr(self, "_drop_hint_timer", None)
        if timer is not None:
            timer.stop()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        hint = getattr(self, "_drop_hint", None)
        if hint is not None and hint.isVisible():
            self._reposition_drop_hint()

    def _reposition_drop_hint(self) -> None:
        """Keep the drag hint centered over the editor viewport."""
        hint = getattr(self, "_drop_hint", None)
        if hint is None:
            return
        inset = 14
        hint.setGeometry(
            inset,
            inset,
            max(0, self.width() - 2 * inset),
            max(0, self.height() - 2 * inset),
        )
        hint.raise_()

    def _show_drop_hint(
        self,
        visible: bool,
        accepted: bool = True,
        *,
        rejected_exts: list[str] | None = None,
    ) -> None:
        """Toggle the drag visual feedback.

        ``accepted`` selects which feedback is shown: green/brand “松开插入
        图片” when the dragged files can be inserted, or an amber “仅支持图片
        文件” rejection when a non-image file is dragged.

        ``rejected_exts`` optionally lists the unsupported file extensions that
        were dragged, so the notice can tell the user which types to remove.
        """
        hint = getattr(self, "_drop_hint", None)
        if hint is None:
            return
        if visible:
            theme = get_theme()
            radius = int(getattr(theme, "radius_md", 10) or 10)
            if accepted:
                accent = getattr(theme, "primary", "#1677FF") or "#1677FF"
                tint = theme.primary_light or accent
                bg = theme_rgba(tint, 0.32)
                border = theme_rgba(accent, 0.9)
                title = "松开插入图片"
                subtitle = "支持一次拖入多张图片"
            else:
                accent = getattr(theme, "warning", "#FAAD14") or "#FAAD14"
                tint = getattr(theme, "warning_bg", accent)
                bg = theme_rgba(tint, 0.55)
                border = theme_rgba(accent, 0.9)
                title = "仅支持图片文件"
                subtitle = self._rejection_subtitle(rejected_exts)
            hint.setStyleSheet(
                f"""
                QLabel#marktext_drop_hint {{
                    background-color: {bg};
                    border: 2px dashed {border};
                    border-radius: {radius}px;
                    color: {getattr(theme, 'text_primary', '#1E293B')};
                }}
                """
            )
            hint.setText(
                f"<div style='font-size:16px; font-weight:600;'>{title}</div>"
                f"<div style='font-size:12px; margin-top:6px; color:{theme_rgba(theme.text_secondary or '#64748B', 0.9)};'>"
                f"{subtitle}</div>"
            )
            self._reposition_drop_hint()
            hint.show()
            hint.raise_()
        else:
            hint.hide()

    @staticmethod
    def _rejection_subtitle(rejected_exts: list[str] | None) -> str:
        """Build the rejection notice's second line.

        When the drag contained local non-image files we recognise their
        extensions and list them so the user knows exactly what to remove; when
        nothing concrete was detected fall back to a generic hint.
        """
        exts = [str(e).strip() for e in (rejected_exts or ()) if str(e).strip()]
        if not exts:
            return "请拖入 PNG / JPG / GIF 等图片文件"
        label = "不支持 " + " / ".join(exts)
        return label + "。请拖入 PNG / JPG / GIF 等图片文件"

    @staticmethod
    def _unsupported_extensions(urls) -> list[str]:
        """Return the distinct, non-empty extensions of local non-image files
        in *urls*, uppercased and dot-prefixed (e.g. ``".PDF"``)."""
        seen: list[str] = []
        for url in urls or ():
            if _is_image_url(url) or not url.isLocalFile():
                continue
            try:
                ext = Path(url.toLocalFile()).suffix.casefold()
            except (OSError, ValueError, TypeError):
                ext = ""
            if ext and ext not in seen:
                seen.append(ext)
        return [e.upper() for e in seen]

    def eventFilter(self, obj, event):  # noqa: N802
        """Resolve local image(s) dropped onto the editor and push them to the
        page; show a visual overlay while any file drag hovers — accepted ones
        read “松开插入图片”, rejected non-image files read “仅支持图片文件”."""
        if obj is self._view and event.type() in (QEvent.DragEnter, QEvent.DragMove):
            mime = event.mimeData()
            if mime and mime.hasUrls():
                urls = mime.urls()
                if any(_is_image_url(url) for url in urls):
                    # Image drag: accept (cursor allows) and keep the hint up
                    # while it hovers; cancel any pending auto-hide.
                    self._stop_drop_hint_auto_hide()
                    self._show_drop_hint(True, accepted=True)
                    event.acceptProposedAction()
                    return True
                if any(url.isLocalFile() for url in urls):
                    # A non-image file drag is rejected outright so the cursor
                    # shows “not allowed”.  Because Qt stops routing the drag to
                    # us once it is rejected, there is no DragLeave to hide the
                    # notice — a one-shot timer auto-hides it shortly.
                    rejected_exts = self._unsupported_extensions(urls)
                    self._show_drop_hint(
                        True,
                        accepted=False,
                        rejected_exts=rejected_exts,
                    )
                    self._start_drop_hint_auto_hide()
                    event.ignore()
                    return True
        if obj is self._view and event.type() == QEvent.DragLeave:
            self._stop_drop_hint_auto_hide()
            self._show_drop_hint(False)
            return False
        if obj is self._view and event.type() == QEvent.Drop:
            mime = event.mimeData()
            # Always hide the hint once the drag ends, image or not.
            self._stop_drop_hint_auto_hide()
            self._show_drop_hint(False)
            if mime and mime.hasUrls():
                # Collect EVERY dropped image so a multi-file drag inserts them
                # all, in the drag order, instead of stopping at the first URL.
                paths = [
                    url.toLocalFile()
                    for url in mime.urls()
                    if _is_image_url(url) and url.toLocalFile()
                ]
                if paths:
                    # Accept the drop so the OS drag source sees a successful
                    # handoff (otherwise it may treat it as a cancelled drop).
                    event.acceptProposedAction()
                    self.bridge.notifyImagesDropped(paths)
                    return True
                # A dropped non-image file is intentionally ignored (rejected).
                event.ignore()
        return super().eventFilter(obj, event)

    def _start_async_bundle_build(self) -> None:
        """Build the Muya bundle off the GUI thread behind a progress dialog.

        First build can take tens of seconds; a modal, indeterminate progress
        dialog keeps the user informed instead of a silent 300s freeze.
        """
        from src.shared.ui.theme import get_theme

        theme = get_theme()
        dialog = QDialog(self)
        dialog.setWindowTitle("准备编辑器组件")
        dialog.setModal(True)
        dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("正在构建 MarkText 编辑器组件…", dialog)
        title.setStyleSheet(f"color: {theme.text_primary}; font-size: 14px; font-weight: 600;")
        hint = QLabel(
            "首次运行需要编译编辑器内核，通常几秒到几十秒。\n请勿关闭窗口。",
            dialog,
        )
        hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
        bar = QProgressBar(dialog)
        bar.setRange(0, 0)  # indeterminate
        bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: {theme.border_light};"
            f" border-radius: 3px; height: 6px; }}"
            f"QProgressBar::chunk {{ background: {theme.primary}; border-radius: 3px; }}"
        )
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(bar)
        dialog.setStyleSheet(f"QDialog {{ background: {theme.bg_card}; }}")
        self._build_dialog = dialog

        worker = _MuyaBuildWorker()
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_bundle_build_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._build_worker = worker
        self._build_thread = thread
        thread.start()
        dialog.open()

    def _on_bundle_build_finished(self, ok: bool) -> None:
        """Close the progress dialog and load (or degrade) the editor."""
        if self._build_dialog is not None:
            self._build_dialog.accept()
            self._build_dialog.deleteLater()
            self._build_dialog = None
        self._bundle_ready = bool(ok)
        self._load_editor_html()

    def _build_editor_html(self) -> str:
        """Return the editor HTML with theme + shared status messages injected."""
        from src.assistant.ui.status_toast import status_toast_payload

        html = _HTML.replace(
            "/* __LDWORD_THEME_VARS__ injected by the Qt shell from get_theme(). */",
            _theme_css_vars(),
        )
        return html.replace(
            "<!-- __LDWORD_STATUS_MSGS__ injected by the Qt shell (single source of truth). -->",
            "<script>\n"
            "window.__ldwordStatusMessages = "
            + json.dumps(status_toast_payload(), ensure_ascii=False)
            + ";\n"
            "function showStatusToast(key) {\n"
            "  var m = window.__ldwordStatusMessages && window.__ldwordStatusMessages[key];\n"
            "  if (!m || typeof showToast !== 'function') return;\n"
            "  showToast(m.text, m.ms || 2200, m.kind || '');\n"
            "}\n"
            "</script>",
        )

    def _load_editor_html(self) -> None:
        """(Re)load the embedded editor page with the current theme."""
        if self._bundle_ready:
            # baseUrl points at the web dir so <script src="muya.bundle.js"> and
            # <link href="muya.bundle.css"> resolve to the built artifacts.
            self._view.setHtml(
                self._build_editor_html(),
                QUrl.fromLocalFile(str(_WEB_DIR) + "/"),
            )
        else:
            self._view.setHtml(
                "<body style='background:#1f2226;color:#e6e6e6;font-family:sans-serif;"
                "padding:24px'><h2>编辑器组件未就绪</h2><p>Muya 编辑器构建产物缺失，"
                "且无法自动构建（需要 Node.js 与 marktext-develop 依赖）。</p>"
                "<p>请运行：</p><pre>cd marktext-develop/packages/muyajs\n"
                "node build_muya.mjs</pre></body>"
            )

    def _reload_editor_html_on_theme(self) -> None:
        """Theme changed: re-inject CSS variables into the editor page."""
        if self._bundle_ready:
            self._load_editor_html()

    def append_chapter_delta(self, index: int, delta: str) -> None:
        """Push a live writing delta for *index* into the embedded view."""
        self.bridge.append_delta(int(index or 0), str(delta or ""))

    def start_chapter(self, index: int) -> None:
        """Signal the page that chapter *index* is starting (clears its buffer)."""
        self.bridge.start_chapter(int(index or 0))

    def fail_chapter(self, index: int) -> None:
        """Flag chapter *index* as failed in the outline, keeping its partial body."""
        self.bridge.fail_chapter(int(index or 0))

    def set_outline(self, titles: list[str]) -> None:
        self.bridge.set_outline(list(titles or ()))

    def set_content(self, markdown: str) -> None:
        self.bridge.set_content(str(markdown or ""))

    def set_active_chapter(self, index: int) -> None:
        self.bridge.set_active_chapter(int(index or 0))

    def refresh_chapter(self, index: int, markdown: str) -> None:
        """Replace a chapter's live buffer with its final body and re-render.

        Called after inline data-URL images are materialised so the editor
        shows relative-path images instead of the raw base64 stream.
        """
        self.bridge.set_chapter_content_now(int(index or 0), str(markdown or ""))

    def set_image_directory(self, path: str) -> None:
        """Point the editor's image persistence at the workbench directory so
        pasted/picked images are copied next to the source document."""
        self.bridge.set_image_directory(str(path or ""))

    def flush_now(self) -> None:
        """Force the page to persist any pending edits immediately.

        Called by the host panel before switching sessions or closing, so an
        in-progress edit is never lost when the web view is torn down.
        """
        self._view.page().runJavaScript("if (typeof flush === 'function') { flush(); }")

    def apply_undo_baseline(self, keep: bool, toast: str = "") -> None:
        """Apply one undo/redo baseline decision to the live editor.

        Called by :func:`src.assistant.ui.undo_policy.apply_to_view` as the
        single low-level entry point for every baseline event (export, save,
        chapter switch, close).  ``keep=True`` snapshots the stack so the user
        can still undo back past the event; ``keep=False`` truly clears it for
        a fresh baseline.  ``toast`` (optional status key) is surfaced through
        the same unified toast table as the other panes.
        """
        if keep:
            fn = "preserveUndoHistory"
        else:
            fn = "resetUndoHistory"
        toast_expr = (
            f"  if (typeof showStatusToast === 'function') {{ showStatusToast('{toast}'); }}"
            if toast
            else ""
        )
        self._view.page().runJavaScript(
            f"if (typeof {fn} === 'function') {{"
            f"  {fn}();"
            f"{toast_expr}"
            "}"
        )

    def preserve_undo_history(self) -> None:
        """Snapshot (not clear) the editor's undo stack after export (keep)."""
        self.apply_undo_baseline(True, "exported_kept")

    def clear_undo_history(self) -> None:
        """Truly clear the editor's undo stack after export (clear)."""
        self.apply_undo_baseline(False, "exported_cleared")

    def preserve_history_after_save(self) -> None:
        """Snapshot the undo stack after a save-to-file (keep)."""
        self.apply_undo_baseline(True, "saved_kept")

    def clear_history_after_save(self) -> None:
        """Truly clear the undo stack after a save-to-file (clear)."""
        self.apply_undo_baseline(False, "saved_cleared")
