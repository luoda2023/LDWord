"""Small, dependency-neutral helpers shared by scene detail panes."""

from __future__ import annotations

from pathlib import Path

from src.qt_api import QDesktopServices, QLineEdit, QPushButton, Qt, QUrl
from src.shared.engine.official_document_material_package import (
    load_official_document_material_package,
    load_official_document_material_table,
)
from src.shared.ui import (
    apply_button_variant,
    build_button_stylesheet,
    build_text_input_stylesheet,
)
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import get_theme


def open_local_path(path: Path) -> bool:
    """Open a local file or directory through Qt's desktop integration."""

    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))))


def _load_official_material_source(
    path: Path | str,
    *,
    profile_id: str,
):
    source = Path(path)
    if source.suffix.lower() == ".json":
        return load_official_document_material_package(source)
    return load_official_document_material_table(
        source,
        profile_id=profile_id,
    )


def _set_combo_by_data(combo: StyledComboBox, target) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == target:
            combo.setCurrentIndex(i)
            return


def _populate_combo(combo: StyledComboBox, items: dict[str, str]) -> None:
    combo.clear()
    for value, label in items.items():
        combo.addItem(label, value)


def _apply_template_line_edit_contract(*line_edits: QLineEdit) -> None:
    stylesheet = build_text_input_stylesheet(get_theme())
    for line_edit in line_edits:
        apply_size_class(line_edit, "md")
        line_edit.setAttribute(Qt.WA_StyledBackground, True)
        line_edit.setStyleSheet(stylesheet)


def _apply_template_button_contract(*buttons: tuple[QPushButton, str]) -> None:
    stylesheet = build_button_stylesheet(get_theme())
    for button, variant in buttons:
        apply_button_variant(button, variant)
        apply_size_class(button, "md")
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(stylesheet)
