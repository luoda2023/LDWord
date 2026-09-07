# -*- coding: utf-8 -*-
"""Visual typesetting-template plugin manager.

The layout/formatting rules for AI-authored engineering documents behave like
a *visual plugin*: the user can create, name and adjust templates (page size,
fonts, heading numbering, table style, figure placeholders, wording style)
and pick which one is active.  The authoring pipeline then injects the active
template's rules into every per-chapter prompt and the docx composer follows
the same template.
"""
from __future__ import annotations

from collections.abc import Callable

from src.assistant.application.typesetting_templates import (
    TypesettingTemplate,
    TypesettingTemplateStore,
)
from src.qt_api import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role


def _label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    apply_text_role(label, TextRole.BODY)
    return label


def _field_row(layout: QVBoxLayout, text: str, widget: QWidget) -> None:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)
    caption = QLabel(text)
    apply_text_role(caption, TextRole.CAPTION)
    row.addWidget(caption)
    row.addWidget(widget, 1)
    layout.addLayout(row)


class TypesettingTemplateDialog(BaseDialog):
    """List + edit named visual typesetting plugins and activate one."""

    def __init__(self, parent=None, store: TypesettingTemplateStore | None = None) -> None:
        super().__init__(
            "排版模板（可视化插件）",
            icon_style="info",
            parent=parent,
        )
        self._store = store if store is not None else TypesettingTemplateStore()
        self._dirty_signal: list[Callable[[], None]] = []
        self.setMinimumWidth(620)
        self.setMaximumWidth(900)
        self.resize(820, 620)

        body = QHBoxLayout()
        body.setContentsMargins(18, 2, 18, 0)
        body.setSpacing(14)

        # ---- left: template list + actions -------------------------------
        left = QVBoxLayout()
        left.setSpacing(8)
        list_title = QLabel("模板列表")
        apply_text_role(list_title, TextRole.NAVIGATION_TITLE_ACTIVE)
        left.addWidget(list_title)

        self._list = QListWidget()
        self._list.setObjectName("typesetting_template_list")
        self._list.setMinimumWidth(210)
        self._list.currentItemChanged.connect(self._on_select)
        left.addWidget(self._list, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        add_btn = QPushButton("＋ 新建")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._create_template)
        apply_size_class(add_btn, "sm")
        apply_button_variant(add_btn, "secondary")
        row.addWidget(add_btn)
        dup_btn = QPushButton("⧉ 复制")
        dup_btn.setCursor(Qt.PointingHandCursor)
        dup_btn.clicked.connect(self._duplicate_template)
        apply_size_class(dup_btn, "sm")
        apply_button_variant(dup_btn, "secondary")
        row.addWidget(dup_btn)
        del_btn = QPushButton("删除")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(self._delete_template)
        apply_size_class(del_btn, "sm")
        apply_button_variant(del_btn, "danger")
        row.addWidget(del_btn)
        left.addLayout(row)
        body.addLayout(left, 0)

        # ---- right: editable fields for the selected template -------------
        right = QVBoxLayout()
        right.setSpacing(8)
        right_title = QLabel("模板设置")
        apply_text_role(right_title, TextRole.NAVIGATION_TITLE_ACTIVE)
        right.addWidget(right_title)

        scroll = QScrollArea()
        scroll.setObjectName("typesetting_template_scroll")
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        host = QWidget(scroll)
        host.setObjectName("typesetting_template_host")
        host.setAttribute(Qt.WA_StyledBackground, True)
        self._editor = QVBoxLayout(host)
        self._editor.setContentsMargins(4, 0, 10, 0)
        self._editor.setSpacing(8)
        scroll.setWidget(host)
        right.addWidget(scroll, 1)

        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        reset_btn = QPushButton("↺ 恢复默认模板")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_default)
        apply_button_variant(reset_btn, "secondary")
        act_row.addWidget(reset_btn)
        act_row.addStretch(1)
        act_btn = QPushButton("✔ 应用为当前排版模板")
        act_btn.setCursor(Qt.PointingHandCursor)
        act_btn.clicked.connect(self._apply_active)
        apply_button_variant(act_btn, "primary")
        act_row.addWidget(act_btn)
        right.addLayout(act_row)
        body.addLayout(right, 1)

        self.content_layout.addLayout(body, 1)

        hint = _label(
            "提示：AI 逐章生成时，会把“当前排版模板”的字体/表格/插图占位规则写入每一章的"
            "写作要求；Word 排版合成时同样读取该模板。需要插图的位置 AI 只插入 "
            "【图：说明】 占位符，后续再接入真实图片。",
            self,
        )
        self.content_layout.addWidget(hint)

        self._close_button = self.add_secondary_button("完成")
        self._close_button.clicked.connect(self.accept)

        self._widgets: dict[str, QWidget] = {}
        self._current_id = ""
        bind_theme(self, self._apply_shell_theme)
        self._apply_shell_theme()
        self._reload_list(select_active=True)

    # ---- public ---------------------------------------------------------
    def on_template_changed(self, callback: Callable[[], None]) -> None:
        """Call after a template is saved or the active template changes."""
        self._dirty_signal.append(callback)

    # ---- list handling ----------------------------------------------------
    def _reload_list(self, *, select_active: bool = False) -> None:
        self._templates = {
            template.template_id: template
            for template in self._store.list_templates()
        }
        active_id = self._store.active_template_id()
        self._list.blockSignals(True)
        self._list.clear()
        for template_id, template in self._templates.items():
            item = QListWidgetItem(self._template_list_label(template, template_id == active_id))
            item.setData(Qt.UserRole, template_id)
            self._list.addItem(item)
        self._list.blockSignals(False)
        target = active_id if select_active else self._current_id
        if target in self._templates:
            index = list(self._templates).index(target)
            self._list.setCurrentRow(index)
            self._render_editor(self._templates[target])

    def _template_list_label(self, template: TypesettingTemplate, active: bool) -> str:
        marker = "● " if active else ""
        return f"{marker}{template.name}"

    def _on_select(self, current: QListWidgetItem | None, _previous=None) -> None:
        if current is None:
            return
        template_id = str(current.data(Qt.UserRole) or "")
        template = self._templates.get(template_id)
        if template is not None:
            self._render_editor(template)

    # ---- editor ------------------------------------------------------------
    def _clear_editor(self) -> None:
        while self._editor.count():
            item = self._editor.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._widgets = {}

    def _render_editor(self, template: TypesettingTemplate) -> None:
        self._current_id = template.template_id
        self._clear_editor()

        def spin(*, minimum: int, maximum: int, value: int) -> QSpinBox:
            box = QSpinBox()
            box.setRange(minimum, maximum)
            box.setValue(int(value))
            box.setSuffix(" pt")
            return box

        name = QLineEdit(template.name)
        name.setPlaceholderText("模板名称")
        name.setObjectName("typesetting_template_name")
        apply_size_class(name, "md")
        self._editor.addWidget(_label("名称", self))
        self._editor.addWidget(name)
        self._widgets["name"] = name

        page_box = QGroupBox("页面")
        page_layout = QVBoxLayout(page_box)
        size_combo = QComboBox()
        size_combo.addItems(["A4", "A3", "B5", "16开"])
        size_combo.setCurrentText(str(template.page.get("size") or "A4"))
        _field_row(page_layout, "纸张", size_combo)
        self._widgets["page_size"] = size_combo

        margin_row = QHBoxLayout()
        margin_row.setSpacing(8)
        margins = {}
        for key, text in (
            ("margin_top_mm", "上"),
            ("margin_bottom_mm", "下"),
            ("margin_left_mm", "左"),
            ("margin_right_mm", "右"),
        ):
            box = QDoubleSpinBox()
            box.setRange(5.0, 80.0)
            box.setDecimals(1)
            box.setValue(float(template.page.get(key) or 25.0))
            box.setSuffix(" mm")
            margin_row.addWidget(QLabel(text))
            margin_row.addWidget(box, 1)
            margins[key] = box
        page_layout.addLayout(margin_row)
        self._widgets["page_margins"] = margins
        self._editor.addWidget(page_box)

        font_box = QGroupBox("字体")
        font_layout = QVBoxLayout(font_box)
        body_cn = QLineEdit(str(template.fonts.get("body_cn") or "仿宋_GB2312"))
        _field_row(font_layout, "正文字体", body_cn)
        body_size = spin(minimum=9, maximum=36, value=int(template.fonts.get("body_size_pt") or 14))
        _field_row(font_layout, "正文字号", body_size)
        h1_cn = QLineEdit(str(template.fonts.get("heading1_cn") or "黑体"))
        _field_row(font_layout, "章标题字体", h1_cn)
        h1_size = spin(minimum=9, maximum=48, value=int(template.fonts.get("heading1_size_pt") or 16))
        _field_row(font_layout, "章标题字号", h1_size)
        self._widgets["fonts"] = {
            "body_cn": body_cn,
            "body_size_pt": body_size,
            "heading1_cn": h1_cn,
            "heading1_size_pt": h1_size,
        }
        self._editor.addWidget(font_box)

        style_box = QGroupBox("表格与插图")
        style_layout = QVBoxLayout(style_box)
        table_combo = QComboBox()
        table_combo.addItems(["three_line", "full_grid", "color_table", "none"])
        table_combo.setCurrentText(str(template.tables.get("style_key") or "three_line"))
        _field_row(style_layout, "表格样式", table_combo)
        self._widgets["table_style"] = table_combo
        prefer_table = QCheckBox("数据型内容一律用表格（清单/参数/进度等）")
        prefer_table.setChecked(bool(template.tables.get("prefer_table_for_data", True)))
        style_layout.addWidget(prefer_table)
        self._widgets["prefer_table"] = prefer_table
        placeholder = QLineEdit(str(template.figures.get("placeholder_prefix") or "【图"))
        _field_row(style_layout, "插图占位前缀", placeholder)
        self._widgets["figure_prefix"] = placeholder
        self._editor.addWidget(style_box)

        knowledge_box = QGroupBox("文风指导")
        knowledge_layout = QVBoxLayout(knowledge_box)
        guidance = QLineEdit(
            str(template.knowledge.get("style_guidance") or "")
            or "用词客观专业，先写总体原则再展开措施；量化指标优先；同章内避免空话套话。"
        )
        _field_row(knowledge_layout, "文风要求", guidance)
        self._widgets["guidance"] = guidance
        self._editor.addWidget(knowledge_box)

        self._editor.addStretch(1)

    # ---- mutations ---------------------------------------------------------
    def _current_template(self) -> TypesettingTemplate | None:
        return self._templates.get(self._current_id)

    def _collect_values(self) -> TypesettingTemplate:
        template = self._current_template()
        if template is None:
            raise ValueError("no template selected")
        fonts = dict(template.fonts)
        fonts.update(
            {
                "body_cn": str(self._widgets["fonts"]["body_cn"].text() or "仿宋_GB2312"),
                "body_size_pt": int(self._widgets["fonts"]["body_size_pt"].value()),
                "heading1_cn": str(self._widgets["fonts"]["heading1_cn"].text() or "黑体"),
                "heading1_size_pt": int(self._widgets["fonts"]["heading1_size_pt"].value()),
            }
        )
        page = dict(template.page)
        margins = self._widgets["page_margins"]
        for key, box in margins.items():
            page[key] = round(float(box.value()), 1)
        page["size"] = str(self._widgets["page_size"].currentText() or "A4")
        tables = dict(template.tables)
        tables["style_key"] = str(self._widgets["table_style"].currentText() or "three_line")
        tables["prefer_table_for_data"] = bool(self._widgets["prefer_table"].isChecked())
        figures = dict(template.figures)
        figures["placeholder_prefix"] = str(
            self._widgets["figure_prefix"].text() or "【图"
        )
        knowledge = dict(template.knowledge)
        knowledge["style_guidance"] = str(self._widgets["guidance"].text() or "")
        return TypesettingTemplate(
            template_id=template.template_id,
            name=str(self._widgets["name"].text() or template.name or "未命名模板"),
            page=page,
            fonts=fonts,
            headings=dict(template.headings),
            tables=tables,
            figures=figures,
            knowledge=knowledge,
            description=template.description,
            updated_at=template.updated_at,
            is_default=template.is_default,
        )

    def _save_current(self) -> None:
        try:
            updated = self._store.save(self._collect_values())
        except (ValueError, OSError) as exc:
            from src.shared.ui.dialogs import warning as dialog_warning

            dialog_warning("保存失败", str(exc), parent=self)
            return
        self._templates[updated.template_id] = updated
        active_id = self._store.active_template_id()
        self._reload_list(select_active=False)
        if updated.template_id == active_id:
            for callback in self._dirty_signal:
                try:
                    callback()
                except Exception:
                    pass

    def _create_template(self) -> None:
        base_id = "template"
        index = 1
        existing = set(self._templates)
        while f"{base_id}{index}" in existing:
            index += 1
        template_id = f"{base_id}{index}"
        seed = self._current_template() or self._store.get("engineering_standard")
        data = seed.to_dict()
        data["template_id"] = template_id
        data["name"] = f"模板 {index}"
        data["is_default"] = False
        template = self._store.save(TypesettingTemplate.from_dict(data))
        self._templates[template_id] = template
        self._reload_list(select_active=False)
        self._list.setCurrentRow(list(self._templates).index(template_id))
        self._render_editor(template)

    def _duplicate_template(self) -> None:
        self._create_template()

    def _delete_template(self) -> None:
        template = self._current_template()
        if template is None:
            return
        if template.is_default or template.template_id == "engineering_standard":
            from src.shared.ui.dialogs import info as dialog_info

            dialog_info("不能删除", "内置默认模板不可删除。", parent=self)
            return
        if self._store.delete(template.template_id):
            self._templates.pop(template.template_id, None)
            self._reload_list(select_active=True)

    def _reset_default(self) -> None:
        """Restore the built-in default template to its original state."""
        from src.shared.ui.dialogs import confirm as dialog_confirm
        from src.shared.ui.dialogs import info as dialog_info

        ok = dialog_confirm(
            "恢复默认模板",
            "将把「内置默认模板」恢复为原始出厂设置，覆盖当前对该模板的所有修改。\n\n"
            "是否继续？",
            destructive=True,
            parent=self,
        )
        if not ok:
            return
        try:
            restored = self._store.save_default()
        except (ValueError, OSError) as exc:
            from src.shared.ui.dialogs import warning as dialog_warning

            dialog_warning("恢复失败", str(exc), parent=self)
            return
        self._templates[restored.template_id] = restored
        self._reload_list(select_active=True)
        dialog_info("已恢复", "内置默认模板已恢复为出厂设置。", parent=self)

    def _apply_active(self) -> None:
        template = self._current_template()
        if template is None:
            return
        self._save_current()
        try:
            self._store.set_active_template_id(template.template_id)
        except (ValueError, OSError) as exc:
            from src.shared.ui.dialogs import warning as dialog_warning

            dialog_warning("无法应用", str(exc), parent=self)
            return
        self._reload_list(select_active=True)
        for callback in self._dirty_signal:
            try:
                callback()
            except Exception:
                pass

    def _apply_shell_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QListWidget#typesetting_template_list {{
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
                padding: 4px;
                font-size: {theme.font_size_sm}px;
            }}
            QListWidget#typesetting_template_list::item {{
                padding: 7px 8px;
                border-radius: {theme.radius_sm}px;
                color: {theme.text_primary};
            }}
            QListWidget#typesetting_template_list::item:selected {{
                background: {theme.primary};
                color: {theme.text_on_primary};
            }}
            QScrollArea#typesetting_template_scroll,
            QWidget#typesetting_template_host {{
                background: transparent;
                border: none;
            }}
            QGroupBox {{
                color: {theme.text_primary};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
                margin-top: 10px;
                padding: 8px 10px 10px 10px;
                font-size: {theme.font_size_sm}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: {theme.primary};
            }}
            """
        )


__all__ = ["TypesettingTemplateDialog"]
