"""Lazy accessors for source-only scene governance registries."""

from __future__ import annotations

from importlib import import_module


def _engineering_registry(module_name: str):
    """Load source-only governance registries only for explicit engineering views."""

    return import_module(f"src.config.{module_name}")


def list_scene_boundary_capabilities(
    *, boundary_group: str = "", subject_id: str = ""
):
    return _engineering_registry(
        "scene_boundary_capability_matrix"
    ).list_scene_boundary_capabilities(
        boundary_group=boundary_group,
        subject_id=subject_id,
    )


def scene_parameter_ownership_specs():
    return _engineering_registry(
        "scene_parameter_ownership"
    ).scene_parameter_ownership_specs()


def audit_scene_parameter_ownership(config_type):
    return _engineering_registry(
        "scene_parameter_ownership"
    ).audit_scene_parameter_ownership(config_type)


def _allowed_parameter_owner_layers():
    return _engineering_registry(
        "scene_parameter_ownership"
    ).ALLOWED_PARAMETER_OWNER_LAYERS


def list_control_contracts():
    return _engineering_registry("control_contract_registry").list_control_contracts()


def audit_control_contract_registry():
    return _engineering_registry(
        "control_contract_registry"
    ).audit_control_contract_registry()


def build_scene_fixed_layout_profile_audit_report():
    return _engineering_registry(
        "scene_fixed_layout_profile_audit"
    ).build_scene_fixed_layout_profile_audit_report()


def product_readiness_for(subject_id: str, *, subject_type: str = "pack"):
    return _engineering_registry("scene_product_readiness").product_readiness_for(
        subject_id,
        subject_type=subject_type,
    )


def build_scene_request_cell_fixture_summary(pack_ids=None):
    return _engineering_registry(
        "scene_request_cell_fixture_registry"
    ).build_scene_request_cell_fixture_summary(pack_ids)


def request_cell_fixtures_for_pack(pack_id: str):
    return _engineering_registry(
        "scene_request_cell_fixture_registry"
    ).request_cell_fixtures_for_pack(pack_id)


def build_scene_sample_coverage_summary(pack_ids):
    return _engineering_registry(
        "scene_sample_fixture_registry"
    ).build_scene_sample_coverage_summary(pack_ids)


def scene_sample_fixtures_for_pack(pack_id: str):
    return _engineering_registry(
        "scene_sample_fixture_registry"
    ).scene_sample_fixtures_for_pack(pack_id)


def _scene_sample_fixture_map():
    return _engineering_registry(
        "scene_sample_fixture_registry"
    ).SCENE_SAMPLE_FIXTURE_MAP
