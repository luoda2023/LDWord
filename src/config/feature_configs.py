"""
Feature-specific configuration dataclasses.

These configs are shared by template, scene, loader, resolver, and runtime
modules. Some of them are still referenced from SceneWorkspace today, but the
page-number model is being migrated toward template ownership.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_FRONT_PHASE_ID = "front"
_BODY_PHASE_ID = "body"
_FRONT_PHASE_SELECTORS = ("front_matter",)
_BODY_PHASE_SELECTORS = ("body", "back_matter")
_DEFAULT_SUPPRESS_HEADER_FOOTER_SELECTORS = ("pre_numbering",)


@dataclass
class HeaderFooterTypographyConfig:
    font_cn: str | None = None
    font_en: str | None = None
    size_pt: float | None = None
    bold: bool = False
    italic: bool = False


@dataclass
class HeaderFooterBorderConfig:
    enabled: bool = True
    line_style: str = "single"
    width_pt: float = 0.5
    spacing_pt: float = 1.0
    color: str = "auto"


@dataclass
class HeaderFooterBehaviorConfig:
    different_first_page: bool = False
    different_odd_even_pages: bool = False
    link_to_previous: str = "never"         # "never" | "always" | "preserve"
    preserve_existing_content: bool = False


@dataclass
class HeaderFooterContentConfig:
    mode: str = "inherit"                  # "inherit" | "none" | "fixed" | "styleref" | "page_number" | "page_number_with_text" | "template" | "preserve"
    fixed_text: str = ""
    template: str = ""
    alignment: str = "center"              # "left" | "center" | "right" | "inside" | "outside"
    styleref_level: int = 1
    styleref_style: str = ""
    styleref_include_number: bool = True


@dataclass
class HeaderFooterVariantConfig:
    header: HeaderFooterContentConfig = field(default_factory=HeaderFooterContentConfig)
    footer: HeaderFooterContentConfig = field(default_factory=HeaderFooterContentConfig)


def _empty_header_footer_variant() -> HeaderFooterVariantConfig:
    return HeaderFooterVariantConfig(
        header=HeaderFooterContentConfig(mode="none"),
        footer=HeaderFooterContentConfig(mode="none"),
    )


@dataclass
class HeaderFooterVariantsConfig:
    default: HeaderFooterVariantConfig = field(default_factory=HeaderFooterVariantConfig)
    first: HeaderFooterVariantConfig = field(default_factory=_empty_header_footer_variant)
    even: HeaderFooterVariantConfig = field(default_factory=HeaderFooterVariantConfig)


@dataclass
class HeaderConfig:
    enabled: bool = True
    mode: str = "styleref"          # "styleref" | "fixed" | "none"
    fixed_text: str = ""
    alignment: str = "center"       # "left" | "center" | "right"
    styleref_level: int = 1
    border: bool = True
    border_style: HeaderFooterBorderConfig = field(default_factory=HeaderFooterBorderConfig)
    hide_on_cover: bool = True
    typography: HeaderFooterTypographyConfig = field(
        default_factory=HeaderFooterTypographyConfig
    )


@dataclass
class FooterConfig:
    enabled: bool = True
    content_mode: str = "page_number"   # "page_number" | "fixed" | "page_number_with_text" | "none"
    fixed_text: str = ""
    alignment: str = "center"           # "left" | "center" | "right"
    page_number_template: str = "{page}"
    hide_on_cover: bool = True
    typography: HeaderFooterTypographyConfig = field(
        default_factory=HeaderFooterTypographyConfig
    )


@dataclass
class PageNumberPhaseConfig:
    phase_id: str = ""
    selectors: list[str] = field(default_factory=list)
    visible: bool = True
    number_format: str = "decimal"      # Word w:pgNumType/@w:fmt, e.g. "decimal" | "upperRoman" | "lowerRoman"
    start_mode: str = "continue"        # "continue" | "restart"
    start_value: int = 1


def default_continuous_page_number_phases() -> list[PageNumberPhaseConfig]:
    """Return the product default page-number plan for generic templates."""

    return [
        PageNumberPhaseConfig(
            phase_id="main",
            selectors=["all_numbered_content"],
            visible=True,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        )
    ]


@dataclass
class PageNumberPlanConfig:
    phases: list[PageNumberPhaseConfig] = field(default_factory=list)
    on_missing_doc_tree: str = "warn_and_fallback"
    validation_mode: str = "strict"     # "strict" | "warn"


@dataclass
class HeaderFooterConfig:
    header: HeaderConfig = field(default_factory=HeaderConfig)
    footer: FooterConfig = field(default_factory=FooterConfig)
    behavior: HeaderFooterBehaviorConfig = field(default_factory=HeaderFooterBehaviorConfig)
    variants: HeaderFooterVariantsConfig = field(default_factory=HeaderFooterVariantsConfig)
    page_number_plan: PageNumberPlanConfig = field(default_factory=PageNumberPlanConfig)
    suppress_header_footer_selectors: list[str] = field(
        default_factory=lambda: list(_DEFAULT_SUPPRESS_HEADER_FOOTER_SELECTORS)
    )

    def _get_phase(
        self,
        phase_id: str,
        selectors: tuple[str, ...],
    ) -> PageNumberPhaseConfig | None:
        for phase in self.page_number_plan.phases:
            if str(phase.phase_id or "").strip() == phase_id:
                return phase

        selector_set = {str(item) for item in selectors}
        for phase in self.page_number_plan.phases:
            phase_selectors = {str(item) for item in phase.selectors}
            if selector_set.issubset(phase_selectors):
                return phase
        return None

    def _ensure_phase(
        self,
        phase_id: str,
        selectors: tuple[str, ...],
        *,
        default_format: str,
        default_start_mode: str,
        default_start_value: int,
    ) -> PageNumberPhaseConfig:
        phase = self._get_phase(phase_id, selectors)
        if phase is not None:
            if not phase.phase_id:
                phase.phase_id = phase_id
            if not phase.selectors:
                phase.selectors = list(selectors)
            return phase

        phase = PageNumberPhaseConfig(
            phase_id=phase_id,
            selectors=list(selectors),
            visible=True,
            number_format=default_format,
            start_mode=default_start_mode,
            start_value=max(1, int(default_start_value)),
        )
        self.page_number_plan.phases.append(phase)
        return phase

    @property
    def header_enabled(self) -> bool:
        return bool(getattr(self.header, "enabled", True))

    @header_enabled.setter
    def header_enabled(self, value: bool) -> None:
        self.header.enabled = bool(value)

    @property
    def header_mode(self) -> str:
        return str(self.header.mode or "styleref")

    @header_mode.setter
    def header_mode(self, value: str) -> None:
        self.header.mode = str(value or "styleref")

    @property
    def header_text(self) -> str:
        return str(self.header.fixed_text or "")

    @header_text.setter
    def header_text(self, value: str) -> None:
        self.header.fixed_text = str(value or "")

    @property
    def header_alignment(self) -> str:
        return str(getattr(self.header, "alignment", "center") or "center")

    @header_alignment.setter
    def header_alignment(self, value: str) -> None:
        normalized = str(value or "center").strip().lower()
        self.header.alignment = normalized if normalized in {"left", "center", "right"} else "center"

    @property
    def header_border(self) -> bool:
        return bool(self.header.border)

    @header_border.setter
    def header_border(self, value: bool) -> None:
        enabled = bool(value)
        self.header.border = enabled
        self.header.border_style.enabled = enabled

    @property
    def footer_enabled(self) -> bool:
        return bool(getattr(self.footer, "enabled", True))

    @footer_enabled.setter
    def footer_enabled(self, value: bool) -> None:
        self.footer.enabled = bool(value)

    @property
    def page_number_enabled(self) -> bool:
        return self.footer_enabled and str(self.footer.content_mode or "page_number") in {
            "page_number",
            "page_number_with_text",
        }

    @page_number_enabled.setter
    def page_number_enabled(self, value: bool) -> None:
        if bool(value):
            self.footer.enabled = True
            self.footer.content_mode = "page_number_with_text" if self.footer.fixed_text else "page_number"
        else:
            self.footer.content_mode = "fixed" if self.footer.fixed_text else "none"

    @property
    def footer_text(self) -> str:
        return str(self.footer.fixed_text or "")

    @footer_text.setter
    def footer_text(self, value: str) -> None:
        self.footer.fixed_text = str(value or "")

    @property
    def footer_alignment(self) -> str:
        return str(self.footer.alignment or "center")

    @footer_alignment.setter
    def footer_alignment(self, value: str) -> None:
        normalized = str(value or "center").strip().lower()
        self.footer.alignment = normalized if normalized in {"left", "center", "right"} else "center"

    @property
    def page_number_template(self) -> str:
        return str(self.footer.page_number_template or "{page}")

    @page_number_template.setter
    def page_number_template(self, value: str) -> None:
        self.footer.page_number_template = str(value or "{page}")

    @property
    def styleref_level(self) -> int:
        return int(self.header.styleref_level or 1)

    @styleref_level.setter
    def styleref_level(self, value: int) -> None:
        self.header.styleref_level = max(1, int(value or 1))

    @property
    def font_cn(self) -> str | None:
        return self.header.typography.font_cn

    @font_cn.setter
    def font_cn(self, value: str | None) -> None:
        self.header.typography.font_cn = str(value) if value not in (None, "") else None

    @property
    def font_en(self) -> str | None:
        return self.header.typography.font_en

    @font_en.setter
    def font_en(self, value: str | None) -> None:
        self.header.typography.font_en = str(value) if value not in (None, "") else None

    @property
    def size_pt(self) -> float | None:
        return self.header.typography.size_pt

    @size_pt.setter
    def size_pt(self, value: float | None) -> None:
        self.header.typography.size_pt = None if value in (None, "") else float(value)

    @property
    def bold(self) -> bool:
        return bool(self.header.typography.bold)

    @bold.setter
    def bold(self, value: bool) -> None:
        self.header.typography.bold = bool(value)

    @property
    def italic(self) -> bool:
        return bool(self.header.typography.italic)

    @italic.setter
    def italic(self, value: bool) -> None:
        self.header.typography.italic = bool(value)

    @property
    def footer_font_cn(self) -> str | None:
        return self.footer.typography.font_cn

    @footer_font_cn.setter
    def footer_font_cn(self, value: str | None) -> None:
        self.footer.typography.font_cn = str(value) if value not in (None, "") else None

    @property
    def footer_font_en(self) -> str | None:
        return self.footer.typography.font_en

    @footer_font_en.setter
    def footer_font_en(self, value: str | None) -> None:
        self.footer.typography.font_en = str(value) if value not in (None, "") else None

    @property
    def footer_size_pt(self) -> float | None:
        return self.footer.typography.size_pt

    @footer_size_pt.setter
    def footer_size_pt(self, value: float | None) -> None:
        self.footer.typography.size_pt = None if value in (None, "") else float(value)

    @property
    def footer_bold(self) -> bool:
        return bool(self.footer.typography.bold)

    @footer_bold.setter
    def footer_bold(self, value: bool) -> None:
        self.footer.typography.bold = bool(value)

    @property
    def footer_italic(self) -> bool:
        return bool(self.footer.typography.italic)

    @footer_italic.setter
    def footer_italic(self, value: bool) -> None:
        self.footer.typography.italic = bool(value)

    @property
    def hide_cover_header_footer(self) -> bool:
        selectors = {
            str(selector or "").strip()
            for selector in (self.suppress_header_footer_selectors or [])
            if str(selector or "").strip()
        }
        return (
            bool(self.header.hide_on_cover)
            and bool(self.footer.hide_on_cover)
            and bool(selectors & {"cover", "pre_numbering"})
        )

    @hide_cover_header_footer.setter
    def hide_cover_header_footer(self, value: bool) -> None:
        hide = bool(value)
        self.header.hide_on_cover = hide
        self.footer.hide_on_cover = hide
        if hide:
            selectors = [
                str(selector or "").strip()
                for selector in (self.suppress_header_footer_selectors or [])
                if str(selector or "").strip()
            ]
            if not selectors:
                selectors = list(_DEFAULT_SUPPRESS_HEADER_FOOTER_SELECTORS)
            elif "cover" not in selectors and "pre_numbering" not in selectors:
                selectors.insert(0, "pre_numbering")
            self.suppress_header_footer_selectors = selectors
        else:
            self.suppress_header_footer_selectors = []

    @property
    def front_matter_page_number_format(self) -> str:
        phase = self._get_phase(_FRONT_PHASE_ID, _FRONT_PHASE_SELECTORS)
        return str(getattr(phase, "number_format", None) or "upperRoman")

    @front_matter_page_number_format.setter
    def front_matter_page_number_format(self, value: str) -> None:
        phase = self._ensure_phase(
            _FRONT_PHASE_ID,
            _FRONT_PHASE_SELECTORS,
            default_format="upperRoman",
            default_start_mode="restart",
            default_start_value=1,
        )
        phase.number_format = str(value or "upperRoman")

    @property
    def front_matter_page_number_start(self) -> int:
        phase = self._get_phase(_FRONT_PHASE_ID, _FRONT_PHASE_SELECTORS)
        return max(1, int(getattr(phase, "start_value", 1) or 1))

    @front_matter_page_number_start.setter
    def front_matter_page_number_start(self, value: int) -> None:
        phase = self._ensure_phase(
            _FRONT_PHASE_ID,
            _FRONT_PHASE_SELECTORS,
            default_format="upperRoman",
            default_start_mode="restart",
            default_start_value=1,
        )
        phase.start_mode = "restart"
        phase.start_value = max(1, int(value or 1))

    @property
    def body_page_number_format(self) -> str:
        phase = self._get_phase(_BODY_PHASE_ID, _BODY_PHASE_SELECTORS)
        return str(getattr(phase, "number_format", None) or "decimal")

    @body_page_number_format.setter
    def body_page_number_format(self, value: str) -> None:
        phase = self._ensure_phase(
            _BODY_PHASE_ID,
            _BODY_PHASE_SELECTORS,
            default_format="decimal",
            default_start_mode="restart",
            default_start_value=1,
        )
        phase.number_format = str(value or "decimal")

    @property
    def body_page_number_start(self) -> int:
        phase = self._get_phase(_BODY_PHASE_ID, _BODY_PHASE_SELECTORS)
        return max(1, int(getattr(phase, "start_value", 1) or 1))

    @body_page_number_start.setter
    def body_page_number_start(self, value: int) -> None:
        phase = self._ensure_phase(
            _BODY_PHASE_ID,
            _BODY_PHASE_SELECTORS,
            default_format="decimal",
            default_start_mode="restart",
            default_start_value=1,
        )
        phase.start_value = max(1, int(value or 1))

    @property
    def restart_body_page_number(self) -> bool:
        phase = self._get_phase(_BODY_PHASE_ID, _BODY_PHASE_SELECTORS)
        return str(getattr(phase, "start_mode", None) or "restart") != "continue"

    @restart_body_page_number.setter
    def restart_body_page_number(self, value: bool) -> None:
        phase = self._ensure_phase(
            _BODY_PHASE_ID,
            _BODY_PHASE_SELECTORS,
            default_format="decimal",
            default_start_mode="restart",
            default_start_value=1,
        )
        phase.start_mode = "restart" if bool(value) else "continue"


@dataclass
class TocConfig:
    mode: str = "word_native"   # "word_native" | "plain"
    max_level: int = 3
    insert_position: str = "auto"   # "auto" | "after_cover" | paragraph index


@dataclass
class CaptionConfig:
    figure_prefix: str = "图"
    table_prefix: str = "表"
    separator: str = "\u3000"
    placeholder: str = "[待补充]"
    numbering_format: str = "chapter.seq"
    numbering_mode: str = "chapter"     # "chapter" | "global"
    auto_insert: bool = True
    format_inserted: bool = False


@dataclass
class FormulaTableConfig:
    """Formula-table visual parameters."""

    formula_font_name: str = "Times New Roman"
    formula_font_size_pt: float = 12.0
    formula_font_size_display: str = "12"
    formula_line_spacing: float = 1.0
    formula_space_before_pt: float = 6.0
    formula_space_before_unit: str = "pt"
    formula_space_after_pt: float = 6.0
    formula_space_after_unit: str = "pt"
    block_alignment: str = "center"
    table_alignment: str = "center"
    formula_cell_alignment: str = "center"
    number_alignment: str = "right"
    number_font_name: str = "Times New Roman"
    number_font_size_pt: float = 12.0
    number_font_size_display: str = "12"
    auto_shrink_number_column: bool = True


@dataclass
class FormulaStyleConfig:
    """Formula-style parameters."""

    unify_font: bool = True
    unify_size: bool = True
    unify_spacing: bool = True


@dataclass
class EquationNumberingConfig:
    """Equation numbering parameters."""

    numbering_format: str = "chapter.seq"


@dataclass
class ReferenceStyleConfig:
    """Reference-list typography."""

    hanging_indent_cm: float = 0.74
    space_after_pt: float = 0
    space_after_unit: str = "pt"
    font_cn: str | None = None
    font_en: str | None = None
    size_pt: float | None = None


@dataclass
class WatermarkConfig:
    """Watermark module configuration."""

    enabled: bool = False
    text: str = ""
    color: str = "#C0C0C0"
    rotation: int = -45
    font_size: int = 48


TABLE_SMART_LEVEL_OPTIONS: tuple[int, ...] = (3, 4, 5, 6)


def normalize_table_smart_levels(value: object) -> int:
    try:
        level = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 4
    return level if level in TABLE_SMART_LEVEL_OPTIONS else 4


@dataclass
class TableConfig:
    """Table-formatting parameters."""

    layout_mode: str = "smart"          # "compact" | "full" | "smart" | "keep"
    smart_levels: int = 4
    border_mode: str = "three_line"     # "full_grid" | "three_line" | "keep" | "color_table" | "none"
    border_width_pt: float = 0.5
    three_line_header_width_pt: float = 1.0
    three_line_bottom_width_pt: float = 0.5
    color_table_accent: str = "blue"
    color_table_variant: str = "header_grid"
    line_spacing_mode: str = "single"   # "single" | "one_half" | "double"
    repeat_header: bool = False
    font_cn: str | None = "微软雅黑"
    font_en: str | None = "Times New Roman"
    size_pt: float | None = 10.5
    bold: bool = False
    italic: bool = False
    table_alignment: str | None = "center"
    cell_alignment: str | None = None
    first_row_bold: bool = False


@dataclass
class OutputConfig:
    """Output artifact configuration."""

    final_docx: bool = True
    compare_docx: bool = True
    compare_text: bool = True
    compare_formatting: bool = True
    report_json: bool = True
    report_markdown: bool = True
    material_manifest: bool = False
    material_package: bool = False
    review_pdf: bool = False


def disabled_output_config() -> OutputConfig:
    """Return an execution projection that authorizes no artifact writes."""

    return OutputConfig(
        final_docx=False,
        compare_docx=False,
        compare_text=False,
        compare_formatting=False,
        report_json=False,
        report_markdown=False,
        material_manifest=False,
        material_package=False,
        review_pdf=False,
    )
