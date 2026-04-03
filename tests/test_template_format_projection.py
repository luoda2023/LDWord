import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.builtin_templates import create_builtin_template
from src.config.template import TemplateConfig
from src.ui.panels.template_format import (
    TEMPLATE_PREVIEW_SPECS,
    build_template_preview_groups,
)


def test_preview_specs_cover_all_template_config_fields_except_identity_fields():
    covered = {field_name for spec in TEMPLATE_PREVIEW_SPECS for field_name in spec.field_names}
    expected = {field.name for field in fields(TemplateConfig)} - {"name", "description"}

    assert covered == expected


def test_preview_groups_expose_real_grouped_summaries_for_builtin_thesis_template():
    groups = build_template_preview_groups(create_builtin_template("thesis_gbt"))
    group_map = {group.group_id: group for group in groups}

    assert len(groups) == len(TEMPLATE_PREVIEW_SPECS)
    assert "3.8" in group_map["page"].summary
    assert "宋体" in group_map["style"].summary
    assert "目录" in group_map["elements"].summary
    assert "章节序号" in group_map["formula"].summary
    assert "悬挂" in group_map["reference"].summary
