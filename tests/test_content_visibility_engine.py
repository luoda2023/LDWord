import sys
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene import ContentVisibilityRule, DeliveryPreset
from src.shared.engine.content_visibility import (
    preview_content_visibility_effects,
    scan_content_visibility_markers,
)


def test_content_visibility_scan_matches_rules_and_reports_marker_issues():
    doc = Document()
    doc.add_paragraph("{{#visibility:answer}}")
    doc.add_paragraph("Answer")
    doc.add_paragraph("{{/visibility:answer}}")
    doc.add_paragraph("{{/content:solution}}")
    doc.add_paragraph("{{#visibility:analysis}}")
    doc.add_paragraph("{{#visibility:hint}}")

    scan = scan_content_visibility_markers(
        doc,
        [
            DeliveryPreset(
                preset_id="student",
                content_visibility_rules=[
                    ContentVisibilityRule(selector="answer", action="remove"),
                    ContentVisibilityRule(selector="missing", action="remove"),
                ],
            )
        ],
    )

    assert scan.selectors == ["analysis", "answer", "hint", "solution"]
    assert scan.start_counts == {"analysis": 1, "answer": 1, "hint": 1}
    assert scan.end_counts == {"answer": 1, "solution": 1}
    assert scan.used_rule_selectors == ["answer", "missing"]
    assert scan.missing_rule_selectors == ["missing"]
    assert scan.unused_document_selectors == ["analysis", "hint", "solution"]
    assert scan.orphan_end_selectors == {"solution": 1}
    assert scan.nested_selectors == {"hint": 1}
    assert scan.unclosed_selectors == {"analysis": 1, "hint": 1}
    assert scan.has_issues is True
    assert "规则 selector 未在文档中找到: missing" in scan.issue_messages()


def test_content_visibility_scan_accepts_content_alias_and_dict_rules():
    doc = Document()
    doc.add_paragraph("{{#content:answer}}")
    doc.add_paragraph("Answer")
    doc.add_paragraph("{{/content:answer}}")

    scan = scan_content_visibility_markers(
        doc,
        [
            {
                "content_visibility_rules": [
                    {"selector": "answer", "action": "exclude"},
                    {"selector": "draft", "action": "keep"},
                ]
            }
        ],
    )

    assert scan.selectors == ["answer"]
    assert scan.used_rule_selectors == ["answer"]
    assert scan.missing_rule_selectors == []
    assert scan.unused_document_selectors == []
    assert scan.has_issues is False


def test_content_visibility_preview_reports_per_preset_removed_blocks():
    doc = Document()
    doc.add_paragraph("Question")
    doc.add_paragraph("{{#visibility:answer}}")
    doc.add_paragraph("Answer")
    doc.add_paragraph("{{/visibility:answer}}")
    doc.add_paragraph("End")

    previews = preview_content_visibility_effects(
        doc,
        [
            DeliveryPreset(
                preset_id="student",
                label="Student",
                content_visibility_rules=[
                    ContentVisibilityRule(selector="answer", action="remove"),
                    ContentVisibilityRule(selector="missing", action="remove"),
                ],
            ),
            DeliveryPreset(preset_id="teacher", label="Teacher"),
        ],
    )

    student, teacher = previews
    assert student.preset_id == "student"
    assert student.remove_selectors == ["answer", "missing"]
    assert student.matched_selectors == ["answer"]
    assert student.missing_selectors == ["missing"]
    assert student.removed_block_count == 1
    assert student.removed_paragraph_count == 3
    assert student.stripped_marker_paragraph_count == 0
    assert student.removed_text_samples == ["Answer"]
    assert len(student.removed_blocks) == 1
    block = student.removed_blocks[0]
    assert block.selector == "answer"
    assert block.start_paragraph_index == 1
    assert block.end_paragraph_index == 3
    assert block.paragraph_count == 3
    assert block.text_samples == ["Answer"]
    assert block.context_before == "Question"
    assert block.context_after == "End"

    assert teacher.preset_id == "teacher"
    assert teacher.remove_selectors == []
    assert teacher.matched_selectors == []
    assert teacher.removed_block_count == 0
    assert teacher.removed_paragraph_count == 0
    assert teacher.stripped_marker_paragraph_count == 2
    assert teacher.removed_blocks == []
