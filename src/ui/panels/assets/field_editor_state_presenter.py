"""Presenter mixin for local field editor state mutation."""

from __future__ import annotations

from src.ui.panels.assets.fields import (
    _format_fields_text,
    _parse_fields_text,
    _parse_required_fields_text,
)


_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS = (
    "question_asset_download_auth",
    "question_figure_download_auth",
    "remote_question_asset_download_auth",
    "asset_download_auth",
    "remote_asset_download_auth",
    "asset_auth",
)


class FieldEditorStatePresenterMixin:
    """Coordinate local field editor values and required-field state."""

    def _on_structured_field_changed(self, field_key: str = "") -> None:
        if field_key and not self._preserve_import_sources:
            self._imported_field_keys.discard(field_key)
        self._refresh_summary()

    def _on_more_fields_changed(self) -> None:
        if not self._preserve_import_sources:
            for key in _parse_fields_text(self._fields_edit.get_text()):
                self._imported_field_keys.discard(key)
        self._refresh_summary()

    def _on_required_fields_changed(self) -> None:
        self._refresh_summary()
        self._sync_material_batch_selection()

    def _required_field_keys(self) -> tuple[str, ...]:
        return tuple(
            _parse_required_fields_text(
                self._required_fields_edit.text(),
                fallback=self._default_required_field_keys(),
            )
        )

    def _editor_fields(self) -> dict[str, str]:
        fields: dict[str, str] = {}
        for key, edit in self._field_inputs.items():
            value = edit.text().strip()
            if value:
                fields[key] = value
        fields.update(_parse_fields_text(self._fields_edit.get_text()))
        for key in _REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS:
            fields.pop(key, None)
        return fields

    def _set_structured_fields(self, fields: dict[str, str]) -> None:
        remaining = dict(fields or {})
        for key in _REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS:
            remaining.pop(key, None)
        for key, edit in self._field_inputs.items():
            edit.setText(str(remaining.pop(key, "") or ""))
        self._fields_edit.set_text(_format_fields_text(remaining))


__all__ = [
    "FieldEditorStatePresenterMixin",
    "_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS",
]
