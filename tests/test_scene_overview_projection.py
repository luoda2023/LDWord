import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene import ExamBlankStyleConfig, ExamPaperConfig, SceneWorkspace
from src.config.scene_family_application import apply_planned_scene_family_defaults
from src.qt_api import QPushButton
from src.shared.ui.icons.catalog import get_icon_names
from src.ui.panels.scene_navigation_projection import overview_navigation_snapshot
from src.ui.panels.scene_output_detail import _OutputDetail
from src.ui.panels.scene_overview_projection import (
    build_scene_overview_spec,
    first_screen_forbidden_terms,
    first_screen_texts,
)
from src.ui.panels.scene_panel import (
    _SceneOverviewDetail,
    _SceneRulesDetail,
    _ScopeDetail,
)
from src.ui.panels.scene_summary_projection import build_scene_overview_summary_items
from src.ui.panels.style_source_projection import build_style_source_projection


def test_style_source_projection_is_template_only():
    scene = SceneWorkspace(scene_id="custom", category="custom", template_id="default")

    projection = build_style_source_projection(
        scene,
        template_label="默认格式",
        template_preview_action="核对页面、正文和 OOXML 对象",
    )

    assert projection.template_label == "默认格式"
    assert projection.template_action_summary == "核对页面、正文和 Word 对象"
    assert projection.status_label == "模板"
    assert projection.primary_action.label == "看模板"
    assert projection.primary_action.target_card_id == "tpl_overview"
    assert "OOXML" not in projection.summary
    assert projection.summary == "模板：默认格式"


def test_scene_overview_projection_shapes_user_first_screen():
    scene = SceneWorkspace(scene_id="custom", category="custom", template_id="default")
    scene.input_source_profile.accepted_formats = ["docx", "markdown"]

    spec = build_scene_overview_spec(scene, template_label="默认格式")
    style_source_projection = build_style_source_projection(
        scene,
        template_label="默认格式",
    )

    assert spec.task.template_label == "默认格式"
    assert spec.task.numbering_label in {"重建编号", "保留原编号"}
    assert "Word 文档" in spec.task.suitable_for
    assert "Markdown" in spec.task.suitable_for
    assert len(spec.key_settings) == 5
    assert [row.label for row in spec.key_settings] == [
        "处理范围",
        "编号策略",
        "输入清理",
        "文档水印",
        "生成结果",
    ]
    scope_row = next(row for row in spec.key_settings if row.key == "scope")
    numbering_row = next(row for row in spec.key_settings if row.key == "numbering")
    cleanup_row = next(row for row in spec.key_settings if row.key == "input_cleanup")
    watermark_row = next(row for row in spec.key_settings if row.key == "watermark")
    assert spec.style_source == style_source_projection
    assert scope_row.summary == "全部内容"
    assert numbering_row.summary == "重建编号"
    assert cleanup_row.summary == "Markdown 自动清理残留；空白规范化未开启"
    assert watermark_row.summary == "未启用文字水印"
    assert "/" not in scope_row.summary
    assert "文档区域" not in scope_row.summary
    assert {row.target_card_id for row in spec.key_settings} == {
        "scn_rules",
        "scn_output",
    }
    assert len(spec.risk_notices) <= 3
    visible_text = "\n".join(first_screen_texts(spec))
    assert "资料包" not in [row.label for row in spec.key_settings]
    assert "读取文件" not in visible_text
    assert "检查风险" not in visible_text
    assert "custom_basic" not in visible_text
    assert "quick_formatting" not in visible_text
    assert "9/9" not in visible_text
    assert "发现风险先提醒；发现风险先提醒" not in visible_text
    assert "宏 会阻断" not in visible_text
    assert "输出版本" not in visible_text
    assert (
        "清理格式时会保留域和批注，不会静默改写高风险对象、清理格式时会保留域和批注"
        not in visible_text
    )
    assert spec.risk_notices
    assert not first_screen_forbidden_terms(spec)


def test_scene_overview_shows_numbering_as_read_only_final_preview(qapp):
    scene = SceneWorkspace(scene_id="custom", category="custom", template_id="default")
    scene.input_source_profile.accepted_formats = ["docx", "markdown"]
    overview = _SceneOverviewDetail([])

    overview.set_scene(scene)
    overview.show()
    qapp.processEvents()

    assert not hasattr(overview, "_rebuild_radio")
    assert not hasattr(overview, "_preserve_radio")
    assert not hasattr(overview, "_run_preview_card")
    assert overview.findChild(QPushButton, "scn_go_execute_btn") is None
    assert "materials" not in overview._setting_rows
    assert {
        key for key, row in overview._setting_rows.items() if row.isVisible()
    } == {"scope", "numbering", "input_cleanup", "watermark", "delivery"}
    assert overview._setting_rows["numbering"].summary_text() == "重建编号"

    scene.strict_mode = False
    overview.set_scene(scene)
    assert overview._setting_rows["numbering"].summary_text() == "保留原编号"


def test_numbering_editor_is_independent_card_below_scope(qapp):
    scene = SceneWorkspace(scene_id="custom", category="custom", template_id="default")
    scope = _ScopeDetail()
    output = _OutputDetail()
    rules = _SceneRulesDetail(scope, output)
    edits: list[bool] = []
    output.scene_edited.connect(lambda: edits.append(True))

    rules.set_scene(scene)
    rules.show()
    qapp.processEvents()

    layout = rules.layout()
    assert layout.indexOf(scope) < layout.indexOf(rules._numbering_rules)
    assert layout.indexOf(rules._numbering_rules) < layout.indexOf(
        rules._input_cleanup_rules
    )
    assert rules._numbering_rules.layout().indexOf(
        rules._numbering_rules._card
    ) == 0

    rules._numbering_rules._preserve_radio.setChecked(True)
    assert scene.strict_mode is False
    assert edits


def test_scene_overview_save_badge_reports_autosave_lifecycle():
    expected = {
        "pending": "待自动保存",
        "saving": "保存中",
        "failed": "保存失败",
        "saved": "已保存",
    }

    for state, label in expected.items():
        snapshot = overview_navigation_snapshot(
            scene_label="测试方案",
            template_label="默认格式",
            scene_dirty=state != "saved",
            scene_save_state=state,
        )
        assert snapshot["badge_text"] == label


def test_scene_overview_icons_are_registered_and_semantically_aligned():
    scene = SceneWorkspace(scene_id="custom", category="custom", template_id="default")
    spec = build_scene_overview_spec(scene, template_label="默认格式")
    summary_items = build_scene_overview_summary_items(scene)

    rule_icons = {row.key: row.icon_name for row in spec.key_settings}
    summary_icons = {
        item.key: item.icon_name
        for item in summary_items
        if item.key in {"input_profile", "object_preflight", "delivery"}
    }

    assert rule_icons == {
        "scope": "scan-text",
        "numbering": "list-ordered",
        "input_cleanup": "sliders-horizontal",
        "watermark": "shield-check",
        "delivery": "folder-output",
    }
    assert summary_icons == {
        "input_profile": "file-input",
        "object_preflight": "shield-alert",
        "delivery": "file-output",
    }

    registered_icons = set(get_icon_names())
    referenced_icons = {
        *rule_icons.values(),
        *summary_icons.values(),
    }
    assert referenced_icons <= registered_icons


def test_scene_overview_projection_uses_exam_assembly_rows_for_exam_scene():
    scene = SceneWorkspace(
        scene_id="exam",
        mode_id="exam",
        name="试卷",
        category="exam_paper",
        category_label="试卷",
        template_id="default",
    )

    spec = build_scene_overview_spec(scene, template_label="默认格式")
    labels = [row.label for row in spec.key_settings]
    visible_text = "\n".join(first_screen_texts(spec))

    assert labels == [
        "当前方案",
        "本次信息",
    ]
    assert "资料包" not in labels
    assert "作用边界" not in labels
    assert "套用模板" not in labels
    assert {row.target_card_id for row in spec.key_settings} == {"scn_exam_paper"}
    assert "工作台" in visible_text
    assert "标题、科目、年级、考试时间、满分" in visible_text
    assert "页眉页脚和密封线由试卷卷面决定" in visible_text
    assert "题目装配" not in visible_text
    assert "答案处理" not in visible_text
    assert "紧凑试卷" not in visible_text
    assert "导入试卷内容" not in visible_text
    assert "生成 Word 试卷" not in visible_text
    assert not first_screen_forbidden_terms(spec)


def test_scene_overview_projection_reads_exam_paper_config_mapping():
    scene = SceneWorkspace(
        scene_id="exam",
        mode_id="exam",
        name="试卷",
        category="exam_paper",
        category_label="试卷",
        template_id="default",
        master_id="default_exam",
        exam_paper=ExamPaperConfig(
            question_structure_mode="numbered_questions",
            answer_policy="student_only",
            runtime_fields=["title", "exam_date"],
        ),
    )

    spec = build_scene_overview_spec(scene, template_label="默认格式")
    rows = {row.key: row for row in spec.key_settings}

    assert "A4 标准卷面" in rows["exam_blank_style"].summary
    assert "紧凑试卷" not in rows["exam_blank_style"].summary
    assert "exam_question_structure" not in rows
    assert "exam_answer_handling" not in rows
    assert rows["exam_runtime_fields"].summary == "工作台填写：标题、日期"
    assert {row.target_card_id for row in rows.values()} == {"scn_exam_paper"}


def test_scene_overview_projection_reads_custom_exam_blank_style_label():
    scene = SceneWorkspace(
        scene_id="exam",
        mode_id="exam",
        name="试卷",
        category="exam_paper",
        category_label="试卷",
        template_id="default",
        master_id="user_default_exam_copy",
        exam_paper=ExamPaperConfig(
            custom_blank_styles=[
                ExamBlankStyleConfig(
                    style_id="user_default_exam_copy",
                    label="默认试卷 副本",
                    base_style_id="default_exam",
                )
            ],
        ),
    )

    spec = build_scene_overview_spec(scene, template_label="默认格式")
    rows = {row.key: row for row in spec.key_settings}

    assert "默认试卷 副本" in rows["exam_blank_style"].summary


def test_scene_overview_projection_uses_shared_template_preview_action_when_available():
    scene = SceneWorkspace(scene_id="custom", category="custom", template_id="default")

    spec = build_scene_overview_spec(
        scene,
        template_label="默认格式",
        template_preview_action="核对页面、正文、标题、表格、页眉页脚、目录和题注",
    )
    assert spec.style_source.status_label == "模板"
    assert spec.style_source.summary == "模板：默认格式"
    assert (
        "核对页面、正文、标题、表格、页眉页脚、目录和题注"
        not in spec.style_source.summary
    )
    assert "编号：" not in spec.style_source.summary
    assert "统一页面、正文、标题、表格和页眉页脚" not in "\n".join(
        first_screen_texts(spec)
    )
    assert not first_screen_forbidden_terms(spec)


def test_scene_overview_projection_cleans_raw_first_screen_terms():
    scene = SceneWorkspace(scene_id="custom", category="custom", template_id="default")
    scene.input_source_profile.accepted_formats = ["docx", "xlsx"]
    scene.compliance_profile.object_preflight.scan_targets = [
        "content_controls",
        "tracked_changes",
    ]

    spec = build_scene_overview_spec(
        scene,
        template_label="preset_final_schema",
        template_preview_action="核对 schema / preset / manual_review / content_controls",
    )
    visible_text = "\n".join(first_screen_texts(spec))
    assert "/" not in visible_text
    assert "schema" not in visible_text.lower()
    assert "preset" not in visible_text.lower()
    assert "manual_review" not in visible_text.lower()
    assert "content_controls" not in visible_text
    assert "docx" not in visible_text.lower()
    assert "xlsx" not in visible_text.lower()
    assert "_" not in visible_text
    assert "资料包" not in [row.label for row in spec.key_settings]
    assert "输入清理" in visible_text
    assert "输出版本" not in visible_text
    assert "Word 文档、Excel 表格" in visible_text
    assert spec.style_source.status_label == "模板"
    assert spec.style_source.summary == "模板：最终资料规则"
    assert "宏 会停止执行" not in visible_text
    assert all(row.key != "risk_confirmation" for row in spec.key_settings)
    assert any(row.key == "delivery" for row in spec.key_settings)
    assert not first_screen_forbidden_terms(spec)


def test_scene_overview_projection_keeps_evidence_out_of_first_screen():
    scene = SceneWorkspace(
        scene_id="contract_delivery",
        category="contract_delivery",
        template_id="default",
    )
    scene.input_source_profile.material_schema_id = "contract_parties_v1"
    apply_planned_scene_family_defaults(scene)

    spec = build_scene_overview_spec(scene, template_label="默认格式")
    visible_text = "\n".join(first_screen_texts(spec))

    assert "合同交付" in spec.task.title
    assert "读取文件" not in visible_text
    assert "核对字段" in visible_text or "合同交付" in visible_text
    delivery_row = next(row for row in spec.key_settings if row.key == "delivery")
    assert all(row.key != "materials" for row in spec.key_settings)
    assert "会生成" in delivery_row.summary
    assert "不判断法律" not in visible_text
    assert not first_screen_forbidden_terms(spec)
    assert spec.evidence_links
    assert {link.evidence_key for link in spec.evidence_links} == {"coverage_pack"}


def test_scene_overview_projection_surfaces_manual_confirmation_as_actionable_text():
    scene = SceneWorkspace(
        scene_id="ip_patent_documents",
        category="ip_patent_documents",
        template_id="default",
    )
    apply_planned_scene_family_defaults(scene)

    spec = build_scene_overview_spec(scene, template_label="默认格式")
    assert all(row.key != "risk_confirmation" for row in spec.key_settings)
    assert any(notice.label == "需确认" for notice in spec.risk_notices)
    assert not first_screen_forbidden_terms(spec)
