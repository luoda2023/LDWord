"""Layout helpers for assets-panel forms."""

from __future__ import annotations

from src.qt_api import QWidget


def _chunk_form_rows(rows: list[QWidget], *, columns: int) -> list[list[QWidget]]:
    column_count = max(1, int(columns))
    return [rows[index : index + column_count] for index in range(0, len(rows), column_count)]


__all__ = ["_chunk_form_rows"]
