from __future__ import annotations

import ast
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_UI_IMPORT_ROOTS = (
    ROOT / "src" / "config",
    ROOT / "src" / "modules",
    ROOT / "src" / "pipeline",
    ROOT / "src" / "reporting",
    ROOT / "src" / "services",
    ROOT / "src" / "shared" / "engine",
)
FORBIDDEN_SERVICE_IMPORT_ROOTS = (
    ROOT / "src" / "config",
    ROOT / "src" / "modules",
    ROOT / "src" / "pipeline",
    ROOT / "src" / "reporting",
    ROOT / "src" / "shared" / "engine",
    ROOT / "src" / "shared" / "io",
)


def _iter_python_files(root: Path):
    if not root.exists():
        return
    yield from sorted(root.rglob("*.py"))


def _import_touches_ui(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name == "src.ui" or alias.name.startswith("src.ui.") for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return module == "src.ui" or module.startswith("src.ui.")
    return False


def _import_touches_services(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(
            alias.name == "src.services"
            or alias.name.startswith("src.services.")
            for alias in node.names
        )
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return module == "src.services" or module.startswith("src.services.")
    return False


def test_non_ui_layers_do_not_import_ui_package():
    violations: list[str] = []

    for root in FORBIDDEN_UI_IMPORT_ROOTS:
        for path in _iter_python_files(root):
            with tokenize.open(path) as handle:
                tree = ast.parse(handle.read(), filename=str(path))
            for node in ast.walk(tree):
                if _import_touches_ui(node):
                    relative = path.relative_to(ROOT).as_posix()
                    line = getattr(node, "lineno", 1)
                    violations.append(f"{relative}:{line}")

    assert violations == []


def test_lower_layers_do_not_reverse_import_services_package():
    violations: list[str] = []

    for root in FORBIDDEN_SERVICE_IMPORT_ROOTS:
        for path in _iter_python_files(root):
            with tokenize.open(path) as handle:
                tree = ast.parse(handle.read(), filename=str(path))
            for node in ast.walk(tree):
                if _import_touches_services(node):
                    relative = path.relative_to(ROOT).as_posix()
                    line = getattr(node, "lineno", 1)
                    violations.append(f"{relative}:{line}")

    assert violations == []


def test_shared_ui_does_not_reverse_import_application_ui():
    violations: list[str] = []
    shared_ui_root = ROOT / "src" / "shared" / "ui"

    for path in _iter_python_files(shared_ui_root):
        with tokenize.open(path) as handle:
            tree = ast.parse(handle.read(), filename=str(path))
        for node in ast.walk(tree):
            if _import_touches_ui(node):
                relative = path.relative_to(ROOT).as_posix()
                line = getattr(node, "lineno", 1)
                violations.append(f"{relative}:{line}")

    assert violations == []
