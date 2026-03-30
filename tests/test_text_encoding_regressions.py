import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.modules.base import BaseModule, ModuleMeta
from src.modules.table.table_format import _available_width
from src.pipeline.scheduler import (
    topological_sort,
    validate_data_flow,
    validate_schema_contract,
)


class _MissingDependencyModule(BaseModule):
    meta = ModuleMeta(
        name="missing_dependency_module",
        description="test",
        category="test",
        depends_on=("absent_dependency",),
    )

    def apply(self, doc, config, tracker, context):
        return None


class _BadContractModule(BaseModule):
    meta = ModuleMeta(
        name="bad_contract_module",
        description="test",
        category="test",
        requires_config=("unknown_config_key",),
        consumes=("unknown_context_input",),
        provides=("unknown_context_output",),
    )

    def apply(self, doc, config, tracker, context):
        return None


class _BadFlowModule(BaseModule):
    meta = ModuleMeta(
        name="bad_flow_module",
        description="test",
        category="test",
        consumes=("unknown_flow_key",),
    )

    def apply(self, doc, config, tracker, context):
        return None


def test_scheduler_error_messages_have_readable_text():
    try:
        topological_sort([_MissingDependencyModule()])
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("topological_sort should fail for missing dependencies")

    schema_errors = validate_schema_contract([_BadContractModule()])
    flow_errors = validate_data_flow([_BadFlowModule()])

    assert "??" not in message
    assert "missing dependency" in message.lower()
    assert all("??" not in error for error in schema_errors)
    assert all("??" not in error for error in flow_errors)
    assert any("requires_config" in error for error in schema_errors)
    assert any("consumes" in error for error in schema_errors)
    assert any("provides" in error for error in schema_errors)
    assert "consumes" in flow_errors[0]


def test_table_format_available_width_docstring_is_readable():
    assert _available_width.__doc__ == "Return available table width in twips."


def test_shared_ui_preview_widgets_keep_readable_copy():
    shared_ui_root = ROOT / "src/shared/ui"
    files = [
        "style_preview.py",
        "override_badge.py",
        "progress_indicator.py",
        "folder_picker.py",
        "confirm_dialog.py",
        "color_picker.py",
        "placeholder_edit.py",
    ]

    for name in files:
        source = (shared_ui_root / name).read_text(encoding="utf-8")
        assert "??" not in source, f"{name} still contains unreadable placeholder text"
