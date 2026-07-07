from __future__ import annotations

import copy
import hashlib
import json
import re
import zipfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

from src.report_writer import write_json_report, write_markdown_report
from src.shared.engine.docx_compare import write_compare_docx

from .material_artifacts import _path_map


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value) -> str:
    return str(value or "").strip()


def _clean_list(values) -> list[str]:
    return [_clean_text(value) for value in list(values or []) if _clean_text(value)]


def _batch_question_figure_comparison_matrix(batch_issue_items) -> dict[str, object]:
    profiles: dict[str, dict[str, object]] = {}
    questions: dict[str, dict[str, object]] = {}
    total_issue_count = 0

    for issue in list(batch_issue_items or []):
        if not isinstance(issue, Mapping):
            continue
        comparison_items = [
            item
            for item in list(issue.get("comparison_issue_items") or [])
            if isinstance(item, Mapping)
        ]
        if not comparison_items:
            continue
        profile_id = _clean_text(issue.get("profile_id"))
        profile_name = _clean_text(issue.get("profile_name"))
        profile_key = profile_id or profile_name or "profile"
        profile_entry = profiles.setdefault(
            profile_key,
            {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "issue_count": 0,
                "_questions": {},
            },
        )
        profile_questions = profile_entry["_questions"]
        if not isinstance(profile_questions, dict):
            continue

        for comparison_item in comparison_items:
            question_index = _comparison_matrix_question_index(comparison_item)
            row = _comparison_matrix_item_payload(
                comparison_item,
                repair_target_type=_clean_text(issue.get("repair_target_type")),
                repair_target_key=_clean_text(issue.get("repair_target_key")),
            )
            question_entry = profile_questions.setdefault(
                question_index,
                {
                    "question_index": question_index,
                    "issue_count": 0,
                    "items": [],
                },
            )
            if not isinstance(question_entry, dict):
                continue
            question_entry["issue_count"] = int(question_entry.get("issue_count") or 0) + 1
            question_items = question_entry.get("items")
            if isinstance(question_items, list):
                question_items.append(row)
            profile_entry["issue_count"] = int(profile_entry.get("issue_count") or 0) + 1

            question_summary = questions.setdefault(
                question_index,
                {
                    "question_index": question_index,
                    "issue_count": 0,
                    "_profiles": {},
                },
            )
            question_summary["issue_count"] = (
                int(question_summary.get("issue_count") or 0) + 1
            )
            question_profiles = question_summary["_profiles"]
            if isinstance(question_profiles, dict):
                summary_profile = question_profiles.setdefault(
                    profile_key,
                    {
                        "profile_id": profile_id,
                        "profile_name": profile_name,
                        "issue_count": 0,
                    },
                )
                summary_profile["issue_count"] = (
                    int(summary_profile.get("issue_count") or 0) + 1
                )
            total_issue_count += 1

    profile_rows = []
    for profile in sorted(
        profiles.values(),
        key=lambda item: (
            _clean_text(item.get("profile_name") if isinstance(item, dict) else ""),
            _clean_text(item.get("profile_id") if isinstance(item, dict) else ""),
        ),
    ):
        question_map = profile.get("_questions") if isinstance(profile, dict) else {}
        profile_rows.append(
            {
                "profile_id": _clean_text(profile.get("profile_id")),
                "profile_name": _clean_text(profile.get("profile_name")),
                "issue_count": int(profile.get("issue_count") or 0),
                "questions": sorted(
                    [
                        {
                            "question_index": _clean_text(question.get("question_index")),
                            "issue_count": int(question.get("issue_count") or 0),
                            "items": list(question.get("items") or []),
                        }
                        for question in list(question_map.values() if isinstance(question_map, dict) else [])
                        if isinstance(question, dict)
                    ],
                    key=lambda item: _comparison_question_sort_key(
                        item.get("question_index")
                    ),
                ),
            }
        )

    question_rows = []
    for question in sorted(
        questions.values(),
        key=lambda item: _comparison_question_sort_key(
            item.get("question_index") if isinstance(item, dict) else ""
        ),
    ):
        profile_map = question.get("_profiles") if isinstance(question, dict) else {}
        question_rows.append(
            {
                "question_index": _clean_text(question.get("question_index")),
                "issue_count": int(question.get("issue_count") or 0),
                "profiles": sorted(
                    [
                        {
                            "profile_id": _clean_text(profile.get("profile_id")),
                            "profile_name": _clean_text(profile.get("profile_name")),
                            "issue_count": int(profile.get("issue_count") or 0),
                        }
                        for profile in list(profile_map.values() if isinstance(profile_map, dict) else [])
                        if isinstance(profile, dict)
                    ],
                    key=lambda item: (
                        _clean_text(item.get("profile_name")),
                        _clean_text(item.get("profile_id")),
                    ),
                ),
            }
        )

    return {
        "kind": "question_figure_comparison_matrix",
        "total_issue_count": total_issue_count,
        "profile_count": len(profile_rows),
        "question_count": len(question_rows),
        "profiles": profile_rows,
        "questions": question_rows,
    }


def _batch_question_figure_repair_queue(batch_issue_items) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    seen_queue_ids: set[str] = set()

    for issue in list(batch_issue_items or []):
        if not isinstance(issue, Mapping):
            continue
        comparison_items = [
            item
            for item in list(issue.get("comparison_issue_items") or [])
            if isinstance(item, Mapping)
        ]
        if not comparison_items:
            continue
        repair_target_type = _clean_text(issue.get("repair_target_type"))
        repair_target_key = _clean_text(issue.get("repair_target_key"))
        if not repair_target_type or not repair_target_key:
            continue

        profile_id = _clean_text(issue.get("profile_id"))
        profile_name = _clean_text(issue.get("profile_name"))
        profile_key = profile_id or profile_name or "profile"
        source_issue_id = _clean_text(issue.get("issue_id"))
        source_kind = _clean_text(issue.get("kind"))
        source_summary = _clean_text(issue.get("summary"))

        for comparison_item in comparison_items:
            question_index = _comparison_matrix_question_index(comparison_item)
            item_payload = _comparison_matrix_item_payload(
                comparison_item,
                repair_target_type=repair_target_type,
                repair_target_key=repair_target_key,
            )
            stable_source = "|".join(
                [
                    profile_key,
                    question_index,
                    item_payload.get("item_id", ""),
                    item_payload.get("asset_id", ""),
                    item_payload.get("path", ""),
                    item_payload.get("reference", ""),
                    source_issue_id,
                ]
            )
            digest = hashlib.sha1(stable_source.encode("utf-8")).hexdigest()[:12]
            queue_id = (
                "repair:question_figure:"
                f"{_repair_queue_token(profile_key)}:"
                f"q{_repair_queue_token(question_index)}:{digest}"
            )
            if queue_id in seen_queue_ids:
                continue
            seen_queue_ids.add(queue_id)
            apply_plan = _question_figure_repair_apply_plan(
                item_payload,
                repair_target_type=repair_target_type,
                repair_target_key=repair_target_key,
            )
            entries.append(
                {
                    "queue_id": queue_id,
                    "kind": "question_figure_repair_candidate",
                    "action": "review_question_figure_replacement",
                    "status": "candidate",
                    "profile_id": profile_id,
                    "profile_name": profile_name,
                    "question_index": question_index,
                    "item_id": item_payload.get("item_id", ""),
                    "label": item_payload.get("label", ""),
                    "asset_id": item_payload.get("asset_id", ""),
                    "current_path": item_payload.get("path", ""),
                    "cache_path": item_payload.get("cache_path", ""),
                    "comparison_reference": item_payload.get("reference", ""),
                    "comparison_display_name": item_payload.get("display_name", ""),
                    "issue_kind": item_payload.get("issue_kind", ""),
                    "issue_type": item_payload.get("issue_type", ""),
                    "issue_summary": item_payload.get("summary") or source_summary,
                    "marked_at": item_payload.get("marked_at", ""),
                    "region_type": item_payload.get("region_type", ""),
                    "region_summary": item_payload.get("region_summary", ""),
                    "region_json": item_payload.get("region_json", ""),
                    "repair_target_type": repair_target_type,
                    "repair_target_key": repair_target_key,
                    "source_issue_id": source_issue_id,
                    "source_kind": source_kind,
                    "review_surface": "assets_panel.question_figure_item",
                    "requires_user_confirmation": True,
                    "auto_apply_supported": False,
                    **apply_plan,
                    "reason": (
                        "Review the manually flagged question figure before "
                        "applying any replacement."
                    ),
                }
            )

    _apply_question_figure_repair_queue_conflict_guard(entries)
    payload = {
        "kind": "question_figure_repair_queue",
        "entries": entries,
    }
    _refresh_question_figure_repair_queue_status(payload)
    return payload


def _apply_question_figure_repair_queue_conflict_guard(
    entries: list[dict[str, object]],
) -> list[list[dict[str, object]]]:
    by_target: dict[str, list[dict[str, object]]] = {}
    for entry in entries:
        if not bool(entry.get("confirmation_apply_supported")):
            continue
        if _clean_text(entry.get("confirmation_status")) != "ready":
            continue
        target_type = _clean_text(entry.get("repair_target_type"))
        target_key = _clean_text(entry.get("repair_target_key"))
        if not target_type or not target_key:
            continue
        group_key = f"{target_type}|{target_key}"
        by_target.setdefault(group_key, []).append(entry)

    conflict_groups = [
        group for group in by_target.values() if len(group) > 1
    ]
    for index, group in enumerate(conflict_groups, start=1):
        digest = hashlib.sha1(
            "|".join(_clean_text(item.get("queue_id")) for item in group).encode(
                "utf-8"
            )
        ).hexdigest()[:12]
        conflict_group_id = f"repair-conflict:{index}:{digest}"
        for item in group:
            blockers = [
                _clean_text(blocker)
                for blocker in list(item.get("apply_blockers") or [])
                if _clean_text(blocker)
            ]
            if "candidate_conflict_same_repair_target" not in blockers:
                blockers.append("candidate_conflict_same_repair_target")
            selection_blockers = [
                blocker
                for blocker in blockers
                if blocker != "candidate_conflict_same_repair_target"
            ]
            selection_supported = (
                _clean_text(item.get("replacement_source_kind")) == "local_file"
                and bool(_clean_text(item.get("replacement_source_path")))
                and not selection_blockers
            )
            item["confirmation_apply_supported"] = False
            item["confirmation_status"] = "conflict"
            item["confirmation_action"] = "resolve_question_figure_replacement_conflict"
            item["conflict_resolution_select_supported"] = selection_supported
            item["conflict_resolution_action"] = (
                "select_question_figure_replacement_conflict_candidate"
                if selection_supported
                else "review_question_figure_replacement_conflict"
            )
            item["conflict_group_id"] = conflict_group_id
            item["conflict_candidate_count"] = len(group)
            item["conflict_candidate_queue_ids"] = [
                _clean_text(candidate.get("queue_id")) for candidate in group
            ]
            item["apply_blockers"] = blockers
    return conflict_groups


def _question_figure_repair_batch_confirmation_plan(
    entries: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> dict[str, object]:
    clean_entries = [
        entry for entry in list(entries or []) if isinstance(entry, Mapping)
    ]
    eligible_entries: list[dict[str, object]] = []
    blocked_entries: list[dict[str, object]] = []
    ready_by_target: dict[str, list[dict[str, object]]] = {}

    def _append_reason(reasons: list[str], reason: str) -> None:
        normalized = _clean_text(reason)
        if normalized and normalized not in reasons:
            reasons.append(normalized)

    for index, entry in enumerate(clean_entries, start=1):
        queue_id = _clean_text(entry.get("queue_id")) or f"entry:{index}"
        repair_target_type = _clean_text(entry.get("repair_target_type"))
        repair_target_key = _clean_text(entry.get("repair_target_key"))
        confirmation_status = _clean_text(entry.get("confirmation_status"))
        replacement_source_kind = _clean_text(entry.get("replacement_source_kind"))
        replacement_source_path = _clean_text(entry.get("replacement_source_path"))
        reasons = _clean_list(entry.get("apply_blockers"))

        if repair_target_type != "question_figure_item":
            _append_reason(reasons, "unsupported_repair_target")
        if not repair_target_key:
            _append_reason(reasons, "repair_target_missing")
        if confirmation_status != "ready":
            _append_reason(
                reasons,
                f"confirmation_status_{confirmation_status or 'missing'}",
            )
        if not bool(entry.get("confirmation_apply_supported")):
            _append_reason(reasons, "confirmation_apply_not_supported")
        if replacement_source_kind != "local_file":
            _append_reason(reasons, "replacement_source_not_local_file")
        if not replacement_source_path:
            _append_reason(reasons, "replacement_source_missing")
        elif not _is_local_file(replacement_source_path):
            _append_reason(reasons, "replacement_source_file_missing")

        plan_entry = {
            "queue_id": queue_id,
            "profile_id": _clean_text(entry.get("profile_id")),
            "profile_name": _clean_text(entry.get("profile_name")),
            "question_index": _clean_text(entry.get("question_index")),
            "repair_target_type": repair_target_type,
            "repair_target_key": repair_target_key,
            "replacement_source_path": replacement_source_path,
            "replacement_source_kind": replacement_source_kind,
            "confirmation_status": confirmation_status,
            "blockers": reasons,
        }
        if reasons:
            blocked_entries.append(plan_entry)
            continue
        eligible_entries.append(plan_entry)
        ready_by_target.setdefault(repair_target_key, []).append(plan_entry)

    duplicate_target_groups: list[dict[str, object]] = []
    duplicate_queue_ids: set[str] = set()
    for target_key, group in ready_by_target.items():
        if len(group) <= 1:
            continue
        queue_ids = [_clean_text(item.get("queue_id")) for item in group]
        queue_ids = [queue_id for queue_id in queue_ids if queue_id]
        duplicate_target_groups.append(
            {
                "repair_target_key": target_key,
                "queue_ids": queue_ids,
            }
        )
        duplicate_queue_ids.update(queue_ids)

    if duplicate_queue_ids:
        still_eligible: list[dict[str, object]] = []
        for entry in eligible_entries:
            queue_id = _clean_text(entry.get("queue_id"))
            if queue_id not in duplicate_queue_ids:
                still_eligible.append(entry)
                continue
            duplicate_entry = dict(entry)
            blockers = _clean_list(duplicate_entry.get("blockers"))
            _append_reason(blockers, "duplicate_ready_candidate_same_repair_target")
            duplicate_entry["blockers"] = blockers
            blocked_entries.append(duplicate_entry)
        eligible_entries = still_eligible

    conflict_queue_ids = [
        _clean_text(entry.get("queue_id"))
        for entry in clean_entries
        if _clean_text(entry.get("confirmation_status")) == "conflict"
        and _clean_text(entry.get("queue_id"))
    ]
    target_count = len(
        {
            _clean_text(entry.get("repair_target_key"))
            for entry in clean_entries
            if _clean_text(entry.get("repair_target_key"))
        }
    )
    eligible_count = len(eligible_entries)
    blocked_count = len(blocked_entries)
    if not clean_entries:
        status = "empty"
    elif eligible_count and blocked_count:
        status = "partial"
    elif eligible_count:
        status = "ready"
    else:
        status = "blocked"

    plan = {
        "kind": "question_figure_repair_batch_confirmation_plan",
        "status": status,
        "action": "review_question_figure_repair_batch_confirmation_plan",
        "requires_user_confirmation": bool(clean_entries),
        "auto_apply_supported": False,
        "batch_apply_supported": False,
        "batch_confirmation_supported": eligible_count > 0,
        "entry_count": len(clean_entries),
        "target_count": target_count,
        "eligible_count": eligible_count,
        "blocked_count": blocked_count,
        "conflict_count": len(conflict_queue_ids),
        "duplicate_target_count": len(duplicate_target_groups),
        "eligible_queue_ids": [
            _clean_text(entry.get("queue_id"))
            for entry in eligible_entries
            if _clean_text(entry.get("queue_id"))
        ],
        "blocked_queue_ids": [
            _clean_text(entry.get("queue_id"))
            for entry in blocked_entries
            if _clean_text(entry.get("queue_id"))
        ],
        "conflict_queue_ids": conflict_queue_ids,
        "duplicate_target_groups": duplicate_target_groups,
        "eligible_entries": eligible_entries,
        "blocked_entries": blocked_entries,
    }
    plan["plan_fingerprint"] = _question_figure_repair_batch_plan_fingerprint(plan)
    return plan


def _question_figure_repair_batch_plan_fingerprint(
    plan: Mapping[str, object],
) -> str:
    fingerprint_payload = {
        key: value
        for key, value in dict(plan).items()
        if key != "plan_fingerprint"
    }
    return hashlib.sha1(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]


def _freeze_question_figure_repair_batch_confirmation_plan(
    question_figure_repair_queue: Mapping[str, object],
    selected_queue_ids: Sequence[str] | str | None = None,
    *,
    confirmed: bool = False,
    confirmed_by: str = "manual",
    confirmation_note: str = "",
    expected_plan_fingerprint: str = "",
) -> dict[str, object]:
    """Return a queue copy with a frozen, explicitly confirmed batch plan."""

    if not isinstance(question_figure_repair_queue, Mapping):
        return {
            "kind": "question_figure_repair_queue",
            "status": "empty",
            "queue_count": 0,
            "conflict_group_count": 0,
            "conflict_count": 0,
            "entries": [],
            "batch_confirmation_freeze": {
                "kind": "question_figure_repair_batch_confirmation_freeze",
                "status": "blocked",
                "confirmed": bool(confirmed),
                "blockers": ["invalid_repair_queue"],
                "batch_apply_supported": False,
            },
        }

    payload = copy.deepcopy(dict(question_figure_repair_queue))
    entries = [
        entry
        for entry in list(payload.get("entries") or [])
        if isinstance(entry, dict)
    ]
    payload["entries"] = entries
    _refresh_question_figure_repair_queue_status(payload)
    plan = dict(payload.get("batch_confirmation_plan") or {})
    plan_fingerprint = _clean_text(plan.get("plan_fingerprint"))
    if not plan_fingerprint:
        plan_fingerprint = _question_figure_repair_batch_plan_fingerprint(plan)
        plan["plan_fingerprint"] = plan_fingerprint
        payload["batch_confirmation_plan"] = plan

    eligible_queue_ids = _clean_list(plan.get("eligible_queue_ids"))
    if selected_queue_ids is None:
        requested_queue_ids = list(eligible_queue_ids)
    elif isinstance(selected_queue_ids, str):
        requested_queue_ids = _clean_list([selected_queue_ids])
    else:
        requested_queue_ids = _clean_list(selected_queue_ids)
    requested_queue_ids = list(dict.fromkeys(requested_queue_ids))

    freeze = {
        "kind": "question_figure_repair_batch_confirmation_freeze",
        "action": "freeze_question_figure_repair_batch_confirmation_plan",
        "confirmed": bool(confirmed),
        "confirmed_by": _clean_text(confirmed_by) or "manual",
        "confirmed_at": _utc_now_iso() if confirmed else "",
        "confirmation_note": _clean_text(confirmation_note),
        "plan_fingerprint": plan_fingerprint,
        "expected_plan_fingerprint": _clean_text(expected_plan_fingerprint),
        "fingerprint_matched": True,
        "requested_queue_ids": requested_queue_ids,
        "frozen_queue_ids": [],
        "frozen_candidate_count": 0,
        "frozen_target_count": 0,
        "blocked_count": int(plan.get("blocked_count") or 0),
        "conflict_count": int(plan.get("conflict_count") or 0),
        "duplicate_target_count": int(plan.get("duplicate_target_count") or 0),
        "blocked_queue_ids": _clean_list(plan.get("blocked_queue_ids")),
        "conflict_queue_ids": _clean_list(plan.get("conflict_queue_ids")),
        "eligible_queue_ids": eligible_queue_ids,
        "frozen_entries": [],
        "excluded_eligible_queue_ids": [],
        "blockers": [],
        "requires_user_confirmation": True,
        "batch_apply_supported": False,
        "execution_plan_ready": False,
    }

    blockers: list[str] = []
    if not confirmed:
        blockers.append("manual_confirmation_required")
    expected = _clean_text(expected_plan_fingerprint)
    if expected and expected != plan_fingerprint:
        freeze["fingerprint_matched"] = False
        blockers.append("plan_fingerprint_mismatch")
    if not requested_queue_ids:
        blockers.append("no_eligible_candidates")
    invalid_queue_ids = [
        queue_id for queue_id in requested_queue_ids if queue_id not in eligible_queue_ids
    ]
    if invalid_queue_ids:
        blockers.append("selected_queue_id_not_eligible")
        freeze["invalid_queue_ids"] = invalid_queue_ids

    if blockers:
        freeze["status"] = "not_confirmed" if not confirmed else "blocked"
        freeze["blockers"] = blockers
        payload["batch_confirmation_freeze"] = freeze
        return payload

    eligible_entries = [
        dict(entry)
        for entry in list(plan.get("eligible_entries") or [])
        if isinstance(entry, Mapping)
    ]
    eligible_by_id = {
        _clean_text(entry.get("queue_id")): entry
        for entry in eligible_entries
        if _clean_text(entry.get("queue_id"))
    }
    frozen_entries = [
        eligible_by_id[queue_id]
        for queue_id in requested_queue_ids
        if queue_id in eligible_by_id
    ]
    frozen_targets = {
        _clean_text(entry.get("repair_target_key"))
        for entry in frozen_entries
        if _clean_text(entry.get("repair_target_key"))
    }
    freeze["status"] = (
        "partial_frozen"
        if freeze["blocked_count"]
        or freeze["conflict_count"]
        or freeze["duplicate_target_count"]
        or len(requested_queue_ids) < len(eligible_queue_ids)
        else "frozen"
    )
    freeze["freeze_id"] = (
        "question-figure-batch-freeze:"
        + hashlib.sha1(
            "|".join([plan_fingerprint, *requested_queue_ids]).encode("utf-8")
        ).hexdigest()[:12]
    )
    freeze["frozen_queue_ids"] = requested_queue_ids
    freeze["frozen_candidate_count"] = len(frozen_entries)
    freeze["frozen_target_count"] = len(frozen_targets)
    freeze["frozen_entries"] = frozen_entries
    freeze["excluded_eligible_queue_ids"] = [
        queue_id for queue_id in eligible_queue_ids if queue_id not in requested_queue_ids
    ]
    freeze["execution_plan_ready"] = bool(frozen_entries)
    payload["batch_confirmation_freeze"] = freeze
    return payload


def _dry_run_question_figure_repair_batch_apply_guard(
    question_figure_repair_queue: Mapping[str, object],
    *,
    expected_freeze_id: str = "",
    expected_plan_fingerprint: str = "",
) -> dict[str, object]:
    """Return a queue copy with a non-mutating batch-apply dry-run guard."""

    if not isinstance(question_figure_repair_queue, Mapping):
        return {
            "kind": "question_figure_repair_queue",
            "status": "empty",
            "queue_count": 0,
            "conflict_group_count": 0,
            "conflict_count": 0,
            "entries": [],
            "batch_apply_dry_run": {
                "kind": "question_figure_repair_batch_apply_dry_run",
                "status": "blocked",
                "blockers": ["invalid_repair_queue"],
                "batch_apply_supported": False,
                "execution_guard_passed": False,
            },
        }

    payload = copy.deepcopy(dict(question_figure_repair_queue))
    entries = [
        entry
        for entry in list(payload.get("entries") or [])
        if isinstance(entry, dict)
    ]
    payload["entries"] = entries
    _refresh_question_figure_repair_queue_status(payload)
    plan = dict(payload.get("batch_confirmation_plan") or {})
    freeze = dict(payload.get("batch_confirmation_freeze") or {})
    current_plan_fingerprint = _clean_text(plan.get("plan_fingerprint"))
    freeze_plan_fingerprint = _clean_text(freeze.get("plan_fingerprint"))
    freeze_id = _clean_text(freeze.get("freeze_id"))
    frozen_queue_ids = _clean_list(freeze.get("frozen_queue_ids"))
    eligible_queue_ids = _clean_list(plan.get("eligible_queue_ids"))
    eligible_entries = [
        dict(entry)
        for entry in list(plan.get("eligible_entries") or [])
        if isinstance(entry, Mapping)
    ]
    eligible_by_id = {
        _clean_text(entry.get("queue_id")): entry
        for entry in eligible_entries
        if _clean_text(entry.get("queue_id"))
    }
    current_entries_by_id = {
        _clean_text(entry.get("queue_id")): entry
        for entry in entries
        if _clean_text(entry.get("queue_id"))
    }

    dry_run = {
        "kind": "question_figure_repair_batch_apply_dry_run",
        "action": "dry_run_question_figure_repair_batch_apply_guard",
        "status": "blocked",
        "freeze_id": freeze_id,
        "freeze_status": _clean_text(freeze.get("status")),
        "plan_fingerprint": freeze_plan_fingerprint,
        "current_plan_fingerprint": current_plan_fingerprint,
        "expected_plan_fingerprint": _clean_text(expected_plan_fingerprint),
        "expected_freeze_id": _clean_text(expected_freeze_id),
        "fingerprint_matched": bool(
            freeze_plan_fingerprint
            and current_plan_fingerprint
            and freeze_plan_fingerprint == current_plan_fingerprint
        ),
        "checked_queue_ids": frozen_queue_ids,
        "checked_candidate_count": 0,
        "checked_target_count": 0,
        "ready_queue_ids": [],
        "blocked_queue_ids": [],
        "candidate_results": [],
        "blockers": [],
        "requires_user_confirmation": True,
        "batch_apply_supported": False,
        "execution_guard_passed": False,
    }

    blockers: list[str] = []
    if not freeze:
        blockers.append("batch_confirmation_freeze_missing")
    if _clean_text(freeze.get("status")) not in {"frozen", "partial_frozen"}:
        blockers.append("batch_confirmation_freeze_not_ready")
    if not bool(freeze.get("confirmed")):
        blockers.append("batch_confirmation_freeze_not_confirmed")
    freeze_blockers = _clean_list(freeze.get("blockers"))
    if freeze_blockers:
        blockers.append("batch_confirmation_freeze_has_blockers")
        dry_run["freeze_blockers"] = freeze_blockers
    expected_freeze = _clean_text(expected_freeze_id)
    if expected_freeze and expected_freeze != freeze_id:
        blockers.append("freeze_id_mismatch")
    expected_plan = _clean_text(expected_plan_fingerprint)
    if expected_plan and expected_plan != freeze_plan_fingerprint:
        blockers.append("expected_plan_fingerprint_mismatch")
    if not dry_run["fingerprint_matched"]:
        blockers.append("plan_fingerprint_mismatch")
    if not frozen_queue_ids:
        blockers.append("no_frozen_candidates")

    target_counts: dict[str, int] = {}
    candidate_results: list[dict[str, object]] = []
    ready_queue_ids: list[str] = []
    blocked_queue_ids: list[str] = []
    for queue_id in frozen_queue_ids:
        plan_entry = eligible_by_id.get(queue_id, {})
        current_entry = current_entries_by_id.get(queue_id, {})
        repair_target_key = _clean_text(
            plan_entry.get("repair_target_key")
            or current_entry.get("repair_target_key")
        )
        replacement_source_path = _clean_text(
            plan_entry.get("replacement_source_path")
            or current_entry.get("replacement_source_path")
        )
        result_blockers: list[str] = []
        if queue_id not in eligible_queue_ids:
            result_blockers.append("frozen_candidate_not_currently_eligible")
        if not repair_target_key:
            result_blockers.append("repair_target_missing")
        if not replacement_source_path:
            result_blockers.append("replacement_source_missing")
        elif not _is_local_file(replacement_source_path):
            result_blockers.append("replacement_source_file_missing")
        if repair_target_key:
            target_counts[repair_target_key] = target_counts.get(repair_target_key, 0) + 1
        if result_blockers:
            blocked_queue_ids.append(queue_id)
        else:
            ready_queue_ids.append(queue_id)
        candidate_results.append(
            {
                "queue_id": queue_id,
                "status": "blocked" if result_blockers else "ready",
                "repair_target_key": repair_target_key,
                "replacement_source_path": replacement_source_path,
                "blockers": result_blockers,
            }
        )

    duplicate_targets = [
        target_key for target_key, count in target_counts.items() if count > 1
    ]
    if duplicate_targets:
        blockers.append("duplicate_frozen_target")
        dry_run["duplicate_target_keys"] = duplicate_targets
        for result in candidate_results:
            if _clean_text(result.get("repair_target_key")) in duplicate_targets:
                result_blockers = _clean_list(result.get("blockers"))
                if "duplicate_frozen_target" not in result_blockers:
                    result_blockers.append("duplicate_frozen_target")
                result["blockers"] = result_blockers
                result["status"] = "blocked"
                queue_id = _clean_text(result.get("queue_id"))
                if queue_id in ready_queue_ids:
                    ready_queue_ids.remove(queue_id)
                if queue_id and queue_id not in blocked_queue_ids:
                    blocked_queue_ids.append(queue_id)

    if blocked_queue_ids:
        blockers.append("frozen_candidate_guard_failed")

    blockers = list(dict.fromkeys(blockers))
    dry_run["candidate_results"] = candidate_results
    dry_run["ready_queue_ids"] = ready_queue_ids
    dry_run["blocked_queue_ids"] = blocked_queue_ids
    dry_run["checked_candidate_count"] = len(candidate_results)
    dry_run["checked_target_count"] = len(
        {
            _clean_text(result.get("repair_target_key"))
            for result in candidate_results
            if _clean_text(result.get("repair_target_key"))
        }
    )
    dry_run["blockers"] = blockers
    if not blockers:
        dry_run["status"] = "ready"
        dry_run["execution_guard_passed"] = True
    payload["batch_apply_dry_run"] = dry_run
    return payload


def _plan_question_figure_repair_batch_apply_execution(
    question_figure_repair_queue: Mapping[str, object],
    *,
    confirmed: bool = False,
    confirmed_by: str = "manual",
    confirmation_note: str = "",
    expected_freeze_id: str = "",
    expected_plan_fingerprint: str = "",
) -> dict[str, object]:
    """Return a queue copy with a non-mutating batch-apply execution draft."""

    if not isinstance(question_figure_repair_queue, Mapping):
        return {
            "kind": "question_figure_repair_queue",
            "status": "empty",
            "queue_count": 0,
            "conflict_group_count": 0,
            "conflict_count": 0,
            "entries": [],
            "batch_apply_execution_plan": {
                "kind": "question_figure_repair_batch_apply_execution_plan",
                "action": "plan_question_figure_repair_batch_apply_execution",
                "status": "blocked",
                "blockers": ["invalid_repair_queue"],
                "requires_final_user_confirmation": True,
                "final_confirmation_provided": bool(confirmed),
                "batch_apply_supported": False,
                "execution_plan_ready": False,
            },
        }

    payload = copy.deepcopy(dict(question_figure_repair_queue))
    entries = [
        entry
        for entry in list(payload.get("entries") or [])
        if isinstance(entry, dict)
    ]
    payload["entries"] = entries
    _refresh_question_figure_repair_queue_status(payload)

    existing_dry_run = (
        dict(payload.get("batch_apply_dry_run"))
        if isinstance(payload.get("batch_apply_dry_run"), Mapping)
        else {}
    )
    expected_freeze = _clean_text(expected_freeze_id)
    expected_plan = _clean_text(expected_plan_fingerprint)
    if existing_dry_run:
        payload = _dry_run_question_figure_repair_batch_apply_guard(
            payload,
            expected_freeze_id=(
                expected_freeze
                or _clean_text(existing_dry_run.get("expected_freeze_id"))
                or _clean_text(existing_dry_run.get("freeze_id"))
            ),
            expected_plan_fingerprint=(
                expected_plan
                or _clean_text(existing_dry_run.get("expected_plan_fingerprint"))
                or _clean_text(existing_dry_run.get("plan_fingerprint"))
            ),
        )
        entries = [
            entry
            for entry in list(payload.get("entries") or [])
            if isinstance(entry, dict)
        ]

    plan = dict(payload.get("batch_confirmation_plan") or {})
    freeze = dict(payload.get("batch_confirmation_freeze") or {})
    dry_run = dict(payload.get("batch_apply_dry_run") or {})
    freeze_id = _clean_text(freeze.get("freeze_id") or dry_run.get("freeze_id"))
    freeze_plan_fingerprint = _clean_text(
        freeze.get("plan_fingerprint") or dry_run.get("plan_fingerprint")
    )
    current_plan_fingerprint = _clean_text(plan.get("plan_fingerprint"))
    dry_run_status = _clean_text(dry_run.get("status"))
    dry_run_ready_ids = _clean_list(dry_run.get("ready_queue_ids"))
    dry_run_blocked_ids = _clean_list(dry_run.get("blocked_queue_ids"))
    dry_run_blockers = _clean_list(dry_run.get("blockers"))
    current_entries_by_id = {
        _clean_text(entry.get("queue_id")): entry
        for entry in entries
        if _clean_text(entry.get("queue_id"))
    }
    frozen_entries_by_id = {
        _clean_text(entry.get("queue_id")): dict(entry)
        for entry in list(freeze.get("frozen_entries") or [])
        if isinstance(entry, Mapping) and _clean_text(entry.get("queue_id"))
    }
    dry_run_results_by_id = {
        _clean_text(result.get("queue_id")): dict(result)
        for result in list(dry_run.get("candidate_results") or [])
        if isinstance(result, Mapping) and _clean_text(result.get("queue_id"))
    }

    execution_plan = {
        "kind": "question_figure_repair_batch_apply_execution_plan",
        "action": "plan_question_figure_repair_batch_apply_execution",
        "status": "blocked",
        "freeze_id": freeze_id,
        "freeze_status": _clean_text(freeze.get("status")),
        "dry_run_status": dry_run_status,
        "plan_fingerprint": freeze_plan_fingerprint,
        "current_plan_fingerprint": current_plan_fingerprint,
        "expected_freeze_id": expected_freeze,
        "expected_plan_fingerprint": expected_plan,
        "fingerprint_matched": bool(
            freeze_plan_fingerprint
            and current_plan_fingerprint
            and freeze_plan_fingerprint == current_plan_fingerprint
        ),
        "confirmed_by": _clean_text(confirmed_by) or "manual",
        "confirmed_at": _utc_now_iso() if confirmed else "",
        "confirmation_note": _clean_text(confirmation_note),
        "requires_final_user_confirmation": True,
        "final_confirmation_provided": bool(confirmed),
        "planned_queue_ids": [],
        "planned_candidate_count": 0,
        "planned_target_count": 0,
        "blocked_queue_ids": [],
        "dry_run_blocked_queue_ids": dry_run_blocked_ids,
        "planned_entries": [],
        "blockers": [],
        "batch_apply_supported": False,
        "word_write_enabled": False,
        "execution_plan_ready": False,
    }

    blockers: list[str] = []
    if not existing_dry_run:
        blockers.append("batch_apply_dry_run_missing")
    if dry_run_status != "ready":
        blockers.append("batch_apply_dry_run_not_ready")
    if not bool(dry_run.get("execution_guard_passed")):
        blockers.append("batch_apply_guard_not_passed")
    if dry_run_blockers:
        blockers.append("batch_apply_dry_run_has_blockers")
        execution_plan["dry_run_blockers"] = dry_run_blockers
    if not bool(confirmed):
        blockers.append("final_confirmation_required")
    if not expected_freeze:
        blockers.append("expected_freeze_id_required")
    elif expected_freeze != freeze_id:
        blockers.append("freeze_id_mismatch")
    if not expected_plan:
        blockers.append("expected_plan_fingerprint_required")
    elif expected_plan != freeze_plan_fingerprint:
        blockers.append("expected_plan_fingerprint_mismatch")
    if not execution_plan["fingerprint_matched"]:
        blockers.append("plan_fingerprint_mismatch")
    if not dry_run_ready_ids:
        blockers.append("no_ready_dry_run_candidates")

    target_counts: dict[str, int] = {}
    planned_entries: list[dict[str, object]] = []
    blocked_entry_queue_ids: list[str] = []
    for index, queue_id in enumerate(dry_run_ready_ids, start=1):
        dry_result = dry_run_results_by_id.get(queue_id, {})
        frozen_entry = frozen_entries_by_id.get(queue_id, {})
        current_entry = current_entries_by_id.get(queue_id, {})
        repair_target_type = _clean_text(
            frozen_entry.get("repair_target_type")
            or current_entry.get("repair_target_type")
            or "question_figure_item"
        )
        repair_target_key = _clean_text(
            dry_result.get("repair_target_key")
            or frozen_entry.get("repair_target_key")
            or current_entry.get("repair_target_key")
        )
        replacement_source_path = _clean_text(
            dry_result.get("replacement_source_path")
            or frozen_entry.get("replacement_source_path")
            or current_entry.get("replacement_source_path")
        )
        entry_blockers = _clean_list(dry_result.get("blockers"))
        if _clean_text(dry_result.get("status")) not in {"", "ready"}:
            entry_blockers.append("dry_run_candidate_not_ready")
        if repair_target_type != "question_figure_item":
            entry_blockers.append("unsupported_repair_target")
        if not repair_target_key:
            entry_blockers.append("repair_target_missing")
        if not replacement_source_path:
            entry_blockers.append("replacement_source_missing")
        elif not _is_local_file(replacement_source_path):
            entry_blockers.append("replacement_source_file_missing")
        entry_blockers = list(dict.fromkeys(entry_blockers))
        if repair_target_key:
            target_counts[repair_target_key] = target_counts.get(repair_target_key, 0) + 1
        if entry_blockers:
            blocked_entry_queue_ids.append(queue_id)
        planned_entries.append(
            {
                "step": index,
                "queue_id": queue_id,
                "operation": "replace_question_figure_asset",
                "status": "blocked" if entry_blockers else "planned",
                "profile_id": _clean_text(
                    frozen_entry.get("profile_id") or current_entry.get("profile_id")
                ),
                "profile_name": _clean_text(
                    frozen_entry.get("profile_name")
                    or current_entry.get("profile_name")
                ),
                "question_index": _clean_text(
                    frozen_entry.get("question_index")
                    or current_entry.get("question_index")
                ),
                "repair_target_type": repair_target_type,
                "repair_target_key": repair_target_key,
                "replacement_source_kind": _clean_text(
                    frozen_entry.get("replacement_source_kind")
                    or current_entry.get("replacement_source_kind")
                    or "local_file"
                ),
                "replacement_source_path": replacement_source_path,
                "source_issue_id": _clean_text(current_entry.get("source_issue_id")),
                "issue_summary": _clean_text(current_entry.get("issue_summary")),
                "guard_status": _clean_text(dry_result.get("status")) or "ready",
                "blockers": entry_blockers,
                "word_write_enabled": False,
            }
        )

    duplicate_targets = [
        target_key for target_key, count in target_counts.items() if count > 1
    ]
    if duplicate_targets:
        blockers.append("duplicate_planned_target")
        execution_plan["duplicate_target_keys"] = duplicate_targets
    if blocked_entry_queue_ids:
        blockers.append("execution_plan_entry_guard_failed")

    blockers = list(dict.fromkeys(blockers))
    planned_queue_ids = [
        _clean_text(entry.get("queue_id"))
        for entry in planned_entries
        if _clean_text(entry.get("queue_id"))
    ]
    execution_plan["planned_entries"] = planned_entries
    execution_plan["planned_queue_ids"] = planned_queue_ids
    execution_plan["planned_candidate_count"] = len(planned_entries)
    execution_plan["planned_target_count"] = len(
        {
            _clean_text(entry.get("repair_target_key"))
            for entry in planned_entries
            if _clean_text(entry.get("repair_target_key"))
        }
    )
    execution_plan["blocked_queue_ids"] = list(dict.fromkeys(blocked_entry_queue_ids))
    execution_plan["blockers"] = blockers
    if not blockers:
        execution_plan["status"] = "planned"
        execution_plan["execution_plan_ready"] = True
        execution_plan["planned_at"] = _utc_now_iso()
    fingerprint = _question_figure_repair_batch_apply_execution_plan_fingerprint(
        execution_plan
    )
    execution_plan["execution_plan_fingerprint"] = fingerprint
    execution_plan["plan_id"] = (
        "question-figure-batch-apply-plan:"
        + hashlib.sha1("|".join([freeze_id, fingerprint]).encode("utf-8")).hexdigest()[
            :12
        ]
    )
    payload["batch_apply_execution_plan"] = execution_plan
    return payload


def _question_figure_repair_batch_apply_execution_plan_fingerprint(
    execution_plan: Mapping[str, object],
) -> str:
    fingerprint_payload = {
        key: value
        for key, value in dict(execution_plan).items()
        if key not in {
            "plan_id",
            "execution_plan_fingerprint",
            "confirmed_at",
            "planned_at",
        }
    }
    return hashlib.sha1(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]


def _apply_question_figure_repair_batch_execution_to_docx(
    question_figure_repair_queue: Mapping[str, object],
    *,
    input_docx_path: str | Path,
    output_docx_path: str | Path,
    audit_dir: str | Path | None = None,
    confirmed: bool = False,
    confirmed_by: str = "manual",
    confirmation_note: str = "",
    expected_plan_id: str = "",
    expected_execution_plan_fingerprint: str = "",
) -> dict[str, object]:
    """Apply a planned question-figure repair batch to a copied docx package."""

    if not isinstance(question_figure_repair_queue, Mapping):
        return {
            "kind": "question_figure_repair_queue",
            "status": "empty",
            "queue_count": 0,
            "conflict_group_count": 0,
            "conflict_count": 0,
            "entries": [],
            "batch_apply_execution_result": {
                "kind": "question_figure_repair_batch_apply_execution_result",
                "action": "apply_question_figure_repair_batch_execution_to_docx",
                "status": "blocked",
                "blockers": ["invalid_repair_queue"],
                "batch_apply_supported": False,
                "word_write_enabled": False,
            },
        }

    payload = copy.deepcopy(dict(question_figure_repair_queue))
    entries = [
        entry
        for entry in list(payload.get("entries") or [])
        if isinstance(entry, dict)
    ]
    payload["entries"] = entries
    execution_plan = (
        dict(payload.get("batch_apply_execution_plan"))
        if isinstance(payload.get("batch_apply_execution_plan"), Mapping)
        else {}
    )
    input_text = _clean_text(input_docx_path)
    output_text = _clean_text(output_docx_path)
    input_path = Path(input_text) if input_text else Path()
    output_path = Path(output_text) if output_text else Path()
    plan_id = _clean_text(execution_plan.get("plan_id"))
    plan_fingerprint = _clean_text(
        execution_plan.get("execution_plan_fingerprint")
    )
    current_plan_fingerprint = (
        _question_figure_repair_batch_apply_execution_plan_fingerprint(
            execution_plan
        )
        if execution_plan
        else ""
    )

    result = {
        "kind": "question_figure_repair_batch_apply_execution_result",
        "action": "apply_question_figure_repair_batch_execution_to_docx",
        "status": "blocked",
        "input_path": input_text,
        "output_path": output_text,
        "plan_id": plan_id,
        "expected_plan_id": _clean_text(expected_plan_id),
        "execution_plan_fingerprint": plan_fingerprint,
        "current_execution_plan_fingerprint": current_plan_fingerprint,
        "expected_execution_plan_fingerprint": _clean_text(
            expected_execution_plan_fingerprint
        ),
        "execution_plan_fingerprint_matched": bool(
            plan_fingerprint
            and current_plan_fingerprint
            and plan_fingerprint == current_plan_fingerprint
        ),
        "confirmed": bool(confirmed),
        "confirmed_by": _clean_text(confirmed_by) or "manual",
        "confirmed_at": _utc_now_iso() if confirmed else "",
        "confirmation_note": _clean_text(confirmation_note),
        "planned_candidate_count": int(
            execution_plan.get("planned_candidate_count") or 0
        ),
        "planned_target_count": int(execution_plan.get("planned_target_count") or 0),
        "applied_count": 0,
        "applied_target_count": 0,
        "entry_results": [],
        "blockers": [],
        "audit_supported": False,
        "audit_written": False,
        "audit_path": "",
        "audit_record_id": "",
        "audit_record": {},
        "batch_apply_supported": False,
        "word_write_enabled": False,
    }

    blockers: list[str] = []
    if not execution_plan:
        blockers.append("batch_apply_execution_plan_missing")
    if _clean_text(execution_plan.get("status")) != "planned":
        blockers.append("batch_apply_execution_plan_not_planned")
    if not bool(execution_plan.get("execution_plan_ready")):
        blockers.append("batch_apply_execution_plan_not_ready")
    if not bool(confirmed):
        blockers.append("manual_execution_confirmation_required")
    expected_id = _clean_text(expected_plan_id)
    if not expected_id:
        blockers.append("expected_plan_id_required")
    elif expected_id != plan_id:
        blockers.append("plan_id_mismatch")
    expected_fingerprint = _clean_text(expected_execution_plan_fingerprint)
    if not expected_fingerprint:
        blockers.append("expected_execution_plan_fingerprint_required")
    elif expected_fingerprint != plan_fingerprint:
        blockers.append("expected_execution_plan_fingerprint_mismatch")
    if not result["execution_plan_fingerprint_matched"]:
        blockers.append("execution_plan_fingerprint_mismatch")
    if not input_text:
        blockers.append("input_docx_missing")
    elif not input_path.is_file():
        blockers.append("input_docx_missing")
    elif not zipfile.is_zipfile(input_path):
        blockers.append("input_docx_invalid")
    if not output_text:
        blockers.append("output_docx_missing")
    elif input_path.exists() and input_path.resolve() == output_path.resolve():
        blockers.append("output_docx_must_differ_from_input")

    planned_entries = [
        dict(entry)
        for entry in list(execution_plan.get("planned_entries") or [])
        if isinstance(entry, Mapping)
    ]
    if not planned_entries:
        blockers.append("no_planned_entries")

    media_hash_map: dict[str, list[str]] = {}
    media_entries: list[str] = []
    if input_path.is_file() and zipfile.is_zipfile(input_path):
        try:
            with zipfile.ZipFile(input_path) as archive:
                for name in archive.namelist():
                    if name.startswith("word/media/") and not name.endswith("/"):
                        media_entries.append(name)
                        digest = hashlib.sha1(archive.read(name)).hexdigest()
                        media_hash_map.setdefault(digest, []).append(name)
        except (OSError, zipfile.BadZipFile):
            blockers.append("input_docx_media_scan_failed")

    if input_path.is_file() and zipfile.is_zipfile(input_path) and not media_entries:
        blockers.append("input_docx_media_missing")

    entry_results: list[dict[str, object]] = []
    replacements: dict[str, bytes] = {}
    replacement_targets: set[str] = set()
    for entry in planned_entries:
        queue_id = _clean_text(entry.get("queue_id"))
        repair_target_key = _clean_text(entry.get("repair_target_key"))
        replacement_source_path = _clean_text(entry.get("replacement_source_path"))
        entry_blockers = _clean_list(entry.get("blockers"))
        target_payload = _question_figure_repair_target_payload(repair_target_key)
        original_path = _clean_text(target_payload.get("path"))
        target_question_index = _clean_text(target_payload.get("question_index"))
        target_item_id = _clean_text(target_payload.get("item_id"))
        media_path = ""
        original_digest = ""
        replacement_digest = ""
        if _clean_text(entry.get("status")) != "planned":
            entry_blockers.append("execution_plan_entry_not_planned")
        if not original_path:
            entry_blockers.append("repair_target_original_path_missing")
        elif not Path(original_path).is_file():
            entry_blockers.append("repair_target_original_file_missing")
        else:
            original_digest = _file_sha1(Path(original_path))
        if not replacement_source_path:
            entry_blockers.append("replacement_source_missing")
        elif not Path(replacement_source_path).is_file():
            entry_blockers.append("replacement_source_file_missing")
        else:
            replacement_digest = _file_sha1(Path(replacement_source_path))
        if original_digest:
            matches = media_hash_map.get(original_digest, [])
            if len(matches) == 1:
                media_path = matches[0]
            elif not matches:
                entry_blockers.append("docx_media_match_missing")
            else:
                entry_blockers.append("docx_media_match_ambiguous")
        if media_path and media_path in replacement_targets:
            entry_blockers.append("duplicate_docx_media_target")
        if (
            media_path
            and replacement_source_path
            and Path(media_path).suffix.lower()
            != Path(replacement_source_path).suffix.lower()
        ):
            entry_blockers.append("replacement_media_extension_mismatch")
        entry_blockers = list(dict.fromkeys(entry_blockers))
        if not entry_blockers and media_path:
            replacements[media_path] = Path(replacement_source_path).read_bytes()
            replacement_targets.add(media_path)
        entry_results.append(
            {
                "queue_id": queue_id,
                "status": "blocked" if entry_blockers else "ready",
                "media_path": media_path,
                "repair_target_key": repair_target_key,
                "question_index": target_question_index,
                "item_id": target_item_id,
                "original_path": original_path,
                "replacement_source_path": replacement_source_path,
                "original_sha1": original_digest,
                "replacement_sha1": replacement_digest,
                "blockers": entry_blockers,
            }
        )
    blocked_queue_ids = [
        _clean_text(entry.get("queue_id"))
        for entry in entry_results
        if _clean_text(entry.get("queue_id"))
        and _clean_text(entry.get("status")) == "blocked"
    ]
    if blocked_queue_ids:
        blockers.append("execution_entry_guard_failed")
        result["blocked_queue_ids"] = blocked_queue_ids

    blockers = list(dict.fromkeys(blockers))
    result["entry_results"] = entry_results
    result["blockers"] = blockers
    if blockers:
        payload["batch_apply_execution_result"] = result
        return payload

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path) as source_archive:
            with zipfile.ZipFile(
                output_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as output_archive:
                for info in source_archive.infolist():
                    data = replacements.get(
                        info.filename,
                        source_archive.read(info.filename),
                    )
                    output_archive.writestr(info, data)
    except (OSError, zipfile.BadZipFile):
        result["blockers"] = ["output_docx_write_failed"]
        payload["batch_apply_execution_result"] = result
        return payload

    applied_entries = [
        dict(entry, status="applied")
        for entry in entry_results
        if _clean_text(entry.get("status")) == "ready"
    ]
    result["status"] = "applied"
    result["entry_results"] = applied_entries
    result["applied_count"] = len(applied_entries)
    result["applied_target_count"] = len(
        {
            _clean_text(entry.get("media_path"))
            for entry in applied_entries
            if _clean_text(entry.get("media_path"))
        }
    )
    result["output_sha1"] = _file_sha1(output_path)
    result["batch_apply_supported"] = True
    result["word_write_enabled"] = True
    audit_record = _question_figure_batch_apply_audit_record(
        result,
        execution_plan=execution_plan,
    )
    audit_base_dir = (
        Path(str(audit_dir))
        if audit_dir is not None and _clean_text(audit_dir)
        else output_path.parent
    )
    audit_record = _append_question_figure_batch_apply_audit_record(
        audit_base_dir,
        audit_record,
    )
    result["audit_supported"] = True
    result["audit_written"] = bool(_clean_text(audit_record.get("artifact_path")))
    result["audit_path"] = _clean_text(audit_record.get("artifact_path"))
    result["audit_record_id"] = _clean_text(audit_record.get("audit_id"))
    result["audit_record"] = audit_record
    payload["batch_apply_execution_result"] = result
    payload["batch_apply_transaction_manifest"] = (
        _write_question_figure_batch_apply_transaction_manifest(
            _question_figure_batch_apply_transaction_manifest_from_audit(
                result["audit_path"],
                expected_apply_audit_id=result["audit_record_id"],
            )
        )
    )
    return payload


def _question_figure_batch_apply_audit_record(
    execution_result: Mapping[str, object],
    *,
    execution_plan: Mapping[str, object],
) -> dict[str, object]:
    confirmed_at = _clean_text(execution_result.get("confirmed_at")) or _utc_now_iso()
    plan_id = _clean_text(execution_result.get("plan_id"))
    output_path = _clean_text(execution_result.get("output_path"))
    output_sha1 = _clean_text(execution_result.get("output_sha1"))
    audit_id = (
        "question-figure-batch-apply-audit:"
        + hashlib.sha1(
            "|".join([plan_id, output_path, output_sha1, confirmed_at]).encode(
                "utf-8"
            )
        ).hexdigest()[:16]
    )
    entry_results = [
        dict(entry)
        for entry in list(execution_result.get("entry_results") or [])
        if isinstance(entry, Mapping)
    ]
    return {
        "audit_id": audit_id,
        "kind": "question_figure_repair_batch_apply_audit_record",
        "action": "question_figure_repair_batch_apply_word_media_write",
        "status": _clean_text(execution_result.get("status")) or "blocked",
        "confirmed": bool(execution_result.get("confirmed")),
        "confirmed_by": _clean_text(execution_result.get("confirmed_by")) or "manual",
        "confirmed_at": confirmed_at,
        "confirmation_note": _clean_text(execution_result.get("confirmation_note")),
        "plan_id": plan_id,
        "execution_plan_fingerprint": _clean_text(
            execution_result.get("execution_plan_fingerprint")
        ),
        "freeze_id": _clean_text(execution_plan.get("freeze_id")),
        "dry_run_status": _clean_text(execution_plan.get("dry_run_status")),
        "input_path": _clean_text(execution_result.get("input_path")),
        "output_path": output_path,
        "output_sha1": output_sha1,
        "planned_candidate_count": int(
            execution_result.get("planned_candidate_count") or 0
        ),
        "planned_target_count": int(
            execution_result.get("planned_target_count") or 0
        ),
        "applied_count": int(execution_result.get("applied_count") or 0),
        "applied_target_count": int(
            execution_result.get("applied_target_count") or 0
        ),
        "entry_results": entry_results,
    }


def _append_question_figure_batch_apply_audit_record(
    audit_dir: Path | None,
    record: Mapping[str, object],
) -> dict[str, object]:
    normalized_record = dict(record)
    if audit_dir is None:
        normalized_record["artifact_path"] = ""
        return normalized_record
    try:
        audit_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        normalized_record["artifact_path"] = ""
        return normalized_record
    history_path = audit_dir / "question_figure_batch_apply_audit.json"
    payload = _read_question_figure_batch_apply_audit_payload(history_path)
    records = payload.get("records", [])
    if not isinstance(records, list):
        records = []
    audit_id = _clean_text(normalized_record.get("audit_id"))
    if audit_id:
        records = [
            item
            for item in records
            if not isinstance(item, Mapping)
            or _clean_text(item.get("audit_id")) != audit_id
        ]
    normalized_record["artifact_path"] = str(history_path)
    records.append(dict(normalized_record))
    records = records[-100:]
    payload["schema_version"] = 1
    payload["kind"] = "question_figure_repair_batch_apply_audit"
    payload["entry_count"] = len(records)
    payload["records"] = records
    payload["updated_at"] = _clean_text(normalized_record.get("confirmed_at"))
    try:
        history_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        normalized_record["artifact_path"] = ""
    return normalized_record


def _read_question_figure_batch_apply_audit_payload(
    history_path: Path,
) -> dict[str, object]:
    if not history_path.exists() or not history_path.is_file():
        return {
            "schema_version": 1,
            "kind": "question_figure_repair_batch_apply_audit",
            "records": [],
        }
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "schema_version": 1,
            "kind": "question_figure_repair_batch_apply_audit",
            "records": [],
        }
    return (
        payload
        if isinstance(payload, dict)
        else {
            "schema_version": 1,
            "kind": "question_figure_repair_batch_apply_audit",
            "records": [],
        }
    )


def _question_figure_batch_apply_transaction_manifest_from_audit(
    history_path: str | Path,
    *,
    expected_apply_audit_id: str = "",
) -> dict[str, object]:
    """Summarize apply/rollback audit records into transaction state."""

    audit_path_text = _clean_text(history_path)
    expected_id = _clean_text(expected_apply_audit_id)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "kind": "question_figure_repair_batch_apply_transaction_manifest",
        "status": "blocked",
        "audit_path": audit_path_text,
        "expected_apply_audit_id": expected_id,
        "expected_apply_audit_found": False,
        "transaction_count": 0,
        "active_count": 0,
        "rolled_back_count": 0,
        "orphan_rollback_count": 0,
        "transactions": [],
        "orphan_rollback_records": [],
        "blockers": [],
    }
    if not audit_path_text:
        manifest["blockers"] = ["audit_history_path_missing"]
        manifest["task_summary"] = (
            _question_figure_batch_apply_transaction_task_summary(manifest)
        )
        return manifest
    history_path_obj = Path(audit_path_text)
    if not history_path_obj.is_file():
        manifest["blockers"] = ["audit_history_missing"]
        manifest["task_summary"] = (
            _question_figure_batch_apply_transaction_task_summary(manifest)
        )
        return manifest

    payload = _read_question_figure_batch_apply_audit_payload(history_path_obj)
    records = [
        dict(record)
        for record in list(payload.get("records") or [])
        if isinstance(record, Mapping)
    ]
    apply_records = [
        record
        for record in records
        if _clean_text(record.get("action"))
        == "question_figure_repair_batch_apply_word_media_write"
    ]
    rollback_records = [
        record
        for record in records
        if _clean_text(record.get("action"))
        == "question_figure_repair_batch_apply_word_media_rollback"
    ]
    rollback_by_apply_id: dict[str, list[dict[str, object]]] = {}
    for record in rollback_records:
        linked_apply_id = _clean_text(record.get("linked_apply_audit_id"))
        rollback_by_apply_id.setdefault(linked_apply_id, []).append(record)

    transactions: list[dict[str, object]] = []
    seen_apply_ids: set[str] = set()
    for record in apply_records:
        apply_id = _clean_text(record.get("audit_id"))
        if not apply_id:
            continue
        seen_apply_ids.add(apply_id)
        rollbacks = list(rollback_by_apply_id.get(apply_id) or [])
        latest_rollback = rollbacks[-1] if rollbacks else {}
        latest_rollback_status = _clean_text(latest_rollback.get("status"))
        transaction_status = (
            "rolled_back"
            if latest_rollback_status == "rolled_back"
            else _clean_text(record.get("status")) or "applied"
        )
        rollback_audit_ids = [
            _clean_text(item.get("audit_id"))
            for item in rollbacks
            if _clean_text(item.get("audit_id"))
        ]
        transaction_id = (
            "question-figure-batch-transaction:"
            + hashlib.sha1(apply_id.encode("utf-8")).hexdigest()[:16]
        )
        transactions.append(
            {
                "transaction_id": transaction_id,
                "transaction_status": transaction_status,
                "apply_audit_id": apply_id,
                "apply_status": _clean_text(record.get("status")) or "applied",
                "plan_id": _clean_text(record.get("plan_id")),
                "execution_plan_fingerprint": _clean_text(
                    record.get("execution_plan_fingerprint")
                ),
                "input_path": _clean_text(record.get("input_path")),
                "applied_output_path": _clean_text(record.get("output_path")),
                "applied_output_sha1": _clean_text(record.get("output_sha1")),
                "applied_count": int(record.get("applied_count") or 0),
                "applied_target_count": int(record.get("applied_target_count") or 0),
                "apply_confirmed_at": _clean_text(record.get("confirmed_at")),
                "rollback_count": len(rollbacks),
                "rollback_audit_ids": rollback_audit_ids,
                "latest_rollback_audit_id": _clean_text(
                    latest_rollback.get("audit_id")
                ),
                "latest_rollback_status": latest_rollback_status,
                "latest_rollback_output_path": _clean_text(
                    latest_rollback.get("output_path")
                ),
                "latest_rollback_output_sha1": _clean_text(
                    latest_rollback.get("output_sha1")
                ),
                "restored_count": int(latest_rollback.get("restored_count") or 0),
                "restored_target_count": int(
                    latest_rollback.get("restored_target_count") or 0
                ),
                "rollback_available": latest_rollback_status != "rolled_back",
            }
        )

    orphan_rollback_records = [
        {
            "audit_id": _clean_text(record.get("audit_id")),
            "linked_apply_audit_id": _clean_text(record.get("linked_apply_audit_id")),
            "status": _clean_text(record.get("status")) or "blocked",
            "output_path": _clean_text(record.get("output_path")),
        }
        for record in rollback_records
        if _clean_text(record.get("linked_apply_audit_id")) not in seen_apply_ids
    ]
    manifest["transactions"] = transactions
    manifest["transaction_count"] = len(transactions)
    manifest["active_count"] = sum(
        1
        for transaction in transactions
        if _clean_text(transaction.get("transaction_status")) != "rolled_back"
    )
    manifest["rolled_back_count"] = sum(
        1
        for transaction in transactions
        if _clean_text(transaction.get("transaction_status")) == "rolled_back"
    )
    manifest["orphan_rollback_records"] = orphan_rollback_records
    manifest["orphan_rollback_count"] = len(orphan_rollback_records)
    manifest["expected_apply_audit_found"] = (
        bool(expected_id) and expected_id in seen_apply_ids
    )
    blockers: list[str] = []
    if expected_id and expected_id not in seen_apply_ids:
        blockers.append("expected_apply_audit_not_found")
    manifest["blockers"] = blockers
    manifest["status"] = (
        "blocked"
        if blockers
        else "tracked"
        if transactions
        else "orphaned"
        if orphan_rollback_records
        else "empty"
    )
    manifest["task_summary"] = (
        _question_figure_batch_apply_transaction_task_summary(manifest)
    )
    return manifest


def _question_figure_batch_apply_transaction_task_summary(
    manifest: Mapping[str, object],
) -> dict[str, object]:
    """Summarize transaction state into a lightweight task-center candidate."""

    transactions = [
        dict(transaction)
        for transaction in list(manifest.get("transactions") or [])
        if isinstance(transaction, Mapping)
    ]
    active_transactions = [
        transaction
        for transaction in transactions
        if _clean_text(transaction.get("transaction_status")) != "rolled_back"
    ]
    rolled_back_transactions = [
        transaction
        for transaction in transactions
        if _clean_text(transaction.get("transaction_status")) == "rolled_back"
    ]
    rollback_available_transactions = [
        transaction
        for transaction in active_transactions
        if bool(transaction.get("rollback_available"))
    ]
    latest_transaction = transactions[-1] if transactions else {}
    blockers = [
        _clean_text(blocker)
        for blocker in list(manifest.get("blockers") or [])
        if _clean_text(blocker)
    ]
    orphan_count = int(manifest.get("orphan_rollback_count") or 0)
    status = "empty"
    next_action = "review_history"
    if blockers:
        status = "blocked"
        next_action = "resolve_manifest_blocker"
    elif rollback_available_transactions:
        status = "active"
        next_action = "review_active_transaction"
    elif transactions:
        status = "completed"
        next_action = "review_transaction_history"
    elif orphan_count:
        status = "orphaned"
        next_action = "review_orphan_rollback"
    return {
        "kind": "question_figure_repair_batch_apply_transaction_task_summary",
        "status": status,
        "next_action": next_action,
        "transaction_count": len(transactions),
        "active_count": len(active_transactions),
        "rolled_back_count": len(rolled_back_transactions),
        "rollback_available_count": len(rollback_available_transactions),
        "orphan_rollback_count": orphan_count,
        "active_transaction_ids": [
            _clean_text(transaction.get("transaction_id"))
            for transaction in active_transactions
            if _clean_text(transaction.get("transaction_id"))
        ],
        "rolled_back_transaction_ids": [
            _clean_text(transaction.get("transaction_id"))
            for transaction in rolled_back_transactions
            if _clean_text(transaction.get("transaction_id"))
        ],
        "rollback_available_transaction_ids": [
            _clean_text(transaction.get("transaction_id"))
            for transaction in rollback_available_transactions
            if _clean_text(transaction.get("transaction_id"))
        ],
        "latest_transaction_id": _clean_text(
            latest_transaction.get("transaction_id")
        ),
        "latest_transaction_status": _clean_text(
            latest_transaction.get("transaction_status")
        ),
        "latest_apply_audit_id": _clean_text(
            latest_transaction.get("apply_audit_id")
        ),
        "latest_rollback_audit_id": _clean_text(
            latest_transaction.get("latest_rollback_audit_id")
        ),
        "artifact_path": _clean_text(manifest.get("artifact_path")),
        "report_path": _clean_text(manifest.get("report_path")),
        "blockers": blockers,
    }


def _write_question_figure_batch_apply_transaction_manifest(
    manifest: Mapping[str, object],
) -> dict[str, object]:
    """Persist a transaction manifest next to the batch-apply audit history."""

    payload = dict(manifest) if isinstance(manifest, Mapping) else {}
    payload.setdefault("schema_version", 1)
    payload.setdefault(
        "kind",
        "question_figure_repair_batch_apply_transaction_manifest",
    )
    payload["artifact_supported"] = False
    payload["artifact_written"] = False
    payload["artifact_path"] = ""
    payload["artifact_write_blockers"] = []
    payload["report_supported"] = False
    payload["report_written"] = False
    payload["report_path"] = ""
    payload["report_write_blockers"] = []
    audit_path = _clean_text(payload.get("audit_path"))
    if not audit_path:
        payload["artifact_write_blockers"] = ["audit_history_path_missing"]
        payload["report_write_blockers"] = ["audit_history_path_missing"]
        payload["task_summary"] = (
            _question_figure_batch_apply_transaction_task_summary(payload)
        )
        return payload
    artifact_path = Path(audit_path).parent / (
        "question_figure_batch_apply_transaction_manifest.json"
    )
    report_path = Path(audit_path).parent / (
        "question_figure_batch_apply_transaction_manifest.md"
    )
    artifact_payload = dict(payload)
    artifact_payload["artifact_supported"] = True
    artifact_payload["artifact_written"] = True
    artifact_payload["artifact_path"] = str(artifact_path)
    artifact_payload["artifact_write_blockers"] = []
    artifact_payload["report_supported"] = True
    artifact_payload["report_written"] = True
    artifact_payload["report_path"] = str(report_path)
    artifact_payload["report_write_blockers"] = []
    artifact_payload["task_summary"] = (
        _question_figure_batch_apply_transaction_task_summary(artifact_payload)
    )
    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            _question_figure_batch_apply_transaction_manifest_markdown(
                artifact_payload
            ),
            encoding="utf-8",
        )
    except OSError:
        artifact_payload["report_written"] = False
        artifact_payload["report_write_blockers"] = [
            "transaction_manifest_report_write_failed"
        ]
    try:
        artifact_path.write_text(
            json.dumps(
                artifact_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    except OSError:
        payload["artifact_supported"] = True
        payload["report_supported"] = artifact_payload.get("report_supported", True)
        payload["report_written"] = artifact_payload.get("report_written", False)
        payload["report_path"] = artifact_payload.get("report_path", str(report_path))
        payload["report_write_blockers"] = artifact_payload.get(
            "report_write_blockers", []
        )
        payload["artifact_write_blockers"] = [
            "transaction_manifest_artifact_write_failed"
        ]
        payload["task_summary"] = (
            _question_figure_batch_apply_transaction_task_summary(payload)
        )
        return payload
    return artifact_payload


def _question_figure_batch_apply_transaction_manifest_markdown(
    manifest: Mapping[str, object],
) -> str:
    lines = [
        "# Question Figure Batch Apply Transaction Manifest",
        "",
        f"- status: {_clean_text(manifest.get('status')) or 'empty'}",
        f"- transactions: {int(manifest.get('transaction_count') or 0)}",
        f"- active: {int(manifest.get('active_count') or 0)}",
        f"- rolled_back: {int(manifest.get('rolled_back_count') or 0)}",
        f"- orphan_rollback: {int(manifest.get('orphan_rollback_count') or 0)}",
        f"- audit_path: {_clean_text(manifest.get('audit_path'))}",
    ]
    expected_id = _clean_text(manifest.get("expected_apply_audit_id"))
    if expected_id:
        lines.append(f"- expected_apply_audit_id: {expected_id}")
        lines.append(
            "- expected_apply_audit_found: "
            + str(bool(manifest.get("expected_apply_audit_found"))).lower()
        )
    blockers = [
        _clean_text(blocker)
        for blocker in list(manifest.get("blockers") or [])
        if _clean_text(blocker)
    ]
    if blockers:
        lines.append(f"- blockers: {', '.join(blockers)}")

    task_summary = (
        dict(manifest.get("task_summary"))
        if isinstance(manifest.get("task_summary"), Mapping)
        else {}
    )
    if task_summary:
        active_ids = [
            _clean_text(item)
            for item in list(task_summary.get("active_transaction_ids") or [])
            if _clean_text(item)
        ]
        rolled_back_ids = [
            _clean_text(item)
            for item in list(task_summary.get("rolled_back_transaction_ids") or [])
            if _clean_text(item)
        ]
        rollback_available_ids = [
            _clean_text(item)
            for item in list(
                task_summary.get("rollback_available_transaction_ids") or []
            )
            if _clean_text(item)
        ]
        lines.extend(
            [
                "",
                "## Task Summary",
                f"- status: {_clean_text(task_summary.get('status')) or 'empty'}",
                f"- next_action: {_clean_text(task_summary.get('next_action'))}",
                f"- active: {int(task_summary.get('active_count') or 0)}",
                f"- rolled_back: {int(task_summary.get('rolled_back_count') or 0)}",
                (
                    "- rollback_available: "
                    + str(int(task_summary.get("rollback_available_count") or 0))
                ),
                (
                    "- orphan_rollback: "
                    + str(int(task_summary.get("orphan_rollback_count") or 0))
                ),
                f"- active_transaction_ids: {', '.join(active_ids)}",
                f"- rolled_back_transaction_ids: {', '.join(rolled_back_ids)}",
                (
                    "- rollback_available_transaction_ids: "
                    + ", ".join(rollback_available_ids)
                ),
                (
                    "- latest_transaction_id: "
                    + _clean_text(task_summary.get("latest_transaction_id"))
                ),
                (
                    "- latest_transaction_status: "
                    + _clean_text(task_summary.get("latest_transaction_status"))
                ),
                (
                    "- latest_apply_audit_id: "
                    + _clean_text(task_summary.get("latest_apply_audit_id"))
                ),
                (
                    "- latest_rollback_audit_id: "
                    + _clean_text(task_summary.get("latest_rollback_audit_id"))
                ),
            ]
        )

    transactions = [
        dict(transaction)
        for transaction in list(manifest.get("transactions") or [])
        if isinstance(transaction, Mapping)
    ]
    if transactions:
        lines.extend(["", "## Transactions"])
        for index, transaction in enumerate(transactions, start=1):
            title = _clean_text(transaction.get("transaction_id")) or f"transaction-{index}"
            rollback_ids = [
                _clean_text(item)
                for item in list(transaction.get("rollback_audit_ids") or [])
                if _clean_text(item)
            ]
            lines.extend(
                [
                    "",
                    f"### {index}. {title}",
                    f"- status: {_clean_text(transaction.get('transaction_status')) or 'unknown'}",
                    f"- apply_audit_id: {_clean_text(transaction.get('apply_audit_id'))}",
                    f"- apply_status: {_clean_text(transaction.get('apply_status')) or 'unknown'}",
                    f"- plan_id: {_clean_text(transaction.get('plan_id'))}",
                    (
                        "- execution_plan_fingerprint: "
                        + _clean_text(transaction.get("execution_plan_fingerprint"))
                    ),
                    f"- input_path: {_clean_text(transaction.get('input_path'))}",
                    (
                        "- applied_output_path: "
                        + _clean_text(transaction.get("applied_output_path"))
                    ),
                    (
                        "- applied_output_sha1: "
                        + _clean_text(transaction.get("applied_output_sha1"))
                    ),
                    f"- applied: {int(transaction.get('applied_count') or 0)}/{int(transaction.get('applied_target_count') or 0)}",
                    f"- rollback_count: {int(transaction.get('rollback_count') or 0)}",
                    f"- rollback_audit_ids: {', '.join(rollback_ids)}",
                    (
                        "- latest_rollback_audit_id: "
                        + _clean_text(transaction.get("latest_rollback_audit_id"))
                    ),
                    (
                        "- latest_rollback_status: "
                        + _clean_text(transaction.get("latest_rollback_status"))
                    ),
                    (
                        "- latest_rollback_output_path: "
                        + _clean_text(transaction.get("latest_rollback_output_path"))
                    ),
                    f"- restored: {int(transaction.get('restored_count') or 0)}/{int(transaction.get('restored_target_count') or 0)}",
                    (
                        "- rollback_available: "
                        + str(bool(transaction.get("rollback_available"))).lower()
                    ),
                ]
            )

    orphan_records = [
        dict(record)
        for record in list(manifest.get("orphan_rollback_records") or [])
        if isinstance(record, Mapping)
    ]
    if orphan_records:
        lines.extend(["", "## Orphan Rollback Records"])
        for index, record in enumerate(orphan_records, start=1):
            lines.extend(
                [
                    "",
                    f"### {index}. {_clean_text(record.get('audit_id')) or 'orphan'}",
                    (
                        "- linked_apply_audit_id: "
                        + _clean_text(record.get("linked_apply_audit_id"))
                    ),
                    f"- status: {_clean_text(record.get('status')) or 'blocked'}",
                    f"- output_path: {_clean_text(record.get('output_path'))}",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _rollback_question_figure_repair_batch_apply_from_audit(
    question_figure_repair_queue: Mapping[str, object],
    *,
    applied_docx_path: str | Path,
    rollback_docx_path: str | Path,
    audit_record: Mapping[str, object] | None = None,
    audit_dir: str | Path | None = None,
    confirmed: bool = False,
    confirmed_by: str = "manual",
    confirmation_note: str = "",
    expected_audit_id: str = "",
    expected_output_sha1: str = "",
) -> dict[str, object]:
    """Restore Word media from a batch-apply audit record into a new docx copy."""

    if not isinstance(question_figure_repair_queue, Mapping):
        return {
            "kind": "question_figure_repair_queue",
            "status": "empty",
            "queue_count": 0,
            "conflict_group_count": 0,
            "conflict_count": 0,
            "entries": [],
            "batch_apply_rollback_result": {
                "kind": "question_figure_repair_batch_apply_rollback_result",
                "action": "rollback_question_figure_repair_batch_apply_from_audit",
                "status": "blocked",
                "blockers": ["invalid_repair_queue"],
                "rollback_supported": False,
                "word_write_enabled": False,
            },
        }

    payload = copy.deepcopy(dict(question_figure_repair_queue))
    entries = [
        entry
        for entry in list(payload.get("entries") or [])
        if isinstance(entry, dict)
    ]
    payload["entries"] = entries
    execution_result = (
        dict(payload.get("batch_apply_execution_result"))
        if isinstance(payload.get("batch_apply_execution_result"), Mapping)
        else {}
    )
    source_audit = (
        dict(audit_record)
        if isinstance(audit_record, Mapping)
        else dict(execution_result.get("audit_record"))
        if isinstance(execution_result.get("audit_record"), Mapping)
        else {}
    )
    applied_text = _clean_text(applied_docx_path)
    rollback_text = _clean_text(rollback_docx_path)
    applied_path = Path(applied_text) if applied_text else Path()
    rollback_path = Path(rollback_text) if rollback_text else Path()
    audit_id = _clean_text(source_audit.get("audit_id"))
    audit_output_sha1 = _clean_text(source_audit.get("output_sha1"))
    current_applied_sha1 = _file_sha1(applied_path) if applied_text else ""

    result = {
        "kind": "question_figure_repair_batch_apply_rollback_result",
        "action": "rollback_question_figure_repair_batch_apply_from_audit",
        "status": "blocked",
        "linked_apply_audit_id": audit_id,
        "expected_audit_id": _clean_text(expected_audit_id),
        "audit_output_sha1": audit_output_sha1,
        "expected_output_sha1": _clean_text(expected_output_sha1),
        "current_applied_sha1": current_applied_sha1,
        "input_path": applied_text,
        "output_path": rollback_text,
        "confirmed": bool(confirmed),
        "confirmed_by": _clean_text(confirmed_by) or "manual",
        "confirmed_at": _utc_now_iso() if confirmed else "",
        "confirmation_note": _clean_text(confirmation_note),
        "planned_candidate_count": int(source_audit.get("planned_candidate_count") or 0),
        "applied_count": int(source_audit.get("applied_count") or 0),
        "restored_count": 0,
        "restored_target_count": 0,
        "entry_results": [],
        "blockers": [],
        "rollback_supported": False,
        "word_write_enabled": False,
        "audit_supported": False,
        "audit_written": False,
        "audit_path": "",
        "audit_record_id": "",
        "audit_record": {},
    }

    blockers: list[str] = []
    if not source_audit:
        blockers.append("batch_apply_audit_record_missing")
    if _clean_text(source_audit.get("status")) != "applied":
        blockers.append("batch_apply_audit_record_not_applied")
    if _clean_text(source_audit.get("action")) != (
        "question_figure_repair_batch_apply_word_media_write"
    ):
        blockers.append("unsupported_audit_record_action")
    if not bool(confirmed):
        blockers.append("manual_rollback_confirmation_required")
    expected_id = _clean_text(expected_audit_id)
    if not expected_id:
        blockers.append("expected_audit_id_required")
    elif expected_id != audit_id:
        blockers.append("audit_id_mismatch")
    expected_sha1 = _clean_text(expected_output_sha1)
    if not expected_sha1:
        blockers.append("expected_output_sha1_required")
    elif expected_sha1 != audit_output_sha1:
        blockers.append("expected_output_sha1_mismatch")
    if not applied_text:
        blockers.append("applied_docx_missing")
    elif not applied_path.is_file():
        blockers.append("applied_docx_missing")
    elif not zipfile.is_zipfile(applied_path):
        blockers.append("applied_docx_invalid")
    if audit_output_sha1 and current_applied_sha1 and audit_output_sha1 != current_applied_sha1:
        blockers.append("applied_docx_sha1_mismatch")
    if not rollback_text:
        blockers.append("rollback_docx_missing")
    elif applied_path.exists() and applied_path.resolve() == rollback_path.resolve():
        blockers.append("rollback_docx_must_differ_from_input")

    audit_entries = [
        dict(entry)
        for entry in list(source_audit.get("entry_results") or [])
        if isinstance(entry, Mapping)
    ]
    if not audit_entries:
        blockers.append("audit_entry_results_missing")

    media_names: set[str] = set()
    media_bytes: dict[str, bytes] = {}
    if applied_path.is_file() and zipfile.is_zipfile(applied_path):
        try:
            with zipfile.ZipFile(applied_path) as archive:
                for name in archive.namelist():
                    if name.startswith("word/media/") and not name.endswith("/"):
                        media_names.add(name)
                        media_bytes[name] = archive.read(name)
        except (OSError, zipfile.BadZipFile):
            blockers.append("applied_docx_media_scan_failed")

    entry_results: list[dict[str, object]] = []
    replacements: dict[str, bytes] = {}
    restored_targets: set[str] = set()
    for entry in audit_entries:
        queue_id = _clean_text(entry.get("queue_id"))
        media_path = _clean_text(entry.get("media_path"))
        original_path = _clean_text(entry.get("original_path"))
        expected_replacement_sha1 = _clean_text(entry.get("replacement_sha1"))
        original_sha1 = _clean_text(entry.get("original_sha1"))
        entry_blockers: list[str] = []
        current_media_sha1 = ""
        restored_sha1 = ""
        if not media_path:
            entry_blockers.append("audit_media_path_missing")
        elif media_path not in media_names:
            entry_blockers.append("audit_media_path_not_found_in_docx")
        else:
            current_media_sha1 = hashlib.sha1(media_bytes[media_path]).hexdigest()
            if (
                expected_replacement_sha1
                and current_media_sha1 != expected_replacement_sha1
            ):
                entry_blockers.append("current_media_sha1_mismatch")
        if not original_path:
            entry_blockers.append("original_path_missing")
        elif not Path(original_path).is_file():
            entry_blockers.append("original_file_missing")
        else:
            restored_sha1 = _file_sha1(Path(original_path))
            if original_sha1 and restored_sha1 != original_sha1:
                entry_blockers.append("original_file_sha1_mismatch")
        if media_path and media_path in restored_targets:
            entry_blockers.append("duplicate_rollback_media_target")
        entry_blockers = list(dict.fromkeys(entry_blockers))
        if not entry_blockers and media_path:
            replacements[media_path] = Path(original_path).read_bytes()
            restored_targets.add(media_path)
        entry_results.append(
            {
                "queue_id": queue_id,
                "status": "blocked" if entry_blockers else "ready",
                "media_path": media_path,
                "original_path": original_path,
                "replacement_source_path": _clean_text(
                    entry.get("replacement_source_path")
                ),
                "current_media_sha1": current_media_sha1,
                "expected_replacement_sha1": expected_replacement_sha1,
                "restored_sha1": restored_sha1,
                "question_index": _clean_text(entry.get("question_index")),
                "item_id": _clean_text(entry.get("item_id")),
                "blockers": entry_blockers,
            }
        )

    blocked_queue_ids = [
        _clean_text(entry.get("queue_id"))
        for entry in entry_results
        if _clean_text(entry.get("queue_id"))
        and _clean_text(entry.get("status")) == "blocked"
    ]
    if blocked_queue_ids:
        blockers.append("rollback_entry_guard_failed")
        result["blocked_queue_ids"] = blocked_queue_ids

    blockers = list(dict.fromkeys(blockers))
    result["entry_results"] = entry_results
    result["blockers"] = blockers
    if blockers:
        payload["batch_apply_rollback_result"] = result
        return payload

    try:
        rollback_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(applied_path) as source_archive:
            with zipfile.ZipFile(
                rollback_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as output_archive:
                for info in source_archive.infolist():
                    data = replacements.get(
                        info.filename,
                        source_archive.read(info.filename),
                    )
                    output_archive.writestr(info, data)
    except (OSError, zipfile.BadZipFile):
        result["blockers"] = ["rollback_docx_write_failed"]
        payload["batch_apply_rollback_result"] = result
        return payload

    restored_entries = [
        dict(entry, status="restored")
        for entry in entry_results
        if _clean_text(entry.get("status")) == "ready"
    ]
    result["status"] = "rolled_back"
    result["entry_results"] = restored_entries
    result["restored_count"] = len(restored_entries)
    result["restored_target_count"] = len(
        {
            _clean_text(entry.get("media_path"))
            for entry in restored_entries
            if _clean_text(entry.get("media_path"))
        }
    )
    result["output_sha1"] = _file_sha1(rollback_path)
    result["rollback_supported"] = True
    result["word_write_enabled"] = True
    rollback_audit_record = _question_figure_batch_apply_rollback_audit_record(
        result,
        apply_audit_record=source_audit,
    )
    audit_base_dir = _batch_apply_audit_output_dir(
        audit_dir,
        source_audit,
        fallback_dir=rollback_path.parent,
    )
    rollback_audit_record = _append_question_figure_batch_apply_audit_record(
        audit_base_dir,
        rollback_audit_record,
    )
    result["audit_supported"] = True
    result["audit_written"] = bool(
        _clean_text(rollback_audit_record.get("artifact_path"))
    )
    result["audit_path"] = _clean_text(rollback_audit_record.get("artifact_path"))
    result["audit_record_id"] = _clean_text(rollback_audit_record.get("audit_id"))
    result["audit_record"] = rollback_audit_record
    payload["batch_apply_rollback_result"] = result
    payload["batch_apply_transaction_manifest"] = (
        _write_question_figure_batch_apply_transaction_manifest(
            _question_figure_batch_apply_transaction_manifest_from_audit(
                result["audit_path"],
                expected_apply_audit_id=audit_id,
            )
        )
    )
    return payload


def _question_figure_batch_apply_rollback_audit_record(
    rollback_result: Mapping[str, object],
    *,
    apply_audit_record: Mapping[str, object],
) -> dict[str, object]:
    confirmed_at = _clean_text(rollback_result.get("confirmed_at")) or _utc_now_iso()
    linked_audit_id = _clean_text(rollback_result.get("linked_apply_audit_id"))
    output_path = _clean_text(rollback_result.get("output_path"))
    output_sha1 = _clean_text(rollback_result.get("output_sha1"))
    audit_id = (
        "question-figure-batch-rollback-audit:"
        + hashlib.sha1(
            "|".join([linked_audit_id, output_path, output_sha1, confirmed_at]).encode(
                "utf-8"
            )
        ).hexdigest()[:16]
    )
    entry_results = [
        dict(entry)
        for entry in list(rollback_result.get("entry_results") or [])
        if isinstance(entry, Mapping)
    ]
    return {
        "audit_id": audit_id,
        "kind": "question_figure_repair_batch_apply_audit_record",
        "action": "question_figure_repair_batch_apply_word_media_rollback",
        "status": _clean_text(rollback_result.get("status")) or "blocked",
        "linked_apply_audit_id": linked_audit_id,
        "plan_id": _clean_text(apply_audit_record.get("plan_id")),
        "execution_plan_fingerprint": _clean_text(
            apply_audit_record.get("execution_plan_fingerprint")
        ),
        "confirmed": bool(rollback_result.get("confirmed")),
        "confirmed_by": _clean_text(rollback_result.get("confirmed_by")) or "manual",
        "confirmed_at": confirmed_at,
        "confirmation_note": _clean_text(rollback_result.get("confirmation_note")),
        "input_path": _clean_text(rollback_result.get("input_path")),
        "output_path": output_path,
        "output_sha1": output_sha1,
        "applied_docx_sha1": _clean_text(rollback_result.get("current_applied_sha1")),
        "restored_count": int(rollback_result.get("restored_count") or 0),
        "restored_target_count": int(
            rollback_result.get("restored_target_count") or 0
        ),
        "entry_results": entry_results,
    }


def _batch_apply_audit_output_dir(
    audit_dir: str | Path | None,
    audit_record: Mapping[str, object],
    *,
    fallback_dir: Path,
) -> Path | None:
    if audit_dir is not None and _clean_text(audit_dir):
        return Path(_clean_text(audit_dir))
    artifact_path = _clean_text(audit_record.get("artifact_path"))
    if artifact_path:
        return Path(artifact_path).parent
    return fallback_dir


def _question_figure_repair_target_payload(
    repair_target_key: str,
) -> dict[str, object]:
    text = _clean_text(repair_target_key)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _file_sha1(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            digest = hashlib.sha1()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def _resolve_question_figure_repair_queue_conflict(
    question_figure_repair_queue: Mapping[str, object],
    selected_queue_id: str,
    *,
    confirmed: bool = False,
    resolved_by: str = "manual",
    resolution_note: str = "",
) -> dict[str, object]:
    """Return a queue copy with one conflict candidate selected for application."""

    if not isinstance(question_figure_repair_queue, Mapping):
        return {
            "kind": "question_figure_repair_queue",
            "status": "empty",
            "queue_count": 0,
            "conflict_group_count": 0,
            "conflict_count": 0,
            "entries": [],
            "resolution_status": "not_resolved",
            "resolution_blockers": ["invalid_repair_queue"],
        }
    payload = copy.deepcopy(dict(question_figure_repair_queue))
    entries = [
        entry
        for entry in list(payload.get("entries") or [])
        if isinstance(entry, dict)
    ]
    payload["entries"] = entries
    if not confirmed:
        payload["resolution_status"] = "not_confirmed"
        return payload

    selected_id = _clean_text(selected_queue_id)
    if not selected_id:
        payload["resolution_status"] = "not_resolved"
        payload["resolution_blockers"] = ["selected_queue_id_missing"]
        return payload
    selected_entry = next(
        (
            entry
            for entry in entries
            if _clean_text(entry.get("queue_id")) == selected_id
        ),
        None,
    )
    if selected_entry is None:
        payload["resolution_status"] = "not_resolved"
        payload["resolution_blockers"] = ["selected_queue_id_not_found"]
        return payload
    if _clean_text(selected_entry.get("confirmation_status")) != "conflict":
        payload["resolution_status"] = "not_resolved"
        payload["resolution_blockers"] = ["selected_candidate_not_conflict"]
        return payload
    conflict_group_id = _clean_text(selected_entry.get("conflict_group_id"))
    if not conflict_group_id:
        payload["resolution_status"] = "not_resolved"
        payload["resolution_blockers"] = ["conflict_group_id_missing"]
        return payload
    conflict_group = [
        entry
        for entry in entries
        if _clean_text(entry.get("conflict_group_id")) == conflict_group_id
        and _clean_text(entry.get("confirmation_status")) == "conflict"
    ]
    if len(conflict_group) < 2:
        payload["resolution_status"] = "not_resolved"
        payload["resolution_blockers"] = ["conflict_group_not_ambiguous"]
        return payload

    group_queue_ids = [
        _clean_text(entry.get("queue_id"))
        for entry in conflict_group
        if _clean_text(entry.get("queue_id"))
    ]
    rejected_queue_ids: list[str] = []
    for entry in conflict_group:
        queue_id = _clean_text(entry.get("queue_id"))
        blockers = [
            blocker
            for blocker in (
                _clean_text(value) for value in list(entry.get("apply_blockers") or [])
            )
            if blocker and blocker != "candidate_conflict_same_repair_target"
        ]
        entry["conflict_resolution_action"] = (
            "manual_select_question_figure_replacement"
        )
        entry["conflict_selected_queue_id"] = selected_id
        entry["conflict_resolution_group_id"] = conflict_group_id
        entry["conflict_resolution_candidate_queue_ids"] = group_queue_ids
        entry["conflict_resolution_by"] = _clean_text(resolved_by) or "manual"
        entry["conflict_resolution_note"] = _clean_text(resolution_note)
        if queue_id == selected_id:
            entry["status"] = "candidate"
            entry["confirmation_action"] = "confirm_question_figure_replacement"
            entry["confirmation_status"] = "ready"
            entry["confirmation_apply_supported"] = True
            entry["conflict_resolution_status"] = "selected"
            entry["apply_blockers"] = blockers
        else:
            rejected_queue_ids.append(queue_id)
            if "candidate_rejected_by_conflict_resolution" not in blockers:
                blockers.append("candidate_rejected_by_conflict_resolution")
            entry["status"] = "rejected"
            entry["confirmation_action"] = "review_question_figure_replacement"
            entry["confirmation_status"] = "rejected"
            entry["confirmation_apply_supported"] = False
            entry["conflict_resolution_status"] = "rejected"
            entry["apply_blockers"] = blockers

    resolution_id_source = "|".join(
        [conflict_group_id, selected_id, *group_queue_ids]
    )
    resolution_id = (
        "repair-conflict-resolution:"
        f"{hashlib.sha1(resolution_id_source.encode('utf-8')).hexdigest()[:12]}"
    )
    resolution_record = {
        "resolution_id": resolution_id,
        "action": "resolve_question_figure_repair_conflict",
        "status": "resolved",
        "conflict_group_id": conflict_group_id,
        "selected_queue_id": selected_id,
        "candidate_queue_ids": group_queue_ids,
        "rejected_queue_ids": rejected_queue_ids,
        "resolved_by": _clean_text(resolved_by) or "manual",
        "resolution_note": _clean_text(resolution_note),
    }
    records = [
        record
        for record in list(payload.get("resolution_records") or [])
        if isinstance(record, Mapping)
    ]
    records.append(resolution_record)
    payload["resolution_records"] = records
    payload["resolution_status"] = "resolved"
    payload["resolved_conflict_group_count"] = int(
        payload.get("resolved_conflict_group_count") or 0
    ) + 1
    payload["resolved_conflict_count"] = int(
        payload.get("resolved_conflict_count") or 0
    ) + len(conflict_group)
    _refresh_question_figure_repair_queue_status(payload)
    return payload


def _refresh_question_figure_repair_queue_status(payload: dict[str, object]) -> None:
    entries = [
        entry for entry in list(payload.get("entries") or []) if isinstance(entry, dict)
    ]
    unresolved_conflict_group_ids = {
        _clean_text(entry.get("conflict_group_id"))
        for entry in entries
        if _clean_text(entry.get("confirmation_status")) == "conflict"
        and _clean_text(entry.get("conflict_group_id"))
    }
    conflict_count = sum(
        1
        for entry in entries
        if _clean_text(entry.get("confirmation_status")) == "conflict"
    )
    payload["queue_count"] = len(entries)
    payload["conflict_group_count"] = len(unresolved_conflict_group_ids)
    payload["conflict_count"] = conflict_count
    if conflict_count:
        payload["status"] = "conflict"
    else:
        payload["status"] = "queued" if entries else "empty"
    payload["batch_confirmation_plan"] = (
        _question_figure_repair_batch_confirmation_plan(entries)
    )


def _question_figure_repair_apply_plan(
    item_payload: Mapping[str, str],
    *,
    repair_target_type: str,
    repair_target_key: str,
) -> dict[str, object]:
    blockers: list[str] = []
    reference = _clean_text(item_payload.get("reference"))
    replacement_source_path = ""
    replacement_source_kind = ""
    if not repair_target_type or repair_target_type != "question_figure_item":
        blockers.append("unsupported_repair_target")
    if not repair_target_key:
        blockers.append("repair_target_missing")
    if not reference:
        blockers.append("comparison_reference_missing")
    elif _is_local_file(reference):
        replacement_source_path = str(Path(reference))
        replacement_source_kind = "local_file"
    else:
        blockers.append("comparison_reference_not_local_file")

    return {
        "confirmation_action": "confirm_question_figure_replacement",
        "confirmation_apply_supported": not blockers,
        "confirmation_status": "ready" if not blockers else "blocked",
        "replacement_source_path": replacement_source_path,
        "replacement_source_kind": replacement_source_kind,
        "apply_blockers": blockers,
    }


def _is_local_file(value: str) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "asset://", "lark://")):
        return False
    try:
        return Path(text).is_file()
    except OSError:
        return False


def _repair_queue_token(value) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", _clean_text(value))
    return token.strip("_") or "item"


def _comparison_matrix_question_index(comparison_item: Mapping[str, object]) -> str:
    metadata = comparison_item.get("metadata")
    metadata_question = ""
    if isinstance(metadata, Mapping):
        metadata_question = _clean_text(metadata.get("question_index"))
    return (
        _clean_text(comparison_item.get("question_index"))
        or _clean_text(comparison_item.get("question_target"))
        or metadata_question
        or "-"
    )


def _comparison_matrix_item_payload(
    comparison_item: Mapping[str, object],
    *,
    repair_target_type: str,
    repair_target_key: str,
) -> dict[str, str]:
    metadata = comparison_item.get("metadata")
    metadata_map = metadata if isinstance(metadata, Mapping) else {}
    return {
        "item_id": _clean_text(comparison_item.get("item_id")),
        "label": _clean_text(comparison_item.get("label")),
        "asset_id": _clean_text(comparison_item.get("asset_id")),
        "path": _clean_text(comparison_item.get("path")),
        "cache_path": _clean_text(comparison_item.get("cache_path")),
        "issue_kind": _clean_text(comparison_item.get("comparison_issue_kind")),
        "issue_type": _clean_text(comparison_item.get("comparison_issue_type")),
        "reference": _clean_text(comparison_item.get("comparison_issue_reference")),
        "display_name": _clean_text(comparison_item.get("comparison_issue_display_name")),
        "marked_at": _clean_text(comparison_item.get("comparison_issue_marked_at")),
        "summary": _clean_text(comparison_item.get("comparison_issue_summary")),
        "region_type": _clean_text(
            comparison_item.get("comparison_issue_region_type")
            or metadata_map.get("comparison_issue_region_type")
        ),
        "region_summary": _clean_text(
            comparison_item.get("comparison_issue_region_summary")
            or metadata_map.get("comparison_issue_region_summary")
        ),
        "region_json": _clean_text(
            comparison_item.get("comparison_issue_region_json")
            or metadata_map.get("comparison_issue_region_json")
        ),
        "repair_target_type": repair_target_type,
        "repair_target_key": repair_target_key,
    }


def _comparison_question_sort_key(value) -> tuple[int, int | str]:
    text = _clean_text(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text)
