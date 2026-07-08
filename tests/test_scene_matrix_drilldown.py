from tests.test_scene_matrix_drilldown_audit import (
    test_scene_matrix_drilldown_audit_rejects_duplicate_item_row_and_source_ids
    as _run_drilldown_audit_rejection_case,
)


def test_scene_matrix_drilldown_audit_rejection_compatibility_entrypoint():
    _run_drilldown_audit_rejection_case()
