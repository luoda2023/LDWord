from __future__ import annotations

from collections.abc import Mapping

from src.qt_api import QObject, Signal


class ExecutionWorker(QObject):
    """Bridge a cooperative runner into Qt signals for the Workbench UI."""

    progress_changed = Signal(int, int, str)
    execution_started = Signal()
    execution_succeeded = Signal(object)
    execution_partial = Signal(object)
    execution_failed = Signal(object)
    execution_cancelled = Signal()
    execution_finished = Signal()

    def __init__(self, runner, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def _is_cancelled(self) -> bool:
        return self._cancel_requested

    def _result_status(self, result) -> str:
        if isinstance(result, Mapping):
            status = result.get("status")
        else:
            status = getattr(result, "status", None)

        if status in {"success", "partial_success", "failed", "cancelled"}:
            return status
        raise ValueError(f"Unknown execution status: {status!r}")

    def _normalize_result(self, result, status: str) -> dict[str, object]:
        if isinstance(result, Mapping):
            output_path = str(result.get("output_path") or "")
            output_paths = _normalize_path_map(result.get("output_paths"))
            compare_paths = _normalize_path_map(result.get("compare_paths"))
            intermediate_paths = _normalize_path_map(result.get("intermediate_paths"))
            material_manifest_paths = _normalize_path_map(result.get("material_manifest_paths"))
            material_package_paths = _normalize_path_map(result.get("material_package_paths"))
            scene_sample_manifest_paths = _normalize_path_map(
                result.get("scene_sample_manifest_paths")
            )
            output_target_preflight = _normalize_dict_payload(
                result.get("output_target_preflight")
            )
            object_preflight = _normalize_dict_payload(result.get("object_preflight"))
            material_field_consistency = _normalize_dict_payload(
                result.get("material_field_consistency")
            )
            batch_isolation = _normalize_dict_payload(result.get("batch_isolation"))
            question_figure_repair_queue = _normalize_dict_payload(
                result.get("question_figure_repair_queue")
            )
            question_figure_comparison_matrix = _normalize_dict_payload(
                result.get("question_figure_comparison_matrix")
            )
            batch_issue_items = list(result.get("batch_issue_items") or [])
            journal_submission_package = _normalize_dict_payload(
                result.get("journal_submission_package")
            )
            official_numbering_preservation = _normalize_dict_payload(
                result.get("official_numbering_preservation")
            )
            technical_chapter_inventory = _normalize_dict_payload(
                result.get("technical_chapter_inventory")
            )
            application_section_word_limits = _normalize_dict_payload(
                result.get("application_section_word_limits")
            )
            raw_report_paths = list(result.get("report_paths") or [])
            failed_items = list(result.get("failed_items") or [])
            failed_count = int(result.get("failed_count") or len(failed_items))
            error_text = str(result.get("error_text") or result.get("error") or "")
            diagnostics_count = int(result.get("diagnostics_count") or 0)
            diagnostics_summary = str(result.get("diagnostics_summary") or "")
            diagnostics_items = _normalize_diagnostics_items(result)
        else:
            output_path = str(getattr(result, "output_path", "") or "")
            output_paths = _normalize_path_map(getattr(result, "output_paths", None))
            compare_paths = _normalize_path_map(getattr(result, "compare_paths", None))
            intermediate_paths = _normalize_path_map(
                getattr(result, "intermediate_paths", None)
            )
            material_manifest_paths = _normalize_path_map(
                getattr(result, "material_manifest_paths", None)
            )
            material_package_paths = _normalize_path_map(
                getattr(result, "material_package_paths", None)
            )
            scene_sample_manifest_paths = _normalize_path_map(
                getattr(result, "scene_sample_manifest_paths", None)
            )
            output_target_preflight = _normalize_dict_payload(
                getattr(result, "output_target_preflight", None)
            )
            object_preflight = _normalize_dict_payload(
                getattr(result, "object_preflight", None)
            )
            material_field_consistency = _normalize_dict_payload(
                getattr(result, "material_field_consistency", None)
            )
            batch_isolation = _normalize_dict_payload(
                getattr(result, "batch_isolation", None)
            )
            question_figure_repair_queue = _normalize_dict_payload(
                getattr(result, "question_figure_repair_queue", None)
            )
            question_figure_comparison_matrix = _normalize_dict_payload(
                getattr(result, "question_figure_comparison_matrix", None)
            )
            batch_issue_items = list(getattr(result, "batch_issue_items", []) or [])
            journal_submission_package = _normalize_dict_payload(
                getattr(result, "journal_submission_package", None)
            )
            official_numbering_preservation = _normalize_dict_payload(
                getattr(result, "official_numbering_preservation", None)
            )
            technical_chapter_inventory = _normalize_dict_payload(
                getattr(result, "technical_chapter_inventory", None)
            )
            application_section_word_limits = _normalize_dict_payload(
                getattr(result, "application_section_word_limits", None)
            )
            raw_report_paths = list(getattr(result, "report_paths", []) or [])
            failed_items = list(getattr(result, "failed_items", []) or [])
            failed_count = int(getattr(result, "failed_count", 0) or len(failed_items))
            error_text = str(
                getattr(result, "error_text", "") or getattr(result, "error", "") or ""
            )
            diagnostics_count = int(getattr(result, "diagnostics_count", 0) or 0)
            diagnostics_summary = str(getattr(result, "diagnostics_summary", "") or "")
            raw_diagnostics_items = getattr(result, "diagnostics_items", None)
            if not raw_diagnostics_items:
                raw_diagnostics_items = getattr(result, "diagnostics", None)
            if not raw_diagnostics_items:
                raw_diagnostics_items = getattr(result, "material_diagnostics", None)
            diagnostics_items = _normalize_diagnostics_items(raw_diagnostics_items)

        if not output_path and output_paths:
            output_path = str(output_paths.get("final") or next(iter(output_paths.values()), ""))

        report_paths = [str(path) for path in raw_report_paths]

        payload = {
            "status": status,
            "output_path": output_path,
            "report_paths": report_paths,
            "failed_count": failed_count,
            "error_text": error_text,
            "diagnostics_count": diagnostics_count,
            "diagnostics_summary": diagnostics_summary,
        }
        if output_paths:
            payload["output_paths"] = output_paths
        if compare_paths:
            payload["compare_paths"] = compare_paths
        if intermediate_paths:
            payload["intermediate_paths"] = intermediate_paths
        if material_manifest_paths:
            payload["material_manifest_paths"] = material_manifest_paths
        if material_package_paths:
            payload["material_package_paths"] = material_package_paths
        if scene_sample_manifest_paths:
            payload["scene_sample_manifest_paths"] = scene_sample_manifest_paths
        if output_target_preflight:
            payload["output_target_preflight"] = output_target_preflight
        if object_preflight:
            payload["object_preflight"] = object_preflight
        if material_field_consistency:
            payload["material_field_consistency"] = material_field_consistency
        if batch_isolation:
            payload["batch_isolation"] = batch_isolation
        if question_figure_repair_queue:
            payload["question_figure_repair_queue"] = question_figure_repair_queue
        if question_figure_comparison_matrix:
            payload["question_figure_comparison_matrix"] = question_figure_comparison_matrix
        if batch_issue_items:
            payload["batch_issue_items"] = batch_issue_items
        if diagnostics_items:
            payload["diagnostics_items"] = diagnostics_items
        if journal_submission_package:
            payload["journal_submission_package"] = journal_submission_package
        if official_numbering_preservation:
            payload["official_numbering_preservation"] = official_numbering_preservation
        if technical_chapter_inventory:
            payload["technical_chapter_inventory"] = technical_chapter_inventory
        if application_section_word_limits:
            payload["application_section_word_limits"] = application_section_word_limits
        return payload

    def _failure_payload(self, error_text: str) -> dict[str, object]:
        return {
            "status": "failed",
            "output_path": "",
            "report_paths": [],
            "failed_count": 0,
            "error_text": error_text,
            "diagnostics_count": 0,
            "diagnostics_summary": "",
        }

    def run(self) -> None:
        self.execution_started.emit()
        try:
            result = self._runner.run(self.progress_changed.emit, self._is_cancelled)
            status = self._result_status(result)
            payload = self._normalize_result(result, status)
            if status == "cancelled":
                self.execution_cancelled.emit()
            elif status == "partial_success":
                self.execution_partial.emit(payload)
            elif status == "failed":
                self.execution_failed.emit(payload)
            else:
                self.execution_succeeded.emit(payload)
        except Exception as exc:
            self.execution_failed.emit(self._failure_payload(str(exc)))
        finally:
            self._cancel_requested = False
            self.execution_finished.emit()


def _normalize_path_map(value) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(path)
        for key, path in value.items()
        if str(key or "").strip() and str(path or "").strip()
    }


def _normalize_diagnostics_items(value) -> list[dict]:
    if isinstance(value, Mapping):
        raw_items = value.get("diagnostics_items")
        if not raw_items:
            diagnostics = value.get("diagnostics")
            if isinstance(diagnostics, Mapping):
                raw_items = diagnostics.get("items")
        if not raw_items and not value.get("batch_issue_items"):
            raw_items = value.get("material_diagnostics")
    else:
        raw_items = value
    return [dict(item) for item in list(raw_items or []) if isinstance(item, Mapping)]


def _normalize_dict_payload(value) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}
