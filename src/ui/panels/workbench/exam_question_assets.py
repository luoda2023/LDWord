from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence

from src.config.material_context import MaterialExecutionContext
from src.config.scene import SceneWorkspace

from .material_preflight import (
    asset_metadata,
    asset_render_path,
    looks_like_remote_asset_path,
    material_asset_items,
    profile_material_schema_ids,
)


def material_context_with_exam_question_assets(
    scene: SceneWorkspace,
    material_context: MaterialExecutionContext,
) -> MaterialExecutionContext:
    runtime_material = material_context.clone()
    profile = getattr(scene, "input_source_profile", None)
    schema_ids = profile_material_schema_ids(profile)
    if "exam_items_v1" not in set(schema_ids):
        return runtime_material

    figure_items = material_asset_items(runtime_material, "question_figure")
    if not figure_items:
        return runtime_material

    entity_data = dict(runtime_material.entity_data)
    for source_key in (
        "exam_items",
        "exam_paper",
        "paper",
        "paper_json",
        "question_schema",
        "questions",
        "sections",
    ):
        payload = _coerce_exam_material_payload(entity_data.get(source_key))
        if payload is None:
            continue
        if inject_question_figure_assets(payload, figure_items):
            entity_data[source_key] = json.dumps(payload, ensure_ascii=False)
            runtime_material.entity_data = entity_data
            return runtime_material
    return runtime_material


def inject_question_figure_path(
    payload: object,
    figure_path: str,
    figure_metadata: Mapping[str, object] | None = None,
) -> bool:
    return inject_question_figure_assets(
        payload,
        [
            {
                "role": "question_figure",
                "path": figure_path,
                "metadata": dict(figure_metadata or {}),
            }
        ],
    )


def inject_question_figure_assets(payload: object, figure_items: Sequence[object]) -> bool:
    questions = list(_iter_exam_question_payloads(payload))
    if not questions:
        return False

    changed = False
    untargeted: list[object] = []
    material_owned_questions: set[int] = set()
    sorted_items = sorted(
        enumerate(figure_items),
        key=lambda pair: _question_figure_asset_sort_key(pair[1], pair[0]),
    )
    for _source_index, item in sorted_items:
        path = asset_render_path(item)
        if not path or looks_like_remote_asset_path(path):
            continue
        target = _target_question_for_asset(item, questions)
        if target is None:
            untargeted.append(item)
            continue
        target_identity = id(target)
        if _question_has_figure_path(target) and target_identity not in material_owned_questions:
            continue
        if _append_question_figure_payload(target, _question_figure_payload_from_asset(item)):
            material_owned_questions.add(target_identity)
            changed = True

    for item in untargeted:
        for question in questions:
            question_identity = id(question)
            if (
                _question_has_figure_path(question)
                and question_identity not in material_owned_questions
            ):
                continue
            if _append_question_figure_payload(question, _question_figure_payload_from_asset(item)):
                material_owned_questions.add(question_identity)
                changed = True
            break
    return changed


def _coerce_exam_material_payload(value: object) -> object | None:
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return copy.deepcopy(list(value))
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, Mapping):
            return dict(parsed)
        if isinstance(parsed, list):
            return parsed
    return None


def _append_question_figure_payload(
    question: dict,
    figure_payload: Mapping[str, object],
) -> bool:
    payload = dict(figure_payload)
    existing = question.get("figure") or question.get("image")
    if existing in (None, ""):
        question["figure"] = payload
        question.pop("image", None)
        return True
    figures = list(existing) if isinstance(existing, list) else [existing]
    normalized_payload = _question_figure_payload_identity(payload)
    for figure in figures:
        if (
            isinstance(figure, Mapping)
            and _question_figure_payload_identity(figure) == normalized_payload
        ):
            return False
    figures.append(payload)
    question["figure"] = figures
    question.pop("image", None)
    return True


def _question_figure_payload_identity(payload: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(payload.get("asset_id") or payload.get("assetId") or "").strip(),
        str(payload.get("path") or payload.get("asset_path") or "").strip(),
        str(payload.get("source") or "").strip(),
    )


def _question_figure_asset_sort_key(item: object, source_index: int) -> tuple[int, str, str, int]:
    metadata = asset_metadata(item)
    order = _asset_figure_order(metadata)
    return (
        order if order is not None else 999_999,
        _asset_question_key(metadata),
        str(_asset_question_index(metadata) if _asset_question_index(metadata) is not None else ""),
        source_index,
    )


def _target_question_for_asset(item: object, questions: Sequence[dict]) -> dict | None:
    metadata = asset_metadata(item)
    target_key = _asset_question_key(metadata)
    if target_key:
        normalized_key = _normalize_question_identity(target_key)
        for index, question in enumerate(questions, start=1):
            identities = _question_identity_values(question, index)
            if normalized_key in {_normalize_question_identity(value) for value in identities}:
                return question

    target_index = _asset_question_index(metadata)
    if target_index is not None and 0 <= target_index < len(questions):
        return questions[target_index]
    return None


def _question_figure_payload_from_asset(item: object) -> dict[str, str]:
    metadata = asset_metadata(item)
    path = asset_render_path(item)
    role = str(
        getattr(item, "role", "")
        if not isinstance(item, Mapping)
        else item.get("role") or ""
    ).strip()
    item_id = str(
        getattr(item, "item_id", "")
        if not isinstance(item, Mapping)
        else item.get("item_id") or ""
    ).strip()
    asset_id = (
        str(metadata.get("asset_id") or metadata.get("assetId") or "").strip()
        or item_id
        or _normalize_exam_key(role)
        or "question_figure"
    )
    figure_payload = {
        "source": str(metadata.get("source") or "asset").strip() or "asset",
        "path": path,
        "asset_id": asset_id,
    }
    alt_text = _asset_alt_text(metadata)
    if alt_text:
        figure_payload["alt"] = alt_text
    title = _asset_title_text(metadata)
    if title:
        figure_payload["title"] = title
    caption = str(metadata.get("caption") or "").strip()
    if caption:
        figure_payload["caption"] = caption
    figure_order = _asset_figure_order(metadata)
    if figure_order is not None:
        figure_payload["figure_order"] = str(figure_order)
    return figure_payload


def _asset_question_key(metadata: Mapping[str, object]) -> str:
    for key in (
        "question_id",
        "questionId",
        "question_key",
        "questionKey",
        "question_no",
        "questionNo",
        "question_number",
        "questionNumber",
        "number",
        "no",
        "id",
    ):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _asset_question_index(metadata: Mapping[str, object]) -> int | None:
    for key in ("question_index", "questionIndex", "index", "order", "position"):
        value = str(metadata.get(key) or "").strip()
        if not value:
            continue
        try:
            number = int(value)
        except ValueError:
            continue
        return number - 1
    return None


def _asset_figure_order(metadata: Mapping[str, object]) -> int | None:
    for key in (
        "figure_order",
        "figureOrder",
        "figure_index",
        "figureIndex",
        "image_order",
        "imageOrder",
        "asset_order",
        "assetOrder",
        "order_within_question",
        "orderWithinQuestion",
        "sort_order",
        "sortOrder",
    ):
        value = str(metadata.get(key) or "").strip()
        if not value:
            continue
        try:
            number = int(value)
        except ValueError:
            continue
        return number
    return None


def _question_identity_values(question: Mapping[str, object], index: int) -> list[str]:
    values = [str(index)]
    for key in (
        "id",
        "question_id",
        "questionId",
        "question_key",
        "questionKey",
        "question_no",
        "questionNo",
        "question_number",
        "questionNumber",
        "number",
        "no",
    ):
        value = str(question.get(key) or "").strip()
        if value:
            values.append(value)
    return values


def _normalize_question_identity(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _asset_title_text(metadata: Mapping[str, object] | None) -> str:
    if not isinstance(metadata, Mapping):
        return ""
    for key in ("title", "caption", "asset_id", "assetId", "source"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _asset_alt_text(metadata: Mapping[str, object] | None) -> str:
    if not isinstance(metadata, Mapping):
        return ""
    for key in ("alt", "alt_text", "altText", "description", "caption"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _iter_exam_question_payloads(payload: object):
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
        return
    if not isinstance(payload, dict):
        return

    for key in ("questions", "items"):
        questions = payload.get(key)
        if isinstance(questions, list):
            for question in questions:
                if isinstance(question, dict):
                    yield question
            return

    sections = payload.get("sections") or payload.get("parts")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            for key in ("questions", "items"):
                questions = section.get(key)
                if not isinstance(questions, list):
                    continue
                for question in questions:
                    if isinstance(question, dict):
                        yield question


def _question_has_figure_path(question: Mapping[str, object]) -> bool:
    figure = question.get("figure") or question.get("image")
    if figure in (None, ""):
        return False
    figures = figure if isinstance(figure, list) else [figure]
    for item in figures:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("path") or item.get("asset_path") or item.get("asset_id") or "").strip():
            return True
    return False


def _normalize_exam_key(value) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


__all__ = [
    "inject_question_figure_assets",
    "inject_question_figure_path",
    "material_context_with_exam_question_assets",
]
