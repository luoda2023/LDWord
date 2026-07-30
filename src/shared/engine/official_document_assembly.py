"""Official-document assembly from master contracts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Mapping
from uuid import uuid4

from docx import Document

from src.config.master_library import (
    MasterSpec,
    resolve_official_master_for_contract,
)
from src.config.master_preflight import check_master_preflight
from src.config.official_document_profiles import (
    OfficialDocumentAssemblyContract,
    get_official_document_assembly_contract,
    get_official_document_profile,
)
from src.config.official_material_form import official_material_field_label
from src.shared.io.artifact_publication import (
    StagedArtifact,
    publish_staged_artifacts,
)
from src.shared.engine.fixed_layout_text import replace_fixed_layout_placeholders
from src.shared.engine.run_ops import get_full_text, replace_run_text
from src.shared.engine.material_token_contract import (
    MATERIAL_TOKEN_PATTERN,
    MaterialTokenNamespace,
    material_token,
    parse_material_token,
)


_REFERENCE_PAGE_HEADINGS = ("版式占位符说明", "母版占位符说明")

DocxPdfRenderer = Callable[[Path, Path], str | None]
DocxPdfRendererEntry = tuple[str, DocxPdfRenderer]
DocxPdfRendererResolver = Callable[[], DocxPdfRendererEntry | None]


@dataclass(frozen=True, slots=True)
class _ReviewPdfOutcome:
    status: str
    path: Path | None = None
    renderer: str = ""
    issue: str = ""


@dataclass(frozen=True, slots=True)
class OfficialDocumentAssemblyResult:
    status: str
    profile_id: str
    master_id: str = ""
    material_schema_ids: tuple[str, ...] = ()
    docx_path: Path | None = None
    internal_review_docx_path: Path | None = None
    archive_manifest_path: Path | None = None
    archive_manifest_markdown_path: Path | None = None
    review_pdf_path: Path | None = None
    review_pdf_status: str = "not_requested"
    review_pdf_renderer: str = ""
    review_pdf_issue: str = ""
    replaced_placeholders: tuple[str, ...] = ()
    missing_required_fields: tuple[str, ...] = ()
    unresolved_placeholders: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def output_paths(self) -> dict[str, str]:
        paths: dict[str, str] = {}
        if self.docx_path is not None:
            paths["official_docx"] = str(self.docx_path)
        if self.internal_review_docx_path is not None:
            paths["internal_review_docx"] = str(self.internal_review_docx_path)
        if self.archive_manifest_path is not None:
            paths["archive_manifest"] = str(self.archive_manifest_path)
        if self.archive_manifest_markdown_path is not None:
            paths["archive_manifest_md"] = str(self.archive_manifest_markdown_path)
        if (
            self.review_pdf_status == "generated"
            and self.review_pdf_path is not None
            and self.review_pdf_path.is_file()
        ):
            paths["review_pdf"] = str(self.review_pdf_path)
        return paths

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "profile_id": self.profile_id,
            "master_id": self.master_id,
            "material_schema_ids": list(self.material_schema_ids),
            "docx_path": str(self.docx_path) if self.docx_path is not None else "",
            "internal_review_docx_path": (
                str(self.internal_review_docx_path)
                if self.internal_review_docx_path is not None
                else ""
            ),
            "archive_manifest_path": (
                str(self.archive_manifest_path)
                if self.archive_manifest_path is not None
                else ""
            ),
            "archive_manifest_markdown_path": (
                str(self.archive_manifest_markdown_path)
                if self.archive_manifest_markdown_path is not None
                else ""
            ),
            "review_pdf_path": str(self.review_pdf_path or ""),
            "review_pdf_status": self.review_pdf_status,
            "review_pdf_renderer": self.review_pdf_renderer,
            "review_pdf_issue": self.review_pdf_issue,
            "output_paths": self.output_paths,
            "replaced_placeholders": list(self.replaced_placeholders),
            "missing_required_fields": list(self.missing_required_fields),
            "unresolved_placeholders": list(self.unresolved_placeholders),
        }


def assemble_official_document_docx(
    profile_id: str,
    entity_data: Mapping[str, object],
    output_dir: Path | str,
    *,
    field_aliases: Mapping[str, str] | None = None,
    filename: str | None = None,
    master: MasterSpec | None = None,
    removed_field_keys: set[str] | tuple[str, ...] | list[str] = (),
    remove_reference_page: bool = True,
    generate_review_pdf: bool = False,
    review_pdf_renderer_resolver: DocxPdfRendererResolver | None = None,
) -> OfficialDocumentAssemblyResult:
    """Assemble one official-document DOCX from the registered master contract."""

    contract = get_official_document_assembly_contract(profile_id)
    normalized_profile_id = str(profile_id or "").strip()
    if contract is None:
        return OfficialDocumentAssemblyResult(
            status="unknown_profile",
            profile_id=normalized_profile_id,
            review_pdf_status=_blocked_review_pdf_status(generate_review_pdf),
        )

    master_spec = resolve_official_master_for_contract(
        contract,
        requested=master,
    )
    if master_spec is None:
        return OfficialDocumentAssemblyResult(
            status="master_not_found",
            profile_id=contract.profile_id,
            material_schema_ids=contract.material_schema_ids,
            review_pdf_status=_blocked_review_pdf_status(generate_review_pdf),
        )
    if (
        master_spec.supported_assembly_types
        and contract.profile_id not in master_spec.supported_assembly_types
    ):
        return OfficialDocumentAssemblyResult(
            status="master_incompatible",
            profile_id=contract.profile_id,
            master_id=master_spec.master_id,
            material_schema_ids=contract.material_schema_ids,
            review_pdf_status=_blocked_review_pdf_status(generate_review_pdf),
        )

    preflight = check_master_preflight(master_spec)
    if preflight.status != "ok":
        return OfficialDocumentAssemblyResult(
            status=preflight.status,
            profile_id=contract.profile_id,
            master_id=master_spec.master_id,
            material_schema_ids=contract.material_schema_ids,
            missing_required_fields=preflight.missing_required_placeholders,
            review_pdf_status=_blocked_review_pdf_status(generate_review_pdf),
        )

    missing_required = _missing_required_fields(
        contract,
        entity_data,
        removed_field_keys=removed_field_keys,
    )
    if missing_required:
        return OfficialDocumentAssemblyResult(
            status="missing_required_fields",
            profile_id=contract.profile_id,
            master_id=master_spec.master_id,
            material_schema_ids=contract.material_schema_ids,
            missing_required_fields=missing_required,
            review_pdf_status=_blocked_review_pdf_status(generate_review_pdf),
        )

    target = _target_docx_path(output_dir, filename, entity_data, contract.profile_id)
    internal_review_target = _internal_review_docx_path(target)
    archive_manifest_target = _archive_manifest_path(target)
    archive_markdown_target = _archive_manifest_markdown_path(target)
    review_pdf_target = _review_pdf_path(target)

    with TemporaryDirectory(prefix="lark-official-assembly-") as temporary:
        stage_root = Path(temporary)
        stage_target = stage_root / target.name
        stage_internal_review = stage_root / internal_review_target.name
        stage_archive_manifest = stage_root / archive_manifest_target.name
        stage_archive_markdown = stage_root / archive_markdown_target.name
        stage_review_pdf = stage_root / review_pdf_target.name

        document = Document(str(master_spec.docx_path))
        if remove_reference_page:
            _remove_placeholder_reference_page(document)
        _remove_empty_optional_paragraphs(document, contract, entity_data)
        _remove_empty_optional_table_rows(document, contract, entity_data)
        _insert_profile_specific_paragraphs(document, contract, entity_data)
        _compact_profile_specific_layout(document, contract)
        replacements = _placeholder_replacements(
            contract,
            entity_data,
            field_aliases=field_aliases,
        )
        replaced = _replace_placeholders(document, replacements)
        unresolved = _unresolved_official_placeholders(document)
        if unresolved:
            return OfficialDocumentAssemblyResult(
                status="unresolved_placeholders",
                profile_id=contract.profile_id,
                master_id=master_spec.master_id,
                material_schema_ids=contract.material_schema_ids,
                review_pdf_status=_blocked_review_pdf_status(generate_review_pdf),
                replaced_placeholders=replaced,
                unresolved_placeholders=unresolved,
            )

        document.save(str(stage_target))
        _insert_internal_review_notice(document)
        document.save(str(stage_internal_review))
        review_pdf_outcome = _ReviewPdfOutcome(status="not_requested")
        if generate_review_pdf:
            review_pdf_outcome = _render_optional_review_pdf(
                stage_internal_review,
                stage_review_pdf,
                renderer_resolver=review_pdf_renderer_resolver,
            )
        published_review_pdf = (
            review_pdf_target
            if review_pdf_outcome.status == "generated"
            and review_pdf_outcome.path is not None
            else None
        )
        _write_archive_manifests(
            stage_archive_manifest,
            stage_archive_markdown,
            contract,
            master_spec,
            entity_data,
            formal_docx_path=target,
            internal_review_docx_path=internal_review_target,
            published_archive_manifest_path=archive_manifest_target,
            published_archive_manifest_markdown_path=archive_markdown_target,
            review_pdf_path=published_review_pdf,
            review_pdf_status=review_pdf_outcome.status,
            review_pdf_renderer=review_pdf_outcome.renderer,
            review_pdf_issue=review_pdf_outcome.issue,
            replaced_placeholders=replaced,
        )
        staged_artifacts = [
            StagedArtifact("official_docx", stage_target, target),
            StagedArtifact(
                "internal_review_docx",
                stage_internal_review,
                internal_review_target,
            ),
            StagedArtifact(
                "archive_manifest",
                stage_archive_manifest,
                archive_manifest_target,
            ),
            StagedArtifact(
                "archive_manifest_md",
                stage_archive_markdown,
                archive_markdown_target,
            ),
        ]
        if published_review_pdf is not None:
            staged_artifacts.append(
                StagedArtifact("review_pdf", stage_review_pdf, review_pdf_target)
            )
        publish_staged_artifacts(
            staged_artifacts,
            execution_id=f"official-assembly-{uuid4().hex}",
        )

    return OfficialDocumentAssemblyResult(
        status="ok",
        profile_id=contract.profile_id,
        master_id=master_spec.master_id,
        material_schema_ids=contract.material_schema_ids,
        docx_path=target,
        internal_review_docx_path=internal_review_target,
        archive_manifest_path=archive_manifest_target,
        archive_manifest_markdown_path=archive_markdown_target,
        review_pdf_path=published_review_pdf,
        review_pdf_status=review_pdf_outcome.status,
        review_pdf_renderer=review_pdf_outcome.renderer,
        review_pdf_issue=review_pdf_outcome.issue,
        replaced_placeholders=replaced,
        unresolved_placeholders=(),
    )


def _missing_required_fields(
    contract: OfficialDocumentAssemblyContract,
    entity_data: Mapping[str, object],
    *,
    removed_field_keys: set[str] | tuple[str, ...] | list[str] = (),
) -> tuple[str, ...]:
    values = entity_data if isinstance(entity_data, Mapping) else {}
    removed = {str(key) for key in removed_field_keys}
    missing: list[str] = []
    for binding in contract.field_bindings:
        if not binding.required or binding.field_key in removed:
            continue
        value = values.get(binding.field_key, "")
        if str(value or "").strip():
            continue
        missing.append(binding.field_key)
    return tuple(dict.fromkeys(missing))


def _placeholder_replacements(
    contract: OfficialDocumentAssemblyContract,
    entity_data: Mapping[str, object],
    *,
    field_aliases: Mapping[str, str] | None = None,
) -> dict[str, str]:
    values = entity_data if isinstance(entity_data, Mapping) else {}
    replacements: dict[str, str] = {}
    for binding in contract.field_bindings:
        token = material_token(MaterialTokenNamespace.TEXT, binding.placeholder_id)
        value = (
            str(values.get(binding.field_key, "") or "")
            if binding.applicable
            else ""
        )
        replacements[token] = value
        label = official_material_field_label(binding.field_key)
        if label:
            replacements[material_token(MaterialTokenNamespace.TEXT, label)] = value
            replacements[material_token(MaterialTokenNamespace.TEXT, label + "1")] = value
    for raw_key, raw_value in values.items():
        key = str(raw_key or "").strip()
        if key:
            replacements.setdefault(
                material_token(MaterialTokenNamespace.TEXT, key),
                str(raw_value or ""),
            )
    for raw_alias, raw_field_key in dict(field_aliases or {}).items():
        alias = str(raw_alias or "").strip()
        field_key = str(raw_field_key or "").strip()
        if alias and field_key in values:
            replacements[
                material_token(MaterialTokenNamespace.TEXT, alias)
            ] = str(values.get(field_key, "") or "")
    return replacements


def _remove_empty_optional_paragraphs(
    document,
    contract: OfficialDocumentAssemblyContract,
    entity_data: Mapping[str, object],
) -> None:
    values = entity_data if isinstance(entity_data, Mapping) else {}
    preserve_blank_layout_tokens = {
        "{{@text:official_security_level}}",
        "{{@text:official_urgency}}",
    }
    empty_tokens = {
        material_token(MaterialTokenNamespace.TEXT, binding.placeholder_id)
        for binding in contract.field_bindings
        if not binding.required
        and (
            not binding.applicable
            or not str(values.get(binding.field_key, "") or "").strip()
        )
        and material_token(
            MaterialTokenNamespace.TEXT,
            binding.placeholder_id,
        ) not in preserve_blank_layout_tokens
    }
    if not empty_tokens:
        return
    for paragraph in list(document.paragraphs):
        text = get_full_text(paragraph)
        if not any(token in text for token in empty_tokens):
            continue
        parent = paragraph._p.getparent()
        if parent is not None:
            parent.remove(paragraph._p)


def _remove_empty_optional_table_rows(
    document,
    contract: OfficialDocumentAssemblyContract,
    entity_data: Mapping[str, object],
) -> None:
    values = entity_data if isinstance(entity_data, Mapping) else {}
    empty_tokens = {
        material_token(MaterialTokenNamespace.TEXT, binding.placeholder_id)
        for binding in contract.field_bindings
        if not binding.required
        and (
            not binding.applicable
            or not str(values.get(binding.field_key, "") or "").strip()
        )
    }
    if not empty_tokens:
        return
    for table in list(document.tables):
        for row in list(table.rows):
            text = "\n".join(cell.text for cell in row.cells)
            if not any(token in text for token in empty_tokens):
                continue
            # Metadata rows containing another non-empty/applicable placeholder
            # must survive. Imprint rows contain exactly one value placeholder.
            row_tokens = set(_official_placeholder_ids(text))
            if any(
                material_token(MaterialTokenNamespace.TEXT, token) not in empty_tokens
                for token in row_tokens
            ):
                continue
            parent = row._tr.getparent()
            if parent is not None:
                parent.remove(row._tr)


def _insert_profile_specific_paragraphs(
    document,
    contract: OfficialDocumentAssemblyContract,
    entity_data: Mapping[str, object],
) -> None:
    if contract.profile_id != "minutes":
        return
    existing_text = "\n".join(
        get_full_text(paragraph) for paragraph in _iter_all_paragraphs(document)
    )
    if (
        "{{@text:official_meeting_time}}" in existing_text
        or "{{@text:official_meeting_attendees}}" in existing_text
    ):
        return
    body_paragraph = next(
        (
            paragraph
            for paragraph in document.paragraphs
            if "{{@text:official_body}}" in get_full_text(paragraph)
        ),
        None,
    )
    if body_paragraph is None:
        return

    values = entity_data if isinstance(entity_data, Mapping) else {}
    rows = (
        ("meeting_date", "会议时间", "official_meeting_time"),
        ("participants", "参会人员", "official_meeting_attendees"),
    )
    for field_key, label, placeholder_id in rows:
        if not str(values.get(field_key, "") or "").strip():
            continue
        paragraph = body_paragraph.insert_paragraph_before(
            f"{label}："
            + material_token(MaterialTokenNamespace.TEXT, placeholder_id),
            style=body_paragraph.style,
        )
        paragraph.paragraph_format.first_line_indent = (
            body_paragraph.paragraph_format.first_line_indent
        )


def _compact_profile_specific_layout(
    document,
    contract: OfficialDocumentAssemblyContract,
) -> None:
    """Keep compact official documents from creating a trailing page.

    The master intentionally leaves a spacer immediately before the printing
    table.  Word can use that spacer to push the last table row (or only the
    end-of-document marker) onto a second page for request and approval
    documents.  Removing the empty spacer preserves the visible hierarchy and
    keeps these short, single-page documents stable across Word renderers.
    """

    if contract.profile_id not in {"minutes", "request", "approval"} or not document.tables:
        return
    printing_table = next(
        (
            table._tbl
            for table in document.tables
            if "official_printing_" in "\n".join(
                cell.text for row in table.rows for cell in row.cells
            )
        ),
        None,
    )
    if printing_table is None:
        return
    preceding = printing_table.getprevious()
    if (
        preceding is not None
        and preceding.tag.endswith("p")
        and not "".join(preceding.itertext()).strip()
        and not preceding.xpath(".//w:sectPr")
    ):
        preceding.getparent().remove(preceding)

    # Request documents commonly include an attachment line.  The master also
    # leaves a blank paragraph between that line and the issuer block; together
    # they can leave too little room for Word's end-of-document marker even
    # when the whole printing table is visibly on page one.
    if contract.profile_id != "request":
        return
    issue_date = printing_table.getprevious()
    issuer = issue_date.getprevious() if issue_date is not None else None
    request_spacer = issuer.getprevious() if issuer is not None else None
    if (
        request_spacer is not None
        and request_spacer.tag.endswith("p")
        and not "".join(request_spacer.itertext()).strip()
        and not request_spacer.xpath(".//w:sectPr")
    ):
        request_spacer.getparent().remove(request_spacer)


def _replace_placeholders(document, replacements: Mapping[str, str]) -> tuple[str, ...]:
    replaced: set[str] = set()
    for token, value in replacements.items():
        count = 0
        for paragraph in _iter_all_paragraphs(document):
            if token not in get_full_text(paragraph):
                continue
            count += replace_run_text(paragraph, token, value)
        fixed_layout_result = replace_fixed_layout_placeholders(document, {token: value})
        count += fixed_layout_result.total_replacements
        if count:
            replaced.add(_placeholder_id(token))
    return tuple(sorted(replaced))


def _placeholder_id(token: str) -> str:
    return parse_material_token(str(token or "")).identifier


def _unresolved_official_placeholders(document) -> tuple[str, ...]:
    found: set[str] = set()
    for paragraph in _iter_all_paragraphs(document):
        found.update(_official_placeholder_ids(get_full_text(paragraph)))
    return tuple(sorted(found))


def _official_placeholder_ids(text: object) -> tuple[str, ...]:
    """Project official ``@text`` surfaces through the central token parser."""

    found: list[str] = []
    for match in MATERIAL_TOKEN_PATTERN.finditer(str(text or "")):
        try:
            ref = parse_material_token(match.group(0))
        except (TypeError, ValueError):
            continue
        if (
            ref.namespace is MaterialTokenNamespace.TEXT
            and ref.identifier.startswith("official_")
        ):
            found.append(ref.identifier)
    return tuple(found)


def _iter_all_paragraphs(container):
    for paragraph in list(getattr(container, "paragraphs", []) or []):
        yield paragraph
    for table in list(getattr(container, "tables", []) or []):
        for row in list(getattr(table, "rows", []) or []):
            for cell in list(getattr(row, "cells", []) or []):
                yield from _iter_all_paragraphs(cell)
    if hasattr(container, "sections"):
        for section in list(getattr(container, "sections", []) or []):
            yield from _iter_all_paragraphs(section.header)
            yield from _iter_all_paragraphs(section.footer)


def _target_docx_path(
    output_dir: Path | str,
    filename: str | None,
    entity_data: Mapping[str, object],
    profile_id: str,
) -> Path:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = str(filename or "").strip()
    if not target_name:
        title = str(entity_data.get("title", "") if isinstance(entity_data, Mapping) else "").strip()
        target_name = f"{_safe_stem(title or profile_id)}.docx"
    if not target_name.lower().endswith(".docx"):
        target_name = f"{target_name}.docx"
    return _available_output_path(target_dir / Path(target_name).name)


def _available_output_path(path: Path) -> Path:
    """Return a non-overwriting sibling path for one assembly artifact."""

    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{path.stem}_1000{path.suffix}")


def _internal_review_docx_path(formal_docx_path: Path) -> Path:
    return formal_docx_path.with_name(f"{formal_docx_path.stem}_internal_review.docx")


def _review_pdf_path(formal_docx_path: Path) -> Path:
    return formal_docx_path.with_name(f"{formal_docx_path.stem}_review.pdf")


def _blocked_review_pdf_status(generate_review_pdf: bool) -> str:
    return "assembly_blocked" if generate_review_pdf else "not_requested"


def _render_optional_review_pdf(
    source_docx_path: Path,
    target_pdf_path: Path,
    *,
    renderer_resolver: DocxPdfRendererResolver | None = None,
) -> _ReviewPdfOutcome:
    resolver = renderer_resolver or _default_review_pdf_renderer_resolver
    try:
        renderer_entry = resolver()
    except Exception as exc:
        return _ReviewPdfOutcome(
            status="renderer_unavailable",
            issue=f"renderer_resolution_failed: {exc}",
        )
    if renderer_entry is None:
        return _ReviewPdfOutcome(
            status="renderer_unavailable",
            issue="docx_to_pdf_renderer_unavailable",
        )

    renderer_name, renderer = renderer_entry
    try:
        renderer(source_docx_path, target_pdf_path)
    except Exception as exc:
        _remove_partial_review_pdf(target_pdf_path)
        return _ReviewPdfOutcome(
            status="render_failed",
            renderer=str(renderer_name or ""),
            issue=f"review_pdf_render_failed: {exc}",
        )
    if not target_pdf_path.is_file() or target_pdf_path.stat().st_size <= 0:
        _remove_partial_review_pdf(target_pdf_path)
        return _ReviewPdfOutcome(
            status="output_missing",
            renderer=str(renderer_name or ""),
            issue="review_pdf_missing_after_render",
        )
    return _ReviewPdfOutcome(
        status="generated",
        path=target_pdf_path,
        renderer=str(renderer_name or ""),
    )


def _default_review_pdf_renderer_resolver() -> DocxPdfRendererEntry | None:
    from src.shared.engine.docx_page_renderer import (
        available_docx_pdf_renderer,
    )

    return available_docx_pdf_renderer()


def _remove_partial_review_pdf(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        return


def _archive_manifest_path(formal_docx_path: Path) -> Path:
    return formal_docx_path.with_name(f"{formal_docx_path.stem}_archive_manifest.json")


def _archive_manifest_markdown_path(formal_docx_path: Path) -> Path:
    return formal_docx_path.with_name(f"{formal_docx_path.stem}_archive_manifest.md")


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    return cleaned or "official_document"


def _insert_internal_review_notice(document) -> None:
    paragraph = document.add_paragraph(
        "内部审阅稿：仅供内部流转和格式核验，不代表正式签发、盖章或归档审批有效。"
    )
    body = document._body._element
    body.remove(paragraph._p)
    body.insert(0, paragraph._p)


def _write_archive_manifests(
    json_path: Path,
    markdown_path: Path,
    contract: OfficialDocumentAssemblyContract,
    master: MasterSpec,
    entity_data: Mapping[str, object],
    *,
    formal_docx_path: Path,
    internal_review_docx_path: Path,
    published_archive_manifest_path: Path,
    published_archive_manifest_markdown_path: Path,
    review_pdf_path: Path | None,
    review_pdf_status: str,
    review_pdf_renderer: str,
    review_pdf_issue: str,
    replaced_placeholders: tuple[str, ...],
) -> None:
    profile = get_official_document_profile(contract.profile_id)
    values = entity_data if isinstance(entity_data, Mapping) else {}
    output_paths = {
        "official_docx": str(formal_docx_path),
        "internal_review_docx": str(internal_review_docx_path),
        "archive_manifest": str(published_archive_manifest_path or json_path),
        "archive_manifest_md": str(
            published_archive_manifest_markdown_path or markdown_path
        ),
    }
    if review_pdf_path is not None and review_pdf_status == "generated":
        output_paths["review_pdf"] = str(review_pdf_path)
    archive_fields = {
        key: str(values.get(key, "") or "")
        for key in (
            "title",
            "document_no",
            "organization",
            "issue_date",
            "issuer",
            "recipient",
            "security_level",
            "urgency",
            "copy_scope",
            "printing_org",
            "printing_date",
            "archive_status",
            "archive_no",
            "retention_period",
        )
    }
    payload = {
        "status": "ok",
        "profile_id": contract.profile_id,
        "profile_label": getattr(profile, "label", "") if profile is not None else "",
        "master_id": master.master_id,
        "material_schema_ids": list(contract.material_schema_ids),
        "delivery_versions": list(contract.delivery_versions),
        "output_paths": output_paths,
        "review_pdf": {
            "status": review_pdf_status,
            "path": str(review_pdf_path or ""),
            "renderer": review_pdf_renderer,
            "issue": review_pdf_issue,
        },
        "archive_fields": archive_fields,
        "replaced_placeholders": list(replaced_placeholders),
        "boundaries": [
            *list(contract.boundaries),
            "system-generated archive manifest is evidence only",
            "does not certify official release validity",
            "does not verify seal legality",
            "does not replace archive-office approval",
        ],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(_archive_manifest_markdown(payload), encoding="utf-8")


def _archive_manifest_markdown(payload: Mapping[str, object]) -> str:
    archive_fields = payload.get("archive_fields", {})
    if not isinstance(archive_fields, Mapping):
        archive_fields = {}
    output_paths = payload.get("output_paths", {})
    if not isinstance(output_paths, Mapping):
        output_paths = {}
    boundaries = [
        str(item or "").strip()
        for item in list(payload.get("boundaries", []) or [])
        if str(item or "").strip()
    ]
    lines = [
        "# 公文归档清单",
        "",
        f"- 文种: {payload.get('profile_label') or payload.get('profile_id') or '-'}",
        f"- 标题: {archive_fields.get('title') or '-'}",
        f"- 文号: {archive_fields.get('document_no') or '-'}",
        f"- 发文机关: {archive_fields.get('organization') or '-'}",
        f"- 成文日期: {archive_fields.get('issue_date') or '-'}",
        f"- 归档号: {archive_fields.get('archive_no') or '-'}",
        f"- 保管期限: {archive_fields.get('retention_period') or '-'}",
        "",
        "## 交付产物",
        "",
    ]
    for key, value in output_paths.items():
        lines.append(f"- {key}: `{value}`")
    if boundaries:
        lines.extend(["", "## 边界说明", ""])
        lines.extend(f"- {item}" for item in boundaries[:8])
    lines.append("")
    return "\n".join(lines)


def _remove_placeholder_reference_page(document) -> None:
    body = document._body._element
    heading_element = None
    for paragraph in document.paragraphs:
        if str(paragraph.text or "").strip() in _REFERENCE_PAGE_HEADINGS:
            heading_element = paragraph._p
            break
    if heading_element is None:
        return

    children = list(body)
    try:
        start_index = children.index(heading_element)
    except ValueError:
        return

    # ``Document.add_section(WD_SECTION.NEW_PAGE)`` stores the section break on
    # the empty paragraph immediately before the reference-page heading.  If
    # that paragraph survives, Word renders an empty trailing page even after
    # the reference-page content has been removed.
    if start_index > 0:
        preceding = children[start_index - 1]
        if (
            preceding.tag.endswith("p")
            and preceding.xpath(".//w:sectPr")
            and not "".join(preceding.itertext()).strip()
        ):
            body.remove(preceding)
            start_index -= 1

    for child in list(body)[start_index:]:
        if child.tag.endswith("sectPr"):
            continue
        body.remove(child)


__all__ = [
    "OfficialDocumentAssemblyResult",
    "assemble_official_document_docx",
]
