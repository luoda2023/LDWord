from __future__ import annotations

from pathlib import Path

from src.qt_api import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    Qt,
    QWidget,
    Signal,
)
from src.shared.ui import ThemedRadioButton
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme

from .document_execution_state import DocumentExecutionTopology
from .output_path_policy import resolve_workbench_output_root


class OutputLocationCard(Card):
    """One output-root policy shared by all document execution topologies."""

    output_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("wb_output_location_card")
        self.set_header("输出目录", icon_name="square-arrow-out-up-right")
        self._custom_output_dir = ""
        self._source_paths: tuple[str, ...] = ()
        self._topology: DocumentExecutionTopology | None = None

        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._default_radio = ThemedRadioButton("默认", row)
        self._custom_radio = ThemedRadioButton("自定义", row)
        self._mode_group.addButton(self._default_radio, 0)
        self._mode_group.addButton(self._custom_radio, 1)
        self._default_radio.setChecked(True)
        self._custom_radio.toggled.connect(self._on_custom_toggled)
        layout.addWidget(self._default_radio)
        layout.addWidget(self._custom_radio)

        self._browse_button = QPushButton("选择目录", row)
        self._browse_button.setObjectName("wb_output_location_browse")
        self._browse_button.clicked.connect(self._choose_directory)
        self._browse_button.setVisible(False)
        self._browse_button.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        layout.addWidget(self._browse_button, 1)

        self._preview = QLabel("", row)
        self._preview.setObjectName("wb_output_location_preview")
        self._preview.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._preview, 2)
        self.add_widget(row)

        bind_theme(self, self._apply_output_theme)
        self._apply_output_theme()

    def output_dir(self) -> str:
        return self._custom_output_dir if self._custom_radio.isChecked() else ""

    def set_output_dir(self, folder: str) -> None:
        value = str(folder or "").strip()
        self._custom_output_dir = value
        if value:
            self._custom_radio.setChecked(True)
            self._browse_button.setText(Path(value).name or value)
            self._browse_button.setToolTip(value)
        else:
            self._default_radio.setChecked(True)
            self._browse_button.setText("选择目录")
            self._browse_button.setToolTip("")
        self._refresh_preview()
        self.output_changed.emit(self.output_dir())

    def set_topology(self, topology: DocumentExecutionTopology) -> None:
        self._topology = topology
        self._refresh_preview()

    def set_source_paths(self, paths) -> None:
        self._source_paths = tuple(
            value
            for item in tuple(paths or ())
            if (value := str(item or "").strip())
        )
        self._refresh_preview()

    def _on_custom_toggled(self, enabled: bool) -> None:
        self._browse_button.setVisible(bool(enabled))
        if not enabled:
            self._custom_output_dir = ""
            self._browse_button.setText("选择目录")
            self._browse_button.setToolTip("")
        self._refresh_preview()
        self.output_changed.emit(self.output_dir())

    def _choose_directory(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            self._custom_output_dir,
        )
        if folder:
            self.set_output_dir(folder)

    def _refresh_preview(self) -> None:
        topology = self._topology
        if topology is None or not topology.expected_output_count:
            self._preview.clear()
            return
        try:
            output_root = resolve_workbench_output_root(
                self.output_dir(),
                self._source_paths,
            )
        except ValueError:
            self._preview.clear()
            self._preview.setToolTip("")
            return
        location = output_root.name or str(output_root)
        count = topology.expected_output_count
        text = f"{location} · {count} 份"
        self._preview.setText(text)
        self._preview.setToolTip(str(output_root))

    def _apply_output_theme(self) -> None:
        theme = get_theme()
        apply_size_class(self._browse_button, "md")
        apply_button_variant(self._browse_button, "secondary")
        self._browse_button.setIcon(
            get_icon("folder-open", 16, theme.text_primary)
        )
        self._preview.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; "
            f"color: {theme.text_secondary}; background: transparent;"
        )


__all__ = ["OutputLocationCard"]
