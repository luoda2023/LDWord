import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.ui.adapters.workbench_strategy_adapter import WorkbenchStrategyAdapter
from src.ui.panels.workbench.state import StrategySummaryState
from src.ui.panels.workbench.strategy_card import StrategyCard
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig


def _app():
    return QApplication.instance() or QApplication([])


def test_strategy_card_exposes_summary_role_hooks():
    _app()
    card = StrategyCard()
    state = StrategySummaryState(
        name="论文标准",
        source_type="scene",
        template_label="thesis.yaml",
        scene_label="结构优先",
        strict_mode=False,
        enabled_module_count=3,
    )

    card.set_state(state)

    assert card._name_value.objectName() == "wb_strategy_headline"
    assert card._template_value.objectName() == "wb_strategy_binding"
    assert card._scene_value.objectName() == "wb_strategy_binding"
    assert card._modules_value.objectName() == "wb_strategy_meta"
    assert card._source_value.objectName() == "wb_strategy_meta"
    assert card._strict_mode_value.objectName() == "wb_strategy_meta"


def test_strategy_summary_state_exposes_homepage_safe_fields():
    state = StrategySummaryState()

    assert state.name == "未命名策略"
    assert state.source_type == "default"
    assert state.template_label == "未绑定模板"
    assert state.scene_label == "未绑定方案"


def test_strategy_card_renders_strategy_summary_labels():
    _app()
    card = StrategyCard()
    state = StrategySummaryState(
        name="论文标准",
        source_type="scene",
        template_label="thesis.yaml",
        scene_label="结构优先",
        strict_mode=True,
        enabled_module_count=3,
    )

    card.set_state(state)

    assert card._name_value.text() == "策略: 论文标准"
    assert card._template_value.text() == "模板: thesis.yaml"
    assert card._scene_value.text() == "方案: 结构优先"
    assert card._modules_value.text() == "模块数: 3"
    assert card._source_value.text() == "来源: 方案"
    assert card._strict_mode_value.text() == "严格模式: 是"


@pytest.mark.parametrize(
    ("source_type", "expected_source"),
    [
        ("default", "默认"),
        ("template", "模板"),
        ("scene", "方案"),
    ],
)
def test_strategy_card_maps_internal_source_type_for_display(source_type, expected_source):
    _app()
    card = StrategyCard()
    state = StrategySummaryState(source_type=source_type)

    card.set_state(state)

    assert card._source_value.text() == f"来源: {expected_source}"


def test_strategy_card_uses_neutral_strict_mode_text_when_scene_unbound():
    _app()
    card = StrategyCard()
    state = StrategySummaryState(
        source_type="template",
        strict_mode=True,
        scene_label="未绑定方案",
    )

    card.set_state(state)

    assert card._strict_mode_value.text() == "严格模式: 未适用"


def test_workbench_strategy_adapter_builds_summary_from_template_and_scene():
    adapter = WorkbenchStrategyAdapter()
    template = TemplateConfig(name="thesis.yaml")
    scene = SceneWorkspace(
        name="论文标准",
        description="结构优先",
        category_label="结构化",
        strict_mode=False,
    )
    for module_name in list(scene.module_switches.keys()):
        scene.module_switches[module_name] = False
    scene.module_switches["test_module"] = True

    summary = adapter.build_summary(template, scene)

    assert summary.name == "论文标准"
    assert summary.template_label == "thesis.yaml"
    assert summary.scene_label == "结构优先"
    assert summary.strict_mode is False
    assert summary.enabled_module_count == 1
    assert summary.source_type == "scene"


def test_workbench_strategy_adapter_preserves_template_when_scene_missing():
    adapter = WorkbenchStrategyAdapter()
    template = TemplateConfig(name="论文模板")

    summary = adapter.build_summary(template, None)

    assert summary.name == "未命名策略"
    assert summary.template_label == "论文模板"
    assert summary.scene_label == "未绑定方案"
    assert summary.enabled_module_count == 0
    assert summary.source_type == "template"
    assert summary.strict_mode is True


def test_workbench_strategy_adapter_preserves_scene_when_template_missing():
    adapter = WorkbenchStrategyAdapter()
    scene = SceneWorkspace(
        name="结构优先",
        description="结构优先场景",
        category_label="结构化",
        strict_mode=True,
    )
    for module_name in list(scene.module_switches.keys()):
        scene.module_switches[module_name] = False
    scene.module_switches["another_module"] = True

    summary = adapter.build_summary(None, scene)

    assert summary.name == "结构优先"
    assert summary.template_label == "未绑定模板"
    assert summary.scene_label == "结构优先场景"
    assert summary.enabled_module_count == 1
    assert summary.source_type == "scene"
    assert summary.strict_mode is True


def test_workbench_strategy_adapter_strips_whitespace_before_fallback_selection():
    adapter = WorkbenchStrategyAdapter()
    template = TemplateConfig(name="   ")
    scene = SceneWorkspace(
        name="  ",
        description="   ",
        category_label="\t",
        strict_mode=True,
    )
    for module_name in list(scene.module_switches.keys()):
        scene.module_switches[module_name] = False

    summary = adapter.build_summary(template, scene)

    assert summary.template_label == "未绑定模板"
    assert summary.name == "未命名策略"
    assert summary.scene_label == "通用方案"
    assert summary.source_type == "scene"
