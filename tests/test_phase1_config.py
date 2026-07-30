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
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.config.scene import SceneWorkspace
from src.config.dataclass_utils import dict_to_dataclass
from src.config.migration import normalize_scene_payload, normalize_template_payload
from src.config.resolved import ImageInsertionItem, ReplacementRule
from src.config.resolver import resolve_config
from src.config.entity import EntityArchive, EntityProfile, load_entity_archive, save_entity_archive


def _materialize_legacy_template(payload: dict) -> TemplateConfig:
    return dict_to_dataclass(TemplateConfig, normalize_template_payload(payload))


def _materialize_legacy_scene(payload: dict) -> SceneWorkspace:
    return dict_to_dataclass(SceneWorkspace, normalize_scene_payload(payload))


@pytest.mark.parametrize(
    "profile_name",
    ("input_source_profile", "compliance_profile"),
)
def test_canonical_scene_loader_rejects_unknown_failure_policy(
    tmp_path,
    profile_name,
):
    from src.config.loader import ConfigLoadError, load_scene

    payload = asdict(SceneWorkspace())
    payload[profile_name]["failure_policy"] = "blok"
    target = tmp_path / f"invalid-{profile_name}.json"
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError, match=f"{profile_name}.failure_policy"):
        load_scene(target)


@pytest.mark.parametrize(
    ("corruption", "expected_issue"),
    (
        ("duplicate", "duplicate_delivery_preset_id:final"),
        ("empty_preset", "delivery_preset_id_empty:0"),
        ("empty_default", "default_delivery_preset_id_empty"),
        ("unknown_default", "default_delivery_preset_id_unknown:missing"),
    ),
)
def test_canonical_scene_loader_rejects_invalid_delivery_identity(
    tmp_path,
    corruption,
    expected_issue,
):
    from src.config.loader import ConfigLoadError, load_scene

    payload = asdict(SceneWorkspace())
    if corruption == "duplicate":
        payload["delivery_presets"].append(
            dict(payload["delivery_presets"][0])
        )
    elif corruption == "empty_preset":
        payload["delivery_presets"][0]["preset_id"] = ""
    elif corruption == "empty_default":
        payload["default_delivery_preset_id"] = ""
    else:
        payload["default_delivery_preset_id"] = "missing"
    target = tmp_path / f"invalid-delivery-{corruption}.json"
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError, match=expected_issue):
        load_scene(target)


@pytest.mark.parametrize("default_id", ("", "missing"))
def test_scene_preserves_invalid_default_delivery_identity_until_fail_closed(
    default_id,
):
    from src.config.scene import DeliveryPreset

    scene = SceneWorkspace(
        default_delivery_preset_id=default_id,
        delivery_presets=[DeliveryPreset(preset_id="first")],
    )

    assert scene.default_delivery_preset_id == default_id
    with pytest.raises(ValueError, match="default_delivery_preset_id"):
        resolve_config(TemplateConfig(), scene)


def test_resolve_config_rejects_duplicate_delivery_identity():
    from src.config.scene import DeliveryPreset

    scene = SceneWorkspace(
        default_delivery_preset_id="same",
        delivery_presets=[
            DeliveryPreset(preset_id="same"),
            DeliveryPreset(preset_id="same"),
        ],
    )

    with pytest.raises(ValueError, match="duplicate_delivery_preset_id:same"):
        resolve_config(TemplateConfig(), scene)


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
    assert not hasattr(scene, "format_scope")
    assert not hasattr(scene, "available_sections")
    assert not hasattr(scene, "application_boundary")
    assert scene.document_scope.mode == "all"
    print("  ✅ SceneWorkspace 实例化正确")


def test_scene_payload_drops_obsolete_scope_fields_without_inference():
    """Removed section metadata cannot recreate an executable boundary."""
    from src.config.migration import normalize_scene_payload

    normalized = normalize_scene_payload(
        {
            "scene_id": "obsolete_scope_payload",
            "format_scope": {
                "sections": {
                    "body": True,
                    "references": False,
                    "appendix": False,
                }
            },
            "available_sections": ["body", "references"],
        }
    )

    assert "format_scope" not in normalized
    assert "available_sections" not in normalized
    assert "application_boundary" not in normalized

    scene = SceneWorkspace(document_scope={"mode": "body"})
    assert scene.document_scope.mode == "body"


def test_normalize_scene_payload_drops_obsolete_scene_output_mirror():
    from src.config.migration import normalize_scene_payload

    normalized = normalize_scene_payload(
        {
            "scene_id": "official",
            "output": {
                "final_docx": True,
                "review_pdf": True,
                "report_json": False,
            },
            "template_overrides": {
                "output.review_pdf": True,
            },
        }
    )

    assert "output" not in normalized
    assert not any(
        key == "output" or key.startswith("output.")
        for key in normalized.get("template_overrides", {})
    )


def test_resolve_config_basic():
    """基本合并: template → scene → session"""
    template = TemplateConfig(name="t1")
    scene = SceneWorkspace(name="s1")
    resolved = resolve_config(template, scene)

    assert resolved.page_setup.paper_size == "A4"
    assert resolved.is_module_enabled("page_setup") is True
    assert resolved.is_module_enabled("md_cleanup") is False
    assert resolved.document_scope.mode == "all"
    print("  ✅ resolve_config() 基本合并正确")


def test_resolve_config_preserves_document_scope_policy():
    scene = SceneWorkspace(name="body_only_scene")
    scene.document_scope.mode = "body"

    resolved = resolve_config(TemplateConfig(), scene)

    assert resolved.document_scope.mode == "body"
    assert resolved.document_scope.included_roles("custom") == ("body",)


def test_resolve_config_defaults_to_all_content_without_document_state():
    scene = SceneWorkspace(name="full_document")

    resolved = resolve_config(TemplateConfig(), scene)

    assert resolved.document_scope.mode == "all"
    assert not hasattr(resolved, "format_scope")


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
                asset_paths={"question_figure": "/tmp/assets/question.png"},
                asset_metadata={"question_figure": {"alt_text": "题目示意图"}},
                asset_items=[
                    {
                        "item_id": "question_figure_1",
                        "role": "question_figure",
                        "path": "/tmp/assets/question_1.png",
                        "metadata": {"question_index": "1", "alt_text": "第一题图"},
                    }
                ],
                asset_item_history=[
                    {
                        "schema_version": "1",
                        "action": "question_figure_library_metadata_update",
                        "changed_at": "2026-06-21T00:00:00Z",
                        "role": "question_figure",
                        "item_id": "question_figure_1",
                        "target_label": "题1",
                        "question_index": "1",
                        "changed_fields": "alt_text",
                        "alt_text_before": "旧说明",
                        "alt_text_after": "第一题图",
                        "change_summary": "图片说明: 旧说明 -> 第一题图",
                    }
                ],
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
        assert loaded.get_profile("main").asset_paths == {"question_figure": "/tmp/assets/question.png"}
        assert loaded.get_profile("main").asset_metadata == {
            "question_figure": {"alt_text": "题目示意图"}
        }
        assert loaded.get_profile("main").asset_items == [
            {
                "item_id": "question_figure_1",
                "role": "question_figure",
                "path": "/tmp/assets/question_1.png",
                "metadata": {"question_index": "1", "alt_text": "第一题图"},
            }
        ]
        assert loaded.get_profile("main").asset_item_history == [
            {
                "schema_version": "1",
                "action": "question_figure_library_metadata_update",
                "changed_at": "2026-06-21T00:00:00Z",
                "role": "question_figure",
                "item_id": "question_figure_1",
                "target_label": "题1",
                "question_index": "1",
                "changed_fields": "alt_text",
                "alt_text_before": "旧说明",
                "alt_text_after": "第一题图",
                "change_summary": "图片说明: 旧说明 -> 第一题图",
            }
        ]
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


def test_scene_workspace_rejects_unknown_module_switch_instead_of_enabling_default():
    with pytest.raises(ValueError, match=r"unknown module switch key.*page_setp"):
        SceneWorkspace(module_switches={"page_setp": False})


def test_canonical_scene_loader_rejects_unknown_module_switch(tmp_path):
    from src.config.loader import ConfigLoadError, load_scene

    payload = asdict(SceneWorkspace())
    payload["module_switches"]["page_setp"] = False
    target = tmp_path / "invalid-module-switch.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="Invalid canonical config payload"):
        load_scene(target)


def test_resolve_config_rejects_module_switch_tampering_before_document_mutation(
    tmp_path,
):
    from docx import Document
    from docx.shared import Cm

    source = tmp_path / "source.docx"
    document = Document()
    document.sections[0].top_margin = Cm(1)
    document.save(source)

    scene = SceneWorkspace()
    scene.module_switches = {"page_setp": False}

    with pytest.raises(ValueError, match=r"unknown module switch key.*page_setp"):
        resolve_config(TemplateConfig(), scene)

    assert round(Document(source).sections[0].top_margin.cm, 2) == 1.0


def test_explicit_scene_migration_rejects_unknown_module_switch_sources():
    for payload in (
        {"module_switches": {"page_setp": False}},
        {"capabilities": {"page_setp": False}},
        {"pipeline": ["page_setp"]},
    ):
        with pytest.raises(ValueError, match=r"unknown module switch key.*page_setp"):
            normalize_scene_payload(payload)


def test_explicit_template_migration_normalizes_legacy_fields():
    """Legacy template fields are handled only by explicit migration."""

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
        "bold": True,
        "italic": True,
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

        template = _materialize_legacy_template(legacy_template)

        assert template.table.layout_mode == "full"
        assert template.table.border_mode == "color_table"
        assert template.table.color_table_accent == "green"
        assert template.table.color_table_variant == "header_grid_zebra"
        assert template.header_footer.header_mode == "none"
        assert template.header_footer.page_number_enabled is False
        assert template.header_footer.header_border is False
        assert template.header_footer.bold is True
        assert template.header_footer.italic is True
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


def test_explicit_template_migration_supports_nested_page_number_plan_schema():

    payload = {
        "name": "nested_page_number_plan",
        "header_footer": {
            "typography": {
                "font_cn": "宋体",
                "font_en": "Times New Roman",
                "size_pt": 10.5,
                "bold": True,
                "italic": True,
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
                "fixed_text": "内部流转",
                "alignment": "right",
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

        template = _materialize_legacy_template(payload)
        header_footer = template.header_footer

        assert header_footer.header.mode == "fixed"
        assert header_footer.header.fixed_text == "固定页眉"
        assert header_footer.footer.content_mode == "none"
        assert header_footer.footer.fixed_text == "内部流转"
        assert header_footer.footer.alignment == "right"
        assert len(header_footer.page_number_plan.phases) == 2
        assert header_footer.page_number_enabled is False
        assert header_footer.front_matter_page_number_format == "lowerRoman"
        assert header_footer.body_page_number_start == 3
        assert header_footer.bold is True
        assert header_footer.italic is True
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_explicit_template_migration_normalizes_flat_footer_fields():

    payload = {
        "name": "flat_footer_fields",
        "footer_text": "Confidential",
        "footer_alignment": "right",
        "page_number_enabled": True,
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        template = _materialize_legacy_template(payload)
        header_footer = template.header_footer

        assert header_footer.footer.content_mode == "page_number_with_text"
        assert header_footer.footer_text == "Confidential"
        assert header_footer.footer_alignment == "right"
        assert header_footer.page_number_enabled is True
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


def test_explicit_template_migration_lifts_legacy_heading_alias():
    """legacy top-level heading 别名应只在 migration 层吸收，不再进入 runtime schema。"""

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

        template = _materialize_legacy_template(legacy_template)

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


def test_explicit_template_migration_preserves_special_indent_fields():

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

        template = _materialize_legacy_template(payload)

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


def test_explicit_scene_migration_normalizes_capabilities_and_overrides():
    """legacy scene capabilities / pipeline / enabled 字段应在 loader 阶段收口。"""

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

        scene = _materialize_legacy_scene(legacy_scene)

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
        assert "table.layout_mode" not in scene.template_overrides
        assert "header_footer.page_number_enabled" not in scene.template_overrides
        assert not hasattr(scene, "header_footer")
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




def test_explicit_scene_migration_accepts_overrides_alias():
    """Scene overrides should normalize into template_overrides."""

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

        scene = _materialize_legacy_scene(payload)

        assert scene.template_overrides["table.layout_mode"] == "compact"
        assert scene.template_overrides["styles.normal.size_display"] == "\u4e94\u53f7"
        assert scene.template_overrides["styles.normal.size_pt"] == 10.5
        print("  ? loader accepts Scene.overrides alias")
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_save_load_scene_omits_removed_template_appearance_fields():
    from src.config.loader import load_scene, save_scene

    scene = SceneWorkspace(name="scene_roundtrip")

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    target = Path(tmp.name)
    tmp.close()
    try:
        save_scene(scene, target)
        reloaded = load_scene(target)

        payload = json.loads(target.read_text(encoding="utf-8"))
        for field_name in (
            "table",
            "header_footer",
            "toc",
            "caption",
            "formula_table",
        ):
            assert field_name not in payload
            assert not hasattr(reloaded, field_name)
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


def test_explicit_scene_migration_preserves_high_level_scene_profiles():
    from src.config.loader import load_scene, save_scene

    payload = {
        "name": "profile_scene",
        "input_sources": {
            "accepted_formats": ["docx", "markdown"],
            "structured_formats": ["json"],
            "markdown_policy": "preview_and_cleanup",
            "latex_policy": "formula_fragments_only",
            "require_material_package": True,
            "material_schema_id": "journal_materials_v1",
            "required_material_fields": ["author", "affiliation"],
            "required_image_roles": ["graphical_abstract"],
            "failure_policy": "block",
        },
        "compliance": {
            "profile_id": "journal_en",
            "rule_family": "journal_submission",
            "count_profile_id": "journal_words",
            "check_scopes": ["body", "references", "figures"],
            "report_level": "detailed",
            "failure_policy": "warn",
        },
        "object_preservation": {
            "preservation_mode": "strict",
            "block_on": ["ole_objects", "embedded_workbooks"],
        },
        "delivery": {
            "default_preset_id": "submission",
            "presets": [
                {
                    "preset_id": "submission",
                    "label": "Submission package",
                    "target_template_id": "journal_default",
                    "artifacts": {
                        "final_docx": True,
                        "compare_docx": False,
                        "compare_text": False,
                        "compare_formatting": False,
                        "report_json": True,
                        "report_markdown": True,
                    },
                    "content_visibility_rules": [
                        {
                            "rule_id": "hide_answers",
                            "label": "Hide answers",
                            "selector_type": "marker_block",
                            "selector": "answer",
                            "action": "remove",
                        }
                    ],
                    "include_structured_intermediate": True,
                    "report_level": "detailed",
                }
            ],
        },
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    target = Path(tmp.name)
    try:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        scene = _materialize_legacy_scene(payload)
        assert scene.input_source_profile.accepted_formats == ["docx", "markdown"]
        assert scene.input_source_profile.require_material_package is True
        assert scene.input_source_profile.material_schema_id == "journal_materials_v1"
        assert scene.compliance_profile.profile_id == "journal_en"
        assert scene.compliance_profile.object_preflight.preservation_mode == "strict"
        assert scene.compliance_profile.object_preflight.block_on == [
            "ole_objects",
            "embedded_workbooks",
        ]
        assert scene.default_delivery_preset_id == "submission"
        assert scene.delivery_presets[0].artifacts.final_docx is True
        assert scene.delivery_presets[0].content_visibility_rules[0].selector == "answer"
        assert scene.delivery_presets[0].content_visibility_rules[0].action == "remove"
        assert scene.delivery_presets[0].include_structured_intermediate is True

        resolved = resolve_config(TemplateConfig(), scene)
        assert resolved.input_source_profile.material_schema_id == "journal_materials_v1"
        assert resolved.compliance_profile.rule_family == "journal_submission"
        assert resolved.default_delivery_preset_id == "submission"
        assert resolved.delivery_presets[0].preset_id == "submission"

        save_scene(scene, target)
        reloaded = load_scene(target)
        assert reloaded.input_source_profile.required_material_fields == [
            "author",
            "affiliation",
        ]
        assert reloaded.delivery_presets[0].artifacts.report_markdown is True
        assert reloaded.delivery_presets[0].content_visibility_rules[0].rule_id == "hide_answers"
    finally:
        target.unlink(missing_ok=True)


def test_builtin_scene_library_profiles_cover_current_matrix():
    from src.config.library import load_scene_from_library

    expected = {
        "custom": ("custom_basic", "final", False, "disabled"),
        "thesis": ("thesis_cn", "final", False, "formula_fragments_only"),
        "bidding": ("bid_package", "original", True, "disabled"),
        "official": ("official_document", "formal", True, "disabled"),
        "technical": ("long_document_publishing", "final_docx", False, "formula_fragments_only"),
        "report": ("general_report", "final", False, "disabled"),
    }

    for scene_id, (
        profile_id,
        default_preset_id,
        requires_materials,
        latex_policy,
    ) in expected.items():
        scene = load_scene_from_library(scene_id)
        preset_ids = [preset.preset_id for preset in scene.delivery_presets]

        assert scene.compliance_profile.profile_id == profile_id
        assert scene.default_delivery_preset_id == default_preset_id
        assert scene.default_delivery_preset_id in preset_ids
        assert scene.input_source_profile.require_material_package is requires_materials
        assert scene.input_source_profile.latex_policy == latex_policy
        assert scene.compliance_profile.object_preflight.enabled is True
        assert scene.delivery_presets


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
