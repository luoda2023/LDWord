import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.ui.panels.workbench.scene_presets import SCENE_METAS


def test_every_declared_builtin_template_id_resolves_to_a_template_config():
    seen: set[str] = set()

    for scene_meta in SCENE_METAS:
        for template_meta in scene_meta.compatible_templates:
            if template_meta.template_id in seen:
                continue
            seen.add(template_meta.template_id)

            template = create_builtin_template(template_meta.template_id)

            assert template.name
            assert template.description is not None


def test_thesis_template_uses_real_config_payload_instead_of_name_only_shell():
    template = create_builtin_template("thesis_gbt")

    assert template.name == "GB/T 7713 学位论文"
    assert template.page_setup.margin.top_cm == 3.8
    assert template.header_footer.header_mode == "styleref"
    assert template.toc.mode == "word_native"
    assert template.formula_table.number_alignment == "right"


def test_builtin_template_factory_returns_fresh_instances():
    first = create_builtin_template("default")
    second = create_builtin_template("default")

    first.page_setup.margin.top_cm = 9.9

    assert second.page_setup.margin.top_cm != 9.9
