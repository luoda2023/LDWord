"""Export visual audit screenshots for the shared style source row.

The screenshots are generated with Qt offscreen rendering. They are useful for
layout, density, and button-boundary checks; text rendering still needs a real
Windows desktop pass when font fidelity is the question.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.config.scene import SceneWorkspace
from src.config.template import StyleConfig
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_panel import ScenePanel
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


OUT_DIR = ROOT / "docs" / "visual_audit" / "2026-06-29" / "style_source"
PANEL_SIZE = (1220, 840)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _process_events(app: QApplication, passes: int = 6) -> None:
    for _ in range(passes):
        app.processEvents()


def _audit_scene() -> SceneWorkspace:
    scene = SceneWorkspace(
        scene_id="custom",
        name="自定义场景",
        category="custom",
        template_id="default",
        default_template_id="default",
        compatible_template_ids=["default"],
    )
    scene.section_styles["references_body"] = StyleConfig(line_spacing_type="exact", line_spacing_pt=26)
    return scene


def _bridge() -> PanelBridge:
    bridge = PanelBridge()
    bridge.set_current_scene(_audit_scene(), config_id="custom", source="runtime", emit_signal=False)
    bridge.set_current_template(
        create_builtin_template("default"),
        config_id="default",
        source="builtin",
        emit_signal=False,
    )
    return bridge


def _save_widget(widget, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    if pixmap.isNull() or not pixmap.save(str(path)):
        raise RuntimeError(f"Failed to save screenshot: {path}")


def _recorded_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _row_metrics(row) -> dict[str, object]:
    if hasattr(row, "comparison_strip"):
        strip = row.comparison_strip
        view_mode = (
            row.property("style_difference_review_mode")
            or row.property("style_source_view_mode")
            or "execution_review"
        )
        if view_mode == "execution_prereview":
            view_mode = "execution_review"
        status = strip.property("style_compare_difference_status") or ""
        if status and status != "-":
            status = "有格式例外"
        detail = str(strip.property("style_compare_detail") or row.toolTip() or "")
        current_status = str(strip.property("style_compare_current_status") or "").strip()
        section_line = strip.current_label.text()
        if current_status and detail.startswith("不同："):
            section_name = current_status.split()[0]
            section_line = f"{section_name}（{detail.removeprefix('不同：')}）"
        return {
            "object_name": row.objectName(),
            "view_mode": view_mode,
            "size": {"width": row.width(), "height": row.height()},
            "label": strip.template_label.text(),
            "status": status,
            "template_line": strip.template_label.text(),
            "section_line": section_line,
            "summary": detail,
            "primary_action": "",
            "primary_visible": False,
            "secondary_action": "",
            "secondary_visible": True,
            "actions_visible": False,
            "actions_size": {"width": 0, "height": 0},
        }
    template_line = row._template_line.text() if hasattr(row, "_template_line") else ""
    section_line = row._section_line.text() if hasattr(row, "_section_line") else row.summary_text()
    view_mode = row.property("style_source_view_mode")
    if not view_mode:
        view_mode = "scene_setting_row" if hasattr(row, "set_spec") else ""
    return {
        "object_name": row.objectName(),
        "view_mode": view_mode,
        "size": {"width": row.width(), "height": row.height()},
        "label": row._label.text(),
        "status": row._status.text(),
        "template_line": template_line,
        "section_line": section_line,
        "summary": row.summary_text(),
        "primary_action": row._jump_btn.text(),
        "primary_visible": not row._jump_btn.isHidden(),
        "secondary_action": row._secondary_jump_btn.text(),
        "secondary_visible": not row._secondary_jump_btn.isHidden(),
        "actions_visible": not row._actions_wrap.isHidden(),
        "actions_size": {
            "width": row._actions_wrap.width(),
            "height": row._actions_wrap.height(),
        },
    }


def _panel_metrics(panel, row, full_path: Path, row_path: Path) -> dict[str, object]:
    _save_widget(panel, full_path)
    _save_widget(row, row_path)
    metrics = _row_metrics(row)
    metrics.update(
        {
            "panel_size": {"width": panel.width(), "height": panel.height()},
            "full_screenshot": _recorded_path(full_path),
            "row_screenshot": _recorded_path(row_path),
        }
    )
    return metrics


def _show_panel(app: QApplication, panel) -> None:
    panel.resize(*PANEL_SIZE)
    panel.show()
    _process_events(app)


def export() -> dict[str, object]:
    app = _app()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    panels = []
    result: dict[str, object] = {
        "note": (
            "Qt offscreen screenshots verify layout and widget boundaries. "
            "Chinese font fidelity still requires a real Windows desktop check."
        ),
        "panel_size": {"width": PANEL_SIZE[0], "height": PANEL_SIZE[1]},
        "entries": {},
    }

    try:
        scene_panel = ScenePanel(_bridge())
        panels.append(scene_panel)
        _show_panel(app, scene_panel)
        scene_row = scene_panel._overview._setting_rows["style_source"]
        result["entries"]["scene_overview"] = _panel_metrics(
            scene_panel,
            scene_row,
            OUT_DIR / "scene_overview_style_source_full.png",
            OUT_DIR / "scene_overview_style_source_row.png",
        )

        workbench_panel = WorkbenchPanel(_bridge())
        panels.append(workbench_panel)
        _show_panel(app, workbench_panel)
        workbench_row = workbench_panel._quick_execution_detail._style_difference_slot
        result["entries"]["workbench_quick_execute"] = _panel_metrics(
            workbench_panel,
            workbench_row,
            OUT_DIR / "workbench_quick_execute_style_source_full.png",
            OUT_DIR / "workbench_quick_execute_style_source_row.png",
        )
    finally:
        for panel in panels:
            panel.close()
        _process_events(app, passes=2)

    metrics_path = OUT_DIR / "style_source_visual_audit_metrics.json"
    metrics_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    payload = export()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
