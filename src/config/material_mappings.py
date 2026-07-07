"""Load entity/replacement mappings from simple JSON, CSV, and Excel files."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from src.config.resolved import ReplacementRule


@dataclass(slots=True)
class MaterialMappingPayload:
    entity_data: dict[str, str] = field(default_factory=dict)
    replacements: list[ReplacementRule] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.entity_data or self.replacements)


def load_material_mapping(path: str | Path) -> MaterialMappingPayload:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".json":
        return _load_json_mapping(source)
    if suffix == ".csv":
        return _load_csv_mapping(source)
    if suffix in {".xlsx", ".xlsm"}:
        return _load_excel_mapping(source)
    raise ValueError(f"Unsupported material mapping file: {source}")


def _load_json_mapping(path: Path) -> MaterialMappingPayload:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        return MaterialMappingPayload()

    entity_data = data.get("entity_data")
    replacements = data.get("replacements")

    if entity_data is None and replacements is None:
        entity_data = data

    return MaterialMappingPayload(
        entity_data=_normalize_entity_data(entity_data),
        replacements=_normalize_replacements(replacements),
    )


def _load_csv_mapping(path: Path) -> MaterialMappingPayload:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    return _payload_from_table_rows(rows)


def _load_excel_mapping(path: Path) -> MaterialMappingPayload:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("Excel material mappings require openpyxl") from exc

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        raw_rows = list(sheet.iter_rows(values_only=True))
    finally:
        workbook.close()

    if not raw_rows:
        return MaterialMappingPayload()

    headers = [str(value or "").strip() for value in raw_rows[0]]
    rows: list[dict[str, Any]] = []
    for raw_row in raw_rows[1:]:
        if not any(value is not None and str(value).strip() for value in raw_row):
            continue
        row: dict[str, Any] = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            row[header] = raw_row[index] if index < len(raw_row) else None
        if row:
            rows.append(row)

    return _payload_from_table_rows(rows)


def _payload_from_table_rows(rows: list[Mapping[str, Any]]) -> MaterialMappingPayload:

    if not rows:
        return MaterialMappingPayload()

    field_names = {str(name or "").strip().lower() for name in (rows[0].keys() or [])}
    if {"old", "new"}.issubset(field_names):
        return MaterialMappingPayload(replacements=_csv_replacements(rows))
    if {"key", "value"}.issubset(field_names):
        return MaterialMappingPayload(entity_data=_csv_entity_data(rows))

    return MaterialMappingPayload(
        entity_data={
            str(key): str(value)
            for key, value in rows[0].items()
            if str(key or "").strip() and value is not None
        }
    )


def _normalize_entity_data(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(raw_value)
        for key, raw_value in value.items()
        if str(key or "").strip()
    }


def _normalize_replacements(value: Any) -> list[ReplacementRule]:
    if not isinstance(value, list):
        return []
    replacements: list[ReplacementRule] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        old = str(item.get("old", "") or "")
        if not old:
            continue
        replacements.append(
            ReplacementRule(
                old=old,
                new=str(item.get("new", "") or ""),
            )
        )
    return replacements


def _csv_entity_data(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    entity_data: dict[str, str] = {}
    for row in rows:
        key = str(_get_case_insensitive(row, "key") or "").strip()
        if not key:
            continue
        entity_data[key] = str(_get_case_insensitive(row, "value") or "")
    return entity_data


def _csv_replacements(rows: list[Mapping[str, Any]]) -> list[ReplacementRule]:
    replacements: list[ReplacementRule] = []
    for row in rows:
        old = str(_get_case_insensitive(row, "old") or "")
        if not old:
            continue
        replacements.append(
            ReplacementRule(
                old=old,
                new=str(_get_case_insensitive(row, "new") or ""),
            )
        )
    return replacements


def _get_case_insensitive(row: Mapping[str, Any], key: str) -> Any:
    for raw_key, value in row.items():
        if str(raw_key or "").strip().lower() == key:
            return value
    return None


__all__ = ["MaterialMappingPayload", "load_material_mapping"]
