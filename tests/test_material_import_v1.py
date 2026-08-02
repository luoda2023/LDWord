from __future__ import annotations

from openpyxl import Workbook

from src.application.materials.import_workflow import (
    ImportMappingProfile,
    inspect_material_workbook,
)


def test_workbook_import_is_a_draft_with_fresh_opaque_ids(tmp_path) -> None:
    source = tmp_path / "资料.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["项目名称", "项目编号", "产品名称"])
    sheet.append(["项目甲", "A-001", "产品一"])
    workbook.save(source)
    workbook.close()
    mapping = ImportMappingProfile(
        field_key_map={
            "项目名称": "project_name",
            "项目编号": "project_code",
            "产品名称": "product_name",
        },
        group_source_fields=("产品名称",),
        group_target_field="product_name",
        record_name_source_fields=("项目名称",),
        activation_required_fields=("project_name", "project_code"),
    )

    draft = inspect_material_workbook(
        source,
        work_mode_id="custom",
        material_contract_id="suite_fields_v1",
        mapping=mapping,
    )
    package = draft.materialize()

    assert draft.package_id.startswith("pkg_")
    assert package.records[0].record_id.startswith("rec_")
    assert package.groups[0].group_id.startswith("grp_")
    assert package.records[0].display_name == "项目甲"
    assert package.records[0].scope.fields == {
        "project_name": "项目甲",
        "project_code": "A-001",
    }
    assert package.groups[0].scope.fields == {"product_name": "产品一"}
    assert "项目名称" not in package.records[0].scope.fields
