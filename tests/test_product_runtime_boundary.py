from __future__ import annotations

import ast
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _local_module_paths() -> dict[str, Path]:
    paths = [ROOT / "main.py", *sorted((ROOT / "src").rglob("*.py"))]
    modules: dict[str, Path] = {}
    for path in paths:
        relative = path.relative_to(ROOT)
        if relative.name == "__init__.py":
            module = ".".join(relative.parent.parts)
        else:
            module = ".".join(relative.with_suffix("").parts)
        modules[module] = path
    return modules


def _relative_import_base(
    *,
    current_module: str,
    current_path: Path,
    level: int,
    target: str,
) -> str:
    package = (
        current_module
        if current_path.name == "__init__.py"
        else current_module.rsplit(".", 1)[0]
    )
    parts = package.split(".") if package else []
    parts = parts[: max(0, len(parts) - level + 1)]
    if target:
        parts.extend(target.split("."))
    return ".".join(parts)


def _runtime_import_graph() -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
]:
    module_paths = _local_module_paths()
    graph = {module: set() for module in module_paths}
    imported_names = {module: set() for module in module_paths}

    for module, path in module_paths.items():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            candidates: list[str] = []
            if isinstance(node, ast.Import):
                candidates.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = (
                    _relative_import_base(
                        current_module=module,
                        current_path=path,
                        level=node.level,
                        target=node.module or "",
                    )
                    if node.level
                    else node.module or ""
                )
                if base:
                    candidates.append(base)
                    candidates.extend(
                        f"{base}.{alias.name}"
                        for alias in node.names
                        if alias.name != "*"
                    )

            imported_names[module].update(candidates)
            graph[module].update(
                candidate for candidate in candidates if candidate in module_paths
            )

    return graph, imported_names


def _main_reachable_modules() -> tuple[set[str], dict[str, set[str]]]:
    graph, imported_names = _runtime_import_graph()
    queue = deque(["main"])
    reachable: set[str] = set()
    while queue:
        module = queue.popleft()
        if module in reachable:
            continue
        reachable.add(module)
        queue.extend(graph.get(module, ()))
    return reachable, imported_names


def test_product_entrypoint_excludes_internal_scene_governance():
    reachable, _ = _main_reachable_modules()

    forbidden_prefixes = (
        "src.config.scene_matrix",
        "src.config.scene_release_",
        "src.config.scene_boundary_maturity",
    )
    forbidden = sorted(
        module
        for module in reachable
        if module.startswith(forbidden_prefixes)
    )
    forbidden.extend(
        sorted(
            module
            for module in reachable
            if module
            in {
                "src.config.scene_product_readiness",
                "src.config.scene_sample_fixture_registry",
                "src.config.scene_request_cell_fixture_registry",
                "src.config.control_contract_registry",
                "src.config.scene_parameter_ownership",
                "src.config.scene_fixed_layout_profile_audit",
                "src.shared.engine.scene_sample_docx_builder",
                "src.services.material_content.docx_normalizer",
                "src.services.material_content.docx_importer",
                "src.services.material_content.metafile_converter",
                "src.services.material_attachments.timeline_preparation",
                "src.services.material_assets.question_figures",
                "src.services.material_assets.question_library",
                "src.services.material_assets.repair_audit",
                "src.services.material_assets.word_docx_recovery",
                "src.report_writer",
                "src.ui.panels.scene_summary_projection",
            }
        )
    )

    assert forbidden == []


def test_product_entrypoint_excludes_optional_workbench_surfaces():
    reachable, _ = _main_reachable_modules()

    optional_batch_modules = {
        "src.reporting.official_batch_payload",
        "src.services.production_runtime.batch_reporting",
        "src.shared.engine.official_document_batch_history",
        "src.ui.panels.workbench.batch_generation_detail",
        "src.ui.panels.workbench.batch_generation_source_area",
    }
    forbidden = sorted(
        module
        for module in reachable
        if module == "src.ui.panels.assets_panel"
        or module.startswith("src.ui.panels.assets.")
        or module == "src.ui.panels.theme_panel"
        or module in optional_batch_modules
    )

    assert forbidden == []


def test_product_entrypoint_does_not_import_test_or_script_namespaces():
    reachable, imported_names = _main_reachable_modules()

    forbidden = sorted(
        (module, imported)
        for module in reachable
        for imported in imported_names[module]
        if imported == "tests"
        or imported.startswith("tests.")
        or imported == "scripts"
        or imported.startswith("scripts.")
    )

    assert forbidden == []


def test_product_runtime_module_budget_is_non_increasing():
    reachable, _ = _main_reachable_modules()

    assert len(reachable) <= 522
