from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_projector_is_qt_free_and_preview_widget_is_business_rule_free():
    projector = _source("src/ui/panels/template_preview/projector.py")
    widget = _source("src/ui/panels/template_preview/widget.py")

    assert "src.qt_api" not in projector
    assert "src.ui.adapters" not in projector
    assert "TemplateConfig" not in projector
    assert "SceneWorkspace" not in projector
    for forbidden in (
        "src.config",
        "resolver",
        "bridge",
        "modules.registry",
        "module_selection",
        "module_switches",
    ):
        assert forbidden not in widget


def test_template_panel_consumes_registry_without_defining_feature_metadata():
    panel = _source("src/ui/panels/template_panel.py")
    navigation = _source("src/ui/adapters/workbench_issue_navigation.py")

    assert "TemplateFeatureSpec(" not in panel
    assert "CARD_DEFINITIONS:" not in panel
    assert "DETAIL_REFORMAT" not in panel
    assert "template_panel import" not in navigation
    assert "template_feature_specs import" in navigation


def test_legacy_template_preview_chain_is_absent_from_production():
    assert not (SRC / "ui/panels/template_style_preview.py").exists()
    assert not (SRC / "ui/panels/template_format.py").exists()
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SRC.rglob("*.py")
    )
    for forbidden in (
        "module_toggled",
        "_ReformatToggleCard",
        "template_overview_preview",
        "build_template_page_presentation_envelope",
        "STYLE_PRESENTATION_KIND_TEMPLATE_PAGE",
        "from_template_page",
        "toc_cfg.enabled",
        'style_key="table_preview"',
    ):
        assert forbidden not in production


def test_production_has_no_direct_reads_of_removed_scene_appearance_fields():
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SRC.rglob("*.py")
    )
    for field_name in (
        "table",
        "header_footer",
        "toc",
        "caption",
        "formula_table",
    ):
        assert f"scene.{field_name}" not in production


def test_repository_assets_use_the_post_cleanup_config_contract():
    removed_scene_roots = {
        "table",
        "header_footer",
        "toc",
        "caption",
        "formula_table",
    }
    scene_paths = tuple((ROOT / "scenes").glob("*.json")) + tuple(
        (ROOT / "config_library/plans").rglob("*.json")
    )
    for path in scene_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert removed_scene_roots.isdisjoint(payload), path

    template_paths = tuple((ROOT / "templates").glob("*.json")) + tuple(
        (ROOT / "config_library/templates").rglob("*.json")
    )
    for path in template_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        toc = payload.get("toc") or {}
        assert "enabled" not in toc, path
