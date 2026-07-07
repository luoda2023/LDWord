"""Product maturity upgrade audit for the high-level scene matrix.

N2.169 keeps product readiness from stopping at a color label.  The audit
turns each pack/family readiness row into an upgrade path: current level,
next target, L5 blockers, gap domains, and the pack/family links a UI can
filter on.  It intentionally does not promote any subject to Green/L5.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.config.scene_coverage_manifest import (
    SCENE_COVERAGE_PACK_MAP,
    coverage_packs_for_family,
)
from src.config.scene_family_registry import PLANNED_SCENE_FAMILY_MAP
from src.config.scene_product_readiness import (
    PRODUCT_READINESS_LEVELS,
    SceneProductReadinessSpec,
    audit_scene_product_readiness,
    list_scene_product_readiness_specs,
)


SCENE_PRODUCT_MATURITY_UPGRADE_AUDIT_SOURCE_ID = (
    "scene_product_maturity_upgrade_audit"
)

SCENE_PRODUCT_MATURITY_UPGRADE_SOURCE_MARKERS: tuple[
    tuple[str, str, tuple[str, ...]],
    ...
] = (
    (
        "scene_product_readiness",
        "src/config/scene_product_readiness.py",
        (
            "SCENE_PRODUCT_READINESS_SPECS",
            "remaining_product_gaps",
            "static_closed_but_not_green_specs",
        ),
    ),
    (
        "scene_matrix_dashboard",
        "src/config/scene_matrix_dashboard.py",
        (
            "scene_product_maturity_upgrade_audit",
            "maturity_upgrade_l5_blocked_subject_count",
        ),
    ),
    (
        "scene_summary_projection",
        "src/ui/panels/scene_summary_projection.py",
        (
            "scene_matrix_readiness",
            "maturity_upgrade_l5_blocked_subject_count",
        ),
    ),
    (
        "report_writer_product_readiness",
        "src/report_writer.py",
        ("scene_product_readiness", "static_closed_but_not_green_count"),
    ),
    (
        "release_gate_product_readiness",
        "scripts/verify_scene_matrix_release_gate.py",
        (
            "scene_product_maturity_upgrade_audit",
            "scene_product_maturity_upgrade_gap_count",
            "gap_domains=",
        ),
    ),
    (
        "n2_393g_plan",
        "docs/audits/高层场景能力矩阵N2_393gGapDomain分类读数归因补充_2026-06-25.md",
        ("N2.393g", "gap_domains=3/3 classified", "gap_domain_counts"),
    ),
)

PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS: tuple[str, ...] = (
    "ui_control",
    "runtime_execution",
    "report_artifact",
    "fixture_sample",
    "rule_governance",
    "boundary_gate",
    "repair_confirmation",
    "structured_source",
)

PRODUCT_MATURITY_UPGRADE_DOMAIN_LABELS: dict[str, str] = {
    "ui_control": "UI controls, previews, and drilldowns",
    "runtime_execution": "Execution, conversion, and fallback behavior",
    "report_artifact": "Reports, output packages, and delivery artifacts",
    "fixture_sample": "Real request and business fixture depth",
    "rule_governance": "Profile, rule-source, and version governance",
    "boundary_gate": "Plugin, manual, and professional boundary gates",
    "repair_confirmation": "Repair, confirmation, and disambiguation routes",
    "structured_source": "Structured input, schema, asset, and metadata sources",
}

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ui_control": (
        "ui",
        "browser",
        "preview",
        "previews",
        "editing",
        "controls",
        "control",
        "visibility",
        "visible",
        "termbase",
        "banner",
        "replacement",
        "asset consistency",
    ),
    "runtime_execution": (
        "runtime",
        "pre-execution",
        "conversion",
        "integration",
        "merge",
        "reuse path",
        "handoff routing",
        "fallback",
        "isolation",
        "layout",
        "ocr",
        "pdf",
        "latex",
        "classifier",
        "fixed row height",
    ),
    "report_artifact": (
        "report",
        "artifact",
        "artifacts",
        "package",
        "archive",
        "delivery",
        "answer-sheet",
        "answer sheet",
        "preset",
        "manifest",
        "output",
        "submission",
        "final",
        "review",
        "inventory",
    ),
    "fixture_sample": (
        "fixture",
        "fixtures",
        "sample",
        "real business",
        "depth",
        "request-cell",
    ),
    "rule_governance": (
        "governance",
        "rule source",
        "source governance",
        "profile updates",
        "source updates",
        "metadata",
        "profile editing",
        "school profile",
        "external rule",
        "regulated rule",
    ),
    "boundary_gate": (
        "boundary",
        "plugin",
        "manual",
        "legal-boundary",
        "handoff",
        "professional",
        "assurance",
        "claim-quality",
        "finance",
    ),
    "repair_confirmation": (
        "repair",
        "confirmation",
        "confirm",
        "residual",
        "checks",
        "disambiguation",
        "consistency",
        "classifier confirmation",
    ),
    "structured_source": (
        "schema",
        "asset",
        "assets",
        "field",
        "spreadsheet",
        "table",
        "mapping",
        "metadata",
        "inventory",
        "limits",
        "records",
        "termbase",
        "question",
    ),
}

_EXPLICIT_GAP_DOMAINS: dict[str, tuple[str, ...]] = {
    "question asset replacement ui": ("ui_control",),
    "asset replacement ui": ("ui_control",),
    "advanced question asset library ui": ("ui_control",),
    "advanced asset library ui": ("ui_control",),
    "advanced question asset library editing ui": ("ui_control",),
    "advanced asset library editing ui": ("ui_control",),
    "advanced question asset library governance ui": ("ui_control", "rule_governance"),
    "advanced asset library governance ui": ("ui_control", "rule_governance"),
    "advanced question asset library bulk version governance ui": (
        "ui_control",
        "rule_governance",
    ),
    "advanced asset library bulk version governance ui": (
        "ui_control",
        "rule_governance",
    ),
    "advanced question asset library version governance ui": (
        "ui_control",
        "rule_governance",
    ),
    "advanced asset library version governance ui": (
        "ui_control",
        "rule_governance",
    ),
}

_NEXT_UPGRADE_GOAL: dict[str, str] = {
    "gray_l1": "yellow_l3",
    "blue_boundary": "boundary_guarded_orange_l4",
    "yellow_l3": "orange_l4",
    "orange_l4": "green_l5",
    "green_l5": "maintain_green_l5",
}


@dataclass(frozen=True, slots=True)
class SceneProductMaturityUpgradeIssue:
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
class SceneProductMaturityUpgradeSourceEvidence:
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
class SceneProductMaturityUpgradeRow:
    subject_type: str
    subject_id: str
    label: str
    status: str
    current_readiness_level: str
    static_closure_level: str
    next_upgrade_goal: str
    target_readiness_level: str
    pack_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    evidence_surfaces: tuple[str, ...]
    evidence_domain_ids: tuple[str, ...]
    remaining_product_gaps: tuple[str, ...]
    gap_domain_ids: tuple[str, ...]
    l5_blocker_count: int
    rationale: str
    issue_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    @property
    def is_green(self) -> bool:
        return self.current_readiness_level == "green_l5"

    @property
    def is_boundary(self) -> bool:
        return self.current_readiness_level == "blue_boundary"

    def to_payload(self) -> dict[str, object]:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "label": self.label,
            "status": self.status,
            "current_readiness_level": self.current_readiness_level,
            "static_closure_level": self.static_closure_level,
            "next_upgrade_goal": self.next_upgrade_goal,
            "target_readiness_level": self.target_readiness_level,
            "pack_ids": list(self.pack_ids),
            "family_ids": list(self.family_ids),
            "evidence_surfaces": list(self.evidence_surfaces),
            "evidence_domain_ids": list(self.evidence_domain_ids),
            "remaining_product_gaps": list(self.remaining_product_gaps),
            "gap_domain_ids": list(self.gap_domain_ids),
            "l5_blocker_count": self.l5_blocker_count,
            "rationale": self.rationale,
            "issue_ids": list(self.issue_ids),
            "warning_ids": list(self.warning_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneProductMaturityUpgradeAuditReport:
    rows: tuple[SceneProductMaturityUpgradeRow, ...]
    issues: tuple[SceneProductMaturityUpgradeIssue, ...]
    warnings: tuple[SceneProductMaturityUpgradeIssue, ...]
    source_evidence: tuple[SceneProductMaturityUpgradeSourceEvidence, ...]
    subject_type_filter: str = ""
    readiness_filter: str = ""
    domain_filter: str = ""
    query: str = ""
    total_subject_count: int = 0

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def subject_count(self) -> int:
        return len(self.rows)

    @property
    def pack_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.subject_type == "pack")

    @property
    def family_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.subject_type == "family")

    @property
    def green_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.is_green)

    @property
    def l5_blocked_subject_count(self) -> int:
        return sum(1 for row in self.rows if not row.is_green)

    @property
    def l3_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.current_readiness_level == "yellow_l3")

    @property
    def l4_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.current_readiness_level == "orange_l4")

    @property
    def boundary_subject_count(self) -> int:
        return sum(1 for row in self.rows if row.is_boundary)

    @property
    def static_closed_not_green_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.static_closure_level == "closed" and not row.is_green
        )

    @property
    def gap_count(self) -> int:
        return sum(len(row.remaining_product_gaps) for row in self.rows)

    @property
    def gap_domain_count(self) -> int:
        return len(
            _unique_values(
                domain_id
                for row in self.rows
                for domain_id in row.gap_domain_ids
            )
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.status != "ready")

    @property
    def gap_domain_counts(self) -> tuple[tuple[str, int], ...]:
        counter: Counter[str] = Counter()
        for row in self.rows:
            counter.update(row.gap_domain_ids)
        return tuple(
            (domain_id, counter[domain_id])
            for domain_id in PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS
            if counter[domain_id]
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_id": SCENE_PRODUCT_MATURITY_UPGRADE_AUDIT_SOURCE_ID,
            "subject_type_filter": self.subject_type_filter,
            "readiness_filter": self.readiness_filter,
            "domain_filter": self.domain_filter,
            "query": self.query,
            "domain_labels": dict(PRODUCT_MATURITY_UPGRADE_DOMAIN_LABELS),
            "counts": {
                "subject_count": self.subject_count,
                "total_subject_count": self.total_subject_count,
                "pack_subject_count": self.pack_subject_count,
                "family_subject_count": self.family_subject_count,
                "green_subject_count": self.green_subject_count,
                "l5_blocked_subject_count": self.l5_blocked_subject_count,
                "l3_subject_count": self.l3_subject_count,
                "l4_subject_count": self.l4_subject_count,
                "boundary_subject_count": self.boundary_subject_count,
                "static_closed_not_green_count": (
                    self.static_closed_not_green_count
                ),
                "gap_count": self.gap_count,
                "gap_domain_count": self.gap_domain_count,
                "issue_count": self.issue_count,
                "warning_count": self.warning_count,
                "missing_source_evidence_count": (
                    self.missing_source_evidence_count
                ),
                "gap_domain_counts": [
                    {"domain_id": domain_id, "count": count}
                    for domain_id, count in self.gap_domain_counts
                ],
            },
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "warnings": [warning.to_payload() for warning in self.warnings],
            "source_evidence": [
                evidence.to_payload() for evidence in self.source_evidence
            ],
        }


def build_scene_product_maturity_upgrade_audit_report(
    *,
    subject_type: str = "",
    readiness_level: str = "",
    domain_id: str = "",
    query: str = "",
    project_root: Path | str | None = None,
) -> SceneProductMaturityUpgradeAuditReport:
    normalized_subject_type = str(subject_type or "").strip()
    normalized_readiness = str(readiness_level or "").strip()
    normalized_domain = str(domain_id or "").strip()
    normalized_query = str(query or "").strip().lower()

    specs = list_scene_product_readiness_specs()
    rows = tuple(_row_for_spec(spec) for spec in specs)
    rows = tuple(
        row
        for row in rows
        if _matches_filters(
            row,
            subject_type=normalized_subject_type,
            readiness_level=normalized_readiness,
            domain_id=normalized_domain,
            query=normalized_query,
        )
    )
    source_evidence = _source_evidence(project_root)
    issues, warnings = audit_scene_product_maturity_upgrade_report(
        SceneProductMaturityUpgradeAuditReport(
            rows=rows,
            issues=(),
            warnings=(),
            source_evidence=source_evidence,
            subject_type_filter=normalized_subject_type,
            readiness_filter=normalized_readiness,
            domain_filter=normalized_domain,
            query=str(query or "").strip(),
            total_subject_count=len(specs),
        )
    )
    return SceneProductMaturityUpgradeAuditReport(
        rows=rows,
        issues=issues,
        warnings=warnings,
        source_evidence=source_evidence,
        subject_type_filter=normalized_subject_type,
        readiness_filter=normalized_readiness,
        domain_filter=normalized_domain,
        query=str(query or "").strip(),
        total_subject_count=len(specs),
    )


def audit_scene_product_maturity_upgrade_report(
    report: SceneProductMaturityUpgradeAuditReport,
) -> tuple[
    tuple[SceneProductMaturityUpgradeIssue, ...],
    tuple[SceneProductMaturityUpgradeIssue, ...],
]:
    issues: list[SceneProductMaturityUpgradeIssue] = []
    warnings: list[SceneProductMaturityUpgradeIssue] = []

    for readiness_issue in audit_scene_product_readiness():
        scope_id = str(getattr(readiness_issue, "subject_id", "") or "readiness")
        kind = str(getattr(readiness_issue, "issue", "") or "readiness_issue")
        issues.append(
            SceneProductMaturityUpgradeIssue(
                "product_readiness",
                scope_id,
                kind,
                f"Underlying product readiness audit is not clean: {kind}.",
            )
        )

    if not report.rows:
        issues.append(
            SceneProductMaturityUpgradeIssue(
                "maturity_upgrade",
                "rows",
                "empty_upgrade_rows",
                "Product maturity upgrade audit must expose at least one subject row.",
            )
        )

    for row in report.rows:
        for issue_id in row.issue_ids:
            issues.append(
                SceneProductMaturityUpgradeIssue(
                    row.subject_type,
                    row.subject_id,
                    issue_id,
                    f"Maturity upgrade row has unresolved issue: {issue_id}.",
                )
            )
        if not row.is_green and not row.remaining_product_gaps:
            issues.append(
                SceneProductMaturityUpgradeIssue(
                    row.subject_type,
                    row.subject_id,
                    "non_green_without_upgrade_gaps",
                    "Non-Green maturity rows must list remaining product gaps.",
                )
            )
        if row.remaining_product_gaps and not row.gap_domain_ids:
            issues.append(
                SceneProductMaturityUpgradeIssue(
                    row.subject_type,
                    row.subject_id,
                    "unclassified_upgrade_gap",
                    "Remaining product gaps must be mapped to upgrade domains.",
                )
            )
        if row.is_boundary and "boundary_gate" not in {
            *row.gap_domain_ids,
            *row.evidence_domain_ids,
        }:
            issues.append(
                SceneProductMaturityUpgradeIssue(
                    row.subject_type,
                    row.subject_id,
                    "boundary_without_boundary_domain",
                    "Boundary maturity rows must expose a plugin/manual/professional domain.",
                )
            )
        for warning_id in row.warning_ids:
            warnings.append(
                SceneProductMaturityUpgradeIssue(
                    row.subject_type,
                    row.subject_id,
                    warning_id,
                    f"Maturity upgrade row has warning: {warning_id}.",
                    severity="warning",
                )
            )

    for evidence in report.source_evidence:
        if evidence.status != "ready":
            issues.append(
                SceneProductMaturityUpgradeIssue(
                    "source_evidence",
                    evidence.source_id,
                    "missing_source_evidence",
                    f"Missing source markers: {', '.join(evidence.missing_markers)}",
                )
            )
    return tuple(issues), tuple(warnings)


def _row_for_spec(
    spec: SceneProductReadinessSpec,
) -> SceneProductMaturityUpgradeRow:
    remaining_gaps = tuple(spec.remaining_product_gaps)
    gap_domains = _domains_for_texts(remaining_gaps)
    evidence_domains = _domains_for_texts(spec.evidence_surfaces)
    return SceneProductMaturityUpgradeRow(
        subject_type=spec.subject_type,
        subject_id=spec.subject_id,
        label=_subject_label(spec),
        status=_row_status(spec),
        current_readiness_level=spec.product_readiness_level,
        static_closure_level=spec.static_closure_level,
        next_upgrade_goal=_NEXT_UPGRADE_GOAL.get(
            spec.product_readiness_level,
            "define_next_upgrade_goal",
        ),
        target_readiness_level="green_l5",
        pack_ids=_pack_ids_for_spec(spec),
        family_ids=_family_ids_for_spec(spec),
        evidence_surfaces=tuple(spec.evidence_surfaces),
        evidence_domain_ids=evidence_domains,
        remaining_product_gaps=remaining_gaps,
        gap_domain_ids=gap_domains,
        l5_blocker_count=0 if spec.is_green else len(remaining_gaps),
        rationale=spec.rationale,
        issue_ids=_row_issue_ids(spec, gap_domains),
        warning_ids=(),
    )


def _row_status(spec: SceneProductReadinessSpec) -> str:
    if spec.product_readiness_level == "green_l5":
        return "green_l5"
    if spec.product_readiness_level == "blue_boundary":
        return "boundary_guarded"
    if spec.product_readiness_level == "orange_l4":
        return "l5_blocked"
    if spec.product_readiness_level == "yellow_l3":
        return "needs_l4_first"
    return "needs_readiness_definition"


def _row_issue_ids(
    spec: SceneProductReadinessSpec,
    gap_domain_ids: tuple[str, ...],
) -> tuple[str, ...]:
    issue_ids: list[str] = []
    if spec.product_readiness_level not in PRODUCT_READINESS_LEVELS:
        issue_ids.append("invalid_readiness_level")
    if spec.product_readiness_level != "green_l5" and not spec.remaining_product_gaps:
        issue_ids.append("missing_l5_upgrade_gap")
    if spec.remaining_product_gaps and not gap_domain_ids:
        issue_ids.append("unclassified_l5_upgrade_gap")
    return tuple(issue_ids)


def _subject_label(spec: SceneProductReadinessSpec) -> str:
    if spec.subject_type == "pack":
        pack = SCENE_COVERAGE_PACK_MAP.get(spec.subject_id)
        return pack.label if pack is not None else spec.subject_id
    family = PLANNED_SCENE_FAMILY_MAP.get(spec.subject_id)
    return family.name if family is not None else spec.subject_id


def _pack_ids_for_spec(spec: SceneProductReadinessSpec) -> tuple[str, ...]:
    if spec.subject_type == "pack":
        return (spec.subject_id,)
    return tuple(pack.pack_id for pack in coverage_packs_for_family(spec.subject_id))


def _family_ids_for_spec(spec: SceneProductReadinessSpec) -> tuple[str, ...]:
    if spec.subject_type == "family":
        return (spec.subject_id,)
    pack = SCENE_COVERAGE_PACK_MAP.get(spec.subject_id)
    return tuple(pack.planned_family_ids) if pack is not None else ()


def _domains_for_texts(values: tuple[str, ...]) -> tuple[str, ...]:
    domain_ids: list[str] = []
    for value in values:
        text = str(value or "").casefold()
        explicit_domains = _EXPLICIT_GAP_DOMAINS.get(text)
        if explicit_domains is not None:
            for domain_id in explicit_domains:
                if domain_id not in domain_ids:
                    domain_ids.append(domain_id)
            continue
        for domain_id in PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS:
            if any(keyword in text for keyword in _DOMAIN_KEYWORDS[domain_id]):
                if domain_id not in domain_ids:
                    domain_ids.append(domain_id)
    return tuple(domain_ids)


def _matches_filters(
    row: SceneProductMaturityUpgradeRow,
    *,
    subject_type: str,
    readiness_level: str,
    domain_id: str,
    query: str,
) -> bool:
    if subject_type and row.subject_type != subject_type:
        return False
    if readiness_level and row.current_readiness_level != readiness_level:
        return False
    if domain_id and domain_id not in row.gap_domain_ids:
        return False
    if query and query not in _row_search_text(row):
        return False
    return True


def _row_search_text(row: SceneProductMaturityUpgradeRow) -> str:
    return " ".join(
        (
            row.subject_type,
            row.subject_id,
            row.label,
            row.status,
            row.current_readiness_level,
            row.static_closure_level,
            row.next_upgrade_goal,
            *row.pack_ids,
            *row.family_ids,
            *row.evidence_surfaces,
            *row.evidence_domain_ids,
            *row.remaining_product_gaps,
            *row.gap_domain_ids,
            row.rationale,
        )
    ).casefold()


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneProductMaturityUpgradeSourceEvidence, ...]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    evidence: list[SceneProductMaturityUpgradeSourceEvidence] = []
    for source_id, source_path, markers in SCENE_PRODUCT_MATURITY_UPGRADE_SOURCE_MARKERS:
        path = root / source_path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneProductMaturityUpgradeSourceEvidence(
                source_id=source_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
                status="ready" if path.exists() and not missing else "missing",
            )
        )
    return tuple(evidence)


def _unique_values(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS",
    "PRODUCT_MATURITY_UPGRADE_DOMAIN_LABELS",
    "SCENE_PRODUCT_MATURITY_UPGRADE_AUDIT_SOURCE_ID",
    "SceneProductMaturityUpgradeAuditReport",
    "SceneProductMaturityUpgradeIssue",
    "SceneProductMaturityUpgradeRow",
    "SceneProductMaturityUpgradeSourceEvidence",
    "audit_scene_product_maturity_upgrade_report",
    "build_scene_product_maturity_upgrade_audit_report",
]
