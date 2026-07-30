"""Presenter mixin for assets section navigation and summary cards."""

from __future__ import annotations

from dataclasses import dataclass, replace
from src.qt_api import QTimer
from src.shared.ui.summary_grid import SummaryGridItem
from src.ui.panels.assets.material_preview_projection import (
    MaterialPreviewDraft,
    build_assets_material_preview_snapshot,
)
from src.ui.panels.assets.roles import _missing_placeholder_label
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    try_parse_material_token,
)


@dataclass(frozen=True)
class SectionSummaryRefreshState:
    archive_name: str
    profile_name: str
    state: dict[str, object]
    fields: object
    asset_items: object
    image_rules: object
    placeholder_tokens: object
    missing_parts: list[str]
    preview_rows: list[dict[str, object]]
    field_count: int
    token_count: int
    fixed_token_count: int
    floating_token_count: int
    scanned_count: int
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

    def _material_token_scope_keys(self) -> tuple[list[str], list[str]]:
        fixed, floating = self._official_field_scope_projection()
        return list(fixed), list(floating)

    def _material_token_counts(
        self,
        fields: object,
    ) -> tuple[int, int, int, int]:
        fixed, floating = self._material_token_scope_keys()
        keys = list(dict.fromkeys((*fixed, *floating)))
        values = dict(fields or {})
        filled = sum(1 for key in keys if str(values.get(key, "") or "").strip())
        return len(keys), len(fixed), len(floating), filled

    def _set_material_token_status(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> None:
        if not hasattr(self, "_generation_status_label"):
            return
        self._generation_status_label.setText(
            f"字段资料 {summary_state.token_count} 项"
        )
        if not hasattr(self, "_generation_detail_label"):
            return
        detail = (
            f"固定字段 {summary_state.fixed_token_count} 项 · "
            f"自由字段 {summary_state.floating_token_count} 项 · "
            f"当前已填写 {summary_state.field_count}/{summary_state.token_count}"
        )
        self._generation_detail_label.setText(detail)

    def _schedule_summary_refresh(
        self,
        delay_ms: int = 250,
        *,
        scope: str = "full",
    ) -> None:
        """Coalesce refreshes while retaining the widest requested scope.

        ``fields`` updates the field, preview and summary projections only.
        ``full`` additionally refreshes asset inventories, history tables and
        every other material projection.  A pending full refresh always
        dominates later field-only requests.
        """

        normalized_scope = "fields" if str(scope) == "fields" else "full"
        pending_scope = str(
            getattr(self, "_pending_summary_refresh_scope", "") or ""
        )
        self._pending_summary_refresh_scope = (
            "full"
            if "full" in {pending_scope, normalized_scope}
            else "fields"
        )

        timer = getattr(self, "_summary_refresh_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._run_scheduled_summary_refresh)
            self._summary_refresh_timer = timer
        timer.start(max(0, int(delay_ms)))

    def _run_scheduled_summary_refresh(self) -> None:
        scope = str(
            getattr(self, "_pending_summary_refresh_scope", "full") or "full"
        )
        self._pending_summary_refresh_scope = ""
        if scope == "fields":
            self._refresh_field_only_projection()
        else:
            self._refresh_summary()

    def _refresh_summary(self) -> None:
        self._pending_summary_refresh_scope = ""
        timer = getattr(self, "_summary_refresh_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        summary_state = self._build_section_summary_state()
        self._last_section_summary_state = summary_state
        archive_name = summary_state.archive_name
        state = summary_state.state
        fields = summary_state.fields
        asset_items = summary_state.asset_items
        image_rules = summary_state.image_rules
        placeholder_tokens = summary_state.placeholder_tokens
        preview_rows = summary_state.preview_rows
        field_count = summary_state.field_count
        scanned_count = summary_state.scanned_count
        image_rule_count = summary_state.image_rule_count
        generation_count = summary_state.generation_count

        self._summary.setText(
            f"{archive_name} · 字段资料 {summary_state.token_count} 项 · "
            f"已填写 {field_count}/{summary_state.token_count} · "
            f"文件资料 {len(self._content_bindings)}/{len(self._content_rules)} · "
            f"图片已选 {scanned_count} 个 · 图片关联 {image_rule_count} 项 · "
            f"附件 {sum(len(binding.items) for binding in self._attachment_bindings.values())} 个"
        )
        self._set_material_token_status(summary_state)
        if hasattr(self, "_generation_status_label"):
            source_path = self._placeholder_source_path()
            source_kind = self._placeholder_source_kind()
            target = self._current_execution_target()
            is_official_contract = (
                source_kind == "master"
                and str(getattr(target, "mode_id", "") or "") == "official"
            )
            if hasattr(self, "_overview_preview_refresh_btn"):
                refresh_text = (
                    "校验母版"
                    if is_official_contract
                    else "重新扫描母版"
                    if source_kind == "master"
                    else "重新扫描当前文档"
                )
                self._overview_preview_refresh_btn.setProperty(
                    "responsive_full_text",
                    refresh_text,
                )
                self._overview_preview_refresh_btn.setText(refresh_text)
                self._overview_preview_refresh_btn.setEnabled(bool(source_path))
            if hasattr(self, "_preview_auto_match_btn"):
                preview_refresh_text = (
                    "校验母版"
                    if is_official_contract
                    else "重新扫描母版"
                    if source_kind == "master"
                    else "重新扫描当前文档"
                )
                self._preview_auto_match_btn.setText(preview_refresh_text)
                self._preview_auto_match_btn.setEnabled(bool(source_path))
        if hasattr(self, "_apply_btn"):
            apply_text = f"生成 {generation_count} 份" if generation_count > 1 else "生成文档"
            self._apply_btn.setProperty("responsive_full_text", apply_text)
            self._apply_btn.setText(apply_text)
        self._refresh_field_statuses(state)
        if hasattr(self, "_preview_label"):
            self._preview_label.setText(
                self._placeholder_preview_text(
                    placeholder_tokens,
                    fields,
                    asset_items,
                    image_rules,
                    preview_rows=preview_rows,
                )
            )
        self._refresh_preview_table(preview_rows)
        self._refresh_overview_material_preview(preview_rows)
        if hasattr(self, "_batch_preview"):
            preview_paths = self.batch_output_preview()
            preview_text = "多份生成预览：" + ("；".join(preview_paths[:3]) if preview_paths else "暂未选择生成项")
            if len(preview_paths) > 3:
                preview_text += f"；等 {len(preview_paths)} 个目录"
            self._batch_preview.setText(preview_text)
        self._refresh_asset_slot_statuses(asset_items)
        self._refresh_attachment_role_statuses(asset_items)
        self._refresh_asset_group_rows()
        asset_diagnostics = list(
            getattr(self, "_asset_resolution_diagnostics", ()) or ()
        )
        source_conflicts = [
            item
            for item in asset_diagnostics
            if str(getattr(item, "code", "") or "") == "asset_source_conflict"
        ]
        if source_conflicts and hasattr(self, "_image_assets_status_label"):
            roles = sorted(
                {
                    str(getattr(item, "role", "") or "")
                    for item in source_conflicts
                    if str(getattr(item, "role", "") or "")
                }
            )
            self._image_assets_status_label.setText(
                f"发现 {len(source_conflicts)} 个图片来源冲突：{'、'.join(roles)}；"
                "冲突角色已隔离，清除重复来源后才会进入执行。"
            )
        self._refresh_question_figure_items_table(asset_items)
        self._refresh_question_figure_library_table(asset_items)
        self._refresh_question_figure_library_issue_table(asset_items)
        self._refresh_question_figure_library_version_history_table(asset_items)
        self._refresh_question_figure_library_master_version_table()
        self._refresh_section_cards(summary_state=summary_state)
        self._refresh_section_summary_cards(summary_state=summary_state)
        self._material_persistence.refresh_actions()
        self._publish_material_preview_snapshot(summary_state)

    def _refresh_field_only_projection(self) -> None:
        """Refresh field/preview projections without touching asset tables."""

        cached = getattr(self, "_last_section_summary_state", None)
        if not isinstance(cached, SectionSummaryRefreshState):
            self._refresh_summary()
            return
        fields = self._material_preview_fields()
        timeline_resolver = getattr(self, "_resolve_timeline_preview_fields", None)
        if callable(timeline_resolver):
            fields = timeline_resolver(fields)
        placeholder_tokens = self._scanned_placeholders()
        state = dict(cached.state)
        unmatched = self._unmatched_placeholders(
            placeholder_tokens,
            fields,
            cached.asset_items,
            list(cached.image_rules),
        )
        state.update(
            {
                "fields": fields,
                "placeholder_tokens": placeholder_tokens,
                "unmatched_placeholders": unmatched,
            }
        )
        preview_rows = self._placeholder_preview_rows(
            placeholder_tokens,
            fields,
            cached.asset_items,
            list(cached.image_rules),
        )
        token_count, fixed_token_count, floating_token_count, filled_count = (
            self._material_token_counts(fields)
        )
        summary_state = replace(
            cached,
            state=state,
            fields=fields,
            placeholder_tokens=placeholder_tokens,
            preview_rows=preview_rows,
            field_count=filled_count,
            token_count=token_count,
            fixed_token_count=fixed_token_count,
            floating_token_count=floating_token_count,
            missing_parts=self._section_summary_missing_parts(
                fields=fields,
                state=state,
                missing_asset_roles=state.get("missing_asset_roles", ()),
                unmatched_placeholders=unmatched,
            ),
        )
        self._last_section_summary_state = summary_state
        self._summary.setText(
            f"{summary_state.archive_name} · 字段资料 {summary_state.token_count} 项 · "
            f"已填写 {summary_state.field_count}/{summary_state.token_count} · "
            f"文件资料 {len(self._content_bindings)}/{len(self._content_rules)} · "
            f"图片已选 {summary_state.scanned_count} 个 · 图片关联 "
            f"{summary_state.image_rule_count} 项 · "
            f"附件 {sum(len(binding.items) for binding in self._attachment_bindings.values())} 个"
        )
        self._set_material_token_status(summary_state)
        self._refresh_field_statuses(state)
        if hasattr(self, "_preview_label"):
            self._preview_label.setText(
                self._placeholder_preview_text(
                    placeholder_tokens,
                    fields,
                    cached.asset_items,
                    list(cached.image_rules),
                    preview_rows=preview_rows,
                )
            )
        self._refresh_preview_table(preview_rows)
        self._refresh_overview_material_preview(preview_rows)
        if hasattr(self, "_apply_btn"):
            apply_text = (
                f"生成 {summary_state.generation_count} 份"
                if summary_state.generation_count > 1
                else "生成文档"
            )
            self._apply_btn.setProperty("responsive_full_text", apply_text)
            self._apply_btn.setText(apply_text)
        self._refresh_section_cards(summary_state=summary_state)
        self._refresh_section_summary_cards(summary_state=summary_state)
        self._material_persistence.refresh_actions()
        self._publish_material_preview_snapshot(summary_state)

    def _publish_material_preview_snapshot(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> None:
        """Publish the current editor draft without freezing execution state."""

        publish = getattr(
            getattr(self, "bridge", None),
            "set_current_material_preview_snapshot",
            None,
        )
        if not callable(publish):
            return

        profile = self._selected_profile()
        entry = getattr(self._material_persistence, "current_entry", None)
        fixed_keys, floating_keys = self._official_field_scope_projection()
        publish(
            build_assets_material_preview_snapshot(
                MaterialPreviewDraft(
                    mode_id=self.bridge.current_work_mode_id(),
                    archive_id=self._archive_id_edit.text().strip(),
                    archive_name=self._archive_name_edit.text().strip(),
                    entry_package_id=str(
                        getattr(entry, "package_id", "") or ""
                    ).strip(),
                    entry_source_type=str(
                        getattr(entry, "source_type", "") or ""
                    ).strip(),
                    profile_id=self._profile_id_edit.text().strip(),
                    profile_name=self._profile_name_edit.text().strip(),
                    field_values=dict(summary_state.fields or {}),
                    profile_field_scopes=dict(
                        getattr(profile, "field_scopes", {}) or {}
                    ),
                    official_fixed_keys=fixed_keys,
                    official_floating_keys=floating_keys,
                    asset_items=tuple(summary_state.asset_items or ()),
                    image_count=summary_state.scanned_count,
                    content_count=len(self._content_bindings),
                    attachment_bindings=dict(self._attachment_bindings or {}),
                    conflicts=tuple(self._field_conflict_keys()),
                )
            )
        )

    def _build_section_summary_state(self) -> SectionSummaryRefreshState:
        archive_name = self._archive_name_edit.text().strip() or "未命名资料包"
        profile_name = self._profile_name_edit.text().strip() or "这一份"
        self._sync_archive_selector()
        state = self._current_preview_state()
        fields = state["fields"]
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
            asset_items,
            image_rules,
        )
        token_count, fixed_token_count, floating_token_count, filled_count = (
            self._material_token_counts(fields)
        )
        return SectionSummaryRefreshState(
            archive_name=archive_name,
            profile_name=profile_name,
            state=state,
            fields=fields,
            asset_items=asset_items,
            image_rules=image_rules,
            placeholder_tokens=placeholder_tokens,
            missing_parts=missing_parts,
            preview_rows=preview_rows,
            field_count=filled_count,
            token_count=token_count,
            fixed_token_count=fixed_token_count,
            floating_token_count=floating_token_count,
            scanned_count=len(asset_items),
            image_rule_count=len(image_rules),
            generation_count=checked_count or 1,
            checked_count=checked_count,
            preparation_text="准备生成",
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
        if missing_asset_roles:
            missing_parts.extend(self._material_role_label(role) for role in missing_asset_roles)
        if unmatched_placeholders:
            for token in unmatched_placeholders[:3]:
                ref = try_parse_material_token(str(token))
                if ref is not None and ref.kind is MaterialTokenKind.CONTENT:
                    missing_parts.append(
                        "文件资料：" + ref.identifier
                    )
                elif ref is not None and ref.kind is MaterialTokenKind.ATTACHMENT:
                    missing_parts.append("附件资料：" + ref.identifier)
                else:
                    missing_parts.append(
                        _missing_placeholder_label(token, self._asset_slot_specs)
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

        preview_rows = summary_state.preview_rows
        state = summary_state.state
        placeholder_tokens = list(state.get("placeholder_tokens") or [])

        update(
            "generate",
            f"当前已填写 {summary_state.field_count}/{summary_state.token_count}",
            f"{summary_state.token_count} 项",
            "success" if summary_state.token_count and summary_state.field_count == summary_state.token_count else "info",
        )
        update(
            "fields",
            f"固定字段 {summary_state.fixed_token_count} 项 · "
            f"自由字段 {summary_state.floating_token_count} 项",
            f"{summary_state.field_count}/{summary_state.token_count}",
            "success" if summary_state.field_count else "neutral",
        )

        content_count = len(self._content_rules)
        content_bound = sum(
            1
            for rule in self._content_rules
            if rule.content_id in self._content_bindings
        )
        update(
            "content",
            f"已绑定 {content_bound}/{content_count} 个内容块",
            f"{content_bound}/{content_count}",
            "success" if content_count and content_bound == content_count else "neutral",
        )

        if summary_state.scanned_count:
            adaptive_count = sum(
                1
                for rule in self._image_material_rules.values()
                if str(rule.placement.mode.value)
                == "fit_remaining_anchor_page"
            )
            watermark_count = sum(
                1
                for rule in self._image_material_rules.values()
                if rule.watermark.enabled
            )
            update(
                "images",
                f"已选 {summary_state.scanned_count} 个 · 原页缩放 {adaptive_count} 项 · "
                f"水印 {watermark_count} 项",
                f"{summary_state.scanned_count} 个",
                "success",
            )
        else:
            update("images", summary_state.assets_text or "选择图片资料", "未选择", "neutral")

        attachment_count = sum(
            len(tuple(binding.items or ()))
            for binding in self._attachment_bindings.values()
        )
        required_attachment_missing = len(
            list(state.get("missing_attachment_roles") or [])
        )
        update(
            "attachments",
            (
                f"已选择 {attachment_count} 个交付附件"
                if attachment_count
                else "仅用于清单与资料包交付"
            ),
            (
                f"缺 {required_attachment_missing}"
                if required_attachment_missing
                else f"{attachment_count} 个"
            ),
            (
                "info"
                if required_attachment_missing
                else "success"
                if attachment_count
                else "neutral"
            ),
        )

        issue_count = sum(1 for row in preview_rows if bool(row.get("issue")))
        matched_count = sum(
            1
            for row in preview_rows
            if str(row.get("status") or "") in {"可写入", "已匹配"}
        )
        if issue_count:
            update("preview", f"{issue_count} 个文档字段未填写", f"缺 {issue_count}", "info")
        elif placeholder_tokens:
            update("preview", f"{matched_count} 个文档字段可写入", "可查看", "success")
        elif preview_rows:
            update("preview", "资料已填写，等待绑定执行文档", "待检测", "neutral")
        else:
            update("preview", "查看 {{字段}} 会填入什么", "查看", "info")

        if summary_state.checked_count > 1:
            update("batch", f"This run will generate {summary_state.checked_count} docs", f"{summary_state.checked_count} selected", "success")
        elif len(self._profiles) > 1:
            update("batch", f"{len(self._profiles)} profiles available", f"{summary_state.generation_count} docs", "info")
        else:
            update("batch", "Single-profile generation", "1 doc", "neutral")

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
        groups = {
            "generate": self._generate_summary_items(summary_state),
            "fields": self._field_summary_items(summary_state),
            "content": self._content_summary_items(),
            "images": self._image_summary_items(summary_state),
            "attachments": self._attachment_summary_items(),
            "preview": self._preview_summary_items(summary_state),
            "batch": self._batch_summary_items(summary_state),
        }
        timeline_items = getattr(self, "_timeline_summary_items", None)
        if callable(timeline_items):
            groups["timeline"] = timeline_items()
        return groups

    def _content_summary_items(self) -> list[SummaryGridItem]:
        bound = sum(
            1
            for rule in self._content_rules
            if rule.content_id in self._content_bindings
        )
        return [
            _summary_item(
                "content",
                "文件资料",
                f"{bound}/{len(self._content_rules)} 已绑定",
                "Markdown / DOCX 经语义预检后插入正文",
                variant="success" if bound else "neutral",
                icon_name="file-text",
            )
        ]

    def _attachment_summary_items(self) -> list[SummaryGridItem]:
        count = sum(
            len(tuple(binding.items or ()))
            for binding in self._attachment_bindings.values()
        )
        return [
            _summary_item(
                "attachments",
                "附件资料",
                f"{count} 个文件",
                "只进入清单、校验和交付包，不插入正文",
                variant="success" if count else "neutral",
                icon_name="paperclip",
            )
        ]

    def _generate_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        return [
            _summary_item(
                "fields", "字段资料", f"{summary_state.token_count} 项",
                f"固定字段 {summary_state.fixed_token_count} 项 · 自由字段 {summary_state.floating_token_count} 项",
                variant="info" if summary_state.token_count else "neutral",
                icon_name="type", detail_emphasis=True,
            ),
            _summary_item(
                "current", "当前资料", summary_state.profile_name,
                f"已填写 {summary_state.field_count}/{summary_state.token_count}",
                variant="info" if summary_state.field_count else "neutral",
                icon_name="package", detail_emphasis=True,
            ),
            _summary_item(
                "ownership", "工作边界", "只管理本包 Token",
                "方案必填与执行条件由工作台检查",
                variant="neutral",
                icon_name="package",
            ),
        ]

    def _field_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        return [
            _summary_item(
                "filled", "已填写", f"{summary_state.field_count} 项",
                "资料包已保存的当前值" if summary_state.field_count else "当前 Token 尚无值",
                variant="success" if summary_state.field_count else "neutral", icon_name="type",
            ),
            _summary_item(
                "fixed", "固定字段",
                f"{summary_state.fixed_token_count} 项",
                "长期保存，可跨任务复用",
                variant="info" if summary_state.fixed_token_count else "neutral", icon_name="package",
            ),
            _summary_item(
                "floating", "自由字段",
                f"{summary_state.floating_token_count} 项",
                "每次任务在工作台填写",
                variant="info" if summary_state.floating_token_count else "neutral", icon_name="file-text",
            ),
        ]

    def _image_summary_items(
        self,
        summary_state: SectionSummaryRefreshState,
    ) -> list[SummaryGridItem]:
        has_assets_dir = bool(self._assets_picker.path().strip())
        return [
            _summary_item(
                "dir", "Image directory", "Selected" if has_assets_dir else "Not selected",
                summary_state.assets_text, variant="info" if has_assets_dir else "neutral",
                icon_name="image",
            ),
            _summary_item(
                "assets", "Assets", f"{summary_state.scanned_count} files",
                "Logo、印章、签名和正文图片",
                variant="success" if summary_state.scanned_count else "neutral",
                icon_name="package",
            ),
            _summary_item(
                "image_rules", "Image links",
                f"{len(self._image_material_rules)} rules",
                "每个图片 Token 独立管理尺寸、水印和锚点策略",
                variant="info" if self._image_material_rules else "neutral", icon_name="eye",
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
                "links", "Unlinked items",
                "None" if not issue_count else f"{issue_count} open",
                "Review field or image anchors",
                variant="info" if issue_count else "success", icon_name="settings",
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

__all__ = ["SectionSummaryPresenterMixin"]
