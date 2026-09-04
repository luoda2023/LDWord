"""Runtime evidence for English journal submission package delivery."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.config.material_schema_registry import get_material_schema, resolve_material_schema_ids


JOURNAL_FAMILY_ID = "journal_en"
JOURNAL_SCHEMA_IDS = ("journal_submission_materials_v1", "journal_materials_v1")
REQUIRED_PACKAGE_COMPONENTS = (
    "submission_manuscript",
    "cover_letter",
    "declaration_package",
)
OPTIONAL_PACKAGE_COMPONENTS = (
    "review_copy",
    "compliance_report",
)


@dataclass(frozen=True, slots=True)
class JournalSubmissionPackageIssue:
    """One issue in journal submission package evidence."""

    component_id: str
    kind: str
    message: str
    severity: str = "warning"
    expected: str = ""
    observed: str = ""


@dataclass(frozen=True, slots=True)
class JournalSubmissionPackageItem:
    """One expected package component or delivery preset."""

    component_id: str
    label: str = ""
    required: bool = False
    preset_id: str = ""
    output_path: str = ""
    report_json: bool = False
    report_markdown: bool = False
    material_manifest: bool = False
    material_package: bool = False
    include_structured_intermediate: bool = False
    satisfied: bool = False


@dataclass(frozen=True, slots=True)
class JournalSubmissionPackageSummary:
    """Compact counts used by reports and Workbench summaries."""

    component_count: int = 0
    required_component_count: int = 0
    satisfied_required_count: int = 0
    output_count: int = 0
    report_enabled_count: int = 0
    material_artifact_enabled_count: int = 0


@dataclass(frozen=True, slots=True)
class JournalSubmissionPackageResult:
    """Structured evidence for English journal delivery packages."""

    family_id: str = ""
    status: str = "not_applicable"
    default_delivery_preset_id: str = ""
    summary: JournalSubmissionPackageSummary = field(
        default_factory=JournalSubmissionPackageSummary
    )
    items: tuple[JournalSubmissionPackageItem, ...] = ()
    issues: tuple[JournalSubmissionPackageIssue, ...] = ()

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity != "error")

    @property
    def manual_confirmation_required(self) -> bool:
        return bool(self.issues)

    def to_dict(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "status": self.status,
            "default_delivery_preset_id": self.default_delivery_preset_id,
            "manual_confirmation_required": self.manual_confirmation_required,
            "summary": {
                "component_count": self.summary.component_count,
                "required_component_count": self.summary.required_component_count,
                "satisfied_required_count": self.summary.satisfied_required_count,
                "output_count": self.summary.output_count,
                "report_enabled_count": self.summary.report_enabled_count,
                "material_artifact_enabled_count": self.summary.material_artifact_enabled_count,
            },
            "items": [
                {
                    "component_id": item.component_id,
                    "label": item.label,
                    "required": item.required,
                    "preset_id": item.preset_id,
                    "output_path": item.output_path,
                    "report_json": item.report_json,
                    "report_markdown": item.report_markdown,
                    "material_manifest": item.material_manifest,
                    "material_package": item.material_package,
                    "include_structured_intermediate": item.include_structured_intermediate,
                    "satisfied": item.satisfied,
                }
                for item in self.items
            ],
            "issue_count": len(self.issues),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "component_id": issue.component_id,
                    "kind": issue.kind,
                    "severity": issue.severity,
                    "expected": issue.expected,
                    "observed": issue.observed,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


def inspect_journal_submission_package(
    config,
    *,
    output_paths: Mapping[str, object] | None = None,
) -> JournalSubmissionPackageResult:
    """Build runtime evidence for English journal submission package presets."""

    schema_ids = _config_material_schema_ids(config)
    family_id = _journal_family_for_schema_ids(schema_ids)
    if not _is_journal_config(config, schema_ids=schema_ids, family_id=family_id):
        return JournalSubmissionPackageResult()

    normalized_output_paths = {
        str(key): str(value)
        for key, value in dict(output_paths or {}).items()
        if str(key or "").strip() and str(value or "").strip()
    }
    presets = list(getattr(config, "delivery_presets", []) or [])
    preset_by_id = {
        str(getattr(preset, "preset_id", "") or "").strip(): preset
        for preset in presets
        if str(getattr(preset, "preset_id", "") or "").strip()
    }
    component_ids = _ordered_component_ids(preset_by_id)
    items: list[JournalSubmissionPackageItem] = []
    issues: list[JournalSubmissionPackageIssue] = []

    for component_id in component_ids:
        preset = preset_by_id.get(component_id)
        required = component_id in REQUIRED_PACKAGE_COMPONENTS
        if preset is None:
            if required:
                issues.append(
                    JournalSubmissionPackageIssue(
                        component_id=component_id,
                        kind="missing_delivery_preset",
                        severity="error",
                        expected=component_id,
                        message=f"Journal submission package requires preset '{component_id}'.",
                    )
                )
            items.append(
                JournalSubmissionPackageItem(
                    component_id=component_id,
                    label=component_id,
                    required=required,
                    satisfied=False,
                )
            )
            continue

        artifacts = getattr(preset, "artifacts", None)
        output_path = normalized_output_paths.get(component_id, "")
        final_docx = bool(getattr(artifacts, "final_docx", False))
        report_json = bool(getattr(artifacts, "report_json", False))
        report_markdown = bool(getattr(artifacts, "report_markdown", False))
        material_manifest = bool(getattr(artifacts, "material_manifest", False))
        material_package = bool(getattr(artifacts, "material_package", False))
        has_report = report_json or report_markdown
        has_material_package = material_manifest or material_package
        satisfied = bool(
            (not final_docx or output_path)
            and (not component_id.endswith("_package") or has_material_package or has_report)
            and (final_docx or has_report or has_material_package)
        )
        if required and final_docx and not output_path:
            issues.append(
                JournalSubmissionPackageIssue(
                    component_id=component_id,
                    kind="missing_runtime_output",
                    severity="error",
                    expected="final docx output path",
                    message=f"Preset '{component_id}' did not produce a DOCX output path.",
                )
            )
        if required and not (has_report or has_material_package or output_path):
            issues.append(
                JournalSubmissionPackageIssue(
                    component_id=component_id,
                    kind="missing_artifact_contract",
                    severity="error",
                    expected="output/report/material artifact",
                    message=f"Preset '{component_id}' has no runtime artifact contract.",
                )
            )
        items.append(
            JournalSubmissionPackageItem(
                component_id=component_id,
                label=str(getattr(preset, "label", "") or component_id),
                required=required,
                preset_id=component_id,
                output_path=output_path,
                report_json=report_json,
                report_markdown=report_markdown,
                material_manifest=material_manifest,
                material_package=material_package,
                include_structured_intermediate=bool(
                    getattr(preset, "include_structured_intermediate", False)
                ),
                satisfied=satisfied,
            )
        )

    if "journal_citations" not in {
        str(value or "").strip()
        for value in list(getattr(getattr(config, "compliance_profile", None), "enabled_checks", []) or [])
    }:
        issues.append(
            JournalSubmissionPackageIssue(
                component_id="citation_source",
                kind="citation_source_check_not_declared",
                severity="warning",
                expected="journal_citations enabled check",
                message="Submission package should declare journal_citations evidence.",
            )
        )

    summary = JournalSubmissionPackageSummary(
        component_count=len(items),
        required_component_count=sum(1 for item in items if item.required),
        satisfied_required_count=sum(1 for item in items if item.required and item.satisfied),
        output_count=sum(1 for item in items if item.output_path),
        report_enabled_count=sum(1 for item in items if item.report_json or item.report_markdown),
        material_artifact_enabled_count=sum(
            1 for item in items if item.material_manifest or item.material_package
        ),
    )
    status = "error" if any(issue.severity == "error" for issue in issues) else "ok"
    if issues and status != "error":
        status = "warning"
    return JournalSubmissionPackageResult(
        family_id=family_id or JOURNAL_FAMILY_ID,
        status=status,
        default_delivery_preset_id=str(
            getattr(config, "default_delivery_preset_id", "") or ""
        ),
        summary=summary,
        items=tuple(items),
        issues=tuple(issues),
    )


def _ordered_component_ids(preset_by_id: Mapping[str, object]) -> tuple[str, ...]:
    result: list[str] = []
    for component_id in [*REQUIRED_PACKAGE_COMPONENTS, *OPTIONAL_PACKAGE_COMPONENTS]:
        if component_id not in result:
            result.append(component_id)
    return tuple(result)


def _config_material_schema_ids(config) -> tuple[str, ...]:
    profile = getattr(config, "input_source_profile", None)
    return resolve_material_schema_ids(
        str(getattr(profile, "material_schema_id", "") or "").strip(),
        list(getattr(profile, "material_schema_ids", []) or []),
    )


def _journal_family_for_schema_ids(schema_ids: tuple[str, ...]) -> str:
    for schema_id in schema_ids:
        try:
            family = get_material_schema(schema_id).family
        except KeyError:
            continue
        if family == JOURNAL_FAMILY_ID:
            return family
    return ""


def _is_journal_config(config, *, schema_ids: tuple[str, ...], family_id: str) -> bool:
    if family_id == JOURNAL_FAMILY_ID or any(schema_id in JOURNAL_SCHEMA_IDS for schema_id in schema_ids):
        return True
    compliance = getattr(config, "compliance_profile", None)
    profile_values = (
        getattr(compliance, "profile_id", ""),
        getattr(compliance, "rule_family", ""),
        getattr(compliance, "count_profile_id", ""),
    )
    return any("journal" in str(value or "").lower() for value in profile_values)


__all__ = [
    "JournalSubmissionPackageIssue",
    "JournalSubmissionPackageItem",
    "JournalSubmissionPackageResult",
    "JournalSubmissionPackageSummary",
    "inspect_journal_submission_package",
]
