from src.config.scene_matrix_dashboard import build_scene_matrix_dashboard


def test_scene_matrix_dashboard_payload_does_not_overclaim_runtime_assurance():
    payload = build_scene_matrix_dashboard().to_payload()

    assert payload["assurance"] == {
        "level": "static_traceability",
        "runtime_behavior_verified": False,
        "release_readiness_verified": False,
        "requires_behavioral_tests": True,
    }
