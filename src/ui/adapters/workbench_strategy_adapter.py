from __future__ import annotations

from typing import TYPE_CHECKING

from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig

if TYPE_CHECKING:
    from src.ui.panels.workbench.state import StrategySummaryState


class WorkbenchStrategyAdapter:
    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return str(value or "").strip()

    def build_summary(
        self,
        template: TemplateConfig | None,
        scene: SceneWorkspace | None,
    ) -> "StrategySummaryState":
        from src.ui.panels.workbench.state import StrategySummaryState

        state = StrategySummaryState()
        if template is not None:
            template_name = self._normalize_text(template.name)
            state.template_label = template_name or "未绑定模板"
            if scene is None:
                state.source_type = "template"
        if scene is not None:
            enabled_count = sum(1 for enabled in scene.module_switches.values() if enabled)
            scene_name = self._normalize_text(scene.name)
            scene_description = self._normalize_text(scene.description)
            scene_category = self._normalize_text(scene.category_label)
            state.name = scene_name or "未命名策略"
            state.scene_label = scene_description or scene_category or "通用方案"
            state.strict_mode = scene.strict_mode
            state.enabled_module_count = enabled_count
            state.source_type = "scene"
        return state
