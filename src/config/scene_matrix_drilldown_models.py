"""Payload models for the scene matrix drilldown."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.scene_matrix_drilldown_sources import (
    REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS,
    SCENE_MATRIX_DRILLDOWN_SOURCE_ID,
)


@dataclass(frozen=True, slots=True)
class SceneMatrixDrilldownIssue:
    scope_type: str
    scope_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneMatrixDrilldownSourceEvidence:
    source_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]
    status: str

    def to_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneMatrixDrilldownRow:
    row_id: str
    label: str
    status: str
    source_id: str
    detail: str
    pack_ids: tuple[str, ...] = ()
    family_ids: tuple[str, ...] = ()
    request_cell_ids: tuple[str, ...] = ()
    fixture_ids: tuple[str, ...] = ()
    count_profile_ids: tuple[str, ...] = ()
    material_schema_ids: tuple[str, ...] = ()
    delivery_preset_ids: tuple[str, ...] = ()
    input_source_ids: tuple[str, ...] = ()
    render_source_ids: tuple[str, ...] = ()
    object_preflight_target_ids: tuple[str, ...] = ()
    action_behavior_ids: tuple[str, ...] = ()
    capability_ids: tuple[str, ...] = ()
    maturity_gap_domain_ids: tuple[str, ...] = ()
    word_risk_surface_ids: tuple[str, ...] = ()
    plugin_gate_ids: tuple[str, ...] = ()
    risk_domain_ids: tuple[str, ...] = ()
    issue_ids: tuple[str, ...] = ()

    @property
    def search_text(self) -> str:
        return " ".join(
            (
                self.row_id,
                self.label,
                self.status,
                self.source_id,
                self.detail,
                *self.pack_ids,
                *self.family_ids,
                *self.request_cell_ids,
                *self.fixture_ids,
                *self.count_profile_ids,
                *self.material_schema_ids,
                *self.delivery_preset_ids,
                *self.input_source_ids,
                *self.render_source_ids,
                *self.object_preflight_target_ids,
                *self.action_behavior_ids,
                *self.capability_ids,
                *self.maturity_gap_domain_ids,
                *self.word_risk_surface_ids,
                *self.plugin_gate_ids,
                *self.risk_domain_ids,
                *self.issue_ids,
            )
        ).lower()

    def to_payload(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "label": self.label,
            "status": self.status,
            "source_id": self.source_id,
            "detail": self.detail,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "request_cell_ids": list(self.request_cell_ids),
            "fixture_ids": list(self.fixture_ids),
            "count_profile_ids": list(self.count_profile_ids),
            "material_schema_ids": list(self.material_schema_ids),
            "delivery_preset_ids": list(self.delivery_preset_ids),
            "input_source_ids": list(self.input_source_ids),
            "render_source_ids": list(self.render_source_ids),
            "object_preflight_target_ids": list(self.object_preflight_target_ids),
            "action_behavior_ids": list(self.action_behavior_ids),
            "capability_ids": list(self.capability_ids),
            "maturity_gap_domain_ids": list(self.maturity_gap_domain_ids),
            "word_risk_surface_ids": list(self.word_risk_surface_ids),
            "plugin_gate_ids": list(self.plugin_gate_ids),
            "risk_domain_ids": list(self.risk_domain_ids),
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneMatrixDrilldownItem:
    drilldown_id: str
    label: str
    source_id: str
    lens_ids: tuple[str, ...]
    route_hint: str
    detail: str
    rows: tuple[SceneMatrixDrilldownRow, ...]
    visible_rows: tuple[SceneMatrixDrilldownRow, ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def visible_count(self) -> int:
        return len(self.visible_rows)

    @property
    def issue_count(self) -> int:
        return sum(len(row.issue_ids) for row in self.rows)

    @property
    def status(self) -> str:
        return "ready" if self.rows and self.issue_count == 0 else "needs_attention"

    def to_payload(self) -> dict[str, object]:
        return {
            "drilldown_id": self.drilldown_id,
            "label": self.label,
            "source_id": self.source_id,
            "status": self.status,
            "row_count": self.row_count,
            "visible_count": self.visible_count,
            "issue_count": self.issue_count,
            "lens_ids": list(self.lens_ids),
            "route_hint": self.route_hint,
            "detail": self.detail,
            "rows": [row.to_payload() for row in self.visible_rows],
        }


@dataclass(frozen=True, slots=True)
class SceneMatrixDrilldownReport:
    items: tuple[SceneMatrixDrilldownItem, ...]
    issues: tuple[SceneMatrixDrilldownIssue, ...]
    source_evidence: tuple[SceneMatrixDrilldownSourceEvidence, ...]
    pack_filter: str = ""
    family_filter: str = ""
    source_filter: str = ""
    query: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def ready_count(self) -> int:
        return sum(1 for item in self.items if item.status == "ready")

    @property
    def row_count(self) -> int:
        return sum(item.row_count for item in self.items)

    @property
    def visible_row_count(self) -> int:
        return sum(item.visible_count for item in self.items)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def source_evidence_count(self) -> int:
        return len(self.source_evidence)

    @property
    def ready_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status == "ready")

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "pack_filter": self.pack_filter,
            "family_filter": self.family_filter,
            "source_filter": self.source_filter,
            "query": self.query,
            "source_id": SCENE_MATRIX_DRILLDOWN_SOURCE_ID,
            "required_drilldown_ids": list(REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS),
            "counts": {
                "item_count": self.item_count,
                "ready_count": self.ready_count,
                "row_count": self.row_count,
                "visible_row_count": self.visible_row_count,
                "issue_count": self.issue_count,
                "source_evidence_count": self.source_evidence_count,
                "ready_source_evidence_count": self.ready_source_evidence_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
            },
            "items": [item.to_payload() for item in self.items],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


__all__ = [
    "SceneMatrixDrilldownIssue",
    "SceneMatrixDrilldownItem",
    "SceneMatrixDrilldownReport",
    "SceneMatrixDrilldownRow",
    "SceneMatrixDrilldownSourceEvidence",
]
