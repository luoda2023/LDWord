from src.services.artifact_failure import (
    apply_artifact_failures,
    capture_artifact_write,
    record_artifact_failure,
)


def test_apply_artifact_failures_is_the_single_status_and_text_policy():
    payload = {
        "status": "success",
        "error_text": "business warning",
        "artifact_failures": [
            {
                "kind": "existing",
                "path": "old.json",
                "error_type": "OSError",
                "error": "old failure",
            }
        ],
    }

    apply_artifact_failures(
        payload,
        [
            {
                "kind": "report",
                "path": "new.json",
                "error_type": "OSError",
                "error": "disk full",
            }
        ],
    )

    assert payload["status"] == "partial_success"
    assert payload["artifact_failure_count"] == 2
    assert [item["kind"] for item in payload["artifact_failures"]] == [
        "existing",
        "report",
    ]
    assert payload["error_text"] == (
        "business warning; auxiliary artifact failures: report: disk full"
    )


def test_record_artifact_failure_stays_json_safe_and_preserves_business_failure():
    payload = {"status": "failed", "error_text": "validation failed"}

    record_artifact_failure(
        payload,
        "execution_session",
        OSError(28, "disk full", "execution_session.json"),
    )

    assert payload["status"] == "failed"
    assert payload["artifact_failure_count"] == 1
    assert payload["artifact_failures"][0]["path"].endswith(
        "execution_session.json"
    )
    assert "execution_session: [Errno 28]" in payload["error_text"]


def test_capture_artifact_write_returns_default_and_records_failure():
    failures = []

    result = capture_artifact_write(
        failures,
        "markdown_report",
        lambda: (_ for _ in ()).throw(RuntimeError("render failed")),
        [],
    )

    assert result == []
    assert failures == [
        {
            "kind": "markdown_report",
            "path": "",
            "error_type": "RuntimeError",
            "error": "render failed",
        }
    ]
