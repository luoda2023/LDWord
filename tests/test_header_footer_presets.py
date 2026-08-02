import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_user_header_footer_preset_can_be_saved_updated_and_deleted(tmp_path, monkeypatch):
    import src.config.header_footer_presets as presets
    from src.config.feature_configs import HeaderFooterConfig, PageNumberPhaseConfig

    monkeypatch.setattr(presets, "USER_PRESET_DIR", tmp_path)

    cfg = HeaderFooterConfig()
    cfg.header.enabled = False
    cfg.footer.enabled = False
    cfg.header.mode = "fixed"
    cfg.header.alignment = "right"
    cfg.header.fixed_text = "实验页眉"
    cfg.behavior.different_first_page = True
    cfg.behavior.different_odd_even_pages = True
    cfg.variants.first.header.mode = "fixed"
    cfg.variants.first.header.alignment = "left"
    cfg.variants.first.header.fixed_text = "首页页眉"
    cfg.variants.even.header.mode = "styleref"
    cfg.variants.even.header.alignment = "right"
    cfg.variants.even.footer.mode = "fixed"
    cfg.variants.even.footer.fixed_text = "偶数页"
    cfg.page_number_plan.even.visibility = "show"
    cfg.page_number_plan.even.template = "第 {page} 页"
    cfg.page_number_plan.even.alignment = "right"
    cfg.page_number_plan.phases = [
        PageNumberPhaseConfig(
            phase_id="body",
            selectors=["body"],
            number_format="decimal",
            start_mode="restart",
            start_value=3,
        )
    ]

    preset_id = presets.save_user_preset("我的页眉页脚", cfg)

    assert preset_id.startswith("user.")
    assert presets.is_user_preset(preset_id)
    assert presets.detect_matching_preset(cfg) == preset_id
    loaded = presets.get_preset_config(preset_id)
    assert loaded is not None
    assert loaded.header.enabled is False
    assert loaded.footer.enabled is False
    assert loaded.header.alignment == "right"
    assert loaded.header.fixed_text == "实验页眉"
    assert loaded.behavior.different_first_page is True
    assert loaded.behavior.different_odd_even_pages is True
    assert loaded.variants.first.header.alignment == "left"
    assert loaded.variants.first.header.fixed_text == "首页页眉"
    assert loaded.variants.even.header.mode == "styleref"
    assert loaded.variants.even.header.alignment == "right"
    assert loaded.variants.even.footer.mode == "fixed"
    assert loaded.variants.even.footer.fixed_text == "偶数页"
    assert loaded.page_number_plan.even.visibility == "show"
    assert loaded.page_number_plan.even.template == "第 {page} 页"
    assert loaded.page_number_plan.even.alignment == "right"
    assert loaded.page_number_plan.phases[0].start_value == 3

    cfg.header.fixed_text = "覆盖页眉"
    presets.save_user_preset("我的页眉页脚", cfg, preset_id=preset_id)
    assert presets.get_preset_config(preset_id).header.fixed_text == "覆盖页眉"

    assert presets.delete_user_preset(preset_id) is True
    assert presets.is_user_preset(preset_id) is False


def test_user_header_footer_preset_rejects_duplicate_display_names(tmp_path, monkeypatch):
    import src.config.header_footer_presets as presets
    from src.config.feature_configs import HeaderFooterConfig

    monkeypatch.setattr(presets, "USER_PRESET_DIR", tmp_path)

    with pytest.raises(ValueError, match="名称已存在"):
        presets.save_user_preset("论文默认", HeaderFooterConfig())

    presets.save_user_preset("我的页眉页脚", HeaderFooterConfig())
    with pytest.raises(ValueError, match="名称已存在"):
        presets.save_user_preset("我的页眉页脚", HeaderFooterConfig())


def test_legacy_user_preset_migrates_footer_page_modes_to_variant_strategy(
    tmp_path,
    monkeypatch,
):
    import src.config.header_footer_presets as presets

    monkeypatch.setattr(presets, "USER_PRESET_DIR", tmp_path)
    (tmp_path / "user.legacy.json").write_text(
        json.dumps(
            {
                "preset_id": "user.legacy",
                "name": "旧版奇偶页",
                "header_footer": {
                    "variants": {
                        "even": {
                            "footer": {
                                "mode": "page_number_with_text",
                                "fixed_text": "偶数页",
                                "template": "第 {page} 页",
                            }
                        }
                    },
                    "page_number_plan": {"enabled": True},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = presets.get_preset_config("user.legacy")

    assert loaded is not None
    assert loaded.variants.even.footer.mode == "fixed"
    assert loaded.variants.even.footer.fixed_text == "偶数页"
    assert loaded.page_number_plan.even.visibility == "show"
    assert loaded.page_number_plan.even.template == "第 {page} 页"

def test_loading_user_preset_removes_obsolete_implicit_scope_roles(
    tmp_path,
    monkeypatch,
):
    import src.config.header_footer_presets as presets
    from src.config.special_title_rules import special_title_selector

    monkeypatch.setattr(presets, "USER_PRESET_DIR", tmp_path)
    selector = special_title_selector("exact", "原创性声明")
    (tmp_path / "user.legacy.json").write_text(
        json.dumps(
            {
                "preset_id": "user.legacy",
                "name": "旧范围",
                "header_footer": {
                    "header": {
                        "hidden_selectors": [
                            "statement",
                            selector,
                        ]
                    },
                    "footer": {
                        "hidden_selectors": [
                            "authorization",
                            "front_note",
                        ]
                    },
                    "page_number_plan": {
                        "phases": [
                            {
                                "phase_id": "legacy",
                                "selectors": [
                                    "statement",
                                    selector,
                                    "body",
                                ],
                                "visible": True,
                                "number_format": "decimal",
                                "start_mode": "restart",
                                "start_value": 1,
                            }
                        ]
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = presets.get_preset_config("user.legacy")

    assert loaded is not None
    assert loaded.header.hidden_selectors == [selector]
    assert loaded.footer.hidden_selectors == []
    legacy_phase = next(
        phase
        for phase in loaded.page_number_plan.phases
        if phase.phase_id == "legacy"
    )
    assert legacy_phase.selectors == [selector, "body"]
