"""Pure question-figure repair projections used by production execution."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path


def _clean_text(value) -> str:
    return str(value or "").strip()


def _clean_list(values) -> list[str]:
    return [_clean_text(value) for value in list(values or []) if _clean_text(value)]


def build_batch_question_figure_comparison_matrix(
    batch_issue_items,
) -> dict[str, object]:
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

    profile_rows = _comparison_matrix_profile_rows(profiles)
    question_rows = _comparison_matrix_question_rows(questions)

    return {
        "kind": "question_figure_comparison_matrix",
        "total_issue_count": total_issue_count,
        "profile_count": len(profile_rows),
        "question_count": len(question_rows),
        "profiles": profile_rows,
        "questions": question_rows,
    }


def _comparison_matrix_profile_rows(
    profiles: Mapping[str, dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for profile in sorted(
        profiles.values(),
        key=lambda item: (
            _clean_text(item.get("profile_name")),
            _clean_text(item.get("profile_id")),
        ),
    ):
        question_map = profile.get("_questions")
        questions = (
            question_map.values() if isinstance(question_map, dict) else ()
        )
        rows.append(
            {
                "profile_id": _clean_text(profile.get("profile_id")),
                "profile_name": _clean_text(profile.get("profile_name")),
                "issue_count": int(profile.get("issue_count") or 0),
                "questions": sorted(
                    [
                        {
                            "question_index": _clean_text(
                                question.get("question_index")
                            ),
                            "issue_count": int(question.get("issue_count") or 0),
                            "items": list(question.get("items") or []),
                        }
                        for question in questions
                        if isinstance(question, dict)
                    ],
                    key=lambda item: _comparison_question_sort_key(
                        item.get("question_index")
                    ),
                ),
            }
        )
    return rows


def _comparison_matrix_question_rows(
    questions: Mapping[str, dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for question in sorted(
        questions.values(),
        key=lambda item: _comparison_question_sort_key(
            item.get("question_index")
        ),
    ):
        profile_map = question.get("_profiles")
        profiles = profile_map.values() if isinstance(profile_map, dict) else ()
        rows.append(
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
                        for profile in profiles
                        if isinstance(profile, dict)
                    ],
                    key=lambda item: (
                        _clean_text(item.get("profile_name")),
                        _clean_text(item.get("profile_id")),
                    ),
                ),
            }
        )
    return rows


def build_batch_question_figure_repair_queue(
    batch_issue_items,
) -> dict[str, object]:
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


def _append_question_figure_confirmation_reason(
    reasons: list[str],
    reason: str,
) -> None:
    normalized = _clean_text(reason)
    if normalized and normalized not in reasons:
        reasons.append(normalized)


def _question_figure_confirmation_entry(
    entry: Mapping[str, object],
    *,
    index: int,
) -> dict[str, object]:
    queue_id = _clean_text(entry.get("queue_id")) or f"entry:{index}"
    repair_target_type = _clean_text(entry.get("repair_target_type"))
    repair_target_key = _clean_text(entry.get("repair_target_key"))
    confirmation_status = _clean_text(entry.get("confirmation_status"))
    replacement_source_kind = _clean_text(entry.get("replacement_source_kind"))
    replacement_source_path = _clean_text(entry.get("replacement_source_path"))
    reasons = _clean_list(entry.get("apply_blockers"))

    if repair_target_type != "question_figure_item":
        _append_question_figure_confirmation_reason(
            reasons,
            "unsupported_repair_target",
        )
    if not repair_target_key:
        _append_question_figure_confirmation_reason(
            reasons,
            "repair_target_missing",
        )
    if confirmation_status != "ready":
        _append_question_figure_confirmation_reason(
            reasons,
            f"confirmation_status_{confirmation_status or 'missing'}",
        )
    if not bool(entry.get("confirmation_apply_supported")):
        _append_question_figure_confirmation_reason(
            reasons,
            "confirmation_apply_not_supported",
        )
    if replacement_source_kind != "local_file":
        _append_question_figure_confirmation_reason(
            reasons,
            "replacement_source_not_local_file",
        )
    if not replacement_source_path:
        _append_question_figure_confirmation_reason(
            reasons,
            "replacement_source_missing",
        )
    elif not _is_local_file(replacement_source_path):
        _append_question_figure_confirmation_reason(
            reasons,
            "replacement_source_file_missing",
        )

    return {
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


def _partition_duplicate_question_figure_targets(
    eligible_entries: list[dict[str, object]],
    ready_by_target: Mapping[str, list[dict[str, object]]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    duplicate_target_groups: list[dict[str, object]] = []
    duplicate_queue_ids: set[str] = set()
    for target_key, group in ready_by_target.items():
        if len(group) <= 1:
            continue
        queue_ids = _question_figure_confirmation_queue_ids(group)
        duplicate_target_groups.append(
            {
                "repair_target_key": target_key,
                "queue_ids": queue_ids,
            }
        )
        duplicate_queue_ids.update(queue_ids)

    retained_entries: list[dict[str, object]] = []
    duplicate_entries: list[dict[str, object]] = []
    for entry in eligible_entries:
        queue_id = _clean_text(entry.get("queue_id"))
        if queue_id not in duplicate_queue_ids:
            retained_entries.append(entry)
            continue
        duplicate_entry = dict(entry)
        blockers = _clean_list(duplicate_entry.get("blockers"))
        _append_question_figure_confirmation_reason(
            blockers,
            "duplicate_ready_candidate_same_repair_target",
        )
        duplicate_entry["blockers"] = blockers
        duplicate_entries.append(duplicate_entry)
    return retained_entries, duplicate_entries, duplicate_target_groups


def _question_figure_confirmation_queue_ids(
    entries: list[dict[str, object]],
) -> list[str]:
    return [
        _clean_text(entry.get("queue_id"))
        for entry in entries
        if _clean_text(entry.get("queue_id"))
    ]


def _question_figure_conflict_queue_ids(
    entries: list[Mapping[str, object]],
) -> list[str]:
    return [
        _clean_text(entry.get("queue_id"))
        for entry in entries
        if _clean_text(entry.get("confirmation_status")) == "conflict"
        and _clean_text(entry.get("queue_id"))
    ]


def _question_figure_confirmation_target_count(
    entries: list[Mapping[str, object]],
) -> int:
    return len(
        {
            _clean_text(entry.get("repair_target_key"))
            for entry in entries
            if _clean_text(entry.get("repair_target_key"))
        }
    )


def _question_figure_confirmation_plan_status(
    *,
    entry_count: int,
    eligible_count: int,
    blocked_count: int,
) -> str:
    if not entry_count:
        return "empty"
    if eligible_count and blocked_count:
        return "partial"
    if eligible_count:
        return "ready"
    return "blocked"


def _question_figure_repair_batch_confirmation_plan(
    entries: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> dict[str, object]:
    clean_entries = [
        entry for entry in list(entries or []) if isinstance(entry, Mapping)
    ]
    eligible_entries: list[dict[str, object]] = []
    blocked_entries: list[dict[str, object]] = []
    ready_by_target: dict[str, list[dict[str, object]]] = {}

    for index, entry in enumerate(clean_entries, start=1):
        plan_entry = _question_figure_confirmation_entry(entry, index=index)
        if plan_entry["blockers"]:
            blocked_entries.append(plan_entry)
            continue
        eligible_entries.append(plan_entry)
        repair_target_key = _clean_text(plan_entry.get("repair_target_key"))
        ready_by_target.setdefault(repair_target_key, []).append(plan_entry)

    (
        eligible_entries,
        duplicate_entries,
        duplicate_target_groups,
    ) = _partition_duplicate_question_figure_targets(
        eligible_entries,
        ready_by_target,
    )
    blocked_entries.extend(duplicate_entries)
    conflict_queue_ids = _question_figure_conflict_queue_ids(clean_entries)
    eligible_count = len(eligible_entries)
    blocked_count = len(blocked_entries)
    status = _question_figure_confirmation_plan_status(
        entry_count=len(clean_entries),
        eligible_count=eligible_count,
        blocked_count=blocked_count,
    )

    plan = {
        "kind": "question_figure_repair_batch_confirmation_plan",
        "status": status,
        "action": "review_question_figure_repair_batch_confirmation_plan",
        "requires_user_confirmation": bool(clean_entries),
        "auto_apply_supported": False,
        "batch_apply_supported": False,
        "batch_confirmation_supported": eligible_count > 0,
        "entry_count": len(clean_entries),
        "target_count": _question_figure_confirmation_target_count(clean_entries),
        "eligible_count": eligible_count,
        "blocked_count": blocked_count,
        "conflict_count": len(conflict_queue_ids),
        "duplicate_target_count": len(duplicate_target_groups),
        "eligible_queue_ids": _question_figure_confirmation_queue_ids(
            eligible_entries
        ),
        "blocked_queue_ids": _question_figure_confirmation_queue_ids(
            blocked_entries
        ),
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


__all__ = [
    "build_batch_question_figure_comparison_matrix",
    "build_batch_question_figure_repair_queue",
]
