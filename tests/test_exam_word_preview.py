from src.config.scene import ExamPaperConfig
from src.shared.engine.exam_word_preview import render_exam_word_preview


def test_exam_word_preview_caches_student_and_answer_docx_separately(tmp_path):
    config = ExamPaperConfig()

    student = render_exam_word_preview(
        style_id="default_exam",
        config=config,
        preview_kind="student",
        cache_root=tmp_path,
        attempt_render=False,
    )
    cached_student = render_exam_word_preview(
        style_id="default_exam",
        config=config,
        preview_kind="student",
        cache_root=tmp_path,
        attempt_render=False,
    )
    answer = render_exam_word_preview(
        style_id="default_exam",
        config=config,
        preview_kind="answer",
        cache_root=tmp_path,
        attempt_render=False,
    )

    assert student.status == "docx_only"
    assert student.docx_path is not None and student.docx_path.is_file()
    assert cached_student.cache_key == student.cache_key
    assert cached_student.cache_hit is True
    assert answer.status == "docx_only"
    assert answer.docx_path is not None and answer.docx_path.is_file()
    assert answer.cache_key != student.cache_key
    assert answer.variant_id == "answer"
