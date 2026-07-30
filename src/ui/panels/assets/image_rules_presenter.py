"""One global placement and watermark policy for all image material roles."""

from __future__ import annotations

from src.config.image_materials import (
    ImageCardinality,
    ImageCoLocationGuard,
    ImageMaterialRule,
    ImageOccurrencePolicy,
    ImagePlacementMode,
    ImagePlacementPolicy,
    ImageWatermarkPolicy,
    ImageWatermarkTextSource,
)
from src.qt_api import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from src.shared.ui.card import Card
from src.shared.ui.layout_sync import refresh_layout_chain_later
from src.shared.ui.themed_radio_button import ThemedRadioButton
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
)


class ImageRulesPresenterMixin:
    """Project one user policy into per-role execution rules."""

    _DIRECT_STRATEGY = "direct"
    _ADAPTIVE_STRATEGY = "adaptive"

    def _setup_image_rules_card(self) -> None:
        rules_card = Card(parent=self._section_contents["images"])
        rules_card.setObjectName("assets_image_rules_card")
        rules_card.set_header("图片规则", icon_name="sliders-horizontal")
        self._image_rules_card = rules_card

        container = QWidget(rules_card)
        container.setObjectName("image_global_rules")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        strategy_row = QWidget(container)
        strategy_layout = QHBoxLayout(strategy_row)
        strategy_layout.setContentsMargins(0, 0, 0, 0)
        strategy_layout.setSpacing(24)
        adaptive = QCheckBox("自适应缩放", strategy_row)
        adaptive.setObjectName("image_rule_adaptive_check")
        strategy_layout.addWidget(adaptive, 0)
        strategy_layout.addStretch(1)
        layout.addWidget(strategy_row)

        watermark_row = QWidget(container)
        watermark_layout = QHBoxLayout(watermark_row)
        watermark_layout.setContentsMargins(0, 0, 0, 0)
        watermark_layout.setSpacing(12)
        watermark_enabled = QCheckBox("图片水印", watermark_row)
        watermark_enabled.setObjectName("image_rule_watermark_check")
        fixed_source = ThemedRadioButton("固定字段", watermark_row)
        fixed_source.setObjectName("image_rule_watermark_fixed_radio")
        free_source = ThemedRadioButton("自由字段", watermark_row)
        free_source.setObjectName("image_rule_watermark_free_radio")
        source_group = QButtonGroup(watermark_row)
        source_group.addButton(fixed_source)
        source_group.addButton(free_source)
        watermark_text = QLineEdit(watermark_row)
        watermark_text.setObjectName("image_rule_watermark_edit")
        watermark_text.setPlaceholderText("水印文字或 {{字段}}")
        watermark_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        watermark_layout.addWidget(watermark_enabled, 0)
        watermark_layout.addWidget(fixed_source, 0)
        watermark_layout.addWidget(free_source, 0)
        watermark_layout.addWidget(watermark_text, 1)
        layout.addWidget(watermark_row)

        self._image_material_rules_container = container
        self._image_rule_adaptive_check = adaptive
        self._image_rule_watermark_check = watermark_enabled
        self._image_rule_watermark_source_group = source_group
        self._image_rule_watermark_fixed_radio = fixed_source
        self._image_rule_watermark_free_radio = free_source
        self._image_rule_watermark_edit = watermark_text

        adaptive.toggled.connect(lambda *_args: self._commit_global_image_policy())
        watermark_enabled.toggled.connect(
            lambda *_args: self._commit_global_image_policy()
        )
        fixed_source.toggled.connect(
            lambda checked: checked and self._commit_global_image_policy()
        )
        free_source.toggled.connect(
            lambda checked: checked and self._commit_global_image_policy()
        )
        watermark_text.editingFinished.connect(self._commit_global_image_policy)

        rules_card.add_widget(container)
        self._sync_image_material_rule_rows()
        self._section_layouts["images"].addWidget(rules_card)

    def _sync_image_material_rule_rows(self) -> None:
        """Normalize legacy per-role settings into one global policy."""

        if not hasattr(self, "_image_rule_adaptive_check"):
            return
        specs = self._image_rule_specs()
        strategy = self._strategy_from_material_rules(specs)
        watermark = self._watermark_from_material_rules(specs)

        self._syncing_image_material_rules = True
        try:
            self._image_rule_adaptive_check.setChecked(
                strategy == self._ADAPTIVE_STRATEGY
            )
            self._image_rule_watermark_check.setChecked(watermark.enabled)
            self._image_rule_watermark_fixed_radio.setChecked(
                watermark.text_source is ImageWatermarkTextSource.FIXED_FIELD
            )
            self._image_rule_watermark_free_radio.setChecked(
                watermark.text_source
                is ImageWatermarkTextSource.WORKBENCH_FREE_FIELD
            )
            self._image_rule_watermark_edit.setText(
                watermark.text_template
                if watermark.text_source is ImageWatermarkTextSource.FIXED_FIELD
                else ""
            )
            self._refresh_watermark_controls()
            self._apply_global_image_policy(
                strategy=strategy,
                watermark=watermark,
            )
        finally:
            self._syncing_image_material_rules = False
        refresh_layout_chain_later(self._image_material_rules_container)

    def _commit_global_image_policy(self) -> bool:
        if self._syncing_image_material_rules:
            return True
        if not self._persist_current_profile_editor():
            self._sync_image_material_rule_rows()
            return False
        snapshot = capture_material_mutation_snapshot(
            local_state={"image_material_rules": self._image_material_rules},
            profile_state=self._selected_profile(),
            profile_index=self._current_profile_index,
            batch_selection=self.bridge.current_material_batch_selection(),
        )
        strategy = (
            self._ADAPTIVE_STRATEGY
            if self._image_rule_adaptive_check.isChecked()
            else self._DIRECT_STRATEGY
        )
        text_source = (
            ImageWatermarkTextSource.WORKBENCH_FREE_FIELD
            if self._image_rule_watermark_free_radio.isChecked()
            else ImageWatermarkTextSource.FIXED_FIELD
        )
        watermark = ImageWatermarkPolicy(
            enabled=self._image_rule_watermark_check.isChecked(),
            text_source=text_source,
            text_template=(
                self._image_rule_watermark_edit.text().strip()
                if text_source is ImageWatermarkTextSource.FIXED_FIELD
                else ""
            ),
        )
        self._refresh_watermark_controls()
        self._apply_global_image_policy(
            strategy=strategy,
            watermark=watermark,
        )
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_image_policy_mutation_selection,
            restore_profile=self._restore_image_policy_mutation_profile,
            restore_local=self._restore_image_policy_mutation_local,
            refresh=self._refresh_image_policy_mutation_ui,
        ):
            return False
        self._refresh_summary()
        return True

    def _restore_image_policy_mutation_selection(self, selection) -> None:
        self.bridge.set_current_material_batch_selection(selection)

    def _restore_image_policy_mutation_profile(self, index: int, profile) -> None:
        self._profiles[index] = profile
        self._update_profile_item(index)

    def _restore_image_policy_mutation_local(self, state) -> None:
        self._image_material_rules = state["image_material_rules"]

    def _refresh_image_policy_mutation_ui(self) -> None:
        self._sync_image_material_rule_rows()
        self._refresh_summary()

    def _refresh_watermark_controls(self) -> None:
        enabled = self._image_rule_watermark_check.isChecked()
        fixed = self._image_rule_watermark_fixed_radio.isChecked()
        self._image_rule_watermark_fixed_radio.setEnabled(enabled)
        self._image_rule_watermark_free_radio.setEnabled(enabled)
        self._image_rule_watermark_edit.setEnabled(enabled and fixed)
        self._image_rule_watermark_edit.setPlaceholderText(
            "水印文字或 {{字段}}" if fixed else "在工作台填写"
        )

    def _apply_global_image_policy(
        self,
        *,
        strategy: str,
        watermark: ImageWatermarkPolicy,
    ) -> None:
        specs = self._image_rule_specs()
        group_roles = {
            spec.role
            for spec in tuple(getattr(self, "_asset_group_specs", ()) or ())
        }
        rules: dict[str, ImageMaterialRule] = {}
        for spec in specs:
            is_group = spec.role in group_roles
            rule_id = f"image:{spec.role}"
            existing = self._image_material_rules.get(rule_id)
            rules[rule_id] = ImageMaterialRule(
                rule_id=rule_id,
                source_role=spec.role,
                anchor_token=spec.target,
                placement=self._global_placement(
                    strategy=strategy,
                    is_group=is_group,
                ),
                required=bool(spec.required),
                occurrence_policy=(
                    existing.occurrence_policy
                    if existing is not None
                    else ImageOccurrencePolicy.EXACTLY_ONE
                ),
                cardinality=(
                    ImageCardinality.MULTIPLE
                    if is_group
                    else ImageCardinality.SINGLE
                ),
                watermark=watermark,
            )
        self._image_material_rules = rules

    @staticmethod
    def _global_placement(
        *,
        strategy: str,
        is_group: bool,
    ) -> ImagePlacementPolicy:
        if strategy == ImageRulesPresenterMixin._DIRECT_STRATEGY:
            return ImagePlacementPolicy(mode=ImagePlacementMode.NATURAL_SIZE)
        if is_group:
            return ImagePlacementPolicy(
                mode=ImagePlacementMode.FIT_CONTAINER_FLOW,
            )
        return ImagePlacementPolicy(
            mode=ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE,
            max_width_cm=16.0,
            co_location_guard=ImageCoLocationGuard.PRECEDING_NONEMPTY_PARAGRAPH,
        )

    def _strategy_from_material_rules(self, specs) -> str:
        rules = [
            self._image_material_rules.get(f"image:{spec.role}")
            for spec in specs
        ]
        existing = [rule for rule in rules if rule is not None]
        if not existing:
            return self._ADAPTIVE_STRATEGY
        adaptive_modes = {
            ImagePlacementMode.FIT_REMAINING_ANCHOR_PAGE,
            ImagePlacementMode.FIT_CONTAINER_FLOW,
        }
        if any(rule.placement.mode in adaptive_modes for rule in existing):
            return self._ADAPTIVE_STRATEGY
        return self._DIRECT_STRATEGY

    def _watermark_from_material_rules(self, specs) -> ImageWatermarkPolicy:
        rules = [
            self._image_material_rules.get(f"image:{spec.role}")
            for spec in specs
        ]
        enabled = [
            rule.watermark
            for rule in rules
            if rule is not None and rule.watermark.enabled
        ]
        if not enabled:
            return ImageWatermarkPolicy()
        source = enabled[0].text_source
        text = ""
        if source is ImageWatermarkTextSource.FIXED_FIELD:
            text = next(
                (
                    policy.text_template
                    for policy in enabled
                    if policy.text_source is source and policy.text_template.strip()
                ),
                "",
            )
        return ImageWatermarkPolicy(
            enabled=True,
            text_source=source,
            text_template=text,
        )

    def _image_rule_specs(self):
        return (
            *tuple(getattr(self, "_asset_slot_specs", ()) or ()),
            *tuple(getattr(self, "_asset_group_specs", ()) or ()),
        )


__all__ = ["ImageRulesPresenterMixin"]
