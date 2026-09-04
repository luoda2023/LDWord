"""Audit exam master user pools before migration or cleanup."""

from __future__ import annotations

import json
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.config import library as config_library
from src.config.loader import load_scene
from src.config.scene import ExamPaperConfig, coerce_exam_paper_config
from src.config.work_mode import work_mode_for_scene_id
from src.shared.engine.exam_paper_style import (
    USER_EXAM_MASTER_DIR,
    ExamUserMasterInventoryItem,
    inventory_user_exam_master_files,
)


_CONFIG_SUFFIXES = (".json", ".yaml", ".yml")
_CLEANUP_CANDIDATE_CATEGORIES = (
    "program_copy_unreferenced",
    "program_import_unreferenced",
)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class ExamMasterReferenceSource:
    """One scene/plan reference to a user exam master DOCX."""

    config_id: str
    scene_id: str
    mode_id: str
    source_type: str
    scene_path: Path
    style_id: str
    label: str
    master_docx_path: str
    resolved_path: Path

    @property
    def file_name(self) -> str:
        return self.resolved_path.name

    def to_payload(self) -> dict[str, object]:
        return {
            "config_id": self.config_id,
            "scene_id": self.scene_id,
            "mode_id": self.mode_id,
            "source_type": self.source_type,
            "scene_path": str(self.scene_path),
            "style_id": self.style_id,
            "label": self.label,
            "master_docx_path": self.master_docx_path,
            "resolved_path": str(self.resolved_path),
            "file_name": self.file_name,
        }


@dataclass(frozen=True, slots=True)
class ExamMasterAuditLoadError:
    """One scene config that could not be loaded during the audit."""

    path: Path
    error: str

    def to_payload(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class ExamUserMasterPoolAudit:
    """Structured audit evidence for one exam master user pool."""

    user_master_dir: Path
    inventory_items: tuple[ExamUserMasterInventoryItem, ...]
    references: tuple[ExamMasterReferenceSource, ...]
    pool_id: str = "custom"
    scanned_scene_count: int = 0
    load_errors: tuple[ExamMasterAuditLoadError, ...] = ()

    @property
    def category_counts(self) -> dict[str, int]:
        counts = Counter(item.category for item in self.inventory_items)
        return dict(sorted(counts.items()))

    @property
    def cleanup_candidate_count(self) -> int:
        return sum(
            1
            for item in self.inventory_items
            if item.category in _CLEANUP_CANDIDATE_CATEGORIES
        )

    @property
    def referenced_file_count(self) -> int:
        return sum(1 for item in self.inventory_items if item.referenced)

    @property
    def has_cleanup_candidates(self) -> bool:
        return self.cleanup_candidate_count > 0

    def references_for_item(
        self,
        item: ExamUserMasterInventoryItem,
    ) -> tuple[ExamMasterReferenceSource, ...]:
        resolved = _safe_resolve(item.path)
        return tuple(
            reference
            for reference in self.references
            if _safe_resolve(reference.resolved_path) == resolved
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": "ldword.exam_master.user_pool_audit",
            "version": 1,
            "pool_id": self.pool_id,
            "user_master_dir": str(self.user_master_dir),
            "summary": {
                "total_file_count": len(self.inventory_items),
                "referenced_file_count": self.referenced_file_count,
                "cleanup_candidate_count": self.cleanup_candidate_count,
                "scanned_scene_count": self.scanned_scene_count,
                "load_error_count": len(self.load_errors),
                "category_counts": self.category_counts,
            },
            "items": [
                _inventory_item_payload(item, self.references_for_item(item))
                for item in self.inventory_items
            ],
            "references": [reference.to_payload() for reference in self.references],
            "load_errors": [error.to_payload() for error in self.load_errors],
        }


@dataclass(frozen=True, slots=True)
class ExamUserMasterArchivePlanEntry:
    """One file that a dry-run archive plan would move after user approval."""

    file_name: str
    category: str
    source_path: Path
    archive_path: Path
    sha1: str
    size_bytes: int
    action: str = "archive"
    reason: str = "unreferenced_program_managed_master"

    def to_payload(self) -> dict[str, object]:
        return {
            "file_name": self.file_name,
            "category": self.category,
            "action": self.action,
            "reason": self.reason,
            "source_path": str(self.source_path),
            "archive_path": str(self.archive_path),
            "sha1": self.sha1,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class ExamUserMasterArchivePlan:
    """Dry-run archive plan derived from a user master pool audit."""

    audit: ExamUserMasterPoolAudit
    archive_root: Path
    entries: tuple[ExamUserMasterArchivePlanEntry, ...]
    dry_run: bool = True

    @property
    def planned_file_count(self) -> int:
        return len(self.entries)

    @property
    def protected_file_count(self) -> int:
        return max(len(self.audit.inventory_items) - self.planned_file_count, 0)

    def planned_file_names(self) -> set[str]:
        return {entry.file_name for entry in self.entries}

    def to_payload(self) -> dict[str, object]:
        planned_names = self.planned_file_names()
        return {
            "kind": "ldword.exam_master.user_pool_archive_plan",
            "version": 1,
            "dry_run": self.dry_run,
            "pool_id": self.audit.pool_id,
            "user_master_dir": str(self.audit.user_master_dir),
            "archive_root": str(self.archive_root),
            "summary": {
                "total_file_count": len(self.audit.inventory_items),
                "planned_file_count": self.planned_file_count,
                "protected_file_count": self.protected_file_count,
                "referenced_file_count": self.audit.referenced_file_count,
                "cleanup_candidate_count": self.audit.cleanup_candidate_count,
                "scanned_scene_count": self.audit.scanned_scene_count,
                "load_error_count": len(self.audit.load_errors),
                "category_counts": self.audit.category_counts,
            },
            "planned_entries": [entry.to_payload() for entry in self.entries],
            "protected_items": [
                _archive_protected_item_payload(
                    item,
                    self.audit.references_for_item(item),
                )
                for item in self.audit.inventory_items
                if item.file_name not in planned_names
            ],
        }


def audit_exam_user_master_pool(
    *,
    user_master_dir: Path | str | None = None,
    scene_roots: Iterable[Path | str] | None = None,
    current_config: ExamPaperConfig | dict | None = None,
    current_config_id: str = "current_session",
    pool_id: str | None = None,
) -> ExamUserMasterPoolAudit:
    """Build read-only audit evidence for one exam master user pool."""

    user_dir = Path(user_master_dir) if user_master_dir is not None else USER_EXAM_MASTER_DIR
    audit_pool_id = str(pool_id or "").strip() or (
        "custom" if user_master_dir is not None else "active"
    )
    references, configs, scanned_count, load_errors = _collect_exam_master_references(
        user_dir=user_dir,
        scene_roots=scene_roots,
    )
    if current_config is not None:
        current_exam_config = coerce_exam_paper_config(current_config)
        if current_exam_config.custom_blank_styles:
            configs = (current_exam_config, *configs)
            references = (
                *_references_from_exam_config(
                    current_exam_config,
                    user_dir=user_dir,
                    config_id=current_config_id,
                    scene_id=current_config_id,
                    mode_id="exam",
                    source_type="current_session",
                    scene_path=Path(f"<{current_config_id}>"),
                ),
                *references,
            )
    items = inventory_user_exam_master_files(
        None,
        user_dir,
        reference_configs=configs,
    )
    return ExamUserMasterPoolAudit(
        user_master_dir=user_dir,
        inventory_items=items,
        references=references,
        pool_id=audit_pool_id,
        scanned_scene_count=scanned_count,
        load_errors=load_errors,
    )


def build_exam_user_master_archive_plan(
    audit: ExamUserMasterPoolAudit,
    *,
    archive_root: Path | str | None = None,
) -> ExamUserMasterArchivePlan:
    """Build a dry-run archive plan without moving or deleting any files."""

    target_root = (
        Path(archive_root)
        if archive_root is not None
        else _default_archive_root(audit)
    )
    entries: list[ExamUserMasterArchivePlanEntry] = []
    for item in audit.inventory_items:
        if item.referenced or item.category not in _CLEANUP_CANDIDATE_CATEGORIES:
            continue
        source_path = _safe_resolve(item.path)
        entries.append(
            ExamUserMasterArchivePlanEntry(
                file_name=item.file_name,
                category=item.category,
                source_path=source_path,
                archive_path=target_root / item.file_name,
                sha1=_file_sha1(source_path),
                size_bytes=_file_size(source_path),
            )
        )
    return ExamUserMasterArchivePlan(
        audit=audit,
        archive_root=target_root,
        entries=tuple(entries),
    )


def audit_active_exam_user_master_pool(
    *,
    scene_roots: Iterable[Path | str] | None = None,
    current_config: ExamPaperConfig | dict | None = None,
    current_config_id: str = "current_session",
) -> ExamUserMasterPoolAudit:
    """Audit the active mode-scoped exam master user pool."""

    return audit_exam_user_master_pool(
        user_master_dir=USER_EXAM_MASTER_DIR,
        scene_roots=scene_roots,
        current_config=current_config,
        current_config_id=current_config_id,
        pool_id="active",
    )


def write_exam_user_master_pool_audit_manifest(
    output_path: Path | str,
    *,
    user_master_dir: Path | str | None = None,
    scene_roots: Iterable[Path | str] | None = None,
    current_config: ExamPaperConfig | dict | None = None,
    current_config_id: str = "current_session",
    pool_id: str | None = None,
) -> Path:
    """Write a JSON audit manifest without mutating or deleting master files."""

    audit = audit_exam_user_master_pool(
        user_master_dir=user_master_dir,
        scene_roots=scene_roots,
        current_config=current_config,
        current_config_id=current_config_id,
        pool_id=pool_id,
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(audit.to_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def write_exam_user_master_archive_plan_manifest(
    output_path: Path | str,
    *,
    user_master_dir: Path | str | None = None,
    scene_roots: Iterable[Path | str] | None = None,
    current_config: ExamPaperConfig | dict | None = None,
    current_config_id: str = "current_session",
    pool_id: str | None = None,
    archive_root: Path | str | None = None,
) -> Path:
    """Write a dry-run archive manifest without moving or deleting files."""

    audit = audit_exam_user_master_pool(
        user_master_dir=user_master_dir,
        scene_roots=scene_roots,
        current_config=current_config,
        current_config_id=current_config_id,
        pool_id=pool_id,
    )
    plan = build_exam_user_master_archive_plan(audit, archive_root=archive_root)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(plan.to_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def format_exam_user_master_pool_audit_markdown(
    audit: ExamUserMasterPoolAudit,
) -> str:
    """Render the audit as a compact human-readable report."""

    lines = [
        "# Exam Master User Pool Audit",
        "",
        f"- Pool: `{audit.pool_id}`",
        f"- User master dir: `{audit.user_master_dir}`",
        f"- Total files: {len(audit.inventory_items)}",
        f"- Referenced files: {audit.referenced_file_count}",
        f"- Cleanup candidates: {audit.cleanup_candidate_count}",
        f"- Scanned scene configs: {audit.scanned_scene_count}",
        f"- Load errors: {len(audit.load_errors)}",
        "",
        "## Category Counts",
        "",
    ]
    if audit.category_counts:
        for category, count in audit.category_counts.items():
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- No files found.")

    lines.extend(["", "## Files", ""])
    for item in audit.inventory_items:
        references = audit.references_for_item(item)
        reference_text = (
            ", ".join(
                f"{reference.config_id}:{reference.style_id}"
                for reference in references
            )
            or "-"
        )
        lines.append(
            f"- `{item.file_name}`: `{item.category}`, "
            f"referenced={str(item.referenced).lower()}, refs={reference_text}"
        )
    return "\n".join(lines).rstrip() + "\n"


def format_exam_user_master_archive_plan_markdown(
    plan: ExamUserMasterArchivePlan,
) -> str:
    """Render a dry-run archive plan as a compact markdown report."""

    lines = [
        "# Exam Master User Pool Archive Plan",
        "",
        f"- Pool: `{plan.audit.pool_id}`",
        f"- Dry run: `{str(plan.dry_run).lower()}`",
        f"- User master dir: `{plan.audit.user_master_dir}`",
        f"- Archive root: `{plan.archive_root}`",
        f"- Total files: {len(plan.audit.inventory_items)}",
        f"- Planned files: {plan.planned_file_count}",
        f"- Protected files: {plan.protected_file_count}",
        f"- Cleanup candidates: {plan.audit.cleanup_candidate_count}",
        "",
        "## Planned Archive Entries",
        "",
    ]
    if plan.entries:
        for entry in plan.entries:
            lines.append(
                f"- `{entry.file_name}`: `{entry.category}`, "
                f"source=`{entry.source_path}`, archive=`{entry.archive_path}`, "
                f"sha1=`{entry.sha1}`"
            )
    else:
        lines.append("- No files planned for archive.")

    planned_names = plan.planned_file_names()
    lines.extend(["", "## Protected Items", ""])
    protected_items = [
        item for item in plan.audit.inventory_items if item.file_name not in planned_names
    ]
    if protected_items:
        for item in protected_items:
            reason = _archive_protected_reason(item, plan.audit.references_for_item(item))
            lines.append(f"- `{item.file_name}`: `{item.category}`, reason=`{reason}`")
    else:
        lines.append("- No protected items.")
    return "\n".join(lines).rstrip() + "\n"


def write_exam_user_master_pool_audit_markdown(
    output_path: Path | str,
    *,
    user_master_dir: Path | str | None = None,
    scene_roots: Iterable[Path | str] | None = None,
    current_config: ExamPaperConfig | dict | None = None,
    current_config_id: str = "current_session",
    pool_id: str | None = None,
) -> Path:
    """Write a markdown audit report without mutating or deleting master files."""

    audit = audit_exam_user_master_pool(
        user_master_dir=user_master_dir,
        scene_roots=scene_roots,
        current_config=current_config,
        current_config_id=current_config_id,
        pool_id=pool_id,
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        format_exam_user_master_pool_audit_markdown(audit),
        encoding="utf-8",
    )
    return target


def write_exam_user_master_archive_plan_markdown(
    output_path: Path | str,
    *,
    user_master_dir: Path | str | None = None,
    scene_roots: Iterable[Path | str] | None = None,
    current_config: ExamPaperConfig | dict | None = None,
    current_config_id: str = "current_session",
    pool_id: str | None = None,
    archive_root: Path | str | None = None,
) -> Path:
    """Write a dry-run archive markdown report without moving files."""

    audit = audit_exam_user_master_pool(
        user_master_dir=user_master_dir,
        scene_roots=scene_roots,
        current_config=current_config,
        current_config_id=current_config_id,
        pool_id=pool_id,
    )
    plan = build_exam_user_master_archive_plan(audit, archive_root=archive_root)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        format_exam_user_master_archive_plan_markdown(plan),
        encoding="utf-8",
    )
    return target


def _collect_exam_master_references(
    *,
    user_dir: Path,
    scene_roots: Iterable[Path | str] | None,
) -> tuple[
    tuple[ExamMasterReferenceSource, ...],
    tuple[ExamPaperConfig, ...],
    int,
    tuple[ExamMasterAuditLoadError, ...],
]:
    references: list[ExamMasterReferenceSource] = []
    configs: list[ExamPaperConfig] = []
    load_errors: list[ExamMasterAuditLoadError] = []
    scanned_count = 0

    for path in _iter_scene_config_paths(scene_roots):
        try:
            scene = load_scene(path)
        except Exception as exc:
            load_errors.append(
                ExamMasterAuditLoadError(path=path, error=f"{type(exc).__name__}: {exc}")
            )
            continue

        scanned_count += 1
        config = coerce_exam_paper_config(getattr(scene, "exam_paper", None))
        if not config.custom_blank_styles:
            continue
        configs.append(config)

        scene_id = str(getattr(scene, "scene_id", "") or path.stem).strip() or path.stem
        mode_id, source_type = _scene_path_mode_and_source(path, scene_id)
        references.extend(
            _references_from_exam_config(
                config,
                user_dir=user_dir,
                config_id=path.stem,
                scene_id=scene_id,
                mode_id=mode_id,
                source_type=source_type,
                scene_path=path,
            )
        )

    return tuple(references), tuple(configs), scanned_count, tuple(load_errors)


def _references_from_exam_config(
    config: ExamPaperConfig,
    *,
    user_dir: Path,
    config_id: str,
    scene_id: str,
    mode_id: str,
    source_type: str,
    scene_path: Path,
) -> tuple[ExamMasterReferenceSource, ...]:
    references: list[ExamMasterReferenceSource] = []
    for style in config.custom_blank_styles:
        style_id = str(getattr(style, "style_id", "") or "").strip()
        raw_path = str(getattr(style, "master_docx_path", "") or "").strip()
        resolved = _resolve_master_path(raw_path, style_id, user_dir)
        if resolved is None:
            continue
        references.append(
            ExamMasterReferenceSource(
                config_id=config_id,
                scene_id=scene_id,
                mode_id=mode_id,
                source_type=source_type,
                scene_path=scene_path,
                style_id=style_id,
                label=str(getattr(style, "label", "") or style_id).strip(),
                master_docx_path=raw_path,
                resolved_path=resolved,
            )
        )
    return tuple(references)


def _iter_scene_config_paths(scene_roots: Iterable[Path | str] | None) -> tuple[Path, ...]:
    roots = (
        tuple(Path(root) for root in scene_roots)
        if scene_roots is not None
        else (config_library.SCENE_LIBRARY_DIR,)
    )
    paths: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for suffix in _CONFIG_SUFFIXES:
            for path in sorted(root.rglob(f"*{suffix}")):
                resolved = _safe_resolve(path)
                if resolved in seen:
                    continue
                seen.add(resolved)
                paths.append(path)
    return tuple(paths)


def _scene_path_mode_and_source(path: Path, scene_id: str) -> tuple[str, str]:
    mode_id = work_mode_for_scene_id(scene_id).mode_id
    source_type = ""
    source_dir = path.parent
    if source_dir.name in {"builtin", "user"}:
        source_type = source_dir.name
        mode_dir = source_dir.parent
        if mode_dir.name:
            mode_id = mode_dir.name

    return mode_id, source_type


def _resolve_master_path(raw_path: str, style_id: str, user_dir: Path) -> Path | None:
    raw = str(raw_path or "").strip()
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return _safe_resolve(path)
    if style_id:
        return _safe_resolve(user_dir / f"{style_id}.docx")
    return None


def _inventory_item_payload(
    item: ExamUserMasterInventoryItem,
    references: tuple[ExamMasterReferenceSource, ...],
) -> dict[str, object]:
    return {
        "file_name": item.file_name,
        "path": str(item.path),
        "category": item.category,
        "referenced": item.referenced,
        "style_id": item.style_id,
        "label": item.label,
        "note": item.note,
        "cleanup_candidate": item.category in _CLEANUP_CANDIDATE_CATEGORIES,
        "references": [reference.to_payload() for reference in references],
    }


def _archive_protected_item_payload(
    item: ExamUserMasterInventoryItem,
    references: tuple[ExamMasterReferenceSource, ...],
) -> dict[str, object]:
    return {
        **_inventory_item_payload(item, references),
        "archive_protected_reason": _archive_protected_reason(item, references),
    }


def _archive_protected_reason(
    item: ExamUserMasterInventoryItem,
    references: tuple[ExamMasterReferenceSource, ...],
) -> str:
    if item.referenced or references:
        return "referenced_by_plan"
    if item.category not in _CLEANUP_CANDIDATE_CATEGORIES:
        return f"category_not_cleanup_candidate:{item.category}"
    return "cleanup_candidate_requires_review"


def _default_archive_root(audit: ExamUserMasterPoolAudit) -> Path:
    pool = str(audit.pool_id or "custom").strip() or "custom"
    suffix = "user_legacy" if pool == "legacy" else f"user_{pool}"
    return audit.user_master_dir.parent / "_archive" / suffix


def _file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


__all__ = [
    "ExamMasterAuditLoadError",
    "ExamMasterReferenceSource",
    "ExamUserMasterArchivePlan",
    "ExamUserMasterArchivePlanEntry",
    "ExamUserMasterPoolAudit",
    "audit_active_exam_user_master_pool",
    "audit_exam_user_master_pool",
    "build_exam_user_master_archive_plan",
    "format_exam_user_master_archive_plan_markdown",
    "format_exam_user_master_pool_audit_markdown",
    "write_exam_user_master_archive_plan_manifest",
    "write_exam_user_master_archive_plan_markdown",
    "write_exam_user_master_pool_audit_manifest",
    "write_exam_user_master_pool_audit_markdown",
]
