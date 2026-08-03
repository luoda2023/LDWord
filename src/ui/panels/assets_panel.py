"""Canonical material-package editor.

The panel owns only an editor draft plus package/record selection IDs.  All
domain changes go through ``MaterialPackageService`` and all durable writes go
through the revision-aware repository facade.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from src.application.materials import (
    PACKAGE_CONTRACT_EXTENSIONS_KEY,
    ImportMappingProfile,
    MaterialPackageService,
    default_material_contract_id,
    get_material_contract,
    get_package_material_contract,
    inspect_material_workbook,
    inspect_material_workbook_headers,
    package_material_field_value_source,
    project_material_preview,
)
from src.config.attachment_materials import attachment_natural_path_key
from src.config.material_package_library import (
    MaterialPackageLibraryEntry,
    create_material_package_in_library_with_receipt,
    default_material_package_entry,
    delete_material_package_entry,
    duplicate_material_package_entry_with_receipt,
    list_material_package_entries,
    load_material_package_entry,
    material_package_repository,
)
from src.domain.materials import (
    MaterialDerivationSpec,
    MaterialGroup,
    MaterialIssue,
    MaterialPackage,
    MaterialPackageRef,
    MaterialRecord,
    MaterialResourceBinding,
    MaterialRunSelection,
    MaterialScope,
    MaterialTimelineSpec,
    clone_material_package,
    clone_material_record,
    generate_package_id,
    generate_record_id,
)
from src.infrastructure.materials.codec import material_package_revision
from src.infrastructure.materials.repository import MaterialPackageSnapshot
from src.qt_api import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDesktopServices,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSize,
    QSizePolicy,
    QStackedWidget,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QUrl,
    QVBoxLayout,
    QWidget,
)
from src.shared.engine.material_timeline import parse_timeline_date
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    material_token,
)
from src.shared.ui import (
    DialogAction,
    FontCombo,
    ImagePreviewDialog,
    PreviewItem,
    StyledComboBox,
    Toast,
    apply_button_variant,
    bind_theme,
    build_button_stylesheet,
    build_checkbox_stylesheet,
    build_text_input_stylesheet,
)
from src.shared.ui.asset_column_guide import AssetColumnGuide
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.card import Card
from src.shared.ui.compact_row_actions import CompactRowActions
from src.shared.ui.data_table import fit_table_height_to_contents
from src.shared.ui.detail_geometry import ScrollableDetailGeometrySync
from src.shared.ui.dialogs import confirm, decision, input_text
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.library_action_row import LibraryActionRow
from src.shared.ui.master_detail_shell import MasterDetailShell
from src.shared.ui.material_text_views import ElidedReadOnlyValue
from src.shared.ui.material_token_edit import MaterialTokenEdit
from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.path_drop import PathAcceptancePolicy, attach_path_drop
from src.shared.ui.persistence_actions import PersistenceActions
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.theme import get_theme
from src.shared.ui.themed_radio_button import ThemedRadioButton
from src.shared.ui.timeline_node_column_guide import (
    TimelineNodeColumnGuide,
    TimelineNodeColumnMetrics,
)
from src.shared.ui.token_column_guide import TokenColumnGuide
from src.shared.ui.token_row_style import (
    apply_token_row_style,
    build_token_row_stylesheet,
)
from src.shared.ui.token_section_header import TokenSectionHeader
from src.shared.ui.workspace_dialog import WorkspaceDialog
from src.ui.base_panel import BasePanel
from src.ui.panels.material_legacy_rows import (
    LegacyAssetTokenRow,
    LegacyContentTokenRow,
    LegacyFieldTokenRow,
    LegacyImageGroupTokenRow,
    LegacySingleImageTokenRow,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _PreparedChange:
    action: str
    package: MaterialPackage
    entry: MaterialPackageLibraryEntry
    snapshot: MaterialPackageSnapshot
    selected_record_ids: tuple[str, ...]
    current_record_id: str
    committed_entry: MaterialPackageLibraryEntry | None = None


@dataclass(frozen=True, slots=True)
class _ClassicSectionSpec:
    section_id: str
    title: str
    icon_name: str


@dataclass(frozen=True, slots=True)
class _TimelineSegmentProjection:
    owner_scope: str
    owner_id: str
    segment_id: str
    start_field: str
    end_field: str
    nodes: tuple[tuple[str, MaterialTimelineSpec], ...]
    ratio_based: bool


_CLASSIC_SECTION_SPECS = (
    _ClassicSectionSpec("generate", "资料包概览", "package"),
    _ClassicSectionSpec("fields", "字段资料", "type"),
    _ClassicSectionSpec("content", "文件资料", "file-text"),
    _ClassicSectionSpec("timeline", "时间计划", "chart-no-axes-gantt"),
    _ClassicSectionSpec("images", "图片资料", "image"),
    _ClassicSectionSpec("attachments", "附件资料", "gallery-vertical-end"),
)

_TIMELINE_WEEKEND_OPTIONS = (
    ("不调整周末", "none"),
    ("周末向后顺延", "forward"),
    ("周末向前调整", "backward"),
    ("调整到最近工作日", "nearest"),
)

_TIMELINE_DATE_FORMAT_OPTIONS = (
    ("自动（跟随开始日期）", "auto"),
    ("2025-5-31", "yyyy-M-d"),
    ("2025-05-31", "yyyy-MM-dd"),
    ("2025年5月31日", "yyyy年M月d日"),
    ("2025年05月31日", "yyyy年MM月dd日"),
    ("5月31日", "M月d日"),
    ("05月31日", "MM月dd日"),
    ("2025.5.31", "yyyy.M.d"),
    ("2025/5/31", "yyyy/M/d"),
    ("2025/05/31", "yyyy/MM/dd"),
)


class _WorkbookMappingDialog(WorkspaceDialog):
    """Small explicit header-to-contract mapping confirmation."""

    def __init__(self, source: Path, contract, parent=None) -> None:
        super().__init__(
            title="确认导入字段映射",
            subtitle="确认 Excel 源列与资料字段之间的对应关系",
            preferred_size=QSize(680, 520),
            parent=parent,
        )
        self._headers_by_sheet = dict(inspect_material_workbook_headers(source))
        self._contract = contract

        body = QWidget(self._surface)
        body.setObjectName("material_workbook_mapping_body")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(QLabel("主数据工作表", body))
        self._sheet = StyledComboBox(body)
        self._sheet.addItems(list(self._headers_by_sheet))
        self._sheet.currentTextChanged.connect(self._rebuild)
        top.addWidget(self._sheet, 1)
        layout.addLayout(top)

        self._table = QTableWidget(0, 2, body)
        self._table.setHorizontalHeaderLabels(("源列", "canonical 字段"))
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self._table, 1)

        hint = QLabel(
            "只有这里确认的映射会进入导入草稿；源列别名不会写入资料包。",
            body,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("取消", body)
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("确认导入", body)
        confirm.clicked.connect(self.accept)
        apply_button_variant(cancel, "secondary")
        apply_button_variant(confirm, "primary")
        cancel.setAutoDefault(False)
        confirm.setDefault(True)
        actions.addWidget(cancel)
        actions.addWidget(confirm)
        layout.addLayout(actions)
        self._surface_layout.addWidget(body, 1)
        self._rebuild(self._sheet.currentText())
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._apply_shell_theme(
            build_button_stylesheet(
                theme,
                'QWidget#material_workbook_mapping_body QPushButton',
            )
            + f"""
            QWidget#material_workbook_mapping_body {{
                color: {theme.text_primary};
                background: transparent;
            }}
            QWidget#material_workbook_mapping_body QLabel {{
                color: {theme.text_primary};
                background: transparent;
            }}
            QTableWidget {{
                color: {theme.text_primary};
                background: {theme.bg_card};
                alternate-background-color: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_md}px;
                gridline-color: {theme.border_light};
            }}
            """
        )

    def mapping(self) -> ImportMappingProfile:
        field_map: dict[str, str] = {}
        record_name_sources: list[str] = []
        for row in range(self._table.rowCount()):
            source = self._table.item(row, 0).text()
            combo = self._table.cellWidget(row, 1)
            target = str(combo.currentData() or "") if combo is not None else ""
            if target:
                field_map[source] = target
                if not record_name_sources:
                    record_name_sources.append(source)
        return ImportMappingProfile(
            primary_sheet=self._sheet.currentText(),
            field_key_map=field_map,
            record_name_source_fields=tuple(record_name_sources),
            activation_required_fields=tuple(
                item.key for item in self._contract.fields if item.required
            ),
            auxiliary_single_row_as_shared=False,
        )

    def _rebuild(self, sheet_name: str) -> None:
        headers = self._headers_by_sheet.get(sheet_name, ())
        self._table.setRowCount(len(headers))
        for row, source in enumerate(headers):
            source_item = QTableWidgetItem(source)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 0, source_item)
            combo = StyledComboBox(self._table)
            combo.addItem("不导入", "")
            for field in self._contract.fields:
                combo.addItem(f"{field.label}  ·  {field.key}", field.key)
                if source in {field.key, field.label}:
                    combo.setCurrentIndex(combo.count() - 1)
            self._table.setCellWidget(row, 1, combo)


class _DerivationEditorDialog(BaseDialog):
    """Edit one calculation in a single window instead of a dialog chain."""

    def __init__(self, keys: tuple[str, ...], parent=None) -> None:
        super().__init__(title="添加计算字段", icon_style="input", parent=parent)
        self.setMinimumWidth(560)
        self._keys = keys

        body = QWidget(self)
        layout = QGridLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self._output = StyledComboBox(body)
        self._output.addItems(keys)
        self._preset = StyledComboBox(body)
        self._preset.addItem("复制一个字段", "copy")
        self._preset.addItem("连接多个字段", "join")
        self._source = StyledComboBox(body)
        self._source.addItems(keys)
        self._inputs = QLineEdit(",".join(keys[:2]), self)
        self._inputs.setPlaceholderText("用英文逗号分隔字段键")
        self._separator = QLineEdit(" ", self)
        self._separator.setPlaceholderText("连接符")
        self._source_label = QLabel("来源字段", self)
        self._inputs_label = QLabel("输入字段", self)
        self._separator_label = QLabel("连接符", self)
        self._status = QLabel("", self)
        self._status.setObjectName("material_hint")

        layout.addWidget(QLabel("输出字段", self), 0, 0)
        layout.addWidget(self._output, 0, 1, 1, 2)
        layout.addWidget(QLabel("计算规则", self), 1, 0)
        layout.addWidget(self._preset, 1, 1, 1, 2)
        layout.addWidget(self._source_label, 2, 0)
        layout.addWidget(self._source, 2, 1, 1, 2)
        layout.addWidget(self._inputs_label, 3, 0)
        layout.addWidget(self._inputs, 3, 1, 1, 2)
        layout.addWidget(self._separator_label, 4, 0)
        layout.addWidget(self._separator, 4, 1, 1, 2)
        layout.addWidget(self._status, 5, 0, 1, 3)

        self.content_layout.addWidget(body)
        cancel = self.add_secondary_button("取消")
        confirm = self.add_primary_button("确认添加")
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self._accept_if_valid)
        input_qss = build_text_input_stylesheet(get_theme())
        self._inputs.setStyleSheet(input_qss)
        self._separator.setStyleSheet(input_qss)
        self._preset.currentIndexChanged.connect(self._sync_preset)
        self._sync_preset()

    def output_field(self) -> str:
        return self._output.currentText()

    def specification(self) -> MaterialDerivationSpec:
        output = self.output_field()
        if self._preset.currentData() == "copy":
            return MaterialDerivationSpec(
                output_field=output,
                preset_id="copy",
                preset_version=1,
                input_fields=(self._source.currentText(),),
            )
        inputs = tuple(
            item.strip()
            for item in self._inputs.text().split(",")
            if item.strip()
        )
        return MaterialDerivationSpec(
            output_field=output,
            preset_id="join",
            preset_version=1,
            input_fields=inputs,
            parameters={"separator": self._separator.text()},
        )

    def _sync_preset(self, *_args) -> None:
        copy_mode = self._preset.currentData() == "copy"
        self._source_label.setVisible(copy_mode)
        self._source.setVisible(copy_mode)
        self._inputs_label.setVisible(not copy_mode)
        self._inputs.setVisible(not copy_mode)
        self._separator_label.setVisible(not copy_mode)
        self._separator.setVisible(not copy_mode)
        self._status.clear()

    def _accept_if_valid(self) -> None:
        if self._preset.currentData() == "join":
            inputs = tuple(
                item.strip()
                for item in self._inputs.text().split(",")
                if item.strip()
            )
            unknown = tuple(item for item in inputs if item not in self._keys)
            if not inputs:
                self._status.setText("至少填写一个输入字段。")
                return
            if unknown:
                self._status.setText("不存在的字段：" + "、".join(unknown))
                return
        self.accept()


class _CurrentPageStack(QStackedWidget):
    """Let the active classic detail page define the scrollable shell height."""

    def sizeHint(self):
        current = self.currentWidget()
        return current.sizeHint() if current is not None else super().sizeHint()

    def minimumSizeHint(self):
        current = self.currentWidget()
        return (
            current.minimumSizeHint()
            if current is not None
            else super().minimumSizeHint()
        )


class AssetsPanel(BasePanel):
    panel_title = "资料包"
    panel_icon = "package"

    def _setup_ui(self) -> None:
        self.setObjectName("AssetsPanel")
        self._mode_id = self.bridge.current_work_mode_id()
        self._entry: MaterialPackageLibraryEntry | None = None
        self._snapshot: MaterialPackageSnapshot | None = None
        self._package: MaterialPackage | None = None
        self._selected_record_ids: tuple[str, ...] = ()
        self._current_record_id = ""
        self._dirty = False
        self._updating = False
        self._syncing_content_policy = False
        self._syncing_image_policy = False
        self._creating_resource_role = False
        self._prepared: _PreparedChange | None = None
        self._resource_tables: dict[str, QTableWidget] = {}
        self._resource_action_buttons: dict[str, tuple[QPushButton, ...]] = {}
        self._legacy_field_rows: dict[str, LegacyFieldTokenRow] = {}
        self._legacy_field_scopes: dict[str, str] = {}
        self._legacy_resource_rows: dict[
            str,
            dict[str, LegacyContentTokenRow | LegacyAssetTokenRow],
        ] = {
            "content": {},
            "image": {},
            "attachment": {},
        }
        self._resource_section_layouts: dict[
            tuple[str, str],
            QVBoxLayout,
        ] = {}
        self._resource_section_headers: dict[
            tuple[str, str],
            TokenSectionHeader,
        ] = {}
        self._resource_column_guides: dict[
            tuple[str, str],
            AssetColumnGuide,
        ] = {}
        self._resource_empty_labels: dict[tuple[str, str], QLabel] = {}
        self._resource_import_directories: dict[
            tuple[str, str, str, str],
            Path,
        ] = {}
        self._timeline_segment_rows: dict[str, QFrame] = {}

        # Restore the original master-detail information architecture.  The
        # widgets below are V1-backed, but the navigation, cards, spacing, and
        # responsive shell intentionally follow the retained classic design.
        self._shell = MasterDetailShell(
            self,
            panel_name="AssetsPanel",
            nav_object_name="assets_section_rail",
            detail_object_name="assets_detail_scroll",
            detail_content_object_name="assets_detail_content",
            # AssetsPanel owns a larger descendant stylesheet in _apply_theme.
            # A second host binding from MasterDetailShell would run after the
            # panel's deferred show refresh and replace that stylesheet with
            # the shell-only rule, exposing native white table backgrounds.
            bind_to_theme=False,
        )
        self._outer_layout = self._shell.layout
        self._section_nav = self._shell.nav_rail
        self._detail_scroll = self._shell.detail_scroll
        self._detail_shell = self._shell.detail_container
        self._detail_layout = self._shell.detail_layout
        self._detail_geometry = ScrollableDetailGeometrySync(
            self._detail_shell,
            self._detail_layout,
            self._detail_scroll,
            parent=self,
        )
        self._detail_stack = _CurrentPageStack(self._detail_shell)
        self._detail_stack.setObjectName("assets_detail_stack")
        self._detail_stack.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )
        self._detail_layout.addWidget(self._detail_stack, 1)

        self._active_section_id = "generate"
        self._section_nav_cards: dict[str, NavigationCard] = {}
        self._section_pages: dict[str, QWidget] = {}
        self._section_layouts: dict[str, QVBoxLayout] = {}
        specs_by_id = {spec.section_id: spec for spec in _CLASSIC_SECTION_SPECS}
        for group_title, section_ids in (
            ("", ("generate",)),
            (
                "资料准备",
                ("fields", "content", "timeline", "images", "attachments"),
            ),
        ):
            if group_title:
                self._section_nav.add_section_header(group_title)
            for section_id in section_ids:
                spec = specs_by_id[section_id]
                nav_card = NavigationCard(
                    section_id,
                    spec.title,
                    icon_name=spec.icon_name,
                    parent=self._section_nav,
                )
                nav_card.setObjectName(f"assets_section_card_{section_id}")
                self._section_nav_cards[section_id] = nav_card
                self._section_nav.add_card(section_id, nav_card)

                page = QWidget(self._detail_stack)
                page.setObjectName(f"assets_section_content_{section_id}")
                page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
                page_layout = QVBoxLayout(page)
                page_layout.setContentsMargins(0, 0, 0, 0)
                page_layout.setSpacing(get_theme().template_detail_section_gap)
                self._detail_stack.addWidget(page)
                self._section_pages[section_id] = page
                self._section_layouts[section_id] = page_layout

        overview_page = self._section_pages["generate"]
        overview_layout = self._section_layouts["generate"]
        archive_card = Card(parent=overview_page)
        self._archive_card = archive_card
        archive_card.set_header("当前资料包", icon_name="package")
        self._package_combo = StyledComboBox(archive_card)
        self._package_combo.setObjectName("assets_overview_archive_combo")
        self._package_combo.set_full_width_mode(True)
        self._package_combo.currentIndexChanged.connect(self._on_package_changed)
        archive_card.add_widget(self._package_combo)

        self._package_actions = LibraryActionRow(
            archive_card,
            object_name="assets_overview_archive_action_row",
        )
        self._new_package_button = self._package_actions.add_action(
            "new",
            "新建",
            object_name="assets_overview_new_archive_btn",
            icon_name="plus",
            callback=self._create_package,
        )
        self._duplicate_button = self._package_actions.add_action(
            "duplicate",
            "复制",
            object_name="assets_overview_duplicate_archive_btn",
            icon_name="copy",
            callback=self._duplicate_package,
        )
        self._rename_package_button = self._package_actions.add_action(
            "rename",
            "重命名",
            object_name="assets_overview_rename_archive_btn",
            icon_name="pencil-line",
            callback=self._prompt_rename_package,
        )
        self._import_package_button = self._package_actions.add_action(
            "import",
            "导入表格",
            object_name="assets_overview_import_archive_btn",
            icon_name="file-input",
            callback=self._import_workbook,
        )
        self._open_package_folder_button = self._package_actions.add_action(
            "open_folder",
            "打开文件夹",
            object_name="assets_overview_open_archive_folder_btn",
            icon_name="folder-open",
            callback=self._open_package_folder,
        )
        self._delete_button = self._package_actions.add_action(
            "delete",
            "删除",
            object_name="assets_overview_delete_archive_btn",
            icon_name="trash-2",
            variant="ghost-danger",
            side="right",
            callback=self._delete_package,
        )
        archive_card.add_widget(self._package_actions)
        self._new_package_button.setToolTip("新建资料包")
        self._duplicate_button.setToolTip("创建资料包副本")
        self._rename_package_button.setToolTip("重命名当前资料包")
        self._import_package_button.setToolTip("从表格导入资料包")
        self._open_package_folder_button.setToolTip("打开当前资料包文件夹")
        self._delete_button.setToolTip("删除当前资料包")

        self._package_name = QLineEdit(archive_card)
        self._package_name.setPlaceholderText("资料包名称")
        self._package_name.editingFinished.connect(self._rename_package)
        self._package_name.hide()

        # These labels remain as compatibility projections for integrations,
        # but the visible overview no longer repeats information already
        # carried by the package selector and edit controls.
        self._mode_label = QLabel(self._mode_id, archive_card)
        self._mode_label.setObjectName("material_mode_badge")
        self._mode_label.hide()
        self._status = QLabel("", archive_card)
        self._status.setObjectName("material_status")
        self._status.hide()
        self._source_banner = QLabel("", archive_card)
        self._source_banner.setObjectName("material_source_banner")
        self._source_banner.setWordWrap(True)
        self._source_banner.hide()
        overview_layout.addWidget(archive_card)

        overview_card = Card(parent=overview_page)
        self._generate_card = overview_card
        overview_card.set_header("资料 Token", icon_name="braces")
        self._overview_summary = QLabel("", overview_card)
        self._overview_summary.setObjectName("material_overview_summary")
        self._overview_summary.setWordWrap(True)
        self._overview_summary.hide()
        self._overview_preview_table = QTableWidget(0, 3, overview_card)
        self._overview_preview_table.setObjectName("assets_overview_preview_table")
        self._overview_preview_table.setHorizontalHeaderLabels(
            ("资料 Token", "当前内容", "状态")
        )
        self._configure_readonly_table(self._overview_preview_table)
        self._overview_preview_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._overview_preview_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self._overview_preview_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self._overview_preview_table.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        self._overview_preview_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeToContents,
        )
        self._overview_preview_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.Stretch,
        )
        self._overview_preview_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeToContents,
        )
        overview_card.add_widget(self._overview_preview_table)
        overview_layout.addWidget(overview_card)

        check_card = Card(parent=overview_page)
        self._preview_card = check_card
        check_card.set_header("生成检查", icon_name="eye")
        check_card.add_widget(self._build_check_tab(check_card))
        # Keep the legacy projection alive for compatibility, but generation
        # validation belongs to the execution flow and must not reappear in the
        # material overview after a parent/page refresh.
        check_card.hide()
        overview_layout.addStretch(1)

        fields_page = self._section_pages["fields"]
        fields_layout = self._section_layouts["fields"]
        records_card = Card(parent=fields_page)
        self._profile_list_card = records_card
        records_card.set_header("资料记录", icon_name="layers")
        records_card.set_description(
            "一条记录代表一份可生成资料；勾选顺序就是本次生成顺序。"
        )
        self._records = QListWidget(records_card)
        self._records.setObjectName("assets_profile_list")
        self._records.setSelectionMode(QAbstractItemView.SingleSelection)
        self._records.currentItemChanged.connect(self._on_current_record_changed)
        self._records.itemChanged.connect(self._on_record_checked)
        self._records.setMinimumHeight(150)
        self._records.setMaximumHeight(260)
        records_card.add_widget(self._records)
        record_actions = QHBoxLayout()
        self._add_record_button = QPushButton("添加记录", records_card)
        self._add_record_button.clicked.connect(self._add_record)
        apply_button_variant(self._add_record_button, "secondary")
        self._remove_record_button = QPushButton("删除记录", records_card)
        self._remove_record_button.clicked.connect(self._remove_record)
        apply_button_variant(self._remove_record_button, "ghost-danger")
        record_actions.addWidget(self._add_record_button)
        record_actions.addWidget(self._remove_record_button)
        record_actions.addStretch(1)
        records_card.add_layout(record_actions)
        fields_layout.addWidget(records_card)
        # The record list is still the V1 selection projection, but the
        # classic tertiary field page never exposed it as a standalone card.
        records_card.hide()

        record_card = Card(parent=fields_page)
        self._record_card = record_card
        record_card.set_header("当前资料", icon_name="file-text")
        record_row = QGridLayout()
        record_row.addWidget(QLabel("这一份名称", record_card), 0, 0)
        self._record_name = QLineEdit(record_card)
        self._record_name.editingFinished.connect(self._rename_record)
        record_row.addWidget(self._record_name, 0, 1)
        record_row.addWidget(QLabel("状态", record_card), 0, 2)
        self._lifecycle = StyledComboBox(record_card)
        for value, label in (
            ("draft", "草稿"),
            ("active", "可执行"),
            ("disabled", "停用"),
            ("archived", "归档"),
        ):
            self._lifecycle.addItem(label, value)
        self._lifecycle.currentIndexChanged.connect(self._set_lifecycle)
        record_row.addWidget(self._lifecycle, 0, 3)
        record_row.addWidget(QLabel("所属分组", record_card), 1, 0)
        self._record_group = StyledComboBox(record_card)
        self._record_group.currentIndexChanged.connect(self._move_record)
        record_row.addWidget(self._record_group, 1, 1)
        self._add_group_button = QPushButton("新建分组", record_card)
        self._add_group_button.clicked.connect(self._add_group)
        apply_button_variant(self._add_group_button, "secondary")
        record_row.addWidget(self._add_group_button, 1, 2)
        group_actions = QWidget(record_card)
        group_actions_layout = QHBoxLayout(group_actions)
        group_actions_layout.setContentsMargins(0, 0, 0, 0)
        group_actions_layout.setSpacing(6)
        self._rename_group_button = QPushButton("重命名", group_actions)
        self._rename_group_button.clicked.connect(self._rename_group)
        apply_button_variant(self._rename_group_button, "secondary")
        group_actions_layout.addWidget(self._rename_group_button)
        self._remove_group_button = QPushButton("删除", group_actions)
        self._remove_group_button.clicked.connect(self._remove_group)
        apply_button_variant(self._remove_group_button, "ghost-danger")
        group_actions_layout.addWidget(self._remove_group_button)
        record_row.addWidget(group_actions, 1, 3)
        record_card.add_layout(record_row)

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("编辑作用域", record_card))
        self._scope = StyledComboBox(record_card)
        self._scope.currentIndexChanged.connect(self._refresh_scope_views)
        scope_row.addWidget(self._scope, 1)
        self._scope_hint = QLabel("下层可以覆盖上层", record_card)
        self._scope_hint.setObjectName("material_hint")
        scope_row.addWidget(self._scope_hint)
        record_card.add_layout(scope_row)
        fields_layout.addWidget(record_card)
        # Lifecycle, group and layer ownership remain available to the V1
        # service.  They are intentionally non-visual here so that the classic
        # field editor is not replaced by a storage-layer administration form.
        record_card.hide()

        field_card = Card(parent=fields_page)
        self._profile_card = field_card
        field_card.set_header("字段资料", icon_name="type")
        self._record_name.setParent(field_card)
        self._record_name.setPlaceholderText("例如：项目 A / 第一份")
        self._profile_form = InspectorForm(parent=field_card)
        self._profile_name_row = template_form_row(
            "这一份名称",
            self._record_name,
            parent=self._profile_form,
        )
        self._profile_form.add_widget(self._profile_name_row)
        field_card.add_widget(self._profile_form)
        # V1.0 release scope: one package exposes one regular field-value set.
        # Keep the record-name editor alive for package compatibility, but do
        # not expose per-record naming in the field page.
        self._profile_form.hide()

        self._field_mapping_example = QLabel(
            "样例：Word 中写 {{@text:公司名称}}，这里只编辑“公司名称”。",
            field_card,
        )
        self._field_mapping_example.setObjectName("material_field_mapping_example")
        self._field_mapping_example.setWordWrap(True)
        field_card.add_widget(self._field_mapping_example)
        self._field_mapping_example.hide()

        self._field_groups_panel = QWidget(field_card)
        field_groups_layout = QVBoxLayout(self._field_groups_panel)
        field_groups_layout.setContentsMargins(0, 0, 0, 0)
        field_groups_layout.setSpacing(14)

        fixed_header = TokenSectionHeader(
            "固定字段",
            hint="长期复用",
            add_text="＋ 新增固定字段",
            parent=self._field_groups_panel,
        )
        self._fixed_field_header = fixed_header
        self._fixed_field_count = fixed_header.count_label
        self._add_material_field_button = fixed_header.add_button
        self._add_material_field_button.setObjectName("material_v1_add_field_button")
        self._add_material_field_button.clicked.connect(
            lambda _checked=False: self._request_add_field_definition("fixed")
        )
        field_groups_layout.addWidget(fixed_header)

        self._fixed_fields_body = QWidget(self._field_groups_panel)
        fixed_fields_layout = QVBoxLayout(self._fixed_fields_body)
        fixed_fields_layout.setContentsMargins(0, 0, 0, 0)
        fixed_fields_layout.setSpacing(0)
        self._field_column_guide = TokenColumnGuide(
            action_count=3,
            parent=self._fixed_fields_body,
        )
        self._field_column_guide.setProperty("fieldScope", "fixed")
        self._field_column_guide.metrics_changed.connect(
            lambda metrics: self._apply_legacy_field_metrics(metrics, "fixed")
        )
        fixed_fields_layout.addWidget(self._field_column_guide)
        self._legacy_fields_container = QWidget(self._fixed_fields_body)
        self._legacy_fields_layout = QVBoxLayout(self._legacy_fields_container)
        self._legacy_fields_layout.setContentsMargins(0, 0, 0, 0)
        self._legacy_fields_layout.setSpacing(0)
        fixed_fields_layout.addWidget(self._legacy_fields_container)
        self._empty_fixed_fields_label = QLabel(
            "暂无固定字段，点击上方新增。",
            self._fixed_fields_body,
        )
        self._empty_fixed_fields_label.setObjectName("material_hint")
        fixed_fields_layout.addWidget(self._empty_fixed_fields_label)
        field_groups_layout.addWidget(self._fixed_fields_body)

        floating_header = TokenSectionHeader(
            "自由字段",
            hint="每次填写",
            add_text="＋ 新增自由字段",
            parent=self._field_groups_panel,
        )
        self._floating_field_header = floating_header
        self._floating_field_count = floating_header.count_label
        self._add_floating_material_field_button = floating_header.add_button
        self._add_floating_material_field_button.setObjectName(
            "material_v1_add_floating_field_button"
        )
        self._add_floating_material_field_button.clicked.connect(
            lambda _checked=False: self._request_add_field_definition("floating")
        )
        field_groups_layout.addWidget(floating_header)

        self._floating_fields_body = QWidget(self._field_groups_panel)
        floating_fields_layout = QVBoxLayout(self._floating_fields_body)
        floating_fields_layout.setContentsMargins(0, 0, 0, 0)
        floating_fields_layout.setSpacing(0)
        self._floating_field_column_guide = TokenColumnGuide(
            action_count=3,
            parent=self._floating_fields_body,
        )
        self._floating_field_column_guide.setProperty("fieldScope", "floating")
        self._floating_field_column_guide.metrics_changed.connect(
            lambda metrics: self._apply_legacy_field_metrics(metrics, "floating")
        )
        floating_fields_layout.addWidget(self._floating_field_column_guide)
        self._floating_fields_container = QWidget(self._floating_fields_body)
        self._floating_fields_layout = QVBoxLayout(self._floating_fields_container)
        self._floating_fields_layout.setContentsMargins(0, 0, 0, 0)
        self._floating_fields_layout.setSpacing(0)
        floating_fields_layout.addWidget(self._floating_fields_container)
        self._empty_floating_fields_label = QLabel(
            "暂无自由字段，点击上方新增；生成时在工作台填写。",
            self._floating_fields_body,
        )
        self._empty_floating_fields_label.setObjectName("material_hint")
        floating_fields_layout.addWidget(self._empty_floating_fields_label)
        field_groups_layout.addWidget(self._floating_fields_body)

        # Compatibility projection retained for integrations that only query
        # whether the field editor is globally empty.
        self._empty_fields_label = QLabel("", field_card)
        self._empty_fields_label.hide()
        field_card.add_widget(self._field_groups_panel)

        # Retain the V1 table as a non-visual compatibility projection for
        # selection-based commands and existing integrations.
        self._fields = QTableWidget(0, 4, field_card)
        self._fields.setObjectName("assets_fields_table")
        self._fields.setHorizontalHeaderLabels(
            ("字段", "占位符", "当前层值", "生效来源")
        )
        self._fields.verticalHeader().setVisible(False)
        self._fields.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeToContents,
        )
        self._fields.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeToContents,
        )
        self._fields.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._fields.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeToContents,
        )
        self._fields.itemChanged.connect(self._on_field_changed)
        self._fields.hide()
        self._clear_field_button = QPushButton("清除当前层设置", field_card)
        self._clear_field_button.clicked.connect(self._clear_selected_field)
        apply_button_variant(self._clear_field_button, "secondary")
        self._clear_field_button.hide()
        fields_layout.addWidget(field_card)
        fields_layout.addStretch(1)

        for section_id, domain, title, icon in (
            ("content", "content", "文件资料", "file-text"),
            ("images", "image", "图片资料", "image"),
            ("attachments", "attachment", "附件资料", "gallery-vertical-end"),
        ):
            page = self._section_pages[section_id]
            if section_id == "content":
                rules_card = Card(parent=page)
                self._content_rules_card = rules_card
                rules_card.set_header("文件规则", icon_name="sliders-horizontal")
                content_policy = QWidget(rules_card)
                content_policy.setObjectName("content_global_rules")
                content_policy_layout = QVBoxLayout(content_policy)
                content_policy_layout.setContentsMargins(0, 0, 0, 0)
                content_policy_layout.setSpacing(12)

                format_row = QHBoxLayout()
                format_row.addWidget(QLabel("内容插入格式", content_policy))
                self._content_rule_target_radio = ThemedRadioButton(
                    "使用目标文档格式",
                    content_policy,
                )
                self._content_rule_source_radio = ThemedRadioButton(
                    "保留来源格式（仅 DOCX，暂不支持）",
                    content_policy,
                )
                self._content_rule_plain_radio = ThemedRadioButton(
                    "仅保留文本",
                    content_policy,
                )
                self._content_rule_format_group = QButtonGroup(content_policy)
                for radio in (
                    self._content_rule_target_radio,
                    self._content_rule_plain_radio,
                ):
                    self._content_rule_format_group.addButton(radio)
                    format_row.addWidget(radio)
                # Keep the future source-format projection isolated from the
                # live UI until DOCX style/numbering migration is implemented.
                self._content_rule_source_radio.setEnabled(False)
                self._content_rule_source_radio.hide()
                format_row.addStretch(1)
                content_policy_layout.addLayout(format_row)

                behavior_row = QHBoxLayout()
                self._content_rule_page_break_check = QCheckBox(
                    "保留源文件中的显式分页符",
                    content_policy,
                )
                behavior_row.addWidget(self._content_rule_page_break_check)
                behavior_row.addStretch(1)
                content_policy_layout.addLayout(behavior_row)
                rules_card.add_widget(content_policy)

                for control in (
                    self._content_rule_target_radio,
                    self._content_rule_plain_radio,
                    self._content_rule_page_break_check,
                ):
                    control.toggled.connect(self._commit_content_policy)
                self._section_layouts[section_id].addWidget(rules_card)
            if section_id == "images":
                rules_card = Card(parent=page)
                self._image_rules_card = rules_card
                rules_card.set_header("图片规则", icon_name="sliders-horizontal")
                image_policy = QWidget(rules_card)
                image_policy.setObjectName("image_global_rules")
                image_policy_layout = QVBoxLayout(image_policy)
                image_policy_layout.setContentsMargins(0, 0, 0, 0)
                image_policy_layout.setSpacing(16)
                strategy_row = QHBoxLayout()
                self._image_rule_adaptive_check = QCheckBox(
                    "自适应缩放",
                    image_policy,
                )
                self._image_rule_adaptive_check.setObjectName(
                    "image_rule_adaptive_check"
                )
                strategy_row.addWidget(self._image_rule_adaptive_check)
                self._image_rule_page_break_after_check = QCheckBox(
                    "图片后插入分页符",
                    image_policy,
                )
                self._image_rule_page_break_after_check.setObjectName(
                    "image_rule_page_break_after_check"
                )
                self._image_rule_page_break_after_check.setToolTip(
                    "每个图片占位符完成全部图片插入后追加一个分页符"
                )
                strategy_row.addWidget(self._image_rule_page_break_after_check)

                self._image_rule_single_name_check = QCheckBox(
                    "单图前显示名称",
                    image_policy,
                )
                self._image_rule_single_name_check.setObjectName(
                    "image_rule_single_name_check"
                )
                self._image_rule_single_name_check.setToolTip(
                    "单图前显示资料项在“名称”列中配置的名称"
                )
                self._image_rule_multi_name_check = QCheckBox(
                    "多图前显示名称",
                    image_policy,
                )
                self._image_rule_multi_name_check.setObjectName(
                    "image_rule_multi_name_check"
                )
                self._image_rule_multi_name_check.setToolTip(
                    "多图文件夹只在第一张图片前显示一次配置名称"
                )
                strategy_row.addWidget(self._image_rule_single_name_check)
                strategy_row.addWidget(self._image_rule_multi_name_check)
                strategy_row.addStretch(1)
                image_policy_layout.addLayout(strategy_row)

                watermark_row = QHBoxLayout()
                self._image_rule_watermark_check = QCheckBox(
                    "图片水印",
                    image_policy,
                )
                self._image_rule_watermark_check.setObjectName(
                    "image_rule_watermark_check"
                )
                self._image_rule_watermark_fixed_radio = ThemedRadioButton(
                    "固定字段",
                    image_policy,
                )
                self._image_rule_watermark_free_radio = ThemedRadioButton(
                    "自由字段",
                    image_policy,
                )
                self._image_rule_watermark_source_group = QButtonGroup(image_policy)
                self._image_rule_watermark_source_group.addButton(
                    self._image_rule_watermark_fixed_radio
                )
                self._image_rule_watermark_source_group.addButton(
                    self._image_rule_watermark_free_radio
                )
                self._image_rule_watermark_edit = QLineEdit(image_policy)
                self._image_rule_watermark_edit.setObjectName(
                    "image_rule_watermark_edit"
                )
                self._image_rule_watermark_edit.setPlaceholderText(
                    "水印文字或 {{字段}}"
                )
                self._image_rule_watermark_font_label = QLabel(
                    "水印字体",
                    image_policy,
                )
                self._image_rule_watermark_font_label.setObjectName(
                    "image_rule_watermark_font_label"
                )
                self._image_rule_watermark_font = FontCombo(
                    lang="cn",
                    parent=image_policy,
                )
                self._image_rule_watermark_font.setObjectName(
                    "image_rule_watermark_font"
                )
                self._image_rule_watermark_font.set_font_name("宋体")
                watermark_row.addWidget(self._image_rule_watermark_check)
                watermark_row.addWidget(self._image_rule_watermark_fixed_radio)
                watermark_row.addWidget(self._image_rule_watermark_free_radio)
                watermark_row.addWidget(self._image_rule_watermark_edit, 1)
                image_policy_layout.addLayout(watermark_row)

                watermark_font_row = QHBoxLayout()
                watermark_font_row.addWidget(
                    self._image_rule_watermark_font_label
                )
                watermark_font_row.addWidget(self._image_rule_watermark_font)
                watermark_font_row.addStretch(1)
                image_policy_layout.addLayout(watermark_font_row)
                rules_card.add_widget(image_policy)
                for control in (
                    self._image_rule_adaptive_check,
                    self._image_rule_page_break_after_check,
                    self._image_rule_single_name_check,
                    self._image_rule_multi_name_check,
                    self._image_rule_watermark_check,
                    self._image_rule_watermark_fixed_radio,
                    self._image_rule_watermark_free_radio,
                ):
                    control.toggled.connect(self._commit_image_policy)
                self._image_rule_watermark_edit.editingFinished.connect(
                    self._commit_image_policy
                )
                self._image_rule_watermark_font.font_changed.connect(
                    self._commit_image_policy
                )

                # Non-visual contract projection retained for compatibility.
                self._image_rules_table = QTableWidget(0, 5, rules_card)
                self._image_rules_table.setObjectName("assets_image_rules_table")
                self._image_rules_table.setHorizontalHeaderLabels(
                    ("图片角色", "数量", "覆盖方式", "允许层级", "媒体类型")
                )
                self._configure_readonly_table(self._image_rules_table)
                self._image_rules_table.hide()
                self._section_layouts[section_id].addWidget(rules_card)
            card = Card(parent=page)
            if section_id == "content":
                self._content_card = card
            elif section_id == "images":
                self._image_card = card
            else:
                self._attachment_card = card
            card.set_header(title, icon_name=icon)
            if section_id == "content":
                self._add_content_material_button = QPushButton(
                    "＋ 新增文件资料",
                    card,
                )
                self._add_content_material_button.clicked.connect(
                    lambda _checked=False: self._request_add_resource_role(
                        "content",
                        "file",
                    )
                )
                apply_button_variant(
                    self._add_content_material_button,
                    "secondary",
                )
                card.add_header_action(self._add_content_material_button)
            card.add_widget(self._build_resource_tab(domain, title, parent=card))
            self._section_layouts[section_id].addWidget(card)
            self._section_layouts[section_id].addStretch(1)

        timeline_page = self._section_pages["timeline"]
        timeline_card = Card(parent=timeline_page)
        self._timeline_card = timeline_card
        timeline_card.set_header("时间计划", icon_name="chart-no-axes-gantt")
        self._timeline_add_segment_button = QPushButton(
            "＋ 新增时间段",
            timeline_card,
        )
        self._timeline_add_segment_button.clicked.connect(self._add_timeline)
        apply_button_variant(self._timeline_add_segment_button, "secondary")
        timeline_card.add_header_action(self._timeline_add_segment_button)
        timeline_card.add_widget(self._build_calculation_tab(timeline_card))
        self._section_layouts["timeline"].addWidget(timeline_card)
        self._section_layouts["timeline"].addStretch(1)

        self._setup_persistence_actions()

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self._section_nav.select_card("generate")
        self._on_section_selected("generate")
        self._reload_library()

    def _setup_persistence_actions(self) -> None:
        """Restore the classic section-header location for draft controls."""

        cards = {
            "fields": self._profile_card,
            "content": self._content_rules_card,
            "timeline": self._timeline_card,
            "images": self._image_rules_card,
            "attachments": self._attachment_card,
        }
        self._persistence_actions: dict[str, PersistenceActions] = {}
        for section_id, card in cards.items():
            actions = PersistenceActions(
                object_name_prefix=f"assets_{section_id}",
                compact=True,
                parent=card,
            )
            actions.restore_requested.connect(
                lambda section_id=section_id: self._restore_section_draft(section_id)
            )
            actions.save_requested.connect(self._save)
            card.add_header_action(actions)
            self._persistence_actions[section_id] = actions

        # Retain the former private button handles used by integrations while
        # keeping their visible owner in the editable section headers.
        field_actions = self._persistence_actions["fields"]
        self._discard_button = field_actions.restore_button
        self._save_button = field_actions.save_button

    def _refresh_persistence_actions(self, *, writable: bool) -> None:
        save_enabled = bool(writable and self._dirty)
        for section_id, actions in self._persistence_actions.items():
            actions.set_states(
                restore_enabled=bool(
                    writable and self._section_has_unsaved_changes(section_id)
                ),
                save_enabled=save_enabled,
            )

    def _section_has_unsaved_changes(self, section_id: str) -> bool:
        if self._package is None or self._snapshot is None:
            return False
        restored = self._package_with_restored_section(
            self._package,
            self._snapshot.package,
            section_id,
        )
        return restored != self._package

    def _restore_section_draft(self, section_id: str) -> bool:
        if self._package is None or self._snapshot is None:
            return False
        restored = self._package_with_restored_section(
            self._package,
            self._snapshot.package,
            section_id,
        )
        if restored == self._package:
            return False
        self._package = restored
        self._dirty = restored != self._snapshot.package
        self._refresh_editor()
        self._publish()
        label = {
            "fields": "字段资料",
            "content": "文件资料",
            "timeline": "时间计划",
            "images": "图片资料",
            "attachments": "附件资料",
        }.get(section_id, "资料")
        Toast.show_success(f"已恢复{label}到上次保存状态")
        return True

    @classmethod
    def _package_with_restored_section(
        cls,
        current: MaterialPackage,
        saved: MaterialPackage,
        section_id: str,
    ) -> MaterialPackage:
        domain = {
            "content": "content",
            "images": "image",
            "attachments": "attachment",
        }.get(section_id, "")
        relevant_roles = (
            cls._roles_for_domain(current, domain)
            | cls._roles_for_domain(saved, domain)
            if domain
            else set()
        )

        def restore_scope(
            active_scope: MaterialScope,
            saved_scope: MaterialScope,
        ) -> MaterialScope:
            if section_id == "fields":
                return MaterialScope(
                    fields=saved_scope.fields,
                    resources=active_scope.resources,
                    derivations=active_scope.derivations,
                    timelines=active_scope.timelines,
                    provenance=saved_scope.provenance,
                )
            if section_id == "timeline":
                return MaterialScope(
                    fields=active_scope.fields,
                    resources=active_scope.resources,
                    derivations=saved_scope.derivations,
                    timelines=saved_scope.timelines,
                    provenance=active_scope.provenance,
                )
            if domain:
                resources = {
                    role: binding
                    for role, binding in active_scope.resources.items()
                    if role not in relevant_roles
                }
                resources.update(
                    {
                        role: binding
                        for role, binding in saved_scope.resources.items()
                        if role in relevant_roles
                    }
                )
                return MaterialScope(
                    fields=active_scope.fields,
                    resources=resources,
                    derivations=active_scope.derivations,
                    timelines=active_scope.timelines,
                    provenance=active_scope.provenance,
                )
            return active_scope

        saved_groups = {group.group_id: group for group in saved.groups}
        groups: list[MaterialGroup] = []
        for group in current.groups:
            baseline = saved_groups.get(group.group_id)
            if baseline is None:
                groups.append(group)
                continue
            groups.append(
                MaterialGroup(
                    group_id=group.group_id,
                    display_name=(
                        baseline.display_name
                        if section_id == "fields"
                        else group.display_name
                    ),
                    scope=restore_scope(group.scope, baseline.scope),
                    metadata=group.metadata,
                )
            )

        saved_records = {record.record_id: record for record in saved.records}
        records: list[MaterialRecord] = []
        for record in current.records:
            baseline = saved_records.get(record.record_id)
            if baseline is None:
                records.append(record)
                continue
            records.append(
                clone_material_record(
                    record,
                    display_name=(
                        baseline.display_name
                        if section_id == "fields"
                        else record.display_name
                    ),
                    group_id=(baseline.group_id if section_id == "fields" else record.group_id),
                    lifecycle=(
                        baseline.lifecycle
                        if section_id == "fields"
                        else record.lifecycle
                    ),
                    scope=restore_scope(record.scope, baseline.scope),
                )
            )

        metadata = cls._metadata_with_restored_section(
            current,
            saved,
            section_id=section_id,
            domain=domain,
            relevant_roles=relevant_roles,
        )
        return clone_material_package(
            current,
            display_name=(
                saved.display_name if section_id == "fields" else current.display_name
            ),
            shared_scope=restore_scope(current.shared_scope, saved.shared_scope),
            groups=tuple(groups),
            records=tuple(records),
            metadata=metadata,
        )

    @staticmethod
    def _roles_for_domain(package: MaterialPackage, domain: str) -> set[str]:
        if not domain:
            return set()
        return {
            role.role
            for role in get_package_material_contract(package).resource_roles
            if role.domain == domain
        }

    @classmethod
    def _metadata_with_restored_section(
        cls,
        current: MaterialPackage,
        saved: MaterialPackage,
        *,
        section_id: str,
        domain: str,
        relevant_roles: set[str],
    ) -> dict[str, object]:
        metadata = dict(current.metadata)
        current_extensions = dict(
            current.metadata.get(PACKAGE_CONTRACT_EXTENSIONS_KEY, {}) or {}
        )
        saved_extensions = dict(
            saved.metadata.get(PACKAGE_CONTRACT_EXTENSIONS_KEY, {}) or {}
        )
        if section_id == "fields":
            current_extensions["fields"] = list(
                saved_extensions.get("fields", ()) or ()
            )
        elif domain:
            restored_roles = [
                dict(item)
                for item in saved_extensions.get("resource_roles", ()) or ()
                if hasattr(item, "get") and str(item.get("domain", "")) == domain
            ]
            restored_iterator = iter(restored_roles)
            merged_roles: list[dict[str, object]] = []
            for item in current_extensions.get("resource_roles", ()) or ():
                if not hasattr(item, "get"):
                    continue
                if str(item.get("domain", "")) != domain:
                    merged_roles.append(dict(item))
                    continue
                replacement = next(restored_iterator, None)
                if replacement is not None:
                    merged_roles.append(replacement)
            merged_roles.extend(restored_iterator)
            current_extensions["resource_roles"] = merged_roles
            if section_id == "images":
                current_extensions["image_policy"] = dict(
                    saved_extensions.get("image_policy", {}) or {}
                )
            elif section_id == "content":
                if "content_policy" in saved_extensions:
                    current_extensions["content_policy"] = dict(
                        saved_extensions.get("content_policy", {}) or {}
                    )
                else:
                    current_extensions.pop("content_policy", None)
        if section_id == "fields" or domain:
            if (
                any(bool(value) for value in current_extensions.values())
                or PACKAGE_CONTRACT_EXTENSIONS_KEY in saved.metadata
            ):
                metadata[PACKAGE_CONTRACT_EXTENSIONS_KEY] = current_extensions
            else:
                metadata.pop(PACKAGE_CONTRACT_EXTENSIONS_KEY, None)

        if domain:
            source_key = "material_resource_authoring_sources"
            current_sources = dict(current.metadata.get(source_key, {}) or {})
            saved_sources = dict(saved.metadata.get(source_key, {}) or {})
            sources = {
                role: value
                for role, value in current_sources.items()
                if role not in relevant_roles
            }
            sources.update(
                {
                    role: value
                    for role, value in saved_sources.items()
                    if role in relevant_roles
                }
            )
            if sources:
                metadata[source_key] = sources
            else:
                metadata.pop(source_key, None)
        return metadata

    def _build_resource_tab(
        self,
        domain: str,
        title: str,
        *,
        parent: QWidget | None = None,
    ) -> QWidget:
        tab = QWidget(parent or self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # The table is now an internal V1 projection.  The visible controls
        # below intentionally follow the former token-row presenters.
        table = QTableWidget(0, 5, tab)
        table.setObjectName(f"material_{domain}_table")
        table.setHorizontalHeaderLabels(
            ("资料角色", "要求", "当前层文件", "生效来源", "状态")
        )
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table.hide()
        self._resource_tables[domain] = table

        add_button = QPushButton("添加或替换文件", tab)
        add_button.clicked.connect(
            lambda _checked=False, selected_domain=domain: self._bind_resource(
                selected_domain
            )
        )
        apply_button_variant(add_button, "secondary")
        open_button = QPushButton("打开文件", tab)
        open_button.clicked.connect(
            lambda _checked=False, selected_domain=domain: self._open_resource(
                selected_domain
            )
        )
        apply_button_variant(open_button, "secondary")
        remove_button = QPushButton("移除当前层", tab)
        remove_button.clicked.connect(
            lambda _checked=False, selected_domain=domain: self._remove_resource(
                selected_domain
            )
        )
        apply_button_variant(remove_button, "ghost-danger")
        add_button.hide()
        open_button.hide()
        remove_button.hide()
        self._resource_action_buttons[domain] = (
            add_button,
            open_button,
            remove_button,
        )

        if domain == "content":
            empty = QLabel("暂无文件资料，点击右上角新增。", tab)
            empty.setObjectName("material_hint")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            self._resource_empty_labels[(domain, "all")] = empty
            rows = QWidget(tab)
            rows_layout = QVBoxLayout(rows)
            rows_layout.setContentsMargins(0, 0, 0, 0)
            rows_layout.setSpacing(0)
            layout.addWidget(rows)
            self._resource_section_layouts[(domain, "all")] = rows_layout
            return tab

        sections = (
            (
                ("single", "单图", "＋ 新增单图", "图片来源", "file"),
                (
                    "folder",
                    "多图文件夹",
                    "＋ 新增多图文件夹",
                    "文件夹来源",
                    "directory",
                ),
            )
            if domain == "image"
            else (
                (
                    "single",
                    "独立附件",
                    "＋ 新增独立附件",
                    "附件来源",
                    "file",
                ),
                (
                    "folder",
                    "附件文件夹",
                    "＋ 新增附件文件夹",
                    "文件夹来源",
                    "directory",
                ),
            )
        )
        for index, (
            section_id,
            section_title,
            add_text,
            source_text,
            source_kind,
        ) in enumerate(sections):
            if index:
                separator = QFrame(tab)
                separator.setObjectName("asset_section_separator")
                separator.setFrameShape(QFrame.NoFrame)
                separator.setMinimumHeight(1)
                separator.setMaximumHeight(1)
                layout.addWidget(separator)
                gap = QWidget(tab)
                gap.setMinimumHeight(10)
                gap.setMaximumHeight(10)
                layout.addWidget(gap)
            header = TokenSectionHeader(
                section_title,
                add_text=add_text,
                parent=tab,
            )
            header.add_button.clicked.connect(
                lambda _checked=False, selected_domain=domain, selected_kind=source_kind: (
                    self._request_add_resource_role(
                        selected_domain,
                        selected_kind,
                    )
                )
            )
            layout.addWidget(header)
            self._resource_section_headers[(domain, section_id)] = header

            body = QWidget(tab)
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(0)
            guide = AssetColumnGuide(
                source_text=source_text,
                action_count=6 if source_kind == "directory" else 5,
                parent=body,
            )
            guide.metrics_changed.connect(
                lambda metrics, selected_domain=domain, selected_section=section_id: (
                    self._apply_legacy_resource_metrics(
                        selected_domain,
                        selected_section,
                        metrics,
                    )
                )
            )
            body_layout.addWidget(guide)
            self._resource_column_guides[(domain, section_id)] = guide
            empty = QLabel(f"暂无{section_title}", body)
            empty.setObjectName("material_hint")
            body_layout.addWidget(empty)
            self._resource_empty_labels[(domain, section_id)] = empty
            rows = QWidget(body)
            rows_layout = QVBoxLayout(rows)
            rows_layout.setContentsMargins(0, 6, 0, 0)
            rows_layout.setSpacing(0)
            body_layout.addWidget(rows)
            self._resource_section_layouts[(domain, section_id)] = rows_layout
            layout.addWidget(body)
        return tab

    def _build_calculation_tab(
        self,
        parent: QWidget | None = None,
    ) -> QWidget:
        tab = QWidget(parent or self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        self._timeline_empty_label = QLabel(
            "暂无时间段，点击右上角新增。",
            tab,
        )
        self._timeline_empty_label.setObjectName("material_hint")
        layout.addWidget(self._timeline_empty_label)
        self._timeline_segments_container = QWidget(tab)
        self._timeline_segments_container.setObjectName("timeline_segments_container")
        self._timeline_segments_layout = QVBoxLayout(self._timeline_segments_container)
        self._timeline_segments_layout.setContentsMargins(0, 0, 0, 0)
        self._timeline_segments_layout.setSpacing(14)
        layout.addWidget(self._timeline_segments_container)

        # Hidden projections preserve the command/test surface while the
        # visible editor uses the retained segmented layout.
        self._add_derivation_button = QPushButton("添加计算", tab)
        self._add_derivation_button.clicked.connect(self._add_derivation)
        self._remove_derivation_button = QPushButton("移除", tab)
        self._remove_derivation_button.clicked.connect(self._remove_derivation)
        self._derivations = QTableWidget(0, 4, tab)
        self._derivations.setHorizontalHeaderLabels(
            ("输出字段", "规则", "输入字段", "参数")
        )
        self._configure_readonly_table(self._derivations)
        self._add_timeline_button = QPushButton("添加日期节点", tab)
        self._add_timeline_button.clicked.connect(self._add_timeline)
        self._remove_timeline_button = QPushButton("移除", tab)
        self._remove_timeline_button.clicked.connect(self._remove_timeline)
        self._timelines = QTableWidget(0, 4, tab)
        self._timelines.setHorizontalHeaderLabels(
            ("输出字段", "基准日期", "偏移天数", "规则")
        )
        self._configure_readonly_table(self._timelines)
        for widget in (
            self._add_derivation_button,
            self._remove_derivation_button,
            self._derivations,
            self._add_timeline_button,
            self._remove_timeline_button,
            self._timelines,
        ):
            widget.hide()
        return tab

    def _build_check_tab(
        self,
        parent: QWidget | None = None,
    ) -> QWidget:
        tab = QWidget(parent or self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        self._check_summary = QLabel("", tab)
        self._check_summary.setObjectName("material_check_summary")
        self._check_summary.setWordWrap(True)
        layout.addWidget(self._check_summary)
        self._issues = QTableWidget(0, 3, tab)
        self._issues.setHorizontalHeaderLabels(("级别", "位置", "问题"))
        self._configure_readonly_table(self._issues)
        self._issues.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeToContents,
        )
        self._issues.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeToContents,
        )
        self._issues.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self._issues, 1)
        return tab

    @staticmethod
    def _configure_readonly_table(table: QTableWidget) -> None:
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for column in range(table.columnCount()):
            table.horizontalHeader().setSectionResizeMode(
                column,
                QHeaderView.Stretch,
            )

    def _apply_theme(self) -> None:
        theme = get_theme()
        if hasattr(self, "_shell"):
            self._shell.apply_theme(theme)
        self.setStyleSheet(
            f"""
            QWidget#AssetsPanel {{
                background: {theme.bg_window};
                color: {theme.text_primary};
            }}
            QStackedWidget#assets_detail_stack {{
                background: {theme.bg_window};
                border: none;
            }}
            QLabel#material_mode_badge {{
                color: {theme.primary};
                background: {theme.primary_light};
                border-radius: {theme.radius_sm}px;
                padding: 4px 9px;
                font-weight: 700;
            }}
            QLabel#material_status {{
                color: {theme.text_secondary};
                font-weight: 700;
            }}
            QLabel#material_hint {{
                color: {theme.text_secondary};
                padding: 2px 0 6px 0;
            }}
            QLabel#material_source_banner {{
                background: {theme.info_bg};
                color: {theme.text_primary};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 10px;
            }}
            QFrame#timeline_segment_header {{
                background: transparent;
                border: 1px solid transparent;
                border-left: 3px solid transparent;
                border-radius: {theme.radius_sm}px;
            }}
            QFrame#timeline_segment_header:hover {{
                background: {theme.bg_hover};
                border-left-color: {theme.primary};
            }}
            QLabel#material_overview_summary,
            QLabel#material_check_summary {{
                background: transparent;
                color: {theme.text_primary};
                border: none;
                padding: 4px 0;
            }}
            QListWidget, QTableWidget {{
                background: {theme.bg_card};
                alternate-background-color: {theme.bg_window};
                color: {theme.text_primary};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                gridline-color: {theme.divider};
                selection-background-color: {theme.bg_selected};
                selection-color: {theme.text_primary};
            }}
            QHeaderView::section {{
                background: {theme.bg_window};
                color: {theme.text_secondary};
                border: none;
                border-bottom: 1px solid {theme.border};
                padding: 8px;
                font-weight: 700;
            }}
            {build_token_row_stylesheet(theme)}
            {build_checkbox_stylesheet(
                theme,
                selector="QWidget#image_global_rules QCheckBox",
            )}
            {build_text_input_stylesheet(theme, selector="QLineEdit")}
            {build_button_stylesheet(theme)}
            """
        )
        for page in getattr(self, "_section_pages", {}).values():
            page.setStyleSheet(
                f"QWidget#{page.objectName()} {{ "
                f"background: {theme.bg_window}; border: none; }}"
            )

    def _connect_signals(self) -> None:
        self.bridge.work_mode_changed.connect(self._on_work_mode_changed)
        self._section_nav.card_selected.connect(self._on_section_selected)

    def _on_section_selected(self, section_id: str) -> None:
        page = self._section_pages.get(section_id)
        if page is None:
            return
        self._active_section_id = section_id
        self._detail_stack.setCurrentWidget(page)
        self._detail_geometry.set_active_widget(page)
        self._detail_geometry.sync_now(page)
        self._detail_scroll.verticalScrollBar().setValue(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "_section_nav"):
            return
        theme = get_theme()
        panel_width = max(0, self.width())
        nav_width = theme.master_detail_nav_width
        margin_x = theme.master_detail_margin_x
        if panel_width and panel_width < 760:
            nav_width = min(nav_width, max(176, int(panel_width * 0.42)))
            margin_x = 16
        elif panel_width and panel_width < 960:
            nav_width = min(nav_width, 230)
            margin_x = 22
        self._section_nav.setFixedWidth(nav_width)
        self._detail_layout.setContentsMargins(
            margin_x,
            theme.master_detail_margin_top,
            margin_x,
            theme.master_detail_margin_bottom,
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._dirty or self._updating or not hasattr(self, "_package_combo"):
            return
        has_persisted_choice, preferred = self._persisted_package_choice()
        if not has_persisted_choice:
            return
        current = str(self._package_combo.currentData() or "").strip()
        if preferred != current:
            self._reload_library(preferred)

    def _on_work_mode_changed(self, _emitted_mode) -> None:
        # A failed mode activation can synchronously roll Bridge back while
        # Qt is still dispatching the original signal.  Always project the
        # authoritative post-callback state, never the stale signal payload.
        mode = self.bridge.current_work_mode()
        mode_id = str(getattr(mode, "mode_id", "") or "").strip()
        if mode_id == self._mode_id:
            return
        self._mode_id = mode_id
        self._mode_label.setText(str(getattr(mode, "label", self._mode_id)))
        self._reload_library()

    def _persisted_package_choice(self) -> tuple[bool, str]:
        store = self.bridge.workspace_preference_store()
        if store is None:
            return False, ""
        preference = store.load().for_mode(self._mode_id)
        if preference is None or not preference.material_selection_configured:
            return False, ""
        package_id = str(preference.material_package_id or "").strip()
        return True, package_id if preference.material_enabled else ""

    def _persist_package_choice(self, package_id: str) -> None:
        store = self.bridge.workspace_preference_store()
        if store is None:
            return
        identity = str(package_id or "").strip()
        try:
            store.update_mode(
                self._mode_id,
                material_enabled=bool(identity),
                material_package_id=identity,
            )
        except (OSError, TypeError, ValueError) as exc:
            logger.warning(
                "Could not persist current material package: %s",
                exc,
                exc_info=exc,
            )

    def _reload_library(self, preferred_id: str | None = None) -> None:
        self._updating = True
        selected_unavailable = False
        try:
            entries = list_material_package_entries(mode_id=self._mode_id)
            self._package_combo.clear()
            self._package_combo.addItem("不使用资料包", "")
            for entry in entries:
                origin = "内置" if entry.source_type == "builtin" else "我的"
                item_index = self._package_combo.count()
                self._package_combo.addItem(
                    f"{entry.display_name}  ·  {origin}",
                    entry.package_id,
                )
                if not entry.is_available:
                    item = self._package_combo.model().item(item_index)
                    if item is not None:
                        item.setEnabled(False)
                    self._package_combo.setItemData(
                        item_index,
                        entry.load_error or "该资料包当前无法读取。",
                        Qt.ToolTipRole,
                    )

            if preferred_id is None:
                has_persisted_choice, preferred = self._persisted_package_choice()
            else:
                has_persisted_choice = True
                preferred = str(preferred_id or "").strip()
            if not has_persisted_choice:
                default = default_material_package_entry(
                    mode_id=self._mode_id,
                    entries=entries,
                )
                preferred = default.package_id if default is not None else ""
            index = self._package_combo.findData(preferred)
            if preferred and index < 0:
                index = self._package_combo.count()
                self._package_combo.addItem(
                    "原资料包（不可用）  ·  失效",
                    preferred,
                )
                item = self._package_combo.model().item(index)
                if item is not None:
                    item.setEnabled(False)
                self._package_combo.setItemData(
                    index,
                    (
                        "已保存的资料包不存在或无法读取："
                        f"{preferred}。请选择其他资料包，或明确选择“不使用资料包”。"
                    ),
                    Qt.ToolTipRole,
                )
                selected_unavailable = True
            elif index >= 0:
                entry = next(
                    (item for item in entries if item.package_id == preferred),
                    None,
                )
                selected_unavailable = bool(entry and not entry.is_available)
            self._package_combo.setCurrentIndex(max(0, index))
        finally:
            self._updating = False
        self._load_selected_package(persist_selection=not selected_unavailable)

    def _on_package_changed(self, _index: int) -> None:
        if self._updating:
            return
        current_id = self._entry.package_id if self._entry is not None else ""
        target_id = str(self._package_combo.currentData() or "")
        if self._dirty and target_id != current_id:
            action = self._prompt_pending_material_action("切换资料包")
            if action == "cancel" or (action == "save" and not self._save()):
                self._updating = True
                try:
                    self._package_combo.setCurrentIndex(
                        max(0, self._package_combo.findData(current_id))
                    )
                finally:
                    self._updating = False
                return
        self._load_selected_package()

    def _clear_loaded_package(self) -> None:
        self._entry = None
        self._snapshot = None
        self._package = None
        self._dirty = False
        self._selected_record_ids = ()
        self._current_record_id = ""

    def _load_selected_package(self, *, persist_selection: bool = True) -> None:
        package_id = str(self._package_combo.currentData() or "")
        if not package_id:
            self._clear_loaded_package()
            self._refresh_editor()
            self._publish()
            if persist_selection:
                self._persist_package_choice("")
            return
        entry = next(
            (
                item
                for item in list_material_package_entries(mode_id=self._mode_id)
                if item.package_id == package_id
            ),
            None,
        )
        if entry is None:
            self._clear_loaded_package()
            self._refresh_editor()
            issue = MaterialIssue(
                code="material.package.not_found",
                message="原资料包已不存在；已保留原选择，请重新选择或明确停用。",
            )
            self._show_issues((issue,))
            self.bridge.set_current_material_package_ref(None)
            self.bridge.set_current_material_preview_snapshot(None)
            self.bridge.set_current_material_run_selection(None)
            return
        try:
            snapshot = load_material_package_entry(entry)
            contract = get_package_material_contract(snapshot.package)
            if contract.contract_id != snapshot.package.material_contract_id:
                raise ValueError("material_contract_identity_mismatch")
        except Exception as exc:
            self._clear_loaded_package()
            self._refresh_editor()
            self._show_exception("material.package.load_failed", exc)
            self.bridge.set_current_material_package_ref(None)
            self.bridge.set_current_material_preview_snapshot(None)
            self.bridge.set_current_material_run_selection(None)
            return
        self._entry = entry
        self._snapshot = snapshot
        self._package = snapshot.package
        self._dirty = False
        active_ids = tuple(
            item.record_id
            for item in snapshot.package.records
            if item.lifecycle == "active"
        )
        self._selected_record_ids = active_ids
        self._current_record_id = (
            active_ids[0]
            if active_ids
            else (
                snapshot.package.records[0].record_id
                if snapshot.package.records
                else ""
            )
        )
        self._refresh_editor()
        self._publish()
        if persist_selection:
            self._persist_package_choice(package_id)

    def _refresh_editor(self) -> None:
        self._updating = True
        try:
            package = self._package
            enabled = package is not None
            writable = bool(self._entry and self._entry.source_type == "user")
            self._package_name.setEnabled(writable)
            self._refresh_persistence_actions(writable=writable)
            self._delete_button.setEnabled(writable)
            self._duplicate_button.setEnabled(enabled)
            self._rename_package_button.setEnabled(writable)
            self._open_package_folder_button.setEnabled(enabled)
            self._add_material_field_button.setEnabled(writable)
            self._add_floating_material_field_button.setEnabled(writable)
            self._add_content_material_button.setEnabled(writable)
            self._timeline_add_segment_button.setEnabled(writable)
            for header in self._resource_section_headers.values():
                header.add_button.setEnabled(writable)
            for button in (
                self._add_record_button,
                self._remove_record_button,
                self._add_group_button,
                self._rename_group_button,
                self._remove_group_button,
                self._clear_field_button,
                self._add_derivation_button,
                self._remove_derivation_button,
                self._add_timeline_button,
                self._remove_timeline_button,
            ):
                button.setEnabled(writable)
            for buttons in self._resource_action_buttons.values():
                buttons[0].setEnabled(writable)
                buttons[1].setEnabled(enabled)
                buttons[2].setEnabled(writable)
            self._package_name.setText(package.display_name if package else "")
            self._records.clear()
            if package is not None:
                for record in package.records:
                    item = QListWidgetItem(record.display_name)
                    item.setData(Qt.UserRole, record.record_id)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(
                        Qt.Checked
                        if record.record_id in self._selected_record_ids
                        else Qt.Unchecked
                    )
                    if record.lifecycle != "active":
                        item.setCheckState(Qt.Unchecked)
                    self._records.addItem(item)
                    if record.record_id == self._current_record_id:
                        self._records.setCurrentItem(item)
            self._refresh_record_editor()
        finally:
            self._updating = False
        self._refresh_persistence_actions(
            writable=bool(self._entry and self._entry.source_type == "user")
        )
        self._status.setText(
            "有未保存修改"
            if self._dirty
            else (
                "内置 · 只读"
                if self._entry and self._entry.source_type == "builtin"
                else ("我的 · 已保存" if self._entry else "未选择资料包")
            )
        )

    def _refresh_record_editor(self) -> None:
        package = self._package
        record = package.get_record(self._current_record_id) if package else None
        preferred_scope = self._selected_scope() if self._scope.count() else None
        writable = bool(self._entry and self._entry.source_type == "user")
        self._record_name.setEnabled(writable and record is not None)
        self._lifecycle.setEnabled(writable and record is not None)
        self._record_group.setEnabled(writable and record is not None)
        self._record_name.setText(record.display_name if record else "")
        self._lifecycle.setCurrentIndex(
            max(0, self._lifecycle.findData(record.lifecycle if record else "draft"))
        )
        self._record_group.clear()
        self._record_group.addItem("无分组", "")
        if package is not None:
            for group in package.groups:
                self._record_group.addItem(group.display_name, group.group_id)
        self._record_group.setCurrentIndex(
            max(0, self._record_group.findData(record.group_id if record else ""))
        )
        self._scope.clear()
        self._scope.addItem("资料包共享", ("shared", ""))
        if package is not None:
            for group in package.groups:
                self._scope.addItem(
                    f"分组 · {group.display_name}",
                    ("group", group.group_id),
                )
        if record is not None:
            self._scope.addItem(
                f"记录 · {record.display_name}",
                ("record", record.record_id),
            )
        scope_index = (
            self._scope.findData(preferred_scope) if preferred_scope is not None else -1
        )
        if scope_index < 0 and record is not None:
            scope_index = self._scope.findData(("record", record.record_id))
        self._scope.setCurrentIndex(max(0, scope_index))
        self._refresh_scope_views()

    def _refresh_scope_views(self, _index: int = -1) -> None:
        self._refresh_fields()
        self._refresh_resources()
        self._refresh_calculations()
        self._refresh_check()
        self._refresh_overview()

    def _refresh_fields(self) -> None:
        package = self._package
        was_updating = self._updating
        self._updating = True
        try:
            self._clear_legacy_field_rows()
            self._fields.setRowCount(0)
            if package is None:
                self._fixed_field_count.setText("0 项")
                self._floating_field_count.setText("0 项")
                self._empty_fixed_fields_label.setVisible(True)
                self._empty_floating_fields_label.setVisible(True)
                self._empty_fields_label.setVisible(False)
                return
            contract = get_package_material_contract(package)
            managed_timeline_fields = self._timeline_managed_field_keys(package)
            visible_fields = tuple(
                field
                for field in contract.fields
                if field.key not in managed_timeline_fields
            )
            owner_scope, owner_id = self._selected_scope()
            scope = self._scope_object(owner_scope, owner_id)
            self._fields.setRowCount(len(visible_fields))
            current_record = package.get_record(self._current_record_id)
            resolution = (
                None
                if current_record is None
                else self._resolved_record(current_record.record_id)
            )
            for row, field in enumerate(visible_fields):
                label = QTableWidgetItem(field.label)
                key = QTableWidgetItem(f"{{{{@text:{field.key}}}}}")
                key.setData(Qt.UserRole, field.key)
                value = QTableWidgetItem(str(scope.fields.get(field.key, "")))
                owner = QTableWidgetItem(
                    str(
                        resolution.record.field_owners.get(field.key, "")
                        if resolution and resolution.record
                        else ""
                    )
                )
                for fixed in (label, key, owner):
                    fixed.setFlags(fixed.flags() & ~Qt.ItemIsEditable)
                if (
                    not self._entry
                    or self._entry.source_type != "user"
                    or owner_scope not in field.allowed_scopes
                ):
                    value.setFlags(value.flags() & ~Qt.ItemIsEditable)
                self._fields.setItem(row, 0, label)
                self._fields.setItem(row, 1, key)
                self._fields.setItem(row, 2, value)
                self._fields.setItem(row, 3, owner)
            self._rebuild_legacy_field_rows(
                visible_fields,
                scope=scope,
                owner_scope=owner_scope,
                writable=bool(self._entry and self._entry.source_type == "user"),
            )
        finally:
            self._updating = was_updating

    def _clear_legacy_field_rows(self) -> None:
        for key, row in self._legacy_field_rows.items():
            layout = (
                self._floating_fields_layout
                if self._legacy_field_scopes.get(key) == "floating"
                else self._legacy_fields_layout
            )
            layout.removeWidget(row)
            # Do not detach a live QWidget: on Windows that promotes it to a
            # native top-level ``pythonw`` window until deferred deletion.
            row.hide()
            row.deleteLater()
        self._legacy_field_rows.clear()
        self._legacy_field_scopes.clear()

    @staticmethod
    def _timeline_managed_field_keys(
        package: MaterialPackage,
    ) -> set[str]:
        managed: set[str] = set()
        scopes = (
            package.shared_scope,
            *(group.scope for group in package.groups),
            *(record.scope for record in package.records),
        )
        for scope in scopes:
            for output, specification in scope.timelines.items():
                if specification.preset_id != "timeline_ratio":
                    continue
                managed.add(output)
                managed.add(specification.anchor_field)
                end_field = str(specification.parameters.get("end_field", ""))
                if end_field:
                    managed.add(end_field)
        return managed

    def _rebuild_legacy_field_rows(
        self,
        fields,
        *,
        scope,
        owner_scope: str,
        writable: bool,
    ) -> None:
        custom_keys = self._custom_field_keys()
        grouped = {
            "fixed": [
                field
                for field in fields
                if package_material_field_value_source(self._package, field.key)
                != "floating"
            ],
            "floating": [
                field
                for field in fields
                if package_material_field_value_source(self._package, field.key)
                == "floating"
            ],
        }
        for field_scope, scoped_fields in grouped.items():
            container = (
                self._floating_fields_container
                if field_scope == "floating"
                else self._legacy_fields_container
            )
            layout = (
                self._floating_fields_layout
                if field_scope == "floating"
                else self._legacy_fields_layout
            )
            for index, field in enumerate(scoped_fields, start=1):
                value = (
                    ""
                    if field_scope == "floating"
                    else str(scope.fields.get(field.key, ""))
                )
                row = LegacyFieldTokenRow(
                    index=index,
                    key=field.key,
                    value=value,
                    custom=field.key in custom_keys,
                    writable=writable,
                    value_writable=(
                        writable
                        and field_scope == "fixed"
                        and owner_scope in field.allowed_scopes
                    ),
                    definition_writable=writable and field.key in custom_keys,
                    value_placeholder=(
                        "在工作台填写"
                        if field_scope == "floating"
                        else "填写字段内容"
                    ),
                    parent=container,
                )
                row.value_committed.connect(self._commit_legacy_field_value)
                row.token_renamed.connect(self._rename_legacy_field_definition)
                row.clear_requested.connect(self._clear_legacy_field_value)
                row.add_requested.connect(self._add_field_series)
                row.remove_requested.connect(self._remove_legacy_field_definition)
                layout.addWidget(row)
                self._legacy_field_rows[field.key] = row
                self._legacy_field_scopes[field.key] = field_scope
                apply_token_row_style(
                    row,
                    object_name="material_v1_field_token_row",
                    is_last=index == len(scoped_fields),
                )
        fixed_count = len(grouped["fixed"])
        floating_count = len(grouped["floating"])
        self._fixed_field_count.setText(f"{fixed_count} 项")
        self._floating_field_count.setText(f"{floating_count} 项")
        self._empty_fixed_fields_label.setVisible(not fixed_count)
        self._empty_floating_fields_label.setVisible(not floating_count)
        self._empty_fields_label.setVisible(False)
        self._apply_legacy_field_metrics(
            self._field_column_guide.metrics(),
            "fixed",
        )
        self._apply_legacy_field_metrics(
            self._floating_field_column_guide.metrics(),
            "floating",
        )

    def _apply_legacy_field_metrics(self, metrics, scope: str = "") -> None:
        for key, row in self._legacy_field_rows.items():
            if scope and self._legacy_field_scopes.get(key) != scope:
                continue
            row.apply_metrics(metrics)

    def _custom_field_keys(self) -> set[str]:
        extensions = self._package_contract_extensions()
        return {
            str(item.get("key", ""))
            for item in extensions.get("fields", ())
            if hasattr(item, "get") and str(item.get("key", "")).strip()
        }

    def _request_add_field_definition(self, value_source: str = "fixed") -> None:
        if not self._is_user_package():
            return
        normalized_source = (
            "floating" if value_source == "floating" else "fixed"
        )
        key = self._next_field_definition_name(normalized_source)
        result = self._service().add_field_definition(
            self._package,
            key=key,
            label=key,
            value_source=normalized_source,
        )
        self._apply_result(result)

    def _add_field_series(self, key: str) -> None:
        self._request_add_field_definition(
            self._legacy_field_scopes.get(key, "fixed")
        )

    def _next_field_definition_name(self, value_source: str = "fixed") -> str:
        existing = {
            field.key for field in get_package_material_contract(self._package).fields
        }
        prefix = "自由字段" if value_source == "floating" else "固定字段"
        index = 1
        while f"{prefix}{index}" in existing:
            index += 1
        return f"{prefix}{index}"

    def _commit_legacy_field_value(self, key: str, value: str) -> None:
        if self._updating or not self._is_user_package():
            return
        owner_scope, owner_id = self._selected_scope()
        self._apply_result(
            self._service().set_field(
                self._package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=key,
                value=value,
                provenance="manual",
            )
        )

    def _clear_legacy_field_value(self, key: str) -> None:
        if not self._is_user_package():
            return
        owner_scope, owner_id = self._selected_scope()
        self._apply_result(
            self._service().remove_field(
                self._package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=key,
            )
        )

    def _rename_legacy_field_definition(
        self,
        current_key: str,
        key: str,
    ) -> None:
        if not self._is_user_package():
            return
        normalized = self._normalize_token_identifier(key)
        if not normalized or normalized == current_key:
            return
        self._apply_result(
            self._service().rename_field_definition(
                self._package,
                current_key=current_key,
                key=normalized,
                label=normalized,
            )
        )

    def _remove_legacy_field_definition(self, key: str) -> None:
        if not self._is_user_package():
            return
        if not confirm(
            "删除字段",
            f"删除 {{@text:{key}}} 及其所有层级中的值和计算规则？",
            confirm_text="删除字段",
            destructive=True,
            parent=self,
        ):
            return
        self._apply_result(
            self._service().remove_field_definition(
                self._package,
                key=key,
            )
        )

    def _refresh_resources(self) -> None:
        package = self._package
        self._clear_legacy_resource_rows()
        for table in self._resource_tables.values():
            table.setRowCount(0)
        self._image_rules_table.setRowCount(0)
        self._refresh_content_policy_controls()
        self._refresh_image_policy_controls()
        if package is None:
            self._refresh_resource_empty_states()
            return
        contract = get_package_material_contract(package)
        self._refresh_image_rules(contract)
        owner_scope, owner_id = self._selected_scope()
        scope = self._scope_object(owner_scope, owner_id)
        current_record = package.get_record(self._current_record_id)
        resolution = (
            self._resolved_record(current_record.record_id)
            if current_record is not None
            else None
        )
        resolved = resolution.record if resolution is not None else None
        writable = bool(self._entry and self._entry.source_type == "user")
        for domain, table in self._resource_tables.items():
            roles = tuple(
                role for role in contract.resource_roles if role.domain == domain
            )
            table.setRowCount(len(roles))
            for row, role in enumerate(roles):
                binding = scope.resources.get(role.role)
                effective_items = (
                    resolved.resources.get(role.role, ()) if resolved else ()
                )
                effective_owners = (
                    resolved.resource_owners.get(role.role, ()) if resolved else ()
                )
                namespace = {
                    "content": "file",
                    "image": "img",
                    "attachment": "attach",
                }[domain]
                role_item = QTableWidgetItem(
                    f"{role.label}\n{{{{@{namespace}:{role.role}}}}}"
                )
                role_item.setData(Qt.UserRole, role.role)
                requirement = (
                    f"{'必需' if role.required else '可选'} · "
                    f"{role.min_items}–"
                    f"{role.max_items if role.max_items is not None else '不限'} 个"
                )
                current_files = (
                    "\n".join(item.original_name for item in binding.items)
                    if binding and binding.items
                    else "—"
                )
                count = len(effective_items)
                within_max = role.max_items is None or count <= role.max_items
                status = (
                    f"正常 · {count} 个"
                    if count >= role.min_items and within_max
                    else f"需处理 · {count} 个"
                )
                values = (
                    role_item,
                    QTableWidgetItem(requirement),
                    QTableWidgetItem(current_files),
                    QTableWidgetItem(" → ".join(effective_owners) or "—"),
                    QTableWidgetItem(status),
                )
                for column, item in enumerate(values):
                    table.setItem(row, column, item)
                table.setRowHeight(row, 48)
            if roles and table.currentRow() < 0:
                table.selectRow(0)
            buttons = self._resource_action_buttons[domain]
            scope_allowed = bool(
                roles and any(owner_scope in role.allowed_scopes for role in roles)
            )
            buttons[0].setEnabled(writable and scope_allowed)
            buttons[1].setEnabled(bool(roles and resolved))
            buttons[2].setEnabled(writable and scope_allowed)
        self._rebuild_legacy_resource_rows(
            contract,
            scope=scope,
            resolved=resolved,
            writable=writable,
        )

    def _refresh_image_rules(self, contract) -> None:
        table = self._image_rules_table
        roles = tuple(
            role for role in contract.resource_roles if role.domain == "image"
        )
        table.setRowCount(len(roles))
        scope_labels = {
            "shared": "资料包",
            "group": "分组",
            "record": "记录",
            "run": "运行时",
        }
        for row, role in enumerate(roles):
            maximum = role.max_items if role.max_items is not None else "不限"
            values = (
                role.label,
                f"{role.min_items}–{maximum}",
                "追加" if role.merge_policy == "append" else "下层替换上层",
                "、".join(
                    scope_labels.get(scope, scope) for scope in role.allowed_scopes
                ),
                "、".join(role.accepted_media_types) or "受支持图片格式",
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(str(value)))
            table.setRowHeight(row, 40)

    def _clear_legacy_resource_rows(self) -> None:
        for domain_rows in self._legacy_resource_rows.values():
            for row in domain_rows.values():
                layout = self._resource_section_layouts.get(
                    (row.property("materialDomain"), row.property("materialSection"))
                )
                if layout is not None:
                    layout.removeWidget(row)
                row.hide()
                row.deleteLater()
            domain_rows.clear()

    def _rebuild_legacy_resource_rows(
        self,
        contract,
        *,
        scope,
        resolved,
        writable: bool,
    ) -> None:
        custom_roles = self._custom_resource_roles()
        owner_scope, owner_id = self._selected_scope()
        section_counts: dict[tuple[str, str], int] = {
            key: 0 for key in self._resource_section_layouts
        }
        for domain in ("content", "image", "attachment"):
            roles = tuple(
                item for item in contract.resource_roles if item.domain == domain
            )
            for role_contract in roles:
                section_id = self._resource_section_for_role(
                    domain,
                    role_contract,
                )
                section_key = (domain, section_id)
                layout = self._resource_section_layouts[section_key]
                binding = scope.resources.get(role_contract.role)
                effective_items = (
                    tuple(resolved.resources.get(role_contract.role, ()))
                    if resolved is not None
                    else ()
                )
                visible_items = (
                    tuple(binding.items)
                    if binding is not None and binding.items
                    else effective_items
                )
                display_name = visible_items[0].original_name if visible_items else ""
                source_paths = self._resource_source_paths(visible_items)
                source_text = self._resource_source_text(visible_items)
                authoring_source = self._resource_authoring_source(
                    owner_scope,
                    owner_id,
                    role_contract.role,
                )
                if authoring_source is not None:
                    source_text = str(authoring_source)
                custom = role_contract.role in custom_roles
                section_index = section_counts[section_key] + 1
                if domain == "content":
                    row = LegacyContentTokenRow(
                        index=section_index,
                        role=role_contract.role,
                        namespace=MaterialTokenNamespace.FILE,
                        display_name=display_name,
                        source_text=source_text,
                        custom=custom,
                        writable=writable,
                        parent=layout.parentWidget(),
                    )
                elif domain == "image":
                    row_type = (
                        LegacyImageGroupTokenRow
                        if section_id == "folder"
                        else LegacySingleImageTokenRow
                    )
                    row = row_type(
                        index=section_index,
                        role=role_contract.role,
                        namespace=(
                            MaterialTokenNamespace.IMAGE
                            if domain == "image"
                            else MaterialTokenNamespace.ATTACHMENT
                        ),
                        label=role_contract.label,
                        display_name=display_name,
                        source_text=source_text,
                        custom=custom,
                        writable=writable,
                        folder_items=tuple(
                            item.original_name for item in visible_items
                        ),
                        preview_path=(source_paths[0] if source_paths else ""),
                        parent=layout.parentWidget(),
                    )
                    row.label_committed.connect(
                        lambda role_name, label, selected_domain=domain: (
                            self._rename_resource_label(
                                selected_domain,
                                role_name,
                                label,
                            )
                        )
                    )
                else:
                    row = LegacyAssetTokenRow(
                        index=section_index,
                        role=role_contract.role,
                        namespace=MaterialTokenNamespace.ATTACHMENT,
                        label=role_contract.label,
                        display_name=display_name,
                        source_text=source_text,
                        custom=custom,
                        writable=writable,
                        folder=section_id == "folder",
                        folder_items=tuple(
                            item.original_name for item in visible_items
                        ),
                        parent=layout.parentWidget(),
                    )
                    row.label_committed.connect(
                        lambda role_name, label, selected_domain=domain: (
                            self._rename_resource_label(
                                selected_domain,
                                role_name,
                                label,
                            )
                        )
                    )
                row.setProperty("materialDomain", domain)
                row.setProperty("materialSection", section_id)
                self._install_resource_path_drop(
                    row,
                    domain=domain,
                    role=role_contract.role,
                    source_kind=(
                        "directory" if section_id == "folder" else "file"
                    ),
                    max_items=role_contract.max_items,
                )
                row.token_renamed.connect(
                    lambda current, renamed, selected_domain=domain: (
                        self._rename_resource_role(
                            selected_domain,
                            current,
                            renamed,
                        )
                    )
                )
                row.choose_requested.connect(
                    lambda role_name, selected_domain=domain: self._bind_resource_role(
                        selected_domain,
                        role_name,
                    )
                )
                if isinstance(row, LegacyAssetTokenRow):
                    row.preview_requested.connect(
                        lambda role_name, selected_domain=domain: (
                            self._preview_resource_role(
                                selected_domain,
                                role_name,
                            )
                        )
                    )
                    row.refresh_requested.connect(
                        lambda role_name, selected_domain=domain: (
                            self._refresh_resource_role(
                                selected_domain,
                                role_name,
                            )
                        )
                    )
                row.open_requested.connect(
                    lambda role_name, selected_domain=domain: self._open_resource_role(
                        selected_domain,
                        role_name,
                    )
                )
                row.clear_requested.connect(
                    lambda role_name, selected_domain=domain: self._clear_resource_role(
                        selected_domain,
                        role_name,
                    )
                )
                row.add_requested.connect(
                    lambda role_name, selected_domain=domain: self._add_resource_series(
                        selected_domain,
                        role_name,
                    )
                )
                row.remove_requested.connect(
                    lambda role_name, selected_domain=domain: (
                        self._remove_resource_definition(
                            selected_domain,
                            role_name,
                        )
                    )
                )
                layout.addWidget(row)
                self._legacy_resource_rows[domain][role_contract.role] = row
                section_counts[section_key] += 1
                apply_token_row_style(
                    row,
                    object_name=row.objectName(),
                    is_last=False,
                )

        for section_key, count in section_counts.items():
            domain, section_id = section_key
            rows = [
                row
                for row in self._legacy_resource_rows[domain].values()
                if row.property("materialSection") == section_id
            ]
            for index, row in enumerate(rows):
                apply_token_row_style(
                    row,
                    object_name=row.objectName(),
                    is_last=index == len(rows) - 1,
                )
            header = self._resource_section_headers.get(section_key)
            if header is not None:
                header.count_label.setText(f"{count} 项")
                guide = self._resource_column_guides.get(section_key)
                if guide is not None:
                    self._apply_legacy_resource_metrics(
                        domain,
                        section_id,
                        guide.metrics(),
                    )
        self._refresh_resource_empty_states()

    def _install_resource_path_drop(
        self,
        row: QWidget,
        *,
        domain: str,
        role: str,
        source_kind: str,
        max_items: int | None,
    ) -> None:
        directory = source_kind == "directory"
        image_suffixes = (
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".gif",
            ".webp",
            ".tif",
            ".tiff",
        )
        policy = PathAcceptancePolicy(
            path_kind="directory" if directory else "file",
            suffixes=image_suffixes if domain == "image" and not directory else (),
            cardinality=(
                "single" if directory or max_items == 1 else "multiple"
            ),
            max_paths=max_items,
            dialog_label="图片" if domain == "image" else "资料文件",
        )
        # Keep the controller owned by the row.  It covers dynamically-created
        # descendants too, matching the drag/drop surface of the classic UI.
        row._material_path_drop_controller = attach_path_drop(  # type: ignore[attr-defined]
            parent=row,
            surface=row,
            policy=policy,
            on_paths=lambda paths: self._bind_resource_paths(
                domain,
                role,
                paths,
                source_kind=source_kind,
            ),
        )

    def _resource_section_for_role(self, domain: str, role_contract) -> str:
        if domain == "content":
            return "all"
        payload = self._resource_extension_payload(role_contract.role)
        if payload.get("source_kind") == "directory":
            return "folder"
        if domain == "image" and role_contract.max_items is None:
            return "folder"
        return "single"

    def _refresh_resource_empty_states(self) -> None:
        for (domain, section_id), label in self._resource_empty_labels.items():
            count = sum(
                row.property("materialSection") == section_id
                for row in self._legacy_resource_rows[domain].values()
            )
            label.setVisible(count == 0)

    def _apply_legacy_resource_metrics(
        self,
        domain: str,
        section_id: str,
        metrics,
    ) -> None:
        for row in self._legacy_resource_rows.get(domain, {}).values():
            if (
                isinstance(row, LegacyAssetTokenRow)
                and row.property("materialSection") == section_id
            ):
                row.apply_metrics(metrics)

    def _resource_source_text(self, items) -> str:
        paths = list(self._resource_source_paths(items))
        if not paths:
            return ""
        if len(paths) == 1:
            return paths[0]
        return f"{len(paths)} 个文件 · {paths[0]}"

    def _resource_source_paths(self, items) -> tuple[str, ...]:
        if not items or self._snapshot is None:
            return ()
        paths: list[str] = []
        for item in items:
            try:
                paths.append(
                    str(
                        material_package_repository().object_path(
                            self._snapshot,
                            item,
                        )
                    )
                )
            except Exception:
                continue
        return tuple(paths)

    def _custom_resource_roles(self) -> set[str]:
        return {
            str(item.get("role", ""))
            for item in self._package_contract_extensions().get(
                "resource_roles",
                (),
            )
            if hasattr(item, "get") and str(item.get("role", "")).strip()
        }

    def _resource_extension_payload(self, role: str) -> dict[str, object]:
        return next(
            (
                dict(item)
                for item in self._package_contract_extensions().get(
                    "resource_roles",
                    (),
                )
                if hasattr(item, "get") and item.get("role") == role
            ),
            {},
        )

    def _resource_authoring_source(
        self,
        owner_scope: str,
        owner_id: str,
        role: str,
    ) -> Path | None:
        if self._package is None:
            return None
        raw = self._package.metadata.get(
            "material_resource_authoring_sources",
            {},
        )
        if not hasattr(raw, "get"):
            return None
        role_sources = raw.get(role, {})
        if not hasattr(role_sources, "get"):
            return None
        value = str(role_sources.get(f"{owner_scope}:{owner_id}", "") or "")
        return Path(value) if value else None

    def _request_add_resource_role(
        self,
        domain: str,
        source_kind: str,
    ) -> None:
        if not self._is_user_package() or self._creating_resource_role:
            return
        self._creating_resource_role = True
        try:
            role = self._next_resource_role_name(domain, source_kind)
            max_items = None if source_kind == "directory" else 1
            self._apply_result(
                self._service().add_resource_role_definition(
                    self._package,
                    role=role,
                    label=role,
                    domain=domain,
                    max_items=max_items,
                    source_kind=source_kind,
                    recursive=source_kind == "directory",
                )
            )
        finally:
            self._creating_resource_role = False

    def _add_resource_series(self, domain: str, role: str) -> None:
        payload = self._resource_extension_payload(role)
        source_kind = str(payload.get("source_kind", "file"))
        self._request_add_resource_role(domain, source_kind)

    def _next_resource_role_name(self, domain: str, source_kind: str) -> str:
        prefix = {
            ("content", "file"): "文件",
            ("image", "file"): "单图",
            ("image", "directory"): "多图文件夹",
            ("attachment", "file"): "附件",
            ("attachment", "directory"): "附件文件夹",
        }[(domain, source_kind)]
        existing = {
            item.role
            for item in get_package_material_contract(self._package).resource_roles
        }
        index = 1
        while f"{prefix}{index}" in existing:
            index += 1
        return f"{prefix}{index}"

    def _rename_resource_role(
        self,
        domain: str,
        current_role: str,
        role: str,
    ) -> None:
        del domain
        if not self._is_user_package():
            return
        normalized = self._normalize_token_identifier(role)
        if not normalized or normalized == current_role:
            return
        payload = self._resource_extension_payload(current_role)
        label = str(payload.get("label", current_role))
        self._apply_result(
            self._service().rename_resource_role_definition(
                self._package,
                current_role=current_role,
                role=normalized,
                label=(normalized if label == current_role else label),
            )
        )

    def _rename_resource_label(
        self,
        domain: str,
        role: str,
        label: str,
    ) -> None:
        del domain
        if not self._is_user_package() or role not in self._custom_resource_roles():
            return
        cleaned = str(label or "").strip()
        if not cleaned:
            return
        self._apply_result(
            self._service().rename_resource_role_definition(
                self._package,
                current_role=role,
                role=role,
                label=cleaned,
            )
        )

    def _remove_resource_definition(self, domain: str, role: str) -> None:
        del domain
        if not self._is_user_package():
            return
        if not confirm(
            "删除资料",
            f"删除资料 Token {role} 及其所有层级中的文件？",
            confirm_text="删除资料",
            destructive=True,
            parent=self,
        ):
            return
        self._apply_result(
            self._service().remove_resource_role_definition(
                self._package,
                role=role,
            )
        )

    def _select_resource_role(self, domain: str, role: str) -> bool:
        table = self._resource_tables[domain]
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.data(Qt.UserRole) == role:
                table.selectRow(row)
                return True
        return False

    def _bind_resource_role(self, domain: str, role: str) -> None:
        if self._select_resource_role(domain, role):
            self._bind_resource(domain)

    def _bind_resource_paths(
        self,
        domain: str,
        role: str,
        paths: tuple[str, ...],
        *,
        source_kind: str = "",
    ) -> None:
        if not self._select_resource_role(domain, role) or not paths:
            return
        resolved_kind = source_kind or str(
            self._resource_extension_payload(role).get("source_kind", "file")
        )
        if resolved_kind == "directory":
            self._bind_resource(domain, directory_override=paths[0])
            return
        self._bind_resource(domain, paths_override=paths)

    def _refresh_resource_role(self, domain: str, role: str) -> None:
        if not self._select_resource_role(domain, role):
            return
        owner_scope, owner_id = self._selected_scope()
        package_id = self._package.package_id if self._package is not None else ""
        source = self._resource_import_directories.get(
            (package_id, owner_scope, owner_id, role)
        )
        if source is None:
            source = self._resource_authoring_source(
                owner_scope,
                owner_id,
                role,
            )
        self._bind_resource(
            domain,
            directory_override=(
                str(source) if source is not None and source.is_dir() else ""
            ),
        )

    def _preview_resource_role(self, domain: str, role: str) -> None:
        if domain != "image" or self._snapshot is None:
            return
        owner_scope, owner_id = self._selected_scope()
        scope = self._scope_object(owner_scope, owner_id)
        binding = scope.resources.get(role)
        items = tuple(binding.items) if binding is not None else ()
        if not items and self._current_record_id:
            resolution = self._resolved_record(self._current_record_id)
            if resolution.record is not None:
                items = tuple(resolution.record.resources.get(role, ()))
        paths = self._resource_source_paths(items)
        preview_items = tuple(
            PreviewItem.from_path(
                path,
                display_name=item.original_name,
                label=role,
            )
            for item, path in zip(items, paths)
        )
        if not preview_items:
            return
        ImagePreviewDialog(
            preview_items,
            title=f"图片预览 · {role}",
            parent=self,
        ).exec()

    def _open_resource_role(self, domain: str, role: str) -> None:
        if self._select_resource_role(domain, role):
            self._open_resource(domain)

    def _clear_resource_role(self, domain: str, role: str) -> None:
        if self._select_resource_role(domain, role):
            self._remove_resource(domain)

    def _refresh_image_policy_controls(self) -> None:
        extensions = self._package_contract_extensions()
        policy = dict(extensions.get("image_policy", {}) or {})
        writable = self._is_user_package()
        self._syncing_image_policy = True
        try:
            self._image_rule_adaptive_check.setChecked(
                bool(policy.get("adaptive", True))
            )
            self._image_rule_page_break_after_check.setChecked(
                bool(policy.get("page_break_after_images", False))
            )
            legacy_show_image_name = bool(policy.get("show_image_name", False))
            self._image_rule_single_name_check.setChecked(
                bool(
                    policy.get(
                        "show_single_image_name",
                        legacy_show_image_name,
                    )
                )
            )
            self._image_rule_multi_name_check.setChecked(
                bool(
                    policy.get(
                        "show_multi_image_name",
                        legacy_show_image_name,
                    )
                )
            )
            self._image_rule_watermark_check.setChecked(
                bool(policy.get("watermark_enabled", False))
            )
            source = str(policy.get("watermark_source", "fixed"))
            self._image_rule_watermark_free_radio.setChecked(source == "free")
            self._image_rule_watermark_fixed_radio.setChecked(source != "free")
            self._image_rule_watermark_edit.setText(
                str(policy.get("watermark_text", ""))
            )
            self._image_rule_watermark_font.set_font_name(
                str(policy.get("watermark_font", "宋体") or "宋体")
            )
        finally:
            self._syncing_image_policy = False
        enabled = self._image_rule_watermark_check.isChecked()
        fixed = self._image_rule_watermark_fixed_radio.isChecked()
        self._image_rule_adaptive_check.setEnabled(writable)
        self._image_rule_page_break_after_check.setEnabled(writable)
        self._image_rule_single_name_check.setEnabled(writable)
        self._image_rule_multi_name_check.setEnabled(writable)
        self._image_rule_watermark_check.setEnabled(writable)
        self._image_rule_watermark_fixed_radio.setEnabled(writable and enabled)
        self._image_rule_watermark_free_radio.setEnabled(writable and enabled)
        self._image_rule_watermark_edit.setEnabled(writable and enabled and fixed)
        self._image_rule_watermark_font_label.setEnabled(writable and enabled)
        self._image_rule_watermark_font.setEnabled(writable and enabled)
        self._image_rule_watermark_edit.setPlaceholderText(
            "水印文字或 {{字段}}" if fixed else "在工作台填写"
        )

    def _refresh_content_policy_controls(self) -> None:
        extensions = self._package_contract_extensions()
        policy = dict(extensions.get("content_policy", {}) or {})
        writable = self._is_user_package()
        mode = str(policy.get("format_mode", "target_document"))
        self._syncing_content_policy = True
        try:
            self._content_rule_plain_radio.setChecked(mode == "plain_text")
            self._content_rule_target_radio.setChecked(mode != "plain_text")
            self._content_rule_page_break_check.setChecked(
                str(policy.get("page_break_policy", "drop"))
                == "preserve_explicit"
            )
        finally:
            self._syncing_content_policy = False
        self._content_rule_target_radio.setEnabled(writable)
        self._content_rule_plain_radio.setEnabled(writable)
        # Source formatting is deliberately unavailable until the DOCX style,
        # numbering and relationship migration path exists end to end.
        self._content_rule_source_radio.setEnabled(False)
        self._content_rule_source_radio.hide()
        self._content_rule_page_break_check.setEnabled(
            writable and mode != "plain_text"
        )

    def _commit_content_policy(self, *_args) -> None:
        if (
            self._updating
            or self._syncing_content_policy
            or not self._is_user_package()
        ):
            return
        self._apply_result(
            self._service().set_content_policy(
                self._package,
                format_mode=(
                    "plain_text"
                    if self._content_rule_plain_radio.isChecked()
                    else "target_document"
                ),
                page_break_policy=(
                    "preserve_explicit"
                    if (
                        not self._content_rule_plain_radio.isChecked()
                        and self._content_rule_page_break_check.isChecked()
                    )
                    else "drop"
                ),
            )
        )

    def _commit_image_policy(self, *_args) -> None:
        if self._updating or self._syncing_image_policy or not self._is_user_package():
            return
        self._apply_result(
            self._service().set_image_policy(
                self._package,
                adaptive=self._image_rule_adaptive_check.isChecked(),
                watermark_enabled=self._image_rule_watermark_check.isChecked(),
                watermark_source=(
                    "free"
                    if self._image_rule_watermark_free_radio.isChecked()
                    else "fixed"
                ),
                watermark_text=self._image_rule_watermark_edit.text(),
                watermark_font=(
                    self._image_rule_watermark_font.selected_font() or "宋体"
                ),
                show_single_image_name=(self._image_rule_single_name_check.isChecked()),
                show_multi_image_name=(self._image_rule_multi_name_check.isChecked()),
                page_break_after_images=(
                    self._image_rule_page_break_after_check.isChecked()
                ),
            )
        )

    def _refresh_calculations(self) -> None:
        expanded_state = {
            segment_key: not body.isHidden()
            for segment_key, row in self._timeline_segment_rows.items()
            if (body := row.findChild(QWidget, "timeline_segment_body")) is not None
        }
        segments_updates_enabled = self._timeline_segments_container.updatesEnabled()
        timeline_is_active = self._active_section_id == "timeline"
        viewport = self._detail_scroll.viewport() if timeline_is_active else None
        viewport_updates_enabled = (
            viewport.updatesEnabled() if viewport is not None else False
        )
        scroll_bar = (
            self._detail_scroll.verticalScrollBar() if timeline_is_active else None
        )
        scroll_value = scroll_bar.value() if scroll_bar is not None else 0

        self._timeline_segments_container.setUpdatesEnabled(False)
        if viewport is not None:
            viewport.setUpdatesEnabled(False)
        try:
            self._rebuild_calculations(expanded_state)
            if timeline_is_active:
                timeline_page = self._section_pages["timeline"]
                self._detail_geometry.sync_now(timeline_page)
                if scroll_bar is not None:
                    scroll_bar.setValue(scroll_value)
        finally:
            self._timeline_segments_container.setUpdatesEnabled(
                segments_updates_enabled
            )
            if segments_updates_enabled:
                self._timeline_segments_container.update()
            if viewport is not None:
                viewport.setUpdatesEnabled(viewport_updates_enabled)
                if viewport_updates_enabled:
                    viewport.update()

    def _rebuild_calculations(
        self,
        expanded_state: dict[str, bool],
    ) -> None:
        self._clear_timeline_segment_rows()
        self._derivations.setRowCount(0)
        self._timelines.setRowCount(0)
        if self._package is None:
            self._timeline_empty_label.setVisible(True)
            return
        owner_scope, owner_id = self._selected_scope()
        scope = self._scope_object(owner_scope, owner_id)
        derivations = tuple(scope.derivations.items())
        self._derivations.setRowCount(len(derivations))
        for row, (key, spec) in enumerate(derivations):
            output = QTableWidgetItem(key)
            output.setData(Qt.UserRole, key)
            values = (
                output,
                QTableWidgetItem(spec.preset_id),
                QTableWidgetItem(", ".join(spec.input_fields)),
                QTableWidgetItem(
                    ", ".join(
                        f"{name}={value}" for name, value in spec.parameters.items()
                    )
                    or "—"
                ),
            )
            for column, item in enumerate(values):
                self._derivations.setItem(row, column, item)
        timelines = tuple(scope.timelines.items())
        self._timelines.setRowCount(len(timelines))
        for row, (key, spec) in enumerate(timelines):
            output = QTableWidgetItem(key)
            output.setData(Qt.UserRole, key)
            values = (
                output,
                QTableWidgetItem(spec.anchor_field),
                QTableWidgetItem(str(spec.parameters.get("days", ""))),
                QTableWidgetItem(spec.preset_id),
            )
            for column, item in enumerate(values):
                self._timelines.setItem(row, column, item)
        if derivations:
            self._derivations.selectRow(0)
        if timelines:
            self._timelines.selectRow(0)
        visible_segments = self._visible_timeline_segments()
        for index, segment_projection in enumerate(
            visible_segments,
            start=1,
        ):
            segment = (
                self._build_ratio_timeline_segment_row(
                    index,
                    segment_projection,
                )
                if segment_projection.ratio_based
                else self._build_timeline_segment_row(
                    index,
                    segment_projection.nodes[0][0],
                    segment_projection.nodes[0][1],
                    owner_scope=segment_projection.owner_scope,
                    owner_id=segment_projection.owner_id,
                )
            )
            segment_key = (
                f"{segment_projection.owner_scope}:"
                f"{segment_projection.owner_id}:"
                f"{segment_projection.segment_id}"
            )
            body = segment.findChild(QWidget, "timeline_segment_body")
            if body is not None:
                body.setVisible(expanded_state.get(segment_key, True))
            self._timeline_segments_layout.addWidget(segment)
            self._timeline_segment_rows[segment_key] = segment
        self._timeline_empty_label.setVisible(not visible_segments)

    def _visible_timeline_specs(
        self,
    ) -> tuple[tuple[str, str, str, MaterialTimelineSpec], ...]:
        """Return the current record's complete classic timeline projection.

        V1 stores calculations at package, group and record layers.  The
        classic timeline page was record-centric and always showed the whole
        effective plan, so it must not become empty merely because an internal
        layer selector currently points at a different owner.
        """

        package = self._package
        if package is None:
            return ()
        entries: list[tuple[str, str, str, MaterialTimelineSpec]] = [
            ("shared", "", key, specification)
            for key, specification in package.shared_scope.timelines.items()
        ]
        record = package.get_record(self._current_record_id)
        if record is not None and record.group_id:
            group = package.get_group(record.group_id)
            if group is not None:
                entries.extend(
                    (
                        "group",
                        group.group_id,
                        key,
                        specification,
                    )
                    for key, specification in group.scope.timelines.items()
                )
        if record is not None:
            entries.extend(
                (
                    "record",
                    record.record_id,
                    key,
                    specification,
                )
                for key, specification in record.scope.timelines.items()
            )
        return tuple(entries)

    def _visible_timeline_segments(
        self,
    ) -> tuple[_TimelineSegmentProjection, ...]:
        grouped: dict[
            tuple[str, str, str],
            list[tuple[str, MaterialTimelineSpec]],
        ] = {}
        ordered: list[
            tuple[
                str,
                str,
                str,
                str,
                str,
                bool,
            ]
        ] = []
        for owner_scope, owner_id, key, specification in self._visible_timeline_specs():
            ratio_based = specification.preset_id == "timeline_ratio"
            segment_id = (
                str(specification.parameters.get("segment_id", ""))
                if ratio_based
                else key
            ) or key
            group_key = (owner_scope, owner_id, segment_id)
            if group_key not in grouped:
                end_field = (
                    str(specification.parameters.get("end_field", ""))
                    if ratio_based
                    else key
                )
                grouped[group_key] = []
                ordered.append(
                    (
                        owner_scope,
                        owner_id,
                        segment_id,
                        specification.anchor_field,
                        end_field,
                        ratio_based,
                    )
                )
            grouped[group_key].append((key, specification))
        projections: list[_TimelineSegmentProjection] = []
        for (
            owner_scope,
            owner_id,
            segment_id,
            start_field,
            end_field,
            ratio_based,
        ) in ordered:
            nodes = grouped[(owner_scope, owner_id, segment_id)]
            if ratio_based:
                nodes.sort(
                    key=lambda item: int(item[1].parameters.get("node_index", "0") or 0)
                )
            projections.append(
                _TimelineSegmentProjection(
                    owner_scope=owner_scope,
                    owner_id=owner_id,
                    segment_id=segment_id,
                    start_field=start_field,
                    end_field=end_field,
                    nodes=tuple(nodes),
                    ratio_based=ratio_based,
                )
            )
        return tuple(projections)

    def _clear_timeline_segment_rows(self) -> None:
        for row in self._timeline_segment_rows.values():
            self._timeline_segments_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self._timeline_segment_rows.clear()

    def _build_ratio_timeline_segment_row(
        self,
        index: int,
        projection: _TimelineSegmentProjection,
    ) -> QFrame:
        first_specification = projection.nodes[0][1]
        parameters = first_specification.parameters
        writable = self._is_user_package()
        resolved_values: dict[str, str] = {}
        if self._current_record_id:
            resolution = self._resolved_record(self._current_record_id)
            if resolution.record is not None:
                resolved_values = dict(resolution.record.field_values)
        start_value = resolved_values.get(projection.start_field, "")
        end_value = resolved_values.get(projection.end_field, "")
        row = QFrame(self._timeline_segments_container)
        row.setObjectName("timeline_segment_row")
        row.setProperty("tokenRow", True)
        row.setProperty("segmentId", projection.segment_id)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        outer = QVBoxLayout(row)
        outer.setContentsMargins(0, 12, 0, 16)
        outer.setSpacing(14)

        header = QFrame(row)
        header.setObjectName("timeline_segment_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 3, 4, 3)
        header_layout.setSpacing(8)
        title = QLabel(f"第 {index} 段时间", header)
        title.setObjectName("timeline_segment_title")
        count_label = QLabel(f"{len(projection.nodes)} 项", header)
        count_label.setObjectName("timeline_segment_range")
        status = QLabel(
            "已配置" if start_value and end_value else "待填写",
            header,
        )
        status.setObjectName("timeline_segment_status")
        actions = CompactRowActions(header)
        collapse = actions.add_action(
            "collapse",
            icon_name="chevron-down",
            tooltip="折叠本段",
            variant="ghost",
        )
        duplicate = actions.add_action(
            "duplicate",
            icon_name="copy",
            tooltip="复制整段",
            variant="ghost-primary",
            callback=lambda *_: self._duplicate_ratio_timeline_segment(projection),
        )
        remove = actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip="删除时间段",
            variant="ghost-danger",
            callback=lambda *_: self._remove_ratio_timeline_segment(projection),
        )
        duplicate.setEnabled(writable)
        remove.setEnabled(writable)
        header_layout.addWidget(title)
        header_layout.addWidget(count_label)
        header_layout.addStretch(1)
        header_layout.addWidget(collapse)
        header_layout.addWidget(status)
        header_layout.addWidget(actions)
        outer.addWidget(header)

        body = QWidget(row)
        body.setObjectName("timeline_segment_body")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        start_edit = QLineEdit(start_value, body)
        end_edit = QLineEdit(end_value, body)
        start_edit.setObjectName("timeline_segment_start_date")
        end_edit.setObjectName("timeline_segment_end_date")
        node_count = StyledSpinBox(body)
        node_count.setDecimals(0)
        node_count.setSingleStep(1)
        node_count.setRange(2, 50)
        node_count.setValue(len(projection.nodes))
        node_count.setSuffix(" 个")
        weekend = StyledComboBox(body)
        weekend.set_full_width_mode()
        for label, value in _TIMELINE_WEEKEND_OPTIONS:
            weekend.addItem(label, value)
        weekend.setCurrentIndex(
            max(
                0,
                weekend.findData(parameters.get("weekend_adjust", "none")),
            )
        )
        date_format = StyledComboBox(body)
        date_format.set_full_width_mode()
        for label, value in _TIMELINE_DATE_FORMAT_OPTIONS:
            date_format.addItem(label, value)
        date_format.setCurrentIndex(
            max(
                0,
                date_format.findData(parameters.get("output_format", "auto")),
            )
        )
        input_scope = StyledComboBox(body)
        input_scope.set_full_width_mode()
        input_scope.addItem("固定字段", "fixed")
        input_scope.addItem("自由字段", "floating")
        input_scope.setCurrentIndex(
            max(
                0,
                input_scope.findData(parameters.get("input_scope", "fixed")),
            )
        )
        floating = input_scope.currentData() == "floating"
        for edit, side in (
            (start_edit, "开始"),
            (end_edit, "结束"),
        ):
            edit.setEnabled(writable and not floating)
            edit.setPlaceholderText(
                f"请在工作台填写{side}日期"
                if floating
                else "例如：2025-10-27 或 2025年10月27日"
            )
        node_count.setEnabled(writable)
        weekend.setEnabled(writable)
        date_format.setEnabled(writable)
        input_scope.setEnabled(writable)

        form = InspectorForm(parent=body)
        form.add_grid(
            [
                [
                    template_form_row("日期格式", date_format, parent=form),
                    template_form_row("填写方式", input_scope, parent=form),
                ],
                [
                    template_form_row("开始日期", start_edit, parent=form),
                    template_form_row("结束日期", end_edit, parent=form),
                ],
                [
                    template_form_row(
                        "节点数量（含起止）",
                        node_count,
                        parent=form,
                    ),
                    template_form_row("周末策略", weekend, parent=form),
                ],
            ]
        )
        body_layout.addWidget(form)

        nodes_header = QWidget(body)
        nodes_header_layout = QHBoxLayout(nodes_header)
        nodes_header_layout.setContentsMargins(0, 0, 0, 0)
        nodes_header_layout.setSpacing(8)
        nodes_title = QLabel("时间节点", nodes_header)
        nodes_title.setObjectName("timeline_nodes_title")
        reset_button = QPushButton("恢复平均分配", nodes_header)
        apply_button_variant(reset_button, "secondary")
        reset_button.setEnabled(writable)
        reset_button.clicked.connect(
            lambda *_: self._reset_ratio_timeline_segment(projection)
        )
        nodes_header_layout.addWidget(nodes_title)
        nodes_header_layout.addStretch(1)
        nodes_header_layout.addWidget(reset_button)
        body_layout.addWidget(nodes_header)

        nodes_body = QWidget(body)
        nodes_body_layout = QVBoxLayout(nodes_body)
        nodes_body_layout.setContentsMargins(0, 0, 0, 0)
        nodes_body_layout.setSpacing(0)
        guide = TimelineNodeColumnGuide(parent=nodes_body)
        nodes_body_layout.addWidget(guide)
        node_rows = []
        node_total = len(projection.nodes)
        for node_index, (key, specification) in enumerate(
            projection.nodes,
            start=1,
        ):
            ratio = Decimal(specification.parameters["ratio"])
            percent = self._timeline_percent_text(ratio)
            node_row = self._build_timeline_node_row(
                parent=nodes_body,
                index=node_index,
                token=f"{{{{@time:{key}}}}}",
                namespace=MaterialTokenNamespace.TIME,
                position=percent,
                result=resolved_values.get(key, ""),
                position_editable=(writable and node_index not in {1, node_total}),
                position_committed=(
                    lambda text, output_key=key: self._commit_ratio_timeline_position(
                        projection,
                        output_key,
                        text,
                    )
                ),
            )
            node_rows.append(node_row)
            nodes_body_layout.addWidget(node_row[0])
        node_rows_tuple = tuple(node_rows)
        guide.metrics_changed.connect(
            lambda metrics, rows=node_rows_tuple: self._apply_timeline_node_metrics(
                rows,
                metrics,
            )
        )
        self._apply_timeline_node_metrics(
            node_rows_tuple,
            guide.metrics(),
        )
        body_layout.addWidget(nodes_body)
        outer.addWidget(body)

        collapse.clicked.connect(lambda *_: body.setVisible(not body.isVisible()))
        start_edit.editingFinished.connect(
            lambda: self._commit_ratio_timeline_dates(
                projection,
                start_edit.text(),
                end_edit.text(),
            )
        )
        end_edit.editingFinished.connect(
            lambda: self._commit_ratio_timeline_dates(
                projection,
                start_edit.text(),
                end_edit.text(),
            )
        )
        node_count.valueChanged.connect(
            lambda value: self._resize_ratio_timeline_segment(
                projection,
                int(value),
            )
        )
        weekend.currentIndexChanged.connect(
            lambda *_: self._update_ratio_timeline_settings(
                projection,
                weekend_adjust=str(weekend.currentData() or "none"),
            )
        )
        date_format.currentIndexChanged.connect(
            lambda *_: self._update_ratio_timeline_settings(
                projection,
                output_format=str(date_format.currentData() or "auto"),
            )
        )
        input_scope.currentIndexChanged.connect(
            lambda *_: self._update_ratio_timeline_settings(
                projection,
                input_scope=str(input_scope.currentData() or "fixed"),
            )
        )
        apply_token_row_style(
            row,
            object_name="timeline_segment_row",
            is_last=True,
            hover_highlight=False,
        )
        return row

    def _build_timeline_segment_row(
        self,
        index: int,
        key: str,
        specification: MaterialTimelineSpec,
        *,
        owner_scope: str,
        owner_id: str,
    ) -> QFrame:
        row = QFrame(self._timeline_segments_container)
        row.setObjectName("timeline_segment_row")
        row.setProperty("tokenRow", True)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        outer = QVBoxLayout(row)
        outer.setContentsMargins(0, 12, 0, 16)
        outer.setSpacing(14)

        header = QFrame(row)
        header.setObjectName("timeline_segment_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 3, 4, 3)
        header_layout.setSpacing(8)
        title = QLabel(f"第 {index} 段时间", header)
        title.setObjectName("timeline_segment_title")
        token_range = QLabel("2 项", header)
        token_range.setObjectName("timeline_segment_range")
        status = QLabel("已配置", header)
        status.setObjectName("timeline_segment_status")
        actions = CompactRowActions(header)
        collapse = actions.add_action(
            "collapse",
            icon_name="chevron-down",
            tooltip="折叠本段",
            variant="ghost",
        )
        duplicate = actions.add_action(
            "duplicate",
            icon_name="copy",
            tooltip="复制整段",
            variant="ghost-primary",
            callback=lambda *_: self._duplicate_timeline_segment(
                key,
                owner_scope=owner_scope,
                owner_id=owner_id,
            ),
        )
        remove = actions.add_action(
            "remove",
            icon_name="trash-2",
            tooltip="删除时间段",
            variant="ghost-danger",
            callback=lambda *_: self._remove_timeline_segment(
                key,
                owner_scope=owner_scope,
                owner_id=owner_id,
            ),
        )
        remove.setEnabled(self._is_user_package())
        duplicate.setEnabled(self._is_user_package())
        header_layout.addWidget(title)
        header_layout.addWidget(token_range)
        header_layout.addWidget(status)
        header_layout.addStretch(1)
        header_layout.addWidget(actions)
        outer.addWidget(header)

        body = QWidget(row)
        body.setObjectName("timeline_segment_body")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        resolved_values: dict[str, str] = {}
        if self._current_record_id:
            resolution = self._resolved_record(self._current_record_id)
            if resolution.record is not None:
                resolved_values = dict(resolution.record.field_values)
        start_edit = QLineEdit(
            resolved_values.get(specification.anchor_field, ""),
            body,
        )
        start_edit.setPlaceholderText("例如：2025-10-27")
        end_edit = QLineEdit(resolved_values.get(key, ""), body)
        end_edit.setPlaceholderText("例如：2026-01-27")
        node_count = StyledSpinBox(body)
        node_count.setDecimals(0)
        node_count.setRange(2, 2)
        node_count.setValue(2)
        node_count.setSuffix(" 个")
        node_count.setEnabled(False)
        weekend = StyledComboBox(body)
        weekend.set_full_width_mode()
        for label, value in _TIMELINE_WEEKEND_OPTIONS:
            weekend.addItem(label, value)
        weekend.setCurrentIndex(0)
        weekend.setEnabled(False)
        weekend.setToolTip("V1 日期偏移规则当前使用自然日")
        date_format = StyledComboBox(body)
        date_format.set_full_width_mode()
        for label, value in _TIMELINE_DATE_FORMAT_OPTIONS:
            date_format.addItem(label, value)
        date_format.setCurrentIndex(0)
        date_format.setEnabled(False)
        date_format.setToolTip("V1 执行链统一输出 ISO 日期")
        input_scope = StyledComboBox(body)
        input_scope.set_full_width_mode()
        input_scope.addItem("固定字段", "fixed")
        input_scope.addItem("自由字段", "floating")
        input_scope.setCurrentIndex(1 if owner_scope == "record" else 0)
        input_scope.setEnabled(False)

        form = InspectorForm(parent=body)
        form.add_grid(
            [
                [
                    template_form_row("日期格式", date_format, parent=form),
                    template_form_row("填写方式", input_scope, parent=form),
                ],
                [
                    template_form_row("开始日期", start_edit, parent=form),
                    template_form_row("结束日期", end_edit, parent=form),
                ],
                [
                    template_form_row(
                        "节点数量（含起止）",
                        node_count,
                        parent=form,
                    ),
                    template_form_row("周末策略", weekend, parent=form),
                ],
            ]
        )
        body_layout.addWidget(form)

        nodes_header = QWidget(body)
        nodes_header_layout = QHBoxLayout(nodes_header)
        nodes_header_layout.setContentsMargins(0, 0, 0, 0)
        nodes_header_layout.setSpacing(8)
        nodes_title = QLabel("时间节点", nodes_header)
        nodes_title.setObjectName("timeline_nodes_title")
        reset_button = QPushButton("恢复平均分配", nodes_header)
        apply_button_variant(reset_button, "secondary")
        reset_button.setEnabled(False)
        nodes_header_layout.addWidget(nodes_title)
        nodes_header_layout.addStretch(1)
        nodes_header_layout.addWidget(reset_button)
        body_layout.addWidget(nodes_header)

        nodes_body = QWidget(body)
        nodes_body_layout = QVBoxLayout(nodes_body)
        nodes_body_layout.setContentsMargins(0, 0, 0, 0)
        nodes_body_layout.setSpacing(0)
        guide = TimelineNodeColumnGuide(parent=nodes_body)
        nodes_body_layout.addWidget(guide)
        node_rows = (
            self._build_timeline_node_row(
                parent=nodes_body,
                index=1,
                token=f"{{{{@text:{specification.anchor_field}}}}}",
                namespace=MaterialTokenNamespace.TEXT,
                position="0",
                result=start_edit.text(),
            ),
            self._build_timeline_node_row(
                parent=nodes_body,
                index=2,
                token=f"{{{{@time:{key}}}}}",
                namespace=MaterialTokenNamespace.TIME,
                position="100",
                result=end_edit.text(),
            ),
        )
        for node_row, _widgets in node_rows:
            nodes_body_layout.addWidget(node_row)
        guide.metrics_changed.connect(
            lambda metrics, rows=node_rows: self._apply_timeline_node_metrics(
                rows,
                metrics,
            )
        )
        self._apply_timeline_node_metrics(node_rows, guide.metrics())
        body_layout.addWidget(nodes_body)
        outer.addWidget(body)

        collapse.clicked.connect(lambda *_: body.setVisible(not body.isVisible()))
        start_edit.editingFinished.connect(
            lambda: self._commit_timeline_date_range(
                key,
                start_edit,
                end_edit,
                specification=specification,
                owner_scope=owner_scope,
                owner_id=owner_id,
            )
        )
        end_edit.editingFinished.connect(
            lambda: self._commit_timeline_date_range(
                key,
                start_edit,
                end_edit,
                specification=specification,
                owner_scope=owner_scope,
                owner_id=owner_id,
            )
        )
        apply_token_row_style(
            row,
            object_name="timeline_segment_row",
            is_last=True,
            hover_highlight=False,
        )
        return row

    def _build_timeline_node_row(
        self,
        *,
        parent: QWidget,
        index: int,
        token: str,
        namespace: MaterialTokenNamespace,
        position: str,
        result: str,
        position_editable: bool = False,
        position_committed=None,
    ) -> tuple[
        QFrame,
        tuple[
            QLabel,
            MaterialTokenEdit,
            QLineEdit,
            ElidedReadOnlyValue,
        ],
    ]:
        row = QFrame(parent)
        row.setObjectName("timeline_node_row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(get_theme().token_row_column_gap)
        index_label = QLabel(str(index), row)
        index_label.setAlignment(Qt.AlignCenter)
        token_edit = MaterialTokenEdit(
            token,
            row,
            editable=False,
            namespace=namespace,
        )
        token_edit.setCompleted(True)
        position_edit = QLineEdit(position, row)
        position_edit.setObjectName("timeline_node_position")
        position_edit.setReadOnly(not position_editable)
        if position_committed is not None:
            position_edit.editingFinished.connect(
                lambda: position_committed(position_edit.text())
            )
        result_edit = ElidedReadOnlyValue(result, row)
        result_edit.setPlaceholderText("等待起止时间")
        layout.addWidget(index_label, 0)
        layout.addWidget(token_edit, 3)
        layout.addWidget(position_edit, 0)
        layout.addWidget(result_edit, 2)
        apply_token_row_style(
            row,
            object_name="timeline_node_row",
            is_last=index == 2,
        )
        return row, (index_label, token_edit, position_edit, result_edit)

    @staticmethod
    def _apply_timeline_node_metrics(
        rows: tuple[
            tuple[
                QFrame,
                tuple[
                    QLabel,
                    MaterialTokenEdit,
                    QLineEdit,
                    ElidedReadOnlyValue,
                ],
            ],
            ...,
        ],
        metrics: TimelineNodeColumnMetrics,
    ) -> None:
        for row, widgets in rows:
            index_label, token_edit, position_edit, result_edit = widgets
            layout = row.layout()
            layout.setContentsMargins(
                metrics.row_margin_x,
                get_theme().token_row_padding_y,
                metrics.row_margin_x,
                get_theme().token_row_padding_y,
            )
            layout.setSpacing(metrics.column_gap)
            index_label.setFixedWidth(metrics.index_width)
            position_edit.setFixedWidth(metrics.position_width)
            token_edit.setMinimumWidth(metrics.token_min_width)
            result_edit.setMinimumWidth(metrics.result_min_width)
            layout.setStretch(1, metrics.token_stretch)
            layout.setStretch(3, metrics.result_stretch)

    def _commit_timeline_date_range(
        self,
        key: str,
        start_edit: QLineEdit,
        end_edit: QLineEdit,
        *,
        specification: MaterialTimelineSpec,
        owner_scope: str,
        owner_id: str,
    ) -> None:
        if self._updating or not self._is_user_package():
            return
        start_text = start_edit.text().strip()
        end_text = end_edit.text().strip()
        try:
            start_date = date.fromisoformat(start_text)
        except ValueError:
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.timeline.start_date_invalid",
                        message="开始日期必须使用 YYYY-MM-DD 格式。",
                        severity="warning",
                    ),
                )
            )
            self._refresh_calculations()
            return
        current = self._service().set_field(
            self._package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            key=specification.anchor_field,
            value=start_text,
            provenance="timeline",
        )
        if not current.ok or current.package is None:
            self._apply_result(current)
            return
        days_text = str(specification.parameters.get("days", "0"))
        if end_text:
            try:
                days_text = str((date.fromisoformat(end_text) - start_date).days)
            except ValueError:
                self._show_issues(
                    (
                        MaterialIssue(
                            code="material.timeline.end_date_invalid",
                            message="结束日期必须使用 YYYY-MM-DD 格式。",
                            severity="warning",
                        ),
                    )
                )
                self._refresh_calculations()
                return
        self._apply_result(
            self._service().set_timeline(
                current.package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=key,
                specification=MaterialTimelineSpec(
                    output_field=key,
                    preset_id="date_offset_days",
                    preset_version=1,
                    anchor_field=specification.anchor_field,
                    parameters={"days": days_text},
                ),
            )
        )

    @staticmethod
    def _decimal_text(value: Decimal) -> str:
        text = format(value.normalize(), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text

    @staticmethod
    def _timeline_percent_text(ratio: Decimal) -> str:
        percent = (ratio * Decimal(100)).quantize(
            Decimal("0.1"),
            rounding=ROUND_HALF_UP,
        )
        return AssetsPanel._decimal_text(percent)

    @staticmethod
    def _ratio_timeline_parameters(
        *,
        segment_id: str,
        end_field: str,
        node_index: int,
        node_count: int,
        ratio: Decimal,
        weekend_adjust: str,
        output_format: str,
        input_scope: str,
    ) -> dict[str, str]:
        return {
            "end_field": end_field,
            "ratio": AssetsPanel._decimal_text(ratio),
            "weekend_adjust": weekend_adjust,
            "output_format": output_format,
            "segment_id": segment_id,
            "node_index": str(node_index),
            "node_count": str(node_count),
            "input_scope": input_scope,
        }

    def _next_timeline_segment_number(
        self,
        package: MaterialPackage | None = None,
    ) -> int:
        active_package = package or self._package
        contract = get_package_material_contract(active_package)
        occupied = {field.key for field in contract.fields}
        number = 1
        while any(
            key in occupied
            for key in (
                f"时间段{number}_开始",
                f"时间段{number}_结束",
                f"时间节点{number}-1",
            )
        ):
            number += 1
        return number

    def _create_ratio_timeline_segment(
        self,
        package: MaterialPackage,
        *,
        owner_scope: str,
        owner_id: str,
        ratios: tuple[Decimal, ...],
        weekend_adjust: str = "none",
        output_format: str = "auto",
        input_scope: str = "fixed",
        start_value: str = "",
        end_value: str = "",
    ):
        number = self._next_timeline_segment_number(package)
        segment_id = f"segment_{number}"
        start_field = f"时间段{number}_开始"
        end_field = f"时间段{number}_结束"
        node_keys = tuple(
            f"时间节点{number}-{index}" for index in range(1, len(ratios) + 1)
        )
        current = None
        working = package
        for field_key in (start_field, end_field, *node_keys):
            current = self._service().add_field_definition(
                working,
                key=field_key,
                label=field_key,
            )
            if not current.ok or current.package is None:
                return current
            working = current.package
        for node_index, (field_key, ratio) in enumerate(
            zip(node_keys, ratios),
            start=1,
        ):
            current = self._service().set_timeline(
                working,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=field_key,
                specification=MaterialTimelineSpec(
                    output_field=field_key,
                    preset_id="timeline_ratio",
                    preset_version=1,
                    anchor_field=start_field,
                    parameters=self._ratio_timeline_parameters(
                        segment_id=segment_id,
                        end_field=end_field,
                        node_index=node_index,
                        node_count=len(ratios),
                        ratio=ratio,
                        weekend_adjust=weekend_adjust,
                        output_format=output_format,
                        input_scope=input_scope,
                    ),
                ),
            )
            if not current.ok or current.package is None:
                return current
            working = current.package
        if start_value and input_scope != "floating":
            current = self._service().set_field(
                working,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=start_field,
                value=start_value,
                provenance="timeline",
            )
            if not current.ok or current.package is None:
                return current
            working = current.package
        if end_value and input_scope != "floating":
            current = self._service().set_field(
                working,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=end_field,
                value=end_value,
                provenance="timeline",
            )
        return current

    def _commit_ratio_timeline_dates(
        self,
        projection: _TimelineSegmentProjection,
        start_text: str,
        end_text: str,
    ) -> None:
        if self._updating or not self._is_user_package():
            return
        start_value = str(start_text or "").strip()
        end_value = str(end_text or "").strip()
        # The two editors commit on focus loss. Moving from the first editor
        # to the second must not validate an incomplete pair or rebuild the
        # form, otherwise the first value is discarded before the user can
        # finish entering the range.
        if not start_value or not end_value:
            return
        try:
            start_date = parse_timeline_date(start_value)
            end_date = parse_timeline_date(end_value)
            if end_date < start_date:
                raise ValueError("end_before_start")
        except ValueError:
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.timeline.date_range_invalid",
                        message="请填写有效的起止日期，且结束日期不能早于开始日期。",
                        severity="warning",
                    ),
                )
            )
            self._refresh_calculations()
            return
        current = self._service().set_field(
            self._package,
            owner_scope=projection.owner_scope,
            owner_id=projection.owner_id,
            key=projection.start_field,
            value=start_value,
            provenance="timeline",
        )
        if not current.ok or current.package is None:
            self._apply_result(current)
            return
        current = self._service().set_field(
            current.package,
            owner_scope=projection.owner_scope,
            owner_id=projection.owner_id,
            key=projection.end_field,
            value=end_value,
            provenance="timeline",
        )
        self._apply_result(current)

    def _update_ratio_timeline_settings(
        self,
        projection: _TimelineSegmentProjection,
        **changes: str,
    ) -> None:
        if self._updating or not self._is_user_package():
            return
        working = self._package
        current = None
        for key, specification in projection.nodes:
            parameters = dict(specification.parameters)
            parameters.update(
                {
                    name: str(value)
                    for name, value in changes.items()
                    if name
                    in {
                        "weekend_adjust",
                        "output_format",
                        "input_scope",
                    }
                }
            )
            current = self._service().set_timeline(
                working,
                owner_scope=projection.owner_scope,
                owner_id=projection.owner_id,
                key=key,
                specification=MaterialTimelineSpec(
                    output_field=key,
                    preset_id="timeline_ratio",
                    preset_version=1,
                    anchor_field=projection.start_field,
                    parameters=parameters,
                ),
            )
            if not current.ok or current.package is None:
                self._apply_result(current)
                return
            working = current.package
        if changes.get("input_scope") == "floating":
            for field_key in (
                projection.start_field,
                projection.end_field,
            ):
                current = self._service().remove_field(
                    working,
                    owner_scope=projection.owner_scope,
                    owner_id=projection.owner_id,
                    key=field_key,
                )
                if not current.ok or current.package is None:
                    self._apply_result(current)
                    return
                working = current.package
        if current is not None:
            self._apply_result(current)

    def _commit_ratio_timeline_position(
        self,
        projection: _TimelineSegmentProjection,
        output_key: str,
        raw_percent: str,
    ) -> None:
        if self._updating or not self._is_user_package():
            return
        try:
            ratio = Decimal(str(raw_percent or "").strip()) / Decimal(100)
        except InvalidOperation:
            ratio = Decimal(-1)
        ratios = [
            (ratio if key == output_key else Decimal(specification.parameters["ratio"]))
            for key, specification in projection.nodes
        ]
        if (
            ratio < 0
            or ratio > 1
            or any(current < previous for previous, current in zip(ratios, ratios[1:]))
        ):
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.timeline.ratio_invalid",
                        message="节点位置必须在 0–100% 之间，并且不能早于前一节点。",
                        severity="warning",
                    ),
                )
            )
            self._refresh_calculations()
            return
        specification = next(
            item for key, item in projection.nodes if key == output_key
        )
        parameters = dict(specification.parameters)
        parameters["ratio"] = self._decimal_text(ratio)
        self._apply_result(
            self._service().set_timeline(
                self._package,
                owner_scope=projection.owner_scope,
                owner_id=projection.owner_id,
                key=output_key,
                specification=MaterialTimelineSpec(
                    output_field=output_key,
                    preset_id="timeline_ratio",
                    preset_version=1,
                    anchor_field=projection.start_field,
                    parameters=parameters,
                ),
            )
        )

    def _reset_ratio_timeline_segment(
        self,
        projection: _TimelineSegmentProjection,
    ) -> None:
        self._set_ratio_timeline_positions(
            projection,
            tuple(
                Decimal(index) / Decimal(len(projection.nodes) - 1)
                for index in range(len(projection.nodes))
            ),
        )

    def _set_ratio_timeline_positions(
        self,
        projection: _TimelineSegmentProjection,
        ratios: tuple[Decimal, ...],
    ) -> None:
        if not self._is_user_package():
            return
        working = self._package
        current = None
        for (key, specification), ratio in zip(
            projection.nodes,
            ratios,
        ):
            parameters = dict(specification.parameters)
            parameters["ratio"] = self._decimal_text(ratio)
            current = self._service().set_timeline(
                working,
                owner_scope=projection.owner_scope,
                owner_id=projection.owner_id,
                key=key,
                specification=MaterialTimelineSpec(
                    output_field=key,
                    preset_id="timeline_ratio",
                    preset_version=1,
                    anchor_field=projection.start_field,
                    parameters=parameters,
                ),
            )
            if not current.ok or current.package is None:
                self._apply_result(current)
                return
            working = current.package
        if current is not None:
            self._apply_result(current)

    def _resize_ratio_timeline_segment(
        self,
        projection: _TimelineSegmentProjection,
        target_count: int,
    ) -> None:
        if self._updating or not self._is_user_package():
            return
        count = max(2, min(50, int(target_count)))
        if count == len(projection.nodes):
            return
        number = int(projection.segment_id.removeprefix("segment_"))
        working = self._package
        current = None
        if count < len(projection.nodes):
            for key, _specification in projection.nodes[count:]:
                current = self._service().remove_timeline(
                    working,
                    owner_scope=projection.owner_scope,
                    owner_id=projection.owner_id,
                    key=key,
                )
                if not current.ok or current.package is None:
                    self._apply_result(current)
                    return
                working = current.package
                current = self._service().remove_field_definition(
                    working,
                    key=key,
                )
                if not current.ok or current.package is None:
                    self._apply_result(current)
                    return
                working = current.package
        else:
            for node_index in range(
                len(projection.nodes) + 1,
                count + 1,
            ):
                key = f"时间节点{number}-{node_index}"
                current = self._service().add_field_definition(
                    working,
                    key=key,
                    label=key,
                )
                if not current.ok or current.package is None:
                    self._apply_result(current)
                    return
                working = current.package
        existing = {
            key: specification for key, specification in projection.nodes[:count]
        }
        base_parameters = dict(projection.nodes[0][1].parameters)
        for node_index in range(1, count + 1):
            key = f"时间节点{number}-{node_index}"
            specification = existing.get(key)
            parameters = (
                dict(specification.parameters)
                if specification is not None
                else dict(base_parameters)
            )
            parameters.update(
                self._ratio_timeline_parameters(
                    segment_id=projection.segment_id,
                    end_field=projection.end_field,
                    node_index=node_index,
                    node_count=count,
                    ratio=(Decimal(node_index - 1) / Decimal(count - 1)),
                    weekend_adjust=parameters["weekend_adjust"],
                    output_format=parameters["output_format"],
                    input_scope=parameters["input_scope"],
                )
            )
            current = self._service().set_timeline(
                working,
                owner_scope=projection.owner_scope,
                owner_id=projection.owner_id,
                key=key,
                specification=MaterialTimelineSpec(
                    output_field=key,
                    preset_id="timeline_ratio",
                    preset_version=1,
                    anchor_field=projection.start_field,
                    parameters=parameters,
                ),
            )
            if not current.ok or current.package is None:
                self._apply_result(current)
                return
            working = current.package
        if current is not None:
            self._apply_result(current)

    def _duplicate_ratio_timeline_segment(
        self,
        projection: _TimelineSegmentProjection,
    ) -> None:
        if not self._is_user_package():
            return
        values: dict[str, str] = {}
        if self._current_record_id:
            resolution = self._resolved_record(self._current_record_id)
            if resolution.record is not None:
                values = dict(resolution.record.field_values)
        parameters = projection.nodes[0][1].parameters
        result = self._create_ratio_timeline_segment(
            self._package,
            owner_scope=projection.owner_scope,
            owner_id=projection.owner_id,
            ratios=tuple(
                Decimal(specification.parameters["ratio"])
                for _key, specification in projection.nodes
            ),
            weekend_adjust=parameters["weekend_adjust"],
            output_format=parameters["output_format"],
            input_scope=parameters["input_scope"],
            start_value=values.get(projection.start_field, ""),
            end_value=values.get(projection.end_field, ""),
        )
        self._apply_result(result)

    def _remove_ratio_timeline_segment(
        self,
        projection: _TimelineSegmentProjection,
    ) -> None:
        if not self._is_user_package():
            return
        working = self._package
        current = None
        for key, _specification in projection.nodes:
            current = self._service().remove_timeline(
                working,
                owner_scope=projection.owner_scope,
                owner_id=projection.owner_id,
                key=key,
            )
            if not current.ok or current.package is None:
                self._apply_result(current)
                return
            working = current.package
        for field_key in (
            *(key for key, _specification in projection.nodes),
            projection.start_field,
            projection.end_field,
        ):
            current = self._service().remove_field_definition(
                working,
                key=field_key,
            )
            if not current.ok or current.package is None:
                self._apply_result(current)
                return
            working = current.package
        if current is not None:
            self._apply_result(current)

    def _duplicate_timeline_segment(
        self,
        key: str,
        *,
        owner_scope: str,
        owner_id: str,
    ) -> None:
        if not self._is_user_package():
            return
        scope = self._scope_object(owner_scope, owner_id)
        source = scope.timelines.get(key)
        if source is None:
            return
        anchor, output = self._next_timeline_field_pair()
        current = self._service().add_field_definition(
            self._package,
            key=anchor,
            label=anchor,
        )
        if not current.ok or current.package is None:
            self._apply_result(current)
            return
        current = self._service().add_field_definition(
            current.package,
            key=output,
            label=output,
        )
        if not current.ok or current.package is None:
            self._apply_result(current)
            return
        self._apply_result(
            self._service().set_timeline(
                current.package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=output,
                specification=MaterialTimelineSpec(
                    output_field=output,
                    preset_id=source.preset_id,
                    preset_version=source.preset_version,
                    anchor_field=anchor,
                    parameters=source.parameters,
                ),
            )
        )

    def _remove_timeline_segment(
        self,
        key: str,
        *,
        owner_scope: str,
        owner_id: str,
    ) -> None:
        if not self._is_user_package():
            return
        scope = self._scope_object(owner_scope, owner_id)
        source = scope.timelines.get(key)
        if source is None:
            return
        current = self._service().remove_timeline(
            self._package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            key=key,
        )
        if not current.ok or current.package is None:
            self._apply_result(current)
            return
        for field_key in (key, source.anchor_field):
            if (
                not self._is_generated_timeline_field(field_key)
                or field_key not in self._custom_field_keys()
                or self._timeline_field_is_referenced(
                    current.package,
                    field_key,
                )
            ):
                continue
            removed = self._service().remove_field_definition(
                current.package,
                key=field_key,
            )
            if not removed.ok or removed.package is None:
                self._apply_result(removed)
                return
            current = removed
        self._apply_result(current)

    def _next_timeline_field_pair(self) -> tuple[str, str]:
        contract = get_package_material_contract(self._package)
        occupied = {field.key for field in contract.fields}
        number = 1
        while True:
            anchor = f"时间段{number}_开始"
            output = f"时间段{number}_结束"
            if anchor not in occupied and output not in occupied:
                return anchor, output
            number += 1

    @staticmethod
    def _is_generated_timeline_field(key: str) -> bool:
        value = str(key or "")
        suffix = next(
            (item for item in ("_开始", "_结束") if value.endswith(item)),
            "",
        )
        return bool(
            suffix
            and value.startswith("时间段")
            and value[len("时间段") : -len(suffix)].isdigit()
        )

    @staticmethod
    def _timeline_field_is_referenced(
        package: MaterialPackage,
        key: str,
    ) -> bool:
        scopes = (
            package.shared_scope,
            *(group.scope for group in package.groups),
            *(record.scope for record in package.records),
        )
        return any(
            any(
                output == key or specification.anchor_field == key
                for output, specification in scope.timelines.items()
            )
            or any(
                output == key or key in specification.input_fields
                for output, specification in scope.derivations.items()
            )
            for scope in scopes
        )

    def _refresh_check(self) -> None:
        # This compatibility projection is intentionally never user-visible.
        # Reassert the invariant here because this method runs on every scope
        # and package refresh.
        self._preview_card.setVisible(False)
        self._issues.setRowCount(0)
        package = self._package
        record = (
            package.get_record(self._current_record_id) if package is not None else None
        )
        if package is None or record is None:
            self._check_summary.setText("未选择资料记录")
            return
        contract = get_package_material_contract(package)
        resolution = self._resolved_record(record.record_id)
        values = resolution.record.field_values if resolution.record else {}
        required = tuple(item for item in contract.fields if item.required)
        filled = sum(bool(values.get(item.key, "")) for item in required)
        issues = list(resolution.issues)
        if self._dirty:
            issues.insert(
                0,
                MaterialIssue(
                    code="material.package.unsaved",
                    path="package",
                    message="当前修改尚未保存；执行仍使用上一次已保存版本。",
                    severity="warning",
                ),
            )
        can_generate = not any(item.severity == "error" for item in issues)
        self._check_summary.setText(
            f"{record.display_name}　·　必填 {filled}/{len(required)}　·　"
            f"{'可生成' if can_generate else '需要处理'}"
        )
        self._issues.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            for column, text in enumerate(
                (
                    "错误" if issue.severity == "error" else "提醒",
                    issue.path or "—",
                    issue.message or issue.code,
                )
            ):
                self._issues.setItem(row, column, QTableWidgetItem(text))

    def _refresh_overview(self) -> None:
        package = self._package
        self._overview_preview_table.setRowCount(0)
        if package is None:
            self._source_banner.setText("尚未选择资料包")
            self._package_combo.setToolTip("选择资料包")
            self._overview_summary.clear()
            fit_table_height_to_contents(self._overview_preview_table)
            return
        contract = get_package_material_contract(package)
        source_text = (
            "内置资料包 · 只读。它是随软件发布的基准规则；"
            "需要修改时请使用“复制为我的”。"
            if self._entry and self._entry.source_type == "builtin"
            else "我的资料包 · 可编辑。所有文件都会归档进资料包对象库。"
        )
        self._source_banner.setText(source_text)
        self._package_combo.setToolTip(source_text)
        resource_counts = {
            domain: sum(1 for role in contract.resource_roles if role.domain == domain)
            for domain in ("content", "image", "attachment")
        }
        self._overview_summary.setText(
            f"{contract.label} · 记录 {len(package.records)} · "
            f"字段 {len(contract.fields)} · "
            f"资料角色 {sum(resource_counts.values())}"
        )
        current_record = package.get_record(self._current_record_id)
        resolution = (
            self._resolved_record(current_record.record_id)
            if current_record is not None
            else None
        )
        values = (
            resolution.record.field_values
            if resolution is not None and resolution.record is not None
            else {}
        )
        resources = (
            resolution.record.resources
            if resolution is not None and resolution.record is not None
            else {}
        )
        preview_rows: list[tuple[str, str, str, str, str]] = []
        for field in contract.fields:
            value = values.get(field.key, "")
            is_filled = bool(str(value).strip())
            status = (
                "已填写"
                if is_filled
                else ("必填未填写" if field.required else "未填写")
            )
            preview_rows.append(
                (
                    material_token(MaterialTokenNamespace.TEXT, field.key),
                    str(value) if is_filled else "—",
                    status,
                    field.key,
                    str(value) if is_filled else "",
                )
            )
        resource_namespaces = {
            "content": MaterialTokenNamespace.FILE,
            "image": MaterialTokenNamespace.IMAGE,
            "attachment": MaterialTokenNamespace.ATTACHMENT,
        }
        for role_contract in contract.resource_roles:
            items = tuple(resources.get(role_contract.role, ()))
            names = tuple(item.original_name for item in items)
            required = bool(role_contract.required or role_contract.min_items)
            preview_rows.append(
                (
                    material_token(
                        resource_namespaces[role_contract.domain],
                        role_contract.role,
                    ),
                    self._resource_overview_text(role_contract.domain, names),
                    (
                        "已绑定"
                        if names
                        else ("必填未绑定" if required else "未绑定")
                    ),
                    role_contract.role,
                    "\n".join(names),
                )
            )

        self._overview_preview_table.setRowCount(len(preview_rows))
        for row, (token, content, status, identity, tooltip) in enumerate(
            preview_rows
        ):
            token_item = QTableWidgetItem(token)
            token_item.setData(Qt.UserRole, identity)
            self._overview_preview_table.setItem(row, 0, token_item)
            content_item = QTableWidgetItem(content)
            if tooltip:
                content_item.setToolTip(tooltip)
            self._overview_preview_table.setItem(row, 1, content_item)
            self._overview_preview_table.setItem(
                row,
                2,
                QTableWidgetItem(status),
            )
            self._overview_preview_table.setRowHeight(row, 38)
        fit_table_height_to_contents(self._overview_preview_table)

    @staticmethod
    def _resource_overview_text(domain: str, names: tuple[str, ...]) -> str:
        if not names:
            return "—"
        if len(names) == 1:
            return names[0]
        unit = {
            "image": "张图片",
            "content": "个文件",
            "attachment": "个附件",
        }.get(domain, "个资源")
        visible_names = "、".join(names[:3])
        suffix = " …" if len(names) > 3 else ""
        return f"{len(names)} {unit} · {visible_names}{suffix}"

    def _resolved_record(self, record_id: str):
        from src.domain.materials import MaterialResolver

        package = self._package
        contract = get_package_material_contract(package)
        return MaterialResolver(package, contract).resolve_record(record_id)

    def _selected_scope(self) -> tuple[str, str]:
        data = self._scope.currentData()
        return data if isinstance(data, tuple) and len(data) == 2 else ("shared", "")

    def _is_user_package(self) -> bool:
        return bool(
            self._package is not None
            and self._entry is not None
            and self._entry.source_type == "user"
        )

    def _package_contract_extensions(self) -> dict[str, object]:
        if self._package is None:
            return {
                "fields": (),
                "resource_roles": (),
                "content_policy": {},
                "image_policy": {},
            }
        raw = self._package.metadata.get(PACKAGE_CONTRACT_EXTENSIONS_KEY, {})
        return dict(raw or {})

    @staticmethod
    def _normalize_token_identifier(value: object) -> str:
        text = str(value or "").strip()
        if text.startswith("{{") and text.endswith("}}"):
            text = text[2:-2].strip()
            if ":" in text:
                text = text.rsplit(":", 1)[-1].strip()
        if (
            not text
            or len(text) > 128
            or any(char.isspace() or char in "{}:" for char in text)
        ):
            return ""
        return text

    def _scope_object(self, owner_scope: str, owner_id: str):
        package = self._package
        if owner_scope == "shared":
            return package.shared_scope
        if owner_scope == "group":
            return package.get_group(owner_id).scope
        return package.get_record(owner_id).scope

    def _apply_result(self, result, *, publish: bool = True) -> bool:
        if not result.ok or result.package is None:
            self._show_issues(result.issues)
            return False
        self._package = result.package
        self._dirty = True
        self._refresh_editor()
        if publish:
            self._publish()
        return True

    def _service(self) -> MaterialPackageService:
        return MaterialPackageService(material_package_repository())

    def _prompt_rename_package(self) -> None:
        if self._package is None or not (
            self._entry and self._entry.source_type == "user"
        ):
            return
        name = input_text(
            "重命名资料包",
            "资料包名称",
            default=self._package.display_name,
            parent=self,
        )
        if name is None:
            return
        self._package_name.setText(name)
        self._rename_package()

    def _open_package_folder(self) -> None:
        if self._snapshot is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._snapshot.bundle_path)))

    def _rename_package(self) -> None:
        if self._updating or self._package is None:
            return
        name = self._package_name.text()
        if name == self._package.display_name:
            return
        self._apply_result(
            self._service().rename_package(
                self._package,
                display_name=name,
            )
        )

    def _add_group(self) -> None:
        if self._package is None:
            return
        name = input_text("新建分组", "分组名称", parent=self)
        if name is not None:
            self._apply_result(
                self._service().add_group(
                    self._package,
                    display_name=name,
                )
            )

    def _rename_group(self) -> None:
        if self._package is None:
            return
        owner_scope, owner_id = self._selected_scope()
        group = self._package.get_group(owner_id) if owner_scope == "group" else None
        if group is None:
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.group.not_selected",
                        message="请先在“编辑作用域”中选择一个分组。",
                    ),
                )
            )
            return
        name = input_text(
            "重命名分组",
            "分组名称",
            default=group.display_name,
            parent=self,
        )
        if name is not None:
            self._apply_result(
                self._service().rename_group(
                    self._package,
                    group_id=owner_id,
                    display_name=name,
                )
            )

    def _remove_group(self) -> None:
        if self._package is None:
            return
        owner_scope, owner_id = self._selected_scope()
        if owner_scope != "group":
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.group.not_selected",
                        message="请先选择要删除的分组作用域。",
                    ),
                )
            )
            return
        self._apply_result(
            self._service().remove_group(
                self._package,
                group_id=owner_id,
            )
        )

    def _add_record(self) -> None:
        if self._package is None:
            return
        name = input_text("添加资料记录", "记录名称", parent=self)
        if name is None:
            return
        result = self._service().add_record(
            self._package,
            display_name=name,
            lifecycle="active",
        )
        if self._apply_result(result, publish=False) and self._package:
            self._current_record_id = self._package.records[-1].record_id
            self._selected_record_ids = (
                *self._selected_record_ids,
                self._current_record_id,
            )
            self._refresh_editor()
            self._publish()

    def _remove_record(self) -> None:
        if self._package is None or not self._current_record_id:
            return
        record_id = self._current_record_id
        result = self._service().remove_record(self._package, record_id=record_id)
        if self._apply_result(result, publish=False):
            self._selected_record_ids = tuple(
                item for item in self._selected_record_ids if item != record_id
            )
            self._current_record_id = (
                self._package.records[0].record_id if self._package.records else ""
            )
            self._refresh_editor()
            self._publish()

    def _on_current_record_changed(self, current, _previous) -> None:
        if self._updating or current is None:
            return
        self._current_record_id = str(current.data(Qt.UserRole) or "")
        self._updating = True
        try:
            self._refresh_record_editor()
        finally:
            self._updating = False
        self._publish()

    def _on_record_checked(self, _item) -> None:
        if self._updating or self._package is None:
            return
        checked = {
            str(self._records.item(index).data(Qt.UserRole) or "")
            for index in range(self._records.count())
            if self._records.item(index).checkState() == Qt.Checked
        }
        self._selected_record_ids = tuple(
            item.record_id
            for item in self._package.records
            if item.record_id in checked and item.lifecycle == "active"
        )
        self._publish()

    def _rename_record(self) -> None:
        if self._updating or self._package is None or not self._current_record_id:
            return
        self._apply_result(
            self._service().rename_record(
                self._package,
                record_id=self._current_record_id,
                display_name=self._record_name.text(),
            )
        )

    def _set_lifecycle(self, _index: int) -> None:
        if self._updating or self._package is None or not self._current_record_id:
            return
        lifecycle = str(self._lifecycle.currentData() or "")
        if self._apply_result(
            self._service().set_record_lifecycle(
                self._package,
                record_id=self._current_record_id,
                lifecycle=lifecycle,
            ),
            publish=False,
        ):
            if lifecycle != "active":
                self._selected_record_ids = tuple(
                    item
                    for item in self._selected_record_ids
                    if item != self._current_record_id
                )
            self._refresh_editor()
            self._publish()

    def _move_record(self, _index: int) -> None:
        if self._updating or self._package is None or not self._current_record_id:
            return
        self._apply_result(
            self._service().move_record(
                self._package,
                record_id=self._current_record_id,
                group_id=str(self._record_group.currentData() or ""),
            )
        )

    def _on_field_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != 2 or self._package is None:
            return
        key_item = self._fields.item(item.row(), 1)
        if key_item is None:
            return
        key = str(key_item.data(Qt.UserRole) or key_item.text())
        owner_scope, owner_id = self._selected_scope()
        self._apply_result(
            self._service().set_field(
                self._package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=key,
                value=item.text(),
                provenance="ui",
            )
        )

    def _clear_selected_field(self) -> None:
        if self._package is None:
            return
        row = self._fields.currentRow()
        key_item = self._fields.item(row, 1) if row >= 0 else None
        if key_item is None:
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.field.not_selected",
                        message="请先选择要清除的字段。",
                    ),
                )
            )
            return
        key = str(key_item.data(Qt.UserRole) or key_item.text())
        owner_scope, owner_id = self._selected_scope()
        self._apply_result(
            self._service().remove_field(
                self._package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=key,
            )
        )

    def _selected_resource_role(self, domain: str) -> str:
        table = self._resource_tables[domain]
        row = table.currentRow()
        item = table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.UserRole) or "") if item is not None else ""

    def _bind_resource(
        self,
        domain: str = "",
        *,
        directory_override: str = "",
        paths_override: tuple[str, ...] = (),
    ) -> None:
        if (
            self._package is None
            or self._snapshot is None
            or self._entry is None
            or self._entry.source_type != "user"
        ):
            return
        role = self._selected_resource_role(domain) if domain else ""
        if not role:
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.resource.role_not_selected",
                        message="当前资料契约没有可选角色，或尚未选择资料角色。",
                    ),
                )
            )
            return
        contract = get_package_material_contract(self._package)
        role_contract = contract.get_resource_role(role)
        if role_contract is None:
            return
        owner_scope, owner_id = self._selected_scope()
        if owner_scope not in role_contract.allowed_scopes:
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.resource.scope_not_allowed",
                        message=f"{role_contract.label} 不允许放在当前作用域。",
                    ),
                )
            )
            return
        role_payload = self._resource_extension_payload(role)
        source_kind = str(role_payload.get("source_kind", "file"))
        if directory_override or (
            domain == "image" and role_contract.max_items is None
        ):
            source_kind = "directory"
        selected_directory: Path | None = None
        selected_authoring_source: Path | None = None
        if source_kind == "directory":
            directory = str(directory_override or "").strip() or (
                QFileDialog.getExistingDirectory(
                    self,
                    f"选择{role_contract.label}文件夹",
                )
            )
            if not directory:
                return
            root = Path(directory)
            selected_directory = root
            selected_authoring_source = root
            candidates = (
                root.rglob("*")
                if bool(role_payload.get("recursive", True))
                else root.iterdir()
            )
            files = tuple(
                sorted(
                    (
                        item
                        for item in candidates
                        if item.is_file()
                        and (
                            domain != "image"
                            or item.suffix.lower()
                            in {
                                ".png",
                                ".jpg",
                                ".jpeg",
                                ".bmp",
                                ".gif",
                                ".webp",
                                ".tif",
                                ".tiff",
                            }
                        )
                    ),
                    key=lambda item: attachment_natural_path_key(
                        item.relative_to(root).as_posix()
                    ),
                )
            )
            paths = [str(item) for item in files[:2048]]
            if not paths:
                self._show_issues(
                    (
                        MaterialIssue(
                            code="material.resource.directory_empty",
                            message="所选文件夹中没有可用文件。",
                            severity="warning",
                        ),
                    )
                )
                return
        elif paths_override:
            paths = [str(path) for path in paths_override if str(path).strip()]
        elif role_contract.max_items == 1:
            path, _filter = QFileDialog.getOpenFileName(
                self,
                f"选择{role_contract.label}",
            )
            paths = [path] if path else []
        else:
            paths, _filter = QFileDialog.getOpenFileNames(
                self,
                f"选择{role_contract.label}",
            )
        if not paths:
            return
        if selected_authoring_source is None and len(paths) == 1:
            selected_authoring_source = Path(paths[0])
        scope = self._scope_object(owner_scope, owner_id)
        existing = scope.resources.get(role)
        existing_items = (
            tuple(existing.items)
            if existing is not None and role_contract.merge_policy == "append"
            else ()
        )
        if (
            role_contract.max_items is not None
            and len(existing_items) + len(paths) > role_contract.max_items
        ):
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.resource.too_many_items",
                        message=(
                            f"{role_contract.label}最多允许 "
                            f"{role_contract.max_items} 个文件。"
                        ),
                    ),
                )
            )
            return
        try:
            imported = tuple(
                material_package_repository().import_object(
                    work_mode_id=self._package.work_mode_id,
                    package_id=self._package.package_id,
                    source_path=path,
                )
                for path in paths
            )
            accepted = set(role_contract.accepted_media_types)
            unsupported = tuple(
                item.original_name
                for item in imported
                if accepted and item.media_type not in accepted
            )
            if unsupported:
                raise ValueError(
                    "material_resource_media_type_not_allowed:" + ",".join(unsupported)
                )
            unique_items = {
                item.object_id: item for item in (*existing_items, *imported)
            }
            service = self._service()
            result = service.bind_resource(
                self._package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                binding=MaterialResourceBinding(
                    role=role,
                    items=tuple(unique_items.values()),
                    merge_policy=role_contract.merge_policy,
                ),
            )
            if (
                selected_authoring_source is not None
                and result.ok
                and result.package is not None
            ):
                result = service.set_resource_authoring_source(
                    result.package,
                    owner_scope=owner_scope,
                    owner_id=owner_id,
                    role=role,
                    source_path=str(selected_authoring_source),
                )
            if self._apply_result(result) and selected_directory is not None:
                self._resource_import_directories[
                    (
                        self._package.package_id,
                        owner_scope,
                        owner_id,
                        role,
                    )
                ] = selected_directory
        except Exception as exc:
            self._show_exception("material.resource.import_failed", exc)

    def _remove_resource(self, domain: str) -> None:
        if self._package is None:
            return
        role = self._selected_resource_role(domain)
        if not role:
            return
        owner_scope, owner_id = self._selected_scope()
        service = self._service()
        result = service.remove_resource(
            self._package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            role=role,
        )
        if result.ok and result.package is not None:
            result = service.set_resource_authoring_source(
                result.package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                role=role,
                source_path="",
            )
        if self._apply_result(result):
            self._resource_import_directories.pop(
                (
                    self._package.package_id,
                    owner_scope,
                    owner_id,
                    role,
                ),
                None,
            )

    def _open_resource(self, domain: str) -> None:
        if self._package is None or self._snapshot is None:
            return
        role = self._selected_resource_role(domain)
        if not role:
            return
        owner_scope, owner_id = self._selected_scope()
        scope = self._scope_object(owner_scope, owner_id)
        binding = scope.resources.get(role)
        items = tuple(binding.items) if binding is not None else ()
        if not items and self._current_record_id:
            resolution = self._resolved_record(self._current_record_id)
            if resolution.record is not None:
                items = tuple(resolution.record.resources.get(role, ()))
        if not items:
            self._show_issues(
                (
                    MaterialIssue(
                        code="material.resource.empty",
                        message="这个资料角色当前没有可打开的文件。",
                        severity="warning",
                    ),
                )
            )
            return
        try:
            path = material_package_repository().object_path(
                self._snapshot,
                items[0],
            )
            authoring_source = self._resource_authoring_source(
                owner_scope,
                owner_id,
                role,
            )
            source_kind = self._resource_extension_payload(role).get(
                "source_kind"
            )
            role_contract = get_package_material_contract(
                self._package
            ).get_resource_role(role)
            if (
                domain == "image"
                and role_contract is not None
                and role_contract.max_items is None
            ):
                source_kind = "directory"
            if source_kind == "directory":
                path = (
                    authoring_source
                    if authoring_source is not None and authoring_source.is_dir()
                    else path.parent
                )
            elif domain == "image":
                path = (
                    authoring_source.parent
                    if authoring_source is not None and authoring_source.is_file()
                    else path.parent
                )
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as exc:
            self._show_exception("material.resource.open_failed", exc)

    def _add_derivation(self) -> None:
        if self._package is None:
            return
        contract = get_package_material_contract(self._package)
        keys = tuple(item.key for item in contract.fields)
        if not keys:
            return
        dialog = _DerivationEditorDialog(keys, self)
        if dialog.exec() != QDialog.Accepted:
            return
        output = dialog.output_field()
        specification = dialog.specification()
        owner_scope, owner_id = self._selected_scope()
        self._apply_result(
            self._service().set_derivation(
                self._package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=output,
                specification=specification,
            )
        )

    def _remove_derivation(self) -> None:
        if self._package is None:
            return
        row = self._derivations.currentRow()
        item = self._derivations.item(row, 0) if row >= 0 else None
        if item is None:
            return
        owner_scope, owner_id = self._selected_scope()
        self._apply_result(
            self._service().remove_derivation(
                self._package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=str(item.data(Qt.UserRole) or item.text()),
            )
        )

    def _add_timeline(self) -> None:
        if self._package is None or not self._is_user_package():
            return
        owner_scope, owner_id = self._selected_scope()
        result = self._create_ratio_timeline_segment(
            self._package,
            owner_scope=owner_scope,
            owner_id=owner_id,
            ratios=(Decimal(0), Decimal(1)),
        )
        self._apply_result(result)

    def _remove_timeline(self) -> None:
        if self._package is None:
            return
        row = self._timelines.currentRow()
        item = self._timelines.item(row, 0) if row >= 0 else None
        if item is None:
            return
        owner_scope, owner_id = self._selected_scope()
        self._apply_result(
            self._service().remove_timeline(
                self._package,
                owner_scope=owner_scope,
                owner_id=owner_id,
                key=str(item.data(Qt.UserRole) or item.text()),
            )
        )

    def _create_package(self) -> None:
        if not self._resolve_pending_before("新建资料包"):
            return
        name = input_text("新建资料包", "资料包名称", parent=self)
        if name is None:
            return
        contract_id = default_material_contract_id(self._mode_id)
        package = MaterialPackage(
            package_id=generate_package_id(),
            display_name=name,
            work_mode_id=self._mode_id,
            material_contract_id=contract_id,
            records=(
                MaterialRecord(
                    record_id=generate_record_id(),
                    display_name="记录 1",
                    lifecycle="active",
                ),
            ),
        )
        try:
            receipt = create_material_package_in_library_with_receipt(package)
        except Exception as exc:
            self._show_exception("material.package.create_failed", exc)
            return
        self._reload_library(receipt.entry.package_id)

    def _duplicate_package(self) -> None:
        if not self._resolve_pending_before("复制资料包"):
            return
        if self._snapshot is None:
            return
        name = input_text(
            "复制资料包",
            "新资料包名称",
            default=f"{self._snapshot.package.display_name} 副本",
            parent=self,
        )
        if name is None:
            return
        try:
            receipt = duplicate_material_package_entry_with_receipt(
                self._snapshot,
                name=name,
            )
        except Exception as exc:
            self._show_exception("material.package.duplicate_failed", exc)
            return
        self._reload_library(receipt.entry.package_id)

    def _import_workbook(self) -> None:
        if not self._resolve_pending_before("导入资料表格"):
            return
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "导入资料表格",
            "",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        contract_id = default_material_contract_id(self._mode_id)
        contract = get_material_contract(contract_id, work_mode_id=self._mode_id)
        try:
            dialog = _WorkbookMappingDialog(Path(path), contract, self)
            if dialog.exec() != QDialog.Accepted:
                return
            draft = inspect_material_workbook(
                path,
                work_mode_id=self._mode_id,
                material_contract_id=contract_id,
                mapping=dialog.mapping(),
            )
            package = draft.materialize()
            receipt = create_material_package_in_library_with_receipt(package)
        except Exception as exc:
            self._show_exception("material.import.failed", exc)
            return
        self._reload_library(receipt.entry.package_id)

    def _delete_package(self) -> None:
        if not self._resolve_pending_before("删除资料包"):
            return
        if self._entry is None or self._entry.source_type != "user":
            return
        if not confirm(
            "删除资料包",
            f"确定删除“{self._entry.name}”及其包内对象吗？",
            confirm_text="删除资料包",
            destructive=True,
            parent=self,
        ):
            return
        try:
            delete_material_package_entry(self._entry)
        except Exception as exc:
            self._show_exception("material.package.delete_failed", exc)
            return
        self._reload_library("")

    def _restore_committed_draft(self) -> bool:
        if self._entry is None:
            return False
        try:
            snapshot = load_material_package_entry(self._entry)
        except Exception as exc:
            self._show_exception("material.package.discard_failed", exc)
            return False
        self._snapshot = snapshot
        self._package = snapshot.package
        self._dirty = False
        valid_ids = {item.record_id for item in snapshot.package.records}
        self._selected_record_ids = tuple(
            item for item in self._selected_record_ids if item in valid_ids
        )
        if self._current_record_id not in valid_ids:
            self._current_record_id = (
                snapshot.package.records[0].record_id
                if snapshot.package.records
                else ""
            )
        self._refresh_editor()
        self._publish()
        return True

    def _discard_draft(self) -> None:
        if not self._dirty:
            return
        if confirm(
            "放弃未保存修改",
            "确定恢复到上一次已保存版本吗？当前未保存修改将被清除。",
            confirm_text="放弃修改",
            destructive=True,
            parent=self,
        ):
            self._restore_committed_draft()

    def _resolve_pending_before(self, reason: str) -> bool:
        if not self._dirty:
            return True
        action = self._prompt_pending_material_action(reason)
        if action == "cancel":
            return False
        if action == "save":
            return self._save()
        return self._restore_committed_draft()

    def _save(self) -> bool:
        if (
            not self._dirty
            or self._package is None
            or self._entry is None
            or self._entry.source_type != "user"
        ):
            return not self._dirty
        result = self._service().save(
            self._package,
            expected_revision=self._entry.revision,
        )
        if not result.ok or result.snapshot is None:
            self._show_issues(result.issues)
            return False
        self._snapshot = result.snapshot
        self._package = result.snapshot.package
        self._entry = MaterialPackageLibraryEntry(
            package_id=self._package.package_id,
            name=self._package.display_name,
            path=result.snapshot.bundle_path / "package.json",
            mode_id=self._package.work_mode_id,
            source_type="user",
            material_contract_id=self._package.material_contract_id,
            revision=result.snapshot.ref.revision,
        )
        self._dirty = False
        self._refresh_editor()
        self._publish()
        return True

    def _publish(self) -> None:
        package = self._package
        snapshot = self._snapshot
        if package is None or snapshot is None:
            self.bridge.set_current_material_package_ref(None)
            self.bridge.set_current_material_run_selection(None)
            self.bridge.set_current_material_preview_snapshot(None)
            self.bridge.set_current_material_issues(())
            return
        contract = get_package_material_contract(package)
        preview = project_material_preview(
            package,
            revision=(
                material_package_revision(package)
                if self._dirty
                else snapshot.ref.revision
            ),
            source_type=snapshot.source_type,
            contract=contract,
            current_record_id=self._current_record_id,
        )
        self.bridge.set_current_material_preview_snapshot(preview)
        if self._dirty:
            self.bridge.set_current_material_issues(
                (
                    MaterialIssue(
                        code="material.package.unsaved",
                        message=(
                            "资料包存在未保存修改，执行选择仍保持在已提交 revision。"
                        ),
                        severity="warning",
                        remediation="保存资料包后再执行。",
                    ),
                )
            )
            return
        package_ref = MaterialPackageRef(
            package_id=package.package_id,
            revision=snapshot.ref.revision,
        )
        selection = MaterialRunSelection(
            package_ref=package_ref,
            selected_record_ids=self._selected_record_ids,
        )
        self.bridge.set_current_material_package_ref(package_ref)
        self.bridge.set_current_material_run_selection(selection)
        self.bridge.set_current_material_issues(())

    def _show_issues(self, issues: tuple[MaterialIssue, ...]) -> None:
        self.bridge.set_current_material_issues(tuple(issues))
        message = (
            "\n".join(item.message or item.code for item in issues) or "资料操作失败"
        )
        self._status.setText(message)
        Toast.show_error(message)

    def _show_exception(self, code: str, exc: Exception) -> None:
        logger.exception("Material UI boundary failed: %s", code, exc_info=exc)
        self._show_issues(
            (
                MaterialIssue(
                    code=code,
                    message=f"{type(exc).__name__}: {exc}",
                    remediation="保持当前选择不变，请修正资料包后重试。",
                ),
            )
        )

    def has_pending_material_changes(self) -> bool:
        return self._dirty

    def prepare_pending_material_changes(self, action: str) -> bool:
        if not self._dirty:
            return True
        if self._package is None or self._entry is None or self._snapshot is None:
            return False
        normalized = str(action or "").strip()
        if normalized not in {"save", "discard"}:
            return False
        self._prepared = _PreparedChange(
            action=normalized,
            package=self._package,
            entry=self._entry,
            snapshot=self._snapshot,
            selected_record_ids=self._selected_record_ids,
            current_record_id=self._current_record_id,
        )
        return True

    def commit_prepared_material_changes(self) -> bool:
        prepared = self._prepared
        if prepared is None:
            return True
        if prepared.action == "save":
            if not self._save():
                return False
            prepared.committed_entry = self._entry
            return True
        self._entry = prepared.entry
        self._snapshot = load_material_package_entry(prepared.entry)
        self._package = self._snapshot.package
        self._dirty = False
        self._refresh_editor()
        self._publish()
        return True

    def rollback_prepared_material_changes(self) -> bool:
        prepared = self._prepared
        if prepared is None:
            return True
        try:
            if prepared.action == "save" and prepared.committed_entry is not None:
                restored = material_package_repository().save_user(
                    prepared.snapshot.package,
                    expected_revision=prepared.committed_entry.revision,
                )
                self._snapshot = restored
                self._entry = MaterialPackageLibraryEntry(
                    package_id=restored.package.package_id,
                    name=restored.package.display_name,
                    path=restored.bundle_path / "package.json",
                    mode_id=restored.package.work_mode_id,
                    source_type="user",
                    material_contract_id=restored.package.material_contract_id,
                    revision=restored.ref.revision,
                )
            else:
                self._snapshot = prepared.snapshot
                self._entry = prepared.entry
            self._package = prepared.package
            self._selected_record_ids = prepared.selected_record_ids
            self._current_record_id = prepared.current_record_id
            self._dirty = True
            self._refresh_editor()
            self._publish()
            return True
        except Exception as exc:
            self._show_exception("material.package.rollback_failed", exc)
            return False

    def finalize_prepared_material_changes(self) -> None:
        self._prepared = None

    def cancel_prepared_material_changes(self) -> bool:
        self._prepared = None
        return True

    def _prompt_pending_material_action(self, reason: str) -> str:
        """Ask how to resolve the canonical editor draft before closing."""

        message = (
            "当前资料包有未保存修改。"
            f"{reason or '关闭窗口'!s}前，请选择保存、放弃或取消。"
        )
        return decision(
            "资料包尚未保存",
            message,
            actions=(
                DialogAction("cancel", "取消", default=True, escape=True),
                DialogAction("discard", "放弃修改", variant="danger"),
                DialogAction("save", "保存", variant="primary"),
            ),
            icon_style="warning",
            parent=self,
        )

    def prepare_close_pending_changes(self) -> bool:
        if not self._dirty:
            return True
        action = self._prompt_pending_material_action("关闭窗口")
        if action == "cancel":
            return False
        return self.prepare_pending_material_changes(action)

    def commit_close_pending_changes(self) -> bool:
        return self.commit_prepared_material_changes()

    def rollback_close_pending_changes(self) -> bool:
        return self.rollback_prepared_material_changes()

    def finalize_close_pending_changes(self) -> bool:
        self.finalize_prepared_material_changes()
        return True

    def cancel_prepared_close(self) -> bool:
        return self.cancel_prepared_material_changes()


__all__ = ["AssetsPanel"]
