"""Ambiguous pack-pair audit for high-frequency scene requests.

N2.162 turns ambiguous user phrasing into a first-class release-gate asset.
Every declared high-frequency pack pair must have at least one ambiguous
request-cell, router evidence, fixture evidence, and a disambiguation prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.scene_coverage_manifest import SCENE_COVERAGE_PACK_MAP
from src.config.scene_high_frequency_request_samples import (
    HighFrequencyRequestSample,
    list_high_frequency_request_samples,
)
from src.config.scene_natural_request_router import (
    NaturalRequestRouteResult,
    route_natural_scene_request,
)
from src.config.scene_request_cell_fixture_registry import (
    SceneRequestCellFixtureSpec,
    list_scene_request_cell_fixtures,
)


N2_162_REQUIRED_BOUNDARY_IDS: tuple[str, ...] = (
    "product_manual_application_vs_technical",
    "quote_plan_application_vs_finance",
    "certificate_materials_bidding_vs_fixed_form",
    "bilingual_document_formatting_vs_review",
    "project_application_form_application_vs_fixed_form",
    "batch_notice_official_vs_hr",
)

N2_162_SOURCE_EVIDENCE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "v29_plan",
        "docs/audits/高层场景能力矩阵V29高频任务全集与边界准入深化规划_2026-06-19.md",
        ("N2.162", "每个易混 pack 对至少有一条 ambiguous request-cell"),
    ),
    (
        "request_samples",
        "src/config/scene_high_frequency_request_samples.py",
        (
            "ambiguous_product_manual",
            "ambiguous_quote_plan",
            "ambiguous_certificate_materials",
            "ambiguous_bilingual_document",
            "project_application_form",
            "ambiguous_batch_notice",
        ),
    ),
    (
        "natural_router",
        "src/config/scene_natural_request_router.py",
        ("项目申请表", "批量通知", "disambiguation_prompt"),
    ),
    (
        "request_cell_fixture_registry",
        "src/config/scene_request_cell_fixture_registry.py",
        ("ambiguous_fixture_set", "disambiguation_required"),
    ),
)


@dataclass(frozen=True, slots=True)
class AmbiguousBoundaryPairSpec:
    boundary_id: str
    phrase: str
    sample_id: str
    expected_route_ids: tuple[str, ...]
    expected_pack_ids: tuple[str, ...]
    clarification_axis: str
    reason: str

    @property
    def pack_pair_key(self) -> str:
        return _pair_key(self.expected_pack_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "boundary_id": self.boundary_id,
            "phrase": self.phrase,
            "sample_id": self.sample_id,
            "expected_route_ids": list(self.expected_route_ids),
            "expected_pack_ids": list(self.expected_pack_ids),
            "pack_pair_key": self.pack_pair_key,
            "clarification_axis": self.clarification_axis,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class SceneAmbiguousBoundaryIssue:
    boundary_id: str
    kind: str
    message: str
    severity: str = "error"

    def to_payload(self) -> dict[str, object]:
        return {
            "boundary_id": self.boundary_id,
            "kind": self.kind,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class SceneAmbiguousBoundarySourceEvidence:
    evidence_id: str
    source_path: str
    markers: tuple[str, ...]
    missing_markers: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.missing_markers else "missing"

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_path": self.source_path,
            "markers": list(self.markers),
            "missing_markers": list(self.missing_markers),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class SceneAmbiguousBoundaryRow:
    boundary_id: str
    phrase: str
    sample_id: str
    expected_route_ids: tuple[str, ...]
    expected_pack_ids: tuple[str, ...]
    pack_pair_key: str
    clarification_axis: str
    sample_status: str
    route_status: str
    candidate_route_ids: tuple[str, ...]
    candidate_pack_ids: tuple[str, ...]
    coverage_level: str
    fixture_ids: tuple[str, ...]
    disambiguation_required: bool
    disambiguation_prompt: str
    issue_ids: tuple[str, ...]

    @property
    def status(self) -> str:
        return "ready" if not self.issue_ids else "needs_attention"

    @property
    def has_fixture_evidence(self) -> bool:
        return bool(self.fixture_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "boundary_id": self.boundary_id,
            "phrase": self.phrase,
            "sample_id": self.sample_id,
            "status": self.status,
            "expected_route_ids": list(self.expected_route_ids),
            "expected_pack_ids": list(self.expected_pack_ids),
            "pack_pair_key": self.pack_pair_key,
            "clarification_axis": self.clarification_axis,
            "sample_status": self.sample_status,
            "route_status": self.route_status,
            "candidate_route_ids": list(self.candidate_route_ids),
            "candidate_pack_ids": list(self.candidate_pack_ids),
            "coverage_level": self.coverage_level,
            "fixture_ids": list(self.fixture_ids),
            "disambiguation_required": self.disambiguation_required,
            "disambiguation_prompt": self.disambiguation_prompt,
            "issue_ids": list(self.issue_ids),
        }


@dataclass(frozen=True, slots=True)
class SceneAmbiguousBoundaryAuditReport:
    rows: tuple[SceneAmbiguousBoundaryRow, ...]
    issues: tuple[SceneAmbiguousBoundaryIssue, ...]
    source_evidence: tuple[SceneAmbiguousBoundarySourceEvidence, ...] = ()
    boundary_filter: str = ""
    pack_filter: str = ""

    @property
    def status(self) -> str:
        return "passed" if not self.issues else "failed"

    @property
    def boundary_count(self) -> int:
        return len(self.rows)

    @property
    def pack_pair_count(self) -> int:
        return len({row.pack_pair_key for row in self.rows})

    @property
    def ready_boundary_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "ready")

    @property
    def ambiguous_sample_count(self) -> int:
        return sum(1 for row in self.rows if row.sample_status == "ambiguous")

    @property
    def fixture_backed_count(self) -> int:
        return sum(1 for row in self.rows if row.has_fixture_evidence)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def missing_source_evidence_count(self) -> int:
        return sum(1 for item in self.source_evidence if item.missing_markers)

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "boundary_filter": self.boundary_filter,
            "pack_filter": self.pack_filter,
            "counts": {
                "boundary_count": self.boundary_count,
                "pack_pair_count": self.pack_pair_count,
                "ready_boundary_count": self.ready_boundary_count,
                "ambiguous_sample_count": self.ambiguous_sample_count,
                "fixture_backed_count": self.fixture_backed_count,
                "issue_count": self.issue_count,
                "missing_source_evidence_count": self.missing_source_evidence_count,
            },
            "required_boundary_ids": list(N2_162_REQUIRED_BOUNDARY_IDS),
            "rows": [row.to_payload() for row in self.rows],
            "issues": [issue.to_payload() for issue in self.issues],
            "source_evidence": [item.to_payload() for item in self.source_evidence],
        }


AMBIGUOUS_BOUNDARY_PAIR_SPECS: tuple[AmbiguousBoundaryPairSpec, ...] = (
    AmbiguousBoundaryPairSpec(
        "product_manual_application_vs_technical",
        "产品手册",
        "ambiguous_product_manual",
        ("product_sales_document", "technical_long_document"),
        ("application_reports", "technical_long_docs"),
        "客户售前资料 vs 技术操作手册",
        "同一说法可能是客户材料，也可能是技术长文档。",
    ),
    AmbiguousBoundaryPairSpec(
        "quote_plan_application_vs_finance",
        "报价方案",
        "ambiguous_quote_plan",
        ("finance_quote_documents", "product_sales_document"),
        ("professional_disclosure", "application_reports"),
        "金额/预算表 vs 售前方案正文",
        "报价类请求不能只靠“方案”二字落到售前，也不能把财务正确性并入核心。",
    ),
    AmbiguousBoundaryPairSpec(
        "certificate_materials_bidding_vs_fixed_form",
        "证书材料",
        "ambiguous_certificate_materials",
        ("bidding_qualification_archive", "fixed_form_batch_documents"),
        ("bidding_materials", "batch_forms"),
        "投标资质附件 vs 批量套打证书",
        "证书既可能是已有资质证照归档，也可能是要批量生成的固定版式输出。",
    ),
    AmbiguousBoundaryPairSpec(
        "bilingual_document_formatting_vs_review",
        "双语文档",
        "ambiguous_bilingual_document",
        ("bilingual_review_documents", "quick_bilingual_formatting"),
        ("professional_disclosure", "quick_formatting"),
        "双语排版 vs 术语一致性/翻译审阅",
        "双语外观排版可以本地处理，翻译质量和术语判断必须进入专业边界。",
    ),
    AmbiguousBoundaryPairSpec(
        "project_application_form_application_vs_fixed_form",
        "项目申请表",
        "project_application_form",
        ("project_application_package", "fixed_form_batch_documents"),
        ("application_reports", "batch_forms"),
        "申报材料包 vs 固定版式表单套打",
        "项目申请表可能是申报正文/附件包，也可能只是固定版式表单。",
    ),
    AmbiguousBoundaryPairSpec(
        "batch_notice_official_vs_hr",
        "批量通知",
        "ambiguous_batch_notice",
        ("hr_batch_documents", "official_policy_documents"),
        ("batch_forms", "official_policy"),
        "一人一份 HR 通知 vs 公文通知/传阅",
        "通知类请求容易在公文和 HR 批量输出之间摇摆，必须先确认对象和交付方式。",
    ),
)


def list_ambiguous_boundary_pair_specs() -> tuple[AmbiguousBoundaryPairSpec, ...]:
    return AMBIGUOUS_BOUNDARY_PAIR_SPECS


def build_scene_ambiguous_boundary_audit_report(
    boundary_id: str = "",
    pack_id: str = "",
    project_root: Path | str | None = None,
) -> SceneAmbiguousBoundaryAuditReport:
    normalized_boundary = str(boundary_id or "").strip()
    normalized_pack = str(pack_id or "").strip()
    specs = tuple(
        spec
        for spec in AMBIGUOUS_BOUNDARY_PAIR_SPECS
        if (not normalized_boundary or spec.boundary_id == normalized_boundary)
        and (not normalized_pack or normalized_pack in spec.expected_pack_ids)
    )
    samples = {sample.sample_id: sample for sample in list_high_frequency_request_samples()}
    cells = {cell.sample_id: cell for cell in list_scene_request_cell_fixtures()}

    rows: list[SceneAmbiguousBoundaryRow] = []
    issues: list[SceneAmbiguousBoundaryIssue] = []
    for spec in specs:
        sample = samples.get(spec.sample_id)
        cell = cells.get(spec.sample_id)
        route_result = (
            route_natural_scene_request(sample.request_text)
            if sample is not None
            else None
        )
        row, row_issues = _build_row(spec, sample, cell, route_result)
        rows.append(row)
        issues.extend(row_issues)

    if not normalized_boundary and not normalized_pack:
        issues.extend(_registry_issues(rows))
    source_evidence = _source_evidence(project_root)
    issues.extend(_source_evidence_issues(source_evidence))
    return SceneAmbiguousBoundaryAuditReport(
        rows=tuple(rows),
        issues=tuple(issues),
        source_evidence=source_evidence,
        boundary_filter=normalized_boundary,
        pack_filter=normalized_pack,
    )


def audit_scene_ambiguous_boundary_report(
    report: SceneAmbiguousBoundaryAuditReport | None = None,
) -> tuple[SceneAmbiguousBoundaryIssue, ...]:
    current = report or build_scene_ambiguous_boundary_audit_report()
    return current.issues


def _build_row(
    spec: AmbiguousBoundaryPairSpec,
    sample: HighFrequencyRequestSample | None,
    cell: SceneRequestCellFixtureSpec | None,
    route_result: NaturalRequestRouteResult | None,
) -> tuple[SceneAmbiguousBoundaryRow, tuple[SceneAmbiguousBoundaryIssue, ...]]:
    issue_ids: list[str] = []
    issues: list[SceneAmbiguousBoundaryIssue] = []

    sample_status = sample.expected_status if sample is not None else ""
    route_status = route_result.status if route_result is not None else ""
    candidate_route_ids = (
        tuple(match.route.route_id for match in route_result.matches)
        if route_result is not None
        else ()
    )
    candidate_pack_ids = (
        tuple(match.route.pack_id for match in route_result.matches)
        if route_result is not None
        else ()
    )
    coverage_level = cell.coverage_level if cell is not None else ""
    fixture_ids = cell.fixture_ids if cell is not None else ()
    disambiguation_required = (
        bool(sample.disambiguation_required) if sample is not None else False
    )
    disambiguation_prompt = (
        route_result.disambiguation_prompt if route_result is not None else ""
    )

    def add_issue(kind: str, message: str) -> None:
        issue_ids.append(kind)
        issues.append(SceneAmbiguousBoundaryIssue(spec.boundary_id, kind, message))

    if sample is None:
        add_issue("missing_request_sample", f"Missing sample {spec.sample_id}.")
    elif sample.expected_status != "ambiguous":
        add_issue(
            "sample_not_ambiguous",
            f"{spec.sample_id} status is {sample.expected_status}, expected ambiguous.",
        )
    else:
        _expect_subset(
            spec,
            "sample_route_ids",
            spec.expected_route_ids,
            sample.expected_route_ids,
            add_issue,
        )
        _expect_subset(
            spec,
            "sample_pack_ids",
            spec.expected_pack_ids,
            sample.expected_pack_ids,
            add_issue,
        )

    if route_result is None:
        add_issue("missing_route_result", "Cannot route missing sample.")
    elif route_result.status != "ambiguous":
        add_issue(
            "route_not_ambiguous",
            f"Router returned {route_result.status}, expected ambiguous.",
        )
    else:
        _expect_subset(
            spec,
            "candidate_route_ids",
            spec.expected_route_ids,
            candidate_route_ids,
            add_issue,
        )
        _expect_subset(
            spec,
            "candidate_pack_ids",
            spec.expected_pack_ids,
            candidate_pack_ids,
            add_issue,
        )

    if cell is None:
        add_issue("missing_request_cell", f"Missing request-cell {spec.sample_id}.")
    elif cell.coverage_level != "ambiguous_fixture_set":
        add_issue(
            "request_cell_not_ambiguous",
            f"{spec.sample_id} coverage is {cell.coverage_level}.",
        )
    elif not cell.fixture_ids:
        add_issue("missing_fixture_evidence", f"{spec.sample_id} has no fixture evidence.")

    if not disambiguation_required:
        add_issue("missing_disambiguation_flag", "Sample must require disambiguation.")
    if not disambiguation_prompt:
        add_issue("missing_disambiguation_prompt", "Router must explain the ambiguity.")
    if len(set(spec.expected_pack_ids)) < 2:
        add_issue("not_a_pack_pair", "Ambiguous boundary must cover at least two packs.")
    for pack_id in spec.expected_pack_ids:
        if pack_id not in SCENE_COVERAGE_PACK_MAP:
            add_issue("unknown_pack", f"Unknown coverage pack {pack_id}.")

    row = SceneAmbiguousBoundaryRow(
        boundary_id=spec.boundary_id,
        phrase=spec.phrase,
        sample_id=spec.sample_id,
        expected_route_ids=spec.expected_route_ids,
        expected_pack_ids=spec.expected_pack_ids,
        pack_pair_key=spec.pack_pair_key,
        clarification_axis=spec.clarification_axis,
        sample_status=sample_status,
        route_status=route_status,
        candidate_route_ids=candidate_route_ids,
        candidate_pack_ids=candidate_pack_ids,
        coverage_level=coverage_level,
        fixture_ids=fixture_ids,
        disambiguation_required=disambiguation_required,
        disambiguation_prompt=disambiguation_prompt,
        issue_ids=tuple(issue_ids),
    )
    return row, tuple(issues)


def _registry_issues(
    rows: tuple[SceneAmbiguousBoundaryRow, ...],
) -> tuple[SceneAmbiguousBoundaryIssue, ...]:
    issues: list[SceneAmbiguousBoundaryIssue] = []
    row_ids = {row.boundary_id for row in rows}
    for boundary_id in N2_162_REQUIRED_BOUNDARY_IDS:
        if boundary_id not in row_ids:
            issues.append(
                SceneAmbiguousBoundaryIssue(
                    boundary_id,
                    "missing_required_boundary",
                    f"Required ambiguous boundary {boundary_id} is missing.",
                )
            )
    duplicate_pairs = _duplicate_values(row.pack_pair_key for row in rows)
    for pair_key in duplicate_pairs:
        issues.append(
            SceneAmbiguousBoundaryIssue(
                pair_key,
                "duplicate_pack_pair",
                f"Pack pair {pair_key} has more than one primary boundary spec.",
            )
        )
    return tuple(issues)


def _source_evidence(
    project_root: Path | str | None,
) -> tuple[SceneAmbiguousBoundarySourceEvidence, ...]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    evidence: list[SceneAmbiguousBoundarySourceEvidence] = []
    for evidence_id, source_path, markers in N2_162_SOURCE_EVIDENCE:
        path = root / source_path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = tuple(marker for marker in markers if marker not in text)
        evidence.append(
            SceneAmbiguousBoundarySourceEvidence(
                evidence_id=evidence_id,
                source_path=source_path,
                markers=markers,
                missing_markers=missing,
            )
        )
    return tuple(evidence)


def _source_evidence_issues(
    source_evidence: tuple[SceneAmbiguousBoundarySourceEvidence, ...],
) -> tuple[SceneAmbiguousBoundaryIssue, ...]:
    return tuple(
        SceneAmbiguousBoundaryIssue(
            evidence.evidence_id,
            "missing_source_evidence",
            (
                f"{evidence.source_path} missing markers: "
                f"{', '.join(evidence.missing_markers)}"
            ),
        )
        for evidence in source_evidence
        if evidence.missing_markers
    )


def _expect_subset(
    spec: AmbiguousBoundaryPairSpec,
    kind: str,
    expected: tuple[str, ...],
    actual: tuple[str, ...],
    add_issue,
) -> None:
    missing = tuple(value for value in expected if value not in actual)
    if missing:
        add_issue(
            f"missing_{kind}",
            (
                f"{spec.boundary_id} missing {kind}: "
                f"expected {','.join(expected)}, actual {','.join(actual)}."
            ),
        )


def _pair_key(pack_ids: tuple[str, ...]) -> str:
    return "::".join(sorted(set(pack_ids)))


def _duplicate_values(values) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
        seen.add(normalized)
    return tuple(duplicates)


__all__ = [
    "AMBIGUOUS_BOUNDARY_PAIR_SPECS",
    "N2_162_REQUIRED_BOUNDARY_IDS",
    "SceneAmbiguousBoundaryAuditReport",
    "SceneAmbiguousBoundaryIssue",
    "build_scene_ambiguous_boundary_audit_report",
    "audit_scene_ambiguous_boundary_report",
    "list_ambiguous_boundary_pair_specs",
]
