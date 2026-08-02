"""Build deterministic Windows application and installer icon assets."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOGO = ROOT / "src" / "shared" / "ui" / "icons" / "app_logo.svg"
APP_PNG = ROOT / "src" / "shared" / "ui" / "icons" / "app_icon.png"
INSTALLER_ASSET_ROOT = ROOT / "installer" / "assets"
APP_ICO = INSTALLER_ASSET_ROOT / "Alavette-Form.ico"
SETUP_PNG = INSTALLER_ASSET_ROOT / "Alavette-Form-Setup.png"
SETUP_ICO = INSTALLER_ASSET_ROOT / "Alavette-Form-Setup.ico"

CANVAS_SIZE = 1024
ICON_SIZES = (
    (16, 16),
    (20, 20),
    (24, 24),
    (32, 32),
    (40, 40),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
)
LOGO_DARK = "#1E293B"
LOGO_LIGHT = "#1677FF"
TILE_BACKGROUND = "#F4F8FD"
TILE_BORDER = "#B9CCE3"


def _logo_renderer() -> QSvgRenderer:
    svg = SOURCE_LOGO.read_text(encoding="utf-8")
    svg = svg.replace("__LOGO_DARK__", LOGO_DARK)
    svg = svg.replace("__LOGO_LIGHT__", LOGO_LIGHT)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid application logo SVG: {SOURCE_LOGO}")
    return renderer


def _draw_tile(painter: QPainter) -> None:
    tile = QRectF(32, 32, 960, 960)
    path = QPainterPath()
    path.addRoundedRect(tile, 184, 184)
    painter.fillPath(path, QColor(TILE_BACKGROUND))
    painter.setPen(QPen(QColor(TILE_BORDER), 14))
    painter.drawPath(path)


def _draw_setup_badge(painter: QPainter) -> None:
    outer = QRectF(702, 702, 266, 266)
    painter.setPen(QPen(QColor("#FFFFFF"), 22))
    painter.setBrush(QColor("#12345B"))
    painter.drawEllipse(outer)

    pen = QPen(QColor("#FFFFFF"), 34)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    center_x = outer.center().x()
    painter.drawLine(int(center_x), 760, int(center_x), 851)
    arrow = QPainterPath()
    arrow.moveTo(center_x - 47, 819)
    arrow.lineTo(center_x, 870)
    arrow.lineTo(center_x + 47, 819)
    painter.drawPath(arrow)

    tray = QPainterPath()
    tray.moveTo(758, 875)
    tray.lineTo(758, 902)
    tray.quadTo(758, 922, 778, 922)
    tray.lineTo(892, 922)
    tray.quadTo(912, 922, 912, 902)
    tray.lineTo(912, 875)
    painter.drawPath(tray)


def _render_png(path: Path, *, installer: bool) -> None:
    image = QImage(
        CANVAS_SIZE,
        CANVAS_SIZE,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        _draw_tile(painter)
        _logo_renderer().render(painter, QRectF(132, 124, 760, 760))
        if installer:
            _draw_setup_badge(painter)
    finally:
        painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Could not save Windows icon preview: {path}")


def _write_ico(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.convert("RGBA").save(destination, format="ICO", sizes=ICON_SIZES)


def build_icon_assets(
    *,
    app_png: Path = APP_PNG,
    app_ico: Path = APP_ICO,
    setup_png: Path = SETUP_PNG,
    setup_ico: Path = SETUP_ICO,
) -> tuple[Path, ...]:
    _render_png(app_png, installer=False)
    _render_png(setup_png, installer=True)
    _write_ico(app_png, app_ico)
    _write_ico(setup_png, setup_ico)
    return app_png, app_ico, setup_png, setup_ico


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate Alavette Form Windows icon assets."
    )
    parser.parse_args(argv)
    for path in build_icon_assets():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
