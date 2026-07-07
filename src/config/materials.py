"""Material asset scanning and insertion-rule helpers."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from src.config.resolved import ImageInsertionItem


IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


@dataclass(slots=True)
class AssetItem:
    item_id: str = ""
    label: str = ""
    role: str = ""
    path: str = ""
    mime_type: str = ""
    tags: list[str] = field(default_factory=list)
    width_cm: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AssetCollection:
    collection_id: str = ""
    name: str = ""
    root_dir: str = ""
    items: list[AssetItem] = field(default_factory=list)


@dataclass(slots=True)
class AssetInsertionRule:
    rule_id: str = ""
    asset_role: str = ""
    target: str = "end"
    width_cm: float = 6.0
    required: bool = True


def scan_asset_collection(root_dir: str | Path) -> AssetCollection:
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return AssetCollection(root_dir=str(root_dir or ""))

    items: list[AssetItem] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        role = _normalize_role(path.stem)
        mime_type = mimetypes.guess_type(str(path))[0] or ""
        items.append(
            AssetItem(
                item_id=role,
                label=path.stem,
                role=role,
                path=str(path),
                mime_type=mime_type,
            )
        )

    return AssetCollection(
        collection_id=root.name,
        name=root.name,
        root_dir=str(root),
        items=items,
    )


def asset_items_from_role_paths(role_paths: Mapping[str, str] | None) -> list[AssetItem]:
    items: list[AssetItem] = []
    if not isinstance(role_paths, Mapping):
        return items
    for raw_role, raw_path in role_paths.items():
        role = _normalize_role(str(raw_role or ""))
        path = Path(str(raw_path or "").strip())
        if not role or not str(path):
            continue
        mime_type = mimetypes.guess_type(str(path))[0] or ""
        items.append(
            AssetItem(
                item_id=role,
                label=path.stem or role,
                role=role,
                path=str(path),
                mime_type=mime_type,
            )
        )
    return items


def build_image_insertions(
    asset_items: Sequence[AssetItem],
    rules: Sequence[AssetInsertionRule],
) -> list[ImageInsertionItem]:
    by_role = {item.role: item for item in asset_items if item.role and item.path}
    insertions: list[ImageInsertionItem] = []
    for rule in rules:
        role = _normalize_role(rule.asset_role)
        item = by_role.get(role)
        if item is None:
            continue
        width_cm = item.width_cm if item.width_cm is not None else rule.width_cm
        insertions.append(
            ImageInsertionItem(
                path=item.path,
                position=rule.target or "end",
                width_cm=width_cm,
            )
        )
    return insertions


def missing_required_asset_roles(
    asset_items: Sequence[AssetItem],
    rules: Sequence[AssetInsertionRule],
) -> list[str]:
    available = {item.role for item in asset_items if item.role and item.path}
    return [
        _normalize_role(rule.asset_role)
        for rule in rules
        if rule.required and _normalize_role(rule.asset_role) not in available
    ]


def parse_asset_insertion_rules(text: str, *, default_width_cm: float = 6.0) -> list[AssetInsertionRule]:
    rules: list[AssetInsertionRule] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            role, target = line.split("=", 1)
        elif ":" in line:
            role, target = line.split(":", 1)
        else:
            continue
        role = _normalize_role(role)
        target = target.strip() or "end"
        if not role:
            continue
        rules.append(
            AssetInsertionRule(
                rule_id=role,
                asset_role=role,
                target=target,
                width_cm=default_width_cm,
            )
        )
    return rules


def _normalize_role(value: str) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    aliases = {
        "公章": "seal",
        "印章": "seal",
        "seal": "seal",
        "stamp": "seal",
        "logo": "logo",
        "徽标": "logo",
        "标志": "logo",
        "法人签名": "legal_signature",
        "legal_signature": "legal_signature",
        "agent_signature": "agent_signature",
        "授权代表签名": "agent_signature",
        "签名": "signature",
        "signature": "signature",
        "资质": "qualification",
        "资质证书": "qualification",
        "qualification": "qualification",
        "二维码": "qrcode",
        "qr": "qrcode",
        "qrcode": "qrcode",
        "封面": "cover",
        "cover": "cover",
    }
    return aliases.get(normalized, normalized)


__all__ = [
    "AssetCollection",
    "AssetInsertionRule",
    "AssetItem",
    "asset_items_from_role_paths",
    "build_image_insertions",
    "missing_required_asset_roles",
    "parse_asset_insertion_rules",
    "scan_asset_collection",
]
