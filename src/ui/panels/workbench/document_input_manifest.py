from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

DEFAULT_MAX_DOCUMENTS = 500
DEFAULT_IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".lark-formatter",
    "__pycache__",
    "ldword-output",
    "ldword-form-outputs",
    "ldword-output",
    "ldword-outputs",
    "output",
    "outputs",
}


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _path_identity(path: Path) -> str:
    return str(_resolved_path(path)).casefold()


def _safe_component(value: str, *, fallback: str) -> str:
    normalized = "".join(
        "_" if char in '<>:"/\\|?*' or ord(char) < 32 else char
        for char in str(value or "").strip()
    ).rstrip(" .")
    return normalized or fallback


@dataclass(frozen=True)
class DocumentInputRoot:
    root_id: str
    path: str
    label: str
    kind: str


@dataclass(frozen=True)
class DiscoveredDocument:
    source_path: str
    root_id: str
    relative_path: str


@dataclass(frozen=True)
class DocumentInputManifest:
    requested_paths: tuple[str, ...] = ()
    roots: tuple[DocumentInputRoot, ...] = ()
    documents: tuple[DiscoveredDocument, ...] = ()
    issues: tuple[str, ...] = ()
    truncated: bool = False
    max_documents: int = DEFAULT_MAX_DOCUMENTS

    def paths(self) -> tuple[str, ...]:
        return tuple(item.source_path for item in self.documents)

    def root_for(self, document: DiscoveredDocument) -> DocumentInputRoot | None:
        return next(
            (root for root in self.roots if root.root_id == document.root_id),
            None,
        )

    def output_roots(self, custom_base: str = "") -> dict[str, str]:
        """Map every source to a stable, source-relative output root."""

        custom_root = (
            _resolved_path(Path(custom_base).expanduser())
            if str(custom_base or "").strip()
            else None
        )
        labels: dict[str, list[DocumentInputRoot]] = {}
        for root in self.roots:
            labels.setdefault(root.label.casefold(), []).append(root)

        root_components: dict[str, str] = {}
        for root in self.roots:
            component = _safe_component(root.label, fallback="documents")
            if len(labels.get(root.label.casefold(), ())) > 1:
                digest = sha256(root.root_id.encode("utf-8")).hexdigest()[:8]
                component = f"{component}-{digest}"
            root_components[root.root_id] = component

        mapping: dict[str, str] = {}
        for document in self.documents:
            root = self.root_for(document)
            if root is None:
                continue
            source = Path(document.source_path)
            relative = Path(document.relative_path)
            relative_parent = (
                relative.parent if str(relative.parent) != "." else Path()
            )
            if custom_root is not None:
                base = custom_root / root_components[root.root_id]
            else:
                root_path = Path(root.path)
                base = root_path / "output"
            output_root = base / relative_parent / _safe_component(
                source.stem,
                fallback="document",
            )
            mapping[document.source_path.casefold()] = str(output_root)
        return mapping


def discover_document_inputs(
    paths: Iterable[str],
    *,
    accepted_suffixes: Iterable[str],
    max_documents: int = DEFAULT_MAX_DOCUMENTS,
    ignored_directory_names: Iterable[str] = DEFAULT_IGNORED_DIRECTORY_NAMES,
) -> DocumentInputManifest:
    """Expand mixed files/folders into one deterministic document manifest."""

    requested = tuple(
        str(value or "").strip()
        for value in paths
        if str(value or "").strip()
    )
    suffixes = {
        (
            suffix
            if str(suffix).startswith(".")
            else f".{suffix}"
        ).casefold()
        for suffix in (
            str(value or "").strip()
            for value in accepted_suffixes
        )
        if suffix
    }
    ignored_names = {
        str(value or "").strip().casefold()
        for value in ignored_directory_names
        if str(value or "").strip()
    }
    limit = max(1, int(max_documents or DEFAULT_MAX_DOCUMENTS))

    roots: list[DocumentInputRoot] = []
    documents: list[DiscoveredDocument] = []
    issues: list[str] = []
    root_by_identity: dict[str, DocumentInputRoot] = {}
    seen_documents: set[str] = set()
    truncated = False

    def ensure_root(root_path: Path, *, kind: str) -> DocumentInputRoot:
        resolved_root = _resolved_path(root_path)
        identity = _path_identity(resolved_root)
        existing = root_by_identity.get(identity)
        if existing is not None:
            return existing
        label = resolved_root.name or "documents"
        root = DocumentInputRoot(
            root_id=identity,
            path=str(resolved_root),
            label=label,
            kind=kind,
        )
        root_by_identity[identity] = root
        roots.append(root)
        return root

    def append_document(path: Path, root: DocumentInputRoot) -> bool:
        nonlocal truncated
        resolved = _resolved_path(path)
        identity = _path_identity(resolved)
        if identity in seen_documents:
            return True
        if len(documents) >= limit:
            truncated = True
            return False
        seen_documents.add(identity)
        try:
            relative = resolved.relative_to(Path(root.path))
        except ValueError:
            relative = Path(resolved.name)
        documents.append(
            DiscoveredDocument(
                source_path=str(resolved),
                root_id=root.root_id,
                relative_path=str(relative),
            )
        )
        return True

    for raw_path in requested:
        candidate = Path(raw_path).expanduser()
        if not candidate.exists():
            issues.append(f"路径不存在：{raw_path}")
            continue
        if candidate.is_file():
            if candidate.name.startswith("~$"):
                continue
            if candidate.suffix.casefold() not in suffixes:
                issues.append(f"不支持的文件格式：{candidate.name}")
                continue
            root = ensure_root(candidate.parent, kind="file_selection")
            if not append_document(candidate, root):
                break
            continue
        if not candidate.is_dir():
            issues.append(f"无法读取路径：{raw_path}")
            continue

        root = ensure_root(candidate, kind="folder")
        scan_errors: list[OSError] = []
        try:
            walker = os.walk(
                candidate,
                topdown=True,
                onerror=scan_errors.append,
                followlinks=False,
            )
            for directory, child_directories, filenames in walker:
                child_directories[:] = sorted(
                    (
                        name
                        for name in child_directories
                        if name.casefold() not in ignored_names
                        and not name.startswith(".")
                    ),
                    key=str.casefold,
                )
                for filename in sorted(filenames, key=str.casefold):
                    child = Path(directory) / filename
                    if (
                        child.name.startswith("~$")
                        or child.suffix.casefold() not in suffixes
                    ):
                        continue
                    if not append_document(child, root):
                        break
                if truncated:
                    break
        except OSError as exc:
            scan_errors.append(exc)
        for exc in scan_errors:
            issues.append(f"文件夹部分内容无法读取：{candidate.name}（{exc}）")
        if truncated:
            break

    if truncated:
        issues.append(f"扫描结果超过单次上限 {limit} 个文档，请缩小范围")
    return DocumentInputManifest(
        requested_paths=requested,
        roots=tuple(roots),
        documents=tuple(documents),
        issues=tuple(issues),
        truncated=truncated,
        max_documents=limit,
    )


__all__ = [
    "DEFAULT_MAX_DOCUMENTS",
    "DiscoveredDocument",
    "DocumentInputManifest",
    "DocumentInputRoot",
    "discover_document_inputs",
]
