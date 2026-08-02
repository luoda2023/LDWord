import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene import SceneWorkspace
from src.config.scene_family_application import (
    audit_planned_scene_family_application_parity,
    apply_planned_scene_family_defaults,
    has_planned_scene_family_application,
    planned_family_id_for_scene,
)
from src.shared.engine.count_engine import get_count_profile
from src.config.scene_presets import (
    create_official_scene,
    create_technical_scene,
    create_thesis_scene,
)


def test_thesis_cn_family_application_keeps_existing_thesis_scene_profile_explicit():
    scene = create_thesis_scene()

    assert planned_family_id_for_scene(scene) == "thesis_cn"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "thesis_cn"
    assert result.default_delivery_preset_id == "final"
    assert result.added_presets == ()
    assert result.updated_presets == ("final", "review", "compliance_report")

    assert scene.description == "中文学位论文·课程论文·综述·开题"
    assert scene.input_source_profile.markdown_policy == "preview_and_cleanup"
    assert scene.input_source_profile.latex_policy == "formula_fragments_only"
    assert scene.input_source_profile.material_schema_id == (
        "thesis_school_rule_context_v1"
    )
    assert scene.input_source_profile.material_schema_ids == [
        "thesis_school_rule_context_v1"
    ]
    assert scene.input_source_profile.require_material_package is False
    assert "json" in scene.input_source_profile.structured_formats

    compliance = scene.compliance_profile
    assert compliance.profile_id == "thesis_cn"
    assert compliance.rule_family == "academic_thesis"
    assert compliance.count_profile_id == "school_thesis"
    assert compliance.report_level == "detailed"
    assert "references" in compliance.check_scopes
    assert get_count_profile("school_thesis").label == "School thesis count"
    assert scene.module_switches["citation_link"] is True
    assert scene.module_switches["reference_format"] is True
    assert scene.is_module_enabled("formula_convert") is True
    assert scene.is_module_enabled("equation_table_format") is True
    assert scene.is_module_enabled("chem_typography") is False
    assert scene.thesis_formula_rules is not None
    assert not any(scene.thesis_formula_rules.chem_typography.scopes.values())

    preflight = compliance.object_preflight
    assert preflight.preservation_mode == "warn"
    assert preflight.block_on == ["macros"]
    assert "fields" in preflight.scan_targets
    assert "visio_drawings" in preflight.scan_targets
    assert preflight.skip_modules_by_finding["fields"] == [
        "toc",
        "citation_link",
        "reference_format",
    ]

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["final"].artifacts.final_docx is True
    assert presets["review"].artifacts.compare_docx is True
    assert presets["review"].include_structured_intermediate is True
    assert presets["compliance_report"].artifacts.final_docx is False
    assert scene.default_delivery_preset().artifacts.final_docx is True
    assert scene.default_delivery_preset().artifacts.compare_docx is False


def test_thesis_cn_family_application_is_idempotent_for_existing_presets():
    scene = create_thesis_scene()
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("final") == 1
    assert preset_ids.count("review") == 1
    assert preset_ids.count("compliance_report") == 1
    assert first.added_presets == ()
    assert second.added_presets == ()
    assert second.updated_presets == ("final", "review", "compliance_report")


def test_contract_delivery_family_application_builds_executable_profile_defaults():
    scene = SceneWorkspace(scene_id="contract_delivery", category="contract_delivery")

    assert planned_family_id_for_scene(scene) == "contract_delivery"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "contract_delivery"
    assert result.added_presets == (
        "review_copy",
        "signing_copy",
        "field_consistency_report",
    )
    assert result.default_delivery_preset_id == "review_copy"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "contract_parties_v1"
    assert profile.material_schema_ids == [
        "contract_parties_v1",
        "signature_assets_v1",
    ]
    assert profile.require_material_package is True
    assert {"party_a", "party_b", "contract_amount", "signing_date"} <= set(
        profile.required_material_fields
    )
    assert "seal" in profile.required_image_roles
    assert "json" in profile.structured_formats

    compliance = scene.compliance_profile
    assert compliance.profile_id == "contract_format"
    assert compliance.rule_family == "contract_delivery"
    assert compliance.count_profile_id == "contract_fields"
    assert "material_field_consistency" in compliance.enabled_checks
    assert get_count_profile("contract_fields").label == "Contract key field and review inventory"
    assert scene.module_switches["image_insertion"] is True

    preflight = compliance.object_preflight
    assert preflight.preservation_mode == "strict"
    assert preflight.block_on == ["macros"]
    assert {
        "fields",
        "comments",
        "tracked_changes",
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "visio_drawings",
        "macros",
    } <= set(preflight.scan_targets)
    assert preflight.skip_modules_by_finding["tracked_changes"] == [
        "paragraph_style",
        "section_format",
        "heading_numbering",
        "md_cleanup",
    ]
    assert preflight.skip_modules_by_finding["fields"] == ["toc", "header_footer"]

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["review_copy"].label == "合同审阅稿"
    assert presets["review_copy"].artifacts.compare_docx is True
    assert presets["review_copy"].include_structured_intermediate is True
    assert presets["signing_copy"].label == "合同签署稿"
    assert presets["signing_copy"].artifacts.compare_docx is False
    assert presets["signing_copy"].artifacts.material_manifest is True
    assert presets["signing_copy"].artifacts.material_package is True
    assert presets["signing_copy"].report_level == "detailed"
    assert presets["field_consistency_report"].artifacts.final_docx is False
    assert presets["field_consistency_report"].report_level == "detailed"
    assert scene.default_delivery_preset().artifacts.compare_docx is True


def test_contract_delivery_family_application_is_idempotent_for_known_presets():
    scene = SceneWorkspace(scene_id="contract_delivery", category="contract_delivery")
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("review_copy") == 1
    assert preset_ids.count("signing_copy") == 1
    assert preset_ids.count("field_consistency_report") == 1
    assert first.added_presets == (
        "review_copy",
        "signing_copy",
        "field_consistency_report",
    )
    assert second.added_presets == ()
    assert second.updated_presets == (
        "review_copy",
        "signing_copy",
        "field_consistency_report",
    )


def test_planned_family_application_parity_has_no_registry_gaps():
    assert audit_planned_scene_family_application_parity() == {}


def test_hr_batch_family_application_builds_batch_defaults():
    scene = SceneWorkspace(scene_id="hr_batch_documents", category="hr_batch_documents")

    assert planned_family_id_for_scene(scene) == "hr_batch_documents"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "hr_batch_documents"
    assert result.added_presets == (
        "per_person_docx",
        "batch_summary_report",
        "failed_items_report",
    )
    assert result.default_delivery_preset_id == "per_person_docx"
    assert scene.input_source_profile.material_schema_id == "personnel_records_v1"
    assert {"employee_name", "employee_id"} <= set(
        scene.input_source_profile.required_material_fields
    )
    assert scene.compliance_profile.count_profile_id == "batch_item_inventory"
    assert "batch_items" in scene.compliance_profile.check_scopes
    assert "content_controls" in scene.compliance_profile.object_preflight.scan_targets
    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["per_person_docx"].artifacts.final_docx is True
    assert presets["batch_summary_report"].artifacts.material_package is True
    assert presets["failed_items_report"].artifacts.final_docx is False


def test_form_batch_family_application_builds_fixed_layout_defaults():
    scene = SceneWorkspace(scene_id="form_batch_documents", category="form_batch_documents")

    assert planned_family_id_for_scene(scene) == "form_batch_documents"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "form_batch_documents"
    assert result.added_presets == (
        "per_record_docx",
        "batch_summary_report",
        "residue_check_report",
    )
    assert result.default_delivery_preset_id == "per_record_docx"
    assert scene.input_source_profile.material_schema_id == "form_batch_fields_v1"
    assert {"form_title", "record_id", "applicant_name"} <= set(
        scene.input_source_profile.required_material_fields
    )
    assert scene.compliance_profile.count_profile_id == "batch_item_inventory"
    assert {"textboxes", "content_controls", "residue"} <= set(
        scene.compliance_profile.check_scopes
    )
    assert "textboxes" in scene.compliance_profile.object_preflight.scan_targets
    assert "content_controls" in scene.compliance_profile.object_preflight.scan_targets
    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["per_record_docx"].artifacts.final_docx is True
    assert presets["batch_summary_report"].artifacts.material_package is True
    assert presets["residue_check_report"].artifacts.final_docx is False


def test_finance_quote_family_application_builds_boundary_report_defaults():
    scene = SceneWorkspace(
        scene_id="finance_quote_documents",
        category="finance_quote_documents",
    )

    assert planned_family_id_for_scene(scene) == "finance_quote_documents"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "finance_quote_documents"
    assert result.added_presets == (
        "customer_quote",
        "internal_review",
        "attachment_report",
    )
    assert result.default_delivery_preset_id == "customer_quote"
    assert scene.input_source_profile.material_schema_id == "finance_quote_fields_v1"
    assert {"customer_name", "quote_no", "amount"} <= set(
        scene.input_source_profile.required_material_fields
    )
    assert scene.compliance_profile.profile_id == "quote_document_format"
    assert scene.compliance_profile.count_profile_id == "finance_attachment_inventory"
    assert {"attachments", "relationships"} <= set(scene.compliance_profile.check_scopes)
    assert "embedded_workbooks" in scene.compliance_profile.object_preflight.scan_targets
    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["customer_quote"].artifacts.final_docx is True
    assert presets["internal_review"].artifacts.compare_docx is True
    assert presets["attachment_report"].artifacts.material_package is True


def test_bilingual_family_application_builds_review_boundary_defaults():
    scene = SceneWorkspace(
        scene_id="bilingual_translation_documents",
        category="bilingual_translation_documents",
    )

    assert planned_family_id_for_scene(scene) == "bilingual_translation_documents"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "bilingual_translation_documents"
    assert result.added_presets == (
        "bilingual_review_copy",
        "parallel_comparison",
        "term_consistency_report",
    )
    assert result.default_delivery_preset_id == "bilingual_review_copy"
    assert scene.input_source_profile.material_schema_id == "bilingual_terms_v1"
    assert {"source_language", "target_language", "document_title"} <= set(
        scene.input_source_profile.required_material_fields
    )
    assert scene.compliance_profile.profile_id == "bilingual_layout"
    assert scene.compliance_profile.count_profile_id == "bilingual_parallel_text"
    assert {"terminology", "revisions", "textboxes"} <= set(
        scene.compliance_profile.check_scopes
    )
    assert "tracked_changes" in scene.compliance_profile.object_preflight.scan_targets
    assert "comments" in scene.compliance_profile.object_preflight.scan_targets
    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["bilingual_review_copy"].artifacts.compare_docx is True
    assert presets["parallel_comparison"].artifacts.final_docx is True
    assert presets["term_consistency_report"].artifacts.final_docx is False


def test_exam_teaching_family_application_builds_multi_version_delivery_defaults():
    scene = SceneWorkspace(scene_id="exam_teaching", category="exam_teaching")

    assert planned_family_id_for_scene(scene) == "exam_teaching"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "exam_teaching"
    assert result.added_presets == (
        "student_version",
        "teacher_version",
        "answer_key",
        "analysis_version",
        "answer_sheet",
    )
    assert result.default_delivery_preset_id == "student_version"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "exam_items_v1"
    assert profile.material_schema_ids == ["exam_items_v1", "teaching_assets_v1"]
    assert profile.require_material_package is True
    assert profile.markdown_policy == "preview_and_cleanup"
    assert profile.latex_policy == "formula_fragments_only"
    assert {"json", "xlsx"} <= set(profile.structured_formats)

    compliance = scene.compliance_profile
    assert compliance.profile_id == "exam_paper"
    assert compliance.rule_family == "exam_teaching"
    assert compliance.count_profile_id == "exam_items"
    assert "exam_question_schema" in compliance.enabled_checks
    assert {"answer_blocks", "analysis_blocks"} <= set(compliance.check_scopes)
    assert get_count_profile("exam_items").label == "Exam item count"
    assert scene.module_switches["placeholder_replace"] is True
    assert scene.module_switches["image_insertion"] is True
    assert scene.is_module_enabled("equation_table_format") is False
    assert scene.thesis_formula_rules is None

    preflight = compliance.object_preflight
    assert preflight.preservation_mode == "warn"
    assert preflight.block_on == ["macros"]
    assert {
        "fields",
        "tracked_changes",
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "visio_drawings",
        "macros",
    } <= set(preflight.scan_targets)
    assert preflight.skip_modules_by_finding["fields"] == ["toc", "header_footer"]

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["student_version"].output_dir_template == "exam/{preset_id}"
    assert presets["student_version"].artifacts.final_docx is True
    assert presets["student_version"].include_structured_intermediate is True
    assert {
        rule.selector
        for rule in presets["student_version"].content_visibility_rules
    } == {"answer", "analysis", "solution", "teacher_note", "knowledge_points"}
    assert presets["teacher_version"].content_visibility_rules == []
    assert presets["teacher_version"].report_level == "detailed"
    assert {
        rule.selector
        for rule in presets["answer_key"].content_visibility_rules
    } == {"question_only", "analysis", "solution", "teacher_note", "knowledge_points"}
    assert {
        rule.selector
        for rule in presets["analysis_version"].content_visibility_rules
    } == {"student_blank", "question_only"}
    assert {
        rule.selector
        for rule in presets["answer_sheet"].content_visibility_rules
    } == {
        "answer",
        "analysis",
        "solution",
        "teacher_note",
        "knowledge_points",
        "question_body",
    }
    assert presets["answer_sheet"].artifacts.material_manifest is True
    assert scene.default_delivery_preset().artifacts.final_docx is True
    assert scene.default_delivery_preset().artifacts.compare_docx is False


def test_exam_teaching_family_application_is_idempotent_for_known_presets():
    scene = SceneWorkspace(scene_id="exam_teaching", category="exam_teaching")
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("student_version") == 1
    assert preset_ids.count("teacher_version") == 1
    assert preset_ids.count("answer_key") == 1
    assert preset_ids.count("analysis_version") == 1
    assert preset_ids.count("answer_sheet") == 1
    assert first.added_presets == (
        "student_version",
        "teacher_version",
        "answer_key",
        "analysis_version",
        "answer_sheet",
    )
    assert second.added_presets == ()
    assert second.updated_presets == (
        "student_version",
        "teacher_version",
        "answer_key",
        "analysis_version",
        "answer_sheet",
    )


def test_journal_en_family_application_builds_submission_package_defaults():
    scene = SceneWorkspace(scene_id="journal_en", category="journal_en")

    assert planned_family_id_for_scene(scene) == "journal_en"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "journal_en"
    assert result.added_presets == (
        "submission_manuscript",
        "review_copy",
        "cover_letter",
        "declaration_package",
        "compliance_report",
    )
    assert result.default_delivery_preset_id == "submission_manuscript"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "journal_submission_materials_v1"
    assert profile.material_schema_ids == ["journal_submission_materials_v1"]
    assert profile.require_material_package is True
    assert {"bibtex", "csl_json", "json"} <= set(profile.structured_formats)

    compliance = scene.compliance_profile
    assert compliance.profile_id == "journal_submission"
    assert compliance.rule_family == "journal_submission"
    assert compliance.count_profile_id == "journal_words"
    assert "journal_citations" in compliance.enabled_checks
    assert "journal_submission_package" in compliance.enabled_checks
    assert {"title", "abstract", "methods", "references"} <= set(compliance.check_scopes)
    assert scene.module_switches["citation_link"] is True
    assert scene.module_switches["reference_format"] is True

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["submission_manuscript"].artifacts.final_docx is True
    assert presets["submission_manuscript"].include_structured_intermediate is True
    assert presets["review_copy"].artifacts.compare_docx is True
    assert presets["cover_letter"].artifacts.final_docx is True
    assert presets["declaration_package"].artifacts.final_docx is False
    assert presets["declaration_package"].artifacts.material_manifest is True
    assert presets["declaration_package"].artifacts.material_package is True
    assert presets["compliance_report"].artifacts.final_docx is False
    assert presets["compliance_report"].artifacts.report_markdown is True
    assert scene.default_delivery_preset().artifacts.final_docx is True


def test_long_document_family_application_builds_delivery_package_defaults():
    scene = SceneWorkspace(scene_id="technical", category="technical")

    assert planned_family_id_for_scene(scene) == "long_document_publishing"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "long_document_publishing"
    assert result.added_presets == (
        "review_copy",
        "proof_copy",
        "final_docx",
        "archive_package",
    )
    assert result.default_delivery_preset_id == "final_docx"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "long_document_metadata_v1"
    assert "long_document_metadata_v1" in profile.material_schema_ids
    assert {"diagram", "figure"} <= set(profile.required_image_roles)
    assert profile.markdown_policy == "preview_and_cleanup"
    assert profile.latex_policy == "formula_fragments_only"

    compliance = scene.compliance_profile
    assert compliance.profile_id == "long_document_publishing"
    assert compliance.rule_family == "long_document_structure"
    assert compliance.count_profile_id == "chapter_inventory"
    assert "technical_chapter_inventory" in compliance.enabled_checks
    assert {"toc", "appendix", "fields", "relationships"} <= set(compliance.check_scopes)

    preflight = compliance.object_preflight
    assert preflight.preservation_mode == "strict"
    assert preflight.block_on == ["macros", "ole_objects", "embedded_workbooks"]
    assert "embedded_packages" in preflight.scan_targets
    assert "visio_drawings" in preflight.scan_targets
    assert preflight.skip_modules_by_finding["fields"] == [
        "toc",
        "header_footer",
        "citation_link",
        "reference_format",
    ]

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["review_copy"].artifacts.compare_docx is True
    assert presets["review_copy"].include_structured_intermediate is True
    assert presets["review_copy"].output_dir_template == "technical/{preset_id}"
    assert presets["proof_copy"].artifacts.compare_docx is True
    assert presets["proof_copy"].report_level == "detailed"
    assert presets["final_docx"].artifacts.final_docx is True
    assert presets["final_docx"].artifacts.compare_docx is False
    assert presets["archive_package"].artifacts.final_docx is False
    assert presets["archive_package"].artifacts.material_manifest is True
    assert presets["archive_package"].artifacts.material_package is True
    assert presets["archive_package"].include_structured_intermediate is True
    assert scene.default_delivery_preset().artifacts.final_docx is True
    assert scene.default_delivery_preset().artifacts.compare_docx is False


def test_long_document_family_application_is_idempotent_for_known_presets():
    scene = SceneWorkspace(scene_id="technical", category="technical")
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("review_copy") == 1
    assert preset_ids.count("proof_copy") == 1
    assert preset_ids.count("final_docx") == 1
    assert preset_ids.count("archive_package") == 1
    assert first.added_presets == (
        "review_copy",
        "proof_copy",
        "final_docx",
        "archive_package",
    )
    assert second.added_presets == ()
    assert second.updated_presets == (
        "review_copy",
        "proof_copy",
        "final_docx",
        "archive_package",
    )


def test_technical_builtin_scene_uses_long_document_delivery_presets():
    scene = create_technical_scene()

    assert planned_family_id_for_scene(scene) == "long_document_publishing"
    assert scene.default_delivery_preset_id == "final_docx"
    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert set(presets) == {
        "review_copy",
        "proof_copy",
        "final_docx",
        "archive_package",
    }
    assert presets["review_copy"].artifacts.compare_docx is True
    assert presets["proof_copy"].include_structured_intermediate is True
    assert presets["archive_package"].artifacts.material_package is True


def test_project_application_family_application_builds_attachment_inventory_profile():
    scene = SceneWorkspace(scene_id="project_application", category="project_application")

    assert planned_family_id_for_scene(scene) == "project_application"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "project_application"
    assert result.added_presets == (
        "application_package",
        "attachment_inventory_report",
    )
    assert result.default_delivery_preset_id == "application_package"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "project_application_materials_v1"
    assert profile.material_schema_ids == ["project_application_materials_v1"]
    assert profile.require_material_package is True
    assert {"json", "xlsx"} <= set(profile.structured_formats)
    assert profile.markdown_policy == "preview_and_cleanup"

    compliance = scene.compliance_profile
    assert compliance.profile_id == "project_application"
    assert compliance.rule_family == "project_application"
    assert compliance.count_profile_id == "application_word_limits"
    assert {"attachments", "fields"} <= set(compliance.check_scopes)

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["application_package"].artifacts.final_docx is True
    assert presets["application_package"].artifacts.material_manifest is True
    assert presets["application_package"].artifacts.material_package is True
    assert presets["application_package"].include_structured_intermediate is True
    assert presets["attachment_inventory_report"].artifacts.final_docx is False
    assert presets["attachment_inventory_report"].artifacts.material_manifest is True
    assert presets["attachment_inventory_report"].artifacts.material_package is True
    assert scene.default_delivery_preset().artifacts.material_manifest is True
    assert scene.default_delivery_preset().artifacts.material_package is True


def test_project_application_family_application_is_idempotent_for_known_presets():
    scene = SceneWorkspace(scene_id="project_application", category="project_application")
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("application_package") == 1
    assert preset_ids.count("attachment_inventory_report") == 1
    assert first.added_presets == (
        "application_package",
        "attachment_inventory_report",
    )
    assert second.added_presets == ()
    assert second.updated_presets == (
        "application_package",
        "attachment_inventory_report",
    )


def test_product_sales_family_application_builds_pre_sales_package_defaults():
    scene = SceneWorkspace(
        scene_id="product_sales_documents",
        category="product_sales_documents",
    )

    assert planned_family_id_for_scene(scene) == "product_sales_documents"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "product_sales_documents"
    assert result.added_presets == (
        "customer_copy",
        "internal_review",
        "asset_report",
        "pre_sales_package",
    )
    assert result.default_delivery_preset_id == "customer_copy"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "product_assets_v1"
    assert profile.material_schema_ids == [
        "product_assets_v1",
        "case_study_assets_v1",
    ]
    assert profile.require_material_package is True
    assert {"json", "xlsx"} <= set(profile.structured_formats)
    assert profile.markdown_policy == "preview_and_cleanup"
    assert profile.latex_policy == "formula_fragments_only"
    assert "product_image" in profile.required_image_roles

    compliance = scene.compliance_profile
    assert compliance.profile_id == "product_document"
    assert compliance.rule_family == "product_sales_documents"
    assert compliance.count_profile_id == "product_asset_inventory"
    assert {"assets", "case_studies", "fields"} <= set(compliance.check_scopes)
    assert get_count_profile("product_asset_inventory").label == (
        "Product and pre-sales asset inventory"
    )
    assert scene.module_switches["placeholder_replace"] is True
    assert scene.module_switches["image_insertion"] is True
    assert scene.module_switches["figure_table_center"] is True

    preflight = compliance.object_preflight
    assert preflight.preservation_mode == "warn"
    assert preflight.block_on == ["macros"]
    assert "embedded_packages" in preflight.scan_targets
    assert "visio_drawings" in preflight.scan_targets
    assert preflight.skip_modules_by_finding["fields"] == ["toc", "header_footer"]

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert "final" not in presets
    assert presets["customer_copy"].artifacts.final_docx is True
    assert presets["customer_copy"].artifacts.material_manifest is True
    assert presets["customer_copy"].include_structured_intermediate is True
    assert presets["internal_review"].artifacts.compare_docx is True
    assert presets["internal_review"].report_level == "detailed"
    assert presets["asset_report"].artifacts.final_docx is False
    assert presets["asset_report"].artifacts.material_manifest is True
    assert presets["pre_sales_package"].artifacts.final_docx is True
    assert presets["pre_sales_package"].artifacts.compare_docx is True
    assert presets["pre_sales_package"].artifacts.material_manifest is True
    assert presets["pre_sales_package"].artifacts.material_package is True
    assert presets["pre_sales_package"].include_structured_intermediate is True
    assert scene.default_delivery_preset().artifacts.final_docx is True
    assert scene.default_delivery_preset().artifacts.material_manifest is True
    assert scene.default_delivery_preset().artifacts.material_package is False


def test_product_sales_family_application_is_idempotent_for_known_presets():
    scene = SceneWorkspace(
        scene_id="product_sales_documents",
        category="product_sales_documents",
    )
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("customer_copy") == 1
    assert preset_ids.count("internal_review") == 1
    assert preset_ids.count("asset_report") == 1
    assert preset_ids.count("pre_sales_package") == 1
    assert first.added_presets == (
        "customer_copy",
        "internal_review",
        "asset_report",
        "pre_sales_package",
    )
    assert second.added_presets == ()
    assert second.updated_presets == (
        "customer_copy",
        "internal_review",
        "asset_report",
        "pre_sales_package",
    )


def test_qualification_archive_family_application_builds_directory_package_defaults():
    scene = SceneWorkspace(
        scene_id="qualification_archive_packages",
        category="qualification_archive_packages",
    )

    assert planned_family_id_for_scene(scene) == "qualification_archive_packages"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "qualification_archive_packages"
    assert result.added_presets == (
        "attachment_package",
        "missing_items_report",
        "archive_manifest",
    )
    assert result.default_delivery_preset_id == "attachment_package"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "qualification_archive_assets_v1"
    assert profile.material_schema_ids == ["qualification_archive_assets_v1"]
    assert profile.required_material_fields == []
    assert profile.required_image_roles == []
    assert profile.require_material_package is True
    assert {"json", "xlsx"} <= set(profile.structured_formats)
    assert profile.markdown_policy == "disabled"
    assert profile.latex_policy == "disabled"

    compliance = scene.compliance_profile
    assert compliance.profile_id == "qualification_inventory"
    assert compliance.rule_family == "qualification_archive_packages"
    assert compliance.count_profile_id == "attachment_inventory"
    assert {"attachments", "package_parts"} <= set(compliance.check_scopes)
    assert compliance.object_preflight.preservation_mode == "warn"
    assert compliance.object_preflight.block_on == ["macros"]

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert presets["attachment_package"].artifacts.final_docx is False
    assert presets["attachment_package"].artifacts.material_manifest is True
    assert presets["attachment_package"].artifacts.material_package is True
    assert presets["attachment_package"].include_structured_intermediate is True
    assert presets["missing_items_report"].artifacts.material_manifest is True
    assert presets["missing_items_report"].artifacts.material_package is False
    assert presets["archive_manifest"].artifacts.material_package is True
    assert scene.default_delivery_preset().artifacts.material_manifest is True
    assert scene.default_delivery_preset().artifacts.material_package is True


def test_qualification_archive_family_replaces_base_bidding_material_requirements():
    scene = SceneWorkspace(
        scene_id="bidding",
        mode_id="bidding",
        category="business",
    )
    scene.input_source_profile.material_schema_id = "bid_materials_v1"
    scene.input_source_profile.material_schema_ids = ["bid_materials_v1"]
    scene.input_source_profile.required_material_fields = [
        "company_name",
        "project_name",
        "legal_person",
    ]
    scene.input_source_profile.required_image_roles = ["logo", "seal"]

    apply_planned_scene_family_defaults(
        scene,
        family_id="qualification_archive_packages",
    )

    profile = scene.input_source_profile
    assert profile.material_schema_id == "qualification_archive_assets_v1"
    assert profile.material_schema_ids == ["qualification_archive_assets_v1"]
    assert profile.required_material_fields == []
    assert profile.required_image_roles == []


def test_qualification_archive_family_application_is_idempotent_for_known_presets():
    scene = SceneWorkspace(
        scene_id="qualification_archive_packages",
        category="qualification_archive_packages",
    )
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("attachment_package") == 1
    assert preset_ids.count("missing_items_report") == 1
    assert preset_ids.count("archive_manifest") == 1
    assert first.added_presets == (
        "attachment_package",
        "missing_items_report",
        "archive_manifest",
    )
    assert second.added_presets == ()
    assert second.updated_presets == (
        "attachment_package",
        "missing_items_report",
        "archive_manifest",
    )


def test_regulated_disclosure_family_application_builds_archive_package_defaults():
    scene = SceneWorkspace(
        scene_id="regulated_disclosure_documents",
        category="regulated_disclosure_documents",
    )

    assert planned_family_id_for_scene(scene) == "regulated_disclosure_documents"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "regulated_disclosure_documents"
    assert result.added_presets == (
        "board_review_copy",
        "public_release_copy",
        "disclosure_archive_package",
        "archive_manifest",
    )
    assert result.default_delivery_preset_id == "board_review_copy"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "regulated_disclosure_materials_v1"
    assert profile.material_schema_ids == ["regulated_disclosure_materials_v1"]
    assert profile.require_material_package is True
    assert {"json", "xlsx"} <= set(profile.structured_formats)
    assert profile.markdown_policy == "preview_and_cleanup"
    assert profile.latex_policy == "disabled"
    assert {"organization", "report_period", "report_type"} <= set(
        profile.required_material_fields
    )

    compliance = scene.compliance_profile
    assert compliance.profile_id == "regulated_disclosure_structure"
    assert compliance.rule_family == "regulated_disclosure_documents"
    assert compliance.count_profile_id == "disclosure_section_inventory"
    assert {"attachments", "comments", "revisions", "hidden_text"} <= set(
        compliance.check_scopes
    )
    assert get_count_profile("disclosure_section_inventory").label == (
        "Regulated disclosure section inventory"
    )
    assert scene.module_switches["validation"] is True
    assert scene.module_switches["table_format"] is True
    assert scene.module_switches["figure_table_center"] is True

    preflight = compliance.object_preflight
    assert preflight.preservation_mode == "warn"
    assert preflight.block_on == ["macros"]
    assert {
        "comments",
        "tracked_changes",
        "hidden_text",
        "fields",
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "visio_drawings",
        "macros",
    } <= set(preflight.scan_targets)
    assert preflight.skip_modules_by_finding["hidden_text"] == [
        "paragraph_style",
        "section_format",
        "heading_numbering",
        "md_cleanup",
    ]

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert "archive_package" not in presets
    assert presets["board_review_copy"].artifacts.final_docx is True
    assert presets["board_review_copy"].artifacts.compare_docx is True
    assert presets["board_review_copy"].artifacts.material_manifest is True
    assert presets["board_review_copy"].include_structured_intermediate is True
    assert presets["public_release_copy"].artifacts.final_docx is True
    assert presets["public_release_copy"].artifacts.compare_docx is False
    assert presets["disclosure_archive_package"].artifacts.final_docx is True
    assert presets["disclosure_archive_package"].artifacts.compare_docx is True
    assert presets["disclosure_archive_package"].artifacts.material_manifest is True
    assert presets["disclosure_archive_package"].artifacts.material_package is True
    assert presets["archive_manifest"].artifacts.final_docx is False
    assert presets["archive_manifest"].artifacts.material_manifest is True
    assert presets["archive_manifest"].artifacts.material_package is True
    assert scene.default_delivery_preset().artifacts.final_docx is True
    assert scene.default_delivery_preset().artifacts.compare_docx is True
    assert scene.default_delivery_preset().artifacts.material_manifest is True
    assert scene.default_delivery_preset().artifacts.material_package is False


def test_regulated_disclosure_family_application_is_idempotent_for_known_presets():
    scene = SceneWorkspace(
        scene_id="regulated_disclosure_documents",
        category="regulated_disclosure_documents",
    )
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("board_review_copy") == 1
    assert preset_ids.count("public_release_copy") == 1
    assert preset_ids.count("disclosure_archive_package") == 1
    assert preset_ids.count("archive_manifest") == 1
    assert first.added_presets == (
        "board_review_copy",
        "public_release_copy",
        "disclosure_archive_package",
        "archive_manifest",
    )
    assert second.added_presets == ()
    assert second.updated_presets == (
        "board_review_copy",
        "public_release_copy",
        "disclosure_archive_package",
        "archive_manifest",
    )


def test_meeting_policy_family_application_builds_official_archive_defaults():
    scene = create_official_scene()

    assert planned_family_id_for_scene(scene) == "meeting_policy_documents"
    assert has_planned_scene_family_application(scene) is True

    result = apply_planned_scene_family_defaults(scene)

    assert result.applied is True
    assert result.family_id == "meeting_policy_documents"
    assert result.added_presets == (
        "formal_minutes",
        "policy_collection",
        "archive_manifest",
    )
    assert result.updated_presets == ("internal_review",)
    assert result.default_delivery_preset_id == "formal_minutes"

    profile = scene.input_source_profile
    assert profile.material_schema_id == "administrative_meeting_fields_v1"
    assert profile.material_schema_ids == [
        "official_document_v1",
        "administrative_meeting_fields_v1",
    ]
    assert profile.require_material_package is True
    assert {"json"} <= set(profile.structured_formats)
    assert {"organization", "meeting_title", "meeting_date"} <= set(
        profile.required_material_fields
    )
    assert "seal" in profile.required_image_roles

    compliance = scene.compliance_profile
    assert compliance.profile_id == "meeting_minutes"
    assert compliance.rule_family == "meeting_policy_documents"
    assert compliance.count_profile_id == "administrative_sections"
    assert "official_numbering_preservation" in compliance.enabled_checks
    assert {"metadata", "appendix", "archive"} <= set(compliance.check_scopes)
    assert get_count_profile("administrative_sections").label == (
        "Administrative section and archive inventory"
    )

    preflight = compliance.object_preflight
    assert preflight.preservation_mode == "warn"
    assert preflight.block_on == ["macros"]
    assert "fields" in preflight.scan_targets
    assert preflight.skip_modules_by_finding["fields"] == ["toc", "header_footer"]

    assert scene.watermark.enabled is True
    assert scene.watermark.text == "内部传阅"
    assert scene.module_switches["watermark"] is True
    assert scene.module_switches["header_footer"] is True

    presets = {preset.preset_id: preset for preset in scene.delivery_presets}
    assert "formal" not in presets
    assert presets["formal_minutes"].artifacts.final_docx is True
    assert presets["formal_minutes"].artifacts.material_manifest is True
    assert presets["formal_minutes"].include_structured_intermediate is True
    assert presets["internal_review"].artifacts.compare_docx is True
    assert presets["internal_review"].include_structured_intermediate is True
    assert presets["policy_collection"].artifacts.material_package is True
    assert presets["archive_manifest"].artifacts.final_docx is False
    assert presets["archive_manifest"].artifacts.material_manifest is True
    assert presets["archive_manifest"].artifacts.material_package is True
    assert scene.default_delivery_preset().artifacts.final_docx is True
    assert scene.default_delivery_preset().artifacts.material_manifest is True


def test_meeting_policy_family_application_is_idempotent_for_known_presets():
    scene = create_official_scene()
    first = apply_planned_scene_family_defaults(scene)
    second = apply_planned_scene_family_defaults(scene)

    preset_ids = [preset.preset_id for preset in scene.delivery_presets]
    assert preset_ids.count("formal_minutes") == 1
    assert preset_ids.count("internal_review") == 1
    assert preset_ids.count("policy_collection") == 1
    assert preset_ids.count("archive_manifest") == 1
    assert first.added_presets == (
        "formal_minutes",
        "policy_collection",
        "archive_manifest",
    )
    assert second.added_presets == ()
    assert second.updated_presets == (
        "formal_minutes",
        "internal_review",
        "policy_collection",
        "archive_manifest",
    )


def test_non_supported_planning_family_application_is_explicit_noop():
    scene = SceneWorkspace(
        scene_id="ip_patent_documents",
        category="ip_patent_documents",
    )

    assert planned_family_id_for_scene(scene) == "ip_patent_documents"
    assert has_planned_scene_family_application(scene) is False

    result = apply_planned_scene_family_defaults(scene)

    assert result.family_id == "ip_patent_documents"
    assert result.applied is False
