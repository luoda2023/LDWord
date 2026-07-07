import sys
from pathlib import Path

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
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
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


def test_execution_worker_honors_cancel_flag():
    _app()
    worker = ExecutionWorker(_StubRunner())
    cancelled = []
    finished = []
    success = []
    partial = []
    failed = []
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.execution_finished.connect(lambda: finished.append(True))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.request_cancel()

    worker.run()

    assert cancelled == [True]
    assert finished == [True]
    assert success == []
    assert partial == []
    assert failed == []


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
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.execution_succeeded.connect(lambda payload: success.append(payload))
    worker.execution_partial.connect(lambda payload: partial.append(payload))
    worker.execution_failed.connect(lambda payload: failed.append(payload))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.request_cancel()
    worker.run()
    worker.run()

    assert cancelled == [True]
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


def test_execution_worker_supports_pipeline_result_objects():
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
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
    worker.execution_finished.connect(lambda: finished.append(True))

    worker.run()

    assert started == [True]
    assert success == []
    assert partial == [
        {
            "status": "partial_success",
            "output_path": "out.docx",
            "output_paths": {"final": "out.docx"},
            "report_paths": [],
            "failed_count": 1,
            "error_text": "1 module operation(s) failed.",
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }
    ]
    assert failed == []
    assert cancelled == []
    assert finished == [True]


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
    worker.execution_cancelled.connect(lambda: cancelled.append(True))
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
                "journal_submission_package": {
                    "status": "ok",
                    "summary": {"satisfied_required_count": 3},
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
            "journal_submission_package": {
                "status": "ok",
                "summary": {"satisfied_required_count": 3},
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
        "rule_name": "section_style",
        "reason": "参考文献字体需要确认",
        "parameter_path": "scene.section_styles.references_body.font_cn",
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
                        "kind": "scene_style_diagnostic",
                        "summary": "参考文献字体需要确认",
                        "parameter_path": "scene.section_styles.references_body.font_cn",
                    }
                ],
                "material_diagnostics": [
                    {
                        "rule_name": "section_style",
                        "reason": "参考文献字体需要确认",
                        "parameter_path": "scene.section_styles.references_body.font_cn",
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
