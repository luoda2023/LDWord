"""
Phase 1 冒烟测试 — 验证配置层

测试内容:
1. TemplateConfig / SceneWorkspace 能正常实例化
2. resolve_config() 三级合并正确
3. ConfigValue 来源标记正确
4. EntityArchive JSON 读写正确
5. Pipeline + ResolvedConfig 集成正确
"""

import sys
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig, PageSetupConfig, MarginConfig, StyleConfig
from src.config.scene import SceneWorkspace
from src.config.resolved import (
    ConfigValue,
    ImageInsertionItem,
    ReplacementRule,
    ResolvedConfig,
)
from src.config.resolver import resolve_config
from src.config.entity import EntityArchive, EntityProfile, load_entity_archive, save_entity_archive


def test_template_config():
    """TemplateConfig 基本实例化"""
    cfg = TemplateConfig(name="test_template")
    assert cfg.page_setup.paper_size == "A4"
    assert cfg.page_setup.margin.top_cm == 3.8
    assert cfg.caption.figure_prefix == "图"
    assert cfg.table.border_mode == "three_line"
    print("  ✅ TemplateConfig 实例化正确")


def test_scene_workspace():
    """SceneWorkspace 基本实例化"""
    scene = SceneWorkspace(name="test_scene")
    assert scene.is_module_enabled("page_setup") is True
    assert scene.is_module_enabled("md_cleanup") is False
    assert scene.is_module_enabled("reference_format") is True
    assert scene.format_scope.mode == "auto"
    assert scene.format_scope.page_ranges_text == ""
    assert scene.format_scope.sections["body"] is True
    print("  ✅ SceneWorkspace 实例化正确")


def test_resolve_config_basic():
    """基本合并: template → scene → session"""
    template = TemplateConfig(name="t1")
    scene = SceneWorkspace(name="s1")
    resolved = resolve_config(template, scene)

    assert resolved.page_setup.paper_size == "A4"
    assert resolved.is_module_enabled("page_setup") is True
    assert resolved.is_module_enabled("md_cleanup") is False
    print("  ✅ resolve_config() 基本合并正确")


def test_resolve_config_override():
    """scene 覆盖 + session 覆盖"""
    template = TemplateConfig()
    scene = SceneWorkspace(
        template_overrides={"page_setup.paper_size": "A3"}
    )

    # Scene 覆盖
    resolved = resolve_config(template, scene)
    assert resolved.page_setup.paper_size == "A3"

    # Session 再覆盖
    resolved2 = resolve_config(
        template, scene,
        session_overrides={"page_setup.paper_size": "B5"},
    )
    assert resolved2.page_setup.paper_size == "B5"
    print("  ✅ resolve_config() 覆盖逻辑正确")


def test_provenance():
    """来源标记"""
    template = TemplateConfig()
    scene = SceneWorkspace(
        template_overrides={"page_setup.paper_size": "A3"}
    )
    resolved = resolve_config(
        template, scene,
        session_overrides={"caption.figure_prefix": "Fig."},
    )

    # page_setup.paper_size 被 scene 覆盖
    cv = resolved.get_with_source("page_setup.paper_size")
    assert cv is not None
    assert cv.source == "scene"
    assert cv.is_overridden is True
    assert cv.template_default == "A4"

    # caption.figure_prefix 被 session 覆盖
    cv2 = resolved.get_with_source("caption.figure_prefix")
    assert cv2 is not None
    assert cv2.source == "session"
    assert cv2.template_default == "图"

    # 未覆盖的保持 template
    cv3 = resolved.get_with_source("caption.table_prefix")
    assert cv3 is not None
    assert cv3.source == "template"
    assert cv3.is_overridden is False

    overrides = resolved.list_overrides()
    assert "page_setup.paper_size" in overrides
    assert "caption.figure_prefix" in overrides
    print("  ✅ 来源标记（provenance）正确")


def test_entity_archive():
    """EntityArchive JSON 读写"""
    archive = EntityArchive(
        archive_id="zjsj",
        archive_name="中建三局",
        profiles=[
            EntityProfile(
                profile_id="main",
                profile_name="投标人主体",
                fields={"company_name": "中建三局", "legal_person": "张三"},
                assets_dir="/tmp/assets",
            ),
            EntityProfile(
                profile_id="sub",
                profile_name="分包方",
                fields={"company_name": "中建子公司", "legal_person": "李四"},
            ),
        ],
    )

    assert archive.get_profile("main").fields["company_name"] == "中建三局"
    assert archive.get_default_profile().profile_id == "main"
    assert len(archive.list_profile_names()) == 2

    # JSON 读写
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    tmp.close()
    try:
        save_entity_archive(archive, tmp.name)
        loaded = load_entity_archive(tmp.name)
        assert loaded.archive_name == "中建三局"
        assert len(loaded.profiles) == 2
        assert loaded.get_profile("sub").fields["legal_person"] == "李四"
        print("  ✅ EntityArchive JSON 读写正确")
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_entity_in_resolved():
    """ResolvedConfig 中挂载实体数据"""
    template = TemplateConfig()
    scene = SceneWorkspace()
    resolved = resolve_config(
        template, scene,
        entity_data={"company_name": "测试公司"},
        entity_assets_dir="/tmp/assets",
    )
    assert resolved.entity_data["company_name"] == "测试公司"
    assert resolved.entity_assets_dir == "/tmp/assets"
    print("  ✅ 实体数据挂载到 ResolvedConfig 正确")


def test_runtime_payloads_in_resolved_config():
    """runtime payloads should materialize into explicit dataclasses."""
    resolved = resolve_config(
        TemplateConfig(),
        SceneWorkspace(),
        images=[
            {"path": "a.png", "position": 2, "width_cm": "8.5"},
            ImageInsertionItem(path="b.png", position="end", width_cm=10.0),
        ],
        replacements=[
            {"old": "{{name}}", "new": "Alice"},
            ReplacementRule(old="{{date}}", new="2026-03-25"),
        ],
    )

    assert len(resolved.images) == 2
    assert isinstance(resolved.images[0], ImageInsertionItem)
    assert resolved.images[0].path == "a.png"
    assert resolved.images[0].position == 2
    assert resolved.images[0].width_cm == 8.5
    assert isinstance(resolved.images[1], ImageInsertionItem)

    assert len(resolved.replacements) == 2
    assert isinstance(resolved.replacements[0], ReplacementRule)
    assert resolved.replacements[0].old == "{{name}}"
    assert resolved.replacements[0].new == "Alice"
    assert isinstance(resolved.replacements[1], ReplacementRule)
    print("  ? runtime payloads materialize into explicit schema")


def test_scene_module_switches_match_registry():
    """Scene 默认开关集应与当前注册模块完全一致。"""
    from src.modules.registry import list_module_names

    scene = SceneWorkspace()
    assert set(scene.module_switches.keys()) == set(list_module_names())
    print("  ✅ Scene module_switches 与注册表一致")


def test_module_switch_alias_normalization():
    """历史模块名应归一到当前注册名。"""
    scene = SceneWorkspace(
        module_switches={
            "page_setup": True,
            "citation_link": False,
            "equation_table_fmt": True,
        }
    )
    resolved = resolve_config(TemplateConfig(), scene)

    assert "equation_table_fmt" not in scene.module_switches
    assert scene.is_module_enabled("citation_link") is False
    assert scene.is_module_enabled("reference_format") is True
    assert resolved.is_module_enabled("reference_format") is True
    assert resolved.is_module_enabled("citation_link") is False
    assert resolved.is_module_enabled("equation_table_format") is True
    print("  ✅ 模块开关别名归一正确")


def test_load_template_normalizes_legacy_fields():
    """legacy template 字段应在 loader 阶段归一到 canonical schema。"""
    from src.config.loader import load_template

    legacy_template = {
        "name": "legacy_template",
        "styles": {
            "normal": {
                "font_cn": "宋体",
                "font_en": "Times New Roman",
                "size_name": "小四",
                "line_spacing_rule": "fixed",
                "line_spacing": 22,
                "left_indent_cm": 1.2,
            },
            "heading1": {
                "font_cn": "黑体",
                "font_en": "Arial",
                "size_pt": 16,
                "bold": True,
                "alignment": "center",
                "line_spacing_type": "single",
                "line_spacing_pt": 20,
            },
            "figure_caption": {
                "font_cn": "宋体",
                "font_en": "Times New Roman",
                "size_pt": 10.5,
                "alignment": "center",
            },
        },
        "normal_table_layout_mode": "full",
        "normal_table_border_mode": "color_table",
        "color_table_accent": "green",
        "color_table_variant": "header_grid_zebra",
        "update_header": False,
        "update_page_number": False,
        "update_header_line": False,
        "heading_numbering": {
            "levels": {
                "heading1": {"format": "chinese_chapter", "separator": " "},
                "heading2": {"format": "chinese_section", "separator": " "},
            }
        },
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        json.dump(legacy_template, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        template = load_template(tmp.name)

        assert template.table.layout_mode == "full"
        assert template.table.border_mode == "color_table"
        assert template.table.color_table_accent == "green"
        assert template.table.color_table_variant == "header_grid_zebra"
        assert template.header_footer.header_mode == "none"
        assert template.header_footer.page_number_enabled is False
        assert template.header_footer.header_border is False
        assert template.styles["normal"].size_display == "小四"
        assert template.styles["normal"].size_pt == 12
        assert template.styles["normal"].line_spacing_type == "exact"
        assert template.styles["normal"].line_spacing_pt == 22
        assert template.styles["normal"].left_indent_chars == 1.2
        assert template.styles["normal"].left_indent_unit == "cm"
        assert template.styles["heading"].font_cn == "黑体"
        assert template.styles["heading"].line_spacing_type == "multiple"
        assert template.styles["heading"].line_spacing_pt == 1.0
        assert template.heading_numbering.level_bindings["heading1"].enabled is True
        assert template.heading_numbering.level_bindings["heading1"].display_core_style == "chinese_lower"
        assert template.heading_numbering.level_bindings["heading1"].display_template == "第{cn}章"
        assert template.heading_numbering.level_bindings["heading1"].title_separator == " "
        assert template.heading_numbering.level_bindings["heading2"].display_template == "第{cn}节"
        print("  ✅ loader 可将 legacy template 归一到 canonical schema")
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_load_template_supports_nested_page_number_plan_schema():
    from src.config.loader import load_template

    payload = {
        "name": "nested_page_number_plan",
        "header_footer": {
            "typography": {
                "font_cn": "宋体",
                "font_en": "Times New Roman",
                "size_pt": 10.5,
            },
            "header": {
                "mode": "fixed",
                "fixed_text": "固定页眉",
                "styleref_level": 2,
                "border": False,
                "hide_on_cover": False,
            },
            "footer": {
                "content_mode": "none",
                "hide_on_cover": False,
            },
            "page_number_plan": {
                "validation_mode": "warn",
                "on_missing_doc_tree": "warn_and_fallback",
                "phases": [
                    {
                        "phase_id": "front",
                        "selectors": ["front_matter"],
                        "visible": True,
                        "number_format": "lowerRoman",
                        "start_mode": "restart",
                        "start_value": 1,
                    },
                    {
                        "phase_id": "body",
                        "selectors": ["body", "back_matter"],
                        "visible": True,
                        "number_format": "decimal",
                        "start_mode": "restart",
                        "start_value": 3,
                    },
                ],
            },
        },
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        template = load_template(tmp.name)
        header_footer = template.header_footer

        assert header_footer.header.mode == "fixed"
        assert header_footer.header.fixed_text == "固定页眉"
        assert header_footer.footer.content_mode == "none"
        assert len(header_footer.page_number_plan.phases) == 2
        assert header_footer.page_number_enabled is False
        assert header_footer.front_matter_page_number_format == "lowerRoman"
        assert header_footer.body_page_number_start == 3
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_save_template_round_trips_nested_page_number_plan_without_legacy_flat_fields():
    from src.config.loader import load_template, save_template

    template = TemplateConfig(name="roundtrip_page_number_plan")
    header_footer = template.header_footer
    header_footer.header_mode = "fixed"
    header_footer.header_text = "固定页眉"
    header_footer.hide_cover_header_footer = False
    header_footer.front_matter_page_number_format = "lowerRoman"
    header_footer.front_matter_page_number_start = 2
    header_footer.body_page_number_format = "decimal"
    header_footer.restart_body_page_number = False
    header_footer.body_page_number_start = 3

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    target = Path(tmp.name)
    tmp.close()
    try:
        save_template(template, target)

        raw = json.loads(target.read_text(encoding="utf-8"))
        assert "page_number_plan" in raw["header_footer"]
        assert "front_matter_page_number_format" not in raw["header_footer"]
        assert "body_page_number_format" not in raw["header_footer"]
        assert "page_number_enabled" not in raw["header_footer"]

        reloaded = load_template(target)
        reloaded_hf = reloaded.header_footer
        assert reloaded_hf.header.mode == "fixed"
        assert reloaded_hf.header.fixed_text == "固定页眉"
        assert reloaded_hf.hide_cover_header_footer is False
        assert reloaded_hf.front_matter_page_number_format == "lowerRoman"
        assert reloaded_hf.front_matter_page_number_start == 2
        assert reloaded_hf.restart_body_page_number is False
        assert reloaded_hf.body_page_number_start == 3
    finally:
        target.unlink(missing_ok=True)


def test_load_template_lifts_legacy_heading_alias_into_heading_numbering():
    """legacy top-level heading 别名应只在 migration 层吸收，不再进入 runtime schema。"""
    from src.config.loader import load_template

    legacy_template = {
        "name": "legacy_heading_alias",
        "heading": {
            "numbering_style": "arabic_dot",
            "separator": " ",
        },
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        json.dump(legacy_template, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        template = load_template(tmp.name)

        assert not hasattr(template, "heading")
        assert template.heading_numbering.level_bindings["heading1"].display_core_style == "arabic"
        assert template.heading_numbering.level_bindings["heading1"].chain == "current_only"
        assert template.heading_numbering.level_bindings["heading2"].chain == "parent.current"
        assert template.heading_numbering.level_bindings["heading3"].chain == "parent.parent.current"
        assert template.heading_numbering.level_bindings["heading2"].display_template == "{chain}"
        assert template.heading_numbering.level_bindings["heading1"].title_separator == " "
        print("  ✅ legacy top-level heading 已在 migration 层归一到 heading_numbering")
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_load_template_preserves_special_indent_schema_and_legacy_fields():
    from src.config.loader import load_template

    payload = {
        "styles": {
            "normal": {
                "font_cn": "宋体",
                "special_indent_mode": "first_line",
                "special_indent_value": 2,
                "special_indent_unit": "chars",
            },
            "heading1": {
                "font_cn": "黑体",
                "hanging_indent_chars": 1.5,
                "hanging_indent_unit": "chars",
            },
        }
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        template = load_template(tmp.name)

        assert template.styles["normal"].special_indent_mode == "first_line"
        assert template.styles["normal"].special_indent_value == 2
        assert template.styles["normal"].special_indent_unit == "chars"
        assert template.styles["normal"].first_line_indent_chars == 2
        assert template.styles["normal"].first_line_indent_unit == "chars"

        assert template.styles["heading1"].special_indent_mode == "hanging"
        assert template.styles["heading1"].special_indent_value == 1.5
        assert template.styles["heading1"].special_indent_unit == "chars"
        assert template.styles["heading1"].hanging_indent_chars == 1.5
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_load_scene_normalizes_legacy_capabilities_and_overrides():
    """legacy scene capabilities / pipeline / enabled 字段应在 loader 阶段收口。"""
    from src.config.loader import load_scene

    legacy_scene = {
        "name": "legacy_scene",
        "capabilities": {
            "section_detection": True,
            "toc_rebuild": True,
            "citation_link_restore": True,
            "chem_typography_restore": False,
            "md_cleanup": True,
        },
        "pipeline": [
            "page_setup",
            "style_manager",
            "heading_detect",
            "caption_format",
        ],
        "citation_link": {
            "enabled": False,
            "auto_number_reference_entries": False,
        },
        "chem_typography": {
            "enabled": True,
            "allow_tokens": ["H2O"],
        },
        "pipeline_strict_mode": False,
        "normal_table_layout_mode": "full",
        "update_page_number": False,
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        json.dump(legacy_scene, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        scene = load_scene(tmp.name)

        assert scene.is_module_enabled("page_setup") is True
        assert scene.is_module_enabled("paragraph_style") is True
        assert scene.is_module_enabled("heading_recognition") is True
        assert scene.is_module_enabled("caption") is True
        assert scene.is_module_enabled("section_format") is True
        assert scene.is_module_enabled("toc") is True
        assert scene.is_module_enabled("reference_format") is False
        assert scene.is_module_enabled("citation_link") is False
        assert scene.is_module_enabled("chem_typography") is True
        assert scene.strict_mode is False
        assert scene.citation_link.auto_number_reference_entries is False
        assert scene.chem_typography.allow_tokens == ["H2O"]
        assert scene.template_overrides["table.layout_mode"] == "full"
        assert "header_footer.page_number_enabled" not in scene.template_overrides
        assert scene.header_footer.page_number_enabled is False
        print("  ✅ loader 可将 legacy scene capabilities/pipeline/enabled 归一")
    finally:
        Path(tmp.name).unlink(missing_ok=True)



def test_normalize_scene_payload_treats_legacy_pipeline_as_explicit_enabled_list():
    """legacy pipeline should only enable the modules it explicitly lists."""
    from src.config.migration import normalize_scene_payload

    normalized = normalize_scene_payload(
        {
            "name": "legacy_pipeline_only",
            "pipeline": ["page_setup", "caption"],
        }
    )
    switches = normalized["module_switches"]

    assert switches["page_setup"] is True
    assert switches["caption"] is True
    assert switches["header_footer"] is False
    assert switches["table_format"] is False
    assert switches["reference_format"] is False
    assert switches["citation_link"] is False
    print("  ? legacy pipeline keeps only explicitly listed modules")




def test_load_scene_accepts_overrides_alias():
    """Scene overrides should normalize into template_overrides."""
    from src.config.loader import load_scene

    payload = {
        "name": "scene_with_overrides_alias",
        "overrides": {
            "normal_table_layout_mode": "compact",
            "styles.normal.size_name": "\u4e94\u53f7",
        },
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        scene = load_scene(tmp.name)

        assert scene.template_overrides["table.layout_mode"] == "compact"
        assert scene.template_overrides["styles.normal.size_display"] == "\u4e94\u53f7"
        assert scene.template_overrides["styles.normal.size_pt"] == 10.5
        print("  ? loader accepts Scene.overrides alias")
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_save_load_scene_preserves_header_footer_and_toc_on_scene_top_level():
    from src.config.loader import load_scene, save_scene

    scene = SceneWorkspace(name="scene_roundtrip")
    scene.header_footer.header_mode = "fixed"
    scene.header_footer.header_text = "固定页眉"
    scene.header_footer.page_number_enabled = False
    scene.header_footer.front_matter_page_number_format = "lowerRoman"
    scene.header_footer.body_page_number_start = 5
    scene.toc.enabled = False
    scene.toc.max_level = 4

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    target = Path(tmp.name)
    tmp.close()
    try:
        save_scene(scene, target)
        reloaded = load_scene(target)

        assert reloaded.header_footer.header_mode == "fixed"
        assert reloaded.header_footer.header_text == "固定页眉"
        assert reloaded.header_footer.page_number_enabled is False
        assert reloaded.header_footer.front_matter_page_number_format == "lowerRoman"
        assert reloaded.header_footer.body_page_number_start == 5
        assert reloaded.toc.enabled is False
        assert reloaded.toc.max_level == 4
        assert "header_footer.page_number_enabled" not in reloaded.template_overrides
        assert "toc.enabled" not in reloaded.template_overrides
    finally:
        target.unlink(missing_ok=True)

def test_resolve_config_normalizes_legacy_override_keys():
    """resolve_config() 应先归一 legacy override key，再进入 provenance / merge。"""
    scene = SceneWorkspace(
        template_overrides={
            "normal_table_layout_mode": "full",
            "update_page_number": False,
            "styles.normal.size_name": "五号",
            "styles.normal.line_spacing_rule": "fixed",
            "styles.normal.line_spacing": 18,
            "styles.normal.left_indent_cm": 0.8,
        }
    )
    resolved = resolve_config(TemplateConfig(), scene)

    assert resolved.table.layout_mode == "full"
    assert resolved.header_footer.page_number_enabled is True
    assert resolved.styles["normal"].size_display == "五号"
    assert resolved.styles["normal"].size_pt == 10.5
    assert resolved.styles["normal"].line_spacing_type == "exact"
    assert resolved.styles["normal"].line_spacing_pt == 18
    assert resolved.styles["normal"].left_indent_chars == 0.8
    assert resolved.styles["normal"].left_indent_unit == "cm"
    assert resolved.get_with_source("header_footer.page_number_enabled").source == "template"
    assert resolved.get_with_source("styles.normal.line_spacing_pt").source == "scene"
    assert resolved.get_with_source("header_footer.update_page_number") is None
    print("  ✅ resolve_config 可归一 legacy override dotted-key")


def test_resolve_config_ignores_legacy_page_number_alias_for_new_nested_override_keys():
    scene = SceneWorkspace(
        template_overrides={
            "header_footer.footer.content_mode": "none",
            "header_footer.page_number_plan.phases": [
                {
                    "phase_id": "front",
                    "selectors": ["front_matter"],
                    "visible": True,
                    "number_format": "lowerRoman",
                    "start_mode": "restart",
                    "start_value": 1,
                },
                {
                    "phase_id": "body",
                    "selectors": ["body", "back_matter"],
                    "visible": True,
                    "number_format": "decimal",
                    "start_mode": "restart",
                    "start_value": 5,
                },
            ],
        }
    )

    resolved = resolve_config(TemplateConfig(), scene)

    assert resolved.header_footer.page_number_enabled is True
    assert resolved.header_footer.front_matter_page_number_format == "upperRoman"
    assert resolved.header_footer.body_page_number_start == 1
    assert resolved.get_with_source("header_footer.page_number_enabled").source == "template"


def test_resolve_config_keeps_non_page_number_header_footer_scene_overrides():
    scene = SceneWorkspace(
        template_overrides={
            "header_footer.header.mode": "fixed",
            "header_footer.header.fixed_text": "场景页眉",
            "header_footer.footer.content_mode": "none",
        }
    )

    resolved = resolve_config(TemplateConfig(), scene)

    assert resolved.header_footer.header_mode == "fixed"
    assert resolved.header_footer.header_text == "场景页眉"
    assert resolved.header_footer.page_number_enabled is True
    assert resolved.get_with_source("header_footer.header_mode").source == "scene"
    assert resolved.get_with_source("header_footer.page_number_enabled").source == "template"


if __name__ == "__main__":
    print("Phase 1 冒烟测试")
    print("=" * 50)

    test_template_config()
    test_scene_workspace()
    test_resolve_config_basic()
    test_resolve_config_override()
    test_provenance()
    test_entity_archive()
    test_entity_in_resolved()

    print("=" * 50)
    print("✅ 全部 7 项测试通过，Phase 1 配置层验证完成！")
