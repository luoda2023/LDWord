from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent

OPTIONAL_ASSET_MODULES = (
    "src.services.material_attachments.timeline_preparation",
    "src.services.material_assets.question_figures",
    "src.services.material_assets.question_library",
    "src.services.material_assets.repair_audit",
    "src.services.material_assets.word_docx_recovery",
)

CORE_PROCESSING_MODULES = (
    "src.services.material_assets.image_document_executor",
    "src.services.material_assets.image_execution_verifier",
    "src.services.material_assets.image_plan_builder",
    "src.services.material_assets.image_transform_batch",
    "src.services.material_assets.image_transformer",
)


def test_material_assets_public_package_has_no_eager_optional_imports():
    path = ROOT / "src/services/material_assets/__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert not imported.intersection(OPTIONAL_ASSET_MODULES)


def test_attachment_processing_loads_only_core_image_execution_closure():
    script = f"""
import json
import sys
import src.services.material_attachments.processing

names = {json.dumps((*OPTIONAL_ASSET_MODULES, *CORE_PROCESSING_MODULES))}
print(json.dumps({{name: name in sys.modules for name in names}}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    loaded = json.loads(result.stdout)

    assert all(not loaded[name] for name in OPTIONAL_ASSET_MODULES)
    assert all(loaded[name] for name in CORE_PROCESSING_MODULES)


def test_release_collects_processing_without_collecting_attachment_package():
    script = (ROOT / "scripts/windows/package_release.bat").read_text(
        encoding="utf-8"
    )

    assert "--hidden-import src.services.material_attachments.processing" in script
    assert "--collect-submodules src.services.material_attachments" not in script
