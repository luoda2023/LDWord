"""LDWord document inspector — 文档体检工具。

读取任意 .docx 并生成结构化诊断信息：规模指标（字数/段落/表格/
图片/链接/节）、修订与批注风险、文档属性（含个人信息，供交付前
脱敏参考）、可读性概览与输出建议。GUI 与 CLI 均可复用，无界面依赖。
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# 常见个人信息属性键（core_properties -> 中文说明）
_PERSONAL_PROPERTY_LABELS: tuple[tuple[str, str], ...] = (
    ("author", "作者"),
    ("last_modified_by", "最后修改者"),
    ("category", "类别"),
    ("comments", "备注"),
    ("subject", "主题"),
    ("title", "标题"),
    ("keywords", "关键词"),
)

_GENERATOR_AUTHORS = {"python-docx", "Microsoft Office Word", "Microsoft Word"}


_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # CJK 统一表意文字
    (0x3400, 0x4DBF),   # CJK 扩展 A
    (0xF900, 0xFAFF),   # CJK 兼容表意文字
    (0x3040, 0x30FF),   # 日文假名
    (0xAC00, 0xD7AF),   # 韩文音节
)


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def _is_letter(char: str) -> bool:
    return unicodedata.category(char).startswith("L")


@dataclass(slots=True)
class WordCounts:
    cjk_characters: int = 0
    words: int = 0
    characters_no_spaces: int = 0
    characters_with_spaces: int = 0


@dataclass(slots=True)
class DocumentInspection:
    path: str
    exists: bool = True
    file_size_bytes: int = 0
    paragraphs: int = 0
    tables: int = 0
    inline_shapes: int = 0          # 图片/形状
    sections: int = 0
    hyperlinks: int = 0
    tracked_revisions: bool = False
    comments: int = 0
    counts: WordCounts = field(default_factory=WordCounts)
    core_properties: dict[str, str] = field(default_factory=dict)
    personal_properties: list[tuple[str, str, str]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def estimated_pages(self) -> int:
        """粗略页数估算：按 350 中文字符或 500 词每页折算，取大值。"""
        if self.counts.cjk_characters and self.counts.words:
            by_cjk = self.counts.cjk_characters / 350.0
            by_words = self.counts.words / 500.0
            return max(1, round(max(by_cjk, by_words)))
        return 1


def _extract_text(doc) -> str:
    """提取正文可见文本（段落 + 表格单元格）。

    直接遍历 XML 中的 w:t 文本节点：python-docx 的 `paragraph.text`
    会跳过修订插入（w:ins）内的 run，而体检应统计文档实际呈现的文字，
    因此这里按文档顺序收集 w:t（排除已删除的 w:del 内容）。
    """
    from docx.oxml.ns import qn
    parts: list[str] = []
    try:
        body = doc.element.body
        for para in body.iter(qn('w:p')):
            # 若该段整体位于 w:del 内则跳过
            if para.getparent() is not None and para.getparent().tag == qn('w:del'):
                continue
            texts: list[str] = []
            for node in para.iter(qn('w:t')):
                # 跳过位于 w:del 里的文本
                ancestor = node.getparent()
                inside_del = False
                while ancestor is not None:
                    if ancestor.tag == qn('w:del'):
                        inside_del = True
                        break
                    ancestor = ancestor.getparent()
                if not inside_del:
                    texts.append(node.text or '')
            parts.append(''.join(texts))
    except Exception:
        # 兜底：退回 python-docx 高层 API
        try:
            for paragraph in doc.paragraphs:
                parts.append(paragraph.text or '')
        except Exception:
            pass
    try:
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    parts.append(cell.text or '')
    except Exception:
        pass
    return '\n'.join(parts)


def _count_text(text: str) -> WordCounts:
    """统计中文字符、西文单词与字符数。

    中文按“字”计（cjk_characters），连续字母序列按“词”计（words），
    与 Word 的“字数/字符数”口径对齐，便于论文/公文场景使用。
    """
    cjk = 0
    no_space = 0
    words = 0
    in_word = False
    for char in text:
        if char.isspace():
            if in_word:
                words += 1
                in_word = False
            continue
        no_space += 1
        if _is_cjk(char):
            cjk += 1
            if in_word:
                words += 1
                in_word = False
        elif _is_letter(char):
            in_word = True
        else:
            if in_word:
                words += 1
                in_word = False
    if in_word:
        words += 1
    return WordCounts(
        cjk_characters=cjk,
        words=words,
        characters_no_spaces=no_space,
        characters_with_spaces=len(text.replace("\n", "")),
    )


def _scan_annotations(document) -> tuple[bool, int]:
    """检测修订痕迹与批注数量。

    修订（w:ins/w:del）与批注引用（w:commentReference）在 document.xml
    中直接可见；遍历一次 XML 字符串避免引入额外依赖。
    """
    tracked = False
    comments = 0
    try:
        from docx.oxml.ns import qn
        body = document.element.body
        xml_text = body.xml
        tracked = ("<w:ins " in xml_text) or ("<w:del " in xml_text)
        comments = xml_text.count("w:commentReference")
    except Exception:
        pass
    return tracked, comments


def _count_hyperlinks(document) -> int:
    """统计正文超链接数量（通过包关系 reltype 识别）。"""
    count = 0
    try:
        for rel in document.part.rels.values():
            if str(getattr(rel, "reltype", "") or "").endswith("/hyperlink"):
                count += 1
    except Exception:
        pass
    return count


def inspect_document(path: str | Path) -> DocumentInspection:
    """体检一个 .docx 文件，返回结构化结果（不抛异常，错误入 errors）。"""
    target = Path(path).expanduser()
    result = DocumentInspection(path=str(target))
    if not target.is_file():
        result.exists = False
        result.errors.append("文件不存在或不可读")
        return result
    result.file_size_bytes = target.stat().st_size

    try:
        import docx  # 延迟导入，避免无文档处理时加载
        document = docx.Document(str(target))
    except Exception as exc:
        result.exists = True
        result.errors.append(f"无法解析 DOCX: {type(exc).__name__}: {exc}")
        return result

    text = _extract_text(document)
    result.counts = _count_text(text)
    result.paragraphs = len(document.paragraphs)
    result.tables = len(document.tables)
    try:
        result.sections = len(document.sections)
        result.inline_shapes = len(document.inline_shapes)
    except Exception:
        pass

    result.hyperlinks = _count_hyperlinks(document)
    tracked, comments = _scan_annotations(document)
    result.comments = comments
    result.tracked_revisions = tracked

    # 核心属性与个人信息
    try:
        cp = document.core_properties
        for attr, label in _PERSONAL_PROPERTY_LABELS:
            try:
                value = str(getattr(cp, attr, "") or "").strip()
            except Exception:
                value = ""
            if value:
                result.core_properties[attr] = value
                if attr == "author" and value in _GENERATOR_AUTHORS:
                    continue  # 生成器默认值，不视为个人信息
                result.personal_properties.append((attr, label, value))
    except Exception:
        pass

    # 风险与提示
    if result.tracked_revisions:
        result.warnings.append("文档包含修订痕迹（插入/删除标记），正式交付前建议接受或拒绝修订")
    if result.comments:
        result.warnings.append(f"文档包含 {result.comments} 条批注，交付前请复核")
    if result.personal_properties:
        names = "、".join(label for _, label, _ in result.personal_properties)
        result.warnings.append(f"文档属性含个人信息字段：{names}；对外分享前可清理元数据")
    if result.counts.cjk_characters == 0 and result.counts.words == 0:
        result.issues.append("未提取到正文文本（可能全部为图片/扫描内容）")
    return result


def format_inspection_report(inspection: DocumentInspection) -> str:
    """生成人类可读的中文报告。"""
    if not inspection.exists:
        return f"[ERROR] 文件不存在: {inspection.path}"
    if inspection.errors and not inspection.core_properties and inspection.paragraphs == 0:
        return f"[ERROR] {inspection.errors[0]}"

    lines: list[str] = []
    lines.append("=" * 48)
    lines.append("LDWord 文档体检报告")
    lines.append("=" * 48)
    lines.append(f"文件    : {inspection.path}")
    size_kb = inspection.file_size_bytes / 1024.0
    lines.append(f"大小    : {size_kb:.1f} KB")
    lines.append("")
    lines.append("── 规模指标 ──")
    lines.append(f"段落数  : {inspection.paragraphs}")
    lines.append(f"表格数  : {inspection.tables}")
    lines.append(f"图片/形状: {inspection.inline_shapes}")
    lines.append(f"节数    : {inspection.sections}")
    lines.append(f"超链接  : {inspection.hyperlinks}")
    lines.append(f"估算页数: {inspection.estimated_pages}（按 350 中文字/页折算）")
    lines.append("")
    lines.append("── 字数统计 ──")
    lines.append(f"中文字符(含标点): {inspection.counts.cjk_characters}")
    lines.append(f"西文单词        : {inspection.counts.words}")
    lines.append(f"字符数(不含空格): {inspection.counts.characters_no_spaces}")
    lines.append(f"字符数(含空格)  : {inspection.counts.characters_with_spaces}")
    lines.append("")
    lines.append("── 修订与批注 ──")
    lines.append(f"修订痕迹: {'有' if inspection.tracked_revisions else '无'}")
    lines.append(f"批注数  : {inspection.comments}")
    lines.append("")
    lines.append("── 文档属性 ──")
    if inspection.personal_properties:
        for _, label, value in inspection.personal_properties:
            lines.append(f"{label}: {value}")
    else:
        lines.append("（未设置作者、最后修改者等个人信息字段）")
    lines.append("")
    if inspection.warnings:
        lines.append("── 提示 ──")
        for warning in inspection.warnings:
            lines.append(f"  ! {warning}")
    if inspection.issues:
        lines.append("── 注意 ──")
        for issue in inspection.issues:
            lines.append(f"  * {issue}")
    if inspection.errors:
        lines.append("── 错误 ──")
        for error in inspection.errors:
            lines.append(f"  x {error}")
    lines.append("=" * 48)
    return "\n".join(lines)
