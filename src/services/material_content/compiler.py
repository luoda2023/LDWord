"""Single capture -> normalize -> publish entry point for content materials."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Callable

from src.config.content_artifacts import (
    CONTENT_COMPILER_CONTRACT,
    CONTENT_IR_CONTRACT,
)
from src.services.material_content.artifact_repository import (
    ArtifactResourcePayload,
    ContentArtifactPublishCancelled,
    ContentArtifactRepository,
    ContentArtifactRepositoryError,
)
from src.services.material_content.import_contract import (
    ContentCompileReceipt,
    ContentCompileResult,
    ContentImportDisposition,
    ContentImportFinding,
    ContentSemanticInventory,
)
from src.services.material_content.markdown_importer import MarkdownImportError
from src.services.material_content.markdown_normalizer import (
    decode_markdown_source,
    inspect_markdown_raster,
    markdown_resource_paths,
    normalize_markdown_content,
)
from src.services.material_content.semantic_inventory import (
    inventory_document_fragment,
)
from src.services.material_content.source_capture import (
    CapturedContentSource,
    ContentSourceCaptureError,
    capture_content_resource,
    capture_content_source,
)


def compile_content_material(
    source_path: str | Path,
    repository: ContentArtifactRepository,
    *,
    cancelled: Callable[[], bool] | None = None,
) -> ContentCompileResult:
    """Compile one external path; no later stage needs that path again."""

    if not isinstance(repository, ContentArtifactRepository):
        raise TypeError("repository must be a ContentArtifactRepository")
    try:
        source = capture_content_source(source_path)
    except ContentSourceCaptureError as exc:
        return _blocked(exc.code, scope="source_capture", object_id="source")
    if source.source_format == "markdown":
        return _compile_markdown(
            Path(source_path),
            source,
            repository,
            cancelled=cancelled,
        )
    return _compile_docx(
        source,
        repository,
        cancelled=cancelled,
    )


def _compile_docx(
    source: CapturedContentSource,
    repository: ContentArtifactRepository,
    *,
    cancelled: Callable[[], bool] | None,
) -> ContentCompileResult:
    try:
        normalizer = import_module(
            "src.services.material_content.docx_normalizer"
        )
    except ModuleNotFoundError:
        return _blocked(
            "docx_compiler_not_installed",
            scope="docx",
            object_id="document",
        )
    try:
        normalization = normalizer.normalize_docx_content(source.payload)
    except normalizer.DocxNormalizationError as exc:
        return ContentCompileResult(
            findings=exc.findings,
            inventory=ContentSemanticInventory.empty(),
        )
    inventory = inventory_document_fragment(normalization.fragment)
    receipt = ContentCompileReceipt(
        compiler_contract=CONTENT_COMPILER_CONTRACT,
        parser_contract=CONTENT_IR_CONTRACT,
        source_sha256=source.sha256,
        inventory=inventory,
        findings=normalization.findings,
    )
    try:
        artifact_ref = repository.publish(
            source,
            normalization.fragment,
            receipt,
            normalization.resources,
            cancelled=cancelled,
        )
    except ContentArtifactPublishCancelled:
        raise
    except ContentArtifactRepositoryError:
        return _blocked(
            "artifact_publish_failed",
            scope="artifact",
            object_id="artifact",
        )
    return ContentCompileResult(
        artifact_ref=artifact_ref,
        fragment=normalization.fragment,
        receipt=receipt,
        findings=normalization.findings,
        inventory=inventory,
    )


def _compile_markdown(
    source_path: Path,
    source: CapturedContentSource,
    repository: ContentArtifactRepository,
    *,
    cancelled: Callable[[], bool] | None,
) -> ContentCompileResult:
    try:
        text = decode_markdown_source(source.payload)
        relative_paths = markdown_resource_paths(text)
    except MarkdownImportError as exc:
        return _blocked_markdown(exc)

    source_root = source_path.expanduser().resolve().parent
    resource_ids: dict[str, str] = {}
    resources: list[ArtifactResourcePayload] = []
    for relative_path in relative_paths:
        candidate = (source_root / Path(relative_path)).resolve()
        try:
            candidate.relative_to(source_root)
        except ValueError:
            return _blocked(
                "image_path_escape",
                scope="markdown_resource",
                object_id=f"resource:{relative_path}",
            )
        try:
            captured = capture_content_resource(
                candidate,
                relative_path=relative_path,
            )
            raster = inspect_markdown_raster(
                captured.payload,
                relative_path=relative_path,
            )
        except ContentSourceCaptureError as exc:
            return _blocked(
                exc.code,
                scope="markdown_resource",
                object_id=f"resource:{relative_path}",
            )
        except MarkdownImportError as exc:
            return _blocked_markdown(
                exc,
                scope="markdown_resource",
                object_id=f"resource:{relative_path}",
            )
        resource = ArtifactResourcePayload.from_bytes(
            captured.payload,
            media_type=raster.media_type,
            suffix=raster.canonical_suffix,
        )
        resource_ids[relative_path] = resource.resource_id
        resources.append(resource)

    try:
        normalization = normalize_markdown_content(
            text,
            source_identity=source.sha256,
            resource_id_by_path=resource_ids,
        )
    except MarkdownImportError as exc:
        return _blocked_markdown(exc)
    inventory = inventory_document_fragment(normalization.fragment)
    receipt = ContentCompileReceipt(
        compiler_contract=CONTENT_COMPILER_CONTRACT,
        parser_contract=CONTENT_IR_CONTRACT,
        source_sha256=source.sha256,
        inventory=inventory,
        findings=normalization.findings,
    )
    try:
        artifact_ref = repository.publish(
            source,
            normalization.fragment,
            receipt,
            tuple(resources),
            cancelled=cancelled,
        )
    except ContentArtifactPublishCancelled:
        raise
    except ContentArtifactRepositoryError:
        return _blocked(
            "artifact_publish_failed",
            scope="artifact",
            object_id="artifact",
        )
    return ContentCompileResult(
        artifact_ref=artifact_ref,
        fragment=normalization.fragment,
        receipt=receipt,
        findings=normalization.findings,
        inventory=inventory,
    )


def _blocked_markdown(
    error: MarkdownImportError,
    *,
    scope: str = "markdown",
    object_id: str = "document",
) -> ContentCompileResult:
    diagnostic = error.diagnostic
    stable_object_id = object_id
    if diagnostic.line is not None and object_id == "document":
        stable_object_id = f"line:{diagnostic.line}"
    return _blocked(diagnostic.code, scope=scope, object_id=stable_object_id)


def _blocked(code: str, *, scope: str, object_id: str) -> ContentCompileResult:
    normalized_code = str(code or "content_compile_failed").strip()
    finding = ContentImportFinding(
        code=normalized_code,
        disposition=ContentImportDisposition.BLOCKER,
        scope=scope,
        object_id=object_id,
        message_key=f"content.{normalized_code}",
        user_message=_user_message(normalized_code),
    )
    return ContentCompileResult(
        findings=(finding,),
        inventory=ContentSemanticInventory.empty(),
    )


def _user_message(code: str) -> str:
    messages = {
        "source_missing": "文件不存在，请重新选择。",
        "source_not_file": "所选路径不是文件。",
        "source_too_large": "文件超出可导入大小限制。",
        "source_not_stable": "文件仍在生成或变化，请稍后重试。",
        "source_encoding_invalid": "Markdown 文件必须使用 UTF-8 编码。",
        "resource_missing": "Markdown 引用的图片不存在。",
        "resource_not_file": "Markdown 引用的图片路径不是文件。",
        "resource_too_large": "Markdown 引用的图片超出大小限制。",
        "resource_not_stable": "Markdown 引用的图片仍在变化，请稍后重试。",
        "resource_not_raster": "Markdown 引用的图片无法安全读取。",
        "resource_raster_format_unsupported": "Markdown 引用了暂不支持的图片格式。",
        "resource_extension_mismatch": "图片扩展名与实际格式不一致。",
        "image_path_escape": "Markdown 图片路径超出了文件所在目录。",
        "raw_html_unsupported": "Markdown 中包含暂不支持的原始 HTML。",
        "docx_compiler_not_ready": "DOCX 编译链尚未完成切换。",
        "docx_compiler_not_installed": "当前版本未安装复杂 DOCX 素材导入能力。",
        "artifact_publish_failed": "文件资料制品保存失败。",
    }
    return messages.get(code, "文件资料包含暂时无法安全转换的内容。")


__all__ = ["compile_content_material"]
