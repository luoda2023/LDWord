"""
Phase 3 冒烟测试 — ✍️ 填充与替换模块 (3 个)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_entity_fill_import():
    """M11: entity_fill 导入+实例化"""
    from src.modules.fill.entity_fill import EntityFillModule

    mod = EntityFillModule()
    assert mod.meta.name == "entity_fill"
    assert mod.meta.category == "fill"
    assert "entity_values" in mod.meta.provides
    print("  ✅ M11 entity_fill 导入正常")


def test_source_fill_import():
    """M12: source_fill 导入+实例化"""
    from src.modules.fill.source_fill import SourceFillModule

    mod = SourceFillModule()
    assert mod.meta.name == "source_fill"
    assert "source_values" in mod.meta.provides
    print("  ✅ M12 source_fill 导入正常")


def test_placeholder_replace_import():
    """M13: placeholder_replace 导入+实例化"""
    from src.modules.fill.placeholder_replace import PlaceholderReplaceModule

    mod = PlaceholderReplaceModule()
    assert mod.meta.name == "placeholder_replace"
    assert mod.meta.category == "fill"
    print("  ✅ M13 placeholder_replace 导入正常")


def test_all_fill_meta():
    """验证 3 模块 meta 完整性"""
    from src.modules.fill.entity_fill import EntityFillModule
    from src.modules.fill.source_fill import SourceFillModule
    from src.modules.fill.placeholder_replace import PlaceholderReplaceModule

    modules = [EntityFillModule(), SourceFillModule(), PlaceholderReplaceModule()]
    for mod in modules:
        assert mod.meta.name
        assert mod.meta.description
        assert mod.meta.category == "fill"

    names = [m.meta.name for m in modules]
    assert len(names) == len(set(names))
    print(f"  ✅ 3 个模块 meta 验证通过: {names}")


if __name__ == "__main__":
    print("Phase 3 冒烟测试 — ✍️ 填充与替换")
    print("=" * 50)

    test_entity_fill_import()
    test_source_fill_import()
    test_placeholder_replace_import()
    test_all_fill_meta()

    print("=" * 50)
    print("✅ 填充与替换 3 个模块全部通过！")
