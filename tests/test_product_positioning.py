from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_public_product_positioning_matches_runtime_brand_and_modes():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert readme.startswith("# Alavette Form V1.0")
    assert "本地优先" in readme
    assert "不会自动上传" in readme
    assert "毕业论文 / 学位论文 `docx` 格式修订桌面工具" not in readme

    for mode_label in (
        "通用版",
        "试卷版",
        "论文版",
        "标书版",
        "公文版",
        "技术文档版",
        "报告版",
    ):
        assert mode_label in readme


def test_package_description_uses_public_brand_while_package_name_stays_compatible():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "lark-formatter"' in pyproject
    assert "Alavette Form V1.0" in pyproject
    assert "Lark Formatter V1.0" not in pyproject
