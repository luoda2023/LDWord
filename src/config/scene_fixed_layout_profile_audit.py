"""Fixed-layout profile productization audit for the scene matrix.

N2.178 sits after the row-height and Word-risk first slices.  It keeps
fixed-layout behavior out of generic table templates while proving that form
profiles can be browsed, previewed with fixtures, repaired, reported, and
validated through the scene-matrix release gate.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_coverage_manifest import (
    SceneCoveragePack,
    list_scene_coverage_packs,
)
from src.config.scene_source_evidence import scan_scene_source_markers


SCENE_FIXED_LAYOUT_PROFILE_AUDIT_ID = "scene_fixed_layout_profile_audit"

FIXED_LAYOUT_PROFILE_FAMILY_IDS: tuple[str, ...] = ("form_batch_documents",)
FIXED_LAYOUT_PROFILE_PACK_IDS: tuple[str, ...] = ("batch_forms",)
FIXED_LAYOUT_WORD_SURFACE_IDS: tuple[str, ...] = (
    "fixed_row_height",
    "content_controls",
    "textbox_shape",
)


@dataclass(frozen=True, slots=True)
class SceneFixedLayoutProfileEvidenceSpec:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    evidence_layer: str


@dataclass(frozen=True, slots=True)
class SceneFixedLayoutProfileSpec:
    profile_channel_id: str
    label: str
    coverage_selector: str
    fixed_layout_surface_ids: tuple[str, ...]
    word_ooxml_touchpoints: tuple[str, ...]
    runtime_surface_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    report_surface_ids: tuple[str, ...]
    repair_target_types: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence: tuple[SceneFixedLayoutProfileEvidenceSpec, ...]


@dataclass(frozen=True, slots=True)
class SceneFixedLayoutProfileIssue:
    profile_channel_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "profile_channel_id": self.profile_channel_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneFixedLayoutProfileEvidence:
    profile_channel_id: str
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]
    evidence_layer: str

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "profile_channel_id": self.profile_channel_id,
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "evidence_layer": self.evidence_layer,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneFixedLayoutProfileRow:
    profile_channel_id: str
    label: str
    coverage_selector: str
    pack_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    fixed_layout_surface_ids: tuple[str, ...]
    word_ooxml_touchpoints: tuple[str, ...]
    runtime_surface_ids: tuple[str, ...]
    ui_surface_ids: tuple[str, ...]
    report_surface_ids: tuple[str, ...]
    repair_target_types: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "profile_channel_id": self.profile_channel_id,
            "label": self.label,
            "coverage_selector": self.coverage_selector,
            "status": self.status,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "fixed_layout_surface_ids": list(self.fixed_layout_surface_ids),
            "word_ooxml_touchpoints": list(self.word_ooxml_touchpoints),
            "runtime_surface_ids": list(self.runtime_surface_ids),
            "ui_surface_ids": list(self.ui_surface_ids),
            "report_surface_ids": list(self.report_surface_ids),
            "repair_target_types": list(self.repair_target_types),
            "test_ids": list(self.test_ids),
            "evidence_ids": list(self.evidence_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneFixedLayoutProfileAuditReport:
    rows: tuple[SceneFixedLayoutProfileRow, ...]
    issues: tuple[SceneFixedLayoutProfileIssue, ...]
    source_evidence: tuple[SceneFixedLayoutProfileEvidence, ...]
    profile_channel_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def profile_channel_count(self) -> int:
        return len(self.rows)

    @property
    def ready_profile_channel_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def fixed_layout_surface_count(self) -> int:
        return len(
            _unique_values(
                surface for row in self.rows for surface in row.fixed_layout_surface_ids
            )
        )

    @property
    def word_ooxml_touchpoint_count(self) -> int:
        return len(
            _unique_values(
                touchpoint for row in self.rows for touchpoint in row.word_ooxml_touchpoints
            )
        )

    @property
    def runtime_surface_count(self) -> int:
        return len(
            _unique_values(surface for row in self.rows for surface in row.runtime_surface_ids)
        )

    @property
    def ui_surface_count(self) -> int:
        return len(_unique_values(surface for row in self.rows for surface in row.ui_surface_ids))

    @property
    def report_surface_count(self) -> int:
        return len(
            _unique_values(surface for row in self.rows for surface in row.report_surface_ids)
        )

    @property
    def repair_target_type_count(self) -> int:
        return len(
            _unique_values(target for row in self.rows for target in row.repair_target_types)
        )

    @property
    def test_evidence_count(self) -> int:
        return len(_unique_values(test_id for row in self.rows for test_id in row.test_ids))

    @property
    def covered_pack_count(self) -> int:
        return len(_unique_values(pack_id for row in self.rows for pack_id in row.pack_ids))

    @property
    def covered_family_count(self) -> int:
        return len(
            _unique_values(family_id for row in self.rows for family_id in row.family_ids)
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def source_evidence_count(self) -> int:
        return len(self.source_evidence)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_FIXED_LAYOUT_PROFILE_AUDIT_ID,
            "profile_channel_filter": self.profile_channel_filter,
            "counts": {
                "profile_channel_count": self.profile_channel_count,
                "ready_profile_channel_count": self.ready_profile_channel_count,
                "fixed_layout_surface_count": self.fixed_layout_surface_count,
                "word_ooxml_touchpoint_count": self.word_ooxml_touchpoint_count,
                "runtime_surface_count": self.runtime_surface_count,
                "ui_surface_count": self.ui_surface_count,
                "report_surface_count": self.report_surface_count,
                "repair_target_type_count": self.repair_target_type_count,
                "test_evidence_count": self.test_evidence_count,
                "covered_pack_count": self.covered_pack_count,
                "covered_family_count": self.covered_family_count,
                "issue_count": self.issue_count,
                "source_evidence_count": self.source_evidence_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


def _evidence(
    evidence_id: str,
    source_path: str,
    evidence_layer: str,
    *markers: str,
) -> SceneFixedLayoutProfileEvidenceSpec:
    return SceneFixedLayoutProfileEvidenceSpec(
        evidence_id=evidence_id,
        source_path=source_path,
        evidence_layer=evidence_layer,
        markers=tuple(markers),
    )


def _spec(
    profile_channel_id: str,
    label: str,
    coverage_selector: str,
    fixed_layout_surface_ids: tuple[str, ...],
    word_ooxml_touchpoints: tuple[str, ...],
    runtime_surface_ids: tuple[str, ...],
    ui_surface_ids: tuple[str, ...],
    report_surface_ids: tuple[str, ...],
    repair_target_types: tuple[str, ...],
    test_ids: tuple[str, ...],
    evidence: tuple[SceneFixedLayoutProfileEvidenceSpec, ...],
) -> SceneFixedLayoutProfileSpec:
    return SceneFixedLayoutProfileSpec(
        profile_channel_id=profile_channel_id,
        label=label,
        coverage_selector=coverage_selector,
        fixed_layout_surface_ids=fixed_layout_surface_ids,
        word_ooxml_touchpoints=word_ooxml_touchpoints,
        runtime_surface_ids=runtime_surface_ids,
        ui_surface_ids=ui_surface_ids,
        report_surface_ids=report_surface_ids,
        repair_target_types=repair_target_types,
        test_ids=test_ids,
        evidence=evidence,
    )


N2_178_FIXED_LAYOUT_PROFILE_SPECS: tuple[SceneFixedLayoutProfileSpec, ...] = (
    _spec(
        "fixed_layout_profile_policy_registry",
        "Fixed-layout profile policy registry",
        "fixed_layout_profile",
        ("fixed_row_height", "content_controls", "textbox_shape"),
        ("w:trHeight", "w:sdt", "w:txbxContent"),
        ("FixedLayoutRowHeightPolicy", "audit_fixed_layout_row_height_policies"),
        ("ScenePanel fixed-layout profile summary",),
        ("control_contracts.fixed_layout.table_row_height",),
        ("fixed_layout", "row_height", "content_controls", "textboxes"),
        (
            "test_form_batch_family_has_fixed_layout_row_height_policy",
            "test_control_contract_registry_keeps_row_height_out_of_generic_table_config",
        ),
        (
            _evidence(
                "config.fixed_layout_policy",
                "src/config/fixed_layout.py",
                "config",
                "FixedLayoutRowHeightPolicy",
                "form_batch_documents.table.row_height_pt",
                'applies_to=("tables", "content_controls", "textboxes")',
            ),
            _evidence(
                "test.fixed_layout_policy",
                "tests/test_scene_family_registry.py",
                "test",
                "def test_form_batch_family_has_fixed_layout_row_height_policy",
                "form_batch_documents.table.row_height_pt",
                "w:trHeight",
            ),
            _evidence(
                "test.control_contract_row_height",
                "tests/test_control_contract_registry.py",
                "test",
                "def test_control_contract_registry_keeps_row_height_out_of_generic_table_config",
                "fixed_layout.table_row_height",
                "not_generic_template",
            ),
        ),
    ),
    _spec(
        "row_height_ooxml_runtime",
        "Word w:trHeight runtime helper",
        "fixed_layout_profile",
        ("fixed_row_height",),
        ("w:tr", "w:trPr", "w:trHeight", "w:hRule"),
        (
            "row_height_state",
            "set_fixed_layout_row_height",
            "clear_fixed_layout_row_height",
            "apply_fixed_layout_row_height_policy",
        ),
        ("Fixed-layout preview fixture",),
        ("RowHeightPolicyApplication",),
        ("row_height",),
        (
            "test_fixed_layout_row_height_policy_writes_trheight_without_generic_table_config",
            "test_fixed_layout_row_height_preserve_policy_does_not_mutate_existing_trheight",
            "test_scene_sample_fixed_layout_preserves_existing_row_height",
        ),
        (
            _evidence(
                "runtime.row_height_ooxml",
                "src/shared/engine/fixed_layout_tables.py",
                "runtime",
                "def row_height_state",
                "def set_fixed_layout_row_height",
                "def clear_fixed_layout_row_height",
                "def apply_fixed_layout_row_height_policy",
                "w:trHeight",
            ),
            _evidence(
                "test.row_height_ooxml",
                "tests/test_table_format_semantics.py",
                "test",
                "def test_fixed_layout_row_height_policy_writes_trheight_without_generic_table_config",
                "def test_fixed_layout_row_height_preserve_policy_does_not_mutate_existing_trheight",
                "target_twips == 360",
            ),
            _evidence(
                "test.row_height_fixture_preserve",
                "tests/test_scene_sample_fixture_regression.py",
                "test",
                "def test_scene_sample_fixed_layout_preserves_existing_row_height",
                "height_twips == 400",
            ),
        ),
    ),
    _spec(
        "exam_answer_sheet_fixed_layout_runtime",
        "Exam answer-sheet writes fixed-layout table row height",
        "exam_answer_sheet_fixed_layout",
        ("fixed_row_height", "answer_sheet_table"),
        ("w:tbl", "w:tr", "w:trHeight", "w:hRule"),
        (
            "_render_exam_answer_sheet_docx",
            "apply_fixed_layout_row_height_policy",
            "ExamRenderedVersion.fixed_layout_kind",
        ),
        ("DeliveryPreset.answer_sheet", "Exam delivery runtime"),
        (
            "exam_delivery_runtime.rendered_versions.fixed_layout_kind",
            "exam_delivery_runtime.rendered_versions.fixed_layout_row_height_twips",
            "Markdown report",
        ),
        ("fixed_layout", "row_height"),
        (
            "test_exam_delivery_runtime_renders_markdown_preview_and_word_versions",
            "test_pipeline_records_exam_delivery_runtime_and_reports",
        ),
        (
            _evidence(
                "runtime.exam_answer_sheet_fixed_layout",
                "src/shared/engine/exam_question_schema.py",
                "runtime",
                "def _render_exam_answer_sheet_docx",
                "exam_teaching.answer_sheet_row_height",
                'applies_to=("answer_sheet_table",)',
                "fixed_layout_kind=\"answer_sheet\"",
            ),
            _evidence(
                "report.exam_answer_sheet_fixed_layout",
                "src/reporting/exam_sections.py",
                "report",
                "fixed_layout_kind",
                "fixed_layout_row_height_twips",
                "fixed_layout=",
            ),
            _evidence(
                "test.exam_answer_sheet_fixed_layout",
                "tests/test_exam_question_schema_runtime.py",
                "test",
                "row_height_state(sheet_doc.tables[0].rows[1]).height_twips == 440",
                "versions[\"answer_sheet\"].fixed_layout_kind == \"answer_sheet\"",
                "fixed_layout=answer_sheet",
            ),
        ),
    ),
    _spec(
        "generic_table_boundary",
        "Fixed row height stays out of generic TableConfig",
        "fixed_layout_profile",
        ("fixed_row_height",),
        ("TableConfig", "w:trHeight"),
        ("ResolvedConfig.table", "TemplateTableDetail"),
        ("Template table detail", "Control contract registry"),
        ("control_contracts.fixed_layout.table_row_height",),
        ("fixed_layout", "row_height"),
        (
            "test_table_config_no_longer_exposes_legacy_row_height_setting",
            "test_template_panel_table_detail_does_not_expose_row_height",
            "test_template_config_ignores_legacy_table_row_height_field",
        ),
        (
            _evidence(
                "test.generic_table_boundary",
                "tests/test_table_format_semantics.py",
                "test",
                "def test_table_config_no_longer_exposes_legacy_row_height_setting",
                "not hasattr(config.table, \"row_height_pt\")",
            ),
            _evidence(
                "test.template_table_boundary",
                "tests/test_template_secondary_details.py",
                "test",
                "def test_template_panel_table_detail_does_not_expose_row_height",
                "not hasattr(detail, \"_row_height_row\")",
            ),
            _evidence(
                "test.template_config_boundary",
                "tests/test_config_feature_hosting.py",
                "test",
                "def test_template_config_ignores_legacy_table_row_height_field",
                "row_height_pt",
            ),
        ),
    ),
    _spec(
        "fixed_layout_text_surface_runtime",
        "Content-control and textbox fixed-layout text runtime",
        "fixed_layout_text_surfaces",
        ("content_controls", "textbox_shape"),
        ("w:sdt", "w:txbxContent", "v:textbox", "wp:docPr"),
        (
            "replace_fixed_layout_placeholders",
            "replace_fixed_layout_mapped_fields",
            "iter_fixed_layout_text_blocks",
        ),
        ("Fixed-layout content-control preview", "Fixed-layout textbox preview"),
        ("fixed_layout_field_mapping",),
        ("content_controls", "textboxes"),
        (
            "test_fixed_layout_text_helper_reports_surface_counts",
            "test_fixed_layout_text_helper_replaces_mapped_field_surfaces",
            "test_fixed_layout_text_helper_replaces_vml_shape_anchor_textbox",
        ),
        (
            _evidence(
                "runtime.fixed_layout_text",
                "src/shared/engine/fixed_layout_text.py",
                "runtime",
                "FIXED_LAYOUT_TEXT_SURFACES",
                "def replace_fixed_layout_placeholders",
                "def replace_fixed_layout_mapped_fields",
                "def iter_fixed_layout_text_blocks",
            ),
            _evidence(
                "test.fixed_layout_text",
                "tests/test_fixed_layout_text_runtime.py",
                "test",
                "def test_fixed_layout_text_helper_reports_surface_counts",
                "def test_fixed_layout_text_helper_replaces_mapped_field_surfaces",
                "def test_fixed_layout_text_helper_replaces_vml_shape_anchor_textbox",
            ),
        ),
    ),
    _spec(
        "entity_fill_fixed_layout_mapping",
        "Entity fill writes fixed-layout mapped fields and report records",
        "fixed_layout_text_surfaces",
        ("content_controls", "textbox_shape"),
        ("w:sdt", "w:txbxContent"),
        ("EntityFillModule", "replace_fixed_layout_mapped_fields"),
        ("Workbench fill execution",),
        ("fixed_layout_field_mapping", "JSON report", "Markdown report"),
        ("content_controls", "textboxes", "placeholder_residue"),
        (
            "test_entity_fill_replaces_content_control_tags_aliases_and_textbox_anchors",
            "test_entity_fill_uses_profile_aliases_and_reports_fixed_layout_mapping",
        ),
        (
            _evidence(
                "runtime.entity_fill_fixed_layout",
                "src/modules/fill/entity_fill.py",
                "runtime",
                "replace_fixed_layout_placeholders",
                "replace_fixed_layout_mapped_fields",
                "fixed_layout_field_mapping",
            ),
            _evidence(
                "test.entity_fill_fixed_layout",
                "tests/test_fixed_layout_text_runtime.py",
                "test",
                "def test_entity_fill_replaces_content_control_tags_aliases_and_textbox_anchors",
                "def test_entity_fill_uses_profile_aliases_and_reports_fixed_layout_mapping",
                "fixed_layout_field_mapping",
            ),
        ),
    ),
    _spec(
        "form_batch_family_defaults",
        "Form-batch family applies fixed-layout defaults",
        "fixed_layout_profile",
        ("fixed_row_height", "content_controls", "textbox_shape", "placeholder_residue"),
        ("w:trHeight", "w:sdt", "w:txbxContent"),
        (
            "apply_planned_scene_family_defaults",
            "InputSourceProfile.form_batch_fields_v1",
            "ObjectPreflightPolicy.scan_targets",
            "DeliveryPreset.per_record_docx",
        ),
        ("ScenePanel family summary", "Workbench scene presets"),
        ("batch_summary_report", "residue_check_report"),
        ("fixed_layout", "content_controls", "textboxes"),
        ("test_form_batch_family_application_builds_fixed_layout_defaults",),
        (
            _evidence(
                "runtime.form_batch_defaults",
                "src/config/scene_family_application.py",
                "runtime",
                "form_batch_documents",
                "form_batch_fields_v1",
                "textboxes",
                "content_controls",
                "residue",
            ),
            _evidence(
                "test.form_batch_defaults",
                "tests/test_scene_family_application.py",
                "test",
                "def test_form_batch_family_application_builds_fixed_layout_defaults",
                "per_record_docx",
                "residue_check_report",
            ),
        ),
    ),
    _spec(
        "fixed_layout_sample_fixture_preview",
        "Fixed-layout profile has openable preview fixture",
        "fixed_layout_profile",
        ("fixed_row_height", "content_controls", "textbox_shape"),
        ("w:trHeight", "w:sdt", "w:txbxContent"),
        ("build_scene_sample_docx", "set_fixed_layout_row_height"),
        ("Sample fixture library", "DOCX preview fixture"),
        ("fixture_manifest", "request_cell_report"),
        ("fixed_layout", "row_height", "content_controls", "textboxes"),
        (
            "test_scene_sample_docx_fixtures_are_real_packages_and_preflight_detects_surfaces",
            "test_scene_sample_docx_library_generator_writes_openable_manifest",
        ),
        (
            _evidence(
                "registry.fixed_layout_fixture",
                "src/config/scene_sample_fixture_registry.py",
                "fixture",
                "batch_forms_fixed_layout",
                "fixed_row_height",
                "content_controls",
                "textboxes",
                "fixed_layout_row_height",
            ),
            _evidence(
                "runtime.fixed_layout_fixture_builder",
                "src/shared/engine/scene_sample_docx_builder.py",
                "runtime",
                "set_fixed_layout_row_height",
                'if "content_controls" in surfaces',
                'if "textboxes" in surfaces',
            ),
            _evidence(
                "test.fixed_layout_fixture",
                "tests/test_scene_sample_fixture_regression.py",
                "test",
                "def test_scene_sample_docx_fixtures_are_real_packages_and_preflight_detects_surfaces",
                "def test_scene_sample_docx_library_generator_writes_openable_manifest",
                "batch_forms_fixed_layout",
            ),
        ),
    ),
    _spec(
        "object_preflight_fixed_layout_surfaces",
        "ObjectPreflight detects fixed-layout Word surfaces",
        "fixed_layout_word_surfaces",
        ("content_controls", "textbox_shape"),
        ("w:sdt", "w:txbxContent", "v:textbox"),
        ("inspect_docx_package", "OBJECT_PREFLIGHT_SCAN_TARGETS"),
        ("Workbench object preflight details",),
        ("object_preflight report",),
        ("content_controls", "textboxes", "object_preflight"),
        (
            "test_object_preflight_detects_content_controls",
            "test_scene_sample_docx_fixtures_are_real_packages_and_preflight_detects_surfaces",
        ),
        (
            _evidence(
                "runtime.object_preflight_fixed_layout",
                "src/shared/engine/object_preflight.py",
                "runtime",
                "OBJECT_PREFLIGHT_SCAN_TARGETS",
                "content_controls",
                "textboxes",
                "w:txbxContent",
            ),
            _evidence(
                "test.object_preflight_fixed_layout",
                "tests/test_object_preflight_semantics.py",
                "test",
                "def test_object_preflight_detects_content_controls",
                "content_controls",
            ),
            _evidence(
                "test.sample_preflight_fixed_layout",
                "tests/test_scene_sample_fixture_regression.py",
                "test",
                "inspect_docx_package",
                "expected_preflight_findings",
            ),
        ),
    ),
    _spec(
        "fixed_layout_repair_route",
        "Fixed-layout issues route to the scene/fixed-layout repair surface",
        "fixed_layout_profile",
        ("fixed_row_height", "content_controls", "textbox_shape", "placeholder_residue"),
        ("w:trHeight", "w:sdt", "w:txbxContent"),
        ("repair_route_for_target", "WorkbenchPanel._open_issue_repair_target"),
        ("ScenePanel fixed-layout profile", "Object preflight details"),
        ("repair_route.fixed_layout",),
        ("fixed_layout", "row_height", "content_controls", "textboxes"),
        (
            "test_scene_repair_routing_registry_covers_n2_131_required_targets",
            "test_workbench_panel_routes_issue_repair_targets_to_existing_surfaces",
        ),
        (
            _evidence(
                "config.fixed_layout_repair_route",
                "src/config/scene_repair_routing.py",
                "routing",
                "route_id=\"fixed_layout\"",
                "row_height",
                "content_control",
                "textboxes",
            ),
            _evidence(
                "ui.workbench.fixed_layout_repair_route",
                "src/ui/adapters/workbench_product_issue_navigation.py",
                "ui",
                "SCENE_TARGET_CARD_MAP",
                '"row_height": "scn_cleanup"',
                '"content_controls": "scn_cleanup"',
                '"textboxes": "scn_cleanup"',
                "workbench_issue_navigation_for_target",
            ),
            _evidence(
                "test.fixed_layout_repair_route",
                "tests/test_scene_repair_routing.py",
                "test",
                "def test_scene_repair_routing_registry_covers_n2_131_required_targets",
                "repair_route_for_target(\"row_height\")",
            ),
            _evidence(
                "test.workbench_fixed_layout_repair_route",
                "tests/test_workbench_detail_architecture.py",
                "test",
                "form_batch_documents.table.row_height_pt",
                "content_controls",
            ),
        ),
    ),
    _spec(
        "fixed_layout_report_evidence",
        "Reports carry fixed-layout control-contract evidence",
        "fixed_layout_profile",
        ("fixed_row_height",),
        ("word.w:trHeight",),
        ("report_writer.control_contracts", "ControlContractEvidence"),
        ("Report detail",),
        ("control_contracts", "Markdown report"),
        ("row_height", "fixed_layout"),
        ("test_report_writer_emits_control_contract_evidence",),
        (
            _evidence(
                "report.fixed_layout_control_contract",
                "src/report_writer.py",
                "report",
                "fixed_layout.table_row_height",
                "control_contracts",
            ),
            _evidence(
                "test.report_fixed_layout_control_contract",
                "tests/test_execution_diagnostics_reporting.py",
                "test",
                "def test_report_writer_emits_control_contract_evidence",
                "fixed_layout.table_row_height",
                "word.w:trHeight",
            ),
        ),
    ),
    _spec(
        "matrix_browse_fixed_layout_profile",
        "Scene matrix can browse fixed-layout profile readiness",
        "fixed_layout_profile",
        ("fixed_row_height", "content_controls", "textbox_shape"),
        ("w:trHeight", "w:sdt", "w:txbxContent"),
        (
            "scene_fixed_layout_profile_audit",
            "SceneMatrixDashboard.fixed_layout_profile",
            "SceneMatrixDrilldown.fixed_layout_profile",
        ),
        ("Dashboard card", "Drilldown item", "Summary projection"),
        ("release_gate.counts",),
        ("fixed_layout", "row_height", "content_controls", "textboxes"),
        (
            "test_scene_fixed_layout_profile_audit_locks_n2_178_channels",
            "test_scene_matrix_drilldown_indexes_required_frontend_sources",
            "test_release_gate_includes_scene_fixed_layout_profile_audit",
        ),
        (
            _evidence(
                "dashboard.fixed_layout_profile",
                "src/config/scene_matrix_dashboard.py",
                "dashboard",
                "scene_fixed_layout_profile_audit",
                "fixed_layout_profile",
            ),
            _evidence(
                "drilldown.fixed_layout_profile",
                "src/config/scene_matrix_drilldown_items.py",
                "drilldown",
                "scene_fixed_layout_profile_audit",
                "fixed_layout_profile",
            ),
            _evidence(
                "summary.fixed_layout_profile",
                "scripts/verify_scene_matrix_release_gate.py",
                "release_gate_summary",
                "fixed_layout_profile_ready_channel_count",
                "fixed-layout profile",
            ),
            _evidence(
                "test.matrix_fixed_layout_profile",
                "tests/test_scene_fixed_layout_profile_audit.py",
                "test",
                "def test_scene_fixed_layout_profile_audit_locks_n2_178_channels",
                "def test_release_gate_includes_scene_fixed_layout_profile_audit",
            ),
        ),
    ),
)


def build_scene_fixed_layout_profile_audit_report(
    *,
    profile_channel_id: str = "",
    project_root: Path | str | None = None,
) -> SceneFixedLayoutProfileAuditReport:
    normalized_channel = str(profile_channel_id or "").strip()
    specs = tuple(
        spec
        for spec in N2_178_FIXED_LAYOUT_PROFILE_SPECS
        if not normalized_channel or spec.profile_channel_id == normalized_channel
    )
    packs = list_scene_coverage_packs()
    source_evidence = _source_evidence(specs, project_root)
    evidence_by_channel = _evidence_by_channel(source_evidence)
    rows = tuple(
        _row(spec, packs, evidence_by_channel.get(spec.profile_channel_id, ()))
        for spec in specs
    )
    issues = audit_scene_fixed_layout_profile_report(
        SceneFixedLayoutProfileAuditReport(
            rows=rows,
            issues=(),
            source_evidence=source_evidence,
            profile_channel_filter=normalized_channel,
        )
    )
    return SceneFixedLayoutProfileAuditReport(
        rows=rows,
        issues=issues,
        source_evidence=source_evidence,
        profile_channel_filter=normalized_channel,
    )


def audit_scene_fixed_layout_profile_report(
    report: SceneFixedLayoutProfileAuditReport,
) -> tuple[SceneFixedLayoutProfileIssue, ...]:
    issues: list[SceneFixedLayoutProfileIssue] = []
    seen_issue_keys: set[tuple[str, str, str]] = set()
    for row in report.rows:
        for issue_id in row.issue_ids:
            _append_issue(
                issues,
                seen_issue_keys,
                row.profile_channel_id,
                issue_id,
                f"Fixed-layout profile channel has unresolved issue: {issue_id}.",
            )
    for evidence in report.source_evidence:
        if evidence.status != "ready":
            _append_issue(
                issues,
                seen_issue_keys,
                evidence.profile_channel_id,
                f"missing_source_evidence.{evidence.evidence_id}",
                f"Missing source markers: {', '.join(evidence.missing_markers)}",
            )
    return tuple(issues)


def _append_issue(
    issues: list[SceneFixedLayoutProfileIssue],
    seen: set[tuple[str, str, str]],
    profile_channel_id: str,
    kind: str,
    message: str,
) -> None:
    key = (profile_channel_id, kind, message)
    if key in seen:
        return
    seen.add(key)
    issues.append(
        SceneFixedLayoutProfileIssue(
            profile_channel_id=profile_channel_id,
            kind=kind,
            message=message,
        )
    )


def _row(
    spec: SceneFixedLayoutProfileSpec,
    packs: tuple[SceneCoveragePack, ...],
    evidence: tuple[SceneFixedLayoutProfileEvidence, ...],
) -> SceneFixedLayoutProfileRow:
    pack_ids, family_ids = _coverage_links(spec.coverage_selector, packs)
    issue_ids: list[str] = []
    if not evidence:
        issue_ids.append("missing_evidence_specs")
    for item in evidence:
        if item.status != "ready":
            issue_ids.append(f"missing_source_evidence.{item.evidence_id}")
    if not pack_ids:
        issue_ids.append("missing_pack_coverage")
    if not family_ids:
        issue_ids.append("missing_family_coverage")
    if not spec.fixed_layout_surface_ids:
        issue_ids.append("missing_fixed_layout_surfaces")
    if not spec.word_ooxml_touchpoints:
        issue_ids.append("missing_word_ooxml_touchpoints")
    if not spec.runtime_surface_ids:
        issue_ids.append("missing_runtime_surfaces")
    if not spec.ui_surface_ids:
        issue_ids.append("missing_ui_surfaces")
    if not spec.report_surface_ids:
        issue_ids.append("missing_report_surfaces")
    if not spec.repair_target_types:
        issue_ids.append("missing_repair_target_types")
    if not spec.test_ids:
        issue_ids.append("missing_test_evidence")
    return SceneFixedLayoutProfileRow(
        profile_channel_id=spec.profile_channel_id,
        label=spec.label,
        coverage_selector=spec.coverage_selector,
        pack_ids=pack_ids,
        family_ids=family_ids,
        fixed_layout_surface_ids=spec.fixed_layout_surface_ids,
        word_ooxml_touchpoints=spec.word_ooxml_touchpoints,
        runtime_surface_ids=spec.runtime_surface_ids,
        ui_surface_ids=spec.ui_surface_ids,
        report_surface_ids=spec.report_surface_ids,
        repair_target_types=spec.repair_target_types,
        test_ids=spec.test_ids,
        evidence_ids=tuple(item.evidence_id for item in evidence),
        issue_ids=_unique_values(issue_ids),
    )


def _coverage_links(
    selector: str,
    packs: tuple[SceneCoveragePack, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if selector == "fixed_layout_profile":
        pack_ids = tuple(
            pack.pack_id
            for pack in packs
            if any(family_id in pack.planned_family_ids for family_id in FIXED_LAYOUT_PROFILE_FAMILY_IDS)
            or "fixed_layout_table" in pack.workflow_archetype_ids
        )
        return (_unique_values(pack_ids), FIXED_LAYOUT_PROFILE_FAMILY_IDS)
    if selector == "fixed_layout_pack":
        selected = tuple(pack for pack in packs if pack.pack_id in FIXED_LAYOUT_PROFILE_PACK_IDS)
        return (
            _unique_values(pack.pack_id for pack in selected),
            _unique_values(family_id for pack in selected for family_id in pack.planned_family_ids),
        )
    if selector == "exam_answer_sheet_fixed_layout":
        selected = tuple(pack for pack in packs if pack.pack_id == "exam_education")
        return (
            _unique_values(pack.pack_id for pack in selected),
            _unique_values(
                family_id
                for pack in selected
                for family_id in pack.planned_family_ids
                if family_id == "exam_teaching"
            ),
        )
    if selector == "fixed_layout_text_surfaces":
        selected = tuple(
            pack
            for pack in packs
            if {"content_controls", "textbox_shape"} & set(pack.word_risk_surface_ids)
        )
        return (
            _unique_values(pack.pack_id for pack in selected),
            _unique_values(family_id for pack in selected for family_id in pack.planned_family_ids),
        )
    if selector == "fixed_layout_word_surfaces":
        selected = tuple(
            pack
            for pack in packs
            if set(FIXED_LAYOUT_WORD_SURFACE_IDS) & set(pack.word_risk_surface_ids)
        )
        return (
            _unique_values(pack.pack_id for pack in selected),
            _unique_values(family_id for pack in selected for family_id in pack.planned_family_ids),
        )
    selected = tuple(
        pack
        for pack in packs
        if any(family_id in pack.planned_family_ids for family_id in FIXED_LAYOUT_PROFILE_FAMILY_IDS)
    )
    return (
        _unique_values(pack.pack_id for pack in selected),
        _unique_values(family_id for pack in selected for family_id in pack.planned_family_ids),
    )


def _source_evidence(
    specs: Iterable[SceneFixedLayoutProfileSpec],
    project_root: Path | str | None,
) -> tuple[SceneFixedLayoutProfileEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    evidence_specs = tuple(
        (spec.profile_channel_id, item)
        for spec in specs
        for item in spec.evidence
    )
    marker_results = scan_scene_source_markers(
        root,
        tuple(
            (item.evidence_id, item.source_path, item.markers)
            for _, item in evidence_specs
        ),
    )
    return tuple(
        SceneFixedLayoutProfileEvidence(
            profile_channel_id=profile_channel_id,
            evidence_id=result.source_id,
            source_path=result.source_path,
            markers=result.markers,
            missing_markers=result.missing_markers,
            evidence_layer=item.evidence_layer,
        )
        for (profile_channel_id, item), result in zip(evidence_specs, marker_results)
    )


def _evidence_by_channel(
    evidence: Iterable[SceneFixedLayoutProfileEvidence],
) -> dict[str, tuple[SceneFixedLayoutProfileEvidence, ...]]:
    grouped: dict[str, list[SceneFixedLayoutProfileEvidence]] = {}
    for item in evidence:
        grouped.setdefault(item.profile_channel_id, []).append(item)
    return {key: tuple(value) for key, value in grouped.items()}


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "N2_178_FIXED_LAYOUT_PROFILE_SPECS",
    "SCENE_FIXED_LAYOUT_PROFILE_AUDIT_ID",
    "SceneFixedLayoutProfileAuditReport",
    "SceneFixedLayoutProfileEvidence",
    "SceneFixedLayoutProfileIssue",
    "SceneFixedLayoutProfileRow",
    "audit_scene_fixed_layout_profile_report",
    "build_scene_fixed_layout_profile_audit_report",
]
