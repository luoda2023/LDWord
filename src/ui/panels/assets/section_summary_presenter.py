"""Presenter mixin for assets section navigation and summary cards."""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.ui.summary_grid import SummaryGridItem
from src.ui.panels.assets.fields import _field_label
from src.ui.panels.assets.roles import _missing_placeholder_label


@dataclass(frozen=True)
class SectionSummaryRefreshState:
    archive_name: str
    profile_name: str
    state: dict[str, object]
    fields: object
    replacements: object
    asset_items: object
    image_rules: object
    placeholder_tokens: object
    missing_parts: list[str]
    preview_rows: list[dict[str, object]]
    field_count: int
    scanned_count: int
    replacement_count: int
    image_rule_count: int
    generation_count: int
    checked_count: int
    preparation_text: str
    assets_text: str


def _summary_item(
    key: str,
    label: str,
    value: str,
    detail: str,
    *,
    variant: str = "neutral",
    icon_name: str = "",
    detail_emphasis: bool = False,
) -> SummaryGridItem:
    return SummaryGridItem(
        key=key,
        label=label,
        value=value,
        detail=detail,
        detail_emphasis=detail_emphasis,
        variant=variant,
        column_span=4,
        icon_name=icon_name,
    )


class SectionSummaryPresenterMixin:
    """Render derived section card and summary-card state."""

    def _refresh_summary(self) -> None:
        summary_state = self._build_section_summary_state()
        archive_name = summary_state.archive_name
        profile_name = summary_state.profile_name
        state = summary_state.state
        fields = summary_state.fields
        replacements = summary_state.replacements
        asset_items = summary_state.asset_items
        image_rules = summary_state.image_rules
        placeholder_tokens = summary_state.placeholder_tokens
        preview_rows = summary_state.preview_rows
        field_count = summary_state.field_count
        scanned_count = summary_state.scanned_count
        replacement_count = summary_state.replacement_count
        generation_count = summary_state.generation_count
        preparation_text = summary_state.preparation_text

        self._summary.setText(
            f"{archive_name} · 资料已填 {field_count} 项 · 材料已选 {scanned_count} 个 · 生成 {generation_count} 份 · {preparation_text}"
        )
        if hasattr(self, "_generation_status_label"):
            self._generation_status_label.setText(
                f"资料包状态：{preparation_text}。当前使用“{archive_name}”，将生成 {generation_count} 份文档。"
            )
        if hasattr(self, "_generation_detail_label"):
            detail_parts = [
                f"当前资料：{profile_name}",
                f"资料已填 {field_count} 项",
                f"材料已选 {scanned_count} 个",
            ]
            if replacement_count:
                detail_parts.append(f"自定义替换 {replacement_count} 条")
            if image_rules:
                detail_parts.append(f"图片放置 {len(image_rules)} 项")
            self._generation_detail_label.setText(" 路 ".join(detail_parts))
        self._refresh_field_statuses(state)
        if hasattr(self, "_preview_label"):
            self._preview_label.setText(
                self._placeholder_preview_text(
                    placeholder_tokens,
                    fields,
                    replacements,
                    asset_items,
                    image_rules,
                    preview_rows=preview_rows,
                )
            )
        self._refresh_preview_table(preview_rows)
        if hasattr(self, "_batch_preview"):
            preview_paths = self.batch_output_preview()
            preview_text = "多份生成预览：" + ("；".join(preview_paths[:3]) if preview_paths else "暂未选择生成项")
            if len(preview_paths) > 3:
                preview_text += f"；等 {len(preview_paths)} 个目录"
            self._batch_preview.setText(preview_text)
        self._refresh_asset_slot_statuses(asset_items)
        self._refresh_question_figure_items_table(asset_items)
        self._refresh_question_figure_library_table(asset_items)
        self._refresh_question_figure_library_issue_table(asset_items)
        self._refresh_question_figure_library_version_history_table(asset_items)
        self._refresh_question_figure_library_master_version_table()
        self._refresh_section_cards(summary_state=summary_state)
        self._refresh_section_summary_cards(summary_state=summary_state)

    def _build_section_summary_state(self) -> SectionSummaryRefreshState:
        archive_name = self._archive_name_edit.text().strip() or "鏈懡鍚嶈祫鏂欏寘"
        profile_name = self._profile_name_edit.text().strip() or "杩欎竴浠?"
        self._sync_archive_selector()
        state = self._current_preview_state()
        fields = state["fields"]
        replacements = state["replacements"]
        assets_dir = self._assets_picker.path().strip()
        asset_items = state["asset_items"]
        image_rules = state["image_rules"]
        placeholder_tokens = state["placeholder_tokens"]
        checked_count = len(self.selected_batch_profile_ids()) if hasattr(self, "_profile_list") else 0
        missing_parts = self._section_summary_missing_parts(
            fields=fields,
            state=state,
            missing_asset_roles=state["missing_asset_roles"],
            unmatched_placeholders=state["unmatched_placeholders"],
        )
        preview_rows = self._placeholder_preview_rows(
            placeholder_tokens,
            fields,
            replacements,
            asset_items,
            image_rules,
        )
        return SectionSummaryRefreshState(
            archive_name=archive_name,
            profile_name=profile_name,
            state=state,
            fields=fields,
            replacements=replacements,
            asset_items=asset_items,
            image_rules=image_rules,
            placeholder_tokens=placeholder_tokens,
            missing_parts=missing_parts,
            preview_rows=preview_rows,
            field_count=len(fields),
            scanned_count=len(asset_items),
            replacement_count=len(replacements),
            image_rule_count=len(image_rules),
            generation_count=checked_count or 1,
            checked_count=checked_count,
            preparation_text=f"还缺：{'、'.join(missing_parts)}" if missing_parts else "可以生成",
            assets_text="图片目录已选择" if assets_dir else "图片目录未选择",
        )

    def _section_summary_missing_parts(
        self,
        *,
        fields: object,
        state: dict[str, object],
        missing_asset_roles: object,
        unmatched_placeholders: object,
    ) -> list[str]:
        missing_parts: list[str] = []
        if not fields:
            missing_parts.append("鏂囧瓧璧勬枡")
        else:
            missing_parts.extend(_field_label(key) for key in state["missing_required_fields"])
        if missing_asset_roles:
            missing_parts.extend(self._material_role_label(role) for role in missing_asset_roles)
        if unmatched_placeholders:
            missing_parts.extend(
                _missing_placeholder_label(token, self._asset_slot_specs, self._attachment_role_specs)
                for token in unmatched_placeholders[:3]
            )
        return missing_parts

    def _refresh_section_cards(
        self,
        *,
        summary_state: SectionSummaryRefreshState,
    ) -> None:
        if not hasattr(self, "_section_nav_cards"):
            return

        def update(section_id: str, subtitle: str, badge: str, variant: str = "neutral") -> None:
            card = self._section_nav_cards.get(section_id)
            if card is not None:
                card.set_subtitle(subtitle)
                card.set_badge(badge, variant)

        state = summary_state.state
        preview_rows = summary_state.preview_rows
        missing_parts = summary_state.missing_parts
        missing_required_fields = list(state.get("missing_required_fields") or [])
        missing_asset_roles = list(state.get("missing_asset_roles") or [])
        placeholder_tokens = list(state.get("placeholder_tokens") or [])
        imported_count = len(getattr(self, "_imported_field_keys", set()))

        if missing_parts:
            update("generate", summary_state.preparation_text, "needs input", "warning")
        else:
            update("generate", f"Ready to generate ? {summary_state.generation_count} docs", "ready", "success")

        if imported_count:
            update("io", f"Imported {imported_count} fields", "imported", "success")
        else:
            update("io", "Import a data sheet or save this asset pack", "import", "info")

        if missing_required_fields:
            labels = ", ".join(_field_label(key) for key in missing_required_fields[:2])
            if len(missing_required_fields) > 2:
                labels += f" and {len(missing_required_fields) - 2} more"
            update("fields", f"Missing {labels}", f"{len(missing_required_fields)} missing", "warning")
        elif summary_state.field_count:
            update("fields", f"{summary_state.field_count} text fields filled", f"{summary_state.field_count} filled", "success")
        else:
            update("fields", "Fill company, project, and contact fields", "empty", "neutral")

        if missing_asset_roles:
            labels = ", ".join(self._material_role_label(role) for role in missing_asset_roles[:2])
            if len(missing_asset_roles) > 2:
                labels += f" and {len(missing_asset_roles) - 2} more"
            update("images", f"Missing {labels}", f"{len(missing_asset_roles)} missing", "warning")
        elif summary_state.scanned_count:
            update("images", f"{summary_state.scanned_count} assets selected", f"{summary_state.scanned_count} selected", "success")
        else:
            update("images", summary_state.assets_text or "Select logos, seals, signatures, and figures", "empty", "neutral")

        issue_count = sum(1 for row in preview_rows if bool(row.get("issue")))
        matched_count = sum(1 for row in preview_rows if not bool(row.get("issue")))
        if issue_count:
            update("preview", f"{issue_count} placeholders need work", f"{issue_count} open", "warning")
        elif preview_rows:
            update("preview", f"{matched_count} placeholders matched", f"{matched_count} matched", "success")
        elif placeholder_tokens:
            update("preview", "No actionable placeholders in the current document", "review", "info")
        else:
            update("preview", "Preview how fields will be filled", "review", "info")

        if summary_state.checked_count > 1:
            update("batch", f"This run will generate {summary_state.checked_count} docs", f"{summary_state.checked_count} selected", "success")
        elif len(self._profiles) > 1:
            update("batch", f"{len(self._profiles)} profiles available", f"{summary_state.generation_count} docs", "info")
        else:
            update("batch", "Single-profile generation", "1 doc", "neutral")

        required_fields_customized = not self._required_fields_match_default(self._required_field_keys())
        if summary_state.replacement_count or summary_state.image_rule_count or required_fields_customized:
            update("advanced", "Custom rules or advanced settings are active", "custom", "info")
        else:
            update("advanced", "Advanced rules are using defaults", "default", "neutral")

    def _refresh_section_summary_cards(
        self,
        *,
        summary_state: SectionSummaryRefreshState,
    ) -> None:
        if not hasattr(self, "_section_summary_cards"):
            return

        for section_id, items in self._section_summary_item_groups(summary_state).items():
            card = self._section_summary_cards.get(section_id)
            if card is not None:
                card.set_summary_items(items)

    def _section_summary_item_groups(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> dict[str, list[SummaryGridItem]]:
        return {
            "generate": self._generate_summary_items(summary_state),
            "io": self._io_summary_items(summary_state),
            "fields": self._field_summary_items(summary_state),
            "images": self._image_summary_items(summary_state),
            "preview": self._preview_summary_items(summary_state),
            "batch": self._batch_summary_items(summary_state),
            "advanced": self._advanced_summary_items(summary_state),
        }

    def _generate_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        preparation_variant = "warning" if summary_state.missing_parts else "success"
        return [
            _summary_item(
                "ready", "Asset pack status", summary_state.preparation_text,
                f"Current pack: {summary_state.archive_name}", variant=preparation_variant,
                icon_name="play", detail_emphasis=True,
            ),
            _summary_item(
                "current", "Current profile", summary_state.profile_name,
                f"{summary_state.field_count} fields filled",
                variant="info" if summary_state.field_count else "neutral",
                icon_name="package", detail_emphasis=True,
            ),
            _summary_item(
                "copies", "Output count", f"{summary_state.generation_count} docs",
                "Batch profiles selected" if summary_state.checked_count else "Single profile generation",
                variant="info" if summary_state.checked_count else "neutral",
                icon_name="layers",
            ),
        ]

    def _io_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        imported_count = len(getattr(self, "_imported_field_keys", set()))
        return [
            _summary_item(
                "mapping", "Data sheet",
                f"{imported_count} imported" if imported_count else "Ready to import",
                "Fill the current profile from a table",
                variant="success" if imported_count else "info", icon_name="download",
            ),
            _summary_item(
                "archive", "Asset pack", summary_state.archive_name,
                "Can import or export the full pack", icon_name="package",
            ),
            _summary_item(
                "batch_import", "Profiles", f"{len(self._profiles)} profiles",
                "Can be batch imported from a data sheet",
                variant="info" if len(self._profiles) > 1 else "neutral",
                icon_name="layers",
            ),
        ]

    def _field_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        state = summary_state.state
        missing_required_fields = list(state.get("missing_required_fields") or [])
        unmatched_placeholders = list(state.get("unmatched_placeholders") or [])
        placeholder_tokens = list(state.get("placeholder_tokens") or [])
        return [
            _summary_item(
                "filled", "Filled fields", f"{summary_state.field_count} fields",
                "Text fields are available to generation" if summary_state.field_count else "Fill company and project fields first",
                variant="success" if summary_state.field_count else "neutral", icon_name="type",
            ),
            _summary_item(
                "required", "Required fields",
                "Complete" if not missing_required_fields else f"{len(missing_required_fields)} missing",
                ", ".join(_field_label(key) for key in missing_required_fields[:2]) or "Default requirements are satisfied",
                variant="warning" if missing_required_fields else "success", icon_name="file-text",
            ),
            _summary_item(
                "template", "Template hints",
                f"{len(unmatched_placeholders)} open" if unmatched_placeholders else "Matched",
                f"{len(placeholder_tokens)} placeholders found" if placeholder_tokens else "Select a document to scan placeholders",
                variant="warning" if unmatched_placeholders else "info", icon_name="eye",
            ),
        ]

    def _image_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        missing_asset_roles = list(summary_state.state.get("missing_asset_roles") or [])
        has_assets_dir = bool(self._assets_picker.path().strip())
        return [
            _summary_item(
                "dir", "Image directory", "Selected" if has_assets_dir else "Not selected",
                summary_state.assets_text, variant="info" if has_assets_dir else "neutral",
                icon_name="image",
            ),
            _summary_item(
                "assets", "Assets", f"{summary_state.scanned_count} files",
                "Logos, seals, signatures, figures, and attachments",
                variant="success" if summary_state.scanned_count else "neutral",
                icon_name="package",
            ),
            _summary_item(
                "missing_assets", "Missing assets",
                "Complete" if not missing_asset_roles else f"{len(missing_asset_roles)} missing",
                ", ".join(self._material_role_label(role) for role in missing_asset_roles[:2]) or "Checked against template rules",
                variant="warning" if missing_asset_roles else "success", icon_name="eye",
            ),
        ]

    def _preview_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        placeholder_tokens = list(summary_state.state.get("placeholder_tokens") or [])
        issue_count = sum(1 for row in summary_state.preview_rows if bool(row.get("issue")))
        matched_count = sum(1 for row in summary_state.preview_rows if not bool(row.get("issue")))
        return [
            _summary_item(
                "placeholders", "Placeholders",
                f"{len(placeholder_tokens)} found" if placeholder_tokens else "Pending scan",
                "Scanned automatically after selecting a document",
                variant="info" if placeholder_tokens else "neutral", icon_name="file-text",
            ),
            _summary_item(
                "matched", "Matched", f"{matched_count} rows",
                "These values will be applied during generation",
                variant="success" if matched_count else "neutral", icon_name="eye",
            ),
            _summary_item(
                "issues", "Open items",
                "No issues" if not issue_count else f"{issue_count} open",
                "Resolve from fields or image selection",
                variant="warning" if issue_count else "success", icon_name="settings",
            ),
        ]

    def _batch_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        return [
            _summary_item(
                "selected", "This run", f"{summary_state.generation_count} docs",
                "Selected batch profiles" if summary_state.checked_count else "Current profile by default",
                variant="success" if summary_state.checked_count > 1 else "neutral",
                icon_name="play",
            ),
            _summary_item(
                "profiles", "Profiles", f"{len(self._profiles)} profiles",
                "Each profile can output independently",
                variant="info" if len(self._profiles) > 1 else "neutral",
                icon_name="layers",
            ),
            _summary_item(
                "naming", "Naming",
                self._batch_output_naming_combo.currentText() if hasattr(self, "_batch_output_naming_combo") else "Default naming",
                "Adjust output naming below", icon_name="file-text",
            ),
        ]

    def _advanced_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        required_fields = self._required_field_keys()
        required_fields_customized = not self._required_fields_match_default(required_fields)
        return [
            _summary_item(
                "required_rules", "Required rules", f"{len(required_fields)} fields",
                "Controls fields required before generation",
                variant="info" if required_fields_customized else "neutral", icon_name="type",
            ),
            _summary_item(
                "replace_rules", "Replacements", f"{summary_state.replacement_count} rules",
                "Optional replacement rules can stay empty",
                variant="info" if summary_state.replacement_count else "neutral",
                icon_name="settings",
            ),
            _summary_item(
                "image_rules", "Image rules", f"{summary_state.image_rule_count} rules",
                "Controls where image assets are inserted",
                variant="info" if summary_state.image_rule_count else "neutral",
                icon_name="image",
            ),
        ]


__all__ = ["SectionSummaryPresenterMixin"]
