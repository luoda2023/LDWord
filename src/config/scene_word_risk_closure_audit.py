"""Word/OOXML risk-surface closure audit for the scene matrix.

N2.157D closes a gap between the high-level scene matrix and the real DOCX
package model: every declared Word risk surface must be tied to scene packs,
sample fixtures when the surface can be represented in minimal DOCX samples,
runtime evidence, tests, and object-preflight/report/workbench visibility where
that surface is fragile enough to need preflight.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.config.scene_coverage_manifest import (
    list_scene_coverage_packs,
    list_word_risk_surfaces,
)
from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures
from src.shared.engine.object_preflight import OBJECT_PREFLIGHT_SCAN_TARGETS


N2_157D_WORD_RISK_SURFACE_IDS: tuple[str, ...] = tuple(
    surface.surface_id for surface in list_word_risk_surfaces()
)

WORD_RISK_SAMPLE_SURFACE_MAP: dict[str, tuple[str, ...]] = {
    "paragraph_run": ("paragraph_run",),
    "table_grid": ("table_grid",),
    "fixed_row_height": ("fixed_row_height",),
    "content_controls": ("content_controls",),
    "textbox_shape": ("textboxes",),
    "drawing_media_rels": (
        "embedded_packages",
        "ole_objects",
        "embedded_workbooks",
        "macros",
    ),
    "fields": ("fields",),
    "comments_revisions": ("comments", "tracked_changes"),
    "hidden_text": ("hidden_text",),
    "ole_embedded_vba": ("ole_objects", "embedded_workbooks", "macros"),
    "package_relationships": (
        "embedded_packages",
        "ole_objects",
        "embedded_workbooks",
        "macros",
    ),
}

WORD_RISK_PREFLIGHT_TARGET_MAP: dict[str, tuple[str, ...]] = {
    "content_controls": ("content_controls",),
    "textbox_shape": ("textboxes",),
    "drawing_media_rels": (
        "visio_drawings",
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "macros",
    ),
    "fields": ("fields",),
    "comments_revisions": ("comments", "tracked_changes"),
    "hidden_text": ("hidden_text",),
    "ole_embedded_vba": ("ole_objects", "embedded_workbooks", "macros"),
    "package_relationships": (
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "visio_drawings",
        "macros",
    ),
}


@dataclass(frozen=True, slots=True)
class WordRiskSourceEvidenceSpec:
    evidence_id: str
    layer: str
    source_path: str
    markers: tuple[str, ...]


def _evidence(
    evidence_id: str,
    layer: str,
    source_path: str,
    *markers: str,
) -> WordRiskSourceEvidenceSpec:
    return WordRiskSourceEvidenceSpec(
        evidence_id=evidence_id,
        layer=layer,
        source_path=source_path,
        markers=tuple(markers),
    )


PREFLIGHT_GLOBAL_EVIDENCE: tuple[WordRiskSourceEvidenceSpec, ...] = (
    _evidence(
        "object_preflight.pipeline",
        "runtime",
        "src/pipeline/runner.py",
        "_run_object_preflight",
        "_build_object_preflight_policy_snapshot",
    ),
    _evidence(
        "object_preflight.report",
        "report",
        "src/report_writer.py",
        "_extract_object_preflight",
        "_format_object_preflight_markdown",
    ),
    _evidence(
        "object_preflight.workbench",
        "workbench",
        "src/ui/adapters/workbench_execution_adapter.py",
        "object_preflight_issue_items",
        "_object_preflight_summary",
    ),
    _evidence(
        "object_preflight.tests",
        "test",
        "tests/test_object_preflight_semantics.py",
        "test_object_preflight_report_includes_policy_and_planning_evidence",
        "test_workbench_runner_payload_includes_object_preflight_evidence",
    ),
)

WORD_RISK_SOURCE_EVIDENCE: dict[str, tuple[WordRiskSourceEvidenceSpec, ...]] = {
    "paragraph_run": (
        _evidence(
            "paragraph_run.runtime",
            "runtime",
            "src/modules/basic/paragraph_style.py",
            "class ParagraphStyleModule",
            "_apply_style_to_paragraph",
        ),
        _evidence(
            "paragraph_run.tests",
            "test",
            "tests/test_body_style_semantics.py",
            "line_spacing_type",
            "apply_style_special_indent",
        ),
    ),
    "styles": (
        _evidence(
            "styles.runtime",
            "runtime",
            "src/modules/basic/paragraph_style.py",
            "_apply_font",
            "sync_spacing_ooxml",
        ),
        _evidence(
            "styles.ui_tests",
            "test",
            "tests/test_template_style_detail.py",
            "SpecialIndentInput(",
            "IndentInput(",
        ),
    ),
    "numbering": (
        _evidence(
            "numbering.runtime",
            "runtime",
            "src/modules/structure/heading_numbering.py",
            "class HeadingNumberingModule",
            "_normalize_restart_on",
        ),
        _evidence(
            "numbering.preservation_runtime",
            "runtime",
            "src/shared/engine/official_numbering_preservation.py",
            "numbering.xml",
            "inspect_official_numbering_preservation",
        ),
        _evidence(
            "numbering.report",
            "report",
            "src/report_writer.py",
            "_extract_official_numbering_preservation",
            "_format_official_numbering_preservation_markdown",
        ),
        _evidence(
            "numbering.tests",
            "test",
            "tests/test_heading_numbering_scheme_closure.py",
            "test_heading_numbering_apply_honors_start_at_and_child_restart",
            "restart_on",
        ),
    ),
    "table_grid": (
        _evidence(
            "table_grid.runtime",
            "runtime",
            "src/shared/engine/table_builder.py",
            "set_column_width",
            "merge_cells",
            "set_repeat_header_row",
        ),
        _evidence(
            "table_grid.tests",
            "test",
            "tests/test_table_format_semantics.py",
            "_grid_widths",
            "test_table_format_keep_layout_preserves_body_table_widths",
        ),
    ),
    "fixed_row_height": (
        _evidence(
            "fixed_row_height.config",
            "runtime",
            "src/config/fixed_layout.py",
            "FixedLayoutRowHeightPolicy",
            "row_height_pt",
        ),
        _evidence(
            "fixed_row_height.runtime",
            "runtime",
            "src/shared/engine/fixed_layout_tables.py",
            "w:trHeight",
            "apply_fixed_layout_row_height_policy",
        ),
        _evidence(
            "fixed_row_height.tests",
            "test",
            "tests/test_table_format_semantics.py",
            "test_fixed_layout_row_height_policy_writes_trheight_without_generic_table_config",
            "test_table_config_no_longer_exposes_legacy_row_height_setting",
        ),
    ),
    "content_controls": (
        _evidence(
            "content_controls.runtime",
            "runtime",
            "src/shared/engine/fixed_layout_text.py",
            "replace_fixed_layout_mapped_fields",
            "content_controls",
        ),
        _evidence(
            "content_controls.preflight",
            "object_preflight",
            "src/shared/engine/object_preflight.py",
            "content_controls",
            'b"<w:sdt"',
        ),
        _evidence(
            "content_controls.tests",
            "test",
            "tests/test_object_preflight_semantics.py",
            "test_object_preflight_detects_content_controls",
            "content_controls",
        ),
    ),
    "textbox_shape": (
        _evidence(
            "textbox_shape.runtime",
            "runtime",
            "src/shared/engine/fixed_layout_text.py",
            "textboxes",
            "iter_fixed_layout_text_blocks",
        ),
        _evidence(
            "textbox_shape.preflight",
            "object_preflight",
            "src/shared/engine/object_preflight.py",
            "textboxes",
            "w:txbxContent",
        ),
        _evidence(
            "textbox_shape.tests",
            "test",
            "tests/test_fixed_layout_text_runtime.py",
            '["textboxes", "content_controls"]',
            "replace_fixed_layout_mapped_fields",
        ),
    ),
    "drawing_media_rels": (
        _evidence(
            "drawing_media_rels.runtime",
            "runtime",
            "src/modules/insert/image_insertion.py",
            "class ImageInsertionModule",
            "_resolve_image_paragraph",
        ),
        _evidence(
            "drawing_media_rels.preflight",
            "object_preflight",
            "src/shared/engine/object_preflight.py",
            "visio_drawings",
            "_inspect_relationships",
        ),
        _evidence(
            "drawing_media_rels.tests",
            "test",
            "tests/test_material_execution_context.py",
            "paragraph_has_image",
            "image_rules",
        ),
    ),
    "fields": (
        _evidence(
            "fields.runtime",
            "runtime",
            "src/shared/engine/field_builder.py",
            "build_complex_field",
            "iter_field_instructions",
        ),
        _evidence(
            "fields.preflight",
            "object_preflight",
            "src/shared/engine/object_preflight.py",
            "fields",
            "w:fldSimple",
        ),
        _evidence(
            "fields.tests",
            "test",
            "tests/test_toc_semantics.py",
            'TOC \\\\o "1-4"',
            "iter_field_instructions",
        ),
    ),
    "headers_footers": (
        _evidence(
            "headers_footers.runtime",
            "runtime",
            "src/modules/basic/header_footer.py",
            "class HeaderFooterModule",
            "_set_page_number",
        ),
        _evidence(
            "headers_footers.tests",
            "test",
            "tests/test_header_footer_semantics.py",
            "test_header_footer_applies_first_and_even_page_variants",
            "PAGE",
        ),
        _evidence(
            "headers_footers.planner_tests",
            "test",
            "tests/test_page_number_planner_semantics.py",
            "test_section_format_and_header_footer_share_phase_plan_without_restarting_same_body_phase",
            "HeaderFooterModule",
        ),
    ),
    "comments_revisions": (
        _evidence(
            "comments_revisions.preflight",
            "object_preflight",
            "src/shared/engine/object_preflight.py",
            "tracked_changes",
            "comments",
        ),
        _evidence(
            "comments_revisions.count_runtime",
            "runtime",
            "src/shared/engine/count_engine.py",
            "comments.xml",
            "_tracked_change_texts",
        ),
        _evidence(
            "comments_revisions.tests",
            "test",
            "tests/test_object_preflight_semantics.py",
            "tracked_changes",
            "comments",
        ),
    ),
    "footnotes_endnotes": (
        _evidence(
            "footnotes_endnotes.runtime",
            "runtime",
            "src/shared/engine/count_engine.py",
            "footnotes.xml",
            "endnotes.xml",
        ),
        _evidence(
            "footnotes_endnotes.tests",
            "test",
            "tests/test_count_engine_semantics.py",
            "word/footnotes.xml",
            "word/endnotes.xml",
        ),
    ),
    "hidden_text": (
        _evidence(
            "hidden_text.preflight",
            "object_preflight",
            "src/shared/engine/object_preflight.py",
            "hidden_text",
            "w:vanish",
        ),
        _evidence(
            "hidden_text.count_runtime",
            "runtime",
            "src/shared/engine/count_engine.py",
            "_hidden_texts",
            "hidden_text",
        ),
        _evidence(
            "hidden_text.tests",
            "test",
            "tests/test_count_engine_semantics.py",
            "hidden_text_count",
            "tracked_changes_count",
        ),
    ),
    "ole_embedded_vba": (
        _evidence(
            "ole_embedded_vba.preflight",
            "object_preflight",
            "src/shared/engine/object_preflight.py",
            "ole_objects",
            "embedded_workbooks",
            "macros",
        ),
        _evidence(
            "ole_embedded_vba.tests",
            "test",
            "tests/test_scene_sample_fixture_regression.py",
            "technical_long_docs_skip_objects",
            "import_ai_boundary_blocking_macro",
        ),
    ),
    "package_relationships": (
        _evidence(
            "package_relationships.preflight",
            "object_preflight",
            "src/shared/engine/object_preflight.py",
            "_inspect_relationships",
            "embedded_packages",
        ),
        _evidence(
            "package_relationships.tests",
            "test",
            "tests/test_object_preflight_semantics.py",
            "relationship",
            "embedded_packages",
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class SceneWordRiskClosureIssue:
    surface_id: str
    kind: str
    message: str

    def to_payload(self) -> dict[str, object]:
        return {
            "surface_id": self.surface_id,
            "kind": self.kind,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class SceneWordRiskSourceEvidence:
    evidence_id: str
    layer: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "layer": self.layer,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneWordRiskClosureRow:
    surface_id: str
    label: str
    touchpoints: tuple[str, ...]
    required_strategy: str
    pack_ids: tuple[str, ...]
    sample_surface_ids: tuple[str, ...]
    sample_fixture_ids: tuple[str, ...]
    preflight_targets: tuple[str, ...]
    source_evidence: tuple[SceneWordRiskSourceEvidence, ...]
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    @property
    def source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status == "ready")

    @property
    def evidence_layer_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted({item.layer for item in self.source_evidence if item.status == "ready"})
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "surface_id": self.surface_id,
            "label": self.label,
            "touchpoints": list(self.touchpoints),
            "required_strategy": self.required_strategy,
            "pack_ids": list(self.pack_ids),
            "sample_surface_ids": list(self.sample_surface_ids),
            "sample_fixture_ids": list(self.sample_fixture_ids),
            "preflight_targets": list(self.preflight_targets),
            "source_evidence_count": self.source_evidence_count,
            "evidence_layer_ids": list(self.evidence_layer_ids),
            "source_evidence": [item.to_payload() for item in self.source_evidence],
            "issue_ids": list(self.issue_ids),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneWordRiskClosureAuditReport:
    rows: tuple[SceneWordRiskClosureRow, ...]
    issues: tuple[SceneWordRiskClosureIssue, ...]

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def surface_count(self) -> int:
        return len(self.rows)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def preflight_surface_count(self) -> int:
        return sum(1 for row in self.rows if row.preflight_targets)

    @property
    def sample_fixture_link_count(self) -> int:
        return sum(len(row.sample_fixture_ids) for row in self.rows)

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "surface_count": self.surface_count,
            "issue_count": self.issue_count,
            "preflight_surface_count": self.preflight_surface_count,
            "sample_fixture_link_count": self.sample_fixture_link_count,
            "required_surface_ids": list(N2_157D_WORD_RISK_SURFACE_IDS),
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
        }


@lru_cache(maxsize=32)
def build_scene_word_risk_closure_audit_report(
    *,
    surface_id: str = "",
    project_root: Path | None = None,
) -> SceneWordRiskClosureAuditReport:
    root = project_root or Path(__file__).resolve().parents[2]
    requested_id = str(surface_id or "").strip()
    surfaces = (
        tuple(
            surface
            for surface in list_word_risk_surfaces()
            if surface.surface_id == requested_id
        )
        if requested_id
        else list_word_risk_surfaces()
    )
    if requested_id and not surfaces:
        return SceneWordRiskClosureAuditReport(
            rows=(),
            issues=(
                SceneWordRiskClosureIssue(
                    surface_id=requested_id,
                    kind="unknown_surface",
                    message=f"Unknown Word risk surface: {requested_id}",
                ),
            ),
        )

    packs = list_scene_coverage_packs()
    fixtures = list_scene_sample_fixtures()
    rows: list[SceneWordRiskClosureRow] = []
    issues: list[SceneWordRiskClosureIssue] = []
    supported_preflight_targets = set(OBJECT_PREFLIGHT_SCAN_TARGETS)

    for surface in surfaces:
        pack_ids = tuple(
            pack.pack_id
            for pack in packs
            if surface.surface_id in pack.word_risk_surface_ids
        )
        sample_surface_ids = WORD_RISK_SAMPLE_SURFACE_MAP.get(surface.surface_id, ())
        sample_fixture_ids = tuple(
            spec.fixture_id
            for spec in fixtures
            if any(sample in spec.docx_surfaces for sample in sample_surface_ids)
        )
        preflight_targets = WORD_RISK_PREFLIGHT_TARGET_MAP.get(surface.surface_id, ())
        source_evidence = _resolve_source_evidence(surface.surface_id, root)
        row_issues = _row_issues(
            surface_id=surface.surface_id,
            touchpoints=surface.touchpoints,
            required_strategy=surface.required_strategy,
            pack_ids=pack_ids,
            sample_surface_ids=sample_surface_ids,
            sample_fixture_ids=sample_fixture_ids,
            preflight_targets=preflight_targets,
            supported_preflight_targets=supported_preflight_targets,
            source_evidence=source_evidence,
        )
        rows.append(
            SceneWordRiskClosureRow(
                surface_id=surface.surface_id,
                label=surface.label,
                touchpoints=surface.touchpoints,
                required_strategy=surface.required_strategy,
                pack_ids=pack_ids,
                sample_surface_ids=sample_surface_ids,
                sample_fixture_ids=sample_fixture_ids,
                preflight_targets=preflight_targets,
                source_evidence=source_evidence,
                issue_ids=tuple(issue.kind for issue in row_issues),
            )
        )
        issues.extend(row_issues)

    return SceneWordRiskClosureAuditReport(rows=tuple(rows), issues=tuple(issues))


def audit_scene_word_risk_closure_report(
    report: SceneWordRiskClosureAuditReport | None = None,
) -> tuple[SceneWordRiskClosureIssue, ...]:
    report = report or build_scene_word_risk_closure_audit_report()
    return report.issues


@lru_cache(maxsize=64)
def _resolve_source_evidence(
    surface_id: str,
    root: Path,
) -> tuple[SceneWordRiskSourceEvidence, ...]:
    specs = list(WORD_RISK_SOURCE_EVIDENCE.get(surface_id, ()))
    if surface_id in WORD_RISK_PREFLIGHT_TARGET_MAP:
        specs.extend(PREFLIGHT_GLOBAL_EVIDENCE)
    evidence: list[SceneWordRiskSourceEvidence] = []
    for spec in specs:
        path = root / spec.source_path
        content = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing_markers = tuple(marker for marker in spec.markers if marker not in content)
        if not path.exists():
            missing_markers = ("<missing file>", *missing_markers)
        evidence.append(
            SceneWordRiskSourceEvidence(
                evidence_id=spec.evidence_id,
                layer=spec.layer,
                source_path=spec.source_path,
                markers=spec.markers,
                missing_markers=missing_markers,
            )
        )
    return tuple(evidence)


def _row_issues(
    *,
    surface_id: str,
    touchpoints: tuple[str, ...],
    required_strategy: str,
    pack_ids: tuple[str, ...],
    sample_surface_ids: tuple[str, ...],
    sample_fixture_ids: tuple[str, ...],
    preflight_targets: tuple[str, ...],
    supported_preflight_targets: set[str],
    source_evidence: tuple[SceneWordRiskSourceEvidence, ...],
) -> tuple[SceneWordRiskClosureIssue, ...]:
    issues: list[SceneWordRiskClosureIssue] = []
    issue_ids: list[str] = []
    ready_layers = {
        item.layer for item in source_evidence if item.status == "ready"
    }

    def append(kind: str, message: str) -> None:
        issue_ids.append(kind)
        issues.append(
            SceneWordRiskClosureIssue(
                surface_id=surface_id,
                kind=kind,
                message=message,
            )
        )

    if not touchpoints:
        append("missing_touchpoints", "Word risk surface must list OOXML touchpoints.")
    if not str(required_strategy or "").strip():
        append("missing_required_strategy", "Word risk surface must declare a strategy.")
    if not pack_ids:
        append("missing_scene_pack", "Word risk surface is not referenced by any scene pack.")
    if sample_surface_ids and not sample_fixture_ids:
        append(
            "missing_sample_fixture",
            "Mapped DOCX sample surfaces have no sample fixture evidence.",
        )
    if not source_evidence:
        append("missing_source_evidence", "No runtime or test evidence is declared.")
    for item in source_evidence:
        if item.status != "ready":
            append(
                f"missing_source_marker.{item.evidence_id}",
                f"{item.source_path} is missing markers: "
                + ", ".join(item.missing_markers),
            )
    if "runtime" not in ready_layers:
        append("missing_runtime_layer", "No ready runtime evidence is available.")
    if "test" not in ready_layers:
        append("missing_test_layer", "No ready test evidence is available.")

    unsupported_targets = tuple(
        target for target in preflight_targets if target not in supported_preflight_targets
    )
    if unsupported_targets:
        append(
            "unsupported_preflight_targets",
            "Preflight targets are not supported: " + ", ".join(unsupported_targets),
        )
    if preflight_targets:
        for layer in ("object_preflight", "report", "workbench"):
            if layer not in ready_layers:
                append(
                    f"missing_preflight_{layer}_layer",
                    f"Preflight surface must expose ready {layer} evidence.",
                )
    return tuple(issues)


__all__ = [
    "N2_157D_WORD_RISK_SURFACE_IDS",
    "SceneWordRiskClosureAuditReport",
    "SceneWordRiskClosureIssue",
    "SceneWordRiskClosureRow",
    "SceneWordRiskSourceEvidence",
    "audit_scene_word_risk_closure_report",
    "build_scene_word_risk_closure_audit_report",
]
