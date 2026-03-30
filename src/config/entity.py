"""
EntityArchive — 实体档案数据结构

支持多公司/多角色配置集，每个档案关联一组替换字段和素材文件夹。
批量生成时可选多个档案，各自独立输出。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EntityProfile:
    """单个实体配置集（如：某公司某角色的一套数据）。"""

    profile_id: str = ""
    profile_name: str = ""          # e.g. "投标人主体"
    fields: dict[str, str] = field(default_factory=dict)
    # 示例 fields:
    # {
    #     "company_name": "中建三局第一建设工程有限公司",
    #     "legal_person": "张三",
    #     "address": "武汉市洪山区xxx路xxx号",
    #     "phone": "027-12345678",
    #     "project_name": "xxx工程",
    #     "bid_date": "2026年3月24日",
    # }

    assets_dir: str = ""            # 关联素材文件夹路径


@dataclass
class EntityArchive:
    """实体档案（一个公司/组织的所有配置集）。"""

    archive_id: str = ""
    archive_name: str = ""          # e.g. "中建三局总部"
    profiles: list[EntityProfile] = field(default_factory=list)

    def get_profile(self, profile_id: str) -> EntityProfile | None:
        for p in self.profiles:
            if p.profile_id == profile_id:
                return p
        return None

    def get_default_profile(self) -> EntityProfile | None:
        return self.profiles[0] if self.profiles else None

    def list_profile_names(self) -> list[str]:
        return [p.profile_name for p in self.profiles]


# ── 持久化 ──────────────────────────────────────────

def load_entity_archive(path: str | Path) -> EntityArchive:
    """从 JSON 文件加载实体档案。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    profiles = [
        EntityProfile(**p) for p in data.get("profiles", [])
    ]
    return EntityArchive(
        archive_id=data.get("archive_id", ""),
        archive_name=data.get("archive_name", ""),
        profiles=profiles,
    )


def save_entity_archive(archive: EntityArchive, path: str | Path) -> None:
    """保存实体档案到 JSON 文件。"""
    data = {
        "archive_id": archive.archive_id,
        "archive_name": archive.archive_name,
        "profiles": [
            {
                "profile_id": p.profile_id,
                "profile_name": p.profile_name,
                "fields": p.fields,
                "assets_dir": p.assets_dir,
            }
            for p in archive.profiles
        ],
    }
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
