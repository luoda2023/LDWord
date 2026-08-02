"""Assets-panel adapter for the shared image preview framework."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from src.qt_api import QSize
from src.services.material_assets import (
    question_figure_items,
    question_figure_payload_matches_item,
    question_figure_target_label,
)
from src.shared.ui.preview_dialog import (
    ImagePreviewDialog,
    PreviewItem,
    load_preview_pixmap,
)
from src.ui.panels.assets.fields import _asset_role_label
from src.ui.panels.assets.image_helpers import _image_quality_text
from src.ui.panels.assets.items import _normalized_asset_item_payloads


class ImagePreviewPresenterMixin:
    """Keep asset business context outside the reusable preview widget."""

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
                display = str(option.get("display_name", "") or "").strip()
                normalized_options.append(
                    {
                        "label": str(option.get("label", "") or "").strip()
                        or display
                        or Path(reference).name,
                        "reference": reference,
                        "source": str(option.get("source", "") or "").strip(),
                        "display_name": display or Path(reference).name,
                        "kind_label": str(option.get("kind_label", "") or "").strip()
                        or "题图对比",
                    }
                )
            if not normalized_options and compare_reference:
                normalized_options.append(
                    {
                        "label": compare_display_name or Path(compare_reference).name,
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

    def _set_image_preview(self, path: str, *, role: str = "") -> None:
        candidate = Path(str(path or "").strip())
        if not candidate.is_file():
            self._set_current_image_preview_path("")
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("当前材料位还没有选择图片。")
            return
        self._set_current_image_preview_path(str(candidate))
        if hasattr(self, "_image_assets_status_label"):
            role_text = _asset_role_label(role, self._asset_slot_specs) if role else "图片"
            self._image_assets_status_label.setText(
                f"正在查看{role_text}：{candidate.name} · "
                f"{_image_quality_text(str(candidate), role=role)}"
            )

    def _selected_full_image_preview_compare_option(self) -> dict[str, str]:
        dialog = getattr(self, "_image_preview_dialog", None)
        item = dialog.selected_compare_item if dialog is not None else None
        if item is not None:
            return {str(key): str(value) for key, value in item.metadata.items()}
        options = list(getattr(self, "_current_image_preview_compare_options", []) or [])
        if options:
            return dict(options[0])
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
                getattr(self, "_current_image_preview_compare_display_name", "") or ""
            ).strip(),
            "kind_label": "缩略图对比",
        }

    def _current_full_image_preview_region_payload(
        self,
        *,
        reference: str,
        display_name: str,
        kind_label: str,
        view_region: Mapping[str, object] | None = None,
        compare_size: QSize | None = None,
    ) -> dict[str, object]:
        dialog = getattr(self, "_image_preview_dialog", None)
        if view_region is None and dialog is not None:
            view_region = dialog.viewport.current_region()
        view = dict(view_region or {})
        image_width = int(view.get("image_width") or 0)
        image_height = int(view.get("image_height") or 0)
        if (not image_width or not image_height) and dialog is not None:
            natural = dialog.content.natural_size
            image_width, image_height = natural.width(), natural.height()
        if compare_size is None and dialog is not None:
            compare_size = dialog.comparison_size()
        compare_size = QSize(compare_size or QSize())
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
                "x": int(view.get("x") or 0),
                "y": int(view.get("y") or 0),
                "width": int(view.get("width") or image_width),
                "height": int(view.get("height") or image_height),
                "zoom": round(float(view.get("zoom") or 1.0), 4),
            },
            "compare": {
                "reference": str(reference or ""),
                "display_name": str(display_name or ""),
                "kind_label": str(kind_label or ""),
                "width": compare_size.width(),
                "height": compare_size.height(),
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

    def _mark_current_full_image_preview_compare_issue(
        self,
        compare_item: PreviewItem | None = None,
        view_region: Mapping[str, object] | None = None,
    ) -> bool:
        option = (
            {str(key): str(value) for key, value in compare_item.metadata.items()}
            if compare_item is not None
            else self._selected_full_image_preview_compare_option()
        )
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
        display_name = str(option.get("display_name", "") or "").strip() or Path(reference).name
        kind_label = str(option.get("kind_label", "") or "").strip() or "题图对比"
        region = self._current_full_image_preview_region_payload(
            reference=reference,
            display_name=display_name,
            kind_label=kind_label,
            view_region=view_region,
        )
        region_summary = self._current_full_image_preview_region_summary(region)
        marked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
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
                        f"{question_figure_target_label(target)} {kind_label}: {display_name}"
                    ),
                    "comparison_issue_region_type": "current_view",
                    "comparison_issue_region_json": json.dumps(
                        region, ensure_ascii=False, sort_keys=True
                    ),
                    "comparison_issue_region_summary": region_summary,
                }
            )
            payload["metadata"] = metadata
            updated = True
            break
        if not updated:
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText(
                    "当前题图不是结构化题图条目，暂不能标注。"
                )
            return False
        previous_payloads = copy.deepcopy(self._asset_item_payloads)
        self._asset_item_payloads = payloads
        if not self._persist_current_profile_editor():
            self._asset_item_payloads = previous_payloads
            return False
        self._refresh_summary()
        table = getattr(self, "_question_figure_items_table", None)
        if table is not None and row < table.rowCount():
            table.setCurrentCell(row, 0)
            table.selectRow(row)
        if hasattr(self, "_image_assets_status_label"):
            self._image_assets_status_label.setText(f"已标记对比问题：{display_name}")
        return True

    def _open_current_image_preview_dialog(self) -> bool:
        path = str(getattr(self, "_current_image_preview_path", "") or "").strip()
        if not path or not Path(path).is_file():
            self._set_current_image_preview_path("")
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText("当前没有可打开的大图预览。")
            return False
        display_name = (
            str(getattr(self, "_current_image_preview_display_name", "") or "").strip()
            or Path(path).name
        )
        item = PreviewItem.from_path(path, display_name=display_name)
        pixmap, _format, error = load_preview_pixmap(item)
        if pixmap.isNull():
            if hasattr(self, "_image_assets_status_label"):
                self._image_assets_status_label.setText(
                    f"当前预览图片无法打开：{error or '未知格式'}"
                )
            return False
        compare_items = tuple(
            PreviewItem.from_path(
                option["reference"],
                display_name=option.get("display_name", ""),
                label=option.get("label", ""),
                metadata=option,
            )
            for option in getattr(self, "_current_image_preview_compare_options", []) or []
            if option.get("reference")
        )
        existing = getattr(self, "_image_preview_dialog", None)
        if existing is not None:
            existing.close()
        dialog = ImagePreviewDialog(
            (item,),
            compare_items=compare_items,
            allow_issue_marking=bool(compare_items),
            title="图片资料预览",
            parent=self,
        )
        dialog.setObjectName("asset_full_image_preview_dialog")
        dialog.issue_requested.connect(
            self._mark_current_full_image_preview_compare_issue
        )
        dialog.finished.connect(
            lambda *_args, current=dialog: self._clear_image_preview_dialog(current)
        )
        self._image_preview_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        if hasattr(self, "_image_assets_status_label"):
            self._image_assets_status_label.setText(f"已打开图片预览：{display_name}")
        return True

    def _clear_image_preview_dialog(self, dialog: ImagePreviewDialog) -> None:
        if getattr(self, "_image_preview_dialog", None) is dialog:
            self._image_preview_dialog = None


__all__ = ["ImagePreviewPresenterMixin"]
