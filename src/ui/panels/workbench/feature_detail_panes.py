from __future__ import annotations

from src.qt_api import QLabel, QLineEdit, QVBoxLayout, QWidget

from src.shared.ui.card import Card
from src.shared.ui.execution_progress_widget import ExecutionProgressWidget
from src.shared.ui.file_drop_zone import FileDropZone
from src.shared.ui.form_row import FormRow
from src.shared.ui.module_status_list import ModuleStatusList
from src.shared.ui.numbering_preset import NumberingPreset
from src.shared.ui.search_input import SearchInput
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.themed_slider import ThemedSlider
from src.shared.ui.toggle_switch import ToggleSwitch
from src.shared.ui.theme import bind_theme, get_theme


class _FeatureDetailPaneBase(QWidget):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        self._title = QLabel(title, self)
        self._subtitle = QLabel(subtitle, self)
        self._subtitle.setWordWrap(True)
        self._summary = QLabel(self)
        self._summary.setWordWrap(True)

        self._layout.addWidget(self._title)
        self._layout.addWidget(self._subtitle)
        self._layout.addWidget(self._summary)

    def finish_setup(self) -> None:
        self._layout.addStretch(1)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_summary(self, text: str) -> None:
        self._summary.setText(text)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._title.setStyleSheet(
            f"font-size: {theme.font_size_xl}px; font-weight: {theme.font_weight_bold}; color: {theme.text_primary};"
        )
        self._subtitle.setStyleSheet(
            f"font-size: {theme.font_size_md}px; color: {theme.text_secondary};"
        )
        self._summary.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
        )


class HeadingNumberingDetailPane(_FeatureDetailPaneBase):
    """标题编号详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "\u6807\u9898\u7f16\u53f7",
            "\u7ef4\u6301\u4e0e\u5de6\u4fa7\u5bfc\u822a\u6458\u8981\u4e00\u81f4\u7684\u6807\u9898\u7f16\u53f7\u65b9\u6848\uff0c\u53ef\u4ee5\u5feb\u901f\u8c03\u6574\u9884\u8bbe\u3001\u5c42\u7ea7\u6df1\u5ea6\u548c\u76ee\u5f55\u8054\u52a8\u3002",
            parent=parent,
        )

        self._search = SearchInput("\u641c\u7d22\u7f16\u53f7\u9884\u8bbe", self)
        self._search.search_changed.connect(lambda *_: self._refresh_summary())
        self._layout.addWidget(self._search)

        preset_card = Card("\u7f16\u53f7\u9884\u8bbe", parent=self)
        self._preset = NumberingPreset(preset_card)
        self._preset.preset_changed.connect(lambda *_: self._refresh_summary())
        preset_card.add_widget(self._preset)

        self._toc_toggle = ToggleSwitch(preset_card, checked=True)
        self._toc_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        preset_card.add_widget(FormRow("\u76ee\u5f55\u8054\u52a8", self._toc_toggle, parent=preset_card))

        self._subtitle_toggle = ToggleSwitch(preset_card, checked=False)
        self._subtitle_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        preset_card.add_widget(FormRow("\u5b50\u6807\u9898\u7f16\u53f7", self._subtitle_toggle, parent=preset_card))
        self._layout.addWidget(preset_card)

        depth_card = Card("\u5c42\u7ea7\u4e0e\u95f4\u8ddd", parent=self)
        self._depth_slider = ThemedSlider(parent=depth_card)
        self._depth_slider.setRange(1, 6)
        self._depth_slider.setValue(4)
        self._depth_slider.valueChanged.connect(self._update_depth_label)
        self._depth_value = QLabel("4 \u7ea7", depth_card)
        depth_card.add_widget(
            FormRow("\u7f16\u53f7\u6df1\u5ea6", self._depth_slider, suffix_widget=self._depth_value, parent=depth_card)
        )

        self._spacing_slider = ThemedSlider(parent=depth_card)
        self._spacing_slider.setRange(8, 28)
        self._spacing_slider.setValue(16)
        self._spacing_slider.valueChanged.connect(self._update_spacing_label)
        self._spacing_value = QLabel("16 pt", depth_card)
        depth_card.add_widget(
            FormRow("\u6807\u9898\u95f4\u8ddd", self._spacing_slider, suffix_widget=self._spacing_value, parent=depth_card)
        )
        self._layout.addWidget(depth_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_depth_label(self, value: int) -> None:
        self._depth_value.setText(f"{value} \u7ea7")
        self._refresh_summary()

    def _update_spacing_label(self, value: int) -> None:
        self._spacing_value.setText(f"{value} pt")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        preset_text = self._preset.currentText() or "\u672a\u8bbe\u7f6e\u9884\u8bbe"
        toc_text = "\u5df2\u8054\u52a8\u76ee\u5f55" if self._toc_toggle.isChecked() else "\u72ec\u7acb\u7f16\u53f7"
        subtitle_text = "\u5305\u542b\u5b50\u6807\u9898" if self._subtitle_toggle.isChecked() else "\u4ec5\u6807\u9898\u751f\u6548"
        search_text = self._search.text.strip()
        filter_hint = f"\uff0c\u641c\u7d22\uff1a{search_text}" if search_text else ""
        self.set_summary(
            f"\u5f53\u524d\u65b9\u6848\uff1a{preset_text} · {self._depth_slider.value()} \u7ea7\u6df1\u5ea6 · {toc_text} · {subtitle_text}{filter_hint}"
        )


class QuickFillDetailPane(_FeatureDetailPaneBase):
    """内容填充详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "\u5185\u5bb9\u586b\u5145",
            "\u4ece\u7ed3\u6784\u5316\u6570\u636e\u6e90\u9009\u62e9\u6a21\u677f\uff0c\u518d\u51b3\u5b9a\u6620\u5c04\u5f3a\u5ea6\u4e0e\u9884\u89c8\u7b56\u7565\u3002",
            parent=parent,
        )

        template_card = Card("\u573a\u666f\u4e0e\u5360\u4f4d\u89c4\u5219", parent=self)
        self._template_combo = StyledComboBox(template_card)
        self._template_combo.addItems(
            [
                "\u9ed8\u8ba4\u586b\u5145\u6d41\u7a0b",
                "\u6280\u672f\u65b9\u6848\u8bf4\u660e",
                "\u6c47\u62a5\u6f14\u793a\u7a3f",
                "\u5408\u540c\u4ea4\u4ed8\u4ef6",
            ]
        )
        self._template_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())
        template_card.add_widget(FormRow("\u586b\u5145\u6a21\u677f", self._template_combo, parent=template_card))

        self._placeholder_toggle = ToggleSwitch(template_card, checked=True)
        self._placeholder_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        template_card.add_widget(FormRow("\u4fdd\u7559\u672a\u5339\u914d\u5360\u4f4d\u7b26", self._placeholder_toggle, parent=template_card))
        self._layout.addWidget(template_card)

        source_card = Card("\u6570\u636e\u6e90", parent=self)
        self._source_picker = FileDropZone(
            dialog_title="\u9009\u62e9\u586b\u5145\u6570\u636e\u6e90",
            file_filter="Data Files (*.xlsx *.csv *.json);;All Files (*)",
            parent=source_card,
        )
        self._source_picker.file_selected.connect(lambda *_: self._refresh_summary())
        source_card.add_widget(self._source_picker)
        self._source_hint = QLabel(
            "\u652f\u6301 Excel / CSV / JSON\uff0c\u540e\u7eed\u53ef\u7ee7\u7eed\u63a5\u771f\u5b9e\u6620\u5c04\u8868\u3002",
            source_card,
        )
        self._source_hint.setWordWrap(True)
        source_card.add_widget(self._source_hint)
        self._layout.addWidget(source_card)

        behavior_card = Card("\u9884\u89c8\u4e0e\u6620\u5c04\u5f3a\u5ea6", parent=self)
        self._confidence_slider = ThemedSlider(parent=behavior_card)
        self._confidence_slider.setRange(50, 100)
        self._confidence_slider.setValue(78)
        self._confidence_slider.valueChanged.connect(self._update_confidence_label)
        self._confidence_value = QLabel("78%", behavior_card)
        behavior_card.add_widget(
            FormRow("\u6620\u5c04\u4fe1\u5fc3\u5ea6", self._confidence_slider, suffix_widget=self._confidence_value, parent=behavior_card)
        )

        self._preview_toggle = ToggleSwitch(behavior_card, checked=True)
        self._preview_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        behavior_card.add_widget(FormRow("\u81ea\u52a8\u9884\u89c8", self._preview_toggle, parent=behavior_card))
        self._layout.addWidget(behavior_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_confidence_label(self, value: int) -> None:
        self._confidence_value.setText(f"{value}%")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        template_name = self._template_combo.currentText() or "\u672a\u9009\u62e9\u6a21\u677f"
        source_name = self._source_picker.file_path() or "\u672a\u6302\u8f7d\u6570\u636e\u6e90"
        source_label = source_name.split("\\")[-1] if source_name else "\u672a\u6302\u8f7d\u6570\u636e\u6e90"
        placeholder_text = "\u4fdd\u7559\u672a\u5339\u914d\u5360\u4f4d\u7b26" if self._placeholder_toggle.isChecked() else "\u76f4\u63a5\u843d\u5730\u66ff\u6362"
        preview_text = "\u5f00\u542f\u81ea\u52a8\u9884\u89c8" if self._preview_toggle.isChecked() else "\u4ec5\u4fdd\u5b58\u7ed3\u679c"
        self.set_summary(
            f"\u5f53\u524d\u6d41\u7a0b\uff1a{template_name} · \u6570\u636e\u6e90 {source_label} · \u4fe1\u5fc3\u5ea6 {self._confidence_slider.value()}% · {placeholder_text} · {preview_text}"
        )

    def _apply_theme(self) -> None:
        super()._apply_theme()
        theme = get_theme()
        self._source_hint.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")


class ModuleControlDetailPane(_FeatureDetailPaneBase):
    """模块控制详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "\u6a21\u5757\u63a7\u5236",
            "\u5728\u8fd9\u91cc\u67e5\u770b\u6a21\u5757\u6267\u884c\u987a\u5e8f\u548c\u5e76\u53d1\u7b56\u7565\uff0c\u8c03\u6574\u4f18\u5148\u7ea7\u65f6\u5de6\u4fa7\u5361\u7247\u4f1a\u7acb\u5373\u53cd\u6620\u3002",
            parent=parent,
        )

        queue_card = Card("\u5f53\u524d\u6a21\u5757\u961f\u5217", parent=self)
        self._status_list = ModuleStatusList(queue_card)
        self._status_list.add_module("heading", "\u6807\u9898\u89c4\u8303\u5316")
        self._status_list.add_module("outline", "\u7ed3\u6784\u68c0\u67e5")
        self._status_list.add_module("assemble", "\u683c\u5f0f\u7ec4\u88c5")
        self._status_list.update_status("heading", "running", 45)
        self._status_list.update_status("outline", "queued", 0)
        self._status_list.update_status("assemble", "queued", 0)
        queue_card.add_widget(self._status_list)
        self._layout.addWidget(queue_card)

        tune_card = Card("\u8c03\u5ea6\u53c2\u6570", parent=self)
        self._module_combo = StyledComboBox(tune_card)
        self._module_combo.addItems(["\u6807\u9898\u89c4\u8303\u5316", "\u7ed3\u6784\u68c0\u67e5", "\u683c\u5f0f\u7ec4\u88c5"])
        self._module_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())
        tune_card.add_widget(FormRow("\u5f53\u524d\u6a21\u5757", self._module_combo, parent=tune_card))

        self._concurrency_slider = ThemedSlider(parent=tune_card)
        self._concurrency_slider.setRange(1, 5)
        self._concurrency_slider.setValue(3)
        self._concurrency_slider.valueChanged.connect(self._update_concurrency_label)
        self._concurrency_value = QLabel("3 \u4e2a\u5e76\u53d1\u69fd", tune_card)
        tune_card.add_widget(
            FormRow("\u5e76\u53d1\u69fd\u4f4d", self._concurrency_slider, suffix_widget=self._concurrency_value, parent=tune_card)
        )

        self._retry_toggle = ToggleSwitch(tune_card, checked=True)
        self._retry_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        tune_card.add_widget(FormRow("\u5931\u8d25\u540e\u81ea\u52a8\u91cd\u8bd5", self._retry_toggle, parent=tune_card))
        self._layout.addWidget(tune_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_concurrency_label(self, value: int) -> None:
        self._concurrency_value.setText(f"{value} \u4e2a\u5e76\u53d1\u69fd")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        module_name = self._module_combo.currentText() or "\u672a\u9009\u62e9\u6a21\u5757"
        retry_text = "\u5f00\u542f\u81ea\u52a8\u91cd\u8bd5" if self._retry_toggle.isChecked() else "\u4ec5\u624b\u52a8\u5904\u7406"
        self.set_summary(
            f"\u5f53\u524d\u805a\u7126\uff1a{module_name} · {self._concurrency_slider.value()} \u4e2a\u5e76\u53d1\u69fd · {retry_text}"
        )


class OutputSettingsDetailPane(_FeatureDetailPaneBase):
    """输出设置详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "\u8f93\u51fa\u8bbe\u7f6e",
            "\u5b9a\u4e49\u8f93\u51fa\u8def\u5f84\u3001\u547d\u540d\u89c4\u5219\u3001\u5bfc\u51fa\u683c\u5f0f\u4e0e\u4ea4\u4ed8\u540e\u52a8\u4f5c\uff0c\u4fdd\u6301\u4e0e\u5de6\u4fa7\u5361\u7247\u6458\u8981\u4e00\u81f4\u3002",
            parent=parent,
        )

        route_card = Card("\u8f93\u51fa\u8def\u5f84", parent=self)
        self._directory_input = QLineEdit(route_card)
        self._directory_input.setPlaceholderText("D:\\Projects\\Lark\\output")
        self._directory_input.textChanged.connect(lambda *_: self._refresh_summary())
        route_card.add_widget(FormRow("\u76ee\u6807\u76ee\u5f55", self._directory_input, parent=route_card))

        self._file_rule_input = QLineEdit(route_card)
        self._file_rule_input.setPlaceholderText("{template}_{date}_{original}")
        self._file_rule_input.textChanged.connect(lambda *_: self._refresh_summary())
        route_card.add_widget(FormRow("\u547d\u540d\u89c4\u5219", self._file_rule_input, parent=route_card))
        self._layout.addWidget(route_card)

        delivery_card = Card("\u5bfc\u51fa\u7b56\u7565", parent=self)
        self._format_combo = StyledComboBox(delivery_card)
        self._format_combo.addItems(["Word (.docx)", "PDF", "Markdown", "HTML \u62a5\u544a"])
        self._format_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())
        delivery_card.add_widget(FormRow("\u8f93\u51fa\u683c\u5f0f", self._format_combo, parent=delivery_card))

        self._auto_open_toggle = ToggleSwitch(delivery_card, checked=True)
        self._auto_open_toggle.toggled_signal.connect(lambda *_: self._refresh_summary())
        delivery_card.add_widget(FormRow("\u5bfc\u51fa\u540e\u81ea\u52a8\u6253\u5f00", self._auto_open_toggle, parent=delivery_card))

        self._quality_slider = ThemedSlider(parent=delivery_card)
        self._quality_slider.setRange(60, 100)
        self._quality_slider.setValue(88)
        self._quality_slider.valueChanged.connect(self._update_quality_label)
        self._quality_value = QLabel("88%", delivery_card)
        delivery_card.add_widget(
            FormRow("\u5bfc\u51fa\u8d28\u91cf", self._quality_slider, suffix_widget=self._quality_value, parent=delivery_card)
        )
        self._layout.addWidget(delivery_card)

        self._refresh_summary()
        self.finish_setup()

    def _update_quality_label(self, value: int) -> None:
        self._quality_value.setText(f"{value}%")
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        directory = self._directory_input.text().strip() or "output"
        rule = self._file_rule_input.text().strip() or "{template}_{date}_{original}"
        auto_open = "\u81ea\u52a8\u6253\u5f00\u6210\u54c1" if self._auto_open_toggle.isChecked() else "\u4ec5\u4fdd\u7559\u5230\u76ee\u5f55"
        self.set_summary(
            f"\u5f53\u524d\u8def\u5f84\uff1a{directory} · \u547d\u540d\uff1a{rule} · \u683c\u5f0f\uff1a{self._format_combo.currentText()} · {auto_open}"
        )


class ExecutionHistoryDetailPane(_FeatureDetailPaneBase):
    """执行历史详情页。"""

    def __init__(self, parent=None):
        super().__init__(
            "\u6267\u884c\u5386\u53f2",
            "\u67e5\u770b\u6700\u8fd1\u4e00\u6b21\u8fd0\u884c\u7684\u8fdb\u5ea6\u3001\u6a21\u5757\u72b6\u6001\u4e0e\u67e5\u770b\u6a21\u5f0f\uff0c\u540e\u7eed\u53ef\u7ee7\u7eed\u63a5\u5165\u771f\u5b9e\u65e5\u5fd7\u6d41\u3002",
            parent=parent,
        )

        self._search = SearchInput("\u641c\u7d22\u5386\u53f2\u8bb0\u5f55", self)
        self._search.search_changed.connect(lambda *_: self._refresh_summary())
        self._layout.addWidget(self._search)

        latest_card = Card("\u6700\u65b0\u8fd0\u884c\u6982\u89c8", parent=self)
        self._progress_widget = ExecutionProgressWidget(latest_card)
        self._progress_widget.set_progress(3, 5, "\u6a21\u5757\u6267\u884c")
        self._progress_widget.update_module_status("\u6a21\u5757\u6267\u884c", "running", 42)
        self._progress_widget.update_module_status("\u62a5\u544a\u751f\u6210", "queued", 0)
        self._progress_widget.append_log("info", "\u6700\u8fd1\u4e00\u6b21\u8fd0\u884c\u5df2\u8fdb\u5165\u6a21\u5757\u6267\u884c\u9636\u6bb5\u3002")
        latest_card.add_widget(self._progress_widget)

        self._module_list = ModuleStatusList(latest_card)
        self._module_list.add_module("heading", "\u6807\u9898\u7f16\u53f7")
        self._module_list.add_module("fill", "\u5185\u5bb9\u586b\u5145")
        self._module_list.add_module("export", "\u8f93\u51fa\u5c01\u88c5")
        self._module_list.update_status("heading", "completed", 100)
        self._module_list.update_status("fill", "running", 42)
        self._module_list.update_status("export", "queued", 0)
        latest_card.add_widget(self._module_list)
        self._layout.addWidget(latest_card)

        filter_card = Card("\u67e5\u770b\u6a21\u5f0f", parent=self)
        self._view_mode_combo = StyledComboBox(filter_card)
        self._view_mode_combo.addItems(["\u5b8c\u6574\u65e5\u5fd7", "\u4ec5\u770b\u8b66\u544a", "\u9519\u8bef\u4e0e\u6458\u8981"])
        self._view_mode_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())
        filter_card.add_widget(FormRow("\u65e5\u5fd7\u89c6\u56fe", self._view_mode_combo, parent=filter_card))
        self._layout.addWidget(filter_card)

        self._refresh_summary()
        self.finish_setup()

    def _refresh_summary(self) -> None:
        filter_text = self._search.text.strip()
        filter_hint = f"\uff0c\u5173\u952e\u5b57\uff1a{filter_text}" if filter_text else ""
        self.set_summary(
            f"\u5f53\u524d\u67e5\u770b\uff1a{self._view_mode_combo.currentText()} · \u6700\u65b0\u4e00\u6b21\u8fd0\u884c\u4ecd\u5728\u8fdb\u884c{filter_hint}"
        )
