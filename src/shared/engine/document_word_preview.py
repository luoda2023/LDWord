"""Shared cached preview pipeline for generated Word documents."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time

from src.shared.engine.docx_page_renderer import render_docx_pages


_CACHE_MANIFEST = "preview_result.json"
_DEFAULT_MAX_CACHE_ENTRIES = 12


@dataclass(frozen=True, slots=True)
class PreviewDocumentBuild:
    status: str
    docx_path: Path | None = None
    uses_sample_data: bool = False
    issues: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status == "ready" and self.docx_path is not None


@dataclass(frozen=True, slots=True)
class DocumentWordPreviewRequest:
    provider_id: str
    variant_id: str
    cache_payload: Mapping[str, object]
    build_document: Callable[[Path], PreviewDocumentBuild]


@dataclass(frozen=True, slots=True)
class DocumentWordPreviewResult:
    status: str
    provider_id: str
    variant_id: str
    page_paths: tuple[Path, ...] = ()
    docx_path: Path | None = None
    pdf_path: Path | None = None
    renderer: str = ""
    cache_key: str = ""
    cache_hit: bool = False
    uses_sample_data: bool = False
    issues: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status == "ready" and bool(self.page_paths)


def render_document_word_preview(
    request: DocumentWordPreviewRequest,
    *,
    cache_root: Path | str | None = None,
    attempt_render: bool = True,
    max_cache_entries: int = _DEFAULT_MAX_CACHE_ENTRIES,
    force: bool = False,
    cancel_event: threading.Event | None = None,
) -> DocumentWordPreviewResult:
    provider_id = _safe_id(request.provider_id or "document")
    variant_id = str(request.variant_id or "default").strip() or "default"
    cache_key = _preview_cache_key(provider_id, variant_id, request.cache_payload)
    if _cancel_requested(cancel_event):
        return _cancelled_preview_result(
            provider_id=provider_id,
            variant_id=variant_id,
            cache_key=cache_key,
        )
    root = (
        Path(cache_root)
        if cache_root is not None
        else Path(tempfile.gettempdir()) / "ldword_form" / "document_word_preview"
    )
    provider_root = root / provider_id
    cache_dir = provider_root / cache_key
    manifest_path = cache_dir / _CACHE_MANIFEST

    if _cancel_requested(cancel_event):
        return _cancelled_preview_result(
            provider_id=provider_id,
            variant_id=variant_id,
            cache_key=cache_key,
        )
    if force and cache_dir.is_dir():
        shutil.rmtree(cache_dir, ignore_errors=True)
    cached = _load_cached_result(manifest_path)
    if cached is not None:
        if _cancel_requested(cancel_event):
            return _cancelled_preview_result(
                provider_id=provider_id,
                variant_id=variant_id,
                cache_key=cache_key,
            )
        try:
            os.utime(cache_dir, None)
        except OSError:
            pass
        return replace(cached, cache_hit=True)
    if manifest_path.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)

    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        build = request.build_document(cache_dir)
    except Exception as exc:
        build = PreviewDocumentBuild(
            status="build_failed",
            issues=(str(exc),),
        )
    if _cancel_requested(cancel_event):
        shutil.rmtree(cache_dir, ignore_errors=True)
        return _cancelled_preview_result(
            provider_id=provider_id,
            variant_id=variant_id,
            cache_key=cache_key,
        )
    if not build.ready:
        result = DocumentWordPreviewResult(
            status=build.status or "build_failed",
            provider_id=provider_id,
            variant_id=variant_id,
            docx_path=build.docx_path,
            cache_key=cache_key,
            uses_sample_data=build.uses_sample_data,
            issues=build.issues,
        )
        _write_cache_manifest(manifest_path, result)
        return result

    rendered = render_docx_pages(
        build.docx_path,
        cache_dir,
        attempt_render=attempt_render,
    )
    if _cancel_requested(cancel_event):
        shutil.rmtree(cache_dir, ignore_errors=True)
        return _cancelled_preview_result(
            provider_id=provider_id,
            variant_id=variant_id,
            cache_key=cache_key,
        )
    status = "ready" if rendered.ready else rendered.status
    result = DocumentWordPreviewResult(
        status=status,
        provider_id=provider_id,
        variant_id=variant_id,
        page_paths=rendered.page_paths,
        docx_path=rendered.docx_path,
        pdf_path=rendered.pdf_path,
        renderer=rendered.renderer,
        cache_key=cache_key,
        uses_sample_data=build.uses_sample_data,
        issues=(*build.issues, *rendered.issues),
    )
    _write_cache_manifest(manifest_path, result)
    _prune_cache(provider_root, keep=cache_key, max_entries=max_cache_entries)
    return result


def _cancel_requested(cancel_event: threading.Event | None) -> bool:
    return bool(cancel_event is not None and cancel_event.is_set())


def _cancelled_preview_result(
    *,
    provider_id: str,
    variant_id: str,
    cache_key: str,
) -> DocumentWordPreviewResult:
    return DocumentWordPreviewResult(
        status="cancelled",
        provider_id=provider_id,
        variant_id=variant_id,
        cache_key=cache_key,
    )


def file_cache_signature(path: Path | str) -> tuple[object, ...]:
    source = Path(path)
    try:
        stat = source.stat()
        return str(source.resolve()), stat.st_mtime_ns, stat.st_size
    except OSError:
        return str(source), 0, 0


def _preview_cache_key(
    provider_id: str,
    variant_id: str,
    payload: Mapping[str, object],
) -> str:
    encoded = json.dumps(
        {
            "provider_id": provider_id,
            "variant_id": variant_id,
            "payload": dict(payload),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()[:24]


def _write_cache_manifest(path: Path, result: DocumentWordPreviewResult) -> None:
    payload = {
        "status": result.status,
        "provider_id": result.provider_id,
        "variant_id": result.variant_id,
        "page_paths": [str(item) for item in result.page_paths],
        "docx_path": str(result.docx_path or ""),
        "pdf_path": str(result.pdf_path or ""),
        "renderer": result.renderer,
        "cache_key": result.cache_key,
        "uses_sample_data": result.uses_sample_data,
        "issues": list(result.issues),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_cached_result(path: Path) -> DocumentWordPreviewResult | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        page_paths = tuple(Path(value) for value in payload.get("page_paths", ()))
        docx_text = str(payload.get("docx_path", "") or "")
        pdf_text = str(payload.get("pdf_path", "") or "")
        required_paths = [*page_paths]
        if docx_text:
            required_paths.append(Path(docx_text))
        if any(not item.is_file() for item in required_paths):
            return None
        status = str(payload.get("status", "") or "")
        if status not in {"ready", "docx_only"}:
            return None
        if status == "ready" and not page_paths:
            return None
        return DocumentWordPreviewResult(
            status=status,
            provider_id=str(payload.get("provider_id", "") or "document"),
            variant_id=str(payload.get("variant_id", "") or "default"),
            page_paths=page_paths,
            docx_path=Path(docx_text) if docx_text else None,
            pdf_path=Path(pdf_text) if pdf_text else None,
            renderer=str(payload.get("renderer", "") or ""),
            cache_key=str(payload.get("cache_key", "") or ""),
            cache_hit=False,
            uses_sample_data=bool(payload.get("uses_sample_data", False)),
            issues=tuple(str(item) for item in payload.get("issues", ())),
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _prune_cache(root: Path, *, keep: str, max_entries: int) -> None:
    try:
        entries = [item for item in root.iterdir() if item.is_dir()]
    except OSError:
        return
    entries.sort(
        key=lambda item: item.stat().st_mtime if item.exists() else time.time(),
        reverse=True,
    )
    retained = 0
    for entry in entries:
        if entry.name == keep or retained < max(1, int(max_entries)):
            retained += 1
            continue
        shutil.rmtree(entry, ignore_errors=True)


def _safe_id(value: str) -> str:
    normalized = str(value or "").strip() or "document"
    return "".join(
        character if character.isalnum() or character in {"_", "-"} else "_"
        for character in normalized
    )


__all__ = [
    "DocumentWordPreviewRequest",
    "DocumentWordPreviewResult",
    "PreviewDocumentBuild",
    "file_cache_signature",
    "render_document_word_preview",
]
