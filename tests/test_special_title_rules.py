import pytest

from src.config.special_title_rules import (
    match_special_title,
    parse_special_title_selector,
    special_title_selector,
    special_title_selector_options,
    validate_special_title_values,
)
from src.config.template import HeadingModelConfig


def test_special_title_rules_match_only_user_literals():
    exact = ["摘要", "目录"]
    prefixes = ["附", "附录"]

    exact_match = match_special_title(
        "1. 摘要",
        exact_values=exact,
        prefix_values=prefixes,
    )
    longest_prefix_match = match_special_title(
        "附录A 数据",
        exact_values=exact,
        prefix_values=prefixes,
    )
    exact_over_prefix = match_special_title(
        "附录A 数据",
        exact_values=[*exact, "附录A 数据"],
        prefix_values=prefixes,
    )

    assert exact_match is not None
    assert exact_match.kind == "exact"
    assert exact_match.value == "摘要"
    assert longest_prefix_match is not None
    assert longest_prefix_match.kind == "prefix"
    assert longest_prefix_match.value == "附录"
    assert exact_over_prefix is not None
    assert exact_over_prefix.kind == "exact"
    assert exact_over_prefix.value == "附录A 数据"
    assert (
        match_special_title(
            "Abstract",
            exact_values=exact,
            prefix_values=prefixes,
        )
        is None
    )


def test_special_title_selector_round_trips_case_and_spacing():
    selector = special_title_selector("exact", "Table of Contents")

    assert parse_special_title_selector(selector) == (
        "exact",
        "Table of Contents",
    )


def test_each_heading_model_item_becomes_one_scope_option():
    model = HeadingModelConfig(
        non_numbered_title_texts=["摘要", "目录"],
        non_numbered_prefixes=["附录", "附件"],
    )

    options = special_title_selector_options(model)

    assert [label for _selector, label in options] == [
        "摘要",
        "目录",
        "附录",
        "附件",
    ]
    assert len({selector for selector, _label in options}) == 4


@pytest.mark.parametrize(
    ("exact", "prefixes", "message"),
    [
        (["摘要", "摘要"], [], "完整标题中存在重复规则"),
        ([], ["附录", "附录"], "标题前缀中存在重复规则"),
        (["附录"], ["附录"], "不能同时作为完整标题和标题前缀"),
    ],
)
def test_duplicate_or_cross_category_rules_are_rejected(
    exact,
    prefixes,
    message,
):
    with pytest.raises(ValueError, match=message):
        validate_special_title_values(exact, prefixes)
