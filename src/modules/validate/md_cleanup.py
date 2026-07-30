"""
md_cleanup — Markdown / LaTeX 残留清理模块

清理从 Markdown/LaTeX/HTML 转换过来的文档中的格式残留。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.modules.base import BaseModule, ModuleMeta
from src.shared.engine.run_ops import get_full_text

if TYPE_CHECKING:
    from docx import Document
    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


# ── Markdown 残留 ──
_MD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),     # **bold** → bold
    (re.compile(r"\*(.+?)\*"), r"\1"),          # *italic* → italic
    (re.compile(r"__(.+?)__"), r"\1"),          # __bold__ → bold
    (re.compile(r"_(.+?)_"), r"\1"),            # _italic_ → italic
    (re.compile(r"~~(.+?)~~"), r"\1"),          # ~~strike~~ → strike
    (re.compile(r"`(.+?)`"), r"\1"),            # `code` → code
    (re.compile(r"^\s*#{1,6}\s+"), ""),         # ### heading → heading
    (re.compile(r"^\s*[-*+]\s+"), ""),          # - list item → list item
    (re.compile(r"^\s*\d+\.\s+"), ""),          # 1. ordered → ordered
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),  # [text](url) → text
    (re.compile(r"!\[[^\]]*\]\([^)]+\)"), ""),      # ![img](url) → remove
    (re.compile(r"^>{1,3}\s?"), ""),                 # > blockquote → remove
    (re.compile(r"^-{3,}$"), ""),                    # --- hr → remove
    (re.compile(r"^\*{3,}$"), ""),                   # *** hr → remove
]

# ── LaTeX 残留 ──
_LATEX_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\\textbf\{([^}]+)\}"), r"\1"),     # \textbf{x} → x
    (re.compile(r"\\textit\{([^}]+)\}"), r"\1"),     # \textit{x} → x
    (re.compile(r"\\emph\{([^}]+)\}"), r"\1"),       # \emph{x} → x
    (re.compile(r"\\underline\{([^}]+)\}"), r"\1"),  # \underline{x} → x
    (re.compile(r"\\text\{([^}]+)\}"), r"\1"),       # \text{x} → x
    (re.compile(r"\\cite\{([^}]+)\}"), r"[\1]"),     # \cite{x} → [x]
    (re.compile(r"\\ref\{([^}]+)\}"), r"\1"),        # \ref{x} → x
    (re.compile(r"\\label\{[^}]+\}"), ""),            # \label{x} → remove
    (re.compile(r"\$([^$]+)\$"), r"\1"),              # $math$ → math
    (re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^}]+)\}"), r"\1"),
    (re.compile(r"\\(?:begin|end)\{[^}]+\}"), ""),   # \begin{x} / \end{x}
    (re.compile(r"\\\\"), ""),                         # \\ → remove
    (re.compile(r"\\[a-zA-Z]+(?:\[[^\]]*\])?\s*"), ""),  # \command[opt] → remove (catch-all)
]

# ── 空白规范化 ──
_WHITESPACE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[ \t]{2,}"), " "),           # 多空格 → 单空格
    (re.compile(r"\u3000{2,}"), "\u3000"),     # 多个全角空格 → 单个
    (re.compile(r"\n{3,}"), "\n\n"),           # 三个以上换行 → 两个
    (re.compile(r"^\s+$"), ""),                # 纯空白段 → 空
]

# ── HTML 标签 ──
_HTML_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"<br\s*/?>"), ""),                      # <br> → remove
    (re.compile(r"</?(?:p|div|span|b|i|em|strong)[^>]*>"), ""),  # 常见标签
    (re.compile(r"&nbsp;"), " "),                        # &nbsp; → space
    (re.compile(r"&amp;"), "&"),                          # &amp; → &
    (re.compile(r"&lt;"), "<"),
    (re.compile(r"&gt;"), ">"),
]

ALL_PATTERNS = _MD_PATTERNS + _LATEX_PATTERNS + _WHITESPACE_PATTERNS + _HTML_PATTERNS


class MdCleanupModule(BaseModule):
    """Markdown / LaTeX / HTML 残留清理模块。

    职责：
    - 清理 Markdown 标记（**、*、~~、`、#、链接、图片、引用）
    - 清理 LaTeX 命令（\\textbf、\\cite、$...$、\\section）
    - 清理 HTML 标签（<br>、<p>、&nbsp;）
    - 空白规范化（多空格、多换行、全角空格压缩）
    """

    meta = ModuleMeta(
        name="md_cleanup",
        description="Markdown/LaTeX 清理",
        category="validate",
        requires_config=(),
    )

    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        count = 0

        # 段落清理
        for para in doc.paragraphs:
            if _clean_paragraph(para):
                count += 1

        # 表格单元格清理
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        if _clean_paragraph(para):
                            count += 1

        if count:
            tracker.record(
                rule_name=self.meta.name,
                target=f"{count} 个段落",
                section="global",
                change_type="cleanup",
                before="含 Markdown/LaTeX 残留",
                after="已清理",
            )


def _clean_paragraph(para) -> bool:
    """清理单个段落，返回是否有修改。"""
    text = get_full_text(para)
    if not text:
        return False

    cleaned = text
    for pattern, repl in ALL_PATTERNS:
        cleaned = pattern.sub(repl, cleaned)

    if cleaned != text:
        if para.runs:
            # 保留首 run 格式，合并为单 run
            para.runs[0].text = cleaned
            for run in para.runs[1:]:
                run._element.getparent().remove(run._element)
        return True
    return False

