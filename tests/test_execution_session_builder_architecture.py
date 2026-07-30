from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = ROOT / "src/services/execution_session"
PUBLIC_SESSION = SESSION_ROOT / "__init__.py"
SESSION_BUILDER = SESSION_ROOT / "builder.py"
SESSION_RESOLUTION = SESSION_ROOT / "resolution.py"
SESSION_VALIDATION = SESSION_ROOT / "validation.py"
SESSION_FREEZING = SESSION_ROOT / "freezing.py"
SESSION_CONTRACT = SESSION_ROOT / "contract.py"
SESSION_SUPPORT = SESSION_ROOT / "support.py"
SESSION_MODULES = {
    "execution_session": PUBLIC_SESSION,
    "builder": SESSION_BUILDER,
    "resolution": SESSION_RESOLUTION,
    "validation": SESSION_VALIDATION,
    "freezing": SESSION_FREEZING,
    "contract": SESSION_CONTRACT,
    "support": SESSION_SUPPORT,
}


def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_public_session_builder_is_a_small_real_phase_orchestrator() -> None:
    function = _function(
        _module(PUBLIC_SESSION),
        "build_execution_session_snapshot",
    )
    assert function.end_lineno - function.lineno + 1 <= 80
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        for node in ast.walk(function)
    )
    calls = [
        (node.func.value.id, node.func.attr)
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id
        in {"builder", "resolution", "validation", "freezing"}
    ]
    assert calls == [
        ("builder", "ExecutionSessionBuildRequest"),
        ("resolution", "resolve_execution_identity"),
        ("resolution", "resolve_execution_resource_graph"),
        ("validation", "validate_execution_resource_graph"),
        ("freezing", "freeze_execution_resources"),
        ("builder", "assemble_execution_session_snapshot"),
    ]


def test_session_build_phases_remain_bounded_and_ui_independent() -> None:
    for path in (
        SESSION_BUILDER,
        SESSION_RESOLUTION,
        SESSION_VALIDATION,
        SESSION_FREEZING,
        SESSION_CONTRACT,
        SESSION_SUPPORT,
    ):
        module = _module(path)
        functions = [
            node for node in module.body if isinstance(node, ast.FunctionDef)
        ]
        if functions:
            assert max(
                node.end_lineno - node.lineno + 1 for node in functions
            ) <= 90
        imported_modules = {
            alias.name
            for node in module.body
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            str(node.module or "")
            for node in module.body
            if isinstance(node, ast.ImportFrom)
        }
        assert not any(
            module_name.startswith(("PySide", "PyQt", "src.ui"))
            for module_name in imported_modules
        )


def test_session_builder_owns_resolution_and_freeze_dependencies() -> None:
    public_source = PUBLIC_SESSION.read_text(encoding="utf-8")
    resolution_source = SESSION_RESOLUTION.read_text(encoding="utf-8")
    freezing_source = SESSION_FREEZING.read_text(encoding="utf-8")
    for dependency in (
        "get_scene_entry",
        "get_template_entry",
        "load_template_from_library",
        "get_master",
    ):
        assert dependency not in public_source
        assert dependency in resolution_source
    assert "atomic_write_bytes" not in public_source
    assert "atomic_write_bytes" in freezing_source


def test_session_phase_import_graph_is_acyclic_and_does_not_depend_on_facade(
) -> None:
    dependencies = {
        name: _session_dependencies(_module(path))
        for name, path in SESSION_MODULES.items()
    }
    phase_modules = {
        "builder",
        "resolution",
        "validation",
        "freezing",
        "contract",
        "support",
    }
    assert all(
        "execution_session" not in dependencies[module_name]
        for module_name in phase_modules
    )
    assert all(
        "TYPE_CHECKING" not in path.read_text(encoding="utf-8")
        for path in SESSION_MODULES.values()
    )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_name: str) -> None:
        assert module_name not in visiting, (
            f"execution-session import cycle reaches {module_name}"
        )
        if module_name in visited:
            return
        visiting.add(module_name)
        for dependency in dependencies[module_name]:
            visit(dependency)
        visiting.remove(module_name)
        visited.add(module_name)

    for module_name in SESSION_MODULES:
        visit(module_name)


def _session_dependencies(module: ast.Module) -> set[str]:
    dependencies: set[str] = set()
    for node in module.body:
        if isinstance(node, ast.ImportFrom):
            imported_module = str(node.module or "")
            if node.level and not imported_module:
                dependencies.update(
                    alias.name
                    for alias in node.names
                    if alias.name in SESSION_MODULES
                )
            else:
                candidate = imported_module.rsplit(".", 1)[-1]
                if candidate in SESSION_MODULES:
                    dependencies.add(candidate)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                candidate = alias.name.rsplit(".", 1)[-1]
                if candidate in SESSION_MODULES:
                    dependencies.add(candidate)
    return dependencies
