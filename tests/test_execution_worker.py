import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline.result import PipelineResult
from src.qt_api import QApplication
from src.ui.panels.workbench.execution_worker import ExecutionWorker


def _app():
    return QApplication.instance() or QApplication([])


class _StubRunner:
    def __init__(self):
        self.cancelled = False

    def run(self, progress_cb, cancel_check):
        progress_cb(1, 3, "prepare")
        if cancel_check():
            self.cancelled = True
            return {"status": "cancelled"}
        progress_cb(2, 3, "process")
        progress_cb(3, 3, "complete")
        return {"status": "success", "output_path": "out.docx", "report_paths": []}


def test_execution_worker_emits_progress_and_success_signals():
    _app()
    worker = ExecutionWorker(_StubRunner())
    progress = []
    success = []
    partial = []
    failed = []
    cancelled = []
    finished = []
    worker.progress_changed.connect(lambda cur, total, stage: progress.append((cur, total, stage)))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.execution_cancelled.connect(lambda payload: cancelled.append(payload))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.run()

    assert progress == [(1, 3, "prepare"), (2, 3, "process"), (3, 3, "complete")]
    assert success == [
        {
            "status": "success",
            "output_path": "out.docx",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]
    assert partial == []
    assert failed == []
    assert cancelled == []
    assert finished == [True]


def test_execution_worker_preserves_material_receipts_errors_and_artifact_failures():
    worker = ExecutionWorker(_StubRunner())
    receipt = {"receipt_id": "a" * 64, "variants": [{"variant_id": "final"}]}
    assembly = {"status": "applied", "receipt": receipt}
    artifact_failure = {
        "kind": "reports",
        "path": "report.json",
        "error_type": "OSError",
        "error": "disk full",
    }
    attachment_bundles = {
        "status": "applied",
        "file_count": 1,
        "receipts": {"evidence": {"receipt_id": "b" * 64}},
    }
    dependency_usage = {
        "index_id": "c" * 64,
        "occurrence_count": 1,
        "fields": [],
        "images": [],
        "consumers": [],
    }

    partial = worker._normalize_result(
        {
            "status": "partial_success",
            "output_path": "out.docx",
            "output_paths": {"final": Path("out.docx")},
            "material_assembly": assembly,
            "material_assembly_receipt": receipt,
            "material_assembly_error": None,
            "attachment_bundles": attachment_bundles,
            "material_dependency_usage": dependency_usage,
            "artifact_failures": [artifact_failure],
        },
        "partial_success",
    )
    assert partial["material_assembly"] == assembly
    assert partial["material_assembly_receipt"] == receipt
    assert partial["attachment_bundles"] == attachment_bundles
    assert partial["material_dependency_usage"] == dependency_usage
    assert "material_assembly_error" not in partial
    assert partial["artifact_failures"] == [artifact_failure]
    assert partial["output_paths"] == {"final": "out.docx"}

    error = {
        "primary": {
            "stage": "content_compose",
            "code": "content_compose_failed",
        }
    }
    failed = worker._normalize_result(
        {
            "status": "failed",
            "material_assembly": {"status": "failed", "error": error},
            "material_assembly_error": error,
            "artifact_failures": [artifact_failure],
        },
        "failed",
    )
    assert failed["material_assembly_error"] == error
    assert failed["artifact_failures"] == [artifact_failure]


def test_execution_worker_honors_cancel_flag():
    _app()
    worker = ExecutionWorker(_StubRunner())
    cancelled = []
    finished = []
    success = []
    partial = []
    failed = []
    worker.execution_cancelled.connect(lambda payload: cancelled.append(payload))
    worker.execution_finished.connect(lambda: finished.append(True))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.request_cancel()

    worker.run()

    assert cancelled == [
        {
            "status": "cancelled",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]
    assert finished == [True]
    assert success == []
    assert partial == []
    assert failed == []


def test_execution_worker_cancel_signal_preserves_published_evidence():
    _app()

    class _CancelledAfterPublicationRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "cancelled",
                "output_path": "published.docx",
                "output_paths": {"final": "published.docx"},
                "report_paths": ["batch_report.json"],
                "batch_isolation": {"completed_count": 1},
                "failed_count": 0,
            }

    worker = ExecutionWorker(_CancelledAfterPublicationRunner())
    cancelled = []
    worker.execution_cancelled.connect(lambda payload: cancelled.append(payload))

    worker.run()

    assert cancelled == [
        {
            "status": "cancelled",
            "output_path": "published.docx",
            "output_paths": {"final": "published.docx"},
            "report_paths": ["batch_report.json"],
            "batch_isolation": {"completed_count": 1},
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]


def test_execution_session_receipt_failure_is_observable_and_degrades_success(
    tmp_path,
    monkeypatch,
):
    _app()

    class _Runner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "success",
                "output_path": "published.docx",
                "execution_session": {
                    "session_id": "session-1",
                    "output_namespace": str(tmp_path),
                },
            }

    def fail_receipt(*_args, **_kwargs):
        raise OSError(28, "simulated receipt disk full", "execution_session.json")

    monkeypatch.setattr(
        "src.services.execution_session_result.atomic_write_text",
        fail_receipt,
    )
    worker = ExecutionWorker(_Runner())
    success = []
    partial = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))

    worker.run()

    assert success == []
    assert partial[0]["status"] == "partial_success"
    assert partial[0]["output_path"] == "published.docx"
    assert partial[0]["failed_count"] == 0
    assert partial[0]["artifact_failure_count"] == 1
    assert partial[0]["artifact_failures"] == [
        {
            "kind": "execution_session",
            "path": "execution_session.json",
            "error_type": "OSError",
            "error": (
                "[Errno 28] simulated receipt disk full: 'execution_session.json'"
            ),
        }
    ]


def test_execution_worker_resets_cancel_flag_after_run_finishes():
    _app()

    class _ReusableRunner:
        def __init__(self):
            self.calls = 0

        def run(self, progress_cb, cancel_check):
            self.calls += 1
            if cancel_check():
                return {"status": "cancelled"}
            progress_cb(1, 1, f"run-{self.calls}")
            return {"status": "success", "output_path": f"out-{self.calls}.docx", "report_paths": []}

    runner = _ReusableRunner()
    worker = ExecutionWorker(runner)
    cancelled = []
    success = []
    partial = []
    failed = []
    finished = []
    worker.execution_cancelled.connect(lambda payload: cancelled.append(payload))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.request_cancel()
    worker.run()
    worker.run()

    assert len(cancelled) == 1
    assert cancelled[0]["status"] == "cancelled"
    assert success == [
        {
            "status": "success",
            "output_path": "out-2.docx",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]
    assert partial == []
    assert failed == []
    assert finished == [True, True]


def test_execution_worker_rejects_non_mapping_runner_results():
    _app()

    class _PipelineResultRunner:
        def run(self, progress_cb, cancel_check):
            progress_cb(1, 1, "done")
            assert cancel_check() is False
            return PipelineResult(
                success=True,
                status="partial_success",
                output_paths={"final": "out.docx"},
                failed_items=[{"rule_name": "heading"}],
                error="1 module operation(s) failed.",
            )

    worker = ExecutionWorker(_PipelineResultRunner())
    started = []
    success = []
    partial = []
    failed = []
    cancelled = []
    finished = []
    worker.execution_started.connect(lambda: started.append(True))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.execution_cancelled.connect(lambda payload: cancelled.append(payload))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.run()

    assert started == [True]
    assert success == []
    assert partial == []
    assert failed == [
        {
            "status": "failed",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": (
                "Execution result must be a mapping, "
                "got src.pipeline.result.PipelineResult"
            ),
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]
    assert cancelled == []
    assert finished == [True]


def test_execution_worker_preserves_complete_runtime_extension_contract(tmp_path):
    _app()
    worker = ExecutionWorker(_StubRunner())

    payload = worker._normalize_result(
        {
            "status": "success",
            "output_paths": {"final": tmp_path / "out.docx"},
            "report_paths": [],
            "content_visibility_scan": {"status": "ok"},
            "content_visibility_preview": [
                {"preset_id": "student", "removed_paragraph_count": 1}
            ],
            "content_visibility_receipts": {
                "student": {"path": tmp_path / "receipt.json"}
            },
            "exam_question_schema": {"status": "ok"},
            "exam_delivery_runtime": {"status": "ok"},
            "exam_markdown_import": {"status": "ok"},
            "future_extension": {"artifact": tmp_path / "future.json"},
        },
        "success",
    )

    assert payload["content_visibility_scan"] == {"status": "ok"}
    assert payload["content_visibility_preview"] == [
        {"preset_id": "student", "removed_paragraph_count": 1}
    ]
    assert payload["content_visibility_receipts"] == {
        "student": {"path": str(tmp_path / "receipt.json")}
    }
    assert payload["exam_question_schema"] == {"status": "ok"}
    assert payload["exam_delivery_runtime"] == {"status": "ok"}
    assert payload["exam_markdown_import"] == {"status": "ok"}
    assert payload["future_extension"] == {
        "artifact": str(tmp_path / "future.json")
    }
    json.dumps(payload, allow_nan=False)


def test_execution_worker_preserves_explicit_empty_known_mappings():
    worker = ExecutionWorker(_StubRunner())

    payload = worker._normalize_result(
        {
            "status": "failed",
            "report_paths": [],
            "exam_markdown_import": {"status": "ok"},
            "exam_question_schema": {},
            "exam_delivery_runtime": {},
        },
        "failed",
    )

    assert payload["exam_question_schema"] == {}
    assert payload["exam_delivery_runtime"] == {}


def test_execution_worker_rejects_path_map_key_collisions_and_non_finite_values():
    worker = ExecutionWorker(_StubRunner())

    with pytest.raises(TypeError, match="key collision.*output_paths"):
        worker._normalize_result(
            {
                "status": "success",
                "output_paths": {1.0: "first.docx", "1.0": "second.docx"},
            },
            "success",
        )

    with pytest.raises(TypeError, match="non-finite.*output_paths"):
        worker._normalize_result(
            {
                "status": "success",
                "output_paths": {"final": float("nan")},
            },
            "success",
        )


def test_execution_worker_rejects_top_level_key_collision_with_known_field():
    worker = ExecutionWorker(_StubRunner())

    with pytest.raises(TypeError, match=r"key collision at \$: 'status'"):
        worker._normalize_result(
            {
                "status": "success",
                Path("status"): "must-not-be-silently-dropped",
            },
            "success",
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("exam_question_schema", ["wrong-shape"]),
        ("items", b"wrong-shape"),
        ("artifact_failures", {"kind": "wrong-shape"}),
        ("output_paths", ["wrong-shape"]),
    ],
)
def test_execution_worker_rejects_invalid_known_field_shapes(
    field_name,
    invalid_value,
):
    worker = ExecutionWorker(_StubRunner())

    with pytest.raises(TypeError):
        worker._normalize_result(
            {"status": "success", field_name: invalid_value},
            "success",
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("failed_count", "1"),
        ("failed_count", -1),
        ("artifact_failure_count", float("nan")),
        ("diagnostics_count", True),
        ("error_text", threading.Lock()),
        ("diagnostics_summary", ["wrong-shape"]),
    ],
)
def test_execution_worker_rejects_invalid_known_scalar_fields(
    field_name,
    invalid_value,
):
    worker = ExecutionWorker(_StubRunner())

    with pytest.raises((TypeError, ValueError)):
        worker._normalize_result(
            {"status": "success", field_name: invalid_value},
            "success",
        )


def test_execution_worker_rejects_mismatched_requested_status():
    worker = ExecutionWorker(_StubRunner())

    with pytest.raises(ValueError, match="does not match normalization request"):
        worker._normalize_result(
            {"status": "failed"},
            "success",
        )


def test_execution_worker_preserves_explicit_empty_diagnostics_items():
    worker = ExecutionWorker(_StubRunner())

    payload = worker._normalize_result(
        {
            "status": "success",
            "diagnostics_items": [],
            "material_diagnostics": [{"reason": "must not leak into projection"}],
        },
        "success",
    )

    assert "diagnostics_items" not in payload


def test_execution_worker_fails_closed_on_live_extension_object():
    _app()

    class _LiveObjectRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "success",
                "future_extension": {"lock": threading.Lock()},
            }

    worker = ExecutionWorker(_LiveObjectRunner())
    succeeded: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    worker.execution_succeeded.connect(succeeded.append)
    worker.execution_failed.connect(failed.append)

    worker.run()

    assert succeeded == []
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"
    assert "$.future_extension.lock" in str(failed[0]["error_text"])
    assert "_thread.lock" in str(failed[0]["error_text"])
    json.dumps(failed[0], allow_nan=False)


def test_execution_worker_treats_unknown_status_as_failure():
    _app()

    class _UnknownStatusRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {"status": "paused"}

    worker = ExecutionWorker(_UnknownStatusRunner())
    success = []
    partial = []
    failures = []
    cancelled = []
    finished = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failures.append(payload))
    worker.execution_cancelled.connect(lambda payload: cancelled.append(payload))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.run()

    assert success == []
    assert partial == []
    assert failures == [
        {
            "status": "failed",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "Unknown execution status: 'paused'",
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]
    assert cancelled == []
    assert finished == [True]


def test_execution_worker_normalizes_report_paths_to_strings():
    _app()

    class _PathResultRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "success",
                "output_path": Path("out.docx"),
                "report_paths": [Path("logs/report.json"), Path("logs/report.md")],
            }

    worker = ExecutionWorker(_PathResultRunner())
    success = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))

    worker.run()

    assert success == [
        {
            "status": "success",
            "output_path": "out.docx",
            "report_paths": [str(Path("logs/report.json")), str(Path("logs/report.md"))],
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]


def test_execution_worker_preserves_question_figure_repair_queue_payload():
    _app()

    class _QuestionFigureRepairQueueRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "partial_success",
                "output_path": "",
                "report_paths": [
                    Path("logs/source_batch_report.json"),
                    Path("logs/source_batch_report.md"),
                ],
                "batch_issue_items": [
                    {
                        "issue_id": "batch:exam:manual_compare:1",
                        "repair_target_type": "question_figure_item",
                    }
                ],
                "question_figure_comparison_matrix": {
                    "kind": "question_figure_comparison_matrix",
                    "total_issue_count": 1,
                },
                "question_figure_repair_queue": {
                    "kind": "question_figure_repair_queue",
                    "queue_count": 1,
                    "entries": [
                        {
                            "queue_id": "repair:question_figure:exam:q2:abc",
                            "status": "candidate",
                        }
                    ],
                },
            }

    worker = ExecutionWorker(_QuestionFigureRepairQueueRunner())
    partial = []
    worker.execution_partial.connect(lambda payload: partial.append(payload))

    worker.run()

    assert partial[0]["batch_issue_items"][0]["issue_id"] == (
        "batch:exam:manual_compare:1"
    )
    assert partial[0]["question_figure_comparison_matrix"]["total_issue_count"] == 1
    assert partial[0]["question_figure_repair_queue"]["queue_count"] == 1
    assert partial[0]["question_figure_repair_queue"]["entries"][0]["status"] == (
        "candidate"
    )


def test_execution_worker_preserves_delivery_artifact_maps():
    _app()

    class _ArtifactRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "success",
                "output_paths": {
                    "final": Path("out/final.docx"),
                    "review": Path("out/review.docx"),
                },
                "compare_paths": {"review": Path("out/review_compare.docx")},
                "intermediate_paths": {"review": Path("out/review_intermediate.json")},
                "material_manifest_paths": {"material": Path("out/material_manifest.json")},
                "material_package_paths": {"zip": Path("out/material_package.zip")},
                "material_package_receipt": {
                    "status": "incomplete",
                    "missing_reference_count": 1,
                },
                "material_package_receipts": {
                    "profile-a": {"status": "complete"},
                },
                "journal_submission_package": {
                    "status": "ok",
                    "summary": {"satisfied_required_count": 3},
                },
                "official_document_assembly": {
                    "status": "ok",
                    "profile_id": "notice",
                    "docx_path": Path("out/notice.docx"),
                },
                "official_numbering_preservation": {
                    "status": "preserved",
                    "strategy": "preserve",
                },
                "technical_chapter_inventory": {
                    "status": "ok",
                    "summary": {"chapter_count": 1, "appendix_count": 1},
                },
                "application_section_word_limits": {
                    "status": "warning",
                    "summary": {"exceeded_section_count": 1},
                },
                "batch_isolation": {
                    "kind": "batch_failure_isolation",
                    "total_count": 2,
                    "success_count": 1,
                    "failed_count": 1,
                },
                "output_target_preflight": {
                    "has_issues": True,
                    "items": [
                        {
                            "preset_id": "review",
                            "path": str(Path("out/review.docx")),
                            "issues": [{"kind": "target_exists", "message": "exists"}],
                        }
                    ],
                },
                "report_paths": [],
            }

    worker = ExecutionWorker(_ArtifactRunner())
    success = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))

    worker.run()

    assert success == [
        {
            "status": "success",
            "output_path": str(Path("out/final.docx")),
            "output_paths": {
                "final": str(Path("out/final.docx")),
                "review": str(Path("out/review.docx")),
            },
            "compare_paths": {"review": str(Path("out/review_compare.docx"))},
            "intermediate_paths": {"review": str(Path("out/review_intermediate.json"))},
            "material_manifest_paths": {"material": str(Path("out/material_manifest.json"))},
            "material_package_paths": {"zip": str(Path("out/material_package.zip"))},
            "material_package_receipt": {
                "status": "incomplete",
                "missing_reference_count": 1,
            },
            "material_package_receipts": {
                "profile-a": {"status": "complete"},
            },
            "journal_submission_package": {
                "status": "ok",
                "summary": {"satisfied_required_count": 3},
            },
            "official_document_assembly": {
                "status": "ok",
                "profile_id": "notice",
                "docx_path": str(Path("out/notice.docx")),
            },
            "official_numbering_preservation": {
                "status": "preserved",
                "strategy": "preserve",
            },
            "technical_chapter_inventory": {
                "status": "ok",
                "summary": {"chapter_count": 1, "appendix_count": 1},
            },
            "application_section_word_limits": {
                "status": "warning",
                "summary": {"exceeded_section_count": 1},
            },
            "batch_isolation": {
                "kind": "batch_failure_isolation",
                "total_count": 2,
                "success_count": 1,
                "failed_count": 1,
            },
            "output_target_preflight": {
                "has_issues": True,
                "items": [
                    {
                        "preset_id": "review",
                        "path": str(Path("out/review.docx")),
                        "issues": [{"kind": "target_exists", "message": "exists"}],
                    }
                ],
            },
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]


def test_execution_worker_preserves_diagnostics_fields():
    _app()

    class _DiagnosticRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            progress_cb(1, 1, "done")
            return {
                "status": "success",
                "output_path": "out.docx",
                "report_paths": [],
                "diagnostics_count": 1,
                "diagnostics_summary": "诊断提示（1）\n- [equation_table_format] 1 个公式编号: skipped",
            }

    worker = ExecutionWorker(_DiagnosticRunner())
    success = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))

    worker.run()

    assert success == [
        {
            "status": "success",
            "output_path": "out.docx",
            "report_paths": [],
            "failed_count": 0,
            "error_text": "",
            "diagnostics_count": 1,
            "diagnostics_summary": "诊断提示（1）\n- [equation_table_format] 1 个公式编号: skipped",
        }
    ]


def test_execution_worker_preserves_structured_diagnostics_items():
    _app()

    diagnostic = {
        "rule_name": "document_scope",
        "reason": "指定区域需要确认",
        "parameter_path": "scene.document_scope.selected_roles",
    }

    class _StructuredDiagnosticRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "success",
                "output_path": "out.docx",
                "report_paths": [],
                "diagnostics_count": 1,
                "diagnostics_summary": "诊断提示（1）",
                "diagnostics": {"items": [diagnostic]},
            }

    worker = ExecutionWorker(_StructuredDiagnosticRunner())
    success = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))

    worker.run()

    assert success[0]["diagnostics_items"] == [diagnostic]


def test_execution_worker_does_not_duplicate_batch_diagnostics_as_plain_items():
    _app()

    class _BatchRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "partial_success",
                "output_path": "",
                "report_paths": [],
                "batch_issue_items": [
                    {
                        "kind": "scene_document_scope_diagnostic",
                        "summary": "指定区域需要确认",
                        "parameter_path": "scene.document_scope.selected_roles",
                    }
                ],
                "material_diagnostics": [
                    {
                        "rule_name": "document_scope",
                        "reason": "指定区域需要确认",
                        "parameter_path": "scene.document_scope.selected_roles",
                    }
                ],
                "diagnostics_count": 1,
                "diagnostics_summary": "诊断提示（1）",
            }

    worker = ExecutionWorker(_BatchRunner())
    partial = []
    worker.execution_partial.connect(lambda payload: partial.append(payload))

    worker.run()

    assert "batch_issue_items" in partial[0]
    assert "diagnostics_items" not in partial[0]


def test_execution_worker_preserves_material_field_consistency_payload():
    _app()

    class _FieldConsistencyRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "success",
                "output_path": "out.docx",
                "report_paths": [],
                "material_field_consistency": {
                    "schema_id": "contract_parties_v1",
                    "family_id": "contract_delivery",
                    "status": "warning",
                    "field_count": 4,
                    "issue_count": 1,
                    "items": [],
                    "issues": [{"kind": "label_value_conflict"}],
                },
            }

    worker = ExecutionWorker(_FieldConsistencyRunner())
    success = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))

    worker.run()

    assert success[0]["material_field_consistency"]["schema_id"] == "contract_parties_v1"
    assert success[0]["material_field_consistency"]["issue_count"] == 1


def test_execution_worker_preserves_object_preflight_payload():
    _app()

    class _ObjectPreflightRunner:
        def run(self, progress_cb, cancel_check):
            assert cancel_check() is False
            return {
                "status": "success",
                "output_path": "out.docx",
                "report_paths": [],
                "object_preflight": {
                    "enabled": True,
                    "scan_targets": ["ole_objects"],
                    "findings_count": 1,
                    "findings": [{"kind": "ole_objects"}],
                    "module_skips_count": 1,
                    "module_skips": [{"module_name": "section_format"}],
                },
            }

    worker = ExecutionWorker(_ObjectPreflightRunner())
    success = []
    worker.execution_succeeded.connect(lambda payload: success.append(payload))

    worker.run()

    assert success[0]["object_preflight"]["findings_count"] == 1
    assert success[0]["object_preflight"]["module_skips_count"] == 1
