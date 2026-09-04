# -*- coding: utf-8 -*-
"""Engineering sample reference library (user-level).

Reads a curated manifest of real engineering documents (docx/md format specs)
located in a user-designated corpus such as H:\\AI-model.  The index lives in
the per-user config library so private paths never ship with the product.

Each sample can be attached to the AI assistant so chapter-by-chapter
authoring learns the real document's table of contents and writing habits.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.app_paths import config_library_data_root

_SCHEMA = "engineering-reference-v1"
_DIR_NAME = "engineering_reference"
_MANIFEST_NAME = "manifest.json"

_PROMPT_TEMPLATE = (
    "请按附件这份{kind}范本的章节目录与写作惯例，"
    "帮我写一份同类{kind}，分章节逐章撰写、各章不要重复，"
    "正文数据与项目信息用\u201c待补充\u201d占位。"
)


@dataclass(frozen=True, slots=True)
class EngineeringReferenceSample:
    stage: str
    kind: str
    name: str
    path: str
    note: str = ""
    available: bool = True

    def recommended_prompt(self) -> str:
        return _PROMPT_TEMPLATE.format(kind=self.kind or "文档")


def engineering_reference_dir() -> Path:
    return config_library_data_root() / _DIR_NAME


def load_engineering_reference_manifest() -> dict:
    path = engineering_reference_dir() / _MANIFEST_NAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if str(payload.get("schema_version") or "") != _SCHEMA:
        return {}
    return payload


def list_engineering_reference_samples() -> tuple[EngineeringReferenceSample, ...]:
    payload = load_engineering_reference_manifest()
    raw = payload.get("samples") or ()
    samples: list[EngineeringReferenceSample] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        path_text = str(item.get("path") or "").strip()
        if not path_text:
            continue
        stem = Path(path_text).stem
        samples.append(
            EngineeringReferenceSample(
                stage=str(item.get("stage") or "").strip(),
                kind=str(item.get("kind") or "").strip() or "文档",
                name=str(item.get("name") or stem).strip() or stem,
                path=path_text,
                note=str(item.get("note") or "").strip(),
                available=Path(path_text).expanduser().is_file(),
            )
        )
    return tuple(samples)


_STAGE_LABELS = {
    "decision": "① 决策立项",
    "design": "② 设计报批",
    "transaction": "③ 招投标与合同",
    "implementation": "④ 施工实施",
    "completion": "⑤ 竣工结算",
    "throughout": "⑥ 贯穿造价分析",
}


def engineering_stage_label(stage_id: str) -> str:
    return _STAGE_LABELS.get(str(stage_id or "").strip(), str(stage_id or "未分组"))


__all__ = [
    "EngineeringReferenceSample",
    "engineering_reference_dir",
    "engineering_stage_label",
    "list_engineering_reference_samples",
    "load_engineering_reference_manifest",
]
