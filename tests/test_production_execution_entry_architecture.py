from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOW_LEVEL_RUNNER_NAMES = {
    "WorkbenchBatchProductionRunner",
    "WorkbenchProductionRunner",
}
APPROVED_RUNNER_CONSTRUCTORS = {
    "src/services/production_execution.py": {
        "WorkbenchProductionRunner",
    },
    "src/services/production_runtime/execution_runtime.py": {
        "WorkbenchProductionRunner",
    },
    "src/ui/panels/workbench/execution_session_controller.py": {
        "WorkbenchBatchProductionRunner",
        "WorkbenchProductionRunner",
    },
}


def _low_level_runner_calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue
        if name in LOW_LEVEL_RUNNER_NAMES:
            calls.add(name)
    return calls


def test_low_level_execution_runners_have_an_explicit_product_allowlist():
    observed = {
        path.relative_to(ROOT).as_posix(): calls
        for path in (ROOT / "src").rglob("*.py")
        if (calls := _low_level_runner_calls(path))
    }
    unexpected = {
        path: calls - APPROVED_RUNNER_CONSTRUCTORS.get(path, set())
        for path, calls in observed.items()
        if calls - APPROVED_RUNNER_CONSTRUCTORS.get(path, set())
    }
    assert unexpected == {}


def test_low_level_execution_runners_are_internal_and_not_exported():
    runtime_path = (
        ROOT / "src/services/production_runtime/execution_runtime.py"
    )
    runtime_tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    runtime_exports: list[str] = []
    runtime_exports_found = False
    runtime_classes: dict[str, ast.ClassDef] = {}
    for node in runtime_tree.body:
        export_value = None
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
        ):
            export_value = node.value
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            export_value = node.value
        if isinstance(export_value, (ast.List, ast.Tuple)):
            runtime_exports_found = True
            runtime_exports = [
                str(element.value)
                for element in export_value.elts
                if isinstance(element, ast.Constant)
            ]
        elif isinstance(node, ast.ClassDef):
            runtime_classes[node.name] = node

    assert runtime_exports_found is True
    assert LOW_LEVEL_RUNNER_NAMES.isdisjoint(runtime_exports)
    for class_name in LOW_LEVEL_RUNNER_NAMES:
        docstring = ast.get_docstring(runtime_classes[class_name]) or ""
        assert "Internal low-level" in docstring


def test_scripts_do_not_construct_low_level_execution_runners():
    constructor_pattern = re.compile(
        r"\b(?:WorkbenchBatchProductionRunner|WorkbenchProductionRunner)\s*\("
    )
    script_constructors = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "scripts").rglob("*")
        if path.is_file()
        and path.suffix.casefold() in {".bat", ".cmd", ".ps1", ".py", ".sh"}
        and constructor_pattern.search(
            path.read_text(encoding="utf-8", errors="replace")
        )
    }
    assert script_constructors == set()
