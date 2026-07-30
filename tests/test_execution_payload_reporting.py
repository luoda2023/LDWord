from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from src.reporting.execution_payload import (
    application_section_word_limits_payload,
    content_visibility_preview_payload,
    content_visibility_receipts_payload,
    content_visibility_scan_payload,
    diagnostics_payload,
    document_scope_payload,
    journal_submission_package_payload,
    official_document_assembly_payload,
    official_numbering_preservation_payload,
    output_target_preflight_payload,
    plain_data,
    technical_chapter_inventory_payload,
)


@dataclass
class _NestedEvidence:
    value: str


@pytest.mark.parametrize(
    ("attribute", "projector"),
    [
        ("journal_submission_package", journal_submission_package_payload),
        ("official_document_assembly", official_document_assembly_payload),
        ("official_numbering_preservation", official_numbering_preservation_payload),
        ("technical_chapter_inventory", technical_chapter_inventory_payload),
        ("application_section_word_limits", application_section_word_limits_payload),
    ],
)
def test_context_evidence_projectors_preserve_nested_plain_data(attribute, projector):
    evidence = {"status": "ok", "nested": _NestedEvidence("kept")}
    result = SimpleNamespace(context=SimpleNamespace(**{attribute: evidence}))

    assert projector(result) == {"status": "ok", "nested": {"value": "kept"}}

    setattr(result.context, attribute, {"status": "not_applicable"})
    assert projector(result) == {}


def test_visibility_and_output_preflight_projectors_keep_computed_contract_fields():
    @dataclass
    class _Scan:
        selectors: list[str]

        @property
        def has_issues(self) -> bool:
            return True

        def issue_messages(self) -> tuple[str, ...]:
            return ("missing answer marker",)

    @dataclass
    class _Preview:
        preset_id: str

    @dataclass
    class _Preflight:
        targets: list[str]

        @property
        def has_issues(self) -> bool:
            return True

        @property
        def issue_count(self) -> int:
            return 2

        @property
        def has_errors(self) -> bool:
            return True

        @property
        def error_count(self) -> int:
            return 1

    context = SimpleNamespace(
        content_visibility_scan=_Scan(["answer"]),
        content_visibility_preview=[_Preview("student")],
        content_visibility_receipts={"student": _NestedEvidence("receipt")},
        output_target_preflight=_Preflight(["student"]),
    )
    result = SimpleNamespace(context=context)

    assert content_visibility_scan_payload(result) == {
        "selectors": ["answer"],
        "has_issues": True,
        "issue_messages": ["missing answer marker"],
    }
    assert content_visibility_preview_payload(result) == [{"preset_id": "student"}]
    assert content_visibility_receipts_payload(result) == {
        "student": {"value": "receipt"}
    }
    assert output_target_preflight_payload(result) == {
        "targets": ["student"],
        "has_issues": True,
        "issue_count": 2,
        "has_errors": True,
        "error_count": 1,
    }


def test_diagnostics_and_plain_data_projectors_are_pure_for_extra_evidence():
    diagnostic = {"level": "warning", "reason": "review required"}

    payload = diagnostics_payload(None, [diagnostic])

    assert payload["count"] == 1
    assert payload["items"] == [diagnostic]
    assert "review required" in str(payload["summary"])
    assert plain_data((_NestedEvidence("a"), _NestedEvidence("b"))) == [
        {"value": "a"},
        {"value": "b"},
    ]


def test_document_scope_payload_is_one_compact_receipt():
    receipt = {
        "plan_mode": "body",
        "detected_region_count": 4,
        "effective_region_count": 1,
        "confirmation_status": "user_confirmed",
        "corrected_region_count": 1,
        "skipped_uncertain_count": 0,
    }
    result = SimpleNamespace(
        context=SimpleNamespace(document_scope_receipt=receipt)
    )

    assert document_scope_payload(result) == receipt
