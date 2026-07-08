"""Presenter mixin for full-image preview dialog behavior."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from src.qt_api import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPixmap,
    QPushButton,
    QScrollArea,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.services.material_assets import (
    question_figure_items,
    question_figure_payload_matches_item,
    question_figure_target_label,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import get_theme
from src.ui.panels.assets.fields import _asset_role_label
from src.ui.panels.assets.image_helpers import _image_quality_text, _load_scaled_pixmap
from src.ui.panels.assets.items import _normalized_asset_item_payloads


class ImagePreviewPresenterMixin:
    """Coordinate the local full-image preview dialog and compare actions."""

    def _set_current_image_preview_path(
        self,
        path: str,
        *,
        display_name: str = "",
        compare_reference: str = "",
        compare_source: str = "",
        compare_display_name: str = "",
        compare_options: Sequence[Mapping[str, str]] | None = None,
        question_figure_row: int | None = None,
    ) -> None:
        candidate = str(path or "").strip()
        has_preview = bool(candidate and Path(candidate).is_file())
        self._current_image_preview_path = candidate if has_preview else ""
        self._current_image_preview_display_name = (
            str(display_name or "").strip() or Path(candidate).name
            if has_preview
            else ""
        )
        self._current_image_preview_compare_reference = (
            str(compare_reference or "").strip() if has_preview else ""
        )
        self._current_image_preview_compare_source = (
            str(compare_source or "").strip() if has_preview else ""
        )
        self._current_image_preview_compare_display_name = (
            str(compare_display_name or "").strip()
            if has_preview and compare_reference
            else ""
        )
        normalized_options: list[dict[str, str]] = []
        if has_preview:
            for option in compare_options or ():
                reference = str(option.get("reference", "") or "").strip()
                if not reference:
                    continue
                label = str(option.get("label", "") or "").strip()
                display = str(option.get("display_name", "") or "").strip()
                normalized_options.append(
                    {
                        "label": label
                        or display
                        or Path(reference).name,
                        "reference": reference,
                        "source": str(option.get("source", "") or "").strip(),
                        "display_name": display
                        or Path(reference).name,
                        "kind_label": str(option.get("kind_label", "") or "").strip()
                        or "题图对比",
                    }
                )
            if not normalized_options and compare_reference:
                normalized_options.append(
                    {
                        "label": compare_display_name
                        or Path(compare_reference).name,
                        "reference": str(compare_reference or "").strip(),
                        "source": str(compare_source or "").strip(),
                        "display_name": compare_display_name
                        or Path(compare_reference).name,
                        "kind_label": "缩略图对比",
                    }
                )
        self._current_image_preview_compare_options = normalized_options
        if not has_preview:
            self._current_image_preview_question_figure_row = -1
        elif question_figure_row is not None:
            self._current_image_preview_question_figure_row = int(question_figure_row)
        button = getattr(self, "_full_image_preview_btn", None)
        if button is not None:
            button.setEnabled(bool(self._current_image_preview_path))

    def _set_image_preview(self, path: str, *, role: str = "") -> None:
        if not hasattr(self, "_image_preview_label"):
            return
        pixmap = _load_scaled_pixmap(path, QSize(260, 180))
        if pixmap is None:
            self._set_current_image_preview_path("")
            self._image_preview_label.clear()
            self._image_preview_label.setText("当前材料位还没有选择图片。")
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("当前材料位还没有选择图片。")
            return
        self._set_current_image_preview_path(path)
        self._image_preview_label.setText("")
        self._image_preview_label.setPixmap(pixmap)
        if hasattr(self, "_image_assets_status_label"):
            role_text = _asset_role_label(role, self._asset_slot_specs) if role else "图片"
            self._image_assets_status_label.setText(
                f"正在查看{role_text}：{Path(path).name} · {_image_quality_text(path, role=role)}"
            )

    def _configure_full_image_preview_tool_button(
        self,
        button: QPushButton,
        icon_name: str,
        tooltip: str,
    ) -> None:
        self._configure_asset_icon_button(button, icon_name, tooltip)
        theme = get_theme()
        try:
            from src.ui.icons.catalog import get_icon

            button.setIcon(get_icon(icon_name, 16, theme.icon_primary))
        except Exception:
            button.setIcon(button.icon())
        apply_button_variant(button, "secondary")
        button.setStyleSheet(build_button_stylesheet(theme))

    def _refresh_full_image_preview_zoom_label(self) -> None:
        label = getattr(self, "_full_image_preview_zoom_label", None)
        if label is None:
            return
        label.setText(f"{round(self._full_image_preview_zoom * 100):d}%")

    def _refresh_full_image_preview_pixmap(self) -> None:
        original = getattr(self, "_full_image_preview_original_pixmap", None)
        label = getattr(self, "_full_image_preview_label", None)
        if original is None or original.isNull() or label is None:
            return
        width = max(1, round(original.width() * self._full_image_preview_zoom))
        height = max(1, round(original.height() * self._full_image_preview_zoom))
        if width == original.width() and height == original.height():
            scaled = original
        else:
            scaled = original.scaled(
                QSize(width, height),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        label.setPixmap(scaled)
        label.resize(scaled.size())
        self._refresh_full_image_preview_zoom_label()

    def _set_full_image_preview_zoom(self, zoom: float) -> None:
        self._full_image_preview_zoom = min(max(float(zoom), 0.1), 4.0)
        self._refresh_full_image_preview_pixmap()

    def _zoom_full_image_preview(self, factor: float) -> None:
        self._set_full_image_preview_zoom(self._full_image_preview_zoom * factor)

    def _reset_full_image_preview_zoom(self) -> None:
        self._set_full_image_preview_zoom(1.0)

    def _fit_full_image_preview_to_window(self) -> None:
        original = getattr(self, "_full_image_preview_original_pixmap", None)
        scroll = getattr(self, "_full_image_preview_scroll", None)
        if original is None or original.isNull() or scroll is None:
            return
        viewport_size = scroll.viewport().size()
        available_width = max(1, viewport_size.width() - 8)
        available_height = max(1, viewport_size.height() - 8)
        scale = min(
            available_width / max(1, original.width()),
            available_height / max(1, original.height()),
            1.0,
        )
        self._set_full_image_preview_zoom(scale)

    def _selected_full_image_preview_compare_option(self) -> dict[str, str]:
        options = list(getattr(self, "_current_image_preview_compare_options", []) or [])
        combo = getattr(self, "_full_image_preview_compare_combo", None)
        if options and combo is not None:
            index = combo.currentIndex()
            if 0 <= index < len(options):
                return dict(options[index])
        reference = str(
            getattr(self, "_current_image_preview_compare_reference", "") or ""
        ).strip()
        if not reference:
            return {}
        return {
            "reference": reference,
            "source": str(
                getattr(self, "_current_image_preview_compare_source", "") or ""
            ).strip(),
            "display_name": str(
                getattr(self, "_current_image_preview_compare_display_name", "")
                or ""
            ).strip(),
            "kind_label": "缩略图对比",
        }

    def _open_full_image_preview_compare(self) -> bool:
        option = self._selected_full_image_preview_compare_option()
        reference = str(option.get("reference", "") or "").strip()
        if not reference:
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("当前预览没有可对比的缩略图。")
            return False
        source = str(option.get("source", "") or "").strip()
        display_name = (
            str(option.get("display_name", "") or "").strip()
            or Path(reference).name
        )
        kind_label = str(option.get("kind_label", "") or "").strip() or "题图对比"
        compare_path = reference
        if not Path(compare_path).is_file():
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("缩略图对比文件不存在。")
            return False
        pixmap = QPixmap(compare_path)
        if pixmap.isNull():
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("缩略图对比图片无法打开。")
            return False
        title = getattr(self, "_full_image_preview_compare_title", None)
        if title is not None:
            title.setText(
                f"对比：{display_name} · {pixmap.width()} × {pixmap.height()} px"
            )
        label = getattr(self, "_full_image_preview_compare_label", None)
        if label is not None:
            label.setPixmap(pixmap)
            label.resize(pixmap.size())
        panel = getattr(self, "_full_image_preview_compare_panel", None)
        if panel is not None:
            panel.setVisible(True)
        if hasattr(self, "_image_assets_status_label"):
            self._image_assets_status_label.setText(f"已打开{kind_label}：{display_name}")
        return True

    def _current_full_image_preview_region_payload(
        self,
        *,
        reference: str,
        display_name: str,
        kind_label: str,
    ) -> dict[str, object]:
        original = getattr(self, "_full_image_preview_original_pixmap", None)
        scroll = getattr(self, "_full_image_preview_scroll", None)
        zoom = max(float(getattr(self, "_full_image_preview_zoom", 1.0) or 1.0), 0.01)
        image_width = original.width() if original is not None and not original.isNull() else 0
        image_height = original.height() if original is not None and not original.isNull() else 0
        viewport_x = 0
        viewport_y = 0
        viewport_width = image_width
        viewport_height = image_height
        if scroll is not None:
            viewport = scroll.viewport().size()
            viewport_x = round(scroll.horizontalScrollBar().value() / zoom)
            viewport_y = round(scroll.verticalScrollBar().value() / zoom)
            viewport_width = round(viewport.width() / zoom)
            viewport_height = round(viewport.height() / zoom)
        if image_width > 0:
            viewport_x = min(max(0, viewport_x), max(0, image_width - 1))
            viewport_width = max(1, min(viewport_width, image_width - viewport_x))
        if image_height > 0:
            viewport_y = min(max(0, viewport_y), max(0, image_height - 1))
            viewport_height = max(1, min(viewport_height, image_height - viewport_y))
        compare_label = getattr(self, "_full_image_preview_compare_label", None)
        compare_pixmap = compare_label.pixmap() if compare_label is not None else None
        compare_width = (
            compare_pixmap.width()
            if compare_pixmap is not None and not compare_pixmap.isNull()
            else 0
        )
        compare_height = (
            compare_pixmap.height()
            if compare_pixmap is not None and not compare_pixmap.isNull()
            else 0
        )
        return {
            "schema_version": 1,
            "type": "current_view",
            "unit": "px",
            "source": "assets_panel_full_preview",
            "image": {
                "path": str(getattr(self, "_current_image_preview_path", "") or ""),
                "display_name": str(
                    getattr(self, "_current_image_preview_display_name", "") or ""
                ),
                "width": image_width,
                "height": image_height,
            },
            "view": {
                "x": viewport_x,
                "y": viewport_y,
                "width": viewport_width,
                "height": viewport_height,
                "zoom": round(zoom, 4),
            },
            "compare": {
                "reference": str(reference or ""),
                "display_name": str(display_name or ""),
                "kind_label": str(kind_label or ""),
                "width": compare_width,
                "height": compare_height,
            },
        }

    def _current_full_image_preview_region_summary(
        self,
        region: Mapping[str, object],
    ) -> str:
        view = region.get("view", {}) if isinstance(region, Mapping) else {}
        image = region.get("image", {}) if isinstance(region, Mapping) else {}
        if not isinstance(view, Mapping):
            return ""
        zoom = float(view.get("zoom") or 1.0)
        pieces = [
            f"x={int(view.get('x') or 0)}",
            f"y={int(view.get('y') or 0)}",
            f"w={int(view.get('width') or 0)}",
            f"h={int(view.get('height') or 0)}",
            f"zoom={round(zoom * 100):d}%",
        ]
        if isinstance(image, Mapping) and image.get("width") and image.get("height"):
            pieces.append(f"image={image.get('width')}x{image.get('height')}")
        return "current_view(" + ", ".join(pieces) + ")"

    def _mark_current_full_image_preview_compare_issue(self) -> bool:
        option = self._selected_full_image_preview_compare_option()
        reference = str(option.get("reference", "") or "").strip()
        if not reference:
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("请先选择一个对比对象。")
            return False
        row = int(getattr(self, "_current_image_preview_question_figure_row", -1))
        if row < 0:
            table = getattr(self, "_question_figure_items_table", None)
            row = table.currentRow() if table is not None else -1
        question_items = question_figure_items(self._current_asset_items())
        if row < 0 or row >= len(question_items):
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("当前大图没有可标注的题图行。")
            return False
        target = question_items[row]
        payloads = _normalized_asset_item_payloads(self._asset_item_payloads)
        display_name = (
            str(option.get("display_name", "") or "").strip()
            or Path(reference).name
        )
        kind_label = str(option.get("kind_label", "") or "").strip() or "题图对比"
        marked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        region = self._current_full_image_preview_region_payload(
            reference=reference,
            display_name=display_name,
            kind_label=kind_label,
        )
        region_summary = self._current_full_image_preview_region_summary(region)
        updated = False
        for payload in payloads:
            if not question_figure_payload_matches_item(payload, target):
                continue
            metadata = (
                dict(payload.get("metadata", {}) or {})
                if isinstance(payload.get("metadata", {}), Mapping)
                else {}
            )
            metadata.update(
                {
                    "comparison_issue_status": "flagged",
                    "comparison_issue_type": "manual_compare",
                    "comparison_issue_reference": reference,
                    "comparison_issue_display_name": display_name,
                    "comparison_issue_kind": kind_label,
                    "comparison_issue_marked_at": marked_at,
                    "comparison_issue_summary": (
                        f"{question_figure_target_label(target)} "
                        f"{kind_label}: {display_name}"
                    ),
                    "comparison_issue_region_type": "current_view",
                    "comparison_issue_region_json": json.dumps(
                        region,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "comparison_issue_region_summary": region_summary,
                }
            )
            payload["metadata"] = metadata
            updated = True
            break
        if not updated:
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("当前题图不是结构化题图条目，暂不能标注。")
            return False
        self._asset_item_payloads = payloads
        self._persist_current_profile_editor()
        self._refresh_summary()
        table = getattr(self, "_question_figure_items_table", None)
        if table is not None and row < table.rowCount():
            table.setCurrentCell(row, 0)
            table.selectRow(row)
        if hasattr(self, "_image_assets_status_label"):
            self._image_assets_status_label.setText(
                f"已标记对比问题：{display_name}"
            )
        return True

    def _open_current_image_preview_dialog(self) -> bool:
        path = str(getattr(self, "_current_image_preview_path", "") or "").strip()
        if not path or not Path(path).is_file():
            self._set_current_image_preview_path("")
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("当前没有可打开的大图预览。")
            return False
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._set_current_image_preview_path("")
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("当前预览图片无法打开。")
            return False
        display_name = (
            str(getattr(self, "_current_image_preview_display_name", "") or "").strip()
            or Path(path).name
        )
        existing = getattr(self, "_full_image_preview_dialog", None)
        if existing is not None:
            existing.close()
        dialog = QDialog(self)
        dialog.setObjectName("asset_full_image_preview_dialog")
        dialog.setWindowTitle(f"大图预览 - {display_name}")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        meta_label = QLabel(
            f"{display_name} · {pixmap.width()} × {pixmap.height()} px",
            dialog,
        )
        meta_label.setObjectName("asset_full_image_preview_meta")
        scroll = QScrollArea(dialog)
        scroll.setObjectName("asset_full_image_preview_scroll")
        scroll.setWidgetResizable(False)
        image_label = QLabel(scroll)
        image_label.setObjectName("asset_full_image_preview_image")
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setPixmap(pixmap)
        image_label.resize(pixmap.size())
        scroll.setWidget(image_label)
        toolbar = QWidget(dialog)
        toolbar.setObjectName("asset_full_image_preview_toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)
        zoom_out_btn = QPushButton(toolbar)
        zoom_out_btn.setObjectName("asset_full_image_preview_zoom_out")
        self._configure_full_image_preview_tool_button(
            zoom_out_btn,
            "minus",
            "缩小",
        )
        zoom_out_btn.clicked.connect(lambda *_args: self._zoom_full_image_preview(0.8))
        zoom_in_btn = QPushButton(toolbar)
        zoom_in_btn.setObjectName("asset_full_image_preview_zoom_in")
        self._configure_full_image_preview_tool_button(
            zoom_in_btn,
            "plus",
            "放大",
        )
        zoom_in_btn.clicked.connect(lambda *_args: self._zoom_full_image_preview(1.25))
        zoom_reset_btn = QPushButton(toolbar)
        zoom_reset_btn.setObjectName("asset_full_image_preview_zoom_reset")
        self._configure_full_image_preview_tool_button(
            zoom_reset_btn,
            "square",
            "原始尺寸",
        )
        zoom_reset_btn.clicked.connect(self._reset_full_image_preview_zoom)
        fit_btn = QPushButton(toolbar)
        fit_btn.setObjectName("asset_full_image_preview_fit")
        self._configure_full_image_preview_tool_button(
            fit_btn,
            "scan",
            "适应窗口",
        )
        fit_btn.clicked.connect(self._fit_full_image_preview_to_window)
        compare_options = list(
            getattr(self, "_current_image_preview_compare_options", []) or []
        )
        compare_combo = QComboBox(toolbar)
        compare_combo.setObjectName("asset_full_image_preview_compare_combo")
        compare_combo.setMinimumWidth(180)
        apply_size_class(compare_combo, "md")
        compare_combo.setStyleSheet(
            build_text_input_stylesheet(get_theme(), selector="QComboBox")
        )
        for option in compare_options:
            compare_combo.addItem(str(option.get("label", "") or "题图对比"))
        compare_combo.setEnabled(bool(compare_options))
        compare_btn = QPushButton(toolbar)
        compare_btn.setObjectName("asset_full_image_preview_compare")
        self._configure_full_image_preview_tool_button(
            compare_btn,
            "copy",
            "对比缩略图",
        )
        compare_btn.setEnabled(bool(compare_options))
        compare_btn.clicked.connect(self._open_full_image_preview_compare)
        mark_issue_btn = QPushButton(toolbar)
        mark_issue_btn.setObjectName("asset_full_image_preview_mark_issue")
        self._configure_full_image_preview_tool_button(
            mark_issue_btn,
            "circle-alert",
            "标记对比问题",
        )
        mark_issue_btn.setEnabled(bool(compare_options))
        mark_issue_btn.clicked.connect(
            self._mark_current_full_image_preview_compare_issue
        )
        zoom_label = QLabel("100%", toolbar)
        zoom_label.setObjectName("asset_full_image_preview_zoom_label")
        zoom_label.setAlignment(Qt.AlignCenter)
        zoom_label.setMinimumWidth(54)
        toolbar_layout.addWidget(zoom_out_btn)
        toolbar_layout.addWidget(zoom_label)
        toolbar_layout.addWidget(zoom_in_btn)
        toolbar_layout.addWidget(zoom_reset_btn)
        toolbar_layout.addWidget(fit_btn)
        toolbar_layout.addWidget(compare_combo)
        toolbar_layout.addWidget(compare_btn)
        toolbar_layout.addWidget(mark_issue_btn)
        toolbar_layout.addStretch(1)
        preview_container = QWidget(dialog)
        preview_container.setObjectName("asset_full_image_preview_container")
        preview_layout = QHBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(10)
        preview_layout.addWidget(scroll, 2)
        compare_panel = QWidget(preview_container)
        compare_panel.setObjectName("asset_full_image_preview_compare_panel")
        compare_panel.setVisible(False)
        compare_layout = QVBoxLayout(compare_panel)
        compare_layout.setContentsMargins(0, 0, 0, 0)
        compare_layout.setSpacing(6)
        compare_title = QLabel("对比缩略图", compare_panel)
        compare_title.setObjectName("asset_full_image_preview_compare_title")
        compare_scroll = QScrollArea(compare_panel)
        compare_scroll.setObjectName("asset_full_image_preview_compare_scroll")
        compare_scroll.setWidgetResizable(False)
        compare_label = QLabel(compare_scroll)
        compare_label.setObjectName("asset_full_image_preview_compare_image")
        compare_label.setAlignment(Qt.AlignCenter)
        compare_scroll.setWidget(compare_label)
        compare_layout.addWidget(compare_title)
        compare_layout.addWidget(compare_scroll)
        preview_layout.addWidget(compare_panel, 1)
        layout.addWidget(meta_label)
        layout.addWidget(toolbar)
        layout.addWidget(preview_container)
        dialog.resize(
            min(max(pixmap.width() + 48, 520), 1080),
            min(max(pixmap.height() + 132, 400), 760),
        )
        self._full_image_preview_dialog = dialog
        self._full_image_preview_label = image_label
        self._full_image_preview_scroll = scroll
        self._full_image_preview_original_pixmap = pixmap
        self._full_image_preview_zoom = 1.0
        self._full_image_preview_zoom_label = zoom_label
        self._full_image_preview_zoom_out_btn = zoom_out_btn
        self._full_image_preview_zoom_in_btn = zoom_in_btn
        self._full_image_preview_zoom_reset_btn = zoom_reset_btn
        self._full_image_preview_fit_btn = fit_btn
        self._full_image_preview_compare_btn = compare_btn
        self._full_image_preview_mark_issue_btn = mark_issue_btn
        self._full_image_preview_compare_combo = compare_combo
        self._full_image_preview_compare_panel = compare_panel
        self._full_image_preview_compare_scroll = compare_scroll
        self._full_image_preview_compare_label = compare_label
        self._full_image_preview_compare_title = compare_title
        self._refresh_full_image_preview_zoom_label()
        dialog.show()
        if hasattr(self, "_image_assets_status_label"):
            self._image_assets_status_label.setText(f"已打开大图预览：{display_name}")
        return True


__all__ = ["ImagePreviewPresenterMixin"]
