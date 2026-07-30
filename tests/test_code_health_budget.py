"""Non-increasing structural budgets for the current monolith hotspots."""

from __future__ import annotations

import ast
from collections import defaultdict
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "src"

FILE_LINE_BUDGETS = {
    "src/assistant/ui/assistant_panel.py": 2150,
    "src/assistant/ui/turn_flow_mixin.py": 1375,
    "src/config/library.py": 3475,
    "src/config/scene_matrix_dashboard.py": 3225,
    "src/pipeline/runner.py": 2325,
    "src/ui/panels/heading_numbering_panel.py": 2400,
    "src/ui/panels/scene_panel.py": 4750,
    "src/ui/panels/scene_summary_projection.py": 3325,
    "src/ui/panels/template_detail_lifecycle.py": 525,
    "src/ui/panels/template_library_management_mixin.py": 480,
    "src/ui/panels/template_navigation_context_mixin.py": 185,
    "src/ui/panels/template_overview_projection_mixin.py": 160,
    "src/ui/panels/template_panel.py": 725,
    "src/ui/panels/template_session_persistence_mixin.py": 425,
    "src/ui/panels/workbench/quick_execution_detail.py": 1850,
    "src/ui/panels/workbench/quick_execution_feedback_mixin.py": 425,
    "src/ui/template_close_prompt.py": 65,
    "src/ui/template_close_transaction.py": 365,
}

SYMBOL_LINE_BUDGETS = {
    ("src/assistant/ui/assistant_panel.py", "AssistantPanel"): 2050,
    ("src/assistant/ui/turn_flow_mixin.py", "AssistantTurnFlowMixin"): 1300,
    ("src/config/scene_matrix_dashboard.py", "_build_scene_matrix_dashboard_uncached"): 475,
    ("src/config/scene_matrix_dashboard.py", "_dashboard_cards"): 575,
    ("src/config/scene_matrix_drilldown.py", "audit_scene_matrix_drilldown_report"): 800,
    ("src/pipeline/runner.py", "Pipeline"): 1550,
    ("src/shared/engine/material_timeline.py", "_resolve_plan"): 250,
    ("src/ui/panels/heading_numbering_panel.py", "HeadingNumberingPanel"): 1875,
    ("src/ui/panels/scene_panel.py", "ScenePanel"): 1730,
    (
        "src/ui/panels/template_detail_lifecycle.py",
        "TemplateDetailLifecycleMixin",
    ): 250,
    (
        "src/ui/panels/template_library_management_mixin.py",
        "TemplateLibraryManagementMixin",
    ): 465,
    (
        "src/ui/panels/template_navigation_context_mixin.py",
        "TemplateNavigationContextMixin",
    ): 175,
    (
        "src/ui/panels/template_overview_projection_mixin.py",
        "TemplateOverviewProjectionMixin",
    ): 140,
    ("src/ui/panels/template_panel.py", "TemplatePanel"): 535,
    (
        "src/ui/panels/template_session_persistence_mixin.py",
        "TemplateSessionPersistenceMixin",
    ): 405,
    ("src/ui/panels/workbench/quick_execution_detail.py", "QuickExecutionDetail"): 1750,
    (
        "src/ui/panels/workbench/quick_execution_feedback_mixin.py",
        "QuickExecutionFeedbackMixin",
    ): 400,
    ("src/ui/template_close_prompt.py", "TemplateClosePrompt"): 55,
    (
        "src/ui/template_close_transaction.py",
        "TemplateCloseTransaction",
    ): 260,
}

SYMBOL_COMPLEXITY_BUDGETS = {
    ("src/config/scene_matrix_dashboard.py", "_build_scene_matrix_dashboard_uncached"): 15,
    ("src/config/scene_matrix_dashboard.py", "_dashboard_cards"): 30,
    ("src/config/scene_matrix_drilldown.py", "audit_scene_matrix_drilldown_report"): 105,
    ("src/shared/engine/material_timeline.py", "_resolve_plan"): 95,
}

SYMBOL_METHOD_COUNT_BUDGETS = {
    ("src/assistant/ui/assistant_panel.py", "AssistantPanel"): 72,
    ("src/ui/panels/heading_numbering_panel.py", "HeadingNumberingPanel"): 102,
    ("src/ui/panels/scene_panel.py", "ScenePanel"): 107,
    (
        "src/ui/panels/template_detail_lifecycle.py",
        "TemplateDetailLifecycleMixin",
    ): 19,
    (
        "src/ui/panels/template_library_management_mixin.py",
        "TemplateLibraryManagementMixin",
    ): 30,
    (
        "src/ui/panels/template_navigation_context_mixin.py",
        "TemplateNavigationContextMixin",
    ): 7,
    (
        "src/ui/panels/template_overview_projection_mixin.py",
        "TemplateOverviewProjectionMixin",
    ): 5,
    ("src/ui/panels/template_panel.py", "TemplatePanel"): 38,
    (
        "src/ui/panels/template_session_persistence_mixin.py",
        "TemplateSessionPersistenceMixin",
    ): 22,
    ("src/ui/panels/workbench/quick_execution_detail.py", "QuickExecutionDetail"): 95,
    (
        "src/ui/template_close_transaction.py",
        "TemplateCloseTransaction",
    ): 13,
    ("src/ui/template_close_prompt.py", "TemplateClosePrompt"): 4,
}

RECIPROCAL_PACKAGE_EDGE_BUDGETS = {
    ("config", "shared"): 89,
    ("modules", "pipeline"): 50,
    ("assistant", "ui"): 8,
    ("services", "shared"): 63,
}

SILENT_BROAD_EXCEPTION_BUDGET = 51


def _module_name(path: Path) -> str:
    module = path.with_suffix("").relative_to(ROOT).as_posix().replace("/", ".")
    return module[: -len(".__init__")] if module.endswith(".__init__") else module


def _module_index() -> dict[str, Path]:
    return {_module_name(path): path for path in SOURCE_ROOT.rglob("*.py")}


def _is_type_checking_import(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    while parent is not None:
        if (
            isinstance(parent, ast.If)
            and isinstance(parent.test, ast.Name)
            and parent.test.id == "TYPE_CHECKING"
        ):
            return True
        parent = parents.get(parent)
    return False


def _import_targets(node: ast.AST, source_module: str) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if not isinstance(node, ast.ImportFrom) or not node.module:
        return ()
    if not node.level:
        return (node.module,)

    source_package = source_module.split(".")[:-1]
    keep = max(0, len(source_package) - node.level + 1)
    prefix = ".".join(source_package[:keep])
    return ((prefix + "." + node.module).strip("."),)


@lru_cache(maxsize=1)
def _runtime_import_edges() -> set[tuple[str, str]]:
    modules = _module_index()
    edges: set[tuple[str, str]] = set()
    for source_module, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if _is_type_checking_import(node, parents):
                continue
            for target in _import_targets(node, source_module):
                matches = [
                    module
                    for module in modules
                    if target == module or target.startswith(module + ".")
                ]
                if matches:
                    edges.add((source_module, max(matches, key=len)))
    return edges


def _strongly_connected_components(
    edges: set[tuple[str, str]],
) -> tuple[tuple[str, ...], ...]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    vertices: set[str] = set()
    for source, target in edges:
        vertices.update((source, target))
        if source != target:
            adjacency[source].append(target)

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low_links: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def visit(vertex: str) -> None:
        nonlocal index
        indices[vertex] = low_links[vertex] = index
        index += 1
        stack.append(vertex)
        on_stack.add(vertex)

        for target in adjacency[vertex]:
            if target not in indices:
                visit(target)
                low_links[vertex] = min(low_links[vertex], low_links[target])
            elif target in on_stack:
                low_links[vertex] = min(low_links[vertex], indices[target])

        if low_links[vertex] != indices[vertex]:
            return
        component: list[str] = []
        while True:
            target = stack.pop()
            on_stack.remove(target)
            component.append(target)
            if target == vertex:
                break
        if len(component) > 1:
            components.append(tuple(sorted(component)))

    for vertex in sorted(vertices):
        if vertex not in indices:
            visit(vertex)
    return tuple(sorted(components))


def _symbol(path: Path, name: str) -> ast.AST:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    assert len(matches) == 1, f"{path.relative_to(ROOT).as_posix()}:{name}"
    return matches[0]


def _line_count(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno")) - int(getattr(node, "lineno")) + 1


def _rough_complexity(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.Assert,
                ast.AsyncFor,
                ast.AsyncWith,
                ast.For,
                ast.If,
                ast.IfExp,
                ast.While,
                ast.With,
            ),
        ):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(0, len(child.values) - 1)
        elif isinstance(child, ast.Try):
            score += len(child.handlers)
            score += int(bool(child.orelse)) + int(bool(child.finalbody))
        elif isinstance(child, ast.Match):
            score += len(child.cases)
    return score


def _method_count(node: ast.AST) -> int:
    assert isinstance(node, ast.ClassDef)
    return sum(
        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        for child in node.body
    )


def _top_level_package(module: str) -> str:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else parts[0]


def _reciprocal_package_edge_count(
    edges: set[tuple[str, str]],
    first: str,
    second: str,
) -> int:
    return sum(
        1
        for source, target in edges
        if {
            _top_level_package(source),
            _top_level_package(target),
        }
        == {first, second}
        and _top_level_package(source) != _top_level_package(target)
    )


@lru_cache(maxsize=1)
def _silent_broad_exception_count() -> int:
    count = 0
    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            broad = node.type is None or (
                isinstance(node.type, ast.Name)
                and node.type.id in {"Exception", "BaseException"}
            )
            silent = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            count += int(broad and silent)
    return count


def test_runtime_import_graph_is_acyclic():
    assert _strongly_connected_components(_runtime_import_edges()) == ()


def test_known_hotspot_files_do_not_grow():
    violations = {
        relative: (len((ROOT / relative).read_text(encoding="utf-8-sig").splitlines()), budget)
        for relative, budget in FILE_LINE_BUDGETS.items()
        if len((ROOT / relative).read_text(encoding="utf-8-sig").splitlines()) > budget
    }
    assert violations == {}


def test_known_hotspot_symbols_do_not_grow():
    violations = {}
    for (relative, name), budget in SYMBOL_LINE_BUDGETS.items():
        actual = _line_count(_symbol(ROOT / relative, name))
        if actual > budget:
            violations[f"{relative}:{name}"] = (actual, budget)
    assert violations == {}


def test_worst_functions_do_not_gain_decision_complexity():
    violations = {}
    for (relative, name), budget in SYMBOL_COMPLEXITY_BUDGETS.items():
        actual = _rough_complexity(_symbol(ROOT / relative, name))
        if actual > budget:
            violations[f"{relative}:{name}"] = (actual, budget)
    assert violations == {}


def test_hotspot_classes_do_not_gain_methods():
    violations = {}
    for (relative, name), budget in SYMBOL_METHOD_COUNT_BUDGETS.items():
        actual = _method_count(_symbol(ROOT / relative, name))
        if actual > budget:
            violations[f"{relative}:{name}"] = (actual, budget)
    assert violations == {}


def test_reciprocal_package_dependencies_do_not_grow():
    edges = _runtime_import_edges()
    violations = {}
    for packages, budget in RECIPROCAL_PACKAGE_EDGE_BUDGETS.items():
        actual = _reciprocal_package_edge_count(edges, *packages)
        if actual > budget:
            violations[" <-> ".join(packages)] = (actual, budget)
    assert violations == {}


def test_silent_broad_exception_handlers_do_not_grow():
    assert _silent_broad_exception_count() <= SILENT_BROAD_EXCEPTION_BUDGET
