from src.ui.panels.assets.token_naming import (
    is_numbered_series_name,
    next_numbered_name,
    next_series_name,
    numbered_series_prefix,
)


def test_numbered_material_names_share_collision_and_series_rules():
    assert next_numbered_name("文件", {"文件1", "文件3"}) == "文件2"
    assert next_numbered_name("图片组", {"图片组1", "图片组2"}) == "图片组3"
    assert next_series_name("资质证书09", {"资质证书10"}) == "资质证书11"
    assert next_series_name("正文", {"正文2"}) == "正文3"
    assert numbered_series_prefix("技术路线12") == "技术路线"
    assert numbered_series_prefix("技术路线") == "技术路线"
    assert is_numbered_series_name("技术路线2", "技术路线")
    assert not is_numbered_series_name("技术路线说明", "技术路线")
