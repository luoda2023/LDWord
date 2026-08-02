from __future__ import annotations

from pathlib import Path

from src.qt_api import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    Qt,
    QVBoxLayout,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme, theme_rgba


class BatchGenerationSourceArea(RoundedSurfaceFrame):
    """Compact batch-input summary using the quick-execution source grammar."""

    source_document_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("wb_batch_source_area")
        self.setMinimumHeight(70)
        self.setAutoFillBackground(False)

        self._count = 0
        self._source_label = "资料包"
        self._profile_summary = ""
        self._source_document_required = True
        self._source_document_path = ""
        self._document_picker_enabled = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(17, 17, 17, 17)
        layout.setSpacing(8)

        self._icon = QLabel(self)
        self._icon.setObjectName("wb_batch_source_icon")
        self._icon.setFixedSize(36, 36)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)

        self._title = QLabel(self)
        self._title.setObjectName("wb_batch_source_title")
        self._hint = QLabel(self)
        self._hint.setObjectName("wb_batch_source_hint")
        self._hint.setWordWrap(False)
        text_column.addWidget(self._title)
        text_column.addWidget(self._hint)
        layout.addLayout(text_column, 1)

        self._document_button = QPushButton("选择源文档", self)
        self._document_button.setObjectName("wb_batch_source_document")
        self._document_button.setCursor(Qt.PointingHandCursor)
        self._document_button.clicked.connect(self._pick_source_document)
        apply_size_class(self._document_button, "md")
        layout.addWidget(self._document_button, 0, Qt.AlignVCenter)

        bind_theme(self, self._apply_theme)
        self._apply_theme()
        self._refresh()

    @property
    def document_button(self) -> QPushButton:
        return self._document_button

    def title_text(self) -> str:
        """Return the user-visible source title without exposing the QLabel."""

        return self._title.text()

    def hint_text(self) -> str:
        """Return the user-visible source summary without exposing the QLabel."""

        return self._hint.text()

    def set_batch_state(
        self,
        *,
        count: int,
        source_label: str,
        profile_summary: str,
        source_document_required: bool,
        source_document_path: str,
    ) -> None:
        self._count = max(0, int(count or 0))
        self._source_label = str(source_label or "").strip() or "资料包"
        self._profile_summary = str(profile_summary or "").strip()
        self._source_document_required = bool(source_document_required)
        self._source_document_path = str(source_document_path or "").strip()
        self._refresh()

    def set_document_picker_visible(self, visible: bool) -> None:
        self._document_picker_enabled = bool(visible)
        self._refresh()

    def _refresh(self) -> None:
        if self._count:
            self._title.setText(f"已准备 {self._count} 份批次资料")
            summary = self._profile_summary or f"来源：{self._source_label}"
            self._hint.setText(summary)
            self._hint.setToolTip(
                "\n".join(
                    part
                    for part in (
                        f"来源：{self._source_label}",
                        self._profile_summary,
                    )
                    if part
                )
            )
        else:
            self._title.setText("尚未选择批次资料")
            self._hint.setText("请先在资料功能中选择批次，本页仅负责生成")
            self._hint.setToolTip("")

        self._document_button.setVisible(
            self._source_document_required
            and self._document_picker_enabled
        )
        if self._source_document_required:
            if self._source_document_path:
                name = Path(self._source_document_path).name
                self._document_button.setText(name or "更换源文档")
                self._document_button.setToolTip(self._source_document_path)
            else:
                self._document_button.setText("选择源文档")
                self._document_button.setToolTip("选择本批次共用的 DOCX 源文档")
        self._refresh_surface()

    def _pick_source_document(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择批次源文档",
            "",
            "Word 文档 (*.docx)",
        )
        cleaned = str(path or "").strip()
        if not cleaned:
            return
        self._source_document_path = cleaned
        self._refresh()
        self.source_document_selected.emit(cleaned)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._icon.setPixmap(get_icon("layers", 18, theme.primary).pixmap(18, 18))
        self._icon.setStyleSheet(
            f"background: {theme_rgba(theme.primary, 0.06)}; "
            f"border-radius: {theme.radius_sm}px;"
        )
        self._title.setStyleSheet(
            f"font-size: {theme.font_size_md}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {theme.text_primary}; background: transparent;"
        )
        self._hint.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_hint}; "
            "background: transparent;"
        )
        apply_size_class(self._document_button, "md")
        apply_button_variant(self._document_button, "secondary")
        self._refresh_surface()

    def _refresh_surface(self) -> None:
        theme = get_theme()
        self.configure_surface(
            background=(
                theme_rgba(theme.primary, 0.02)
                if self._count
                else theme.bg_card
            ),
            radius=theme.radius_sm,
            border_color=theme.primary if self._count else theme.border,
            border_width=1.0,
        )
        self.update()


__all__ = ["BatchGenerationSourceArea"]
