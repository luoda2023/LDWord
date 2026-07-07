"""Themed QDoubleSpinBox matching the shared input control metrics."""

from __future__ import annotations

from src.qt_api import QDoubleSpinBox, QEvent, QPainter, Qt

from src.shared.ui.input_metrics import (
    build_input_editor_stylesheet,
    configure_input_line_edit,
    draw_input_surface,
    draw_spin_chevrons,
    sync_input_line_edit_geometry,
)
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.theme import bind_theme, get_theme


class StyledSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox with shared input text geometry and custom chrome."""

    _id_counter = 0

    def __init__(self, parent=None):
        super().__init__(parent)

        self._style_initialized = False
        StyledSpinBox._id_counter += 1
        spin_id = StyledSpinBox._id_counter
        self.setObjectName(f"styled_spin_{spin_id}")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._editor_widget = None
        self._syncing_editor_geometry = False

        apply_size_class(self, "md")
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._style_initialized = True
        self._refresh_style()
        bind_theme(self, self._refresh_style)

    def setObjectName(self, name: str) -> None:  # noqa: N802 - Qt API contract
        previous_name = self.objectName()
        super().setObjectName(name)
        if getattr(self, "_style_initialized", False) and self.objectName() != previous_name:
            self._refresh_style()

    @staticmethod
    def build_spin_stylesheet(object_name: str, theme) -> str:
        """Generate QSS that hides native buttons and applies themed colours."""
        height_sm = resolved_control_height(theme, "sm")
        height_md = resolved_control_height(theme, "md")
        height_lg = resolved_control_height(theme, "lg")
        return f"""
            #{object_name} {{
                background: {theme.bg_input};
                color: {theme.text_primary};
                border: none;
                border-radius: {theme.input_radius}px;
                padding: {theme.input_padding_y}px {theme.input_padding_x}px;
                padding-right: {theme.spin_button_width}px;
                font-size: {theme.font_size_md}px;
                font-family: {theme.font_family};
                selection-background-color: {theme.primary};
                selection-color: {theme.text_on_primary};
            }}
            #{object_name}:focus {{
                background: {theme.bg_window};
            }}
            #{object_name}:disabled {{
                background: {theme.bg_hover};
                color: {theme.text_disabled};
            }}
            #{object_name}::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: {theme.spin_button_width}px;
                border: none;
                background: transparent;
            }}
            #{object_name}::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: {theme.spin_button_width}px;
                border: none;
                background: transparent;
            }}
            #{object_name}::up-arrow,
            #{object_name}::down-arrow {{
                width: 0; height: 0;
                image: none;
            }}
            #{object_name}[sizeClass="sm"] {{
                min-height: {height_sm}px;
                max-height: {height_sm}px;
                padding-top: 0px;
                padding-bottom: 0px;
            }}
            #{object_name}[sizeClass="md"] {{
                min-height: {height_md}px;
                max-height: {height_md}px;
                padding-top: 0px;
                padding-bottom: 0px;
            }}
            #{object_name}[sizeClass="lg"] {{
                min-height: {height_lg}px;
                max-height: {height_lg}px;
                padding-top: 0px;
                padding-bottom: 0px;
            }}
        """

    def paintEvent(self, event):
        super().paintEvent(event)

        theme = get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        active = self.hasFocus()
        draw_input_surface(
            painter,
            self.width(),
            self.height(),
            theme=theme,
            enabled=self.isEnabled(),
            active=active,
            button_width=theme.spin_button_width,
        )
        draw_spin_chevrons(
            painter,
            self.width(),
            self.height(),
            theme=theme,
            enabled=self.isEnabled(),
            active=active,
        )
        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_editor_geometry()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._editor_widget and event.type() in {QEvent.Move, QEvent.Resize, QEvent.Show}:
            self._sync_editor_geometry()
        return super().eventFilter(watched, event)

    def _configure_editor(self) -> None:
        line_edit = self.lineEdit()
        if line_edit is None:
            return

        configure_input_line_edit(line_edit, get_theme(), stylesheet=build_input_editor_stylesheet(get_theme()))
        if self._editor_widget is not line_edit:
            self._release_editor_filter()
            self._editor_widget = line_edit
            line_edit.installEventFilter(self)
        self._sync_editor_geometry()

    def _release_editor_filter(self) -> None:
        if self._editor_widget is None:
            return
        try:
            self._editor_widget.removeEventFilter(self)
        except RuntimeError:
            pass
        self._editor_widget = None

    def _sync_editor_geometry(self) -> None:
        line_edit = self.lineEdit()
        if line_edit is None or self._syncing_editor_geometry:
            return

        self._syncing_editor_geometry = True
        try:
            sync_input_line_edit_geometry(
                self,
                line_edit,
                button_width=get_theme().spin_button_width,
                theme=get_theme(),
            )
        finally:
            self._syncing_editor_geometry = False

    def _refresh_style(self) -> None:
        theme = get_theme()
        self.setStyleSheet(self.build_spin_stylesheet(self.objectName(), theme))
        self._configure_editor()
        self.updateGeometry()
        self.update()
