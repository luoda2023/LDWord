import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.config.scene import SceneWorkspace
from src.config.scene_family_application import apply_planned_scene_family_defaults
from src.ui.adapters.workbench_execution_adapter import WorkbenchIssueItem
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_panel import (
    _build_material_schema_validation_items,
    _format_request_cell_tooltip as scene_request_cell_tooltip,
)
from src.ui.panels.scene_summary_projection import (
    build_delivery_summary_items,
    build_input_profile_summary_items,
    build_scene_overview_summary_items,
    build_scene_sample_fixture_detail_text,
    scene_request_cell_count_text,
    scene_request_cell_count_tooltip,
    scene_request_cell_empty_text,
    scene_request_cell_evidence_status_text,
    scene_request_cell_evidence_status_tooltip,
    scene_request_cell_filter_options,
    scene_request_cell_fixture_specs_for_scene,
    scene_request_cell_list_item_projection,
    scene_request_cell_matches_filter,
    scene_sample_fixture_specs_for_scene,
    scene_sample_fixture_list_item_projection,
    scene_sample_fixture_library_status_text,
    scene_sample_fixture_library_status_tooltip,
)
from src.ui.panels.template_panel import TemplatePanel
import src.ui.panels.workbench.quick_execution_detail as quick_execution_detail_module
from src.ui.panels.workbench.quick_execution_detail import QuickExecutionDetail
from src.ui.panels.workbench.scene_presets import (
    create_bidding_scene,
    create_official_scene,
    create_technical_scene,
    create_thesis_scene,
)


def _app():
    return QApplication.instance() or QApplication([])


def _planned_scene(scene_id: str, category: str) -> SceneWorkspace:
    scene = SceneWorkspace(scene_id=scene_id, category=category)
    apply_planned_scene_family_defaults(scene)
    return scene


def _summary_texts(scene: SceneWorkspace) -> list[str]:
    texts: list[str] = []
    for item in build_scene_overview_summary_items(scene):
        texts.extend(
            str(value or "")
            for value in (item.label, item.value, item.detail, item.tooltip)
        )
    texts.append(build_scene_sample_fixture_detail_text(scene))
    return texts


def _summary_visible_texts(scene: SceneWorkspace) -> list[str]:
    texts: list[str] = []
    for item in build_scene_overview_summary_items(scene):
        texts.extend(
            str(value or "")
            for value in (item.label, item.value, item.detail)
        )
    return texts


def _input_delivery_visible_texts(scene: SceneWorkspace) -> list[str]:
    texts: list[str] = []
    for item in (
        *build_input_profile_summary_items(scene),
        *build_delivery_summary_items(scene),
    ):
        texts.extend(
            str(value or "")
            for value in (item.label, item.value, item.detail)
        )
    return texts


def _schema_validation_visible_texts(scene: SceneWorkspace) -> list[str]:
    texts: list[str] = []
    for item in _build_material_schema_validation_items(scene):
        texts.extend(
            str(value or "")
            for value in (item.label, item.value, item.detail)
        )
    return texts


def _overview_evidence_visible_texts(scene: SceneWorkspace) -> list[str]:
    texts: list[str] = []
    for item in build_scene_overview_summary_items(scene):
        if not item.key.endswith("_evidence"):
            continue
        texts.extend(
            str(value or "")
            for value in (item.label, item.value, item.detail)
        )
    return texts


def _assert_absent(texts: list[str], banned_terms: tuple[str, ...], context: str) -> None:
    joined = "\n".join(str(text or "") for text in texts)
    for term in banned_terms:
        assert term not in joined, f"{context} leaked {term!r}:\n{joined}"


def test_scene_visible_copy_guard_keeps_machine_terms_out_of_main_paths():
    scenes = [
        create_thesis_scene(),
        _planned_scene("journal_en", "journal_en"),
        create_official_scene(),
        create_technical_scene(),
        _planned_scene("form_batch_documents", "form_batch_documents"),
        _planned_scene("product_sales_documents", "product_sales_documents"),
        _planned_scene("contract_delivery", "contract_delivery"),
    ]
    for scene in scenes:
        apply_planned_scene_family_defaults(scene)

    banned_terms = (
        "request-cells:",
        "fixture=",
        "cell=",
        "level=",
        "boundary=",
        "channels=",
        "0proxy",
        "pack_fixture_proxy",
        "manual_boundary_fixture",
        "ambiguous_fixture_set",
        "negative_control",
        "Academic rule evidence",
        "Journal submission evidence",
        "Official metadata evidence",
        "Technical long-doc evidence",
        "Application/report evidence",
        "Fixed-layout batch evidence",
        "Boundary capability evidence",
        "product readiness",
        "static closure",
        "static=",
        "readiness=",
        "Green/L5",
        "green_l5",
    )

    visible_texts: list[str] = []
    for scene in scenes:
        visible_texts.extend(_summary_texts(scene))

    _assert_absent(visible_texts, banned_terms, "scene summary copy")
    joined = "\n".join(visible_texts)
    for label in (
        "学术规则证据",
        "期刊投稿证据",
        "公文元数据证据",
        "技术长文档证据",
        "固定版式批量证据",
        "申报/材料证据",
        "已打通",
        "配置检查",
        "可用程度",
    ):
        assert label in joined


def test_scene_overview_summary_main_copy_hides_internal_keys_and_counts():
    scenes = [
        create_bidding_scene(),
        create_thesis_scene(),
        create_official_scene(),
        _planned_scene("form_batch_documents", "form_batch_documents"),
        _planned_scene("product_sales_documents", "product_sales_documents"),
        _planned_scene("contract_delivery", "contract_delivery"),
    ]
    for scene in scenes:
        apply_planned_scene_family_defaults(scene)

    visible_texts: list[str] = []
    for scene in scenes:
        visible_texts.extend(_summary_visible_texts(scene))

    _assert_absent(
        visible_texts,
        (
            "模板管样式 13",
            "场景管流程 37",
            "资料管输入 6",
            "输出管版本 17",
            "custom_basic",
            "quick_formatting",
            "compliance counting",
            "official fields",
            "preserve numbering",
            "collection archive",
            "Original copy",
            "Duplicate copy",
            "Internal review",
            "Policy collection archive",
            "Bid strategy",
            "certificate truthfulness",
            "Green/L5",
            "green_l5",
        ),
        "scene overview visible copy",
    )
    joined = "\n".join(visible_texts)
    assert "缩进、段落间距、固定版式行高、公式、水印等已归一" in joined
    assert "5 类控件归属已分开" in joined
    assert "内部审阅稿" in joined
    assert "政策资料归档" in joined


def test_scene_detail_input_and_delivery_copy_hides_internal_ids():
    scenes = [
        create_bidding_scene(),
        _planned_scene("journal_en", "journal_en"),
        create_official_scene(),
        _planned_scene("product_sales_documents", "product_sales_documents"),
        _planned_scene("regulated_disclosure_documents", "regulated_disclosure_documents"),
        _planned_scene("contract_delivery", "contract_delivery"),
    ]
    for scene in scenes:
        apply_planned_scene_family_defaults(scene)

    visible_texts: list[str] = []
    for scene in scenes:
        visible_texts.extend(_input_delivery_visible_texts(scene))

    _assert_absent(
        visible_texts,
        (
            "bid_materials_v1",
            "journal_submission_materials_v1",
            "administrative_meeting_fields_v1",
            "product_assets_v1",
            "case_study_assets_v1",
            "regulated_disclosure_materials_v1",
            "contract_parties_v1",
            "signature_assets_v1",
            "company_name",
            "product_image",
            "preset",
            "formal_minutes",
            "customer_copy",
            "board_review_copy",
            "policy_collection",
            "pre_sales_package",
            "disclosure_archive_package",
        ),
        "scene detail input/delivery visible copy",
    )
    joined = "\n".join(visible_texts)
    for label in (
        "标书资料",
        "期刊投稿资料",
        "公文/会议字段资料",
        "产品资料",
        "案例资料",
        "披露材料资料",
        "合同方字段资料",
        "签章资料",
        "正式纪要",
        "客户版",
        "董事会审阅稿",
    ):
        assert label in joined


def test_scene_material_rule_validation_copy_hides_registry_internals():
    scenes = [
        _planned_scene("contract_delivery", "contract_delivery"),
        _planned_scene("product_sales_documents", "product_sales_documents"),
        _planned_scene("qualification_archive_packages", "qualification_archive_packages"),
    ]
    for scene in scenes:
        apply_planned_scene_family_defaults(scene)

    visible_texts: list[str] = []
    for scene in scenes:
        visible_texts.extend(_schema_validation_visible_texts(scene))

    _assert_absent(
        visible_texts,
        (
            "Schema",
            "schema",
            "family",
            "contract_parties_v1",
            "signature_assets_v1",
            "product_assets_v1",
            "qualification_archive_assets_v1",
            "Contract party fields",
            "Signature and seal assets",
            "profile override",
            "organization ·",
            "certificate ·",
            "assets/",
        ),
        "scene material rule validation visible copy",
    )
    joined = "\n".join(visible_texts)
    for label in (
        "资料规则校验",
        "资料规则",
        "适用场景族",
        "合同方字段资料",
        "签章资料",
        "产品资料",
        "资质归档资料",
        "甲方（必填）",
        "产品名称（必填）",
        "资质证书（必填，图片 / PDF）",
    ):
        assert label in joined


def test_scene_evidence_cards_keep_technical_ids_in_tooltips():
    scenes = [
        create_bidding_scene(),
        create_thesis_scene(),
        _planned_scene("journal_en", "journal_en"),
        create_official_scene(),
        create_technical_scene(),
        _planned_scene("form_batch_documents", "form_batch_documents"),
        _planned_scene("product_sales_documents", "product_sales_documents"),
        _planned_scene("contract_delivery", "contract_delivery"),
    ]
    for scene in scenes:
        apply_planned_scene_family_defaults(scene)

    visible_texts: list[str] = []
    for scene in scenes:
        visible_texts.extend(_overview_evidence_visible_texts(scene))

    _assert_absent(
        visible_texts,
        (
            "bid_materials_v1",
            "qualification_archive_assets_v1",
            "thesis_school_rule_context_v1",
            "journal_submission_materials_v1",
            "contract_parties_v1",
            "technical_document_v1",
            "product_assets_v1",
            "form_batch_fields_v1",
            "official_metadata_report",
            "field_consistency_report",
            "contract_field_consistency_report",
            "seal_position_residue_report",
            "school_rule_source_selection",
            "reviewed_journal_profile_update",
            "fixed_layout_profile_browser",
            "application_reports_product_sales_assets",
            "contract_delivery_signature_fields_degraded",
        ),
        "scene evidence visible copy",
    )
    joined = "\n".join(visible_texts)
    for label in (
        "标书资料",
        "资质归档资料",
        "学校论文规则资料",
        "期刊投稿资料",
        "合同方字段资料",
        "技术文档资料",
        "产品资料",
        "表单字段资料",
        "报告 1 项",
        "样本",
    ):
        assert label in joined


def test_request_cell_tooltips_use_reader_labels_in_scene_panel():
    scene = _planned_scene("contract_delivery", "contract_delivery")
    cells = scene_request_cell_fixture_specs_for_scene(scene)
    assert cells

    tooltips: list[str] = []
    for cell in cells:
        tooltips.append(scene_request_cell_tooltip(cell))

    _assert_absent(
        tooltips,
        (
            "direct_family_fixture",
            "manual_boundary_fixture",
            "ambiguous_fixture_set",
            "negative_control",
            "pack_fixture_proxy",
            "coverage pack",
            "fixture：",
            "family：",
            "样本文件：",
        ),
        "request-cell tooltip copy",
    )
    joined = "\n".join(tooltips)
    assert "覆盖层级：直接证据" in joined
    assert "覆盖层级：容易误解" in joined
    assert "资料包：合同交付" in joined
    assert "场景族：合同交付" in joined
    assert "证据样本：1 个" in joined
    assert "证据编号：contract_delivery_revisions" in joined


def test_request_cell_list_item_projection_unifies_disambiguation_copy():
    scene = _planned_scene("contract_delivery", "contract_delivery")
    ambiguous_cell = next(
        cell
        for cell in scene_request_cell_fixture_specs_for_scene(scene)
        if cell.disambiguation_required
    )

    projection = scene_request_cell_list_item_projection(ambiguous_cell)

    assert projection.sample_id == "ambiguous_contract_legal_review"
    assert "合同法律审查签署包" in projection.text
    assert "先澄清" in projection.text
    assert "需要先澄清" in projection.tooltip
    assert "澄清：" in projection.tooltip
    assert "候选资料包：" in projection.tooltip
    assert "候选路由" not in projection.tooltip


def test_sample_fixture_list_item_projection_keeps_fixture_id_in_tooltip():
    scene = _planned_scene("contract_delivery", "contract_delivery")
    sample_fixture = scene_sample_fixture_specs_for_scene(scene)[0]
    projection = scene_sample_fixture_list_item_projection(sample_fixture, 1)

    assert projection.fixture_id == "contract_delivery_revisions"
    assert "合同交付样本 1" in projection.text
    assert "contract_delivery_revisions" not in projection.text
    assert "样本编号：contract_delivery_revisions" in projection.tooltip
    assert "Word 对象：" in projection.tooltip


def test_scene_sample_fixture_detail_visible_copy_hides_fixture_ids():
    scene = _planned_scene("contract_delivery", "contract_delivery")
    detail_text = build_scene_sample_fixture_detail_text(scene)

    _assert_absent(
        [detail_text],
        (
            "[contract_delivery]",
            "Contract delivery",
            "contract_delivery_revisions",
            "contract_delivery_signature_fields_degraded",
            "contract_signing_consistency",
            "contract_review_revisions",
            "contract_signature_package_fields",
            "ambiguous_contract_legal_review",
            "样本文件：",
            "证据文件：",
            "覆盖层级：",
        ),
        "scene sample fixture visible copy",
    )
    assert "资料包：合同交付" in detail_text
    assert "合同交付样本 1" in detail_text
    assert "常见说法：" in detail_text
    assert "覆盖方式：直接证据" in detail_text
    assert "证据样本：1 个" in detail_text


def test_request_cell_filter_projection_is_readable_and_complete():
    scene = _planned_scene("professional_disclosure", "professional_disclosure")
    cells = scene_request_cell_fixture_specs_for_scene(scene)
    options = scene_request_cell_filter_options()

    assert options == (
        ("all", "全部说法"),
        ("direct_family_fixture", "直接证据"),
        ("manual_boundary_fixture", "人工确认"),
        ("ambiguous_fixture_set", "容易误解"),
        ("negative_control", "不处理样本"),
        ("pack_fixture_proxy", "借用样本"),
    )
    assert all(
        scene_request_cell_matches_filter(cell, "all")
        for cell in cells
    )
    manual_cells = [
        cell for cell in cells if scene_request_cell_matches_filter(
            cell,
            "manual_boundary_fixture",
        )
    ]
    ambiguous_cells = [
        cell for cell in cells if scene_request_cell_matches_filter(
            cell,
            "ambiguous_fixture_set",
        )
    ]
    assert manual_cells
    assert ambiguous_cells
    assert all(cell.coverage_level == "manual_boundary_fixture" for cell in manual_cells)
    assert all(cell.coverage_level == "ambiguous_fixture_set" for cell in ambiguous_cells)


def test_request_cell_count_and_empty_projection_speaks_reader_language():
    assert scene_request_cell_count_text(5, 5) == "5 条说法"
    assert scene_request_cell_count_text(6, 9) == "6 条 / 共 9 条"
    assert scene_request_cell_count_text(0, 9) == "无匹配说法"
    assert scene_request_cell_count_text(0, 0) == "无请求说法"

    tooltip = scene_request_cell_count_tooltip(0, 9, "direct_family_fixture")
    assert "当前筛选：直接证据" in tooltip
    assert "没有匹配的请求说法" in tooltip
    assert "本场景共 9 条" in tooltip
    assert scene_request_cell_empty_text(
        "manual_boundary_fixture",
        9,
    ) == "当前没有“人工确认”的请求说法"


def test_request_cell_evidence_status_projection_keeps_paths_out_of_main_copy():
    assert scene_request_cell_evidence_status_text("no_selection") == "先选择一条请求说法"
    assert (
        scene_request_cell_evidence_status_text("no_docx")
        == "当前说法没有可打开的 Word 证据"
    )
    assert scene_request_cell_evidence_status_text("missing_file") == "证据文件未生成"
    assert scene_request_cell_evidence_status_text("opened") == "已打开说法依据"
    assert scene_request_cell_evidence_status_text("open_failed") == "无法打开说法依据"

    tooltip = scene_request_cell_evidence_status_tooltip(
        "missing_file",
        "C:/tmp/scene_samples/sample.docx",
    )
    assert "证据文件未生成" in tooltip
    assert "先生成样本库" in tooltip
    assert "位置：C:/tmp/scene_samples/sample.docx" in tooltip
    assert "C:/tmp" not in scene_request_cell_evidence_status_text("missing_file")


def test_sample_fixture_library_status_projection_keeps_paths_out_of_main_copy():
    assert scene_sample_fixture_library_status_text("not_generated") == "尚未生成样本库"
    assert (
        scene_sample_fixture_library_status_text("generated", 42)
        == "样本库已生成 · 42 个样本"
    )
    assert scene_sample_fixture_library_status_text("generation_failed") == "样本库生成失败"
    assert scene_sample_fixture_library_status_text("sample_missing") == "样本文件未生成"
    assert scene_sample_fixture_library_status_text("directory_missing") == "样本目录未生成"

    tooltip = scene_sample_fixture_library_status_tooltip(
        "generation_failed",
        "C:/tmp/scene_samples",
        detail="permission denied",
    )
    assert "样本库生成失败" in tooltip
    assert "说明：permission denied" in tooltip
    assert "位置：C:/tmp/scene_samples" in tooltip
    assert "permission denied" not in scene_sample_fixture_library_status_text(
        "generation_failed"
    )


def test_template_scene_entry_context_copy_stays_task_oriented():
    app = _app()
    bridge = PanelBridge()
    bridge.set_current_scene(
        SceneWorkspace(scene_id="contract_delivery", template_id="default"),
        config_id="contract_delivery",
        emit_signal=False,
    )
    panel = TemplatePanel(bridge)
    try:
        panel.handle_navigation_intent(
            {
                "panel_id": "template",
                "card_id": "tpl_overview",
                "return_panel_id": "scene",
                "return_card_id": "scn_overview",
                "payload": {
                    "entry_context_title": "来自场景：核对模板与样式",
                    "entry_context_detail": "场景：合同交付；模板：默认格式 (default)",
                    "entry_context_action": (
                        "核对页面、正文、标题、表格、页眉页脚、目录和题注"
                    ),
                },
            }
        )
        app.processEvents()

        texts = [
            panel._entry_context_title.text(),
            panel._entry_context_detail.text(),
            panel._return_label.text(),
        ]
        _assert_absent(
            texts,
            (
                "field_id",
                "repair_target_key",
                "issue_item_id",
                "return_card_id",
                "payload",
                "body.font_name",
            ),
            "template entry context copy",
        )
        assert panel._entry_context_title.text() == "来自场景：核对模板与样式"
        assert (
            "核对页面、正文、标题、表格、页眉页脚、目录和题注"
            in panel._entry_context_detail.text()
        )
    finally:
        panel.close()


def test_workbench_issue_visible_copy_translates_raw_audit_terms(monkeypatch):
    app = _app()
    detail = QuickExecutionDetail()
    try:
        monkeypatch.setattr(
            quick_execution_detail_module,
            "sample_fixture_issue_items",
            lambda _scene: [
                WorkbenchIssueItem(
                    issue_id=(
                        "sample_fixture."
                        "contract_delivery_missing_surfaces_contract_delivery_revisions"
                    ),
                    category="sample_fixture",
                    severity="error",
                    title="样本覆盖缺口",
                    summary="contract_delivery: missing_surfaces",
                    details=(
                        "覆盖 pack：contract_delivery",
                        "缺口类型：missing_surfaces",
                        "Sample fixture must declare at least one DOCX surface.",
                    ),
                    source_notes=("scene_sample_fixture_registry",),
                    repair_target_type="sample_fixture",
                    repair_target_key="contract_delivery",
                    owner="scene",
                )
            ],
        )
        detail._apply_scene(
            SceneWorkspace(scene_id="contract_delivery", category="contract_delivery")
        )
        detail.set_document_path("C:/docs/contract.docx")
        app.processEvents()

        assert any(
            item.summary == "contract_delivery: missing_surfaces"
            for item in detail.current_issue_items()
        )
        unfiltered_tooltip = detail._issue_queue_label.toolTip()
        detail.set_issue_queue_filter("sample_fixture")
        app.processEvents()

        if detail._issue_list.count():
            detail._issue_list.setCurrentRow(0)
            app.processEvents()

        texts = [
            detail._issue_queue_label.text(),
            detail._issue_queue_label.toolTip(),
            unfiltered_tooltip,
            detail._issue_detail_title.text(),
            detail._issue_detail_advice.text(),
            detail._issue_detail_body.text(),
        ]
        for index in range(detail._issue_list.count()):
            item = detail._issue_list.item(index)
            texts.extend([item.text(), item.toolTip()])

        _assert_absent(
            texts,
            (
                "coverage pack",
                "覆盖 pack",
                "scene_sample_fixture_registry",
                "missing_surfaces",
                "Sample fixture",
                "does not provide legal advice",
                "field:",
                "asset:",
            ),
            "workbench issue visible copy",
        )
        joined = "\n".join(texts)
        assert "合同交付" in joined
        assert "样本缺少 Word 对象" in joined
        assert "样本覆盖登记" in joined
        assert "不提供法律意见" in joined
    finally:
        detail.close()
