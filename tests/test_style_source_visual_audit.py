import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import export_style_source_visual_audit as visual_audit


def _recorded_file(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def test_style_source_visual_audit_exports_current_style_source_screenshots(tmp_path, monkeypatch):
    out_dir = tmp_path / "style_source_visual_audit"
    monkeypatch.setattr(visual_audit, "OUT_DIR", out_dir)

    payload = visual_audit.export()
    entries = payload["entries"]

    assert set(entries) == {
        "scene_overview",
        "workbench_quick_execute",
    }
    assert entries["scene_overview"]["view_mode"] == "scene_setting_row"
    assert entries["workbench_quick_execute"]["view_mode"] == "execution_review"

    assert entries["scene_overview"]["label"] == "套用模板"
    assert entries["scene_overview"]["primary_action"] == "设置"
    assert entries["scene_overview"]["secondary_visible"] is False
    assert entries["workbench_quick_execute"]["secondary_visible"] is True
    assert entries["scene_overview"]["status"] == "有格式例外"
    assert entries["workbench_quick_execute"]["status"] == "有格式例外"
    assert "参考文献有格式例外" in entries["scene_overview"]["section_line"]
    assert "参考文献（特殊缩进、行距）" in entries["workbench_quick_execute"]["section_line"]

    for entry in entries.values():
        assert entry["size"]["width"] > 0
        assert entry["size"]["height"] > 0
        assert _recorded_file(entry["full_screenshot"]).exists()
        assert _recorded_file(entry["row_screenshot"]).exists()
    assert (out_dir / "style_source_visual_audit_metrics.json").exists()
