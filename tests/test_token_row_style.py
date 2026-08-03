from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QFrame
from src.shared.ui.theme import get_theme
from src.shared.ui.token_row_style import (
    apply_token_row_style,
    build_token_row_stylesheet,
)


def test_token_row_uses_dynamic_state_instead_of_per_row_qss(qapp) -> None:
    row = QFrame()

    apply_token_row_style(row, object_name="material_row", is_last=False)

    assert row.objectName() == "material_row"
    assert row.property("tokenRow") is True
    assert row.property("tokenRowHover") is True
    assert row.property("tokenRowLast") is False
    assert row.styleSheet() == ""

    apply_token_row_style(row, object_name="material_row", is_last=True)

    assert row.property("tokenRowLast") is True
    qss = build_token_row_stylesheet(get_theme())
    assert 'QWidget[tokenRow="true"]' in qss
    assert 'QWidget[tokenRow="true"][tokenRowLast="true"]' in qss
    assert 'QWidget[tokenRow="true"][tokenRowHover="true"]:hover' in qss


def test_token_row_can_disable_large_surface_hover(qapp) -> None:
    row = QFrame()

    apply_token_row_style(
        row,
        object_name="timeline_segment_row",
        is_last=True,
        hover_highlight=False,
    )

    assert row.property("tokenRowHover") is False
