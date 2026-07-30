"""Filesystem adapter that feeds all material consumers into one pure index."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable

from docx import Document

from src.config.attachment_materials import AttachmentProcessingMode
from src.config.content_materials import (
    DocumentFragment,
    HeadingBlock,
    ImageBlock,
    InlineKind,
    ListBlock,
    ParagraphBlock,
    TableBlock,
)
from src.config.library import CONFIG_LIBRARY_ROOT
from src.config.material_snapshot import MaterialSnapshot
from src.shared.engine.docx_material_tokens import extract_docx_material_token_blocks
from src.shared.engine.material_dependency_index import (
    MATERIAL_DEPENDENCY_SCANNER_CONTRACT,
    MaterialConsumerKind,
    MaterialConsumerRef,
    MaterialConsumerScan,
    MaterialDependencyIndex,
    build_material_dependency_index,
    scan_material_consumer,
)
from src.shared.engine.material_token_router import TokenTextBlock
from src.shared.engine.material_token_contract import normalize_material_token
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
)


class MaterialDependencyIndexingError(RuntimeError):
    """A declared source could not be read into dependency facts."""


@dataclass(frozen=True, slots=True)
class MaterialDependencyIndexRequest:
    snapshot: MaterialSnapshot
    main_document_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, MaterialSnapshot):
            raise TypeError("snapshot must be a MaterialSnapshot")
        if not isinstance(self.main_document_path, str) or not self.main_document_path.strip():
            raise ValueError("main_document_path must not be empty")


class MaterialDependencyIndexer:
    """Read source documents; classification and aggregation stay pure."""

    def __init__(
        self,
        document_loader: Callable[[str], object] = Document,
        content_repository: ContentArtifactRepository | None = None,
    ) -> None:
        if not callable(document_loader):
            raise TypeError("document_loader must be callable")
        self._document_loader = document_loader
        self._content_repository = content_repository or ContentArtifactRepository(
            CONFIG_LIBRARY_ROOT / "content_artifacts"
        )

    def build(self, request: MaterialDependencyIndexRequest) -> MaterialDependencyIndex:
        if not isinstance(request, MaterialDependencyIndexRequest):
            raise TypeError("request must be a MaterialDependencyIndexRequest")
        snapshot = request.snapshot
        scans: list[MaterialConsumerScan] = []
        revisions: dict[str, str] = {}

        main_path = Path(request.main_document_path).expanduser().resolve(strict=False)
        main_consumer = MaterialConsumerRef(
            MaterialConsumerKind.MAIN_DOCUMENT,
            "source-docx",
        )
        scans.append(
            self._scan_docx(
                main_consumer,
                main_path,
                snapshot=snapshot,
                content_replacement_enabled=True,
                attachment_replacement_enabled=True,
                material_replacement_enabled=True,
            )
        )
        revisions[main_consumer.consumer_id] = _sha256_file(main_path)

        for binding in snapshot.content_bindings:
            consumer = MaterialConsumerRef(
                MaterialConsumerKind.CONTENT_SOURCE,
                binding.content_id,
            )
            fragment = self._content_repository.load_fragment(binding.artifact_ref)
            scan = scan_material_consumer(
                consumer,
                _fragment_token_blocks(fragment, binding.content_id),
                image_rules=snapshot.frozen_image_rules,
                content_rules=snapshot.content_rules,
                attachment_bindings=snapshot.attachment_bindings,
                declaration_scope="present",
                content_replacement_enabled=False,
            )
            scans.append(scan)
            revisions[consumer.consumer_id] = binding.artifact_ref.artifact_id

        for binding in snapshot.attachment_bindings:
            processing_enabled = (
                binding.processing_mode is AttachmentProcessingMode.SUBSTITUTE_COPY
            )
            for item in binding.items:
                consumer = MaterialConsumerRef(
                    MaterialConsumerKind.ATTACHMENT_ITEM,
                    binding.role,
                    item.item_id,
                )
                revisions[consumer.consumer_id] = item.file_ref.content_sha256
                if Path(item.relative_path).suffix.casefold() != ".docx":
                    continue
                scans.append(
                    self._scan_docx(
                        consumer,
                        Path(item.file_ref.source_path),
                        snapshot=snapshot,
                        content_replacement_enabled=False,
                        material_replacement_enabled=processing_enabled,
                    )
                )

        return build_material_dependency_index(
            scans,
            field_values=snapshot.field_values,
            field_token_bindings=snapshot.field_token_bindings,
            image_rules=snapshot.frozen_image_rules,
            image_source_bindings=snapshot.image_source_bindings,
            attachment_bindings=snapshot.attachment_bindings,
            source_revisions=revisions,
            declaration_revision=_declaration_revision(snapshot),
        )

    def _scan_docx(
        self,
        consumer: MaterialConsumerRef,
        path: Path,
        *,
        snapshot: MaterialSnapshot,
        content_replacement_enabled: bool,
        attachment_replacement_enabled: bool = False,
        material_replacement_enabled: bool,
    ) -> MaterialConsumerScan:
        try:
            document = self._document_loader(str(path))
            blocks = extract_docx_material_token_blocks(document).blocks
        except Exception as exc:
            raise MaterialDependencyIndexingError(
                f"docx_dependency_source_unreadable:{consumer.consumer_id}:{path}"
            ) from exc
        return scan_material_consumer(
            consumer,
            blocks,
            image_rules=snapshot.frozen_image_rules,
            content_rules=snapshot.content_rules,
            attachment_bindings=snapshot.attachment_bindings,
            declaration_scope="present",
            content_replacement_enabled=content_replacement_enabled,
            attachment_replacement_enabled=attachment_replacement_enabled,
            material_replacement_enabled=material_replacement_enabled,
        )


def build_material_dependency_index_from_sources(
    request: MaterialDependencyIndexRequest,
) -> MaterialDependencyIndex:
    return MaterialDependencyIndexer().build(request)


def _fragment_token_blocks(
    fragment: DocumentFragment,
    content_id: str,
) -> tuple[TokenTextBlock, ...]:
    output: list[TokenTextBlock] = []

    def inline_text(inlines) -> str:
        values: list[str] = []
        for inline in inlines:
            if inline.kind is InlineKind.FIELD_TOKEN:
                values.append(normalize_material_token(inline.field_key))
            elif inline.kind is InlineKind.TAB:
                values.append("\t")
            elif inline.kind in {InlineKind.SOFT_BREAK, InlineKind.HARD_BREAK}:
                values.append("\n")
            else:
                values.append(inline.text)
        return "".join(values)

    def visit(block, identity: str) -> None:
        if isinstance(block, (HeadingBlock, ParagraphBlock)):
            output.append(
                TokenTextBlock(
                    block_id=identity,
                    text=inline_text(block.inlines),
                    surface="body",
                    story_id=f"content:{content_id}",
                )
            )
        elif isinstance(block, ListBlock):
            for index, item in enumerate(block.items):
                output.append(
                    TokenTextBlock(
                        block_id=f"{identity}:item:{index}",
                        text=inline_text(item.inlines),
                        surface="body",
                        story_id=f"content:{content_id}",
                    )
                )
        elif isinstance(block, TableBlock):
            for row_index, row in enumerate(block.rows):
                for cell_index, cell in enumerate(row.cells):
                    for child_index, child in enumerate(cell.blocks):
                        visit(
                            child,
                            f"{identity}:cell:{row_index}:{cell_index}:{child_index}",
                        )
        elif isinstance(block, ImageBlock):
            return

    for index, block in enumerate(fragment.blocks):
        visit(block, f"block:{index}")
    return tuple(output)


def _declaration_revision(snapshot: MaterialSnapshot) -> str:
    payload = {
        "scanner_contract": MATERIAL_DEPENDENCY_SCANNER_CONTRACT,
        "field_token_bindings": dict(snapshot.field_token_bindings),
        "image_rules": [item.to_dict() for item in snapshot.frozen_image_rules],
        "content_rules": [item.to_dict() for item in snapshot.content_rules],
        "attachment_tokens": [
            {
                "role": item.role,
                "anchor_token": item.anchor_token,
                "render_mode": item.render_mode.value,
            }
            for item in snapshot.attachment_bindings
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        digest = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        raise MaterialDependencyIndexingError(
            f"dependency_source_unreadable:{path}"
        ) from exc


__all__ = [
    "MaterialDependencyIndexer",
    "MaterialDependencyIndexingError",
    "MaterialDependencyIndexRequest",
    "build_material_dependency_index_from_sources",
]
