"""Side-drawer editor for user-owned official-document requirements."""

from __future__ import annotations

from collections.abc import Sequence

from src.assistant.application.official_plan_editing import (
    OfficialPlanEditValues,
    validate_official_plan_edit_values,
)
from src.assistant.application.official_plan_binding import (
    OFFICIAL_DELIVERY_FORMAL,
    OFFICIAL_DELIVERY_INTERNAL_REVIEW,
    OFFICIAL_DELIVERY_MEETING_ARCHIVE,
)
from src.config.master_library import get_master
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    list_official_document_profiles,
)
from src.qt_api import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Signal,
    Qt,
)
from src.shared.ui.button_style import (
    apply_button_variant,
    build_button_stylesheet,
)
from src.shared.ui.card import Card
from src.shared.ui.flow_section import FlowSection
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.inline_alert import InlineAlert
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.config_selector_models import SelectorOption


_CONTENT_REQUIREMENTS_HEIGHT = 104


class OfficialPlanEditor(QWidget):
    save_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(
        self,
        values: OfficialPlanEditValues,
        parent=None,
        *,
        master_options: Sequence[SelectorOption] = (),
        template_options: Sequence[SelectorOption] = (),
    ) -> None:
        super().__init__(parent)
        self._initial = values
        self._master_options = tuple(master_options)
        self._template_options = tuple(template_options)
        self._last_document_type_id = values.document_type_id
        self._build_ui()
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("official_plan_editor_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget(scroll)
        content.setObjectName("official_plan_editor_content")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(18, 16, 18, 16)
        self._official_field_rows = {}

        basic_card = Card("公文基本信息", parent=content)
        basic_form = InspectorForm(parent=basic_card)
        self.document_type = StyledComboBox(basic_form)
        self.document_type.set_full_width_mode(True)
        for profile in list_official_document_profiles():
            self.document_type.addItem(profile.label, profile.profile_id)
        index = self.document_type.findData(self._initial.document_type_id)
        if index >= 0:
            self.document_type.setCurrentIndex(index)
        self.organization = _line_edit(
            self._initial.organization,
            "例如：某某市教育局",
            basic_form,
        )
        self.recipient = _line_edit(
            self._initial.recipient,
            "适用时填写主送机关",
            basic_form,
        )
        self.signer = _line_edit(
            self._initial.signer,
            "命令、报告、请示、议案需要填写",
            basic_form,
        )
        basic_form.add_field("文种", self.document_type)
        basic_form.add_field("发文机关", self.organization)
        self._official_field_rows["recipient"] = basic_form.add_field(
            "主送机关",
            self.recipient,
        )
        self._official_field_rows["signer"] = basic_form.add_field(
            "签发人",
            self.signer,
        )
        basic_card.add_widget(basic_form)
        self._content_layout.addWidget(basic_card)

        content_card = Card("起草内容", parent=content)
        content_form = InspectorForm(parent=content_card)
        self.title = _line_edit(
            self._initial.title,
            "可留空，由模型根据内容拟定",
            content_form,
        )
        self.content_requirements = QTextEdit(content_form)
        self.content_requirements.setAcceptRichText(False)
        self.content_requirements.setPlainText(self._initial.content_requirements)
        self.content_requirements.setPlaceholderText(
            "说明发文目的、背景、需落实的事项、对象和时间要求"
        )
        self.content_requirements.setFixedHeight(_CONTENT_REQUIREMENTS_HEIGHT)
        content_form.add_field("标题", self.title)
        content_form.add_field("内容要求", self.content_requirements)
        content_card.add_widget(content_form)
        self._content_layout.addWidget(content_card)

        format_card = Card("版式与交付", parent=content)
        format_form = InspectorForm(parent=format_card)
        self.template = StyledComboBox(format_form)
        self.template.set_full_width_mode(True)
        self._populate_selector_options(
            self.template,
            self._template_options,
            selected_value=self._initial.template_id,
        )
        self.master = StyledComboBox(format_form)
        self.master.set_full_width_mode(True)
        self._populate_selector_options(
            self.master,
            self._master_options,
            selected_value=self._initial.master_id,
        )
        self.delivery_profile = StyledComboBox(format_form)
        self.delivery_profile.set_full_width_mode(True)
        for label, profile_id in (
            ("正式版 Word", OFFICIAL_DELIVERY_FORMAL),
            ("内部审阅版 Word", OFFICIAL_DELIVERY_INTERNAL_REVIEW),
            ("会议纪要与归档套件", OFFICIAL_DELIVERY_MEETING_ARCHIVE),
        ):
            self.delivery_profile.addItem(label, profile_id)
        delivery_index = self.delivery_profile.findData(
            self._initial.delivery_profile
        )
        if delivery_index >= 0:
            self.delivery_profile.setCurrentIndex(delivery_index)
        format_form.add_field("格式模板", self.template)
        format_form.add_field("公文版式", self.master)
        format_form.add_field("交付方式", self.delivery_profile)
        format_card.add_widget(format_form)
        self._content_layout.addWidget(format_card)
        self.document_type.currentIndexChanged.connect(
            self._on_document_type_changed
        )
        self.master.currentIndexChanged.connect(self._sync_template_for_master)
        self._sync_master_for_document_type()
        self._sync_template_for_master()

        formal = FlowSection("版记与附加字段", expanded=False, parent=content)
        formal_form = InspectorForm(parent=formal)
        self.document_no = _line_edit(
            self._initial.document_no,
            "留空将使用“待编”",
            formal_form,
        )
        self.issue_date = _line_edit(
            self._initial.issue_date,
            "留空将暂按当天日期",
            formal_form,
        )
        self.attachment_note = _line_edit(
            self._initial.attachment_note,
            "适用时填写",
            formal_form,
        )
        self.copy_scope = _line_edit(
            self._initial.copy_scope,
            "适用时填写抄送机关",
            formal_form,
        )
        self.issuer = _line_edit(
            self._initial.issuer,
            "适用时填写",
            formal_form,
        )
        self.printing_org = _line_edit(
            self._initial.printing_org,
            "适用时填写",
            formal_form,
        )
        self.printing_date = _line_edit(
            self._initial.printing_date,
            "适用时填写",
            formal_form,
        )
        self.security_level = _line_edit(
            self._initial.security_level,
            "例如：秘密",
            formal_form,
        )
        self.urgency = _line_edit(
            self._initial.urgency,
            "例如：加急",
            formal_form,
        )
        for field_key, label, control in (
            ("document_no", "发文字号", self.document_no),
            ("issue_date", "成文日期", self.issue_date),
            ("attachment_note", "附件说明", self.attachment_note),
            ("copy_scope", "抄送机关", self.copy_scope),
            ("issuer", "落款机关", self.issuer),
            ("printing_org", "印发机关", self.printing_org),
            ("printing_date", "印发日期", self.printing_date),
            ("security_level", "密级", self.security_level),
            ("urgency", "紧急程度", self.urgency),
        ):
            self._official_field_rows[field_key] = formal_form.add_field(
                label,
                control,
            )
        formal.add_widget(formal_form)
        self._content_layout.addWidget(formal)

        meeting = FlowSection("纪要字段", expanded=False, parent=content)
        self._meeting_section = meeting
        meeting_form = InspectorForm(parent=meeting)
        self.meeting_date = _line_edit(
            self._initial.meeting_date,
            "纪要适用",
            meeting_form,
        )
        self.participants = _line_edit(
            self._initial.participants,
            "纪要适用",
            meeting_form,
        )
        self._official_field_rows["meeting_date"] = meeting_form.add_field(
            "会议时间",
            self.meeting_date,
        )
        self._official_field_rows["participants"] = meeting_form.add_field(
            "参会人员",
            self.participants,
        )
        meeting.add_widget(meeting_form)
        self._content_layout.addWidget(meeting)
        self._sync_official_field_visibility()

        output_card = Card("输出", parent=content)
        output_form = InspectorForm(parent=output_card)
        self.output_root = FolderPicker(
            placeholder="请选择生成文件的保存目录",
            parent=output_form,
        )
        self.output_root.set_path(self._initial.output_root)
        output_form.add_field("输出目录", self.output_root)
        output_card.add_widget(output_form)
        self._content_layout.addWidget(output_card)

        self._error = InlineAlert("", variant="error", parent=content)
        self._error.hide()
        self._content_layout.addWidget(self._error)
        self._content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        footer = QWidget(self)
        footer.setObjectName("official_plan_editor_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.setSpacing(8)
        footer_layout.addStretch(1)
        self.cancel_button = QPushButton("取消", footer)
        apply_button_variant(self.cancel_button, "secondary")
        apply_size_class(self.cancel_button, "md")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.save_button = QPushButton("应用修改", footer)
        apply_button_variant(self.save_button, "primary")
        apply_size_class(self.save_button, "md")
        self.save_button.clicked.connect(self._submit)
        footer_layout.addWidget(self.cancel_button)
        footer_layout.addWidget(self.save_button)
        root.addWidget(footer)

    def _values(self) -> OfficialPlanEditValues:
        return OfficialPlanEditValues(
            document_type_id=str(self.document_type.currentData() or "").strip(),
            organization=self.organization.text().strip(),
            content_requirements=(self.content_requirements.toPlainText().strip()),
            title=self.title.text().strip(),
            recipient=self.recipient.text().strip(),
            signer=self.signer.text().strip(),
            document_no=self.document_no.text().strip(),
            issue_date=self.issue_date.text().strip(),
            attachment_note=self.attachment_note.text().strip(),
            copy_scope=self.copy_scope.text().strip(),
            issuer=self.issuer.text().strip(),
            printing_org=self.printing_org.text().strip(),
            printing_date=self.printing_date.text().strip(),
            security_level=self.security_level.text().strip(),
            urgency=self.urgency.text().strip(),
            meeting_date=self.meeting_date.text().strip(),
            participants=self.participants.text().strip(),
            output_root=self.output_root.path().strip(),
            master_id=str(self.master.currentData() or "").strip(),
            template_id=str(self.template.currentData() or "").strip(),
            delivery_profile=str(
                self.delivery_profile.currentData() or ""
            ).strip(),
        )

    def _submit(self) -> None:
        values = self._values()
        try:
            validate_official_plan_edit_values(values)
        except ValueError as exc:
            messages = {
                "official_plan_document_type_required": "请选择公文文种。",
                "official_plan_organization_required": "请填写发文机关。",
                "official_plan_content_requirements_required": (
                    "请填写发文目的和需要落实的事项。"
                ),
                "official_plan_recipient_required": "请填写当前文种的主送机关。",
                "official_plan_signer_required": "请填写当前文种的签发人。",
                "official_plan_master_unavailable": "所选公文版式不可用。",
                "official_plan_master_incompatible": "所选公文版式不支持当前文种。",
                "official_plan_template_unavailable": "所选格式模板不可用。",
                "official_plan_template_incompatible": "所选格式模板与公文版式不兼容。",
                "official_plan_delivery_invalid": "请选择有效的交付方式。",
            }
            self._error.set_message(messages.get(str(exc), "请检查公文信息后再保存。"))
            self._error.show()
            return
        self._error.hide()
        self.save_requested.emit(values)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._content_layout.setSpacing(theme.spacing_md)
        controls = (
            self.organization,
            self.recipient,
            self.signer,
            self.title,
            self.document_no,
            self.issue_date,
            self.attachment_note,
            self.copy_scope,
            self.issuer,
            self.printing_org,
            self.printing_date,
            self.security_level,
            self.urgency,
            self.meeting_date,
            self.participants,
        )
        for control in controls:
            control.setStyleSheet(build_text_input_stylesheet(theme))
            apply_size_class(control, "md")
        self.content_requirements.setStyleSheet(
            build_text_input_stylesheet(
                theme,
                selector="QTextEdit",
                min_height=_CONTENT_REQUIREMENTS_HEIGHT,
            )
        )
        button_style = build_button_stylesheet(theme)
        self.cancel_button.setStyleSheet(button_style)
        self.save_button.setStyleSheet(button_style)
        self.setStyleSheet(
            f"""
            #official_plan_editor_scroll,
            #official_plan_editor_content {{
                background: {theme.bg_window};
                border: none;
            }}
            #official_plan_editor_footer {{
                background: {theme.bg_card};
                border-top: 1px solid {theme.border_light};
            }}
            """
        )

    @staticmethod
    def _populate_selector_options(
        combo: StyledComboBox,
        options: Sequence[SelectorOption],
        *,
        selected_value: str,
    ) -> None:
        for option in options:
            badge_text = "内置" if option.source_type == "builtin" else "自定"
            badge_kind = "neutral" if option.source_type == "builtin" else "user"
            index = combo.add_badged_item(
                option.label,
                option.value,
                badge_text=badge_text,
                badge_kind=badge_kind,
            )
            if option.tooltip:
                combo.setItemData(index, option.tooltip, Qt.ToolTipRole)
            item = getattr(combo.model(), "item", lambda _index: None)(index)
            if item is not None and option.disabled:
                item.setEnabled(False)
        selected = combo.findData(str(selected_value or "").strip())
        if selected >= 0:
            combo.setCurrentIndex(selected)

    def _on_document_type_changed(self, _index: int = -1) -> None:
        previous = self._last_document_type_id
        current = str(self.document_type.currentData() or "").strip()
        self._last_document_type_id = current
        self._sync_master_for_document_type()
        current_delivery = str(
            self.delivery_profile.currentData() or ""
        ).strip()
        if current == "minutes" and current_delivery == OFFICIAL_DELIVERY_FORMAL:
            index = self.delivery_profile.findData(
                OFFICIAL_DELIVERY_MEETING_ARCHIVE
            )
            if index >= 0:
                self.delivery_profile.setCurrentIndex(index)
        elif previous == "minutes" and current_delivery == OFFICIAL_DELIVERY_MEETING_ARCHIVE:
            index = self.delivery_profile.findData(OFFICIAL_DELIVERY_FORMAL)
            if index >= 0:
                self.delivery_profile.setCurrentIndex(index)
        self._sync_official_field_visibility()

    def _sync_official_field_visibility(self) -> None:
        profile_id = str(self.document_type.currentData() or "").strip()
        contract = get_official_document_assembly_contract(profile_id)
        requirements = (
            {
                binding.field_key: binding.resolved_requirement
                for binding in contract.field_bindings
            }
            if contract is not None
            else {}
        )
        for field_key, row in self._official_field_rows.items():
            row.setVisible(
                requirements.get(field_key, "forbidden") != "forbidden"
            )
        self._meeting_section.setVisible(
            any(
                requirements.get(field_key, "forbidden") != "forbidden"
                for field_key in ("meeting_date", "participants")
            )
        )
        self.recipient.setPlaceholderText(
            "必填：请填写主送机关"
            if requirements.get("recipient") == "required"
            else "适用时填写主送机关"
        )
        self.signer.setPlaceholderText(
            "必填：请填写签发人及职务"
            if requirements.get("signer") == "required"
            else "适用时填写签发人"
        )

    def _sync_master_for_document_type(self) -> None:
        document_type_id = str(self.document_type.currentData() or "").strip()
        current_id = str(self.master.currentData() or "").strip()
        current = get_master(current_id, "official") if current_id else None
        if current is not None:
            supported = tuple(current.supported_assembly_types or ())
            if not supported or document_type_id in supported:
                return
        contract = get_official_document_assembly_contract(document_type_id)
        target_id = str(getattr(contract, "master_id", "") or "").strip()
        target_index = self.master.findData(target_id)
        if target_index >= 0:
            self.master.setCurrentIndex(target_index)

    def _sync_template_for_master(self, _index: int = -1) -> None:
        master_id = str(self.master.currentData() or "").strip()
        master = get_master(master_id, "official") if master_id else None
        if master is None:
            return
        current_template = str(self.template.currentData() or "").strip()
        compatible = tuple(master.compatible_template_config_ids or ())
        if not compatible or current_template in compatible:
            return
        preferred = str(master.template_config_id or "").strip()
        index = self.template.findData(preferred)
        if index >= 0:
            self.template.setCurrentIndex(index)


def _line_edit(value: str, placeholder: str, parent=None) -> QLineEdit:
    control = QLineEdit(str(value or ""), parent)
    control.setPlaceholderText(placeholder)
    return control


__all__ = ["OfficialPlanEditor"]
