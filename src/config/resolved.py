"""
ResolvedConfig ? merged configuration consumed by modules.

Modules should only read ResolvedConfig and never reach back into
TemplateConfig / SceneWorkspace directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config.template import (
    PageSetupConfig,
    StyleConfig,
    HeadingNumberingConfig,
    HeadingModelConfig,
    TocConfig,
    CaptionConfig,
    TableConfig,
    SectionConfig,
    HeaderFooterConfig,
    WatermarkConfig,
    ReferenceStyleConfig,
    FormulaTableConfig,
    FormulaStyleConfig,
    EquationNumberingConfig,
)
from src.config.feature_configs import OutputConfig, disabled_output_config
from src.config.document_scope import DocumentScopePolicy
from src.config.scene import (
    ExamPaperConfig,
    MdCleanupOptions,
    WhitespaceOptions,
    CitationLinkOptions,
    FormulaConvertOptions,
    ChemTypographyOptions,
    InputSourceProfile,
    ComplianceProfile,
    DeliveryPreset,
)


@dataclass(slots=True)
class ReplacementRule:
    """Runtime replacement rule for placeholder_replace."""

    old: str = ""
    new: str = ""


@dataclass(slots=True)
class ImageInsertionItem:
    """Runtime image insertion payload for image_insertion."""

    path: str = ""
    position: int | str = "end"
    width_cm: float = 14.0
    role: str = ""
    item_id: str = ""
    group_id: str = ""
    sequence: int | None = None
    normalized_name: str = ""


@dataclass
class ConfigValue:
    """Value with provenance metadata."""

    value: Any
    source: str                     # "template" | "scene" | "session"
    template_default: Any = None

    @property
    def is_overridden(self) -> bool:
        return self.source != "template"

    def reset(self) -> "ConfigValue":
        return ConfigValue(
            value=self.template_default,
            source="template",
            template_default=self.template_default,
        )


@dataclass
class ResolvedConfig:
    """Fully merged configuration and runtime payloads."""

    page_setup: PageSetupConfig = field(default_factory=PageSetupConfig)
    styles: dict[str, StyleConfig] = field(default_factory=dict)
    heading_numbering: HeadingNumberingConfig = field(default_factory=HeadingNumberingConfig)
    heading_model: HeadingModelConfig = field(default_factory=HeadingModelConfig)
    toc: TocConfig = field(default_factory=TocConfig)
    caption: CaptionConfig = field(default_factory=CaptionConfig)
    table: TableConfig = field(default_factory=TableConfig)
    section: SectionConfig = field(default_factory=SectionConfig)
    header_footer: HeaderFooterConfig = field(default_factory=HeaderFooterConfig)
    watermark: WatermarkConfig = field(default_factory=WatermarkConfig)
    reference_style: ReferenceStyleConfig = field(default_factory=ReferenceStyleConfig)
    formula_table: FormulaTableConfig = field(default_factory=FormulaTableConfig)
    formula_style: FormulaStyleConfig = field(default_factory=FormulaStyleConfig)
    equation_numbering: EquationNumberingConfig = field(default_factory=EquationNumberingConfig)
    output: OutputConfig = field(default_factory=disabled_output_config)

    module_switches: dict[str, bool] = field(default_factory=dict)
    mode_id: str = "custom"
    document_scope: DocumentScopePolicy = field(default_factory=DocumentScopePolicy)
    strict_mode: bool = True

    md_cleanup: MdCleanupOptions = field(default_factory=MdCleanupOptions)
    whitespace: WhitespaceOptions = field(default_factory=WhitespaceOptions)
    citation_link: CitationLinkOptions = field(default_factory=CitationLinkOptions)
    formula_convert: FormulaConvertOptions = field(default_factory=FormulaConvertOptions)
    chem_typography: ChemTypographyOptions = field(default_factory=ChemTypographyOptions)
    input_source_profile: InputSourceProfile = field(default_factory=InputSourceProfile)
    compliance_profile: ComplianceProfile = field(default_factory=ComplianceProfile)
    default_delivery_preset_id: str = ""
    delivery_presets: list[DeliveryPreset] = field(default_factory=list)
    exam_paper: ExamPaperConfig | None = None

    entity_data: dict[str, str] = field(default_factory=dict)
    field_scopes: dict[str, str] = field(default_factory=dict)
    field_aliases: dict[str, str] = field(default_factory=dict)
    timeline_field_keys: tuple[str, ...] = ()
    entity_assets_dir: str = ""
    images: list[ImageInsertionItem] = field(default_factory=list)
    replacements: list[ReplacementRule] = field(default_factory=list)
    exact_material_placeholders: bool = False

    _provenance: dict[str, ConfigValue] = field(default_factory=dict)

    def get_with_source(self, key: str) -> ConfigValue | None:
        return self._provenance.get(key)

    def list_overrides(self) -> list[str]:
        return [k for k, v in self._provenance.items() if v.is_overridden]

    def is_module_enabled(self, module_name: str) -> bool:
        return self.module_switches.get(module_name, False)
