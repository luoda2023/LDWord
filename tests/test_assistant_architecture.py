from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSISTANT_ROOT = ROOT / "src" / "assistant"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_assistant_has_no_runtime_dependency_on_reference_projects():
    for path in ASSISTANT_ROOT.rglob("*.py"):
        assert not any(name.startswith("alavette_flow") for name in _imports(path)), path


def test_assistant_contracts_and_runtime_do_not_import_form_ui():
    for relative in ("contracts", "runtime", "storage"):
        for path in (ASSISTANT_ROOT / relative).rglob("*.py"):
            imports = _imports(path)
            assert "src.ui" not in imports
            assert not any(name.startswith("src.ui.") for name in imports), path


def test_assistant_provider_runtime_does_not_import_form_services():
    for path in (ASSISTANT_ROOT / "runtime").rglob("*.py"):
        assert not any(name.startswith("src.services") for name in _imports(path)), path


def test_assistant_tools_do_not_import_form_ui_or_services():
    for path in (ASSISTANT_ROOT / "tools").rglob("*.py"):
        imports = _imports(path)
        assert not any(name.startswith("src.ui") for name in imports), path
        assert not any(name.startswith("src.services") for name in imports), path


def test_assistant_lower_layers_do_not_reverse_import_assistant_ui_or_qt():
    for relative in ("contracts", "runtime", "storage", "tools", "application", "adapters"):
        for path in (ASSISTANT_ROOT / relative).rglob("*.py"):
            imports = _imports(path)
            assert not any(name.startswith("src.assistant.ui") for name in imports), path
            assert "src.qt_api" not in imports, path
