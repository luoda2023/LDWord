import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_scene_matrix_release_gate import (  # noqa: E402
    build_scene_matrix_release_gate_payload,
)
from src.config.scene_release_trace_partition_guard_audit import (  # noqa: E402
    audit_scene_release_trace_partition_guard_report,
    build_scene_release_trace_partition_guard_audit_report,
)


def test_release_trace_partition_guard_covers_terminal_traces_without_overlap():
    report = build_scene_release_trace_partition_guard_audit_report(project_root=ROOT)
    payload = report.to_payload()
    rows = {row.partition_id: row for row in report.rows}
    source_status = {
        evidence["source_id"]: evidence["status"]
        for evidence in payload["source_evidence"]
    }

    assert report.status == "passed"
    assert audit_scene_release_trace_partition_guard_report(report) == ()
    assert payload["counts"]["partition_count"] == 3
    assert payload["counts"]["ready_partition_count"] == 3
    assert payload["counts"]["terminal_trace_count"] == 36
    assert payload["counts"]["subject_trace_count"] == 26
    assert payload["counts"]["non_subject_trace_count"] == 10
    assert payload["counts"]["partitioned_trace_count"] == 36
    assert payload["counts"]["missing_trace_count"] == 0
    assert payload["counts"]["overlap_trace_count"] == 0
    assert payload["counts"]["extra_trace_count"] == 0
    assert payload["counts"]["issue_count"] == 0
    assert payload["counts"]["missing_source_evidence_count"] == 0
    assert source_status["export_script"] == "ready"

    assert rows["terminal_release_trace_total"].trace_count == 36
    assert rows["subject_release_trace_partition"].trace_count == 26
    assert rows["non_subject_release_trace_partition"].trace_count == 10
    assert rows["terminal_release_trace_total"].status == "partition_ready"
    assert (
        set(report.subject_trace_ids) | set(report.non_subject_trace_ids)
    ) == set(report.terminal_trace_ids)
    assert set(report.subject_trace_ids).isdisjoint(report.non_subject_trace_ids)


def test_release_trace_partition_guard_export_script_supports_json_and_markdown():
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_trace_partition_guard_audit.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(json_result.stdout)

    assert payload["status"] == "passed"
    assert payload["counts"]["terminal_trace_count"] == 36
    assert payload["counts"]["partitioned_trace_count"] == 36
    rows = {row["partition_id"]: row for row in payload["rows"]}
    subject = rows["subject_release_trace_partition"]
    assert subject["trace_count"] == 26
    assert subject["expected_trace_count"] == 26
    assert (
        "boundary_guarded_maturity:family:ip_patent_documents"
        in subject["trace_ids"]
    )
    non_subject = rows["non_subject_release_trace_partition"]
    assert non_subject["trace_count"] == 10
    assert non_subject["expected_trace_count"] == 10
    assert (
        "managed_residual_warnings:scene_count_profile_audit:count_profile:basic:registry_only_profile"
        in non_subject["trace_ids"]
    )
    partitions = payload["trace_partitions"]
    assert len(partitions["subject_trace_ids"]) == 26
    assert len(partitions["non_subject_trace_ids"]) == 10
    assert partitions["missing_trace_ids"] == []
    assert partitions["overlap_trace_ids"] == []

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_release_trace_partition_guard_audit.py",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Release Trace Partition Guard Audit" in markdown_result.stdout
    assert "Partitioned traces: 36/36" in markdown_result.stdout
    assert "subject_release_trace_partition" in markdown_result.stdout
    assert "non_subject_release_trace_partition" in markdown_result.stdout


def test_release_gate_includes_release_trace_partition_guard(tmp_path):
    payload = build_scene_matrix_release_gate_payload(tmp_path)

    assert payload["status"] == "passed"
    assert payload["checks"]["scene_release_trace_partition_guard_audit"][
        "status"
    ] == "passed"
    assert payload["counts"]["scene_release_trace_partition_guard_partition_count"] == 3
    assert payload["counts"]["scene_release_trace_partition_guard_ready_count"] == 3
    assert (
        payload["counts"]["scene_release_trace_partition_guard_terminal_trace_count"]
        == 36
    )
    assert (
        payload["counts"]["scene_release_trace_partition_guard_subject_trace_count"]
        == 26
    )
    assert (
        payload["counts"][
            "scene_release_trace_partition_guard_non_subject_trace_count"
        ]
        == 10
    )
    assert (
        payload["counts"][
            "scene_release_trace_partition_guard_partitioned_trace_count"
        ]
        == 36
    )
    assert (
        payload["counts"]["scene_release_trace_partition_guard_missing_trace_count"]
        == 0
    )
    assert (
        payload["counts"]["scene_release_trace_partition_guard_overlap_trace_count"]
        == 0
    )
    assert (
        payload["counts"]["scene_release_trace_partition_guard_extra_trace_count"]
        == 0
    )
