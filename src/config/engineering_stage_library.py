# -*- coding: utf-8 -*-
"""工程阶段大纲库：读取 config_library/engineering_stages/*.json。

工程版工作模式用它按阶段提供行业章节大纲、要素提问与自检清单，
供 AI 起草（分阶段/分章生成）与 UI 阶段切换读取。纯读取，不落盘。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STAGES_ROOT = _PROJECT_ROOT / "config_library" / "engineering_stages"


@dataclass(frozen=True, slots=True)
class EngineeringSection:
    title: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class EngineeringDocKind:
    kind: str
    title_pattern: str
    typical: bool = False
    sections: tuple[EngineeringSection, ...] = ()
    checklist: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EngineeringStage:
    stage_id: str
    label: str
    order: int
    summary: str
    question_set: tuple[str, ...]
    documents: tuple[EngineeringDocKind, ...]

    @property
    def doc_kinds(self) -> tuple[str, ...]:
        return tuple(doc.kind for doc in self.documents)

    def typical_doc_kind(self) -> EngineeringDocKind | None:
        return next((d for d in self.documents if d.typical), None)


def _read_json(name: str) -> dict:
    path = _STAGES_ROOT / name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"engineering stage resource unreadable: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"engineering stage resource must be an object: {path}")
    return payload


def list_engineering_stages() -> tuple[EngineeringStage, ...]:
    index = _read_json("stages_index.json")
    stages: list[EngineeringStage] = []
    for entry in index.get("stages", []):
        stage_id = str(entry.get("stage_id", "")).strip()
        if not stage_id:
            continue
        data = _read_json(f"{stage_id}.json")
        documents = tuple(
            EngineeringDocKind(
                kind=str(doc.get("kind", "")).strip() or "未命名文档",
                title_pattern=str(doc.get("title_pattern", "")).strip(),
                typical=bool(doc.get("typical", False)),
                sections=tuple(
                    EngineeringSection(
                        title=str(sec.get("title", "")).strip(),
                        note=str(sec.get("note", "")).strip(),
                    )
                    for sec in doc.get("sections", [])
                ),
                checklist=tuple(str(item) for item in doc.get("checklist", [])),
            )
            for doc in data.get("documents", [])
        )
        stages.append(
            EngineeringStage(
                stage_id=stage_id,
                label=str(data.get("label") or entry.get("label") or stage_id),
                order=int(entry.get("order") or data.get("order") or 0),
                summary=str(data.get("summary", "")).strip(),
                question_set=tuple(str(q) for q in data.get("question_set", [])),
                documents=documents,
            )
        )
    return tuple(sorted(stages, key=lambda s: s.order))


def get_engineering_stage(stage_id: str) -> EngineeringStage | None:
    normalized = str(stage_id or "").strip().casefold()
    return next(
        (s for s in list_engineering_stages() if s.stage_id.casefold() == normalized),
        None,
    )


__all__ = [
    "EngineeringDocKind",
    "EngineeringSection",
    "EngineeringStage",
    "get_engineering_stage",
    "list_engineering_stages",
]
