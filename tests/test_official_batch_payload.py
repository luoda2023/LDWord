from types import SimpleNamespace

from src.reporting.official_batch_payload import (
    official_document_batch_exception_payload,
    official_document_batch_item_payload,
    official_document_batch_preflight_failure_payload,
)


def _item():
    return SimpleNamespace(
        profile_id="task-1",
        profile_name="通知任务",
        output_dir="out/task-1",
    )


def test_official_batch_item_payload_keeps_outputs_and_import_diagnostics():
    assembly = SimpleNamespace(
        ok=True,
        profile_id="notice",
        status="success",
        output_paths={
            "official_docx": "out/task-1/notice.docx",
            "archive_manifest": "out/task-1/manifest.json",
        },
        missing_required_fields=(),
        unresolved_placeholders=(),
        to_dict=lambda: {"status": "success", "profile_id": "notice"},
    )

    payload = official_document_batch_item_payload(
        _item(),
        assembly,
        metadata={"unknown_fields": ["legacy_column"]},
    )

    assert payload["status"] == "success"
    assert payload["output_path"] == "out/task-1/notice.docx"
    assert payload["material_manifest_paths"] == {
        "archive_manifest": "out/task-1/manifest.json"
    }
    assert payload["diagnostics_count"] == 1
    assert payload["material_diagnostics"][0]["change_type"] == (
        "official_unknown_material_fields"
    )


def test_official_batch_failure_payloads_preserve_runtime_reason_contract():
    preflight = official_document_batch_preflight_failure_payload(
        _item(),
        profile_id="notice",
        error_text="missing title",
        material_diagnostics=[{"reason": "missing title"}],
        metadata={},
    )
    exception = official_document_batch_exception_payload(
        _item(),
        profile_id="notice",
        error_text="boom",
        metadata={},
    )

    assert preflight["error_text"] == "missing title"
    assert preflight["failed_count"] == 1
    assert exception["error_text"] == "公文批次任务执行异常: boom"
    assert exception["material_diagnostics"][0]["level"] == "error"
