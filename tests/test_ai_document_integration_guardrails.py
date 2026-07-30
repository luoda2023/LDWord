from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _class_method_count(relative_path: str, class_name: str) -> int:
    tree = ast.parse(_source(relative_path), filename=relative_path)
    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in owner.body
    )


def test_large_ui_coordinator_method_budgets_are_non_increasing():
    """New behavior must be extracted instead of growing existing coordinators."""

    budgets = {
        ("src/assistant/ui/assistant_panel.py", "AssistantPanel"): 92,
        ("src/assistant/ui/creative_home.py", "AssistantCreativeHome"): 36,
        (
            "src/ui/panels/workbench/quick_execution_detail.py",
            "QuickExecutionDetail",
        ): 114,
        ("src/ui/panels/workbench/panel_v2.py", "WorkbenchPanel"): 60,
        (
            "src/ui/panels/workbench/batch_generation_detail.py",
            "BatchGenerationDetail",
        ): 52,
    }

    for (relative_path, class_name), maximum in budgets.items():
        assert _class_method_count(relative_path, class_name) <= maximum, (
            f"{class_name} exceeded its non-increasing method budget; "
            "extract a presenter/controller/domain service instead"
        )


def test_provider_presentation_has_one_owner():
    assistant_source = _source("src/assistant/ui/assistant_panel.py")
    preferences_source = _source("src/ui/panels/preferences_panel.py")

    for consumer in (assistant_source, preferences_source):
        assert "from src.assistant.ui.provider_presentation import" in consumer
        assert "def _provider_error_text" not in consumer
        assert "def _provider_connection_badge" not in consumer
        assert "def _provider_connection_status_text" not in consumer


def test_assets_material_preview_normalization_stays_a_pure_projection():
    projection_path = "src/ui/panels/assets/material_preview_projection.py"
    projection_source = _source(projection_path)
    projection_tree = ast.parse(projection_source, filename=projection_path)
    imported_modules = {
        node.module
        for node in ast.walk(projection_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(projection_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not any(module.startswith("src.qt_api") for module in imported_modules)
    assert not any(module.startswith("src.ui") for module in imported_modules)

    presenter_source = _source(
        "src/ui/panels/assets/section_summary_presenter.py"
    )
    assert "build_assets_material_preview_snapshot" in presenter_source
    assert "build_material_preview_snapshot" not in presenter_source


def test_batch_detail_has_no_hidden_compatibility_state_widgets():
    source = _source("src/ui/panels/workbench/batch_generation_detail.py")

    for retired_name in (
        "_source_summary",
        "_profile_summary",
        "_rule_summary",
        "_source_document_summary",
        "self._progress =",
        "self._readiness_label =",
        "self._result_label =",
        "self._status_label =",
    ):
        assert retired_name not in source


def test_workbench_execution_uses_shared_material_state():
    source = _source("src/ui/panels/workbench/panel_v2.py")
    start_execution = source.split("    def _start_execution(", 1)[1].split(
        "    def _start_batch_execution(", 1
    )[0]

    assert "material_context=self.bridge.current_material_context()" in start_execution
    assert "_content_fill_detail.material_context()" not in start_execution
