from pathlib import Path
import ast

from src.ui.panels import assets
from src.ui.panels.assets import enterprise_boundary


ROOT = Path(__file__).resolve().parents[1]
ASSETS_PANEL_PATH = ROOT / "src/ui/panels/assets_panel.py"
ASSETS_MODULE_DIR = ROOT / "src/ui/panels/assets"
MATERIAL_ASSETS_DIR = ROOT / "src/services/material_assets"
ENTERPRISE_BOUNDARY_SCAN_PATHS = (
    ASSETS_PANEL_PATH,
    *sorted(ASSETS_MODULE_DIR.glob("*.py")),
    *sorted(MATERIAL_ASSETS_DIR.glob("*.py")),
)


def _module_identifier_names(path: Path) -> set[str]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _assert_removed_tokens_absent_from_asset_sources(*tokens: str) -> None:
    for path in ENTERPRISE_BOUNDARY_SCAN_PATHS:
        names = _module_identifier_names(path)
        for token in tokens:
            assert all(token not in name for name in names), f"{path}:{token}"


def test_enterprise_boundary_registry_is_exported_from_assets_package():
    assert assets.ASSET_CAPABILITY_BOUNDARIES is enterprise_boundary.ASSET_CAPABILITY_BOUNDARIES
    assert assets.boundary_summary_counts()["keep"] == 2


def test_enterprise_boundary_classifies_core_and_enterprise_groups():
    assert enterprise_boundary.boundary_by_key("local_question_figures").decision == "keep"
    assert enterprise_boundary.boundary_by_key("lightweight_shared_cache") is None
    assert enterprise_boundary.boundary_by_key("remote_preview_download") is None
    assert enterprise_boundary.boundary_by_key("remote_url_metadata_compatibility") is None


def test_enterprise_boundary_finds_most_specific_function_group():
    local_boundary = enterprise_boundary.primary_boundary_for_function(
        "_question_figure_asset_items"
    )
    remote_url_boundary = enterprise_boundary.primary_boundary_for_function("_is_remote_asset_preview_url")

    assert local_boundary.key == "local_question_figures"
    assert remote_url_boundary is None


def test_enterprise_boundary_module_does_not_depend_on_assets_panel():
    source = Path(enterprise_boundary.__file__).read_text(encoding="utf-8")

    assert "assets_panel" not in source
    assert all(
        boundary.decision in {"keep", "isolate", "freeze", "delete_candidate"}
        for boundary in enterprise_boundary.ASSET_CAPABILITY_BOUNDARIES
    )


def test_deleted_enterprise_incident_entrypoints_are_not_registered_or_implemented():
    removed_key = "_".join(("subscription", "drift", "recovery"))
    assert enterprise_boundary.boundary_by_key(removed_key) is None

    removed_tokens = (
        "_".join(("subscription", "drift")),
        "_".join(("failure", "recovery")),
        "_".join(("persistent", "worker")),
        "_".join(("durable", "worker")),
        "_".join(("sla", "center")),
    )

    for token in removed_tokens:
        assert enterprise_boundary.boundary_by_key(token) is None
    _assert_removed_tokens_absent_from_asset_sources(*removed_tokens)


def test_deleted_non_question_family_remote_governance_is_not_registered_or_implemented():
    removed_token = "_".join(("non", "question", "asset", "family"))
    removed_key = f"{removed_token}_remote_governance"
    assert enterprise_boundary.boundary_by_key(removed_key) is None

    _assert_removed_tokens_absent_from_asset_sources(removed_token)


def test_deleted_remote_handoff_and_enterprise_access_are_not_registered_or_implemented():
    removed_writeback_token = "_".join(("remote", "writeback"))
    removed_auth_key = "_".join(("enterprise", "remote", "auth"))
    assert enterprise_boundary.boundary_by_key(removed_writeback_token) is None
    assert enterprise_boundary.boundary_by_key(removed_auth_key) is None

    _assert_removed_tokens_absent_from_asset_sources(
        removed_writeback_token,
        removed_auth_key,
    )


def test_deleted_master_registry_and_subscription_entrypoints_are_not_registered_or_implemented():
    assert enterprise_boundary.boundary_by_key("master_data_governance") is None

    removed_tokens = (
        "_".join(("master", "registry")),
        "_".join(("registry", "sync")),
        "_".join(("subscription", "lock")),
        "_".join(("subscription", "change")),
    )

    for token in removed_tokens:
        assert enterprise_boundary.boundary_by_key(token) is None
    _assert_removed_tokens_absent_from_asset_sources(*removed_tokens)
