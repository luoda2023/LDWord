from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTITY_MODULES = (
    PROJECT_ROOT / "src/config/entity.py",
    PROJECT_ROOT / "src/config/entity_models.py",
    PROJECT_ROOT / "src/config/entity_archive_codec.py",
    PROJECT_ROOT / "src/config/entity_archive_validation.py",
    PROJECT_ROOT / "src/config/entity_archive_wire_contracts.py",
    PROJECT_ROOT / "src/config/entity_wire_validation.py",
    PROJECT_ROOT / "src/config/entity_timeline_wire_validation.py",
    PROJECT_ROOT / "src/config/entity_bundle.py",
    PROJECT_ROOT / "src/config/entity_bundle_preflight.py",
    PROJECT_ROOT / "src/config/entity_artifact_gateway.py",
)


def test_entity_modules_have_no_static_config_to_services_import() -> None:
    violations: list[str] = []
    for path in ENTITY_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module == "src.services" or module.startswith("src.services."):
                    violations.append(f"{path.name}:{node.lineno}:{module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "src.services" or alias.name.startswith(
                        "src.services."
                    ):
                        violations.append(
                            f"{path.name}:{node.lineno}:{alias.name}"
                        )
    assert violations == []


def test_entity_facade_model_import_does_not_load_io_or_service_layers() -> None:
    script = """
import sys
import src.config.entity as entity
assert entity.EntityProfile.__module__ == 'src.config.entity_models'
for name in (
    'src.config.entity_archive_codec',
    'src.config.entity_archive_validation',
    'src.config.entity_archive_wire_contracts',
    'src.config.entity_wire_validation',
    'src.config.entity_timeline_wire_validation',
    'src.config.entity_bundle',
    'src.config.entity_bundle_preflight',
    'src.config.library',
    'src.services.material_content.artifact_repository',
):
    assert name not in sys.modules, name
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_bundle_without_content_artifacts_does_not_load_content_service() -> None:
    script = """
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from src.config.entity import EntityArchive, save_entity_archive_bundle
with TemporaryDirectory() as temporary_directory:
    save_entity_archive_bundle(
        EntityArchive(archive_id='empty'),
        Path(temporary_directory) / 'package',
    )
assert 'src.services.material_content.artifact_repository' not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_entity_facade_delegates_io_to_single_implementation_modules() -> None:
    from src.config import entity

    assert entity.load_entity_archive.__module__ == (
        "src.config.entity_archive_codec"
    )
    assert entity.save_entity_archive.__module__ == (
        "src.config.entity_archive_codec"
    )
    assert entity.save_entity_archive_bundle.__module__ == (
        "src.config.entity_bundle"
    )
