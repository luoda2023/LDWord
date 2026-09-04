"""Material asset scanning and insertion-rule helpers."""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from src.config.resolved import ImageInsertionItem


IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


# Keys use the same compact form as spreadsheet column matching.  Keep every
# supported human-facing alias here so import, persistence and execution cannot
# disagree about the identity of one image role.
ASSET_ROLE_ALIASES: dict[str, str] = {
    "logo": "logo",
    "标志": "logo",
    "徽标": "logo",
    "品牌标志": "logo",
    "seal": "seal",
    "stamp": "seal",
    "公章": "seal",
    "印章": "seal",
    "signature": "signature",
    "签名": "signature",
    "legalsignature": "legal_signature",
    "法人签名": "legal_signature",
    "法定代表人签名": "legal_signature",
    "agentsignature": "agent_signature",
    "授权代表签名": "agent_signature",
    "委托代理人签名": "agent_signature",
    "qualification": "qualification",
    "资质": "qualification",
    "资质证书": "qualification",
    "productimage": "product_image",
    "产品图片": "product_image",
    "caseimage": "case_image",
    "案例图片": "case_image",
    "diagram": "diagram",
    "示意图": "diagram",
    "figure": "figure",
    "插图": "figure",
    "qr": "qrcode",
    "qrcode": "qrcode",
    "二维码": "qrcode",
    "cover": "cover",
    "封面": "cover",
    "封面图": "cover",
    "questionfigure": "question_figure",
    "questionimage": "question_figure",
    "questionasset": "question_figure",
    "题目图片": "question_figure",
    "试题图片": "question_figure",
    "题图": "question_figure",
}


def resolve_asset_role_alias(value: object) -> str:
    """Resolve a declared alias, returning ``""`` for an unknown role."""

    compact = re.sub(
        r"[^0-9a-z\u4e00-\u9fff]+",
        "",
        str(value or "").strip().casefold(),
    )
    return ASSET_ROLE_ALIASES.get(compact, "")


def normalize_asset_role(value: object) -> str:
    """Return the single canonical identity used by every image-material layer."""

    raw = str(value or "").strip().casefold()
    alias = resolve_asset_role_alias(raw)
    if alias:
        return alias
    return re.sub(r"\s+", "_", raw)


def is_supported_image_path(path: str | Path) -> bool:
    """Whether a path belongs to the image-material boundary.

    This is deliberately suffix-based: discovery and planning may run before a
    local file is available, while byte-level validation remains the insertion
    module's responsibility.
    """

    text = str(path or "").strip()
    return bool(text) and Path(text).suffix.lower() in IMAGE_EXTENSIONS


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
    group_id: str = ""
    sequence: int | None = None
    source_path: str = ""
    original_relative_path: str = ""
    normalized_name: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        self.role = normalize_asset_role(self.role)


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
    cardinality: str = "single"
    min_items: int = 0
    max_items: int | None = 1
    occurrence_policy: str = "first"

    def __post_init__(self) -> None:
        self.asset_role = normalize_asset_role(self.asset_role)


def scan_asset_collection(root_dir: str | Path) -> AssetCollection:
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return AssetCollection(root_dir=str(root_dir or ""))

    items: list[AssetItem] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_supported_image_path(path):
            continue
        role = normalize_asset_role(path.stem)
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
        role = normalize_asset_role(raw_role)
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
                source_path=str(path),
                original_relative_path=path.name,
                normalized_name=path.name,
            )
        )
    return items


def build_image_insertions(
    asset_items: Sequence[AssetItem],
    rules: Sequence[AssetInsertionRule],
) -> list[ImageInsertionItem]:
    by_role: dict[str, list[tuple[int, AssetItem]]] = {}
    for source_index, item in enumerate(asset_items):
        role = normalize_asset_role(item.role)
        if not role or not item.path or not is_supported_image_path(item.path):
            continue
        by_role.setdefault(role, []).append((source_index, item))
    for items in by_role.values():
        items.sort(key=lambda pair: _asset_item_sort_key(pair[1], pair[0]))

    insertions: list[ImageInsertionItem] = []
    for rule in rules:
        role = normalize_asset_role(rule.asset_role)
        indexed_items = by_role.get(role, [])
        if not indexed_items:
            continue
        items = [item for _source_index, item in indexed_items]
        is_multiple = _normalize_cardinality(rule.cardinality) == "multiple"
        selected = items if is_multiple else items[:1]
        for item in selected:
            width_cm = item.width_cm if item.width_cm is not None else rule.width_cm
            insertions.append(
                ImageInsertionItem(
                    path=item.path,
                    position=rule.target or "end",
                    width_cm=width_cm,
                    role=role if is_multiple else "",
                    item_id=item.item_id if is_multiple else "",
                    group_id=(item.group_id or role) if is_multiple else "",
                    sequence=item.sequence if is_multiple else None,
                    normalized_name=item.normalized_name if is_multiple else "",
                )
            )
    return insertions


def _asset_item_sort_key(
    item: AssetItem,
    source_index: int = 0,
) -> tuple[int, int, str, str, int]:
    sequence = item.sequence
    if sequence is None:
        for key in (
            "sequence",
            "figure_order",
            "figureOrder",
            "image_order",
            "imageOrder",
            "sort_order",
            "sortOrder",
        ):
            value = str(item.metadata.get(key, "") or "").strip()
            if not value:
                continue
            try:
                sequence = int(value)
            except ValueError:
                continue
            break
    return (
        0 if sequence is not None else 1,
        sequence if sequence is not None else 0,
        str(item.original_relative_path or item.normalized_name or item.path).casefold(),
        str(item.item_id or "").casefold(),
        source_index,
    )


def _normalize_cardinality(value: object) -> str:
    return "multiple" if str(value or "").strip().lower() == "multiple" else "single"


def missing_required_asset_roles(
    asset_items: Sequence[AssetItem],
    rules: Sequence[AssetInsertionRule],
) -> list[str]:
    available = {
        item.role
        for item in asset_items
        if item.role and item.path and is_supported_image_path(item.path)
    }
    return [
        normalize_asset_role(rule.asset_role)
        for rule in rules
        if rule.required and normalize_asset_role(rule.asset_role) not in available
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
        role = normalize_asset_role(role)
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




__all__ = [
    "ASSET_ROLE_ALIASES",
    "AssetCollection",
    "AssetInsertionRule",
    "AssetItem",
    "asset_items_from_role_paths",
    "build_image_insertions",
    "is_supported_image_path",
    "missing_required_asset_roles",
    "normalize_asset_role",
    "parse_asset_insertion_rules",
    "resolve_asset_role_alias",
    "scan_asset_collection",
]
