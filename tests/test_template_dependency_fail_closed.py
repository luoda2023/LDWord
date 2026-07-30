from __future__ import annotations

import pytest

from src.config.library import (
    ConfigDependencyResolutionError,
    is_template_library_path,
)
from src.config.loader import load_template, save_template
from src.qt_api import QApplication
from src.ui.bridge import PanelBridge
import src.ui.panels.template_panel as template_panel_module
from src.ui.panels.template_panel import TemplatePanel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_template_save_is_blocked_visibly_when_plan_dependencies_are_unverifiable(
    monkeypatch,
) -> None:
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_work_mode("official", emit_signal=False)
    panel = TemplatePanel(bridge)
    errors: list[str] = []
    try:
        monkeypatch.setattr(
            template_panel_module,
            "template_dependent_scene_descriptors",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ConfigDependencyResolutionError(
                    "plan_dependency_unresolved:broken:malformed"
                )
            ),
        )
        monkeypatch.setattr(
            template_panel_module.Toast,
            "show_error",
            staticmethod(lambda message, **_kwargs: errors.append(message)),
        )

        allowed = panel._confirm_shared_template_write_for_context(
            panel._draft_context
        )

        assert allowed is False
        assert errors
        assert "已阻止保存" in errors[-1]
        assert "plan_dependency_unresolved:broken" in errors[-1]
        assert "已阻止保存" in panel._last_template_management_status
    finally:
        panel.close()
        app.processEvents()


@pytest.mark.parametrize(
    ("source", "source_type"),
    (("file", ""), ("library", "user"), ("library", "builtin")),
)
def test_non_library_template_path_does_not_scan_unrelated_library_plans(
    monkeypatch,
    tmp_path,
    source,
    source_type,
) -> None:
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    target = save_template(panel._current_template, tmp_path / "external.json")
    try:
        panel._activate_template(
            load_template(target),
            template_id="external",
            path=str(target),
            source=source,
            source_type=source_type,
        )
        monkeypatch.setattr(
            template_panel_module,
            "template_dependent_scene_descriptors",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("non-library path must not scan library plans")
            ),
        )

        assert panel._confirm_shared_template_write_for_context(
            panel._draft_context
        ) is True
    finally:
        panel.close()
        app.processEvents()


def test_shared_dependency_check_uses_prepared_target_not_stale_context_path(
    monkeypatch,
    tmp_path,
) -> None:
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    target = tmp_path / "save-as-external.json"
    try:
        assert panel._draft_context.path
        monkeypatch.setattr(
            template_panel_module,
            "template_dependent_scene_descriptors",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "prepared non-library target must not scan library plans"
                )
            ),
        )

        plans = panel._prepare_draft_context_saves(
            (panel._draft_context,),
            confirm_shared=True,
            path=target,
        )

        assert plans[0].target == target
        assert plans[0].context is panel._draft_context
    finally:
        panel.close()
        app.processEvents()


def test_pathless_context_resolved_to_user_library_still_scans_dependencies(
    monkeypatch,
) -> None:
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    calls: list[tuple[str, str]] = []
    try:
        panel._activate_template(
            panel._current_template,
            template_id="new-pathless-template",
            path="",
            source="library",
            source_type="user",
        )

        def _record_dependencies(template_id, *, mode_id):
            calls.append((template_id, mode_id))
            return ()

        monkeypatch.setattr(
            template_panel_module,
            "template_dependent_scene_descriptors",
            _record_dependencies,
        )

        plans = panel._prepare_draft_context_saves(
            (panel._draft_context,),
            confirm_shared=True,
        )

        assert is_template_library_path(plans[0].target)
        assert calls == [("new-pathless-template", "custom")]
    finally:
        panel.close()
        app.processEvents()


def test_prepared_dependency_identity_ignores_diverged_active_panel_globals(
    monkeypatch,
) -> None:
    app = _app()
    bridge = PanelBridge()
    panel = TemplatePanel(bridge)
    calls: list[tuple[str, str]] = []
    try:
        expected_template_id = panel._draft_context.template_id
        expected_mode_id = panel._draft_context.mode_id
        assert is_template_library_path(panel._draft_context.path)
        panel._current_template_id = "wrong-active-template"
        bridge.set_current_work_mode("official", emit_signal=False)

        def _record_dependencies(template_id, *, mode_id):
            calls.append((template_id, mode_id))
            return ()

        monkeypatch.setattr(
            template_panel_module,
            "template_dependent_scene_descriptors",
            _record_dependencies,
        )

        plans = panel._prepare_draft_context_saves(
            (panel._draft_context,),
            confirm_shared=True,
        )

        assert plans[0].template_id == expected_template_id
        assert plans[0].context.mode_id == expected_mode_id
        assert calls == [(expected_template_id, expected_mode_id)]
    finally:
        panel.close()
        app.processEvents()
