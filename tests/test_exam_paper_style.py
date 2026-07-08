from zipfile import ZipFile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn

from src.config.scene import ExamBlankStyleConfig, ExamPaperConfig
from src.shared.engine.exam_paper_style import (
    EXAM_MARKDOWN_AUTHORING_PROMPT,
    EXAM_MASTER_CONVERSION_PROMPT,
    create_exam_blank_master_copy,
    create_exam_blank_style_copy,
    ensure_builtin_exam_master_docx,
    ensure_current_exam_blank_master_docx,
    exam_blank_style_label,
    exam_blank_style_preview_lines,
    import_exam_blank_master_docx,
    write_exam_blank_master_docx,
    write_exam_blank_style_sample_docx,
    write_exam_paper_docx,
    write_exam_paper_docx_files,
)


def _all_docx_text(document: Document) -> str:
    paragraphs = []

    def collect(parent) -> None:
        paragraphs.extend(paragraph.text for paragraph in getattr(parent, "paragraphs", []))
        for table in getattr(parent, "tables", []):
            for row in table.rows:
                for cell in row.cells:
                    collect(cell)

    collect(document)
    return "\n".join(paragraphs)


def _sealed_header_xml_from_package(path) -> str:
    with ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.startswith("word/header") or not name.endswith(".xml"):
                continue
            xml = archive.read(name).decode("utf-8")
            if "ExamSeal" in xml and "rotation:-5898240f" in xml:
                return xml
    raise AssertionError("sealed first-page header XML not found")


def test_exam_blank_style_copy_is_scene_owned_and_selectable():
    config = ExamPaperConfig()

    copied = create_exam_blank_style_copy(config, "default_exam")
    config.custom_blank_styles.append(copied)
    config.blank_style_id = copied.style_id
    normalized = ExamPaperConfig(
        blank_style_id=config.blank_style_id,
        custom_blank_styles=[
            {
                "style_id": copied.style_id,
                "label": copied.label,
                "base_style_id": copied.base_style_id,
            }
        ],
    )

    assert normalized.blank_style_id == copied.style_id
    assert normalized.custom_blank_styles == [
        ExamBlankStyleConfig(
            style_id=copied.style_id,
            label=copied.label,
            base_style_id="default_exam",
        )
    ]
    assert exam_blank_style_label(copied.style_id, normalized) == copied.label


def test_exam_blank_master_copy_creates_scene_owned_docx(tmp_path):
    config = ExamPaperConfig()

    copied = create_exam_blank_master_copy(
        config,
        "default_exam",
        output_dir=tmp_path / "masters",
    )
    config.custom_blank_styles.append(copied)
    config.blank_style_id = copied.style_id

    path = ensure_current_exam_blank_master_docx(config, copied.style_id)
    assert path.exists()
    assert path.parent == tmp_path / "masters"
    assert copied.master_docx_path
    text = _all_docx_text(Document(path))
    assert "{{af_title}}" in text
    assert "{{af_questions}}" in text


def test_import_exam_blank_master_docx_copies_existing_word_master(tmp_path):
    source_path = tmp_path / "学校常用试卷母版.docx"
    source = Document()
    source.add_paragraph("学校常用母版标识")
    source.save(source_path)

    config = ExamPaperConfig()
    imported = import_exam_blank_master_docx(
        config,
        source_path,
        output_dir=tmp_path / "masters",
    )
    config.custom_blank_styles.append(imported)
    config.blank_style_id = imported.style_id

    stored_path = ensure_current_exam_blank_master_docx(config, imported.style_id)
    assert imported.style_id == "user_imported_exam"
    assert imported.label == "学校常用试卷母版"
    assert stored_path.parent == tmp_path / "masters"
    assert stored_path.exists()
    assert source_path.exists()
    assert "学校常用母版标识" in _all_docx_text(Document(stored_path))

    sample_path = write_exam_blank_style_sample_docx(
        imported.style_id,
        tmp_path / "samples",
        config=config,
    )
    assert "学校常用母版标识" in _all_docx_text(Document(sample_path))


def test_exam_blank_style_preview_switches_student_and_answer_versions():
    student_lines = "\n".join(exam_blank_style_preview_lines("default_exam"))
    answer_lines = "\n".join(
        exam_blank_style_preview_lines("default_exam", answer_version=True)
    )

    assert "学生卷：答案与解析不显示" not in student_lines
    assert "答案速查" not in student_lines
    assert "下列词语中加点字读音" in student_lines
    assert "答案速查" in answer_lines
    assert "1. C" in answer_lines
    assert "2. 按表达评分" in answer_lines
    assert "注意事项" not in answer_lines
    assert "下列词语中加点字读音" not in answer_lines
    assert "阅读材料，概括文章" not in answer_lines


def test_exam_ai_prompts_separate_content_and_master_responsibilities():
    assert "只输出 Markdown 正文" in EXAM_MARKDOWN_AUTHORING_PROMPT
    assert "不要编写页眉、页脚、页码、密封线" in EXAM_MARKDOWN_AUTHORING_PROMPT
    assert "## 答案速查" in EXAM_MARKDOWN_AUTHORING_PROMPT
    assert "answer_area_kind" in EXAM_MARKDOWN_AUTHORING_PROMPT
    assert "数学计算/解答/证明" in EXAM_MARKDOWN_AUTHORING_PROMPT
    assert "{{af_questions}}" not in EXAM_MARKDOWN_AUTHORING_PROMPT

    assert "Word 试卷模板工程师" in EXAM_MASTER_CONVERSION_PROMPT
    assert "{{af_title}}" in EXAM_MASTER_CONVERSION_PROMPT
    assert "{{af_questions}}" in EXAM_MASTER_CONVERSION_PROMPT
    assert "{{af_answer_area}}" in EXAM_MASTER_CONVERSION_PROMPT
    assert "页眉页脚只作为母版版式存在" in EXAM_MASTER_CONVERSION_PROMPT


def test_exam_default_style_sample_docx_is_generated(tmp_path):
    path = write_exam_blank_style_sample_docx("default_exam", tmp_path)

    assert path.exists()
    document = Document(path)
    text = _all_docx_text(document)
    assert "七年级语文期中测试样张" in text
    assert "学生卷" in text
    assert "科目：语文" in text
    assert "年级：七年级" in text
    assert "考试时间：90 分钟" in text
    assert "满分：100 分" in text
    assert "{{af_title}}" not in text
    assert "{{af_questions}}" not in text
    assert "题目插入点" not in text
    assert "作答区" not in text
    assert "答案速查" not in text
    assert "答案：C" not in text
    assert "1. C" not in text


def test_exam_paper_writer_inserts_payload_into_current_master(tmp_path):
    payload = {
        "title": "五年级数学期中测试卷",
        "subject": "数学",
        "grade": "五年级",
        "duration": "90 分钟",
        "total_score": "100 分",
        "sections": [
            {
                "title": "一、填空题",
                "questions": [
                    {
                        "stem": "7 个 0.9 是（    ）。",
                        "answer": "6.3",
                        "score": "2",
                    },
                    {
                        "stem": "选择正确答案。",
                        "options": {"A": "3.14", "B": "6.28"},
                        "answer": "B",
                        "analysis": "按小数乘法计算。",
                        "score": "3",
                    },
                ],
            }
        ],
    }

    path = write_exam_paper_docx("default_exam", tmp_path, payload=payload)

    assert path.exists()
    assert path.name == "五年级数学期中测试卷.docx"
    text = _all_docx_text(Document(path))
    assert "五年级数学期中测试卷" in text
    assert "学生卷" in text
    assert "一、填空题" in text
    assert "一、题目区" not in text
    assert "1. 7 个 0.9 是（    ）。（2 分）" in text
    assert "A. 3.14" in text
    assert "答案速查" not in text
    assert "1. 6.3" not in text
    assert "2. B" not in text
    assert "答案：6.3" not in text
    assert "解析：按小数乘法计算。" not in text
    assert "{{af_title}}" not in text
    assert "{{af_questions}}" not in text
    assert "题目插入点" not in text
    assert "作答区" not in text

    first_page_header_xml = _sealed_header_xml_from_package(path)
    assert first_page_header_xml.count("AlternateContent") == 4
    assert first_page_header_xml.count("rotation:-5898240f") == 2
    assert "ExamSealDottedLine" in first_page_header_xml


def test_exam_paper_writer_outputs_separate_student_and_answer_key_files(tmp_path):
    payload = {
        "title": "五年级数学期中测试卷",
        "subject": "数学",
        "grade": "五年级",
        "duration": "90 分钟",
        "total_score": "100 分",
        "sections": [
            {
                "title": "一、填空题",
                "questions": [
                    {"stem": "7 个 0.9 是（    ）。", "answer": "6.3", "score": "2"},
                    {
                        "stem": "选择正确答案。",
                        "options": {"A": "3.14", "B": "6.28"},
                        "answer": "B",
                        "analysis": "按小数乘法计算。",
                        "score": "3",
                    },
                ],
            }
        ],
    }

    outputs = write_exam_paper_docx_files("default_exam", tmp_path, payload=payload)

    assert outputs.student_docx.exists()
    assert outputs.answer_key_docx is not None
    assert outputs.answer_key_docx.exists()
    assert outputs.student_docx.name == "五年级数学期中测试卷_学生卷.docx"
    assert outputs.answer_key_docx.name == "五年级数学期中测试卷_答案速查.docx"

    student_text = _all_docx_text(Document(outputs.student_docx))
    assert "学生卷" in student_text
    assert "答案速查" not in student_text
    assert "1. 7 个 0.9 是（    ）。（2 分）" in student_text
    assert "1. 6.3" not in student_text

    answer_text = _all_docx_text(Document(outputs.answer_key_docx))
    assert "答案速查" in answer_text
    assert "1. 6.3" in answer_text
    assert "2. B" in answer_text
    assert "7 个 0.9 是" not in answer_text
    assert "A. 3.14" not in answer_text
    assert "解析：" not in answer_text


def test_exam_questions_restart_numbering_by_section_and_use_hanging_layout(tmp_path):
    payload = {
        "title": "Restart Numbering Exam",
        "subject": "Language",
        "grade": "Grade 7",
        "duration": "45 min",
        "total_score": "30",
        "sections": [
            {
                "title": "I. Basics",
                "questions": [
                    {"stem": "Alpha question", "answer": "A1", "score": "3"},
                    {"stem": "Beta question", "answer": "B2", "score": "4"},
                ],
            },
            {
                "title": "II. Reading",
                "questions": [
                    {"stem": "Gamma question", "answer": "C3", "score": "5"},
                    {
                        "stem": "Delta question with a longer prompt that should wrap under the stem text instead of the number marker",
                        "answer": "D4",
                        "score": "6",
                    },
                ],
            },
        ],
    }

    outputs = write_exam_paper_docx_files("default_exam", tmp_path, payload=payload)

    student = Document(outputs.student_docx)
    student_text = _all_docx_text(student)
    assert "1. Alpha question" in student_text
    assert "2. Beta question" in student_text
    assert "1. Gamma question" in student_text
    assert "2. Delta question" in student_text
    assert "3. Gamma question" not in student_text
    question_paragraph = next(
        paragraph for paragraph in student.paragraphs if paragraph.text.startswith("1. Alpha question")
    )
    assert question_paragraph.style.name == "Exam Question Stem"
    question_format = student.styles["Exam Question Stem"].paragraph_format
    assert question_format.space_before.pt == 4
    assert question_format.space_after.pt == 1
    assert round(question_format.left_indent.cm, 2) == 0.72
    assert round(question_format.first_line_indent.cm, 2) == -0.72

    answer = Document(outputs.answer_key_docx)
    answer_text = _all_docx_text(answer)
    assert "1. A1" in answer_text
    assert "2. B2" in answer_text
    assert "1. C3" in answer_text
    assert "2. D4" in answer_text
    assert "3. C3" not in answer_text


def test_exam_text_response_questions_reserve_answer_space(tmp_path):
    payload = {
        "title": "Answer Space Exam",
        "subject": "Language",
        "grade": "Grade 7",
        "duration": "45 min",
        "total_score": "30",
        "sections": [
            {
                "title": "I. Basics",
                "questions": [
                    {
                        "type": "single_choice",
                        "stem": "Choose the right answer.",
                        "options": ["A. One", "B. Two"],
                        "answer": "B",
                        "score": "3",
                    },
                    {
                        "stem": "Complete the sentence: ____.",
                        "answer": "sample",
                        "score": "2",
                    },
                ],
            },
            {
                "title": "II. Reading",
                "questions": [
                    {
                        "type": "short_answer",
                        "stem": "Explain the character's two actions.",
                        "answer": "Helped others; kept learning",
                        "score": "9",
                        "answer_lines": 3,
                    },
                    {
                        "type": "writing",
                        "stem": "Write a short paragraph of no fewer than 200 words.",
                        "answer": "Rubric answer",
                        "score": "12",
                    },
                ],
            },
        ],
    }

    outputs = write_exam_paper_docx_files("default_exam", tmp_path, payload=payload)

    student = Document(outputs.student_docx)
    answer_spaces = [
        paragraph
        for paragraph in student.paragraphs
        if paragraph.style.name == "Exam Answer Space"
    ]
    assert len(answer_spaces) == 8
    assert all("<w:bottom" in paragraph._p.xml for paragraph in answer_spaces)
    assert student.styles["Exam Answer Space"].paragraph_format.space_before.pt == 2
    assert round(student.styles["Exam Answer Space"].paragraph_format.left_indent.cm, 2) == 0.72

    student_text = _all_docx_text(student)
    assert "1. Choose the right answer." in student_text
    assert "2. Complete the sentence: ____." in student_text
    assert "1. Explain the character's two actions." in student_text
    assert "2. Write a short paragraph" in student_text

    answer = Document(outputs.answer_key_docx)
    assert not [
        paragraph
        for paragraph in answer.paragraphs
        if paragraph.style.name == "Exam Answer Space"
    ]


def test_exam_math_solution_questions_use_free_answer_area(tmp_path):
    payload = {
        "title": "Math Free Area Exam",
        "subject": "数学",
        "grade": "Grade 5",
        "duration": "45 min",
        "total_score": "20",
        "sections": [
            {
                "title": "I. Calculation",
                "type": "calculation",
                "questions": [
                    {
                        "type": "single_choice",
                        "stem": "1 + 1 = ?",
                        "options": ["A. 1", "B. 2"],
                        "answer": "B",
                        "score": "2",
                    },
                    {
                        "type": "fill_blank",
                        "stem": "3 x 4 = ____.",
                        "answer": "12",
                        "score": "2",
                    },
                    {
                        "type": "calculation",
                        "stem": "Calculate 36 x 24 and show your process.",
                        "answer": "864",
                        "score": "8",
                    },
                    {
                        "stem": "Prove the two angles are equal.",
                        "answer": "Use parallel-line angle relationships.",
                        "score": "8",
                        "answer_area": {"kind": "free", "lines": 6},
                    },
                ],
            }
        ],
    }

    outputs = write_exam_paper_docx_files("default_exam", tmp_path, payload=payload)

    student = Document(outputs.student_docx)
    line_spaces = [
        paragraph
        for paragraph in student.paragraphs
        if paragraph.style.name == "Exam Answer Space"
    ]
    free_tables = [
        table
        for table in student.tables
        if table.cell(0, 0).paragraphs
        and table.cell(0, 0).paragraphs[0].style.name == "Exam Free Answer Area"
    ]
    assert not line_spaces
    assert len(free_tables) == 2
    assert all(table.cell(0, 0).text == "" for table in free_tables)
    assert [
        round(table.rows[0].height.cm, 2)
        for table in free_tables
    ] == [2.88, 4.32]
    table_indent = free_tables[0]._tbl.tblPr.first_child_found_in("w:tblInd")
    assert table_indent is not None
    assert table_indent.get(qn("w:w")) == str(int(0.72 * 567))

    answer = Document(outputs.answer_key_docx)
    assert not [
        table
        for table in answer.tables
        if table.cell(0, 0).paragraphs
        and table.cell(0, 0).paragraphs[0].style.name == "Exam Free Answer Area"
    ]


def test_exam_style_sample_docx_uses_current_master_file(tmp_path):
    config = ExamPaperConfig()
    copied = create_exam_blank_master_copy(
        config,
        "default_exam",
        output_dir=tmp_path / "masters",
    )
    config.custom_blank_styles.append(copied)
    config.blank_style_id = copied.style_id
    master_path = ensure_current_exam_blank_master_docx(config, copied.style_id)

    master = Document(master_path)
    master.add_paragraph("自定义母版标识")
    master.save(master_path)

    sample_path = write_exam_blank_style_sample_docx(
        copied.style_id,
        tmp_path / "samples",
        config=config,
    )
    text = _all_docx_text(Document(sample_path))
    assert "自定义母版标识" in text
    assert "学生卷" in text


def test_exam_default_master_file_is_stable_builtin_docx():
    path = ensure_builtin_exam_master_docx("default_exam")

    assert path.exists()
    assert path.name == "default_exam_v20.docx"
    document = Document(path)
    text = _all_docx_text(document)
    assert "{{af_title}}" in text
    assert "{{af_version}}" in text
    assert "科目：{{af_subject}}" in text
    assert "年级：{{af_grade}}" in text
    assert "考试时间：{{af_duration}}" in text
    assert "满分：{{af_total_score}}" in text
    assert "占位符保持原样；页眉页脚和密封线由试卷母版决定。" in text
    assert "工作台字段：" not in text
    assert "生成结果字段：" not in text
    assert "题目从 {{af_questions}} 处生成。" not in text
    assert "{{af_questions}}" in text
    assert "{{af_answer_area}}" in text
    assert "默认试卷 · 空白母版" not in text
    assert document.paragraphs[0].text == "{{af_title}}"
    assert document.tables[0].rows[0].cells[0].text == "题号"
    assert len(document.tables[0].columns) == 8
    section_row = document.tables[1]
    assert len(section_row.rows) == 1
    assert len(section_row.columns) == 2
    grid_widths = [
        column.get(qn("w:w"))
        for column in section_row._tbl.tblGrid.iterchildren(tag=qn("w:gridCol"))
    ]
    assert grid_widths == ["1846", "7083"]
    score_cell = section_row.cell(0, 0)
    title_cell = section_row.cell(0, 1)
    assert score_cell.vertical_alignment == WD_CELL_VERTICAL_ALIGNMENT.CENTER
    assert title_cell.vertical_alignment == WD_CELL_VERTICAL_ALIGNMENT.CENTER
    assert len(score_cell.tables) == 1
    assert score_cell.tables[0].rows[0].cells[0].text == "得分"
    assert "一、题目区" in title_cell.text
    title_paragraph = title_cell.paragraphs[0]
    assert title_paragraph.paragraph_format.space_before.pt == 0
    assert title_paragraph.paragraph_format.space_after.pt == 0
    assert title_paragraph.paragraph_format.line_spacing == 1.0


def test_exam_default_master_uses_header_sealed_zone_not_outer_layout_table():
    path = ensure_builtin_exam_master_docx("default_exam")
    document = Document(path)

    assert document.paragraphs[0].text == "{{af_title}}"
    assert len(document.tables[0].columns) == 8
    section = document.sections[0]
    assert section.different_first_page_header_footer is True
    first_page_header_xml = _sealed_header_xml_from_package(path)
    regular_header_xml = section.header._element.xml
    assert "_x0000_s1026" in first_page_header_xml
    assert first_page_header_xml.count("<w:pict") == 7
    assert first_page_header_xml.count("AlternateContent") == 4
    assert "xmlns:w15=" in first_page_header_xml
    assert "xmlns:wpsCustomData=" in first_page_header_xml
    assert "ExamSealDottedLine" in first_page_header_xml
    assert "ExamSealDottedTextGuide" in first_page_header_xml
    assert "ExamSealSolidLineTop" in first_page_header_xml
    assert "ExamSealSolidLineBottom" in first_page_header_xml
    assert "ExamSealLabelBox" in first_page_header_xml
    assert first_page_header_xml.count("rotation:-5898240f") == 2
    assert "margin-left:-451.1pt" in first_page_header_xml
    assert "margin-left:-343.2pt" in first_page_header_xml
    assert "mso-width-relative:page" in first_page_header_xml
    assert "\u5b66\u6821\uff1a" in first_page_header_xml
    assert "\u73ed\u7ea7\uff1a" in first_page_header_xml
    assert "\u5b66\u53f7\uff1a" in first_page_header_xml
    assert "\u59d3\u540d\uff1a" in first_page_header_xml
    assert "margin-left:-102pt" not in first_page_header_xml
    assert "ExamSealDottedLine" not in regular_header_xml
    assert "ExamSealLabelBox" not in regular_header_xml
    assert "rotation:-5898240f" not in regular_header_xml


def test_exam_default_master_exposes_runtime_control_markers():
    path = ensure_builtin_exam_master_docx("default_exam")
    document = Document(path)

    marker_paragraphs = [
        paragraph
        for paragraph in document.paragraphs
        if paragraph.style.name == "Exam Control Marker"
    ]
    assert len(marker_paragraphs) == 2
    assert {paragraph.text for paragraph in marker_paragraphs} == {
        "{{af_questions}}",
        "{{af_answer_area}}",
    }
    assert all(not paragraph.runs[0].font.hidden for paragraph in marker_paragraphs)
    assert {paragraph.style.name for paragraph in marker_paragraphs} == {"Exam Control Marker"}


def test_exam_default_master_docx_is_generated_without_sample_answers(tmp_path):
    path = write_exam_blank_master_docx("default_exam", tmp_path)

    assert path.exists()
    document = Document(path)
    text = _all_docx_text(document)
    assert "{{af_title}}" in text
    assert "{{af_version}}" in text
    assert "科目：{{af_subject}}" in text
    assert "年级：{{af_grade}}" in text
    assert "考试时间：{{af_duration}}" in text
    assert "满分：{{af_total_score}}" in text
    assert "占位符保持原样" in text
    assert "工作台字段：" not in text
    assert "题目从 {{af_questions}} 处生成。" not in text
    assert "默认试卷 · 空白母版" not in text
    assert "题目区" in text
    assert "{{af_questions}}" in text
    assert "{{af_answer_area}}" in text
    assert "答案：C" not in text
    assert "七年级语文期中测试样张" not in text
    assert "一、积累与运用" not in text
