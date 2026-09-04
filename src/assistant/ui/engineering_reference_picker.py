# -*- coding: utf-8 -*-
"""Engineering reference sample picker for the AI assistant composer.

Lists curated real-world engineering documents (from the user-level manifest)
grouped by project stage.  Picking a sample attaches it to the composer and
pre-fills a prompt so chapter-by-chapter authoring learns from the sample.
"""
from __future__ import annotations

from src.config.engineering_reference import (
    engineering_stage_label,
    list_engineering_reference_samples,
)
from src.qt_api import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role


class _SampleRow(QWidget):
    """One selectable sample card."""

    def __init__(self, sample, parent=None) -> None:
        super().__init__(parent)
        self.sample = sample
        self.setObjectName("engineering_reference_sample_row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 12, 12)
        row.setSpacing(12)

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)

        title = QLabel(sample.name, self)
        title.setObjectName("engineering_reference_sample_title")
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setToolTip(sample.path or "")
        apply_text_role(title, TextRole.NAVIGATION_TITLE_ACTIVE)
        column.addWidget(title)

        meta_parts = [engineering_stage_label(sample.stage), sample.kind]
        if sample.note:
            meta_parts.append(sample.note)
        subtitle = QLabel(" · ".join(part for part in meta_parts if part), self)
        subtitle.setObjectName("engineering_reference_sample_subtitle")
        subtitle.setWordWrap(True)
        subtitle.setTextInteractionFlags(Qt.TextSelectableByMouse)
        apply_text_role(subtitle, TextRole.CAPTION)
        column.addWidget(subtitle)

        row.addLayout(column, 1)

        self._use_button = QPushButton(
            "选用此范本" if sample.available else "文件缺失",
            self,
        )
        self._use_button.setEnabled(sample.available)
        self._use_button.setCursor(Qt.PointingHandCursor)
        apply_size_class(self._use_button, "sm")
        apply_button_variant(
            self._use_button,
            "primary" if sample.available else "secondary",
        )
        row.addWidget(self._use_button, 0, Qt.AlignVCenter)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def connect_use(self, callback) -> None:
        self._use_button.clicked.connect(callback)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#engineering_reference_sample_row {{
                background: {theme.bg_window};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            QLabel#engineering_reference_sample_title {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
            }}
            QLabel#engineering_reference_sample_subtitle {{
                color: {theme.text_secondary};
                background: transparent;
                border: none;
            }}
            """
        )


class EngineeringReferencePicker(BaseDialog):
    """Choose one engineering sample to attach and learn from."""

    def __init__(self, parent=None) -> None:
        super().__init__(
            "工程范本库",
            icon_style="info",
            parent=parent,
        )
        self._selected_path = ""
        self._selected_prompt = ""
        self._samples = list_engineering_reference_samples()
        # BaseDialog defaults to a 460-600px width band; give the library a
        # roomier, still centered canvas so rows and subtitles breathe.
        self.setMinimumWidth(560)
        self.setMaximumWidth(780)
        self.content_layout.setContentsMargins(24, 2, 24, 0)

        count = len(self._samples)
        caption = QLabel(
            f"从工程范本库选一份真实文档（共 {count} 份）。软件会把它作为附件，"
            "AI 按它的章节目录与写作惯例，分章节起草一份同类的工程文件。",
            self,
        )
        caption.setWordWrap(True)
        caption.setTextInteractionFlags(Qt.TextSelectableByMouse)
        apply_text_role(caption, TextRole.BODY)
        self.content_layout.addWidget(caption)

        if not self._samples:
            empty = QLabel(
                "还没有可用的工程范本。请先在用户数据目录 "
                "config_library/engineering_reference/manifest.json 配置范本清单，"
                "并确保文件路径可访问，然后重试。",
                self,
            )
            empty.setWordWrap(True)
            empty.setTextInteractionFlags(Qt.TextSelectableByMouse)
            apply_text_role(empty, TextRole.BODY)
            self.content_layout.addWidget(empty)
        else:
            self.content_layout.addWidget(self._build_scroll_list(), 1)

        self._close_button = self.add_secondary_button("关闭")
        self._close_button.clicked.connect(self.reject)

        bind_theme(self, self._apply_shell_theme)
        self._apply_shell_theme()
        self.resize(720, 560)

    def _build_scroll_list(self) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setObjectName("engineering_reference_scroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)

        host = QWidget(scroll)
        host.setObjectName("engineering_reference_host")
        host.setAttribute(Qt.WA_StyledBackground, True)
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 6, 0)
        host_layout.setSpacing(8)

        current_stage = None
        for sample in self._samples:
            if sample.stage != current_stage:
                current_stage = sample.stage
                heading = QLabel(engineering_stage_label(current_stage), host)
                heading.setObjectName("engineering_reference_stage_heading")
                heading.setTextInteractionFlags(Qt.TextSelectableByMouse)
                apply_text_role(heading, TextRole.CAPTION)
                host_layout.addWidget(heading)
            row = _SampleRow(sample, host)
            row.connect_use(
                lambda _checked=False, s=sample: self._choose(s)
            )
            host_layout.addWidget(row)
        host_layout.addStretch(1)
        scroll.setWidget(host)
        return scroll

    def _choose(self, sample) -> None:
        self._selected_path = str(sample.path or "")
        self._selected_prompt = sample.recommended_prompt()
        self.accept()

    def selected_path(self) -> str:
        return self._selected_path

    def selected_prompt(self) -> str:
        return self._selected_prompt

    def _apply_shell_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QScrollArea#engineering_reference_scroll,
            QWidget#engineering_reference_host {{
                background: transparent;
                border: none;
            }}
            QScrollArea#engineering_reference_scroll QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollArea#engineering_reference_scroll QScrollBar::handle:vertical {{
                background: {theme.border};
                border-radius: 3px;
                min-height: 28px;
            }}
            QScrollArea#engineering_reference_scroll QScrollBar::add-line:vertical,
            QScrollArea#engineering_reference_scroll QScrollBar::sub-line:vertical,
            QScrollArea#engineering_reference_scroll QScrollBar::add-page:vertical,
            QScrollArea#engineering_reference_scroll QScrollBar::sub-page:vertical {{
                background: transparent;
                border: none;
                height: 0;
            }}
            QLabel#engineering_reference_stage_heading {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
                padding-top: 4px;
            }}
            """
        )


__all__ = ["EngineeringReferencePicker"]
