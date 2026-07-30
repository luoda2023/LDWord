from dataclasses import asdict

from src.config.resolver import resolve_template_baseline
from src.config.template import TemplateConfig


def test_template_baseline_resolver_is_read_only_and_has_template_provenance():
    template = TemplateConfig(name="baseline")
    template.page_setup.paper_size = "B5"
    template.table.layout_mode = "compact"
    template.toc.max_level = 4
    before = asdict(template)

    resolved = resolve_template_baseline(template)

    assert resolved.page_setup.paper_size == "B5"
    assert resolved.table.layout_mode == "compact"
    assert resolved.toc.max_level == 4
    assert resolved.module_switches == {}
    assert resolved.get_with_source("page_setup.paper_size").source == "template"
    assert resolved.get_with_source("table.layout_mode").source == "template"
    assert resolved.get_with_source("output.final_docx") is None
    assert not any(
        (
            resolved.output.final_docx,
            resolved.output.compare_docx,
            resolved.output.compare_text,
            resolved.output.compare_formatting,
            resolved.output.report_json,
            resolved.output.report_markdown,
            resolved.output.material_manifest,
            resolved.output.material_package,
            resolved.output.review_pdf,
        )
    )
    assert asdict(template) == before


def test_template_baseline_resolver_does_not_share_mutable_values():
    template = TemplateConfig()
    resolved = resolve_template_baseline(template)

    resolved.page_setup.margin.top_cm = 9.9
    resolved.styles["transient"] = object()

    assert template.page_setup.margin.top_cm != 9.9
    assert "transient" not in template.styles
