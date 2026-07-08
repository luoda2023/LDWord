"""Blank exam-paper style definitions and real master document handling."""

from __future__ import annotations

from collections.abc import Iterable as IterableABC, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from shutil import copy2
from typing import Iterable
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml import etree

from src.config.scene import ExamBlankStyleConfig, ExamPaperConfig


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXAM_MASTER_ROOT = PROJECT_ROOT / "exam_masters"
BUILTIN_EXAM_MASTER_DIR = EXAM_MASTER_ROOT / "builtin"
USER_EXAM_MASTER_DIR = EXAM_MASTER_ROOT / "user"

BUILTIN_EXAM_BLANK_STYLE_IDS = ("default_exam",)
BUILTIN_MASTER_VERSION = "exam-master-v20-free-answer-area-2026-07-06"
MASTER_TITLE_PLACEHOLDER = "{{af_title}}"
MASTER_SUBTITLE_PLACEHOLDER = "{{af_version}}"
MASTER_SUBJECT_PLACEHOLDER = "科目：{{af_subject}}"
MASTER_GRADE_PLACEHOLDER = "年级：{{af_grade}}"
MASTER_DURATION_PLACEHOLDER = "考试时间：{{af_duration}}"
MASTER_TOTAL_SCORE_PLACEHOLDER = "满分：{{af_total_score}}"
MASTER_METADATA_PLACEHOLDER = (
    f"{MASTER_SUBJECT_PLACEHOLDER}    {MASTER_GRADE_PLACEHOLDER}    "
    f"{MASTER_DURATION_PLACEHOLDER}    {MASTER_TOTAL_SCORE_PLACEHOLDER}"
)
MASTER_CONTROL_GUIDE_TEXT = "占位符保持原样；页眉页脚和密封线由试卷母版决定。"
MASTER_METADATA_GUIDE_TEXT = "工作台字段：{{af_title}}、{{af_subject}}、{{af_grade}}、{{af_duration}}、{{af_total_score}}。"
MASTER_DELIVERY_GUIDE_TEXT = "生成结果字段：{{af_version}}。"
MASTER_SCORE_TABLE_GUIDE_TEXT = "固定区：得分栏、密封线、页眉页脚可直接在 Word 中调整。"
MASTER_QUESTION_GUIDE_TEXT = "题目从 {{af_questions}} 处生成。"
MASTER_QUESTION_INSERT_MARKER = "{{af_questions}}"
MASTER_ANSWER_AREA_MARKER = "{{af_answer_area}}"
ANSWER_SPACE_LINE_KEYS = (
    "answer_lines",
    "answer_space_lines",
    "response_lines",
    "writing_lines",
    "答题行数",
)
ANSWER_AREA_KIND_KEYS = (
    "answer_area_kind",
    "answer_space_kind",
    "response_area_kind",
    "答题区类型",
)
ANSWER_SPACE_MAX_LINES = 10
ANSWER_SPACE_DEFAULT_LINES = 2
ANSWER_FREE_AREA_MIN_LINES = 4
ANSWER_FREE_AREA_DEFAULT_LINES = 5
ANSWER_AREA_LEFT_INDENT_CM = 0.72
MASTER_CONTROL_GUIDE_TEXTS = frozenset(
    {
        MASTER_CONTROL_GUIDE_TEXT,
        MASTER_METADATA_GUIDE_TEXT,
        MASTER_DELIVERY_GUIDE_TEXT,
        MASTER_SCORE_TABLE_GUIDE_TEXT,
        MASTER_QUESTION_GUIDE_TEXT,
        "母版提示：可调整版式和样式，请保留 {{af_*}} 占位符。",
        "母版编辑说明：方括号【占位符：...】由 Alavette 自动替换；可调整位置和样式，但不要删除、改名或拆分占位符。",
        "工作台字段占位符：标题、科目、年级、考试时间、满分。",
        "生成结果占位符：学生卷 / 答案版；正式输出会自动替换卷别。",
        "题目区占位符：工作台导入的题目会从下方插入点开始生成。",
    }
)
EXAM_MARKDOWN_AUTHORING_PROMPT = """你是一名严谨的中小学命题老师。请根据我提供的要求，生成一份适合导入 Alavette Form 试卷场景的 Markdown 试卷内容。

【命题要求】
学科：{{学科}}
年级：{{年级}}
考试范围：{{考试范围}}
考试时间：{{考试时间}}
满分：{{满分}}
题型与题量：{{题型与题量}}
难度：{{难度}}
其他要求：{{其他要求}}

【输出规则】
1. 只输出 Markdown 正文，不要代码围栏，不要解释。
2. 不要编写页眉、页脚、页码、密封线、字体、页边距、装订线等版式信息，这些由试卷母版决定。
3. 使用清晰的大题结构，例如：
   # 试卷标题
   > 科目：语文　年级：七年级　考试时间：90 分钟　满分：100 分

   ## 一、积累与运用
   1. 题干……（3 分）
      A. 选项
      B. 选项
      C. 选项
      D. 选项

   ## 二、阅读与表达
4. 每个大题内小题从 1 重新编号，答案速查与学生卷保持一致。
5. 每道题都要标明分值。
6. 选择题选项使用 A. B. C. D. 格式。
7. 答案、解析不要混入题干正文。
8. 文末单独输出：
   ## 答案速查
   1. A
   2. 示例答案……
9. 如需要解析，在答案后追加简短解析：
   1. A。解析：……
10. 需要预留答题区时，在题目结构中加入 answer_area_kind 和 answer_lines：语文简答/阅读用 answer_area_kind: lines、answer_lines: 3；数学计算/解答/证明用 answer_area_kind: free、answer_lines: 5；选择题不要设置答题区。
11. 内容应适合直接导入，不要加入“以下是试卷”等对话性文字。"""

EXAM_MASTER_CONVERSION_PROMPT = """你是一名 Word 试卷模板工程师。请把我提供的常规试卷改造成 Alavette Form 可用的“试卷母版”。

【核心目标】
保留这份卷子的版式风格，例如标题区、信息栏、注意事项、密封线、页眉、页脚、页码、表格样式和题目排版风格；删除具体题目、答案和解析，把可变内容替换为占位符。

【必须使用的占位符】
请原样保留以下占位符，不要改名，不要加空格，不要拆开，不要放入多个文本框或多个样式片段中：

{{af_title}}
{{af_subject}}
{{af_grade}}
{{af_duration}}
{{af_total_score}}
{{af_questions}}
{{af_answer_area}}

【改造要求】
1. 将原试卷标题替换为：{{af_title}}
2. 将科目、年级、考试时间、满分等可变信息替换为：
   科目：{{af_subject}}　年级：{{af_grade}}　考试时间：{{af_duration}}　满分：{{af_total_score}}
3. 删除所有真实题目、答案、解析和学生作答内容。
4. 在正文题目开始的位置，单独放一行：{{af_questions}}
5. 如果卷面需要预留答题区，在合适位置单独放一行：{{af_answer_area}}
6. 页眉、页脚、页码、密封线、注意事项、装订线可以保留在母版中，因为它们属于试卷版式。
7. 不要在母版中写具体题目内容，不要写真实答案，不要写示例题。
8. 占位符必须是普通可编辑文本，尤其是 {{af_questions}} 和 {{af_answer_area}} 必须作为独立段落存在。
9. 不要把占位符放在图片、形状、艺术字、文本框或页眉页脚中。

【输出要求】
如果你可以直接编辑 Word，请输出改造后的 .docx 文件。
如果你只能给出修改方案，请逐项说明应该删除什么、保留什么、替换成哪个占位符。

【自检清单】
最终母版应满足：
- 能一眼看出标题由 {{af_title}} 决定。
- 能一眼看出科目、年级、时间、满分由对应占位符决定。
- 正文题目插入点只有 {{af_questions}}。
- 没有真实题目、答案、解析残留。
- 页眉页脚只作为母版版式存在，不再依赖普通模板二次覆盖。"""

EXAM_AI_PROMPT_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("markdown", "生成试卷", EXAM_MARKDOWN_AUTHORING_PROMPT),
    ("master", "改造母版", EXAM_MASTER_CONVERSION_PROMPT),
)
LEGACY_MASTER_TITLE_PLACEHOLDERS = (
    "【试卷标题】",
    "【试卷标题｜工作台：标题】",
    "【占位符：试卷标题｜来源：工作台-标题｜请保留】",
)
LEGACY_MASTER_SUBTITLE_PLACEHOLDERS = (
    "【副标题】",
    "【卷别｜生成结果：学生卷 / 答案版】",
    "【占位符：卷别｜来源：生成结果-学生卷/答案版｜请保留】",
)
LEGACY_MASTER_SUBJECT_PLACEHOLDERS = (
    "科目：____________",
    "科目：【占位符：科目｜工作台｜请保留】",
)
LEGACY_MASTER_GRADE_PLACEHOLDERS = (
    "年级：____________",
    "年级：【占位符：年级｜工作台｜请保留】",
)
LEGACY_MASTER_DURATION_PLACEHOLDERS = (
    "考试时间：____________",
    "考试时间：【占位符：考试时间｜工作台｜请保留】",
)
LEGACY_MASTER_TOTAL_SCORE_PLACEHOLDERS = (
    "满分：____________",
    "满分：【占位符：满分｜工作台｜请保留】",
)
LEGACY_MASTER_QUESTION_MARKERS = (
    "题目会在正式生成时从这里开始。",
    "【题目插入点｜工作台导入内容从这里开始】",
    "【占位符：题目插入点｜工作台导入题目从这里开始｜请保留】",
)
LEGACY_MASTER_ANSWER_AREA_MARKERS = (
    "作答区域会按题目自动延展。",
    "【作答区｜程序按题目自动延展】",
    "【占位符：作答区｜程序按题目自动延展｜请保留】",
)
SECTION_SCORE_CELL_WIDTH_CM = 1846 / 567
SECTION_TITLE_CELL_WIDTH_CM = 7083 / 567
VML_NS = "urn:schemas-microsoft-com:vml"
OFFICE_NS = "urn:schemas-microsoft-com:office:office"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
WORD_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@dataclass(frozen=True)
class ExamBlankStyleSpec:
    style_id: str
    label: str
    summary: str
    status: str
    base_style_id: str
    readonly: bool = True
    master_filename: str = ""
    top_margin_cm: float = 2.3
    bottom_margin_cm: float = 2.0
    left_margin_cm: float = 2.2
    right_margin_cm: float = 2.2
    body_font_size_pt: int = 10
    line_spacing: float = 1.25


@dataclass(frozen=True)
class ExamPaperDocxOutputs:
    """Separate Word files generated from one exam source."""

    student_docx: Path | None = None
    answer_key_docx: Path | None = None


_BUILTIN_STYLE_SPECS: dict[str, ExamBlankStyleSpec] = {
    "default_exam": ExamBlankStyleSpec(
        style_id="default_exam",
        label="默认试卷",
        summary="标准 A4 卷面，含标题区、考试信息栏、注意事项、题目区和页脚。",
        status="内置，可直接使用",
        base_style_id="default_exam",
        master_filename="default_exam_v20.docx",
        top_margin_cm=1.84,
        bottom_margin_cm=1.74,
        left_margin_cm=2.58,
        right_margin_cm=2.58,
        body_font_size_pt=12,
        line_spacing=1.5,
    ),
}


EXAM_SAMPLE_PAYLOAD: dict[str, object] = {
    "title": "七年级语文期中测试样张",
    "subject": "语文",
    "grade": "七年级",
    "duration": "90 分钟",
    "total_score": "100 分",
    "sections": [
        {
            "title": "一、积累与运用",
            "questions": [
                {
                    "stem": "下列词语中加点字读音完全正确的一项是（  ）。",
                    "options": ["A. 酝酿 niang", "B. 静谧 mi", "C. 贮蓄 zhu", "D. 粗犷 kuang"],
                    "answer": "C",
                    "score": "3",
                },
                {
                    "stem": "请根据语境填写恰当的古诗文名句。",
                    "answer": "示例答案略",
                    "score": "6",
                },
            ],
        },
        {
            "title": "二、阅读与表达",
            "questions": [
                {
                    "stem": "阅读材料，概括文章围绕人物写了哪两件事。",
                    "answer": "写了人物助人和坚持学习两件事。",
                    "score": "8",
                },
                {
                    "stem": "请以“那个温暖的瞬间”为题写一段不少于 200 字的片段。",
                    "answer": "评分时关注中心、细节和语言表达。",
                    "score": "20",
                },
            ],
        },
    ],
}


def builtin_exam_blank_style_options() -> tuple[tuple[str, str], ...]:
    return tuple(
        (_BUILTIN_STYLE_SPECS[style_id].style_id, _BUILTIN_STYLE_SPECS[style_id].label)
        for style_id in BUILTIN_EXAM_BLANK_STYLE_IDS
        if style_id in _BUILTIN_STYLE_SPECS
    )


def exam_ai_prompt_text(prompt_id: str) -> str:
    target = str(prompt_id or "").strip()
    for value, _label, text in EXAM_AI_PROMPT_OPTIONS:
        if value == target:
            return text
    return EXAM_MARKDOWN_AUTHORING_PROMPT


def exam_blank_style_options(config: ExamPaperConfig | None = None) -> tuple[tuple[str, str], ...]:
    custom = []
    if config is not None:
        custom = [
            (style.style_id, style.label)
            for style in getattr(config, "custom_blank_styles", []) or []
            if str(style.style_id or "").strip()
        ]
    return tuple(custom) + builtin_exam_blank_style_options()


def exam_blank_style_label(
    style_id: str,
    config: ExamPaperConfig | None = None,
    *,
    fallback: str = "默认试卷",
) -> str:
    return resolve_exam_blank_style(config, style_id).label if style_id else fallback


def resolve_exam_blank_style(
    config: ExamPaperConfig | None,
    style_id: str,
) -> ExamBlankStyleSpec:
    target = str(style_id or "").strip() or "default_exam"
    custom_style = _find_custom_blank_style(config, target)
    if custom_style is not None:
        base = _BUILTIN_STYLE_SPECS.get(custom_style.base_style_id, _BUILTIN_STYLE_SPECS["default_exam"])
        return ExamBlankStyleSpec(
            style_id=custom_style.style_id,
            label=custom_style.label,
            summary=f"用户副本，基于“{base.label}”，可打开 Word 修改。",
            status="用户副本，可修改",
            base_style_id=base.style_id,
            readonly=False,
            master_filename=Path(custom_style.master_docx_path).name if custom_style.master_docx_path else "",
            top_margin_cm=base.top_margin_cm,
            bottom_margin_cm=base.bottom_margin_cm,
            left_margin_cm=base.left_margin_cm,
            right_margin_cm=base.right_margin_cm,
            body_font_size_pt=base.body_font_size_pt,
            line_spacing=base.line_spacing,
        )
    return _BUILTIN_STYLE_SPECS.get(target, _BUILTIN_STYLE_SPECS["default_exam"])


def create_exam_blank_style_copy(
    config: ExamPaperConfig,
    source_style_id: str | None = None,
) -> ExamBlankStyleConfig:
    """Create user-owned style metadata without touching the filesystem."""

    source = resolve_exam_blank_style(config, source_style_id or config.blank_style_id)
    base_style_id = source.base_style_id if not source.readonly else source.style_id
    existing_ids = {
        str(style.style_id or "").strip()
        for style in getattr(config, "custom_blank_styles", []) or []
    }
    existing_labels = {
        str(style.label or "").strip()
        for style in getattr(config, "custom_blank_styles", []) or []
    }
    index = 1
    while True:
        suffix = "" if index == 1 else str(index)
        style_id = f"user_{base_style_id}_copy{suffix}"
        label = f"{source.label} 副本{suffix}"
        if style_id not in existing_ids and label not in existing_labels:
            break
        index += 1
    return ExamBlankStyleConfig(
        style_id=style_id,
        label=label,
        base_style_id=base_style_id,
    )


def create_exam_blank_master_copy(
    config: ExamPaperConfig,
    source_style_id: str | None = None,
    *,
    output_dir: Path | str | None = None,
) -> ExamBlankStyleConfig:
    """Create a user-owned style and copy the current real DOCX master file."""

    style = create_exam_blank_style_copy(config, source_style_id)
    source_path = ensure_current_exam_blank_master_docx(
        config,
        source_style_id or config.blank_style_id,
    )
    target_dir = Path(output_dir) if output_dir is not None else USER_EXAM_MASTER_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_docx_path(target_dir / f"{style.style_id}.docx")
    copy2(source_path, target)
    style.master_docx_path = _stored_master_path(target)
    return style


def import_exam_blank_master_docx(
    config: ExamPaperConfig,
    source_docx_path: Path | str,
    *,
    label: str | None = None,
    base_style_id: str | None = None,
    output_dir: Path | str | None = None,
) -> ExamBlankStyleConfig:
    """Copy an existing Word file into the scene-owned exam master library."""

    source = Path(source_docx_path)
    if source.suffix.lower() != ".docx":
        raise ValueError("请选择 .docx 格式的 Word 母版")
    if not _docx_is_openable(source):
        raise ValueError("选择的 Word 母版无法打开")

    requested_label = _safe_docx_stem(label or source.stem) or "导入试卷母版"
    base_source = resolve_exam_blank_style(
        config,
        base_style_id or getattr(config, "blank_style_id", "") or "default_exam",
    )
    style_id, style_label = _unique_imported_style_identity(config, requested_label)
    style = ExamBlankStyleConfig(
        style_id=style_id,
        label=style_label,
        base_style_id=base_source.base_style_id if not base_source.readonly else base_source.style_id,
    )

    target_dir = Path(output_dir) if output_dir is not None else USER_EXAM_MASTER_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_docx_path(target_dir / f"{style.style_id}.docx")
    copy2(source, target)
    style.master_docx_path = _stored_master_path(target)
    return style


def ensure_builtin_exam_master_files() -> tuple[Path, ...]:
    return tuple(
        ensure_builtin_exam_master_docx(style_id)
        for style_id in BUILTIN_EXAM_BLANK_STYLE_IDS
    )


def ensure_builtin_exam_master_docx(style_id: str) -> Path:
    spec = _BUILTIN_STYLE_SPECS.get(str(style_id or "").strip(), _BUILTIN_STYLE_SPECS["default_exam"])
    target = BUILTIN_EXAM_MASTER_DIR / spec.master_filename
    if not _builtin_master_is_current(target):
        _write_exam_blank_master_document(spec, target)
    return target


def ensure_current_exam_blank_master_docx(
    config: ExamPaperConfig | None,
    style_id: str,
) -> Path:
    target = str(style_id or "").strip() or "default_exam"
    custom_style = _find_custom_blank_style(config, target)
    if custom_style is None:
        return ensure_builtin_exam_master_docx(target)

    stored = _resolve_stored_master_path(custom_style.master_docx_path)
    if stored is None:
        stored = USER_EXAM_MASTER_DIR / f"{custom_style.style_id}.docx"
        custom_style.master_docx_path = _stored_master_path(stored)

    if not _docx_is_openable(stored):
        source = ensure_builtin_exam_master_docx(custom_style.base_style_id)
        stored.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, stored)
    return stored


def exam_blank_style_preview_lines(
    style_id: str,
    config: ExamPaperConfig | None = None,
    *,
    answer_version: bool = False,
) -> list[str]:
    spec = resolve_exam_blank_style(config, style_id)
    header_lines = [
        f"{spec.label} / A4",
        "七年级语文期中测试样张",
        "科目：语文    年级：七年级    考试时间：90 分钟    满分：100 分",
    ]
    footer_line = "页脚：第 1 页 / 共 2 页"
    if answer_version:
        return header_lines + [
            "答案速查",
            "一、积累与运用",
            "1. C",
            "2. 示例答案略",
            "二、阅读与表达",
            "1. 助人与坚持学习",
            "2. 按表达评分",
            footer_line,
        ]

    return header_lines + [
        "注意事项：请在规定区域内作答，保持卷面整洁。",
        "一、积累与运用",
        "1. 下列词语中加点字读音完全正确的一项是（  ）。",
        "2. 请根据语境填写恰当的古诗文名句。",
        "二、阅读与表达",
        "3. 阅读材料，概括文章围绕人物写了哪两件事。",
        "4. 请以“那个温暖的瞬间”为题写一段片段。",
        footer_line,
    ]


def write_exam_blank_style_sample_docx(
    style_id: str,
    output_dir: Path | str,
    *,
    config: ExamPaperConfig | None = None,
) -> Path:
    spec = resolve_exam_blank_style(config, style_id)
    return write_exam_paper_docx(
        style_id,
        output_dir,
        payload=EXAM_SAMPLE_PAYLOAD,
        config=config,
        include_answer_version=False,
        filename=f"{_safe_stem(spec.label)}_样张.docx",
    )


def write_exam_paper_docx(
    style_id: str,
    output_dir: Path | str,
    *,
    payload: Mapping[str, object] | None = None,
    config: ExamPaperConfig | None = None,
    include_answer_version: bool = False,
    filename: str | None = None,
) -> Path:
    spec = resolve_exam_blank_style(config, style_id)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    exam_payload = payload or EXAM_SAMPLE_PAYLOAD
    target_name = filename or f"{_safe_stem(_exam_payload_title(exam_payload))}.docx"
    if not target_name.lower().endswith(".docx"):
        target_name = f"{target_name}.docx"
    target = target_dir / Path(target_name).name

    master_path = ensure_current_exam_blank_master_docx(config, style_id)
    document = Document(str(master_path))
    _configure_exam_styles(document, spec)
    _write_exam_payload_into_master(document, spec, exam_payload)
    if include_answer_version:
        document.add_page_break()
        _add_answer_version(document, spec, exam_payload)
    document.save(str(target))
    _patch_saved_first_header_from_source(target, master_path)
    return target


def write_exam_paper_docx_files(
    style_id: str,
    output_dir: Path | str,
    *,
    payload: Mapping[str, object] | None = None,
    config: ExamPaperConfig | None = None,
    include_student: bool = True,
    include_answer_key: bool = True,
    filename_stem: str | None = None,
) -> ExamPaperDocxOutputs:
    exam_payload = payload or EXAM_SAMPLE_PAYLOAD
    base_stem = _safe_docx_stem(filename_stem or _exam_payload_title(exam_payload))
    student_docx = (
        write_exam_paper_docx(
            style_id,
            output_dir,
            payload=exam_payload,
            config=config,
            include_answer_version=False,
            filename=f"{base_stem}_学生卷.docx",
        )
        if include_student
        else None
    )
    answer_key_docx = (
        write_exam_answer_key_docx(
            style_id,
            output_dir,
            payload=exam_payload,
            config=config,
            filename=f"{base_stem}_答案速查.docx",
        )
        if include_answer_key
        else None
    )
    return ExamPaperDocxOutputs(
        student_docx=student_docx,
        answer_key_docx=answer_key_docx,
    )


def write_exam_answer_key_docx(
    style_id: str,
    output_dir: Path | str,
    *,
    payload: Mapping[str, object] | None = None,
    config: ExamPaperConfig | None = None,
    filename: str | None = None,
) -> Path:
    spec = resolve_exam_blank_style(config, style_id)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    exam_payload = payload or EXAM_SAMPLE_PAYLOAD
    target_name = filename or f"{_safe_stem(_exam_payload_title(exam_payload))}_答案速查.docx"
    if not target_name.lower().endswith(".docx"):
        target_name = f"{target_name}.docx"
    target = target_dir / Path(target_name).name

    document = Document()
    _apply_exam_document_page(document, spec)
    _configure_exam_styles(document, spec)
    _add_answer_version(document, spec, exam_payload)
    for section in document.sections:
        _set_page_number_footer(section.footer)
    document.save(str(target))
    return target


def write_exam_blank_master_docx(
    style_id: str,
    output_dir: Path | str,
    *,
    config: ExamPaperConfig | None = None,
) -> Path:
    spec = resolve_exam_blank_style(config, style_id)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{_safe_stem(spec.label)}_母版.docx"
    _write_exam_blank_master_document(spec, target)
    return target


def _write_exam_blank_master_document(spec: ExamBlankStyleSpec, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.core_properties.title = f"{spec.label} 试卷母版"
    document.core_properties.subject = "Alavette Form exam paper master"
    document.core_properties.comments = BUILTIN_MASTER_VERSION
    _apply_exam_document_page(document, spec)
    _configure_exam_styles(document, spec)
    _add_blank_master_page(document, spec)
    document.save(str(target))
    _patch_saved_reference_sealed_header(target)


def _patch_saved_reference_sealed_header(target: Path) -> None:
    reference_xml = _load_reference_sealed_header_xml()
    if reference_xml is None:
        return
    _patch_saved_first_header_xml(target, reference_xml)


def _patch_saved_first_header_from_source(target: Path, source: Path) -> None:
    header_xml = _load_first_page_header_xml(source)
    if header_xml is None:
        return
    _patch_saved_first_header_xml(target, header_xml)


def _patch_saved_first_header_xml(target: Path, header_xml: bytes) -> None:
    temp_target = target.with_name(f"{target.name}.tmp")
    try:
        with ZipFile(target) as archive:
            document_xml = archive.read("word/document.xml")
            document_rels_xml = archive.read("word/_rels/document.xml.rels")
            first_header_part = _first_header_part_name(document_xml, document_rels_xml)
            if first_header_part is None:
                return

            with ZipFile(temp_target, "w", ZIP_DEFLATED) as output:
                for info in archive.infolist():
                    data = archive.read(info.filename)
                    if info.filename == first_header_part:
                        data = header_xml
                    output.writestr(info, data)
        temp_target.replace(target)
    except (BadZipFile, KeyError, OSError, etree.XMLSyntaxError):
        try:
            if temp_target.exists():
                temp_target.unlink()
        except OSError:
            pass


def _load_first_page_header_xml(path: Path) -> bytes | None:
    try:
        with ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
            document_rels_xml = archive.read("word/_rels/document.xml.rels")
            first_header_part = _first_header_part_name(document_xml, document_rels_xml)
            if first_header_part is None:
                return None
            return archive.read(first_header_part)
    except (BadZipFile, KeyError, OSError, etree.XMLSyntaxError):
        return None


def _load_reference_sealed_header_xml() -> bytes | None:
    reference_path = BUILTIN_EXAM_MASTER_DIR / "default_exam_v10.docx"
    if not reference_path.exists():
        return None

    try:
        with ZipFile(reference_path) as archive:
            for name in archive.namelist():
                if not name.startswith("word/header") or not name.endswith(".xml"):
                    continue
                xml_bytes = archive.read(name)
                if b"ExamSeal" in xml_bytes and b"rotation:-5898240f" in xml_bytes:
                    return xml_bytes
    except (BadZipFile, KeyError, OSError):
        return None
    return None


def _first_header_part_name(document_xml: bytes, document_rels_xml: bytes) -> str | None:
    document_root = etree.fromstring(document_xml)
    rel_id = None
    for header_ref in document_root.xpath(".//w:headerReference", namespaces={"w": WORD_NS}):
        if header_ref.get(qn("w:type")) == "first":
            rel_id = header_ref.get(qn("r:id"))
            break
    if rel_id is None:
        return None

    rels_root = etree.fromstring(document_rels_xml)
    for relationship in rels_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        if relationship.get("Id") != rel_id:
            continue
        if relationship.get("Type") != f"{WORD_REL_NS}/header":
            return None
        target = relationship.get("Target", "")
        if not target:
            return None
        if target.startswith("/"):
            return target.lstrip("/")
        return f"word/{target}"
    return None


def _apply_exam_document_page(document: Document, spec: ExamBlankStyleSpec) -> None:
    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(spec.top_margin_cm)
    section.bottom_margin = Cm(spec.bottom_margin_cm)
    section.left_margin = Cm(spec.left_margin_cm)
    section.right_margin = Cm(spec.right_margin_cm)
    section.header_distance = Cm(1.4)
    section.footer_distance = Cm(1.2)


def _configure_exam_styles(document: Document, spec: ExamBlankStyleSpec) -> None:
    styles = document.styles
    _set_style_font(styles["Normal"], "宋体", spec.body_font_size_pt)
    styles["Normal"].paragraph_format.line_spacing = spec.line_spacing
    styles["Normal"].paragraph_format.space_after = Pt(0)

    title_style = _paragraph_style(document, "Exam Title")
    _set_style_font(title_style, "宋体", 18, bold=True)
    title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_style.paragraph_format.space_after = Pt(0)
    title_style.paragraph_format.line_spacing = spec.line_spacing

    subtitle_style = _paragraph_style(document, "Exam Subtitle")
    _set_style_font(subtitle_style, "黑体", 24, bold=True)
    subtitle_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_style.paragraph_format.space_after = Pt(4)
    subtitle_style.paragraph_format.line_spacing = spec.line_spacing

    meta_style = _paragraph_style(document, "Exam Metadata")
    _set_style_font(meta_style, "宋体", spec.body_font_size_pt)
    meta_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_style.paragraph_format.space_after = Pt(3)
    meta_style.paragraph_format.line_spacing = spec.line_spacing

    heading_style = _paragraph_style(document, "Exam Section Heading")
    _set_style_font(heading_style, "宋体", 14, bold=True)
    heading_style.paragraph_format.space_before = Pt(4)
    heading_style.paragraph_format.space_after = Pt(0)
    heading_style.paragraph_format.line_spacing = spec.line_spacing

    question_style = _paragraph_style(document, "Exam Question")
    _set_style_font(question_style, "宋体", spec.body_font_size_pt)
    question_style.paragraph_format.line_spacing = spec.line_spacing
    question_style.paragraph_format.space_after = Pt(0)

    question_stem_style = _paragraph_style(document, "Exam Question Stem")
    _set_style_font(question_stem_style, "宋体", spec.body_font_size_pt)
    question_stem_style.paragraph_format.line_spacing = spec.line_spacing
    question_stem_style.paragraph_format.space_before = Pt(4)
    question_stem_style.paragraph_format.space_after = Pt(1)
    question_stem_style.paragraph_format.left_indent = Cm(0.72)
    question_stem_style.paragraph_format.first_line_indent = Cm(-0.72)

    option_style = _paragraph_style(document, "Exam Option")
    _set_style_font(option_style, "宋体", spec.body_font_size_pt)
    option_style.paragraph_format.left_indent = Cm(0.72)
    option_style.paragraph_format.line_spacing = spec.line_spacing
    option_style.paragraph_format.space_after = Pt(0)

    answer_space_style = _paragraph_style(document, "Exam Answer Space")
    _set_style_font(answer_space_style, "宋体", spec.body_font_size_pt)
    answer_space_style.paragraph_format.left_indent = Cm(0.72)
    answer_space_style.paragraph_format.line_spacing = 1.4
    answer_space_style.paragraph_format.space_before = Pt(2)
    answer_space_style.paragraph_format.space_after = Pt(2)

    free_answer_style = _paragraph_style(document, "Exam Free Answer Area")
    _set_style_font(free_answer_style, "宋体", spec.body_font_size_pt)
    free_answer_style.paragraph_format.line_spacing = 1.0
    free_answer_style.paragraph_format.space_before = Pt(0)
    free_answer_style.paragraph_format.space_after = Pt(0)

    muted_style = _paragraph_style(document, "Exam Muted")
    _set_style_font(muted_style, "宋体", 10, color="666666")
    muted_style.paragraph_format.line_spacing = spec.line_spacing
    muted_style.paragraph_format.space_after = Pt(0)

    guide_style = _paragraph_style(document, "Exam Control Guide")
    _set_style_font(guide_style, "微软雅黑", 9, color="1677FF")
    guide_style.paragraph_format.line_spacing = 1.0
    guide_style.paragraph_format.space_after = Pt(2)

    marker_style = _paragraph_style(document, "Exam Control Marker")
    _set_style_font(marker_style, "微软雅黑", 9, bold=True, color="0958D9")
    marker_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    marker_style.paragraph_format.line_spacing = 1.0
    marker_style.paragraph_format.space_before = Pt(2)
    marker_style.paragraph_format.space_after = Pt(2)


def _add_blank_master_page(document: Document, spec: ExamBlankStyleSpec) -> None:
    _add_sealed_zone_to_header(document)
    document.add_paragraph(MASTER_TITLE_PLACEHOLDER, style="Exam Title")
    document.add_paragraph(MASTER_SUBTITLE_PLACEHOLDER, style="Exam Subtitle")
    document.add_paragraph(MASTER_METADATA_PLACEHOLDER, style="Exam Metadata")
    _add_control_guide_paragraph(document, MASTER_CONTROL_GUIDE_TEXT)
    _add_score_summary_table(document)
    spacer = document.add_paragraph()
    spacer.paragraph_format.line_spacing = 1.0
    spacer.paragraph_format.space_after = Pt(8)
    document.add_paragraph("注意事项：请在规定区域内作答，保持卷面整洁。", style="Exam Question")
    _add_section_header_row(document, "一、题目区")
    _add_control_marker_paragraph(document, MASTER_QUESTION_INSERT_MARKER)
    _add_control_marker_paragraph(document, MASTER_ANSWER_AREA_MARKER)

    for section in document.sections:
        _set_page_number_footer(section.first_page_footer)
        _set_page_number_footer(section.footer)


def _add_control_guide_paragraph(document: Document, text: str) -> None:
    document.add_paragraph(text, style="Exam Control Guide")


def _add_control_marker_paragraph(document: Document, text: str) -> None:
    document.add_paragraph(text, style="Exam Control Marker")


def _set_page_number_footer(footer) -> None:
    footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_para.text = ""
    footer_para.add_run("第 ")
    _add_field(footer_para, "PAGE")
    footer_para.add_run(" 页 / 共 ")
    _add_field(footer_para, "NUMPAGES")
    footer_para.add_run(" 页")


def _add_hidden_marker_paragraph(document: Document, text: str) -> None:
    paragraph = document.add_paragraph(style="Exam Muted")
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.0
    run = paragraph.add_run(text)
    run.font.hidden = True


def _add_sealed_zone_to_header(document: Document) -> None:
    """Place the sealing area in the first-page header only."""

    for section in document.sections:
        section.different_first_page_header_footer = True
        regular_header = section.header
        regular_header.is_linked_to_previous = False
        if regular_header.paragraphs:
            regular_header.paragraphs[0].text = ""

        header = section.first_page_header
        header.is_linked_to_previous = False

        if _copy_reference_sealed_header(header._element):
            continue

        paragraph = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        paragraph.text = ""
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.0
        run = etree.SubElement(paragraph._element, qn("w:r"))
        pict = etree.SubElement(run, qn("w:pict"))
        if not _append_reference_sealed_zone(pict):
            _append_fallback_sealed_zone(pict)


def _copy_reference_sealed_header(header_element) -> bool:
    """Copy the complete manually verified v10 first-page header XML."""

    reference_path = BUILTIN_EXAM_MASTER_DIR / "default_exam_v10.docx"
    if not reference_path.exists():
        return False

    try:
        with ZipFile(reference_path) as archive:
            header_names = [
                name
                for name in archive.namelist()
                if name.startswith("word/header") and name.endswith(".xml")
            ]
            for header_name in header_names:
                xml_bytes = archive.read(header_name)
                if b"ExamSeal" not in xml_bytes and b"rotation:-5898240f" not in xml_bytes:
                    continue

                root = etree.fromstring(xml_bytes)
                if not _reference_header_has_sealed_zone(root):
                    continue

                for child in list(header_element):
                    header_element.remove(child)
                for name, value in root.attrib.items():
                    header_element.set(name, value)
                for child in root:
                    header_element.append(deepcopy(child))
                return True
    except (BadZipFile, KeyError, OSError, etree.XMLSyntaxError):
        return False

    return False


def _reference_header_has_sealed_zone(root) -> bool:
    xml = etree.tostring(root, encoding="unicode")
    return "ExamSeal" in xml and "rotation:-5898240f" in xml


def _append_reference_sealed_zone(pict) -> bool:
    """Fallback: copy v10 VML elements when complete header replacement fails."""

    reference_path = BUILTIN_EXAM_MASTER_DIR / "default_exam_v10.docx"
    if not reference_path.exists():
        return False

    try:
        with ZipFile(reference_path) as archive:
            header_names = [
                name
                for name in archive.namelist()
                if name.startswith("word/header") and name.endswith(".xml")
            ]
            for header_name in header_names:
                xml_bytes = archive.read(header_name)
                if b"ExamSeal" not in xml_bytes and b"rotation:-5898240f" not in xml_bytes:
                    continue

                root = etree.fromstring(xml_bytes)
                copied = False
                for element in root.iter():
                    if not _is_reference_seal_element(element):
                        continue
                    pict.append(deepcopy(element))
                    copied = True
                if copied:
                    return True
    except (BadZipFile, KeyError, OSError, etree.XMLSyntaxError):
        return False

    return False


def _is_reference_seal_element(element) -> bool:
    if element.tag not in {
        f"{{{VML_NS}}}shape",
        f"{{{VML_NS}}}line",
    }:
        return False
    shape_id = element.get("id", "")
    style = element.get("style", "")
    return "ExamSeal" in shape_id or "rotation:-5898240f" in style


def _append_fallback_sealed_zone(pict) -> None:
    """Fallback for clean installs without the v10 reference master file."""

    _append_vml_rotated_textbox(
        pict,
        "ExamSealTextLine",
        margin_left="-451.1pt",
        margin_top="300.35pt",
        width="847.25pt",
        height="27.4pt",
        z_index="251662336",
        text=(
            "密封线········密封线········密封线········密封线········"
            "密封线········密封线········密封线········密封线········"
            "密封线········密封线"
        ),
        font_size_half_points="20",
        bold=True,
    )
    _append_vml_rotated_textbox(
        pict,
        "ExamSealFieldLine",
        margin_left="-343.2pt",
        margin_top="317.65pt",
        width="578.25pt",
        height="25.8pt",
        z_index="251661312",
        text="学校：_____________  班级：_____________  学号：_____________  姓名：_____________",
        font_size_half_points="21",
    )


def _append_vml_line(
    pict,
    shape_id: str,
    *,
    margin_left: str,
    margin_top: str,
    from_point: str,
    to_point: str,
    dashed: bool,
    weight: str,
) -> None:
    line = etree.SubElement(pict, f"{{{VML_NS}}}line")
    line.set("id", shape_id)
    line.set("from", from_point)
    line.set("to", to_point)
    line.set(
        "style",
        "position:absolute;"
        f"margin-left:{margin_left};"
        f"margin-top:{margin_top};"
        "mso-position-horizontal:absolute;"
        "mso-position-horizontal-relative:page;"
        "mso-position-vertical:absolute;"
        "mso-position-vertical-relative:page;"
        "z-index:251654144;",
    )
    line.set(f"{{{OFFICE_NS}}}allowincell", "f")
    line.set("strokecolor", "#000000")
    line.set("strokeweight", weight)
    if dashed:
        stroke = etree.SubElement(line, f"{{{VML_NS}}}stroke")
        stroke.set("dashstyle", "dot")


def _append_vml_textbox(
    pict,
    shape_id: str,
    *,
    margin_left: str,
    margin_top: str,
    width: str,
    height: str,
    lines: tuple[str, ...],
    font_size_half_points: str = "24",
    line_spacing: str = "300",
) -> None:
    shape = etree.SubElement(pict, f"{{{VML_NS}}}shape")
    shape.set("id", shape_id)
    shape.set("title", "Exam sealed-zone labels")
    shape.set("type", "#_x0000_t202")
    shape.set(
        "style",
        "position:absolute;"
        f"margin-left:{margin_left};"
        f"margin-top:{margin_top};"
        f"width:{width};"
        f"height:{height};"
        "mso-position-horizontal:absolute;"
        "mso-position-horizontal-relative:page;"
        "mso-position-vertical:absolute;"
        "mso-position-vertical-relative:page;"
        "z-index:251654145;",
    )
    shape.set(f"{{{OFFICE_NS}}}allowincell", "f")
    shape.set("stroked", "f")
    shape.set("filled", "f")

    text_box = etree.SubElement(shape, f"{{{VML_NS}}}textbox")
    text_box.set("inset", "0,0,0,0")
    content = etree.SubElement(text_box, qn("w:txbxContent"))
    for line in lines:
        _append_vml_textbox_paragraph(
            content,
            line,
            font_size_half_points=font_size_half_points,
            line_spacing=line_spacing,
        )


def _append_vml_rotated_textbox(
    pict,
    shape_id: str,
    *,
    margin_left: str,
    margin_top: str,
    width: str,
    height: str,
    z_index: str,
    text: str,
    font_size_half_points: str,
    bold: bool = False,
) -> None:
    shape = etree.SubElement(pict, f"{{{VML_NS}}}shape")
    shape.set("id", shape_id)
    shape.set("title", "Exam first-page sealed zone")
    shape.set("type", "#_x0000_t202")
    shape.set(
        "style",
        "position:absolute;"
        "left:0pt;"
        f"margin-left:{margin_left};"
        f"margin-top:{margin_top};"
        f"height:{height};"
        f"width:{width};"
        "rotation:-5898240f;"
        "mso-position-horizontal:absolute;"
        "mso-position-horizontal-relative:page;"
        "mso-position-vertical:absolute;"
        "mso-position-vertical-relative:page;"
        f"z-index:{z_index};"
        "mso-width-relative:page;"
        "mso-height-relative:page;",
    )
    shape.set(f"{{{OFFICE_NS}}}allowincell", "f")
    shape.set("stroked", "f")
    shape.set("filled", "f")

    text_box = etree.SubElement(shape, f"{{{VML_NS}}}textbox")
    text_box.set("inset", "0,0,0,0")
    content = etree.SubElement(text_box, qn("w:txbxContent"))
    _append_vml_textbox_paragraph(
        content,
        text,
        font_size_half_points=font_size_half_points,
        line_spacing="240",
        bold=bold,
    )


def _append_vml_textbox_paragraph(
    parent,
    text: str,
    *,
    font_size_half_points: str,
    line_spacing: str,
    bold: bool = False,
) -> None:
    paragraph = etree.SubElement(parent, qn("w:p"))
    p_pr = etree.SubElement(paragraph, qn("w:pPr"))
    jc = etree.SubElement(p_pr, qn("w:jc"))
    jc.set(qn("w:val"), "center")
    spacing = etree.SubElement(p_pr, qn("w:spacing"))
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), line_spacing)
    spacing.set(qn("w:lineRule"), "auto")

    run = etree.SubElement(paragraph, qn("w:r"))
    r_pr = etree.SubElement(run, qn("w:rPr"))
    fonts = etree.SubElement(r_pr, qn("w:rFonts"))
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(key), "宋体")
    size = etree.SubElement(r_pr, qn("w:sz"))
    size.set(qn("w:val"), font_size_half_points)
    if bold:
        etree.SubElement(r_pr, qn("w:b"))
        etree.SubElement(r_pr, qn("w:bCs"))
    text_node = etree.SubElement(run, qn("w:t"))
    if not text:
        text_node.set(qn("xml:space"), "preserve")
        text_node.text = " "
    else:
        text_node.text = text


def _add_score_summary_table(container) -> None:
    labels = ("题号", "一", "二", "三", "四", "五", "六", "总分")
    widths = (1.6, 2.05, 2.05, 2.05, 2.05, 2.05, 2.05, 1.9)
    table = container.add_table(rows=2, cols=len(labels))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _set_table_grid(table, widths)
    _set_table_borders(table)
    for column_index, label in enumerate(labels):
        _format_table_cell(table.cell(0, column_index), label, widths[column_index], bold=True)
        _format_table_cell(
            table.cell(1, column_index),
            "分数" if column_index == 0 else "",
            widths[column_index],
            bold=column_index == 0,
        )
    spacer = container.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)
    spacer.paragraph_format.line_spacing = 1.0


def _add_section_header_row(container, title: str) -> Table:
    row = _add_table_for_container(
        container,
        rows=1,
        cols=2,
        width_cm=SECTION_SCORE_CELL_WIDTH_CM + SECTION_TITLE_CELL_WIDTH_CM,
    )
    row.autofit = False
    row.alignment = WD_TABLE_ALIGNMENT.LEFT
    _set_table_grid(row, (SECTION_SCORE_CELL_WIDTH_CM, SECTION_TITLE_CELL_WIDTH_CM))
    _clear_table_borders(row)
    score_cell = row.cell(0, 0)
    title_cell = row.cell(0, 1)
    _set_cell_width(score_cell, SECTION_SCORE_CELL_WIDTH_CM)
    _set_cell_width(title_cell, SECTION_TITLE_CELL_WIDTH_CM)
    score_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    title_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _set_cell_margins(score_cell, top=0, bottom=0, start=0, end=0)
    _set_cell_margins(title_cell, top=0, bottom=0, start=120, end=0)
    _clear_cell(score_cell)
    _clear_cell(title_cell)
    _add_section_score_box(score_cell)
    paragraph = title_cell.add_paragraph(title, style="Exam Section Heading")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.0
    return row


def _add_table_for_container(container, *, rows: int, cols: int, width_cm: float) -> Table:
    try:
        return container.add_table(rows=rows, cols=cols)
    except TypeError:
        return container.add_table(rows=rows, cols=cols, width=Cm(width_cm))


def _add_section_score_box(container) -> None:
    table = container.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    _set_table_grid(table, (1.2, 1.85))
    _set_table_borders(table)
    _format_table_cell(table.cell(0, 0), "得分", 1.2, bold=True)
    _format_table_cell(table.cell(0, 1), "", 1.85)


def _format_table_cell(
    cell,
    text: str,
    width_cm: float,
    *,
    bold: bool = False,
) -> None:
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _set_cell_width(cell, width_cm)
    _set_cell_margins(cell, top=80, bottom=80, start=120, end=120)
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.text = ""
    run = paragraph.add_run(text)
    _set_run_font(run, "宋体", 10.5, bold=bold)


def _set_table_borders(
    table,
    *,
    size: str = "6",
    color: str = "000000",
) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def _clear_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "nil")


def _set_cell_border(
    cell,
    edge: str,
    *,
    val: str = "single",
    size: str = "6",
    color: str = "000000",
) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    tag = f"w:{edge}"
    element = borders.find(qn(tag))
    if element is None:
        element = OxmlElement(tag)
        borders.append(element)
    element.set(qn("w:val"), val)
    element.set(qn("w:sz"), size)
    element.set(qn("w:space"), "0")
    element.set(qn("w:color"), color)


def _set_cell_margins(
    cell,
    *,
    top: int = 0,
    bottom: int = 0,
    start: int = 0,
    end: int = 0,
) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for edge, value in (("top", top), ("bottom", bottom), ("start", start), ("end", end)):
        element = margins.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            margins.append(element)
        element.set(qn("w:w"), str(value))
        element.set(qn("w:type"), "dxa")


def _set_paragraph_bottom_border(
    paragraph: Paragraph,
    *,
    color: str = "BFBFBF",
) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)
    bottom = borders.find(qn("w:bottom"))
    if bottom is None:
        bottom = OxmlElement("w:bottom")
        borders.append(bottom)
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)


def _set_table_indent(table: Table, indent_cm: float) -> None:
    tbl_pr = table._tbl.tblPr
    tbl_ind = tbl_pr.first_child_found_in("w:tblInd")
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(int(indent_cm * 567)))
    tbl_ind.set(qn("w:type"), "dxa")


def _set_table_grid(table, widths_cm: tuple[float, ...]) -> None:
    widths_dxa = [int(width * 567) for width in widths_cm]
    total_width = sum(widths_dxa)
    table.autofit = False
    tbl = table._tbl
    tbl_pr = tbl.tblPr

    tbl_w = tbl_pr.first_child_found_in("w:tblW")
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(total_width))
    tbl_w.set(qn("w:type"), "dxa")

    layout = tbl_pr.first_child_found_in("w:tblLayout")
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")

    tbl_grid = tbl.tblGrid
    if tbl_grid is None:
        tbl_grid = OxmlElement("w:tblGrid")
        tbl.insert(1, tbl_grid)
    for child in list(tbl_grid):
        tbl_grid.remove(child)
    for width in widths_dxa:
        grid_col = OxmlElement("w:gridCol")
        grid_col.set(qn("w:w"), str(width))
        tbl_grid.append(grid_col)

    for row in table.rows:
        for cell, width in zip(row.cells, widths_dxa):
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.tcW
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")


def _set_cell_width(cell, width_cm: float) -> None:
    cell.width = Cm(width_cm)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.tcW
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(int(width_cm * 567)))
    tc_w.set(qn("w:type"), "dxa")


def _clear_cell(cell) -> None:
    for paragraph in list(cell.paragraphs):
        _remove_paragraph(paragraph)


def _prepare_master_as_student_sample(document: Document, spec: ExamBlankStyleSpec) -> None:
    _write_exam_payload_into_master(document, spec, EXAM_SAMPLE_PAYLOAD)


def _write_exam_payload_into_master(
    document: Document,
    spec: ExamBlankStyleSpec,
    payload: Mapping[str, object],
) -> None:
    _remove_master_control_guides(document)
    _replace_any_text(
        document,
        (MASTER_TITLE_PLACEHOLDER, *LEGACY_MASTER_TITLE_PLACEHOLDERS),
        _exam_payload_title(payload),
    )
    _replace_master_subtitle(document, spec, "学生卷")
    _replace_any_text(
        document,
        (MASTER_SUBJECT_PLACEHOLDER, *LEGACY_MASTER_SUBJECT_PLACEHOLDERS),
        f"科目：{_payload_text(payload, ('subject', '科目'))}",
    )
    _replace_any_text(
        document,
        (MASTER_GRADE_PLACEHOLDER, *LEGACY_MASTER_GRADE_PLACEHOLDERS),
        f"年级：{_payload_text(payload, ('grade', '年级'))}",
    )
    _replace_any_text(
        document,
        (MASTER_DURATION_PLACEHOLDER, *LEGACY_MASTER_DURATION_PLACEHOLDERS),
        f"考试时间：{_payload_text(payload, ('duration', 'time', '考试时间'))}",
    )
    _replace_any_text(
        document,
        (MASTER_TOTAL_SCORE_PLACEHOLDER, *LEGACY_MASTER_TOTAL_SCORE_PLACEHOLDERS),
        f"满分：{_payload_text(payload, ('total_score', 'score', '满分'))}",
    )
    _remove_master_question_placeholder_rows(document)

    marker = _find_any_paragraph(
        document,
        (MASTER_QUESTION_INSERT_MARKER, *LEGACY_MASTER_QUESTION_MARKERS),
    )
    if marker is None:
        last = document.paragraphs[-1] if document.paragraphs else document.add_paragraph()
    else:
        last = marker
    last = _insert_exam_payload_questions_after(last, spec, payload)

    if marker is not None:
        _remove_paragraph(marker)
    _remove_paragraphs_with_exact_text(document, MASTER_ANSWER_AREA_MARKER)
    for marker_text in LEGACY_MASTER_ANSWER_AREA_MARKERS:
        _remove_paragraphs_with_exact_text(document, marker_text)


def _remove_master_control_guides(document: Document) -> None:
    for paragraph in list(_iter_paragraphs(document)):
        if (
            paragraph.text.strip() in MASTER_CONTROL_GUIDE_TEXTS
            or getattr(getattr(paragraph, "style", None), "name", "") == "Exam Control Guide"
        ):
            _remove_paragraph(paragraph)


def _insert_student_questions_after(paragraph: Paragraph, spec: ExamBlankStyleSpec) -> Paragraph:
    return _insert_exam_payload_questions_after(paragraph, spec, EXAM_SAMPLE_PAYLOAD)


def _insert_exam_payload_questions_after(
    paragraph: Paragraph,
    spec: ExamBlankStyleSpec,
    payload: Mapping[str, object],
) -> Paragraph:
    current_block: Paragraph | Table = paragraph
    current_paragraph = paragraph
    for section_index, section in enumerate(_exam_payload_sections(payload), start=1):
        section_row = _insert_section_header_row_after(
            current_block,
            paragraph._parent,
            _section_title(section, section_index),
        )
        current_block = section_row
        for question_number, question in enumerate(_section_questions(section), start=1):
            current_paragraph = _insert_paragraph_after_block(
                current_block,
                _student_question_line(question_number, question),
                "Exam Question Stem",
            )
            current_block = current_paragraph
            for option in _question_options(question):
                current_paragraph = _insert_paragraph_after_block(current_block, option, "Exam Option")
                current_block = current_paragraph
            figure_block, figure_paragraph = _insert_question_figures_after_block(
                current_block,
                question,
            )
            current_block = figure_block
            if figure_paragraph is not None:
                current_paragraph = figure_paragraph
            answer_area_kind, answer_area_lines = _question_answer_area(
                question,
                section,
                payload,
            )
            if answer_area_kind == "lines":
                for _ in range(answer_area_lines):
                    current_paragraph = _insert_paragraph_after_block(
                        current_block,
                        " ",
                        "Exam Answer Space",
                    )
                    _set_paragraph_bottom_border(current_paragraph)
                    current_block = current_paragraph
            elif answer_area_kind == "free":
                current_block = _insert_free_answer_area_after_block(
                    current_block,
                    paragraph._parent,
                    answer_area_lines,
                )
    return current_paragraph


def _add_answer_version(
    document: Document,
    spec: ExamBlankStyleSpec,
    payload: Mapping[str, object] | None = None,
) -> None:
    exam_payload = payload or EXAM_SAMPLE_PAYLOAD
    _add_exam_header(document, "答案速查", spec, exam_payload, include_notice=False)
    for section_index, section in enumerate(_exam_payload_sections(exam_payload), start=1):
        document.add_paragraph(_section_title(section, section_index), style="Exam Section Heading")
        for question_number, question in enumerate(_section_questions(section), start=1):
            document.add_paragraph(_answer_key_line(question_number, question), style="Exam Question")


def _add_exam_header(
    document: Document,
    version_label: str,
    spec: ExamBlankStyleSpec,
    payload: Mapping[str, object] | None = None,
    *,
    include_notice: bool = True,
) -> None:
    exam_payload = payload or EXAM_SAMPLE_PAYLOAD
    title = document.add_paragraph(_exam_payload_title(exam_payload), style="Exam Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    version = document.add_paragraph(version_label, style="Exam Subtitle")
    version.alignment = WD_ALIGN_PARAGRAPH.CENTER
    metadata = _exam_payload_metadata_line(exam_payload)
    if metadata:
        document.add_paragraph(metadata, style="Exam Metadata")
    notice = _payload_text(exam_payload, ("notice", "instructions", "注意事项"))
    if include_notice and notice:
        document.add_paragraph(f"注意事项：{notice}", style="Exam Question")


def _remove_master_question_placeholder_rows(document: Document) -> None:
    for table in list(document.tables):
        if _is_master_question_placeholder_row(table):
            _remove_table(table)


def _is_master_question_placeholder_row(table: Table) -> bool:
    if len(table.rows) != 1 or len(table.columns) != 2:
        return False
    title_text = table.cell(0, 1).text.strip()
    return title_text == "一、题目区"


def _remove_table(table: Table) -> None:
    element = table._tbl
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _insert_section_header_row_after(
    anchor: Paragraph | Table,
    container,
    title: str,
) -> Table:
    table = _add_section_header_row(container, title)
    anchor_element = anchor._p if isinstance(anchor, Paragraph) else anchor._tbl
    anchor_element.addnext(table._tbl)
    return table


def _insert_free_answer_area_after_block(
    anchor: Paragraph | Table,
    container,
    line_count: int,
) -> Table:
    width_cm = max(
        6.0,
        SECTION_SCORE_CELL_WIDTH_CM + SECTION_TITLE_CELL_WIDTH_CM - ANSWER_AREA_LEFT_INDENT_CM,
    )
    table = _add_table_for_container(container, rows=1, cols=1, width_cm=width_cm)
    anchor_element = anchor._p if isinstance(anchor, Paragraph) else anchor._tbl
    anchor_element.addnext(table._tbl)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    _set_table_grid(table, (width_cm,))
    _set_table_indent(table, ANSWER_AREA_LEFT_INDENT_CM)
    _set_table_borders(table, size="4", color="BFBFBF")
    row = table.rows[0]
    row.height = Cm(_free_answer_area_height_cm(line_count))
    row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    cell = table.cell(0, 0)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    _set_cell_width(cell, width_cm)
    _set_cell_margins(cell, top=100, bottom=100, start=120, end=120)
    _clear_cell(cell)
    paragraph = cell.add_paragraph("", style="Exam Free Answer Area")
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.space_after = Pt(0)
    return table


def _student_question_line(number: int, question: Mapping[str, object]) -> str:
    stem = _question_stem(question)
    score = _question_score(question)
    suffix = f"（{score} 分）" if score else ""
    return f"{number}. {stem}{suffix}"


def _answer_key_line(number: int, question: Mapping[str, object]) -> str:
    answer = _question_answer(question) or "待补充"
    return f"{number}. {answer}"


def _question_answer_area(
    question: Mapping[str, object],
    section: Mapping[str, object],
    payload: Mapping[str, object],
) -> tuple[str, int]:
    explicit_kind = _explicit_answer_area_kind(question)
    explicit_lines = _explicit_answer_space_lines(question)
    if explicit_kind == "none":
        return "none", 0
    if explicit_kind == "free":
        return "free", _free_answer_area_lines(question, explicit_lines)
    if explicit_kind == "lines":
        lines = explicit_lines if explicit_lines is not None else _question_answer_space_lines(question, section)
        return ("lines", lines) if lines else ("none", 0)

    if _question_options(question):
        return "none", 0

    question_type = _question_type_text(question, section)
    if _looks_like_choice_type(question_type):
        return "none", 0

    stem = _question_stem(question)
    if _stem_has_inline_answer_blank(stem):
        return "none", 0

    subject = _payload_text(payload, ("subject", "科目"))
    if _looks_like_free_answer_response(question_type, stem, subject):
        return "free", _free_answer_area_lines(question, explicit_lines)

    lines = explicit_lines if explicit_lines is not None else _question_answer_space_lines(question, section)
    return ("lines", lines) if lines else ("none", 0)


def _explicit_answer_area_kind(question: Mapping[str, object]) -> str:
    for key in ANSWER_AREA_KIND_KEYS:
        kind = _normalize_answer_area_kind(question.get(key))
        if kind:
            return kind
    for key in ("answer_area", "response_area"):
        value = question.get(key)
        if isinstance(value, Mapping):
            kind = _normalize_answer_area_kind(value.get("kind") or value.get("type"))
            if kind:
                return kind
    return ""


def _normalize_answer_area_kind(value: object) -> str:
    text = str(value or "").strip().casefold()
    if not text:
        return ""
    if text in {"none", "no", "false", "0", "无", "不留", "不预留"}:
        return "none"
    if text in {"line", "lines", "text", "ruled", "横线", "答题行", "文本"}:
        return "lines"
    if text in {
        "free",
        "box",
        "blank",
        "space",
        "process",
        "calculation",
        "solution",
        "grid",
        "自由",
        "自由答题区",
        "演算",
        "演算区",
        "计算",
        "解答区",
    }:
        return "free"
    return ""


def _question_answer_space_lines(
    question: Mapping[str, object],
    section: Mapping[str, object],
) -> int:
    explicit = _explicit_answer_space_lines(question)
    if explicit is not None:
        return explicit
    if _question_options(question):
        return 0

    question_type = _question_type_text(question, section)
    if _looks_like_choice_type(question_type):
        return 0

    stem = _question_stem(question)
    if _stem_has_inline_answer_blank(stem) and not _looks_like_extended_text_response(question_type, stem):
        return 0

    score = _question_score_number(question)
    lines = _score_based_answer_space_lines(score)
    if _looks_like_extended_text_response(question_type, stem):
        lines = max(lines, 5)
    return lines


def _explicit_answer_space_lines(question: Mapping[str, object]) -> int | None:
    for key in ANSWER_SPACE_LINE_KEYS:
        value = question.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            return ANSWER_SPACE_DEFAULT_LINES if value else 0
        try:
            return _clamp_answer_space_lines(int(float(str(value).strip())))
        except (TypeError, ValueError):
            continue
    for key in ("answer_area", "response_area"):
        value = question.get(key)
        if isinstance(value, Mapping):
            for line_key in ("lines", "height_lines", "rows", "line_count"):
                line_value = value.get(line_key)
                if line_value is None:
                    continue
                try:
                    return _clamp_answer_space_lines(int(float(str(line_value).strip())))
                except (TypeError, ValueError):
                    continue
    return None


def _question_type_text(question: Mapping[str, object], section: Mapping[str, object]) -> str:
    return " ".join(
        value
        for value in (
            _payload_text(question, ("type", "question_type", "题型")),
            _payload_text(section, ("type", "question_type", "题型")),
        )
        if value
    ).casefold()


def _looks_like_choice_type(question_type: str) -> bool:
    return any(
        keyword in question_type
        for keyword in (
            "choice",
            "single",
            "multiple",
            "select",
            "选择",
            "单选",
            "多选",
            "判断",
        )
    )


def _looks_like_extended_text_response(question_type: str, stem: str) -> bool:
    text = f"{question_type} {stem}".casefold()
    return any(
        keyword in text
        for keyword in (
            "essay",
            "composition",
            "writing",
            "作文",
            "写作",
            "表达",
            "不少于",
            "片段",
            "论述",
        )
    )


def _looks_like_free_answer_response(question_type: str, stem: str, subject: str) -> bool:
    text = f"{question_type} {stem} {subject}".casefold()
    if _looks_like_math_or_science_subject(subject) and not _looks_like_extended_text_response(question_type, stem):
        return True
    return any(
        keyword in text
        for keyword in (
            "calculation",
            "calculate",
            "solution",
            "solve",
            "proof",
            "prove",
            "geometry",
            "application_problem",
            "计算",
            "解答",
            "证明",
            "推导",
            "演算",
            "列式",
            "解方程",
            "解不等式",
            "几何",
            "作图",
            "应用题",
        )
    )


def _looks_like_math_or_science_subject(subject: str) -> bool:
    text = str(subject or "").casefold()
    return any(keyword in text for keyword in ("math", "数学", "物理", "化学"))


def _stem_has_inline_answer_blank(stem: str) -> bool:
    compact = stem.replace(" ", "")
    return (
        "____" in stem
        or "________" in stem
        or "（　　）" in stem
        or "（）" in compact
        or "(    )" in stem
    )


def _score_based_answer_space_lines(score: float | None) -> int:
    if score is None:
        return ANSWER_SPACE_DEFAULT_LINES
    return _clamp_answer_space_lines(int((score + 3) // 4) or 1)


def _free_answer_area_lines(
    question: Mapping[str, object],
    explicit_lines: int | None,
) -> int:
    if explicit_lines is not None:
        return _clamp_answer_space_lines(max(ANSWER_FREE_AREA_MIN_LINES, explicit_lines))
    score = _question_score_number(question)
    if score is None:
        return ANSWER_FREE_AREA_DEFAULT_LINES
    return _clamp_answer_space_lines(max(ANSWER_FREE_AREA_MIN_LINES, int((score + 1) // 2) or 1))


def _free_answer_area_height_cm(line_count: int) -> float:
    return max(2.4, _clamp_answer_space_lines(line_count) * 0.72)


def _question_score_number(question: Mapping[str, object]) -> float | None:
    raw_score = _question_score(question)
    if not raw_score:
        return None
    number_text = "".join(ch for ch in str(raw_score) if ch.isdigit() or ch == ".")
    if not number_text:
        return None
    try:
        return float(number_text)
    except ValueError:
        return None


def _clamp_answer_space_lines(value: int) -> int:
    return max(0, min(ANSWER_SPACE_MAX_LINES, value))


def _sample_sections() -> Iterable[dict[str, object]]:
    return EXAM_SAMPLE_PAYLOAD["sections"]  # type: ignore[return-value]


def _exam_payload_title(payload: Mapping[str, object]) -> str:
    return _payload_text(payload, ("title", "paper_title", "name", "试卷标题"), fallback="试卷")


def _exam_payload_metadata_line(payload: Mapping[str, object]) -> str:
    items = [
        ("科目", _payload_text(payload, ("subject", "科目"))),
        ("年级", _payload_text(payload, ("grade", "年级"))),
        ("考试时间", _payload_text(payload, ("duration", "time", "考试时间"))),
        ("满分", _payload_text(payload, ("total_score", "score", "满分"))),
    ]
    return "    ".join(f"{label}：{value}" for label, value in items if value)


def _exam_payload_sections(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw_sections = payload.get("sections")
    sections = _mapping_items(raw_sections)
    if sections:
        return sections
    questions = _section_questions(payload)
    if questions:
        return [{"title": "一、题目区", "questions": questions}]
    return []


def _section_title(section: Mapping[str, object], index: int) -> str:
    return _payload_text(section, ("title", "name", "heading"), fallback=f"{index}、题目区")


def _section_questions(section: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw_questions = (
        section.get("questions")
        or section.get("items")
        or section.get("children")
    )
    return _mapping_items(raw_questions, text_key="stem")


def _question_stem(question: Mapping[str, object]) -> str:
    return _payload_text(question, ("stem", "question", "content", "text"), fallback="题目内容待填写")


def _question_options(question: Mapping[str, object]) -> list[str]:
    raw_options = question.get("options") or question.get("choices")
    if isinstance(raw_options, Mapping):
        options = []
        for key, value in raw_options.items():
            key_text = str(key).strip()
            value_text = str(value).strip()
            if key_text and value_text:
                options.append(f"{key_text}. {value_text}")
            elif value_text:
                options.append(value_text)
        return options
    return [str(item).strip() for item in _iterable_items(raw_options) if str(item).strip()]


def _insert_question_figures_after_block(
    block: Paragraph | Table,
    question: Mapping[str, object],
) -> tuple[Paragraph | Table, Paragraph | None]:
    current_block: Paragraph | Table = block
    current_paragraph: Paragraph | None = None
    for figure in _question_figures(question):
        figure_path = _resolve_question_figure_path(figure)
        if figure_path is None:
            continue
        paragraph = _insert_paragraph_after_block(current_block, "", "Exam Question")
        try:
            inline_shape = paragraph.add_run().add_picture(str(figure_path), width=Cm(5.08))
        except Exception:
            continue
        alt_text = _question_figure_alt_text(figure)
        if alt_text:
            _set_inline_shape_alt_text(
                inline_shape,
                alt_text=alt_text,
                title=_question_figure_title(figure),
            )
        current_block = paragraph
        current_paragraph = paragraph
    return current_block, current_paragraph


def _question_figures(question: Mapping[str, object]) -> list[Mapping[str, object]]:
    figure = question.get("figure") or question.get("image")
    if figure is None or figure == "":
        return []
    if isinstance(figure, Mapping):
        figures = [figure]
    else:
        figures = _iterable_items(figure)
    return [item for item in figures if isinstance(item, Mapping)]


def _resolve_question_figure_path(figure: Mapping[str, object]) -> Path | None:
    raw_path = _payload_text(figure, ("path", "asset_path", "asset_id"))
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    candidates = [path] if path.is_absolute() else [path, Path.cwd() / path]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _question_figure_alt_text(figure: Mapping[str, object]) -> str:
    return _payload_text(figure, ("alt", "alt_text", "altText", "description", "caption"))


def _question_figure_title(figure: Mapping[str, object]) -> str:
    return _payload_text(figure, ("title", "caption", "asset_id", "source"))


def _set_inline_shape_alt_text(
    inline_shape,
    *,
    alt_text: str,
    title: str = "",
) -> None:
    doc_pr = getattr(getattr(inline_shape, "_inline", None), "docPr", None)
    if doc_pr is None:
        return
    doc_pr.set("descr", alt_text)
    if title:
        doc_pr.set("title", title)


def _question_answer(question: Mapping[str, object]) -> str:
    raw_answer = (
        question.get("answer")
        or question.get("answers")
        or question.get("correct_answer")
        or question.get("solution")
    )
    if isinstance(raw_answer, (list, tuple, set)):
        return "、".join(str(item).strip() for item in raw_answer if str(item).strip())
    return str(raw_answer or "").strip()


def _question_score(question: Mapping[str, object]) -> str:
    return _payload_text(question, ("score", "points", "分值"))


def _payload_text(
    payload: Mapping[str, object],
    keys: Iterable[str],
    *,
    fallback: str = "",
) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return fallback


def _mapping_items(value: object, *, text_key: str = "title") -> list[Mapping[str, object]]:
    if isinstance(value, Mapping):
        return [value]
    items = []
    for item in _iterable_items(value):
        if isinstance(item, Mapping):
            items.append(item)
        else:
            text = str(item).strip()
            if text:
                items.append({text_key: text})
    return items


def _iterable_items(value: object) -> list[object]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, IterableABC):
        return list(value)
    return []


def _find_custom_blank_style(
    config: ExamPaperConfig | None,
    style_id: str,
) -> ExamBlankStyleConfig | None:
    if config is None:
        return None
    target = str(style_id or "").strip()
    for style in getattr(config, "custom_blank_styles", []) or []:
        if style.style_id == target:
            return style
    return None


def _unique_imported_style_identity(
    config: ExamPaperConfig,
    requested_label: str,
) -> tuple[str, str]:
    existing_ids = {
        *BUILTIN_EXAM_BLANK_STYLE_IDS,
        *(
            str(style.style_id or "").strip()
            for style in getattr(config, "custom_blank_styles", []) or []
        ),
    }
    existing_labels = {
        str(style.label or "").strip()
        for style in getattr(config, "custom_blank_styles", []) or []
    }
    label_seed = _safe_stem(requested_label) or "导入试卷母版"
    index = 1
    while True:
        suffix = "" if index == 1 else f"_{index}"
        label_suffix = "" if index == 1 else f" {index}"
        style_id = f"user_imported_exam{suffix}"
        label = f"{label_seed}{label_suffix}"
        if style_id not in existing_ids and label not in existing_labels:
            return style_id, label
        index += 1


def _resolve_stored_master_path(value: str) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _stored_master_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def _unique_docx_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix or ".docx"
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def _docx_is_openable(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        Document(str(path))
    except Exception:
        return False
    return True


def _builtin_master_is_current(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        document = Document(str(path))
    except Exception:
        return False
    return document.core_properties.comments == BUILTIN_MASTER_VERSION


def _paragraph_style(document: Document, name: str):
    try:
        return document.styles[name]
    except KeyError:
        return document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)


def _set_style_font(
    style,
    font_name: str,
    size_pt: int | None = None,
    *,
    bold: bool | None = None,
    color: str | None = None,
) -> None:
    style.font.name = font_name
    if size_pt is not None:
        style.font.size = Pt(size_pt)
    if bold is not None:
        style.font.bold = bold
    if color:
        style.font.color.rgb = RGBColor.from_string(color)
    r_pr = style.element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        r_fonts.set(qn(key), font_name)


def _set_run_font(
    run,
    font_name: str,
    size_pt: float | int,
    *,
    bold: bool = False,
) -> None:
    run.bold = bold
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        r_fonts.set(qn(key), font_name)


def _add_field(paragraph: Paragraph, instruction: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    display = OxmlElement("w:t")
    display.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, display, end])


def _replace_text(document: Document, old: str, new: str) -> None:
    for paragraph in _iter_paragraphs(document):
        for run in paragraph.runs:
            if old in run.text:
                run.text = run.text.replace(old, new)


def _replace_any_text(document: Document, placeholders: Iterable[str], new: str) -> None:
    for placeholder in placeholders:
        value = str(placeholder or "")
        if value:
            _replace_text(document, value, new)


def _replace_master_subtitle(document: Document, spec: ExamBlankStyleSpec, version_label: str) -> None:
    replacement = version_label
    for paragraph in _iter_paragraphs(document):
        if (
            any(placeholder in paragraph.text for placeholder in (MASTER_SUBTITLE_PLACEHOLDER, *LEGACY_MASTER_SUBTITLE_PLACEHOLDERS))
            or "空白母版" in paragraph.text
        ):
            paragraph.text = replacement
            paragraph.style = "Exam Subtitle"


def _find_paragraph(document: Document, text: str) -> Paragraph | None:
    for paragraph in _iter_paragraphs(document):
        if paragraph.text == text:
            return paragraph
    return None


def _find_any_paragraph(document: Document, texts: Iterable[str]) -> Paragraph | None:
    targets = {str(text or "") for text in texts if str(text or "")}
    for paragraph in _iter_paragraphs(document):
        if paragraph.text in targets:
            return paragraph
    return None


def _remove_paragraphs_with_exact_text(document: Document, text: str) -> None:
    for paragraph in list(_iter_paragraphs(document)):
        if paragraph.text == text:
            _remove_paragraph(paragraph)


def _remove_paragraph(paragraph: Paragraph) -> None:
    element = paragraph._element
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _iter_paragraphs(parent):
    for paragraph in getattr(parent, "paragraphs", []):
        yield paragraph
    for table in getattr(parent, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_paragraphs(cell)


def _insert_paragraph_after(
    paragraph: Paragraph,
    text: str,
    style: str | None = None,
) -> Paragraph:
    return _insert_paragraph_after_block(paragraph, text, style)


def _insert_paragraph_after_block(
    block: Paragraph | Table,
    text: str,
    style: str | None = None,
) -> Paragraph:
    new_element = OxmlElement("w:p")
    if isinstance(block, Paragraph):
        block._p.addnext(new_element)
        parent = block._parent
    else:
        block._tbl.addnext(new_element)
        parent = block._parent
    new_paragraph = Paragraph(new_element, parent)
    if style:
        new_paragraph.style = style
    if text:
        new_paragraph.add_run(text)
    return new_paragraph


def _safe_stem(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(ch if ch not in forbidden else "_" for ch in str(value or "").strip())
    return cleaned.strip(" ._") or "默认试卷"


def _safe_docx_stem(value: str) -> str:
    raw = str(value or "").strip()
    if raw.lower().endswith(".docx"):
        raw = Path(raw).stem
    return _safe_stem(raw)


__all__ = [
    "BUILTIN_EXAM_BLANK_STYLE_IDS",
    "BUILTIN_EXAM_MASTER_DIR",
    "ExamPaperDocxOutputs",
    "EXAM_AI_PROMPT_OPTIONS",
    "EXAM_MARKDOWN_AUTHORING_PROMPT",
    "EXAM_MASTER_CONVERSION_PROMPT",
    "EXAM_MASTER_ROOT",
    "EXAM_SAMPLE_PAYLOAD",
    "USER_EXAM_MASTER_DIR",
    "ExamBlankStyleSpec",
    "builtin_exam_blank_style_options",
    "create_exam_blank_master_copy",
    "create_exam_blank_style_copy",
    "ensure_builtin_exam_master_docx",
    "ensure_builtin_exam_master_files",
    "ensure_current_exam_blank_master_docx",
    "exam_ai_prompt_text",
    "exam_blank_style_label",
    "exam_blank_style_options",
    "exam_blank_style_preview_lines",
    "import_exam_blank_master_docx",
    "resolve_exam_blank_style",
    "write_exam_blank_master_docx",
    "write_exam_blank_style_sample_docx",
    "write_exam_answer_key_docx",
    "write_exam_paper_docx",
    "write_exam_paper_docx_files",
]
