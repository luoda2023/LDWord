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


def resolve_engineering_outline(
    intent: str,
    *,
    stage_hint: str = "",
    doc_kind_hint: str = "",
) -> tuple[str, str, tuple[str, ...]]:
    """Match a user intent to a stage/doc kind and its outline section titles.

    Returns (stage_id, doc_kind, section_titles).  Empty titles mean no match.
    """
    text = str(intent or "").strip()
    if not text:
        return ("", "", ())
    normalized = text.casefold()
    best_stage: EngineeringStage | None = None
    best_doc: EngineeringDocKind | None = None
    best_rank = -1
    hint = str(doc_kind_hint or "").strip().casefold()
    stage_h = str(stage_hint or "").strip().casefold()
    for stage in list_engineering_stages():
        if stage_h and stage.stage_id.casefold() == stage_h:
            if best_stage is None or stage.order < (best_stage.order or 99):
                best_stage = stage
        for doc in stage.documents:
            rank = 0
            kind = doc.kind.casefold()
            if hint and hint == kind:
                rank += 4
            if hint and hint in kind:
                rank += 2
            for token in (kind,):
                if token and token in normalized:
                    rank += 3
            # 常见别名权重
            for alias in _DOC_KIND_ALIASES.get(doc.kind, ()):
                if alias and alias.casefold() in normalized:
                    rank += 3
            if rank > best_rank:
                best_rank = rank
                best_stage = stage
                best_doc = doc
    if best_stage is None or best_doc is None or best_rank <= 0:
        return ("", "", ())
    titles = tuple(
        section.title for section in best_doc.sections if section.title.strip()
    )
    return (best_stage.stage_id, best_doc.kind, titles)


_DOC_KIND_ALIASES: dict[str, tuple[str, ...]] = {
    "可行性研究报告": ("可研", "可行性"),
    "项目建议书": ("建议书", "立项"),
    "投资估算": ("估算",),
    "初步设计说明": ("初设", "初步设计"),
    "设计概算": ("概算",),
    "施工图设计说明": ("施工图",),
    "工程结算书": ("结算",),
    "结算审计方案": ("审计方案", "结算审计"),
    "签证索赔报告": ("索赔", "签证"),
    "施工组织设计": ("施组", "组织设计"),
    "专项施工方案": ("专项方案", "施工方案"),
    "技术交底": ("交底",),
    "工艺标准": ("工艺",),
    "招标文件": ("招标",),
    "投标文件": ("投标",),
    "施工合同": ("合同", "总包合同"),
    "分包合同": ("分包",),
    "采购合同": ("采购", "购销"),
    "造价分析手册": ("造价分析",),
    "目标成本测算": ("目标成本", "成本测算"),
    "PPT汇报": ("PPT", "课件", "汇报"),
}


__all__ = [
    "EngineeringDocKind",
    "EngineeringSection",
    "EngineeringStage",
    "get_engineering_stage",
    "list_engineering_stages",
    "resolve_engineering_outline",
]
