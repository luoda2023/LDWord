"""Overview projection orchestration for the template panel."""

from __future__ import annotations

import logging
from src.pipeline.module_selection import (
    ModuleSelectionPlan,
    build_module_selection_plan,
)
from src.ui.panels.template_overview_projection import (
    TemplateOverviewProjection,
    build_template_overview_failure_projection,
    build_template_overview_projection,
)
from src.ui.panels.template_preview.model import TemplatePreviewMode


_LOGGER = logging.getLogger(__name__)


class TemplateOverviewProjectionMixin:
    """Build and apply the overview's normal and fail-safe projections."""

    def _refresh_overview_projection(self, *, reason: str) -> None:
        scene = self.bridge.current_scene()
        if (
            scene is None
            and self._preview_mode is TemplatePreviewMode.CURRENT_PLAN
        ):
            self._preview_mode = TemplatePreviewMode.TEMPLATE_BASELINE
        mode = self._preview_mode
        projection, plan_selection = self._build_overview_projection_state(
            scene=scene,
            mode=mode,
            reason=reason,
        )
        self._apply_overview_projection_state(
            projection,
            plan_selection=plan_selection,
            mode=mode,
            has_scene=scene is not None,
            reason=reason,
        )

    def _build_overview_projection_state(
        self,
        *,
        scene,
        mode: TemplatePreviewMode,
        reason: str,
    ) -> tuple[TemplateOverviewProjection, ModuleSelectionPlan | None]:
        baseline = None
        try:
            baseline = self._template_preview_baseline_resolver(
                self._current_template
            )
            plan_selection: ModuleSelectionPlan | None = None
            preview_config = baseline
            preview_selection: ModuleSelectionPlan | None = None
            if scene is not None:
                resolved_plan = self._template_preview_config_resolver(
                    self._current_template,
                    scene,
                )
                plan_selection = build_module_selection_plan(
                    self._preview_modules,
                    is_requested=resolved_plan.is_module_enabled,
                )
                if mode is TemplatePreviewMode.CURRENT_PLAN:
                    preview_config = resolved_plan
                    preview_selection = plan_selection
            projection = build_template_overview_projection(
                baseline,
                preview_selection,
                mode=mode,
                preview_config=preview_config,
            )
            return projection, plan_selection
        except Exception:
            _LOGGER.exception(
                "Template overview projection failed during %s",
                reason,
            )
            return self._build_overview_failure_projection_state(
                baseline=baseline,
                scene=scene,
                mode=mode,
            )

    def _build_overview_failure_projection_state(
        self,
        *,
        baseline,
        scene,
        mode: TemplatePreviewMode,
    ) -> tuple[TemplateOverviewProjection, ModuleSelectionPlan | None]:
        requests = dict(getattr(scene, "module_switches", {}) or {})
        plan_selection = (
            build_module_selection_plan(
                self._preview_modules,
                is_requested=lambda name: bool(requests.get(name, False)),
            )
            if scene is not None
            else None
        )
        if baseline is None:
            baseline = self._template_preview_baseline_resolver(
                self._template_library_controller.default_selection(
                    mode_id=self._current_work_mode_id(),
                ).template
            )
        projection = build_template_overview_failure_projection(
            baseline,
            (
                plan_selection
                if mode is TemplatePreviewMode.CURRENT_PLAN
                else None
            ),
            mode=mode,
        )
        return projection, plan_selection

    def _apply_overview_projection_state(
        self,
        projection: TemplateOverviewProjection,
        *,
        plan_selection: ModuleSelectionPlan | None,
        mode: TemplatePreviewMode,
        has_scene: bool,
        reason: str,
    ) -> None:
        self._module_selection = plan_selection
        self._overview_projection = projection
        self._overview_projection_stale = False
        self._projection_refresh_count += 1
        self._last_projection_refresh_reason = str(reason)
        self._overview_detail.apply_projection(projection)
        self._overview_detail.set_preview_mode_state(
            mode,
            has_scene=has_scene,
        )

        overview_card = self._nav_cards.get("tpl_overview")
        if overview_card is not None:
            overview_card.set_subtitle(
                self._current_template.name or "默认格式"
            )
        for feature in projection.features:
            nav_card = self._nav_cards.get(feature.card_id)
            if nav_card is not None:
                nav_card.set_subtitle(feature.summary)
        self._apply_module_selection(plan_selection)
