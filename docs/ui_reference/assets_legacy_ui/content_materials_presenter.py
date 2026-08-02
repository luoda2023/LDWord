"""Presenter for reusable Markdown/DOCX content materials."""

from __future__ import annotations

from dataclasses import replace

from src.config.content_artifacts import ContentMaterialBinding
from src.config.content_materials import (
    ContentInsertionRule,
    content_anchor_token,
)
from src.config.library import CONFIG_LIBRARY_ROOT
from src.qt_api import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
    ContentArtifactRepositoryError,
)
from src.services.material_content.compiler import compile_content_material
from src.services.material_content.import_contract import (
    ContentImportDisposition,
    ContentImportFinding,
    aggregate_content_findings,
)
from src.services.material_content.intake import CONTENT_SOURCE_SUFFIXES
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    parse_material_token,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.card import Card
from src.shared.ui.compact_row_actions import CompactRowActions
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.dialogs import confirm
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.material_text_views import ElidedPathEdit
from src.shared.ui.path_action_semantics import PathAction, path_action_presentation
from src.shared.ui.path_drop import PathAcceptancePolicy, attach_path_drop
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toast import Toast
from src.shared.ui.token_row_style import apply_token_row_style
from src.ui.panels.assets.token_naming import (
    is_numbered_series_name,
    next_numbered_name,
    next_series_name,
    numbered_series_prefix,
)
from src.ui.panels.assets.mutation_transaction import (
    capture_material_mutation_snapshot,
    publish_or_rollback_material_mutation,
)


_CONTENT_PATH_POLICY = PathAcceptancePolicy(
    path_kind="file",
    suffixes=CONTENT_SOURCE_SUFFIXES,
    dialog_label="文件资料",
    include_all_files=False,
)


def _blocking_content_message(
    findings: tuple[ContentImportFinding, ...],
) -> str:
    blockers = tuple(
        item
        for item in aggregate_content_findings(findings)
        if item.disposition is ContentImportDisposition.BLOCKER
    )
    if not blockers:
        return "文件资料暂时无法生成可用内容。"
    expanded = tuple(
        item for item in blockers if item.code != "diagnostic_limit_exceeded"
    )
    primary = expanded[0] if expanded else blockers[0]
    omitted = sum(
        item.count
        for item in blockers
        if item.code == "diagnostic_limit_exceeded"
    )
    total_objects = len(expanded) + omitted
    if total_objects <= 1:
        return primary.user_message
    message = primary.user_message.rstrip("。！？；")
    return f"{message}；另有 {total_objects - 1} 个未展开的阻断对象。"


class ContentMaterialsPresenterMixin:
    """Edit typed content bindings and their canonical insertion rules."""

    def _setup_content_materials_card(self) -> None:
        card = Card(parent=self._section_contents["content"])
        self._content_card = card
        card.setObjectName("assets_content_card")
        self._content_materials_title = card.set_header(
            "文件资料",
            icon_name="file-text",
        )
        self._add_content_material_btn = QPushButton("＋ 新增文件资料", card)
        self._add_content_material_btn.setObjectName("content_materials_add_btn")
        apply_button_variant(self._add_content_material_btn, "secondary")
        self._add_content_material_btn.setStyleSheet(
            build_button_stylesheet(get_theme())
        )
        self._add_content_material_btn.clicked.connect(
            self._request_add_content_material
        )
        card.add_header_action(self._add_content_material_btn)

        self._content_materials_container = QWidget(card)
        self._content_materials_layout = QVBoxLayout(
            self._content_materials_container
        )
        self._content_materials_layout.setContentsMargins(0, 0, 0, 0)
        self._content_materials_layout.setSpacing(0)
        card.add_widget(self._content_materials_container)
        self._sync_content_material_rows()
        self._section_layouts["content"].addWidget(card)

    def _request_add_content_material(self) -> None:
        occupied = {rule.content_id for rule in self._content_rules}
        content_id = next_numbered_name("文件", occupied)
        self._insert_content_material(len(self._content_rules), content_id)

    def _add_content_material_series(self, source_content_id: str) -> None:
        rules = list(self._content_rules)
        source_index = next(
            (
                index
                for index, rule in enumerate(rules)
                if rule.content_id == source_content_id
            ),
            -1,
        )
        if source_index < 0:
            return
        occupied = {rule.content_id for rule in rules}
        prefix = numbered_series_prefix(source_content_id)
        content_id = next_series_name(source_content_id, occupied)
        insert_at = source_index + 1
        while (
            insert_at < len(rules)
            and is_numbered_series_name(rules[insert_at].content_id, prefix)
        ):
            insert_at += 1
        self._insert_content_material(insert_at, content_id)

    def _insert_content_material(self, index: int, content_id: str) -> bool:
        normalized = self._normalize_content_id(content_id)
        if not normalized:
            Toast.show_warning("内容名称不能为空，且不能包含空格、花括号或冒号。")
            return False
        if any(rule.content_id == normalized for rule in self._content_rules):
            Toast.show_warning(f"文件资料 {content_anchor_token(normalized)} 已存在。")
            return False
        rule = ContentInsertionRule(
            rule_id=f"content:{normalized}",
            content_id=normalized,
            anchor_token=content_anchor_token(normalized),
        )
        snapshot = self._capture_content_material_mutation_snapshot()
        if snapshot is None:
            return False
        self._content_rules.insert(
            max(0, min(index, len(self._content_rules))),
            rule,
        )
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_content_material_mutation_selection,
            restore_profile=self._restore_content_material_mutation_profile,
            restore_local=self._restore_content_material_mutation_local,
            refresh=self._refresh_content_material_mutation_ui,
        ):
            return False
        self._refresh_content_material_mutation_ui()
        Toast.show_success(f"已新增 {content_anchor_token(normalized)}")
        return True

    def _commit_content_material_token(
        self,
        current_content_id: str,
        raw_token: str,
    ) -> bool:
        current = next(
            (
                rule
                for rule in self._content_rules
                if rule.content_id == current_content_id
            ),
            None,
        )
        if current is None:
            return False
        content_id = self._normalize_content_id(raw_token)
        edit = getattr(self, "_content_material_token_edits", {}).get(
            current_content_id
        )
        if not content_id:
            Toast.show_warning("内容名称不能为空，且不能包含空格、花括号或冒号")
            if edit is not None:
                edit.setText(current.anchor_token)
            return False
        occupied = {
            rule.content_id
            for rule in self._content_rules
            if rule.content_id != current_content_id
        }
        if content_id in occupied:
            Toast.show_warning(f"文件资料已存在：{content_anchor_token(content_id)}")
            if edit is not None:
                edit.setText(current.anchor_token)
            return False
        if content_id == current_content_id:
            if edit is not None:
                edit.setText(current.anchor_token)
            return False

        replacement_rule = replace(
            current,
            rule_id=f"content:{content_id}",
            content_id=content_id,
            anchor_token=content_anchor_token(content_id),
        )
        snapshot = self._capture_content_material_mutation_snapshot()
        if snapshot is None:
            return False
        self._content_rules = [
            replacement_rule if rule.content_id == current_content_id else rule
            for rule in self._content_rules
        ]
        binding = self._content_bindings.pop(current_content_id, None)
        if binding is not None:
            self._content_bindings[content_id] = replace(
                binding,
                content_id=content_id,
                label=(
                    content_id
                    if binding.label == current_content_id
                    else binding.label
                ),
            )
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_content_material_mutation_selection,
            restore_profile=self._restore_content_material_mutation_profile,
            restore_local=self._restore_content_material_mutation_local,
            refresh=self._refresh_content_material_mutation_ui,
        ):
            return False
        self._refresh_content_material_mutation_ui()
        Toast.show_success(f"已修改 Token：{content_anchor_token(content_id)}")
        return True

    def _ensure_content_material_rule(self, content_id: str) -> ContentInsertionRule:
        existing = next(
            (item for item in self._content_rules if item.content_id == content_id),
            None,
        )
        if existing is not None:
            return existing
        rule = ContentInsertionRule(
            rule_id=f"content:{content_id}",
            content_id=content_id,
            anchor_token=content_anchor_token(content_id),
        )
        self._content_rules.append(rule)
        self._sync_content_material_rows()
        return rule

    def _focus_content_material(self, content_id: str) -> bool:
        normalized = self._normalize_content_id(content_id)
        if not normalized:
            return False
        self._ensure_content_material_rule(normalized)
        row = self._content_material_rows.get(normalized, self._content_card)
        self._show_missing_target(row, self._content_card)
        choose = self._content_material_choose_buttons.get(normalized)
        if choose is not None:
            choose.setFocus()
        return True

    @staticmethod
    def _normalize_content_id(raw: object) -> str:
        value = str(raw or "").strip()
        try:
            ref = parse_material_token(value)
        except (TypeError, ValueError):
            ref = None
        if ref is not None:
            if ref.namespace is not MaterialTokenNamespace.FILE:
                return ""
            value = ref.identifier
        if not value or any(char.isspace() or char in "{}:" for char in value):
            return ""
        return value

    def _select_content_material_file(self, content_id: str) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            f"选择 {content_anchor_token(content_id)} 的文件资料",
            "",
            _CONTENT_PATH_POLICY.dialog_filter,
        )
        if not file_path:
            return
        self._bind_content_material_path(content_id, file_path)

    def _bind_content_material_path(self, content_id: str, file_path: str) -> bool:
        rule = next(
            (item for item in self._content_rules if item.content_id == content_id),
            None,
        )
        if rule is None:
            Toast.show_warning("文件内容规则已不存在，请刷新后重试。")
            return False
        snapshot = self._capture_content_material_mutation_snapshot()
        if snapshot is None:
            return False
        previous = self._content_bindings.get(content_id)
        label = previous.label if previous is not None else content_id
        repository = self._content_repository()
        result = compile_content_material(file_path, repository)
        if result.blocked or result.artifact_ref is None:
            Toast.show_warning(_blocking_content_message(result.findings))
            return False
        binding = ContentMaterialBinding(
            content_id=content_id,
            label=label,
            artifact_ref=result.artifact_ref,
        )
        self._content_bindings[content_id] = binding
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_content_material_mutation_selection,
            restore_profile=self._restore_content_material_mutation_profile,
            restore_local=self._restore_content_material_mutation_local,
            refresh=self._refresh_content_material_mutation_ui,
        ):
            return False
        self._refresh_content_material_mutation_ui()
        warnings = [
            item
            for item in result.findings
            if item.disposition is ContentImportDisposition.WARNING
        ]
        if warnings:
            Toast.show_warning(warnings[0].user_message)
        return True

    def _clear_content_material_file(self, content_id: str) -> bool:
        snapshot = self._capture_content_material_mutation_snapshot()
        if snapshot is None:
            return False
        self._content_bindings.pop(content_id, None)
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_content_material_mutation_selection,
            restore_profile=self._restore_content_material_mutation_profile,
            restore_local=self._restore_content_material_mutation_local,
            refresh=self._refresh_content_material_mutation_ui,
        ):
            return False
        self._refresh_content_material_mutation_ui()
        return True

    def _remove_content_material(self, content_id: str) -> bool:
        binding = self._content_bindings.get(content_id)
        source_name = ""
        if binding is not None:
            try:
                source_name = self._content_repository().validate(
                    binding.artifact_ref
                ).manifest.source.original_name
            except ContentArtifactRepositoryError:
                source_name = "已编译文件"
        if binding is not None and not confirm(
            "删除文件内容",
            f"{content_anchor_token(content_id)} 已绑定 {source_name}，"
            "删除后会同时移除绑定。",
            confirm_text="删除",
            destructive=True,
            parent=self,
        ):
            return False
        snapshot = self._capture_content_material_mutation_snapshot()
        if snapshot is None:
            return False
        self._content_bindings.pop(content_id, None)
        self._content_rules = [
            rule for rule in self._content_rules if rule.content_id != content_id
        ]
        if not publish_or_rollback_material_mutation(
            snapshot,
            publish=self._sync_material_batch_selection,
            restore_selection=self._restore_content_material_mutation_selection,
            restore_profile=self._restore_content_material_mutation_profile,
            restore_local=self._restore_content_material_mutation_local,
            refresh=self._refresh_content_material_mutation_ui,
        ):
            return False
        self._refresh_content_material_mutation_ui()
        return True

    def _capture_content_material_mutation_snapshot(self):
        if not self._persist_current_profile_editor():
            return None
        return capture_material_mutation_snapshot(
            local_state={
                "content_bindings": self._content_bindings,
                "content_rules": self._content_rules,
            },
            profile_state=self._selected_profile(),
            profile_index=self._current_profile_index,
            batch_selection=self.bridge.current_material_batch_selection(),
        )

    def _restore_content_material_mutation_selection(self, selection) -> None:
        self.bridge.set_current_material_batch_selection(selection)

    def _restore_content_material_mutation_profile(self, index: int, profile) -> None:
        self._profiles[index] = profile
        self._update_profile_item(index)

    def _restore_content_material_mutation_local(self, state) -> None:
        self._content_bindings = state["content_bindings"]
        self._content_rules = state["content_rules"]

    def _refresh_content_material_mutation_ui(self) -> None:
        self._sync_content_material_rows()
        self._refresh_summary()

    def _sync_content_material_rows(self) -> None:
        if not hasattr(self, "_content_materials_layout"):
            return
        wanted = {rule.content_id for rule in self._content_rules}
        for content_id in tuple(self._content_material_rows):
            if content_id in wanted:
                continue
            row = self._content_material_rows.pop(content_id)
            self._content_material_path_edits.pop(content_id, None)
            self._content_material_status_labels.pop(content_id, None)
            self._content_material_choose_buttons.pop(content_id, None)
            self._content_material_clear_buttons.pop(content_id, None)
            getattr(self, "_content_material_index_labels", {}).pop(content_id, None)
            getattr(self, "_content_material_thumbnail_labels", {}).pop(content_id, None)
            getattr(self, "_content_material_token_edits", {}).pop(content_id, None)
            getattr(self, "_content_material_action_strips", {}).pop(content_id, None)
            getattr(self, "_content_material_add_buttons", {}).pop(content_id, None)
            getattr(self, "_content_material_remove_buttons", {}).pop(content_id, None)
            getattr(self, "_content_material_drop_controllers", {}).pop(
                content_id,
                None,
            )
            row.setParent(None)
            row.deleteLater()
        for index, rule in enumerate(self._content_rules):
            row = self._content_material_rows.get(rule.content_id)
            if row is None:
                row = self._build_content_material_row(rule)
                self._content_material_rows[rule.content_id] = row
                self._content_materials_layout.addWidget(row)
            index_label = getattr(self, "_content_material_index_labels", {}).get(
                rule.content_id
            )
            if index_label is not None:
                index_label.setText(str(index + 1))
            apply_token_row_style(
                row,
                object_name="content_material_row",
                is_last=index == len(self._content_rules) - 1,
            )
            self._refresh_content_material_row(rule)
        count = len(self._content_rules)
        self._content_materials_container.setVisible(count > 0)

    def _build_content_material_row(self, rule: ContentInsertionRule) -> QFrame:
        row = QFrame(self._content_materials_container)
        row.setObjectName("content_material_row")
        row.setProperty("content_id", rule.content_id)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        row.setMinimumHeight(get_theme().token_row_min_height)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(
            4,
            get_theme().token_row_padding_y,
            4,
            get_theme().token_row_padding_y,
        )
        layout.setSpacing(get_theme().token_row_column_gap)

        index_label = QLabel("1", row)
        index_label.setObjectName("asset_row_index")
        index_label.setFixedWidth(34)
        index_label.setAlignment(Qt.AlignCenter)

        thumbnail = QLabel("未选", row)
        thumbnail.setObjectName("content_material_thumbnail")
        thumbnail.setFixedSize(52, 52)
        thumbnail.setAlignment(Qt.AlignCenter)

        token_edit = MaterialTokenEdit(rule.anchor_token, row, editable=True)
        token_edit.setObjectName("content_material_token")
        token_edit.setMinimumWidth(260)
        token_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        token_edit.editingFinished.connect(
            lambda content_id=rule.content_id, widget=token_edit: (
                self._commit_content_material_token(content_id, widget.text())
            )
        )
        token_edit.copied.connect(lambda _text: Toast.show_success("复制成功"))

        path_edit = ElidedPathEdit(parent=row)
        path_edit.setObjectName("content_material_path")
        path_edit.setPlaceholderText("尚未选择文件")
        path_edit.setClearButtonEnabled(False)

        actions = CompactRowActions(row)
        actions.setObjectName("content_material_actions")
        clear = actions.add_action(
            "clear",
            icon_name="x",
            tooltip=f"清除{rule.anchor_token}文件",
            variant="ghost-danger",
            callback=lambda *_args, content_id=rule.content_id: self._clear_content_material_file(
                content_id
            ),
        )
        choose_action = path_action_presentation(PathAction.CHOOSE_FILE)
        choose = actions.add_action(
            "choose",
            icon_name=choose_action.icon_name,
            tooltip=f"为{rule.anchor_token}选择文件",
            callback=lambda *_args, content_id=rule.content_id: self._select_content_material_file(
                content_id
            ),
        )
        choose.setProperty("pathAction", PathAction.CHOOSE_FILE.value)
        add = actions.add_action(
            "add",
            icon_name="plus",
            tooltip=f"新增一项{rule.anchor_token}",
            variant="outlined-primary",
            callback=lambda *_args, content_id=rule.content_id: defer_qt_method(
                self,
                "_add_content_material_series",
                content_id,
            ),
        )
        remove = actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip=f"删除{rule.anchor_token}",
            variant="outlined-danger",
            callback=lambda *_args, content_id=rule.content_id: defer_qt_method(
                self,
                "_remove_content_material",
                content_id,
            ),
        )
        clear.setProperty("content_clear_button", rule.content_id)

        layout.addWidget(index_label, 0, Qt.AlignVCenter)
        layout.addWidget(thumbnail, 0, Qt.AlignVCenter)
        layout.addWidget(token_edit, 0, Qt.AlignVCenter)
        layout.addWidget(path_edit, 1, Qt.AlignVCenter)
        layout.addWidget(actions, 0, Qt.AlignVCenter)

        for name in (
            "_content_material_index_labels",
            "_content_material_thumbnail_labels",
            "_content_material_token_edits",
            "_content_material_action_strips",
            "_content_material_add_buttons",
            "_content_material_remove_buttons",
        ):
            if not hasattr(self, name):
                setattr(self, name, {})
        self._content_material_index_labels[rule.content_id] = index_label
        self._content_material_thumbnail_labels[rule.content_id] = thumbnail
        self._content_material_token_edits[rule.content_id] = token_edit
        self._content_material_action_strips[rule.content_id] = actions
        self._content_material_add_buttons[rule.content_id] = add
        self._content_material_remove_buttons[rule.content_id] = remove
        self._content_material_path_edits[rule.content_id] = path_edit
        self._content_material_choose_buttons[rule.content_id] = choose
        self._content_material_clear_buttons[rule.content_id] = clear
        if not hasattr(self, "_content_material_drop_controllers"):
            self._content_material_drop_controllers = {}
        drop_controller = attach_path_drop(
            parent=row,
            surface=row,
            policy=_CONTENT_PATH_POLICY,
            on_paths=lambda paths, content_id=rule.content_id: self._bind_content_material_path(
                content_id,
                paths[0],
            ),
        )
        self._content_material_drop_controllers[rule.content_id] = drop_controller

        def apply_theme() -> None:
            theme = get_theme()
            layout.setContentsMargins(4, theme.token_row_padding_y, 4, theme.token_row_padding_y)
            layout.setSpacing(theme.token_row_column_gap)
            index_label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.primary}; background: transparent; border: none;"
            )
            thumbnail.setStyleSheet(
                f"QLabel#content_material_thumbnail {{ background: {theme.bg_card}; "
                f"border: 1px solid {theme.border}; border-radius: {theme.radius_sm}px; "
                f"color: {theme.text_hint}; font-size: {theme.font_size_xs}px; }}"
            )
            apply_size_class(path_edit, "md")

        bind_theme(row, apply_theme)
        apply_theme()
        return row

    def _refresh_content_material_row(self, rule: ContentInsertionRule) -> None:
        binding = self._content_bindings.get(rule.content_id)
        path_edit = self._content_material_path_edits.get(rule.content_id)
        thumbnail = getattr(self, "_content_material_thumbnail_labels", {}).get(
            rule.content_id
        )
        token_edit = getattr(self, "_content_material_token_edits", {}).get(
            rule.content_id
        )
        clear = self._content_material_clear_buttons.get(rule.content_id)
        display_name = ""
        source_format = ""
        if binding is not None:
            try:
                manifest = self._content_repository().validate(
                    binding.artifact_ref
                ).manifest
                display_name = manifest.source.original_name
                source_format = manifest.source.format.upper()
            except ContentArtifactRepositoryError:
                display_name = "制品缺失"
        if path_edit is not None:
            path_edit.setText(display_name)
            path_edit.setAccessibleName(display_name)
        if thumbnail is not None:
            thumbnail.setText(source_format if binding is not None else "未选")
        if token_edit is not None:
            token_edit.setCompleted(binding is not None)
        if clear is not None:
            clear.setEnabled(binding is not None)

    @staticmethod
    def _content_repository() -> ContentArtifactRepository:
        return ContentArtifactRepository(CONFIG_LIBRARY_ROOT / "content_artifacts")


__all__ = ["ContentMaterialsPresenterMixin"]
