from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dependency_index_is_pure_and_filesystem_adapter_is_explicit() -> None:
    engine = (
        ROOT / "src/shared/engine/material_dependency_index.py"
    ).read_text(encoding="utf-8")
    indexer = (
        ROOT / "src/services/material_execution/dependency_indexer.py"
    ).read_text(encoding="utf-8")

    assert "from pathlib import" not in engine
    assert "from docx import" not in engine
    assert ".read_text(" not in engine
    assert "MaterialDependencyIndexer" in indexer
    assert "from docx import Document" in indexer
    assert "ContentArtifactRepository" in indexer
    assert ".load_fragment(" in indexer


def test_image_planner_uses_shared_docx_token_extractor() -> None:
    planner = (
        ROOT / "src/services/material_assets/image_plan_builder.py"
    ).read_text(encoding="utf-8")
    extractor = (
        ROOT / "src/shared/engine/docx_material_tokens.py"
    ).read_text(encoding="utf-8")

    assert "from src.shared.engine.docx_material_tokens import" in planner
    assert "def _document_token_blocks" not in planner
    assert "def extract_docx_material_token_blocks" in extractor


def test_all_material_renderers_share_one_strict_token_paragraph_contract() -> None:
    planner = (
        ROOT / "src/services/material_assets/image_plan_builder.py"
    ).read_text(encoding="utf-8")
    renderer = (
        ROOT / "src/services/material_content/docx_renderer.py"
    ).read_text(encoding="utf-8")
    attachment_renderer = (
        ROOT / "src/services/material_attachments/docx_renderer.py"
    ).read_text(encoding="utf-8")
    owner = (
        ROOT / "src/shared/engine/docx_material_tokens.py"
    ).read_text(encoding="utf-8")

    assert "def is_strict_material_token_paragraph" in owner
    assert "is_strict_material_token_paragraph(" in planner
    assert "is_strict_material_token_paragraph(" in renderer
    assert "is_strict_material_token_paragraph(" in attachment_renderer
    assert "def _is_strict_token_paragraph" not in planner
    assert "def _is_strict_anchor_paragraph" not in renderer
    assert "text.strip() != binding.anchor_token" not in attachment_renderer


def test_attachment_images_reuse_shared_plan_transform_and_layout_chain() -> None:
    processing = (
        ROOT / "src/services/material_attachments/processing.py"
    ).read_text(encoding="utf-8")
    executor = (
        ROOT / "src/services/material_assets/image_document_executor.py"
    ).read_text(encoding="utf-8")
    assembly = (
        ROOT / "src/services/material_execution/assembly.py"
    ).read_text(encoding="utf-8")

    assert ".add_picture(" not in processing
    assert ".add_picture(" not in executor
    assert "ImageInsertionPlanBuilder" in executor
    assert "ImageTransformBatch" in executor
    assert "build_office_image_layout_request" in executor
    assert "verify_office_layout_receipt" in executor
    assert "verify_office_layout_receipt" in assembly
    assert "def _verify_layout_geometry_evidence" not in assembly
