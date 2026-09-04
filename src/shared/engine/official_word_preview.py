"""Official-document adapter for the shared Word preview pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from src.config.master_library import MasterSpec
from src.shared.engine.document_word_preview import (
    DocumentWordPreviewRequest,
    DocumentWordPreviewResult,
    PreviewDocumentBuild,
    file_cache_signature,
    render_document_word_preview,
)
from src.shared.engine.docx_page_renderer import (
    REAL_WORD_PREVIEW_ENV,
    real_word_preview_enabled,
)
from src.shared.engine.official_document_assembly import (
    assemble_official_document_docx,
)
from src.shared.engine.official_document_sample_data import (
    official_sample_entity_data,
)


OfficialWordPreviewResult = DocumentWordPreviewResult


def build_official_word_preview_request(
    *,
    profile_id: str,
    entity_data: Mapping[str, object] | None,
    field_aliases: Mapping[str, str] | None = None,
    master: MasterSpec,
    template_id: str = "",
) -> DocumentWordPreviewRequest:
    normalized_profile = str(profile_id or "notice").strip() or "notice"
    supplied = {
        str(key): value
        for key, value in dict(entity_data or {}).items()
        if str(value or "").strip()
    }
    sample_data = official_sample_entity_data(normalized_profile)
    uses_sample_data = any(
        not str(supplied.get(key, "") or "").strip()
        for key in ("title", "body", "organization", "document_no", "issue_date")
    )
    resolved_data = {**sample_data, **supplied, "document_type": normalized_profile}

    def build_document(output_dir: Path) -> PreviewDocumentBuild:
        assembly = assemble_official_document_docx(
            normalized_profile,
            resolved_data,
            output_dir,
            field_aliases=field_aliases,
            filename="word_preview.docx",
            master=master,
        )
        if not assembly.ok or assembly.docx_path is None:
            issues = tuple(
                item
                for item in (
                    f"assembly_{assembly.status}",
                    *(f"missing:{item}" for item in assembly.missing_required_fields),
                    *(f"unresolved:{item}" for item in assembly.unresolved_placeholders),
                )
                if item
            )
            return PreviewDocumentBuild(
                status=assembly.status,
                docx_path=assembly.docx_path,
                uses_sample_data=uses_sample_data,
                issues=issues,
            )
        return PreviewDocumentBuild(
            status="ready",
            docx_path=assembly.docx_path,
            uses_sample_data=uses_sample_data,
        )

    return DocumentWordPreviewRequest(
        provider_id="official",
        variant_id=normalized_profile,
        cache_payload={
            "profile_id": normalized_profile,
            "entity_data": resolved_data,
            "field_aliases": dict(field_aliases or {}),
            "master_id": master.master_id,
            "master_version": master.master_version,
            "master_signature": file_cache_signature(master.docx_path),
            "template_id": str(template_id or ""),
        },
        build_document=build_document,
    )


def render_official_word_preview(
    *,
    profile_id: str,
    entity_data: Mapping[str, object] | None,
    field_aliases: Mapping[str, str] | None = None,
    master: MasterSpec,
    template_id: str = "",
    cache_root: Path | str | None = None,
    attempt_render: bool = True,
    max_cache_entries: int = 12,
    force: bool = False,
) -> DocumentWordPreviewResult:
    request = build_official_word_preview_request(
        profile_id=profile_id,
        entity_data=entity_data,
        field_aliases=field_aliases,
        master=master,
        template_id=template_id,
    )
    return render_document_word_preview(
        request,
        cache_root=cache_root,
        attempt_render=attempt_render,
        max_cache_entries=max_cache_entries,
        force=force,
    )


__all__ = [
    "OfficialWordPreviewResult",
    "REAL_WORD_PREVIEW_ENV",
    "build_official_word_preview_request",
    "real_word_preview_enabled",
    "render_official_word_preview",
]
