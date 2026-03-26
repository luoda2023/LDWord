import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.scene.manager import get_scene_upgrade_notes
from src.scene.manager import load_scene
from src.scene.manager import save_scene
from src.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_load_scene_collects_upgrade_notes_for_former_template(tmp_path):
    src = Path("tests/former-templates/default_format.json")
    dst = tmp_path / "legacy_template.json"
    shutil.copy2(src, dst)

    cfg = load_scene(dst)
    notes = get_scene_upgrade_notes(cfg)

    assert notes
    assert any("heading_numbering_v2" in note for note in notes)
    assert any("Markdown 清理配置" in note for note in notes)
    assert any("目录模式配置" in note for note in notes)
    assert getattr(cfg, "_scene_upgrade_applied", False) is True
    assert getattr(cfg, "_heading_numbering_v2_source", "") == "derived"
    assert cfg.toc.mode == "word_native"


def test_main_window_silently_rewrites_former_template_and_logs_it(tmp_path):
    _app()

    src = Path("tests/former-templates/default_format.json")
    dst = tmp_path / "legacy_template.json"
    shutil.copy2(src, dst)

    raw_before = json.loads(dst.read_text(encoding="utf-8"))
    assert "heading_numbering_v2" not in raw_before
    assert "toc" not in raw_before
    assert "md_cleanup" not in raw_before

    window = MainWindow()
    window._log_text.clear()
    try:
        ok = window._load_scene_from_path(
            dst,
            custom=True,
            source_label="自定义场景",
            clear_on_fail=False,
        )
        assert ok is True

        raw_after = json.loads(dst.read_text(encoding="utf-8"))
        assert "heading_numbering_v2" in raw_after
        assert "toc" in raw_after
        assert "md_cleanup" in raw_after
        assert "formula_convert" in raw_after
        assert "formula_to_table" in raw_after
        assert "equation_table_format" in raw_after
        assert "formula_style" in raw_after
        assert "formula_table" in raw_after

        log_text = window._log_text.toPlainText()
        assert "已静默升级旧版模板以适配当前格式定义。" in log_text
        assert "已静默回写升级后的模板" in log_text
    finally:
        window.close()


def test_load_scene_upgrades_legacy_format_file_base_and_keeps_overlay(tmp_path):
    legacy_base = tmp_path / "legacy_base.json"
    shutil.copy2(Path("tests/former-templates/default_format.json"), legacy_base)

    overlay = tmp_path / "overlay.json"
    overlay.write_text(
        json.dumps(
            {
                "name": "overlay",
                "format_file": "legacy_base.json",
                "styles": {
                    "normal": {
                        "size_pt": 14.0,
                        "size_display": "14",
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    cfg = load_scene(overlay)
    notes = get_scene_upgrade_notes(cfg)

    assert notes
    assert cfg.heading_numbering_v2.level_bindings
    assert cfg.heading_numbering_v2.enabled is True
    assert cfg.styles["normal"].size_pt == 14.0
    assert cfg.styles["normal"].size_display == "14"
    assert getattr(cfg, "_heading_numbering_v2_source", "") == "derived"


def test_main_window_does_not_repeat_upgrade_log_after_rewrite(tmp_path):
    _app()

    src = Path("tests/former-templates/default_format.json")
    dst = tmp_path / "legacy_template.json"
    shutil.copy2(src, dst)

    window = MainWindow()
    try:
        assert window._load_scene_from_path(
            dst,
            custom=True,
            source_label="自定义场景",
            clear_on_fail=False,
        ) is True
        first_log = window._log_text.toPlainText()
        assert "已静默升级旧版模板以适配当前格式定义。" in first_log

        window._log_text.clear()
        assert window._load_scene_from_path(
            dst,
            custom=True,
            source_label="自定义场景",
            clear_on_fail=False,
        ) is True
        second_log = window._log_text.toPlainText()
        assert "已静默升级旧版模板以适配当前格式定义。" not in second_log
    finally:
        window.close()


def test_silent_upgrade_round_trip_preserves_legacy_heading_layout_fields(tmp_path):
    src = Path("tests/former-templates/default_format.json")
    dst = tmp_path / "legacy_template.json"
    shutil.copy2(src, dst)

    before = load_scene(dst)
    expected_layout = {
        level_name: {
            "format": before.heading_numbering.levels[level_name].format,
            "template": before.heading_numbering.levels[level_name].template,
            "separator": before.heading_numbering.levels[level_name].separator,
            "alignment": before.heading_numbering.levels[level_name].alignment,
            "left_indent_chars": before.heading_numbering.levels[level_name].left_indent_chars,
        }
        for level_name in ("heading1", "heading2", "heading3", "heading4")
    }

    save_scene(before, dst)
    reloaded = load_scene(dst)

    for level_name, expected in expected_layout.items():
        level = reloaded.heading_numbering.levels[level_name]
        assert level.format == expected["format"]
        assert level.template == expected["template"]
        assert level.separator == expected["separator"]
        assert level.alignment == expected["alignment"]
        assert level.left_indent_chars == expected["left_indent_chars"]
