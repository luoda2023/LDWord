"""
Phase 3 冒烟测试 — 🔧 插入与特殊模块 (6 个)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_image_insertion():
    from src.modules.insert.image_insertion import ImageInsertionModule
    mod = ImageInsertionModule()
    assert mod.meta.name == "image_insertion"
    assert mod.meta.category == "insert"
    assert mod.meta.modifies_structure is True
    assert "inserted_images" in mod.meta.provides
    print("  ✅ M14 image_insertion 导入正常")


def test_watermark():
    from src.modules.insert.watermark import WatermarkModule
    mod = WatermarkModule()
    assert mod.meta.name == "watermark"
    assert mod.meta.category == "insert"
    print("  ✅ M15 watermark 导入正常")


def test_chem_typography():
    from src.modules.special.chem_typography import ChemTypographyModule
    mod = ChemTypographyModule()
    assert mod.meta.name == "chem_typography"
    assert mod.meta.category == "special"
    assert "paragraph_style" in mod.meta.soft_after
    print("  ✅ M16 chem_typography 导入正常")


def test_md_cleanup():
    from src.modules.validate.md_cleanup import MdCleanupModule
    mod = MdCleanupModule()
    assert mod.meta.name == "md_cleanup"
    assert mod.meta.category == "validate"
    print("  ✅ M17 md_cleanup 导入正常")


def test_equation_table_format():
    from src.modules.special.equation_table_format import EquationTableFormatModule
    mod = EquationTableFormatModule()
    assert mod.meta.name == "equation_table_format"
    assert mod.meta.category == "special"
    assert "table_format" in mod.meta.soft_after
    print("  ✅ M18 equation_table_format 导入正常")


def test_reference_format():
    from src.modules.special.reference_format import ReferenceFormatModule
    mod = ReferenceFormatModule()
    assert mod.meta.name == "reference_format"
    assert mod.meta.category == "special"
    assert "heading_recognition" in mod.meta.soft_after
    print("  ✅ M19 reference_format 导入正常")


def test_all_meta():
    from src.modules.insert.image_insertion import ImageInsertionModule
    from src.modules.insert.watermark import WatermarkModule
    from src.modules.special.chem_typography import ChemTypographyModule
    from src.modules.validate.md_cleanup import MdCleanupModule
    from src.modules.special.equation_table_format import EquationTableFormatModule
    from src.modules.special.reference_format import ReferenceFormatModule

    modules = [
        ImageInsertionModule(), WatermarkModule(),
        ChemTypographyModule(), MdCleanupModule(),
        EquationTableFormatModule(), ReferenceFormatModule(),
    ]
    names = set()
    for mod in modules:
        assert mod.meta.name
        assert mod.meta.description
        names.add(mod.meta.name)
    assert len(names) == 6
    print(f"  ✅ 6 个模块 meta 验证通过: {sorted(names)}")


if __name__ == "__main__":
    print("Phase 3 冒烟测试 — 🔧 插入与特殊")
    print("=" * 50)

    test_image_insertion()
    test_watermark()
    test_chem_typography()
    test_md_cleanup()
    test_equation_table_format()
    test_reference_format()
    test_all_meta()

    print("=" * 50)
    print("✅ 插入与特殊 6 个模块全部通过！")
