from tests.test_scene_matrix_dashboard_aggregate import (
    run_scene_matrix_dashboard_aggregate_coverage
    as _run_dashboard_aggregate_case,
)
from tests.test_scene_matrix_dashboard_release_gate_payload import (
    run_scene_matrix_dashboard_release_gate_payload_coverage
    as _run_dashboard_release_gate_payload_case,
)


def test_scene_matrix_dashboard_aggregate_compatibility_entrypoint():
    _run_dashboard_aggregate_case()


def test_scene_matrix_dashboard_release_gate_payload_compatibility_entrypoint(
    tmp_path,
    capsys,
):
    _run_dashboard_release_gate_payload_case(tmp_path, capsys)
