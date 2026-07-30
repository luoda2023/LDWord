from __future__ import annotations

import json

import src.product_report_writer as product_report_writer
import src.report_writer as report_writer
from src.pipeline.result import PipelineResult


def test_default_product_reports_do_not_load_internal_evidence(
    tmp_path,
    monkeypatch,
):
    def fail_if_loaded(*_args, **_kwargs):
        raise AssertionError("internal engineering evidence entered a product report")

    monkeypatch.setattr(
        report_writer,
        "_extract_scene_product_readiness",
        fail_if_loaded,
    )
    monkeypatch.setattr(
        report_writer,
        "_extract_scene_sample_fixture_manifest",
        fail_if_loaded,
    )
    monkeypatch.setattr(
        report_writer,
        "_extract_parameter_ownership",
        fail_if_loaded,
    )
    monkeypatch.setattr(
        report_writer,
        "_extract_control_contracts",
        fail_if_loaded,
    )

    result = PipelineResult(success=True)
    json_path = tmp_path / "product-report.json"
    markdown_path = tmp_path / "product-report.md"

    report_writer.write_json_report(
        result,
        input_path=tmp_path / "input.docx",
        output_path=tmp_path / "output.docx",
        report_path=json_path,
        elapsed=0.1,
        modules_enabled=0,
        modules_total=0,
    )
    report_writer.write_markdown_report(
        result,
        input_path=tmp_path / "input.docx",
        output_path=tmp_path / "output.docx",
        report_path=markdown_path,
        elapsed=0.1,
        modules_enabled=0,
        modules_total=0,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["status"] == "success"
    assert "scene_product_readiness" not in payload
    assert "scene_sample_fixtures" not in payload
    assert "parameter_ownership" not in payload
    assert "control_contracts" not in payload
    assert "产品成熟度证据" not in markdown
    assert "样本库证据" not in markdown
    assert "参数归属证据" not in markdown
    assert "控件契约证据" not in markdown


def test_product_report_writer_matches_legacy_public_projection(tmp_path):
    result = PipelineResult(success=True)
    common = {
        "input_path": tmp_path / "input.docx",
        "output_path": tmp_path / "output.docx",
        "elapsed": 0.25,
        "modules_enabled": 3,
        "modules_total": 4,
    }
    legacy_json = tmp_path / "legacy.json"
    product_json = tmp_path / "product.json"
    legacy_markdown = tmp_path / "legacy.md"
    product_markdown = tmp_path / "product.md"

    report_writer.write_json_report(
        result,
        report_path=legacy_json,
        **common,
    )
    product_report_writer.write_json_report(
        result,
        report_path=product_json,
        **common,
    )
    report_writer.write_markdown_report(
        result,
        report_path=legacy_markdown,
        **common,
    )
    product_report_writer.write_markdown_report(
        result,
        report_path=product_markdown,
        **common,
    )

    assert product_json.read_bytes() == legacy_json.read_bytes()
    assert product_markdown.read_bytes() == legacy_markdown.read_bytes()


def test_product_report_writer_delegates_explicit_internal_evidence(
    tmp_path,
    monkeypatch,
):
    calls: list[dict[str, object]] = []

    def record_internal(_result, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(report_writer, "write_json_report", record_internal)
    product_report_writer.write_json_report(
        PipelineResult(success=True),
        input_path=tmp_path / "input.docx",
        output_path=tmp_path / "output.docx",
        report_path=tmp_path / "internal.json",
        elapsed=0.1,
        modules_enabled=1,
        modules_total=1,
        include_internal_evidence=True,
    )

    assert calls and calls[0]["include_internal_evidence"] is True
