from __future__ import annotations

import ast
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPOSITORY_ROOT / "src" / "shared" / "engine"
PREFIX = "src.shared.engine.office_image_layout"

MODULE_PATHS = {
    "facade": ENGINE_ROOT / "office_image_layout.py",
    "child_lifecycle": ENGINE_ROOT / "office_image_layout_child_lifecycle.py",
    "contracts": ENGINE_ROOT / "office_image_layout_contracts.py",
    "coordinator": ENGINE_ROOT / "office_image_layout_coordinator.py",
    "fileio": ENGINE_ROOT / "office_image_layout_fileio.py",
    "geometry": ENGINE_ROOT / "office_image_layout_geometry.py",
    "inventory": ENGINE_ROOT / "office_image_layout_inventory.py",
    "preflight": ENGINE_ROOT / "office_image_layout_preflight.py",
    "worker": ENGINE_ROOT / "office_image_layout_worker.py",
}
MODULE_NAMES = {
    label: PREFIX if label == "facade" else f"{PREFIX}_{label}"
    for label in MODULE_PATHS
}
NAME_TO_LABEL = {name: label for label, name in MODULE_NAMES.items()}


def _tree(label: str) -> ast.Module:
    return ast.parse(MODULE_PATHS[label].read_text(encoding="utf-8"))


def _layout_dependencies(label: str) -> set[str]:
    dependencies: set[str] = set()
    for node in ast.walk(_tree(label)):
        if not isinstance(node, ast.ImportFrom) or node.module not in NAME_TO_LABEL:
            continue
        dependencies.add(NAME_TO_LABEL[node.module])
    return dependencies


def _maximum_function_lines(label: str) -> int:
    functions = (
        node
        for node in ast.walk(_tree(label))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    return max(
        (int(node.end_lineno or node.lineno) - node.lineno + 1 for node in functions),
        default=0,
    )


def test_office_image_layout_modules_form_an_explicit_acyclic_dag() -> None:
    expected = {
        "child_lifecycle": {"contracts", "fileio"},
        "contracts": set(),
        "fileio": set(),
        "geometry": {"contracts"},
        "inventory": {"contracts"},
        "preflight": {"contracts", "fileio", "inventory"},
        "coordinator": {"contracts", "fileio", "inventory", "preflight"},
        "worker": {
            "child_lifecycle",
            "contracts",
            "fileio",
            "geometry",
            "inventory",
        },
        "facade": {"contracts", "coordinator", "geometry", "inventory", "worker"},
    }
    actual = {label: _layout_dependencies(label) for label in MODULE_PATHS}
    assert actual == expected

    visited: set[str] = set()
    active: set[str] = set()

    def visit(label: str) -> None:
        assert label not in active, f"Office layout dependency cycle at {label}"
        if label in visited:
            return
        active.add(label)
        for dependency in actual[label]:
            visit(dependency)
        active.remove(label)
        visited.add(label)

    for label in actual:
        visit(label)


def test_office_image_layout_facade_contains_no_layout_implementation() -> None:
    tree = _tree("facade")
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert classes == []
    assert functions == ["_module_main"]
    assert _maximum_function_lines("facade") <= 5


def test_office_image_layout_module_and_function_sizes_stay_bounded() -> None:
    line_limits = {
        "facade": 150,
        "child_lifecycle": 120,
        "contracts": 1000,
        "coordinator": 950,
        "fileio": 80,
        "geometry": 260,
        "inventory": 700,
        "preflight": 450,
        "worker": 1200,
    }
    function_limits = {
        "facade": 5,
        "child_lifecycle": 40,
        "contracts": 100,
        "coordinator": 125,
        "fileio": 30,
        "geometry": 120,
        "inventory": 140,
        "preflight": 60,
        "worker": 100,
    }
    for label, path in MODULE_PATHS.items():
        assert len(path.read_text(encoding="utf-8").splitlines()) <= line_limits[label]
        assert _maximum_function_lines(label) <= function_limits[label]


def test_preflight_and_child_lifecycle_have_single_implementation_owners() -> None:
    coordinator = MODULE_PATHS["coordinator"].read_text(encoding="utf-8")
    preflight = MODULE_PATHS["preflight"].read_text(encoding="utf-8")
    worker = MODULE_PATHS["worker"].read_text(encoding="utf-8")
    lifecycle = MODULE_PATHS["child_lifecycle"].read_text(encoding="utf-8")

    assert "def parent_preflight(" in preflight
    assert "def _preflight_" not in coordinator
    assert "class OfficeChildSession" in lifecycle
    assert "class OfficeChildSession" not in worker
    assert "CoInitialize" in lifecycle and "CoInitialize" not in worker
    assert ".Close(False)" in lifecycle and ".Close(False)" not in worker
    assert ".Quit()" in lifecycle and ".Quit()" not in worker


def test_contracts_and_geometry_are_free_of_process_docx_and_com_io() -> None:
    forbidden_modules = {
        "lxml",
        "os",
        "shutil",
        "subprocess",
        "tempfile",
        "win32com",
        "src.shared.io.safe_docx_package",
    }
    for label in ("contracts", "geometry"):
        imported: set[str] = set()
        for node in ast.walk(_tree(label)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not imported.intersection(forbidden_modules)


def test_production_services_use_real_office_layout_owners_not_the_facade() -> None:
    facade_import = "from src.shared.engine.office_image_layout import"
    offenders = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in (REPOSITORY_ROOT / "src" / "services").rglob("*.py")
        if facade_import in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_child_command_keeps_the_stable_facade_module_entrypoint() -> None:
    coordinator = MODULE_PATHS["coordinator"].read_text(encoding="utf-8")
    facade = MODULE_PATHS["facade"].read_text(encoding="utf-8")
    assert 'module_name="src.shared.engine.office_image_layout"' in coordinator
    assert "run_office_image_layout_child" in facade
    assert "_worker_module_main(argv)" in facade
