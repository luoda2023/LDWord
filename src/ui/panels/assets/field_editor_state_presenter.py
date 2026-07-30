"""Presenter mixin for local field editor state mutation."""

from __future__ import annotations

from src.ui.panels.assets.fields import (
    MATERIAL_FIELD_DRAFT_PREFIX,
    _duplicate_fields_text_keys,
    _parse_fields_text,
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
        if field_key:
            self._declared_field_keys.add(field_key)
        if field_key and not self._preserve_import_sources:
            self._imported_field_keys.discard(field_key)
        self._refresh_field_conflict_state()
        if field_key:
            edit = self._field_inputs.get(field_key)
            self._update_preview_field_value(
                field_key,
                edit.text().strip() if edit is not None else "",
            )
        self._schedule_summary_refresh(scope="fields")

    def _on_more_fields_changed(self) -> None:
        parsed_fields = _parse_fields_text(self._fields_edit.get_text())
        self._declared_field_keys.update(parsed_fields)
        if not self._preserve_import_sources:
            for key in parsed_fields:
                self._imported_field_keys.discard(key)
        self._refresh_field_conflict_state()
        self._schedule_summary_refresh(scope="fields")

    def _editor_fields(self) -> dict[str, str]:
        fields: dict[str, str] = {}
        for key, edit in self._field_inputs.items():
            value = edit.text().strip()
            if value:
                fields[key] = value
        fields.update(_parse_fields_text(self._fields_edit.get_text()))
        for key, edit in self._template_field_inputs.items():
            if key.startswith(MATERIAL_FIELD_DRAFT_PREFIX):
                continue
            # A floating row can have a read-only runtime projection.  Never
            # harvest that projection into the persisted package payload.
            if key in getattr(self, "_official_floating_field_keys", ()):
                continue
            if bool(edit.property("timelineOwned")):
                continue
            value = edit.text().strip()
            if value:
                fields[key] = value
        for key in getattr(self, "_official_floating_field_keys", ()):
            value = str(self._template_field_values.get(key, "") or "").strip()
            if value:
                fields[key] = value
        for key in _REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS:
            fields.pop(key, None)
        return fields

    def _material_field_render_value(self, key: str, scope: str) -> str:
        """Return package value plus the current task's floating overlay."""

        if scope == "floating" and key in getattr(self, "_task_field_values", {}):
            return str(self._task_field_values.get(key, "") or "")
        return str(self._template_field_values.get(key, "") or "")

    def _material_preview_fields(self) -> dict[str, str]:
        """Build execution preview values without mutating package fields."""

        fields = self._editor_fields()
        task_values = dict(getattr(self, "_task_field_values", {}) or {})
        for key in getattr(self, "_official_floating_field_keys", ()):
            if key not in task_values:
                continue
            value = str(task_values.get(key, "") or "").strip()
            if value:
                fields[key] = value
            else:
                fields.pop(key, None)
        return fields

    def _field_conflict_keys(self) -> tuple[str, ...]:
        conflicts = list(_duplicate_fields_text_keys(self._fields_edit.get_text()))
        more_fields = _parse_fields_text(self._fields_edit.get_text())
        for key, edit in self._template_field_inputs.items():
            if bool(edit.property("timelineOwned")):
                continue
            template_value = edit.text().strip()
            if key.startswith(MATERIAL_FIELD_DRAFT_PREFIX):
                if template_value and "字段代码未填写" not in conflicts:
                    conflicts.append("字段代码未填写")
                continue
            more_value = str(more_fields.get(key, "") or "").strip()
            if template_value and more_value and template_value != more_value and key not in conflicts:
                conflicts.append(key)
        for key, edit in self._field_inputs.items():
            structured_value = edit.text().strip()
            more_value = str(more_fields.get(key, "") or "").strip()
            if structured_value and more_value and structured_value != more_value and key not in conflicts:
                conflicts.append(key)

        return tuple(conflicts)

    def _refresh_field_conflict_state(self) -> None:
        conflicts = self._field_conflict_keys() if hasattr(self, "_fields_edit") else ()
        self._field_conflicts = conflicts
        for name in ("_apply_btn", "_batch_generate_btn", "_save_btn"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(not conflicts)
        sync_hint = getattr(self, "_sync_field_conflict_hint", None)
        if callable(sync_hint):
            sync_hint()

    def _set_structured_fields(self, fields: dict[str, str]) -> None:
        remaining = dict(fields or {})
        for key in _REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS:
            remaining.pop(key, None)
        for key, edit in self._field_inputs.items():
            edit.setText(str(remaining.pop(key, "") or ""))
        declared_manual = [
            key
            for key in getattr(self, "_declared_field_keys", ())
            if key not in self._field_inputs
            and not key.startswith(MATERIAL_FIELD_DRAFT_PREFIX)
        ]
        self._manual_field_keys = list(
            dict.fromkeys((*remaining.keys(), *declared_manual))
        )
        self._template_field_values = {
            key: str(value or "")
            for key, value in remaining.items()
            if str(value or "").strip()
        }
        # The keyed row controller keeps widgets alive across profile switches.
        # Refresh from the loaded model without harvesting the previous
        # widgets first; the update callback then applies the new values to the
        # retained rows in place.
        self._fields_edit.set_text("")
        self._refresh_unknown_field_suggestions(
            self._document_field_order,
            capture_live_values=False,
        )
        self._refresh_field_conflict_state()


__all__ = [
    "FieldEditorStatePresenterMixin",
    "_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS",
]
