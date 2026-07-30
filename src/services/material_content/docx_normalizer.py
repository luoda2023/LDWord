"""Scope-aware DOCX normalization into content IR and typed findings."""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.config.content_materials import DocumentFragment
from src.services.material_content.artifact_repository import ArtifactResourcePayload
from src.services.material_content.docx_importer import (
    DocxContentImportError,
    DocxImportDiagnostic,
    DocxImportDiagnosticCode,
    import_docx_package,
)
from src.shared.io.safe_docx_package import (
    DocxPackageError,
    SafeDocxPackage,
)
from src.services.material_content.import_contract import (
    ContentImportDisposition,
    ContentImportFinding,
    aggregate_content_findings,
)


_RELATIONSHIP_ID_RE = re.compile(r"@Id=['\"]([^'\"]+)['\"]")
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_V_NS = "urn:schemas-microsoft-com:vml"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_MAX_OBJECT_FINDINGS = 100

_DIAGNOSTIC_OBJECT_LABELS = {
    "invalid_package": "损坏的 DOCX 文件包",
    "invalid_package_path": "不安全的 DOCX 包内路径",
    "duplicate_package_part": "重复的 DOCX 包内文件",
    "missing_part": "缺失的 DOCX 必需组成部分",
    "malformed_xml": "损坏的 DOCX XML 内容",
    "dangling_relationship": "失效的文档关系",
    "orphan_relationship": "未使用的文档关系",
    "orphan_resource": "未匹配的媒体资源",
    "disallowed_external_relationship": "不允许的外部链接",
    "external_image": "外链图片",
    "header_footer_content": "页眉或页脚内容",
    "complex_section": "多栏或复杂分节",
    "floating_image": "浮动图片",
    "text_box": "文本框",
    "shape": "形状或组合图形",
    "smart_art": "SmartArt",
    "chart": "图表",
    "ole_object": "嵌入对象",
    "macro": "宏",
    "active_x": "ActiveX 控件",
    "revision": "无法确定最终结果的修订",
    "comment": "批注对象",
    "hidden_text": "隐藏文字",
    "content_control": "无法解包的内容控件",
    "word_field": "没有可见缓存结果的 Word 域",
    "footnote_endnote": "脚注或尾注",
    "internal_bookmark_link": "内部书签链接",
    "omml": "公式",
    "alt_chunk": "外部内容块",
    "vml": "旧版 VML 图形",
    "alternate_content": "无法解析的 Office 兼容块",
    "subdocument": "子文档",
    "unsupported_body_object": "不支持的正文块",
    "unsupported_inline": "不支持的行内内容",
    "unsupported_break": "不支持的换行或分页",
    "unsupported_content_token": "不支持的资料 Token",
    "unsupported_list_format": "不支持的列表编号",
    "list_nesting_too_deep": "超过九层的列表",
    "ordered_list_start": "无效的列表起始编号",
    "complex_numbering": "复杂编号",
    "mixed_image_paragraph": "标题或列表项中的图片",
    "multiple_inline_images": "段落内多图对象",
    "invalid_image": "无效图片",
    "unsupported_image_type": "不支持格式的图片",
    "image_media_type_mismatch": "媒体类型不一致的图片",
    "nested_table": "嵌套表格",
    "merged_table_cell": "无法解析的合并表格",
    "non_rectangular_table": "结构不规则的表格",
    "unsupported_table_cell": "不支持的表格单元格内容",
}

_FORBIDDEN_OBJECT_CODES = {
    "macro",
    "active_x",
    "ole_object",
    "disallowed_external_relationship",
    "external_image",
}

_UNLABELED_DIAGNOSTIC_CODES = {
    item.value for item in DocxImportDiagnosticCode
} - set(_DIAGNOSTIC_OBJECT_LABELS)
if _UNLABELED_DIAGNOSTIC_CODES:
    raise RuntimeError(
        "DOCX diagnostic object labels are incomplete: "
        + ", ".join(sorted(_UNLABELED_DIAGNOSTIC_CODES))
    )


class DocxNormalizationError(ValueError):
    def __init__(self, findings: tuple[ContentImportFinding, ...]) -> None:
        self.findings = aggregate_content_findings(findings)
        super().__init__("DOCX normalization was blocked")


@dataclass(frozen=True, slots=True)
class DocxNormalization:
    fragment: DocumentFragment
    resources: tuple[ArtifactResourcePayload, ...]
    findings: tuple[ContentImportFinding, ...] = ()


def normalize_docx_content(payload: bytes) -> DocxNormalization:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    try:
        package = SafeDocxPackage.open(payload)
    except DocxPackageError as exc:
        raise DocxNormalizationError((_package_finding(exc),)) from exc
    ignored = _scope_findings(package)
    try:
        imported = import_docx_package(package)
    except DocxContentImportError as exc:
        findings = aggregate_content_findings(
            tuple(_diagnostic_finding(item) for item in exc.diagnostics)
        )
        if len(findings) > _MAX_OBJECT_FINDINGS:
            retained_count = _MAX_OBJECT_FINDINGS - 1
            omitted_count = len(findings) - retained_count
            findings = findings[:retained_count] + (
                ContentImportFinding(
                    code="diagnostic_limit_exceeded",
                    disposition=ContentImportDisposition.BLOCKER,
                    scope="summary",
                    object_id="diagnostic-overflow",
                    message_key="content.docx.diagnostic_limit_exceeded",
                    user_message=(
                        f"另有 {omitted_count} 个暂不支持的对象未展开。"
                    ),
                    count=omitted_count,
                ),
            )
        raise DocxNormalizationError(findings) from exc
    resources = tuple(
        ArtifactResourcePayload(
            item.resource_id,
            item.media_type,
            item.payload,
        )
        for item in imported.resources
    )
    normalized = tuple(
        ContentImportFinding(
            code=code,
            disposition=ContentImportDisposition.NORMALIZED,
            scope="main_body",
            object_id=f"normalization:{code}",
            message_key=f"content.docx.{code}",
            user_message=_normalization_message(code),
            count=count,
        )
        for code, count in imported.normalized_counts
    )
    return DocxNormalization(
        fragment=imported.fragment,
        resources=resources,
        findings=aggregate_content_findings((*ignored, *normalized)),
    )


def _scope_findings(package: SafeDocxPackage) -> tuple[ContentImportFinding, ...]:
    findings: list[ContentImportFinding] = []
    for part in package.part_names:
        lowered = part.casefold()
        if lowered.startswith("word/header") or lowered.startswith("word/footer"):
            root = package.parse_xml(part)
            visible = any(
                (
                    node.tag == f"{{{_W_NS}}}t"
                    and bool((node.text or "").strip())
                )
                or node.tag
                in {
                    f"{{{_W_NS}}}tbl",
                    f"{{{_W_NS}}}drawing",
                    f"{{{_W_NS}}}pict",
                }
                for node in root.iter()
            )
            if visible:
                findings.append(
                    _ignored(
                        "header_footer_ignored",
                        "header_footer",
                        f"story:{part}",
                        "源文档页眉页脚不作为正文文件资料导入。",
                        part=part,
                    )
                )
        elif lowered.startswith("word/comments"):
            findings.append(
                _ignored(
                    "comment_metadata_ignored",
                    "comments",
                    "comments-metadata",
                    "批注元数据不作为正文文件资料导入。",
                    part=part,
                )
            )

    if package.has_part("word/settings.xml"):
        settings = package.parse_xml("word/settings.xml")
        compatibility_nodes = sum(
            1
            for node in settings.iter()
            if _namespace(node.tag) in {_V_NS, _MC_NS}
            or node.tag == f"{{{_MC_NS}}}AlternateContent"
        )
        if compatibility_nodes:
            findings.append(
                _ignored(
                    "settings_compatibility_ignored",
                    "settings",
                    "settings-compatibility",
                    "已忽略不影响正文语义的 Office/WPS 兼容设置。",
                    part="word/settings.xml",
                    count=compatibility_nodes,
                )
            )
    settings_rels = "word/_rels/settings.xml.rels"
    if package.has_part(settings_rels):
        root = package.parse_xml(settings_rels)
        attached = [
            node
            for node in root.findall(f"{{{_REL_NS}}}Relationship")
            if str(node.get("Type", "")).rstrip("/").endswith("attachedTemplate")
        ]
        if attached:
            findings.append(
                _ignored(
                    "attached_template_ignored",
                    "settings",
                    "attached-template",
                    "已忽略源文档的外部模板引用。",
                    part=settings_rels,
                    count=len(attached),
                )
            )
    if package.has_part("word/document.xml"):
        document = package.parse_xml("word/document.xml")
        sections = document.findall(f".//{{{_W_NS}}}sectPr")
        if sections:
            findings.append(
                _ignored(
                    "source_section_layout_ignored",
                    "main_body",
                    "source-section-layout",
                    "源纸张、页边距和普通分节版式由目标文档接管。",
                    part="word/document.xml",
                    count=len(sections),
                )
            )
    return tuple(findings)


def _package_finding(error: DocxPackageError) -> ContentImportFinding:
    return ContentImportFinding(
        code=error.code,
        disposition=ContentImportDisposition.BLOCKER,
        scope="package",
        object_id=f"part:{error.part}" if error.part else "package",
        message_key=f"content.docx.{error.code}",
        user_message="DOCX 文件包损坏、异常或超出安全限制。",
        technical_context=(("part", error.part[:256]),) if error.part else (),
    )


def _diagnostic_finding(diagnostic: DocxImportDiagnostic) -> ContentImportFinding:
    relationship = _RELATIONSHIP_ID_RE.search(diagnostic.path)
    if relationship:
        object_id = f"relationship:{diagnostic.part}:{relationship.group(1)}"
    else:
        object_id = _semantic_object_id(diagnostic.part, diagnostic.path)
    code = diagnostic.code.value
    return ContentImportFinding(
        code=code,
        disposition=ContentImportDisposition.BLOCKER,
        scope=_scope_for_part(diagnostic.part),
        object_id=object_id,
        cause_id=object_id,
        message_key=f"content.docx.{code}",
        user_message=_diagnostic_message(code),
        technical_context=(
            ("part", diagnostic.part[:256]),
            ("path", diagnostic.path[:512]),
        ),
    )


def _ignored(
    code: str,
    scope: str,
    object_id: str,
    message: str,
    *,
    part: str,
    count: int = 1,
) -> ContentImportFinding:
    return ContentImportFinding(
        code=code,
        disposition=ContentImportDisposition.IGNORED,
        scope=scope,
        object_id=object_id,
        message_key=f"content.docx.{code}",
        user_message=message,
        count=count,
        technical_context=(("part", part),),
    )


def _scope_for_part(part: str) -> str:
    lowered = part.casefold()
    if lowered == "word/document.xml":
        return "main_body"
    if "numbering" in lowered:
        return "numbering"
    if "styles" in lowered:
        return "styles"
    if "settings" in lowered:
        return "settings"
    if "header" in lowered or "footer" in lowered:
        return "header_footer"
    if "media" in lowered:
        return "media"
    if lowered.endswith(".rels"):
        return "relationships"
    return "package"


def _diagnostic_message(code: str) -> str:
    normalized_code = str(code or "").strip()
    label = _DIAGNOSTIC_OBJECT_LABELS.get(
        normalized_code,
        f"未识别对象（诊断代码：{normalized_code or 'unknown'}）",
    )
    action = "禁止导入" if normalized_code in _FORBIDDEN_OBJECT_CODES else "暂不支持"
    return f"DOCX 中有 1 个{action}的对象：{label}。"


def _normalization_message(code: str) -> str:
    messages = {
        "revision_final_view": "已按最终可见结果处理修订内容。",
        "revision_metadata_removed": "已移除不影响最终正文的修订元数据。",
        "content_control_unwrapped": "已提取内容控件中的普通正文。",
        "field_cached_result": "已保留 Word 字段的可见缓存结果。",
        "alternate_content_resolved": "已选择 Office 兼容块中的可见正文分支。",
        "table_merge_normalized": "已保留表格的横向或纵向合并语义。",
        "floating_image_inlined": "已将浮动图片规范化为稳定的文档流位置。",
        "vml_image_normalized": "已将旧版 Word 图片规范化为普通内容图片。",
        "metafile_rasterized": "已将 WMF/EMF 图片确定性转换为 PNG。",
    }
    return messages.get(code, "已将源文档结构规范化为目标正文语义。")


def _semantic_object_id(part: str, path: str) -> str:
    paragraph = re.match(r"(.*/w:p(?:\[\d+\])?)(?:/.*)?$", path)
    if paragraph:
        return f"body-object:{part}:{paragraph.group(1)}"
    table = re.match(r"(.*/w:tbl(?:\[\d+\])?)(?:/.*)?$", path)
    if table:
        return f"table:{part}:{table.group(1)}"
    return f"object:{part}:{path[:256]}"


def _namespace(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return ""


__all__ = [
    "DocxNormalization",
    "DocxNormalizationError",
    "normalize_docx_content",
]
