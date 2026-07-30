"""Local image helper functions for the assets panel."""

from __future__ import annotations

from src.config.materials import IMAGE_EXTENSIONS
from src.qt_api import QPixmap, QSize, Qt
from src.shared.ui.path_drop import PathAcceptancePolicy
from src.ui.panels.assets.fields import _asset_role_label


def _image_file_dialog_filter() -> str:
    return _image_path_policy().dialog_filter


def _image_path_policy() -> PathAcceptancePolicy:
    return PathAcceptancePolicy(
        path_kind="file",
        suffixes=tuple(sorted(IMAGE_EXTENSIONS)),
        dialog_label="图片文件",
        include_all_files=False,
    )


def _load_scaled_pixmap(path: str, size: QSize) -> QPixmap | None:
    if not str(path or "").strip():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _image_quality_text(path: str, *, role: str = "") -> str:
    if not str(path or "").strip():
        return "未选择图片。"
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return "无法读取尺寸，建议重新选择图片。"
    width = pixmap.width()
    height = pixmap.height()
    short_side = min(width, height)
    size_text = f"尺寸 {width}x{height}"
    minimum = _asset_role_min_short_side(role)
    role_text = _asset_role_label(role) if role else "图片"
    if short_side < minimum:
        return f"{size_text}，作为{role_text}偏小，建议至少 {minimum}px 以上，生成后可能模糊。"
    if short_side < minimum * 1.5:
        return f"{size_text}，作为{role_text}可用，建议换更清晰图片。"
    return f"{size_text}，作为{role_text}清晰度看起来够用。"


def _asset_role_min_short_side(role: str) -> int:
    return {
        "logo": 300,
        "seal": 300,
        "legal_signature": 240,
        "agent_signature": 240,
        "qualification": 900,
        "qrcode": 300,
        "cover": 900,
    }.get(str(role or ""), 300)


__all__ = [
    "_load_scaled_pixmap",
    "_image_file_dialog_filter",
    "_image_path_policy",
    "_image_quality_text",
    "_asset_role_min_short_side",
]
