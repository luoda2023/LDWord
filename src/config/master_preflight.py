"""Reusable preflight checks for DOCX-backed master specs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from src.config.master_library import (
    MasterManifestError,
    MasterSpec,
    PlaceholderContract,
)
from src.config.master_placeholder_index import (
    placeholder_identifier,
    placeholder_index_matches_payload,
    scan_master_placeholder_index,
)


@dataclass(frozen=True, slots=True)
class MasterPreflightResult:
    """Result of checking one master file against its placeholder contract."""

    mode_id: str = ""
    master_id: str = ""
    docx_path: Path | None = None
    status: str = "not_checked"
    required_placeholders: tuple[str, ...] = ()
    optional_placeholders: tuple[str, ...] = ()
    missing_required_placeholders: tuple[str, ...] = ()
    missing_optional_placeholders: tuple[str, ...] = ()
    unexpected_placeholders: tuple[str, ...] = ()
    indexed_placeholders: tuple[str, ...] = ()
    placeholder_index_status: str = "not_registered"
    placeholder_index_sha256: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def check_master_preflight(master: MasterSpec) -> MasterPreflightResult:
    """Check a ``MasterSpec`` DOCX against its placeholder contract."""

    status, missing = check_placeholder_contract(
        master.docx_path,
        master.placeholder_contract,
    )
    index = None
    try:
        index = scan_master_placeholder_index(master.docx_path)
    except (OSError, ValueError):
        index = None
    required = _normalized_placeholders(master.placeholder_contract.required)
    optional = _normalized_placeholders(master.placeholder_contract.optional)
    runtime_inserted = _normalized_placeholders(
        master.placeholder_contract.runtime_inserted_placeholders
    )
    replaceable = {
        placeholder_identifier(key)
        for key in (index.replaceable_placeholder_ids if index is not None else ())
    }
    declared = set((*required, *optional))
    missing_optional = tuple(
        key
        for key in optional
        if key not in replaceable and key not in runtime_inserted
    )
    unexpected = tuple(
        placeholder_identifier(key)
        for key in (index.replaceable_placeholder_ids if index is not None else ())
        if placeholder_identifier(key) not in declared
    )
    registered_index = _registered_placeholder_index(master)
    if registered_index and index is not None:
        index_status = (
            "ok"
            if placeholder_index_matches_payload(index, registered_index)
            else "stale"
        )
    else:
        index_status = "not_registered"
    if status == "ok" and index_status == "stale":
        status = "placeholder_index_stale"
    return MasterPreflightResult(
        mode_id=master.mode_id,
        master_id=master.master_id,
        docx_path=master.docx_path,
        status=status,
        required_placeholders=required,
        optional_placeholders=optional,
        missing_required_placeholders=missing,
        missing_optional_placeholders=missing_optional,
        unexpected_placeholders=unexpected,
        indexed_placeholders=(index.placeholder_ids if index is not None else ()),
        placeholder_index_status=index_status,
        placeholder_index_sha256=index.sha256 if index is not None else "",
    )


def check_placeholder_contract(
    master_docx_path: Path | str,
    contract: PlaceholderContract,
) -> tuple[str, tuple[str, ...]]:
    """Return a stable status and missing required placeholder ids."""

    path = Path(master_docx_path)
    required = _normalized_placeholders(contract.required)
    if not required:
        return "no_required_placeholders", ()
    if not path.is_file():
        return "missing_master_docx", required
    try:
        index = scan_master_placeholder_index(path)
    except (OSError, ValueError):
        return "unreadable_master_docx", required
    available = {
        placeholder_identifier(key) for key in index.replaceable_placeholder_ids
    }
    available.update(_normalized_placeholders(contract.runtime_inserted_placeholders))
    missing = tuple(
        placeholder for placeholder in required if placeholder not in available
    )
    if missing:
        return "missing_required_placeholders", missing
    return "ok", ()


def _normalized_placeholders(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(item or "").strip() for item in values if str(item or "").strip())


def _registered_placeholder_index(master: MasterSpec) -> dict[str, object]:
    path = master.manifest_path
    if path is None:
        return {}
    if not path.is_file():
        raise MasterManifestError(f"master_manifest_missing:{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MasterManifestError(f"master_manifest_unreadable:{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MasterManifestError(
            f"master_manifest_schema_invalid:{path}: root must be an object"
        )
    if (
        payload.get("mode_id") != master.mode_id
        or payload.get("master_id") != master.master_id
    ):
        raise MasterManifestError(
            f"master_manifest_identity_mismatch:{path}: preflight identity drift"
        )
    value = payload.get("placeholder_index")
    if not isinstance(value, dict):
        raise MasterManifestError(
            f"master_manifest_schema_invalid:{path}: placeholder_index must be an object"
        )
    return dict(value)


__all__ = [
    "MasterPreflightResult",
    "check_master_preflight",
    "check_placeholder_contract",
]
