"""Local question-figure repair audit helpers.

These helpers record local repair and rollback evidence. They deliberately do
not cover enterprise remote governance or incident-management workflows.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from src.config.atomic_io import atomic_write_text
from src.config.materials import AssetItem
from src.services.material_assets.question_figures import (
    _question_figure_candidate_list,
    _question_figure_target_label,
    _question_figure_target_value,
)


def _question_figure_repair_audit_record(
    candidate: Mapping[str, object],
    *,
    original_item: AssetItem,
    replacement_path: str,
    archive_id: str,
    archive_name: str,
    profile_id: str,
    profile_name: str,
    applied_at: str,
) -> dict[str, object]:
    original_metadata = dict(getattr(original_item, "metadata", {}) or {})
    question_index = (
        str(candidate.get("question_index") or "").strip()
        or _question_figure_target_value(original_metadata)
    )
    original_path = str(getattr(original_item, "path", "") or "").strip()
    repair_target_key = str(candidate.get("repair_target_key") or "").strip()
    queue_id = str(candidate.get("queue_id") or "").strip()
    audit_id = _question_figure_repair_audit_id(
        queue_id=queue_id,
        profile_id=profile_id,
        repair_target_key=repair_target_key,
        original_path=original_path,
        replacement_path=replacement_path,
        applied_at=applied_at,
    )
    return {
        "audit_id": audit_id,
        "action": "frontstage_question_figure_repair_apply",
        "status": "applied",
        "applied_at": applied_at,
        "archive_id": str(archive_id or ""),
        "archive_name": str(archive_name or ""),
        "profile_id": str(profile_id or ""),
        "profile_name": str(profile_name or ""),
        "queue_id": queue_id,
        "candidate_kind": str(candidate.get("kind") or ""),
        "source_issue_id": str(candidate.get("source_issue_id") or ""),
        "source_kind": str(candidate.get("source_kind") or ""),
        "issue_summary": str(candidate.get("issue_summary") or ""),
        "question_index": question_index,
        "item_id": str(
            candidate.get("item_id")
            or getattr(original_item, "item_id", "")
            or ""
        ),
        "label": str(candidate.get("label") or getattr(original_item, "label", "") or ""),
        "target_label": _question_figure_target_label(original_item),
        "repair_target_key": repair_target_key,
        "original_path": original_path,
        "replacement_source_path": str(replacement_path or ""),
        "replacement_source_kind": str(candidate.get("replacement_source_kind") or ""),
        "applied_path": str(replacement_path or ""),
        "confirmation_action": str(candidate.get("confirmation_action") or ""),
        "confirmation_status": str(candidate.get("confirmation_status") or ""),
        "confirmation_apply_supported": bool(
            candidate.get("confirmation_apply_supported")
        ),
        "conflict_group_id": str(candidate.get("conflict_group_id") or ""),
        "conflict_resolution_status": str(
            candidate.get("conflict_resolution_status") or ""
        ),
        "conflict_resolution_action": str(
            candidate.get("conflict_resolution_action") or ""
        ),
        "conflict_selected_queue_id": str(
            candidate.get("conflict_selected_queue_id") or ""
        ),
        "conflict_resolution_group_id": str(
            candidate.get("conflict_resolution_group_id") or ""
        ),
        "conflict_resolution_candidate_queue_ids": (
            _question_figure_candidate_list(
                candidate.get("conflict_resolution_candidate_queue_ids")
            )
        ),
        "conflict_resolution_rejected_queue_ids": (
            _question_figure_candidate_list(
                candidate.get("conflict_resolution_rejected_queue_ids")
            )
        ),
        "conflict_resolution_by": str(
            candidate.get("conflict_resolution_by") or ""
        ),
        "conflict_resolution_note": str(
            candidate.get("conflict_resolution_note") or ""
        ),
        "confirmed": True,
    }


def _question_figure_repair_rollback_audit_record(
    applied_record: Mapping[str, object],
    *,
    rollback_from_item: AssetItem,
    rollback_path: str,
    archive_id: str,
    archive_name: str,
    profile_id: str,
    profile_name: str,
    rolled_back_at: str,
) -> dict[str, object]:
    linked_audit_id = str(applied_record.get("audit_id") or "").strip()
    rollback_from_path = str(getattr(rollback_from_item, "path", "") or "").strip()
    applied_path = str(applied_record.get("applied_path") or rollback_from_path).strip()
    original_path = str(applied_record.get("original_path") or rollback_path).strip()
    audit_id = _question_figure_repair_rollback_audit_id(
        linked_audit_id=linked_audit_id,
        profile_id=profile_id,
        repair_target_key=str(applied_record.get("repair_target_key") or ""),
        rollback_from_path=rollback_from_path or applied_path,
        rollback_to_path=rollback_path,
        rolled_back_at=rolled_back_at,
    )
    return {
        "audit_id": audit_id,
        "action": "frontstage_question_figure_repair_rollback",
        "status": "rolled_back",
        "rolled_back_at": rolled_back_at,
        "archive_id": str(archive_id or ""),
        "archive_name": str(archive_name or ""),
        "profile_id": str(profile_id or ""),
        "profile_name": str(profile_name or ""),
        "linked_apply_audit_id": linked_audit_id,
        "queue_id": str(applied_record.get("queue_id") or ""),
        "source_issue_id": str(applied_record.get("source_issue_id") or ""),
        "source_kind": str(applied_record.get("source_kind") or ""),
        "issue_summary": str(applied_record.get("issue_summary") or ""),
        "question_index": str(applied_record.get("question_index") or ""),
        "item_id": str(
            applied_record.get("item_id")
            or getattr(rollback_from_item, "item_id", "")
            or ""
        ),
        "target_label": _question_figure_target_label(rollback_from_item),
        "repair_target_key": str(applied_record.get("repair_target_key") or ""),
        "original_path": original_path,
        "applied_path": applied_path,
        "rollback_from_path": rollback_from_path or applied_path,
        "rollback_to_path": str(rollback_path or ""),
        "confirmation_action": "confirm_question_figure_repair_rollback",
        "confirmation_status": "ready",
        "rollback_confirmed": True,
    }


def _question_figure_repair_audit_dir(
    assets_dir: str,
    original_path: str,
    replacement_path: str,
) -> Path | None:
    candidates = [
        Path(str(assets_dir or "").strip()) if str(assets_dir or "").strip() else None,
        Path(str(original_path or "").strip()).parent if str(original_path or "").strip() else None,
        Path(str(replacement_path or "").strip()).parent if str(replacement_path or "").strip() else None,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_dir():
            return candidate
    return None


class QuestionFigureRepairAuditIntegrityError(RuntimeError):
    """Existing repair evidence cannot be read without risking data loss."""


def _append_question_figure_repair_audit_record(
    audit_dir: Path | None,
    record: Mapping[str, object],
) -> dict[str, object]:
    normalized_record = dict(record)
    if audit_dir is None:
        normalized_record["artifact_path"] = ""
        normalized_record["audit_persistence_status"] = "not_available"
        return normalized_record
    history_path = audit_dir / "question_figure_repair_audit.json"
    payload = _read_question_figure_repair_audit_payload(history_path)
    records = list(payload["records"])
    audit_id = str(normalized_record.get("audit_id") or "").strip()
    if audit_id:
        records = [
            item
            for item in records
            if str(item.get("audit_id") or "").strip() != audit_id
        ]
    normalized_record["artifact_path"] = str(history_path)
    normalized_record["audit_persistence_status"] = "written"
    records.append(dict(normalized_record))
    records = records[-100:]
    payload["schema_version"] = 1
    payload["entry_count"] = len(records)
    payload["records"] = records
    payload["updated_at"] = str(
        normalized_record.get("applied_at")
        or normalized_record.get("rolled_back_at")
        or ""
    )
    try:
        atomic_write_text(
            history_path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        normalized_record["artifact_path"] = ""
        normalized_record["audit_persistence_status"] = "failed"
        normalized_record["audit_persistence_error"] = "write_failed"
    return normalized_record


def _read_question_figure_repair_audit_payload(history_path: Path) -> dict[str, object]:
    if not history_path.exists():
        return {"schema_version": 1, "records": []}
    if not history_path.is_file():
        raise QuestionFigureRepairAuditIntegrityError(
            f"question_figure_repair_audit_not_file:{history_path}"
        )
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise QuestionFigureRepairAuditIntegrityError(
            f"question_figure_repair_audit_unreadable:{history_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise QuestionFigureRepairAuditIntegrityError(
            f"question_figure_repair_audit_invalid_root:{history_path}"
        )
    records = payload.get("records")
    if not isinstance(records, list) or any(
        not isinstance(record, Mapping) for record in records
    ):
        raise QuestionFigureRepairAuditIntegrityError(
            f"question_figure_repair_audit_invalid_records:{history_path}"
        )
    return payload


def _question_figure_repair_audit_id(
    *,
    queue_id: str,
    profile_id: str,
    repair_target_key: str,
    original_path: str,
    replacement_path: str,
    applied_at: str,
) -> str:
    digest = hashlib.sha256(
        "|".join(
            [
                str(queue_id or ""),
                str(profile_id or ""),
                str(repair_target_key or ""),
                str(original_path or ""),
                str(replacement_path or ""),
                str(applied_at or ""),
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"repair-apply-{digest}"


def _question_figure_repair_rollback_audit_id(
    *,
    linked_audit_id: str,
    profile_id: str,
    repair_target_key: str,
    rollback_from_path: str,
    rollback_to_path: str,
    rolled_back_at: str,
) -> str:
    digest = hashlib.sha256(
        "|".join(
            [
                str(linked_audit_id or ""),
                str(profile_id or ""),
                str(repair_target_key or ""),
                str(rollback_from_path or ""),
                str(rollback_to_path or ""),
                str(rolled_back_at or ""),
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"repair-rollback-{digest}"


build_question_figure_repair_audit_record = _question_figure_repair_audit_record
build_question_figure_repair_rollback_audit_record = (
    _question_figure_repair_rollback_audit_record
)
resolve_question_figure_repair_audit_dir = _question_figure_repair_audit_dir
append_question_figure_repair_audit_record = _append_question_figure_repair_audit_record
read_question_figure_repair_audit_payload = _read_question_figure_repair_audit_payload
question_figure_repair_audit_id = _question_figure_repair_audit_id
question_figure_repair_rollback_audit_id = _question_figure_repair_rollback_audit_id


__all__ = [
    'QuestionFigureRepairAuditIntegrityError',
    'build_question_figure_repair_audit_record',
    'build_question_figure_repair_rollback_audit_record',
    'resolve_question_figure_repair_audit_dir',
    'append_question_figure_repair_audit_record',
    'read_question_figure_repair_audit_payload',
    'question_figure_repair_audit_id',
    'question_figure_repair_rollback_audit_id',
    '_question_figure_repair_audit_record',
    '_question_figure_repair_rollback_audit_record',
    '_question_figure_repair_audit_dir',
    '_append_question_figure_repair_audit_record',
    '_read_question_figure_repair_audit_payload',
    '_question_figure_repair_audit_id',
    '_question_figure_repair_rollback_audit_id',
]
