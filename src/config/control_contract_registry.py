"""UI control contracts shared by template, scene, and workbench surfaces.

The scene matrix keeps boundary-sensitive parameters in one product language.
This registry records canonical controls, units, pairing, owners, and source
evidence so future scene controls do not drift back into template management.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ALLOWED_CONTROL_OWNER_LAYERS: tuple[str, ...] = (
    "template",
    "scene",
    "material",
    "output",
    "plugin",
)


@dataclass(frozen=True, slots=True)
class ControlContractEvidence:
    source_path: str
    markers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ControlContractEvidenceLocation:
    contract_id: str
    source_path: str
    marker: str
    line_number: int


@dataclass(frozen=True, slots=True)
class ControlContract:
    contract_id: str
    canonical_label: str
    owner_layer: str
    canonical_control: str
    parameter_paths: tuple[str, ...]
    unit_set: tuple[str, ...] = ()
    paired_contract_ids: tuple[str, ...] = ()
    disabled_state_rule: str = ""
    template_surface: str = ""
    scene_surface: str = ""
    workbench_surface: str = ""
    evidence: tuple[ControlContractEvidence, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ControlContractAuditResult:
    missing_required_contracts: tuple[str, ...] = ()
    invalid_owner_layers: tuple[tuple[str, str], ...] = ()
    missing_paired_contracts: tuple[tuple[str, str], ...] = ()
    missing_evidence_files: tuple[tuple[str, str], ...] = ()
    missing_evidence_markers: tuple[tuple[str, str, str], ...] = ()

    @property
    def is_clean(self) -> bool:
        return not (
            self.missing_required_contracts
            or self.invalid_owner_layers
            or self.missing_paired_contracts
            or self.missing_evidence_files
            or self.missing_evidence_markers
        )


def _evidence(source_path: str, *markers: str) -> ControlContractEvidence:
    return ControlContractEvidence(source_path=source_path, markers=tuple(markers))


def _contract(
    contract_id: str,
    canonical_label: str,
    owner_layer: str,
    canonical_control: str,
    parameter_paths: tuple[str, ...],
    *,
    unit_set: tuple[str, ...] = (),
    paired_contract_ids: tuple[str, ...] = (),
    disabled_state_rule: str = "",
    template_surface: str = "",
    scene_surface: str = "",
    workbench_surface: str = "",
    evidence: tuple[ControlContractEvidence, ...] = (),
    notes: str = "",
) -> ControlContract:
    return ControlContract(
        contract_id=contract_id,
        canonical_label=canonical_label,
        owner_layer=owner_layer,
        canonical_control=canonical_control,
        parameter_paths=parameter_paths,
        unit_set=unit_set,
        paired_contract_ids=paired_contract_ids,
        disabled_state_rule=disabled_state_rule,
        template_surface=template_surface,
        scene_surface=scene_surface,
        workbench_surface=workbench_surface,
        evidence=evidence,
        notes=notes,
    )


PARAGRAPH_INDENT_UNITS: tuple[str, ...] = ("chars", "pt", "cm")
PARAGRAPH_SPACING_UNITS: tuple[str, ...] = ("pt", "lines", "cm", "mm", "in", "auto")
LINE_SPACING_KINDS: tuple[str, ...] = (
    "exact",
    "single",
    "one_half",
    "double",
    "multiple",
)


CONTROL_CONTRACTS: tuple[ControlContract, ...] = (
    _contract(
        "body.font_cn",
        "中文字体",
        "template",
        "FontCombo(lang='cn')",
        ("template.styles.body.font_cn", "scene.section_styles.*.font_cn"),
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must reuse ParagraphStyleEditor FontCombo",
        evidence=(
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "self._font_cn = FontCombo",
                "style_field_layout_rows",
                '"font_cn": self._font_cn',
            ),
        ),
    ),
    _contract(
        "body.font_en",
        "英文字体",
        "template",
        "FontCombo(lang='en')",
        ("template.styles.body.font_en", "scene.section_styles.*.font_en"),
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must reuse ParagraphStyleEditor FontCombo",
        evidence=(
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "self._font_en = FontCombo",
                "style_field_layout_rows",
                '"font_en": self._font_en',
            ),
        ),
    ),
    _contract(
        "body.size_pt",
        "字号",
        "template",
        "SizeCombo",
        ("template.styles.body.size_pt", "scene.section_styles.*.size_pt"),
        unit_set=("pt", "word_named_size"),
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must reuse ParagraphStyleEditor SizeCombo",
        evidence=(
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "self._size_combo = SizeCombo",
                "style_field_layout_rows",
                '"size_pt": self._size_combo',
            ),
        ),
    ),
    _contract(
        "body.left_indent",
        "左缩进",
        "template",
        "IndentInput",
        (
            "template.styles.body.left_indent_chars",
            "template.styles.body.left_indent_unit",
            "scene.section_styles.*.left_indent_chars",
            "scene.section_styles.*.left_indent_unit",
        ),
        unit_set=PARAGRAPH_INDENT_UNITS,
        paired_contract_ids=("body.right_indent",),
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must show left/right indent on one row",
        evidence=(
            _evidence(
                "src/shared/ui/paragraph_style_inputs.py",
                "class IndentInput",
                "_INDENT_UNITS",
            ),
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "_left_indent = IndentInput",
                "style_field_layout_rows",
                '"left_indent": self._left_indent',
                '"right_indent": self._right_indent',
            ),
        ),
    ),
    _contract(
        "body.right_indent",
        "右缩进",
        "template",
        "IndentInput",
        (
            "template.styles.body.right_indent_chars",
            "template.styles.body.right_indent_unit",
            "scene.section_styles.*.right_indent_chars",
            "scene.section_styles.*.right_indent_unit",
        ),
        unit_set=PARAGRAPH_INDENT_UNITS,
        paired_contract_ids=("body.left_indent",),
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must show left/right indent on one row",
        evidence=(
            _evidence(
                "src/shared/ui/paragraph_style_inputs.py",
                "class IndentInput",
                "_INDENT_UNITS",
            ),
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "_right_indent = IndentInput",
                "style_field_layout_rows",
                '"left_indent": self._left_indent',
                '"right_indent": self._right_indent',
            ),
        ),
    ),
    _contract(
        "body.special_indent",
        "特殊缩进",
        "template",
        "SpecialIndentInput",
        (
            "template.styles.body.special_indent_mode",
            "template.styles.body.special_indent_value",
            "template.styles.body.special_indent_unit",
            "scene.section_styles.*.special_indent_mode",
            "scene.section_styles.*.special_indent_value",
            "scene.section_styles.*.special_indent_unit",
        ),
        unit_set=PARAGRAPH_INDENT_UNITS,
        disabled_state_rule="mode=none disables the value/unit editor and returns value 0",
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must expose none/first_line/hanging switching",
        evidence=(
            _evidence(
                "src/shared/ui/paragraph_style_inputs.py",
                "class SpecialIndentInput",
                "_SPECIAL_MODES",
                "_sync_enabled_state",
            ),
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "_special_indent = SpecialIndentInput",
                "style_field_layout_rows",
                '"special_indent": self._special_indent',
            ),
        ),
    ),
    _contract(
        "body.line_spacing",
        "行距",
        "template",
        "StyledComboBox + SpacingInput",
        (
            "template.styles.body.line_spacing_type",
            "template.styles.body.line_spacing_pt",
            "scene.section_styles.*.line_spacing_type",
            "scene.section_styles.*.line_spacing_pt",
        ),
        unit_set=LINE_SPACING_KINDS,
        disabled_state_rule="single/one_half/double lock the value editor; exact/multiple enable it",
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must keep line type/value as a coupled control",
        evidence=(
            _evidence(
                "src/config/style_semantics.py",
                "LINE_SPACING_OPTIONS",
                "line_spacing_is_editable",
            ),
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "_line_type_combo = StyledComboBox",
                "_line_value = SpacingInput",
                "style_field_layout_rows",
                '"line_spacing_pt"',
            ),
        ),
    ),
    _contract(
        "body.space_before",
        "段前",
        "template",
        "SpacingInput",
        (
            "template.styles.body.space_before_pt",
            "template.styles.body.space_before_unit",
            "scene.section_styles.*.space_before_pt",
            "scene.section_styles.*.space_before_unit",
        ),
        unit_set=PARAGRAPH_SPACING_UNITS,
        paired_contract_ids=("body.space_after",),
        disabled_state_rule="unit=auto disables numeric editing",
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must show before/after spacing on one row",
        evidence=(
            _evidence("src/shared/ui/spacing_input.py", "class SpacingInput"),
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "_space_before = SpacingInput",
                "style_field_layout_rows",
                '"space_before": self._space_before',
                '"space_after": self._space_after',
            ),
        ),
    ),
    _contract(
        "body.space_after",
        "段后",
        "template",
        "SpacingInput",
        (
            "template.styles.body.space_after_pt",
            "template.styles.body.space_after_unit",
            "scene.section_styles.*.space_after_pt",
            "scene.section_styles.*.space_after_unit",
        ),
        unit_set=PARAGRAPH_SPACING_UNITS,
        paired_contract_ids=("body.space_before",),
        disabled_state_rule="unit=auto disables numeric editing",
        template_surface="TemplatePanel StyleDetail",
        scene_surface="scene style override must show before/after spacing on one row",
        evidence=(
            _evidence("src/shared/ui/spacing_input.py", "class SpacingInput"),
            _evidence(
                "src/shared/ui/paragraph_style_editor.py",
                "_space_after = SpacingInput",
                "style_field_layout_rows",
                '"space_before": self._space_before',
                '"space_after": self._space_after',
            ),
        ),
    ),
    _contract(
        "fixed_layout.table_row_height",
        "固定版位行高",
        "scene",
        "FixedLayoutRowHeightPolicy + OOXML helper",
        ("form_batch_documents.table.row_height_pt", "word.w:trHeight"),
        unit_set=("pt", "twips"),
        disabled_state_rule="only enabled for fixed-layout form/certificate/quote profiles",
        template_surface="not_generic_template",
        scene_surface="form_batch_documents fixed-layout row-height policy",
        workbench_surface="fixed-layout policy/report",
        evidence=(
            _evidence(
                "src/config/fixed_layout.py",
                "FixedLayoutRowHeightPolicy",
                "form_batch_documents.table.row_height_pt",
            ),
            _evidence(
                "src/shared/engine/fixed_layout_tables.py",
                "apply_fixed_layout_row_height_policy",
                "w:trHeight",
            ),
            _evidence(
                "src/config/scene_coverage_manifest.py",
                "form_batch_documents",
                "w:trHeight",
            ),
            _evidence(
                "tests/test_table_format_semantics.py",
                "test_table_config_no_longer_exposes_legacy_row_height_setting",
                "row_height_pt",
            ),
        ),
        notes="Keeps row height out of generic TableConfig while reserving it for fixed-layout scenes.",
    ),
    _contract(
        "scene.formula_conversion_strategy",
        "公式策略",
        "scene",
        "scene policy + workbench/runtime gate",
        (
            "scene.formula_convert.output_mode",
            "scene.formula_convert.low_confidence_policy",
            "scene.formula_convert.office_fallback_enabled",
            "scene.formula_style.unify_font",
            "scene.formula_style.unify_size",
            "scene.formula_style.unify_spacing",
        ),
        unit_set=("word_native", "image_fallback", "keep_source", "manual_review"),
        disabled_state_rule=(
            "full LaTeX projects and professional conversion quality remain plugin/manual gated"
        ),
        template_surface="formula visual typography still follows template-owned controls",
        scene_surface="scene preset/workbench formula conversion policy",
        workbench_surface="formula confidence and import-boundary evidence",
        evidence=(
            _evidence(
                "src/config/scene_parameter_ownership.py",
                "formula_convert.output_mode",
                "formula_style.unify_font",
            ),
            _evidence(
                "src/config/scene.py",
                "class FormulaConvertOptions",
                "low_confidence_policy",
                "office_fallback_enabled",
            ),
            _evidence(
                "src/config/plugin_manual_gate.py",
                "full_latex_project_conversion",
                "confidence_report_required=True",
            ),
        ),
        notes=(
            "Scene owns conversion and confidence policy; font/size/spacing controls "
            "must stay aligned with template formula controls."
        ),
    ),
    _contract(
        "scene.watermark_status",
        "水印状态",
        "scene",
        "ToggleSwitch + QLineEdit(template input contract)",
        (
            "scene.watermark.enabled",
            "scene.watermark.text",
            "scene.watermark.color",
            "scene.watermark.rotation",
            "scene.watermark.font_size",
        ),
        disabled_state_rule="enabled=false disables the status-text editor without clearing text",
        template_surface="watermark visual baseline belongs to template/control contract",
        scene_surface="ScenePanel content watermark enabled/text controls",
        workbench_surface="official/internal/archive delivery status report",
        evidence=(
            _evidence(
                "src/config/scene_parameter_ownership.py",
                "watermark.enabled",
                "watermark.text",
            ),
            _evidence(
                "src/ui/panels/scene_panel.py",
                "_watermark_enabled",
                "_watermark_text",
                '"水印文本"',
                "_sync_watermark_text_state",
            ),
            _evidence(
                "src/config/scene_family_application.py",
                "scene.watermark.enabled = True",
                'scene.watermark.text = "内部传阅"',
            ),
        ),
        notes="Scene owns watermark business/status text; color, angle, and size remain visual baseline concerns.",
    ),
    _contract(
        "material.schema_selection",
        "资料 Schema",
        "material",
        "StyledComboBox + QLineEdit(template input contract) + action buttons",
        (
            "scene.input_source_profile.material_schema_id",
            "scene.input_source_profile.material_schema_ids",
            "material_schema_registry.*",
        ),
        disabled_state_rule="unknown schema enables replace/remove actions; registered schema enables set/append",
        scene_surface="ScenePanel content material schema registry tools",
        workbench_surface="AssetsPanel/Workbench material repair target",
        evidence=(
            _evidence(
                "src/config/material_schema_registry.py",
                "class MaterialSchema",
                "resolve_material_schema_ids",
                "missing_material_schema_ids",
            ),
            _evidence(
                "src/ui/panels/scene_panel.py",
                "_schema_registry_combo",
                "_material_schema_id",
                "_set_primary_schema_btn",
                "_append_schema_btn",
                "_replace_unknown_schema_btn",
            ),
            _evidence(
                "src/ui/panels/scene_material_requirement_block.py",
                "class _MaterialRequirementBlock",
                "def sync_actions",
                "def _build_material_schema_validation_items",
            ),
            _evidence(
                "src/ui/adapters/workbench_execution_adapter.py",
                "material_schema_readiness_reasons",
                "missing_material_schema_ids",
            ),
        ),
        notes="Material schemas are fact-source contracts, not formatting presets.",
    ),
    _contract(
        "output.delivery_preset",
        "输出版本",
        "output",
        "StyledComboBox + preset editor + artifact toggles",
        (
            "scene.default_delivery_preset_id",
            "scene.delivery_presets.*",
            "scene.output.*",
        ),
        disabled_state_rule="family defaults button is enabled only when a planned family has delivery defaults",
        scene_surface="ScenePanel scene rules generated-result editor",
        workbench_surface="Workbench delivery target groups and artifact browser",
        evidence=(
            _evidence(
                "src/config/scene.py",
                "class DeliveryPreset",
                "default_delivery_preset_id",
            ),
            _evidence(
                "src/ui/panels/scene_panel.py",
                "_default_delivery = StyledComboBox",
                "_apply_family_delivery_btn",
                "_delivery_summary",
            ),
            _evidence(
                "src/ui/panels/scene_delivery_helpers.py",
                "_DELIVERY_PRESET_TEMPLATE_MAP",
                "_populate_delivery_preset_template_combo",
                "_scene_family_delivery_preview_tooltip",
            ),
            _evidence(
                "src/ui/panels/workbench/execution_runtime.py",
                "_uses_delivery_presets",
                "_write_delivery_reports",
                "_delivery_preset_payload",
            ),
        ),
        notes="Business versions are DeliveryPreset objects; loose output toggles remain artifact-level details.",
    ),
    _contract(
        "output.content_visibility_rules",
        "内容显隐",
        "output",
        "TextArea + StyledComboBox + insert action",
        (
            "scene.delivery_presets.*.content_visibility_rules",
            "ContentVisibilityRule.selector",
            "ContentVisibilityRule.action",
        ),
        disabled_state_rule="rules belong to the selected delivery preset and update with preset selection",
        scene_surface="ScenePanel scene rules generated-result visibility editor",
        workbench_surface="content visibility engine and delivery intermediate payload",
        evidence=(
            _evidence(
                "src/config/scene.py",
                "class ContentVisibilityRule",
                "content_visibility_rules",
            ),
            _evidence(
                "src/ui/panels/scene_panel.py",
                "_visibility_selector_input",
                "_visibility_action_combo",
                "_insert_visibility_rule_btn",
            ),
            _evidence(
                "src/ui/panels/scene_delivery_helpers.py",
                "def _parse_visibility_rules",
                "def _append_visibility_rule_text",
                "_VISIBILITY_ACTION_OPTIONS",
            ),
            _evidence(
                "src/shared/engine/content_visibility.py",
                "content_visibility_rules",
                "selector",
                "action",
            ),
        ),
        notes="Role/version output must use structured visibility rules, not ad hoc hidden text promises.",
    ),
    _contract(
        "plugin.manual_gate",
        "插件人工确认",
        "plugin",
        "Workbench issue + manual confirmation payload",
        (
            "plugin_manual_gate.*",
            "coverage_pack.plugin_boundary",
            "WorkbenchIssueItem.repair_target_type=plugin_manual_gate",
        ),
        disabled_state_rule="high-risk import/professional work blocks or warns until manual confirmation/plugin handoff",
        scene_surface="coverage pack plugin boundary projection",
        workbench_surface="Workbench issue queue plugin_manual_gate repair target",
        evidence=(
            _evidence(
                "src/config/plugin_manual_gate.py",
                "class PluginManualGate",
                "PLUGIN_MANUAL_GATES",
                "plugin_manual_gate_payload",
            ),
            _evidence(
                "src/ui/adapters/workbench_execution_adapter.py",
                "plugin_manual_gate_for_pack",
                "repair_target_type",
                "plugin_manual_gate",
            ),
            _evidence(
                "src/report_writer.py",
                "_clean_plugin_manual_gate",
                "plugin_manual_gate",
            ),
        ),
        notes="AI/OCR/PDF/LaTeX and professional judgments must not masquerade as core scene controls.",
    ),
)


CONTROL_CONTRACT_MAP: dict[str, ControlContract] = {
    contract.contract_id: contract for contract in CONTROL_CONTRACTS
}

REQUIRED_CONTROL_CONTRACT_IDS: tuple[str, ...] = (
    "body.font_cn",
    "body.font_en",
    "body.size_pt",
    "body.left_indent",
    "body.right_indent",
    "body.special_indent",
    "body.line_spacing",
    "body.space_before",
    "body.space_after",
    "fixed_layout.table_row_height",
    "scene.formula_conversion_strategy",
    "scene.watermark_status",
    "material.schema_selection",
    "output.delivery_preset",
    "output.content_visibility_rules",
    "plugin.manual_gate",
)


def list_control_contracts() -> tuple[ControlContract, ...]:
    return CONTROL_CONTRACTS


def get_control_contract(contract_id: str) -> ControlContract:
    normalized = str(contract_id or "").strip()
    try:
        return CONTROL_CONTRACT_MAP[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown control contract: {contract_id}") from exc


def resolve_control_contract_evidence_locations(
    contract_id: str,
    *,
    project_root: Path | None = None,
) -> tuple[ControlContractEvidenceLocation, ...]:
    contract = get_control_contract(contract_id)
    root = project_root or Path(__file__).resolve().parents[2]
    locations: list[ControlContractEvidenceLocation] = []
    for evidence in contract.evidence:
        source_path = str(evidence.source_path or "").strip()
        if not source_path:
            continue
        evidence_path = root / source_path
        lines: list[str] = []
        if evidence_path.exists():
            lines = evidence_path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).splitlines()
        for marker in evidence.markers:
            normalized_marker = str(marker or "").strip()
            if not normalized_marker:
                continue
            locations.append(
                ControlContractEvidenceLocation(
                    contract_id=contract.contract_id,
                    source_path=source_path,
                    marker=normalized_marker,
                    line_number=_first_marker_line(lines, normalized_marker),
                )
            )
    return tuple(locations)


def audit_control_contract_registry(
    *,
    project_root: Path | None = None,
) -> ControlContractAuditResult:
    root = project_root or Path(__file__).resolve().parents[2]
    contract_ids = set(CONTROL_CONTRACT_MAP)
    missing_required = tuple(
        contract_id
        for contract_id in REQUIRED_CONTROL_CONTRACT_IDS
        if contract_id not in contract_ids
    )
    invalid_owner_layers = tuple(
        sorted(
            (
                (contract.contract_id, contract.owner_layer)
                for contract in CONTROL_CONTRACTS
                if contract.owner_layer not in ALLOWED_CONTROL_OWNER_LAYERS
            ),
            key=lambda item: item[0],
        )
    )
    missing_paired_contracts: list[tuple[str, str]] = []
    missing_evidence_files: list[tuple[str, str]] = []
    missing_evidence_markers: list[tuple[str, str, str]] = []

    for contract in CONTROL_CONTRACTS:
        for paired_id in contract.paired_contract_ids:
            if paired_id not in contract_ids:
                missing_paired_contracts.append((contract.contract_id, paired_id))
                continue
            paired = CONTROL_CONTRACT_MAP[paired_id]
            if contract.contract_id not in paired.paired_contract_ids:
                missing_paired_contracts.append((paired_id, contract.contract_id))
        for evidence in contract.evidence:
            evidence_path = root / evidence.source_path
            if not evidence_path.exists():
                missing_evidence_files.append((contract.contract_id, evidence.source_path))
                continue
            content = evidence_path.read_text(encoding="utf-8", errors="ignore")
            for marker in evidence.markers:
                if marker not in content:
                    missing_evidence_markers.append(
                        (contract.contract_id, evidence.source_path, marker)
                    )

    return ControlContractAuditResult(
        missing_required_contracts=missing_required,
        invalid_owner_layers=invalid_owner_layers,
        missing_paired_contracts=tuple(sorted(set(missing_paired_contracts))),
        missing_evidence_files=tuple(sorted(missing_evidence_files)),
        missing_evidence_markers=tuple(sorted(missing_evidence_markers)),
    )


def build_control_contract_summary(contract: ControlContract) -> str:
    units = "/".join(contract.unit_set) if contract.unit_set else "-"
    pairs = "/".join(contract.paired_contract_ids) if contract.paired_contract_ids else "-"
    return (
        f"{contract.contract_id} [{contract.owner_layer}] -> "
        f"{contract.canonical_control}; label={contract.canonical_label}; "
        f"units={units}; pairs={pairs}"
    )


def _first_marker_line(lines: list[str], marker: str) -> int:
    for index, line in enumerate(lines, start=1):
        if marker in line:
            return index
    return 0


__all__ = [
    "ALLOWED_CONTROL_OWNER_LAYERS",
    "CONTROL_CONTRACT_MAP",
    "CONTROL_CONTRACTS",
    "ControlContract",
    "ControlContractAuditResult",
    "ControlContractEvidence",
    "ControlContractEvidenceLocation",
    "REQUIRED_CONTROL_CONTRACT_IDS",
    "audit_control_contract_registry",
    "build_control_contract_summary",
    "get_control_contract",
    "list_control_contracts",
    "resolve_control_contract_evidence_locations",
]
