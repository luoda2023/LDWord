from src.config.builtin_templates import create_builtin_template
from src.config.style_variant_semantics import (
    STYLE_VARIANTS,
    disable_variant_override,
    enable_variant_override,
    get_effective_style,
    is_variant_overridden,
)
from src.config.template import StyleConfig


def test_style_variants_are_template_owned():
    template = create_builtin_template("default")
    template.styles["body"] = StyleConfig(font_cn="宋体", size_pt=12)

    inherited = get_effective_style(template, "references_body")

    assert inherited is template.styles["body"]
    assert is_variant_overridden(template, "references_body") is False

    override = enable_variant_override(template, "references_body")
    assert override is template.styles["references_body"]
    assert override is not template.styles["body"]
    assert override.font_cn == "宋体"
    assert override.size_pt == 12
    assert is_variant_overridden(template, "references_body") is True

    override.font_cn = "黑体"
    assert template.styles["body"].font_cn == "宋体"

    disable_variant_override(template, "references_body")
    assert is_variant_overridden(template, "references_body") is False
    assert get_effective_style(template, "references_body") is template.styles["body"]


def test_style_variant_registry_uses_document_roles_without_scene_state():
    assert {variant.section_type for variant in STYLE_VARIANTS} == {
        "references",
        "acknowledgment",
        "abstract_cn",
        "appendix",
        "resume",
    }
    assert all(variant.key.endswith("_body") for variant in STYLE_VARIANTS)
