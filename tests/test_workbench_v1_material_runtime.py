from __future__ import annotations

from pathlib import Path

from src.application.materials import (
    RUNTIME_IMAGE_WATERMARK_KEY,
    MaterialPreviewSnapshot,
    MaterialRuntimeFieldPreview,
)
from src.domain.materials import (
    MaterialIssue,
    MaterialPackageRef,
    MaterialRunSelection,
    generate_package_id,
    generate_record_id,
)
from src.ui.panels.workbench.material_state import material_execution_gate
from src.ui.panels.workbench.quick_execution_detail import QuickExecutionDetail

ROOT = Path(__file__).resolve().parents[1]


def test_quick_execution_floating_inputs_update_the_run_selection(qapp) -> None:
    selection = MaterialRunSelection(
        package_ref=MaterialPackageRef(
            generate_package_id(),
            "sha256:" + "a" * 64,
        ),
        selected_record_ids=(generate_record_id(),),
    )
    preview = MaterialPreviewSnapshot(
        package_id=selection.package_ref.package_id,
        package_revision=selection.package_ref.revision,
        package_name="运行资料",
        source_type="user",
        runtime_fields=(
            MaterialRuntimeFieldPreview(
                "start",
                "开始日期",
                editor_kind="date",
                timeline=True,
            ),
            MaterialRuntimeFieldPreview(
                RUNTIME_IMAGE_WATERMARK_KEY,
                "图片水印文字",
                image_watermark=True,
            ),
        ),
    )
    detail = QuickExecutionDetail(include_shared_chrome=False)
    try:
        detail.set_material_selection(selection, preview_snapshot=preview)
        detail._on_floating_field_changed("start", "2026-08-01")
        detail._on_floating_field_changed(
            RUNTIME_IMAGE_WATERMARK_KEY,
            "内部使用",
        )

        frozen = detail.execution_material_selection()

        assert frozen is not None
        assert frozen.runtime_field_overrides["start"] == "2026-08-01"
        assert frozen.runtime_image_watermark_text == "内部使用"
        assert set(detail._floating_field_inputs) == {
            "start",
            RUNTIME_IMAGE_WATERMARK_KEY,
        }
    finally:
        detail.deleteLater()
        qapp.processEvents()


def test_all_workbench_run_paths_consume_quick_runtime_selection() -> None:
    source = (
        ROOT / "src/ui/panels/workbench/panel_v2.py"
    ).read_text(encoding="utf-8")
    start_batch = source.split("    def _start_batch_execution(", 1)[1].split(
        "    def _start_failed_batch_retry(", 1
    )[0]
    retry = source.split("    def _start_failed_batch_retry(", 1)[1]

    expected = "self._quick_execution_detail.execution_material_selection()"
    assert expected in start_batch
    assert expected in retry


def test_material_execution_gate_blocks_errors_and_routes_to_package() -> None:
    decision = material_execution_gate(
        None,
        (
            MaterialIssue(
                code="material.selection.package_unavailable",
                path="package_id",
                message="Package is unavailable.",
            ),
        ),
    )

    assert decision.can_run is False
    assert decision.blocking_reasons == ("Package is unavailable.",)
    assert decision.primary_action is not None
    assert decision.primary_action.target_type == "material_package"


def test_material_execution_gate_keeps_warnings_runnable() -> None:
    decision = material_execution_gate(
        None,
        (
            MaterialIssue(
                code="material.preview.optional_gap",
                message="Optional material is missing.",
                severity="warning",
            ),
        ),
    )

    assert decision.can_run is True
    assert decision.warning_reasons == ("Optional material is missing.",)
    assert decision.primary_action is not None
    assert decision.primary_action.target_type == "material_package"


def test_quick_material_repair_action_targets_package_editor(qapp) -> None:
    detail = QuickExecutionDetail(include_shared_chrome=False)
    emitted = []
    try:
        detail.material_repair_requested.connect(
            lambda target_type, target_key: emitted.append((target_type, target_key))
        )
        detail.set_material_issues(
            (
                MaterialIssue(
                    code="material.selection.package_unavailable",
                    message="Package is unavailable.",
                ),
            )
        )

        detail._request_material_repair()

        assert emitted == [("material_package", "")]
    finally:
        detail.deleteLater()
        qapp.processEvents()
