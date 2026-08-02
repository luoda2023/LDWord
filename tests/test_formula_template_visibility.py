from src.config import library
from src.config.builtin_templates import create_builtin_template
from src.config.library import load_template_from_library
from src.config.migration import upgrade_legacy_user_template_layout_policies
from src.ui.adapters.config_selector_models import template_selector_options

TEMPLATE_ID = "南开大学研究生学位论文写作规范（2026版）"


def test_nankai_template_is_visible_without_persisting_formula_policy(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", tmp_path / "templates")
    template = create_builtin_template("thesis_custom", mode_id="thesis")
    template.name = TEMPLATE_ID
    library.save_template_to_library(
        template,
        TEMPLATE_ID,
        mode_id="thesis",
    )

    options = template_selector_options("thesis")
    by_id = {option.value: option for option in options}

    assert TEMPLATE_ID in by_id
    assert by_id[TEMPLATE_ID].source_type == "user"
    assert by_id[TEMPLATE_ID].disabled is False

    template = load_template_from_library(TEMPLATE_ID, mode_id="thesis")
    assert template.name == TEMPLATE_ID
    assert not hasattr(template, "formula_table")
    assert not hasattr(template, "formula_style")
    assert not hasattr(template, "equation_numbering")


def test_compatible_template_upgrade_drops_every_formula_policy_root():
    payload = {
        "formula_convert": {"enabled": True},
        "formula_to_table": {"enabled": True},
        "formula_table": {"formula_font_name": "Cambria Math"},
        "formula_style": {"enabled": True},
        "equation_table_format": {"enabled": True},
        "equation_numbering": {"numbering_format": "global"},
        "chem_typography": {"enabled": True},
        "name": "legacy template",
    }

    upgraded = upgrade_legacy_user_template_layout_policies(payload)

    assert upgraded == {"name": "legacy template"}
