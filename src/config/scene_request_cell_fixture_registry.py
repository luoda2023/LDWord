"""Request-cell fixture coverage for high-frequency scene samples.

Pack-level DOCX fixtures prove that every coverage pack has at least one
Word/OOXML sample.  This registry bridges those fixtures to concrete user
request samples, so high-frequency requests can be audited without pretending
that every family already has an independent DOCX fixture.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.config.scene_high_frequency_request_samples import (
    HighFrequencyRequestSample,
    audit_high_frequency_request_samples,
    list_high_frequency_request_samples,
)
from src.config.scene_sample_fixture_registry import (
    SceneSampleFixtureSpec,
    audit_scene_sample_fixtures,
    scene_sample_fixtures_for_pack,
)


REQUEST_CELL_COVERAGE_LEVELS: tuple[str, ...] = (
    "direct_family_fixture",
    "pack_fixture_proxy",
    "manual_boundary_fixture",
    "ambiguous_fixture_set",
    "negative_control",
)


@dataclass(frozen=True, slots=True)
class SceneRequestCellFixtureSpec:
    """One high-frequency request sample linked to fixture evidence."""

    sample_id: str
    request_text: str
    expected_status: str
    expected_pack_ids: tuple[str, ...]
    expected_family_ids: tuple[str, ...]
    expected_plugin_gate_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    fixture_pack_ids: tuple[str, ...]
    fixture_family_ids: tuple[str, ...]
    manual_gate_ids: tuple[str, ...]
    coverage_level: str
    disambiguation_required: bool = False
    family_proxy_gap_ids: tuple[str, ...] = ()
    boundary_notes: tuple[str, ...] = ()

    @property
    def has_fixture_evidence(self) -> bool:
        return bool(self.fixture_ids)

    @property
    def is_family_proxy(self) -> bool:
        return self.coverage_level == "pack_fixture_proxy"

    def to_payload(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "request_text": self.request_text,
            "expected_status": self.expected_status,
            "expected_pack_ids": list(self.expected_pack_ids),
            "expected_family_ids": list(self.expected_family_ids),
            "expected_plugin_gate_ids": list(self.expected_plugin_gate_ids),
            "fixture_ids": list(self.fixture_ids),
            "fixture_pack_ids": list(self.fixture_pack_ids),
            "fixture_family_ids": list(self.fixture_family_ids),
            "manual_gate_ids": list(self.manual_gate_ids),
            "coverage_level": self.coverage_level,
            "disambiguation_required": self.disambiguation_required,
            "family_proxy_gap_ids": list(self.family_proxy_gap_ids),
            "boundary_notes": list(self.boundary_notes),
        }


def request_cell_family_ids(
    cell: SceneRequestCellFixtureSpec,
) -> tuple[str, ...]:
    """Return the canonical family ownership for one request cell.

    Explicit request routing remains authoritative.  A direct family fixture
    may additionally establish ownership when the natural-language sample
    intentionally lands at pack level.  Proxy and ambiguous fixture sets must
    not spread one request across every linked family.
    """

    explicit_family_ids = _unique_values(cell.expected_family_ids)
    if explicit_family_ids:
        return explicit_family_ids
    fixture_family_ids = _unique_values(cell.fixture_family_ids)
    if (
        cell.coverage_level == "direct_family_fixture"
        and len(fixture_family_ids) == 1
    ):
        return fixture_family_ids
    return ()


@dataclass(frozen=True, slots=True)
class SceneRequestCellFixtureAuditIssue:
    sample_id: str
    kind: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class SceneRequestCellFixtureSummary:
    cell_count: int
    fixture_cell_count: int
    negative_control_count: int
    family_proxy_count: int
    manual_boundary_count: int
    ambiguous_count: int
    coverage_level_counts: tuple[tuple[str, int], ...]
    pack_ids: tuple[str, ...]
    sample_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    family_proxy_sample_ids: tuple[str, ...]
    audit_issues: tuple[SceneRequestCellFixtureAuditIssue, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.audit_issues

    def to_payload(self) -> dict[str, object]:
        return {
            "cell_count": self.cell_count,
            "fixture_cell_count": self.fixture_cell_count,
            "negative_control_count": self.negative_control_count,
            "family_proxy_count": self.family_proxy_count,
            "manual_boundary_count": self.manual_boundary_count,
            "ambiguous_count": self.ambiguous_count,
            "coverage_level_counts": [
                {"coverage_level": level, "count": count}
                for level, count in self.coverage_level_counts
            ],
            "pack_ids": list(self.pack_ids),
            "sample_ids": list(self.sample_ids),
            "fixture_ids": list(self.fixture_ids),
            "family_proxy_sample_ids": list(self.family_proxy_sample_ids),
            "audit_issues": [
                {
                    "sample_id": issue.sample_id,
                    "kind": issue.kind,
                    "message": issue.message,
                    "severity": issue.severity,
                }
                for issue in self.audit_issues
            ],
        }


@dataclass(frozen=True, slots=True)
class SceneRequestCellBrowserItem:
    """One display row for the global request-cell registry browser."""

    sample_id: str
    request_text: str
    coverage_level: str
    coverage_label: str
    expected_status: str
    expected_pack_ids: tuple[str, ...]
    expected_family_ids: tuple[str, ...]
    expected_plugin_gate_ids: tuple[str, ...]
    fixture_ids: tuple[str, ...]
    fixture_pack_ids: tuple[str, ...]
    fixture_family_ids: tuple[str, ...]
    manual_gate_ids: tuple[str, ...]
    boundary_notes: tuple[str, ...]
    disambiguation_required: bool
    status_label: str
    search_text: str

    def to_payload(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "request_text": self.request_text,
            "coverage_level": self.coverage_level,
            "coverage_label": self.coverage_label,
            "expected_status": self.expected_status,
            "expected_pack_ids": list(self.expected_pack_ids),
            "expected_family_ids": list(self.expected_family_ids),
            "expected_plugin_gate_ids": list(self.expected_plugin_gate_ids),
            "fixture_ids": list(self.fixture_ids),
            "fixture_pack_ids": list(self.fixture_pack_ids),
            "fixture_family_ids": list(self.fixture_family_ids),
            "manual_gate_ids": list(self.manual_gate_ids),
            "boundary_notes": list(self.boundary_notes),
            "disambiguation_required": self.disambiguation_required,
            "status_label": self.status_label,
            "search_text": self.search_text,
        }


@dataclass(frozen=True, slots=True)
class SceneRequestCellRegistryBrowser:
    """Filterable global browser model for all request-cell fixture evidence."""

    items: tuple[SceneRequestCellBrowserItem, ...]
    total_count: int
    visible_count: int
    pack_filter: str = ""
    coverage_filter: str = ""
    family_filter: str = ""
    query: str = ""
    pack_options: tuple[str, ...] = ()
    coverage_options: tuple[str, ...] = ()
    family_options: tuple[str, ...] = ()
    coverage_level_counts: tuple[tuple[str, int], ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "total_count": self.total_count,
            "visible_count": self.visible_count,
            "pack_filter": self.pack_filter,
            "coverage_filter": self.coverage_filter,
            "family_filter": self.family_filter,
            "query": self.query,
            "pack_options": list(self.pack_options),
            "coverage_options": list(self.coverage_options),
            "family_options": list(self.family_options),
            "coverage_level_counts": [
                {"coverage_level": level, "count": count}
                for level, count in self.coverage_level_counts
            ],
            "items": [item.to_payload() for item in self.items],
        }


def list_scene_request_cell_fixtures() -> tuple[SceneRequestCellFixtureSpec, ...]:
    return tuple(
        _build_request_cell(sample)
        for sample in list_high_frequency_request_samples()
    )


def request_cell_fixtures_for_pack(
    pack_id: str,
) -> tuple[SceneRequestCellFixtureSpec, ...]:
    normalized = str(pack_id or "").strip()
    return tuple(
        cell
        for cell in list_scene_request_cell_fixtures()
        if normalized in cell.expected_pack_ids
    )


def build_scene_request_cell_fixture_summary(
    pack_ids: Sequence[str] | None = None,
) -> SceneRequestCellFixtureSummary:
    requested_pack_ids = _unique_values(pack_ids or ())
    cells = list_scene_request_cell_fixtures()
    if requested_pack_ids:
        cells = tuple(
            cell
            for cell in cells
            if set(cell.expected_pack_ids) & set(requested_pack_ids)
        )
    level_counts = Counter(cell.coverage_level for cell in cells)
    return SceneRequestCellFixtureSummary(
        cell_count=len(cells),
        fixture_cell_count=sum(1 for cell in cells if cell.has_fixture_evidence),
        negative_control_count=sum(
            1 for cell in cells if cell.coverage_level == "negative_control"
        ),
        family_proxy_count=sum(1 for cell in cells if cell.is_family_proxy),
        manual_boundary_count=sum(
            1 for cell in cells if cell.coverage_level == "manual_boundary_fixture"
        ),
        ambiguous_count=sum(
            1 for cell in cells if cell.coverage_level == "ambiguous_fixture_set"
        ),
        coverage_level_counts=tuple(
            (level, int(level_counts.get(level, 0)))
            for level in REQUEST_CELL_COVERAGE_LEVELS
            if level_counts.get(level, 0)
        ),
        pack_ids=_unique_values(
            pack_id for cell in cells for pack_id in cell.expected_pack_ids
        ),
        sample_ids=tuple(cell.sample_id for cell in cells),
        fixture_ids=_unique_values(
            fixture_id for cell in cells for fixture_id in cell.fixture_ids
        ),
        family_proxy_sample_ids=tuple(
            cell.sample_id for cell in cells if cell.is_family_proxy
        ),
        audit_issues=audit_scene_request_cell_fixtures(),
    )


def build_scene_request_cell_registry_browser(
    *,
    pack_id: str = "",
    coverage_level: str = "",
    family_id: str = "",
    query: str = "",
) -> SceneRequestCellRegistryBrowser:
    """Build a filterable global browser state for request-cell evidence."""

    cells = list_scene_request_cell_fixtures()
    normalized_pack = str(pack_id or "").strip()
    normalized_coverage = str(coverage_level or "").strip()
    normalized_family = str(family_id or "").strip()
    normalized_query = str(query or "").strip().lower()

    items = tuple(_request_cell_browser_item(cell) for cell in cells)
    filtered = tuple(
        item
        for item in items
        if _matches_browser_filters(
            item,
            pack_id=normalized_pack,
            coverage_level=normalized_coverage,
            family_id=normalized_family,
            query=normalized_query,
        )
    )
    level_counts = Counter(item.coverage_level for item in items)
    return SceneRequestCellRegistryBrowser(
        items=filtered,
        total_count=len(items),
        visible_count=len(filtered),
        pack_filter=normalized_pack,
        coverage_filter=normalized_coverage,
        family_filter=normalized_family,
        query=str(query or "").strip(),
        pack_options=_unique_values(pack_id for item in items for pack_id in item.expected_pack_ids),
        coverage_options=tuple(
            level for level in REQUEST_CELL_COVERAGE_LEVELS if level_counts.get(level, 0)
        ),
        family_options=_unique_values(
            family_id
            for item in items
            for family_id in (*item.expected_family_ids, *item.fixture_family_ids)
        ),
        coverage_level_counts=tuple(
            (level, int(level_counts.get(level, 0)))
            for level in REQUEST_CELL_COVERAGE_LEVELS
            if level_counts.get(level, 0)
        ),
    )


def audit_scene_request_cell_fixtures() -> tuple[SceneRequestCellFixtureAuditIssue, ...]:
    issues: list[SceneRequestCellFixtureAuditIssue] = []
    _append_upstream_audit_issues(issues)
    cells = list_scene_request_cell_fixtures()
    seen: set[str] = set()
    for cell in cells:
        if cell.sample_id in seen:
            issues.append(
                SceneRequestCellFixtureAuditIssue(
                    sample_id=cell.sample_id,
                    kind="duplicate_request_cell",
                    message=f"Duplicate request-cell fixture entry: {cell.sample_id}.",
                )
            )
        seen.add(cell.sample_id)
        if cell.coverage_level not in REQUEST_CELL_COVERAGE_LEVELS:
            issues.append(
                SceneRequestCellFixtureAuditIssue(
                    sample_id=cell.sample_id,
                    kind="unknown_coverage_level",
                    message=f"Unknown request-cell coverage level: {cell.coverage_level}.",
                )
            )
        if cell.expected_status != "unmatched" and not cell.fixture_ids:
            issues.append(
                SceneRequestCellFixtureAuditIssue(
                    sample_id=cell.sample_id,
                    kind="missing_request_cell_fixture",
                    message="Matched or ambiguous request sample has no fixture evidence.",
                )
            )
        missing_pack_ids = tuple(
            pack_id
            for pack_id in cell.expected_pack_ids
            if pack_id not in cell.fixture_pack_ids
        )
        if missing_pack_ids:
            issues.append(
                SceneRequestCellFixtureAuditIssue(
                    sample_id=cell.sample_id,
                    kind="missing_pack_fixture_link",
                    message=(
                        "Request-cell fixture evidence does not cover expected packs: "
                        + ", ".join(missing_pack_ids)
                    ),
                )
            )
        if cell.expected_plugin_gate_ids and not (
            set(cell.expected_plugin_gate_ids) & set(cell.manual_gate_ids)
        ):
            issues.append(
                SceneRequestCellFixtureAuditIssue(
                    sample_id=cell.sample_id,
                    kind="missing_manual_gate_fixture",
                    message=(
                        "Request sample expects plugin/manual gate evidence but "
                        "linked fixtures do not expose the gate."
                    ),
                )
            )
    expected_sample_ids = {sample.sample_id for sample in list_high_frequency_request_samples()}
    actual_sample_ids = {cell.sample_id for cell in cells}
    for sample_id in sorted(expected_sample_ids - actual_sample_ids):
        issues.append(
            SceneRequestCellFixtureAuditIssue(
                sample_id=sample_id,
                kind="missing_request_cell",
                message="High-frequency request sample has no request-cell entry.",
            )
        )
    return tuple(issues)


def _request_cell_browser_item(
    cell: SceneRequestCellFixtureSpec,
) -> SceneRequestCellBrowserItem:
    search_values = (
        cell.sample_id,
        cell.request_text,
        cell.expected_status,
        cell.coverage_level,
        *cell.expected_pack_ids,
        *cell.expected_family_ids,
        *cell.expected_plugin_gate_ids,
        *cell.fixture_ids,
        *cell.fixture_pack_ids,
        *cell.fixture_family_ids,
        *cell.manual_gate_ids,
        *cell.boundary_notes,
    )
    return SceneRequestCellBrowserItem(
        sample_id=cell.sample_id,
        request_text=cell.request_text,
        coverage_level=cell.coverage_level,
        coverage_label=_coverage_level_label(cell.coverage_level),
        expected_status=cell.expected_status,
        expected_pack_ids=cell.expected_pack_ids,
        expected_family_ids=cell.expected_family_ids,
        expected_plugin_gate_ids=cell.expected_plugin_gate_ids,
        fixture_ids=cell.fixture_ids,
        fixture_pack_ids=cell.fixture_pack_ids,
        fixture_family_ids=cell.fixture_family_ids,
        manual_gate_ids=cell.manual_gate_ids,
        boundary_notes=cell.boundary_notes,
        disambiguation_required=cell.disambiguation_required,
        status_label=_request_cell_status_label(cell),
        search_text=" ".join(str(value or "").strip().lower() for value in search_values),
    )


def _matches_browser_filters(
    item: SceneRequestCellBrowserItem,
    *,
    pack_id: str,
    coverage_level: str,
    family_id: str,
    query: str,
) -> bool:
    if pack_id and pack_id not in item.expected_pack_ids:
        return False
    if coverage_level and item.coverage_level != coverage_level:
        return False
    if family_id and family_id not in (*item.expected_family_ids, *item.fixture_family_ids):
        return False
    if query and query not in item.search_text:
        return False
    return True


def _coverage_level_label(coverage_level: str) -> str:
    return {
        "direct_family_fixture": "直接证据",
        "pack_fixture_proxy": "proxy",
        "manual_boundary_fixture": "人工门",
        "ambiguous_fixture_set": "歧义",
        "negative_control": "负例",
    }.get(str(coverage_level or ""), str(coverage_level or "未知"))


def _request_cell_status_label(cell: SceneRequestCellFixtureSpec) -> str:
    if cell.coverage_level == "negative_control":
        return "负例"
    if cell.coverage_level == "manual_boundary_fixture":
        return "人工确认"
    if cell.coverage_level == "ambiguous_fixture_set":
        return "需裁决"
    if cell.has_fixture_evidence:
        return "有证据"
    return "缺证据"


def _build_request_cell(
    sample: HighFrequencyRequestSample,
) -> SceneRequestCellFixtureSpec:
    fixtures = _fixtures_for_sample(sample)
    fixture_family_ids = _unique_values(fixture.family_id for fixture in fixtures)
    manual_gate_ids = _unique_values(fixture.manual_gate_id for fixture in fixtures)
    family_proxy_gap_ids = _family_proxy_gap_ids(sample, fixture_family_ids)
    coverage_level = _coverage_level(sample, fixtures, family_proxy_gap_ids)
    return SceneRequestCellFixtureSpec(
        sample_id=sample.sample_id,
        request_text=sample.request_text,
        expected_status=sample.expected_status,
        expected_pack_ids=sample.expected_pack_ids,
        expected_family_ids=sample.expected_family_ids,
        expected_plugin_gate_ids=sample.expected_plugin_gate_ids,
        fixture_ids=tuple(fixture.fixture_id for fixture in fixtures),
        fixture_pack_ids=_unique_values(fixture.pack_id for fixture in fixtures),
        fixture_family_ids=fixture_family_ids,
        manual_gate_ids=manual_gate_ids,
        coverage_level=coverage_level,
        disambiguation_required=sample.disambiguation_required,
        family_proxy_gap_ids=family_proxy_gap_ids,
        boundary_notes=_unique_values(
            note for fixture in fixtures for note in fixture.boundary_notes
        ),
    )


def _fixtures_for_sample(
    sample: HighFrequencyRequestSample,
) -> tuple[SceneSampleFixtureSpec, ...]:
    fixtures: list[SceneSampleFixtureSpec] = []
    for pack_id in sample.expected_pack_ids:
        fixtures.extend(
            fixture
            for fixture in scene_sample_fixtures_for_pack(pack_id)
            if _fixture_matches_sample(fixture, sample)
        )
    return tuple(_dedupe_fixtures(fixtures))


def _fixture_matches_sample(
    fixture: SceneSampleFixtureSpec,
    sample: HighFrequencyRequestSample,
) -> bool:
    if not fixture.request_sample_ids:
        return True
    return sample.sample_id in fixture.request_sample_ids


def _family_proxy_gap_ids(
    sample: HighFrequencyRequestSample,
    fixture_family_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if not sample.expected_family_ids:
        return ()
    return tuple(
        family_id
        for family_id in sample.expected_family_ids
        if family_id not in fixture_family_ids
    )


def _coverage_level(
    sample: HighFrequencyRequestSample,
    fixtures: tuple[SceneSampleFixtureSpec, ...],
    family_proxy_gap_ids: tuple[str, ...],
) -> str:
    if sample.expected_status == "unmatched":
        return "negative_control"
    if sample.expected_status == "ambiguous":
        return "ambiguous_fixture_set"
    manual_gate_ids = {
        fixture.manual_gate_id for fixture in fixtures if fixture.manual_gate_id
    }
    if sample.expected_plugin_gate_ids and (
        set(sample.expected_plugin_gate_ids) & manual_gate_ids
    ):
        return "manual_boundary_fixture"
    if family_proxy_gap_ids:
        return "pack_fixture_proxy"
    return "direct_family_fixture"


def _append_upstream_audit_issues(
    issues: list[SceneRequestCellFixtureAuditIssue],
) -> None:
    sample_issues = audit_high_frequency_request_samples()
    if sample_issues:
        issues.append(
            SceneRequestCellFixtureAuditIssue(
                sample_id="registry:high_frequency_request_samples",
                kind="upstream_high_frequency_sample_audit_failed",
                message=(
                    "High-frequency request sample audit must be clean before "
                    "request-cell fixture coverage can be trusted."
                ),
            )
        )
    fixture_issues = audit_scene_sample_fixtures()
    if fixture_issues:
        issues.append(
            SceneRequestCellFixtureAuditIssue(
                sample_id="registry:scene_sample_fixtures",
                kind="upstream_scene_sample_fixture_audit_failed",
                message=(
                    "Scene sample fixture audit must be clean before request-cell "
                    "fixture coverage can be trusted."
                ),
            )
        )


def _dedupe_fixtures(
    fixtures: Iterable[SceneSampleFixtureSpec],
) -> tuple[SceneSampleFixtureSpec, ...]:
    result: list[SceneSampleFixtureSpec] = []
    seen: set[str] = set()
    for fixture in fixtures:
        if fixture.fixture_id in seen:
            continue
        result.append(fixture)
        seen.add(fixture.fixture_id)
    return tuple(result)


def _unique_values(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


__all__ = [
    "REQUEST_CELL_COVERAGE_LEVELS",
    "SceneRequestCellBrowserItem",
    "SceneRequestCellFixtureAuditIssue",
    "SceneRequestCellFixtureSpec",
    "SceneRequestCellFixtureSummary",
    "SceneRequestCellRegistryBrowser",
    "audit_scene_request_cell_fixtures",
    "build_scene_request_cell_fixture_summary",
    "build_scene_request_cell_registry_browser",
    "list_scene_request_cell_fixtures",
    "request_cell_family_ids",
    "request_cell_fixtures_for_pack",
]
