"""Plugin/manual gate registry for high-risk import and professional workflows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PluginManualGate:
    """Planning contract for workflows that must not run as silent core formatting."""

    gate_id: str
    pack_id: str
    label: str
    plugin_entry_id: str
    plugin_entry_label: str
    manual_confirmation_required: bool = True
    confidence_report_required: bool = False
    boundary_report_required: bool = True
    blocks_core_execution_until_confirmed: bool = True
    professional_review_required: bool = False
    risk_domain_ids: tuple[str, ...] = ()
    accepted_inputs: tuple[str, ...] = ()
    unsupported_core_inputs: tuple[str, ...] = ()
    confirmation_scope: tuple[str, ...] = ()
    confirmation_decision_states: tuple[str, ...] = (
        "accepted",
        "rejected",
        "needs_plugin_handoff",
    )
    report_fields: tuple[str, ...] = ()
    blocking_family_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "pack_id": self.pack_id,
            "label": self.label,
            "plugin_entry_id": self.plugin_entry_id,
            "plugin_entry_label": self.plugin_entry_label,
            "manual_confirmation_required": self.manual_confirmation_required,
            "confidence_report_required": self.confidence_report_required,
            "boundary_report_required": self.boundary_report_required,
            "blocks_core_execution_until_confirmed": (
                self.blocks_core_execution_until_confirmed
            ),
            "professional_review_required": self.professional_review_required,
            "risk_domain_ids": list(self.risk_domain_ids),
            "accepted_inputs": list(self.accepted_inputs),
            "unsupported_core_inputs": list(self.unsupported_core_inputs),
            "confirmation_scope": list(self.confirmation_scope),
            "confirmation_decision_states": list(
                self.confirmation_decision_states
            ),
            "report_fields": list(self.report_fields),
            "blocking_family_ids": list(self.blocking_family_ids),
        }


PLUGIN_MANUAL_GATES: tuple[PluginManualGate, ...] = (
    PluginManualGate(
        gate_id="journal_publisher_rule_review_gate",
        pack_id="english_journal",
        label="Journal publisher rule and final-layout gate",
        plugin_entry_id="journal_publisher_rule_review_plugin",
        plugin_entry_label="Journal publisher rule / final-layout review plugin",
        confidence_report_required=False,
        risk_domain_ids=(
            "publisher_final_layout",
            "unreviewed_journal_rules",
            "citation_source_integrity",
        ),
        accepted_inputs=("publisher_guidelines", "bibtex", "csl_json", "response_letter"),
        unsupported_core_inputs=(
            "publisher_final_layout_guarantee",
            "unreviewed_rule_fetching",
            "citation_source_truthfulness",
        ),
        confirmation_scope=(
            "target journal rules reviewed",
            "citation source completeness accepted",
            "publisher-final layout remains outside core formatting",
        ),
        report_fields=(
            "target_journal",
            "rule_review_status",
            "citation_source_status",
            "manual_decision",
        ),
    ),
    PluginManualGate(
        gate_id="exam_ai_complex_diagram_gate",
        pack_id="exam_education",
        label="Exam AI quality and complex diagram gate",
        plugin_entry_id="exam_ai_quality_diagram_plugin",
        plugin_entry_label="Exam AI quality / complex diagram plugin",
        confidence_report_required=True,
        risk_domain_ids=(
            "ai_content_quality",
            "complex_diagram_generation",
        ),
        accepted_inputs=("ai_generated_questions", "complex_diagram_assets"),
        unsupported_core_inputs=("ai_quality_judgment", "geometry_diagram_generation"),
        confirmation_scope=(
            "question correctness",
            "answer completeness",
            "complex diagram fidelity",
        ),
        report_fields=("confidence_level", "unsupported_diagrams", "manual_decision"),
    ),
    PluginManualGate(
        gate_id="professional_disclosure_review_gate",
        pack_id="professional_disclosure",
        label="Professional disclosure review gate",
        plugin_entry_id="professional_disclosure_review_plugin",
        plugin_entry_label="Audit/legal/patent/finance/translation review plugin",
        professional_review_required=True,
        risk_domain_ids=(
            "audit_assurance",
            "legal_opinion",
            "financial_assurance",
            "ip_patent_quality",
            "medical_regulatory",
            "translation_quality",
        ),
        accepted_inputs=(
            "audit_disclosure",
            "legal_disclosure",
            "medical_regulatory_submission",
            "patent_draft",
            "finance_quote",
            "translation_review",
        ),
        unsupported_core_inputs=(
            "audit_opinion",
            "legal_conclusion",
            "medical_or_drug_regulatory_conclusion",
            "patentability_judgment",
            "financial_assurance",
            "translation_quality_judgment",
        ),
        confirmation_scope=(
            "professional boundary accepted",
            "review responsibility assigned",
            "archive package does not equal compliance proof",
        ),
        report_fields=("boundary_text", "review_owner", "manual_decision"),
        blocking_family_ids=(
            "finance_quote_documents",
            "ip_patent_documents",
            "bilingual_translation_documents",
            "regulated_disclosure_documents",
        ),
    ),
    PluginManualGate(
        gate_id="import_ai_conversion_gate",
        pack_id="import_ai_boundary",
        label="Import and AI conversion gate",
        plugin_entry_id="import_ai_assistant_plugin",
        plugin_entry_label="OCR/PDF/LaTeX/AI import assistant plugin",
        confidence_report_required=True,
        risk_domain_ids=(
            "ocr_confidence",
            "pdf_conversion",
            "full_latex_conversion",
            "ai_content_quality",
            "complex_diagram_generation",
        ),
        accepted_inputs=("ocr", "pdf", "latex", "ai_generated_content", "complex_diagram"),
        unsupported_core_inputs=(
            "lossless_pdf_to_word",
            "full_latex_project_conversion",
            "ocr_truthfulness",
            "ai_content_quality",
        ),
        confirmation_scope=(
            "confidence report reviewed",
            "low-confidence regions accepted or repaired",
            "core execution approved after import",
        ),
        report_fields=(
            "source_type",
            "confidence_level",
            "low_confidence_regions",
            "manual_decision",
            "handoff_pack_id",
            "handoff_family_id",
            "handoff_status",
            "fallback_strategy",
        ),
    ),
)

PLUGIN_MANUAL_GATE_MAP: dict[str, PluginManualGate] = {
    gate.pack_id: gate for gate in PLUGIN_MANUAL_GATES
}


def get_plugin_manual_gate(pack_id: str) -> PluginManualGate:
    normalized = str(pack_id or "").strip()
    try:
        return PLUGIN_MANUAL_GATE_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown plugin/manual gate for pack: {pack_id}") from exc


def plugin_manual_gate_for_pack(pack_id: str) -> PluginManualGate | None:
    return PLUGIN_MANUAL_GATE_MAP.get(str(pack_id or "").strip())


def plugin_manual_gate_payload(pack_id: str) -> dict[str, object]:
    gate = plugin_manual_gate_for_pack(pack_id)
    return gate.to_payload() if gate is not None else {}


def list_plugin_manual_gates() -> tuple[PluginManualGate, ...]:
    return PLUGIN_MANUAL_GATES


def plugin_manual_gate_execution_issue(config: object) -> str:
    """Return the exact whole-family gate that blocks core execution.

    Coverage-pack membership is intentionally insufficient: journal and exam
    gates apply only to high-risk sub-workflows.  A whole-family block is
    activated solely by the canonical compliance ``rule_family`` explicitly
    listed on a gate.  Until a verifiable external-receipt contract exists,
    there is deliberately no boolean confirmation escape hatch here.
    """

    compliance = getattr(config, "compliance_profile", None)
    family_id = str(getattr(compliance, "rule_family", "") or "").strip()
    if not family_id:
        return ""
    for gate in PLUGIN_MANUAL_GATES:
        if (
            gate.blocks_core_execution_until_confirmed
            and family_id in gate.blocking_family_ids
        ):
            return (
                "plugin_manual_gate_required:"
                f"{gate.gate_id}:{family_id}:verified_external_receipt_missing"
            )
    return ""


__all__ = [
    "PLUGIN_MANUAL_GATE_MAP",
    "PLUGIN_MANUAL_GATES",
    "PluginManualGate",
    "get_plugin_manual_gate",
    "list_plugin_manual_gates",
    "plugin_manual_gate_execution_issue",
    "plugin_manual_gate_for_pack",
    "plugin_manual_gate_payload",
]
