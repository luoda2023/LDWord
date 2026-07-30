from src.config.master_library import get_master
from src.config.material_context import MaterialExecutionContext
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
)
from src.ui.panels.scene_official_preview_projection import (
    build_official_plan_preview_projection,
)


def test_official_preview_projection_is_pure_and_reports_missing_material_fields():
    contract = get_official_document_assembly_contract("notice")
    master = get_master(contract.master_id, "official")
    context = MaterialExecutionContext(entity_data={"title": "项目通知"})

    projection = build_official_plan_preview_projection(
        profile_id="notice",
        master=master,
        contract=contract,
        material_context=context,
        current_template_id="official_gbt",
    )

    assert "当前文种：通知" in projection.header_text
    assert "资料包：已填 1 项" in projection.material_status_text
    assert "缺少必填字段" in projection.material_status_text
    assert "资料契约：official_document_v1" in projection.contract_text
    assert projection.sample_enabled is True
    assert projection.open_master_enabled is True
    assert projection.request_word_preview is True
    assert context.entity_data == {"title": "项目通知"}


def test_official_preview_projection_fails_closed_without_registered_master():
    contract = get_official_document_assembly_contract("notice")

    projection = build_official_plan_preview_projection(
        profile_id="notice",
        master=None,
        contract=contract,
        material_context=MaterialExecutionContext(),
        current_template_id="official_gbt",
    )

    assert "关联版式：未登记版式" in projection.header_text
    assert projection.contract_text == "版式：未登记公文版式。"
    assert projection.sample_enabled is False
    assert projection.open_master_enabled is False
    assert projection.request_word_preview is False
