from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATERIAL_DOMAIN_MODULES = tuple(
    sorted((PROJECT_ROOT / "src/domain/materials").glob("*.py"))
)


def test_material_domain_has_no_static_ui_or_service_import() -> None:
    violations: list[str] = []
    for path in MATERIAL_DOMAIN_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules = (
                (str(node.module or ""),)
                if isinstance(node, ast.ImportFrom)
                else tuple(alias.name for alias in node.names)
                if isinstance(node, ast.Import)
                else ()
            )
            for module in modules:
                if module == "src.ui" or module.startswith("src.ui."):
                    violations.append(f"{path.name}:{node.lineno}:{module}")
                if module == "src.services" or module.startswith("src.services."):
                    violations.append(f"{path.name}:{node.lineno}:{module}")
    assert MATERIAL_DOMAIN_MODULES
    assert violations == []


def test_material_domain_facade_import_does_not_load_storage_or_ui() -> None:
    script = """
import sys
import src.domain.materials as materials
assert materials.MaterialPackage.__module__ == 'src.domain.materials.model'
for name in tuple(sys.modules):
    assert not name.startswith('src.ui'), name
    assert not name.startswith('src.services'), name
    assert name != 'src.config.material_package_library', name
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_entity_fill_consumes_resolved_data_without_legacy_entity_archive() -> None:
    path = PROJECT_ROOT / "src/modules/fill/entity_fill.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imported_modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "entity_data = config.entity_data" in source
    assert not any(module.startswith("src.config.entity") for module in imported_modules)
    assert not any(module.startswith("src.services") for module in imported_modules)
