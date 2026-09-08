# -*- coding: utf-8 -*-
"""篇幅目标与截断续写的回归测试。

锁定契约：
* ``parse_length_target`` 识别「1000页」「30页」「2千页」「50万字」等
  篇幅表达，未提及篇幅时返回 None；
* ``allocate_chapter_targets`` 把总字数按章分摊且单章封顶；
* 章节长度指令注入后，章节 prompt 里出现本章目标字数；
* 真实 gateway 流式路径上 ``finish_reason=length`` 触发自动续写拼接。
"""

from __future__ import annotations

from src.assistant.application.length_targeting import (
    CHARS_PER_PAGE,
    allocate_chapter_targets,
    chapter_length_directive,
    parse_length_target,
    total_length_directive,
)
from src.assistant.application.content_generation_service import (
    MAX_CONTINUATION_ATTEMPTS,
    AssistantContentGenerationService,
    _continuation_tail,
)
from src.assistant.runtime.provider_contract import (
    PROVIDER_DONE,
    PROVIDER_TEXT_DELTA,
    ModelGateway,
    ProviderRequest,
    ProviderStreamEvent,
)


# ---------------------------------------------------------------- 解析
def test_parse_length_target_pages():
    total, matched = parse_length_target("我要写一篇1000页的施工组织设计")
    assert total == 1000 * CHARS_PER_PAGE
    assert "1000页" in matched


def test_parse_length_target_decimal_and_thousand_pages():
    assert parse_length_target("大约2.5千页")[0] == 2500 * CHARS_PER_PAGE
    assert parse_length_target("30页的标书")[0] == 30 * CHARS_PER_PAGE
    assert parse_length_target("1000 page doc")[0] == 1000 * CHARS_PER_PAGE


def test_parse_length_target_word_counts():
    assert parse_length_target("50万字的报告")[0] == 500000
    assert parse_length_target("约2千字")[0] == 2000
    assert parse_length_target("800字说明")[0] == 800


def test_parse_length_target_none_when_absent():
    assert parse_length_target("帮我写一份施工组织设计") is None


# ---------------------------------------------------------------- 分摊
def test_allocate_targets_even_split():
    targets = allocate_chapter_targets(70_000, 7)
    assert len(targets) == 7
    assert sum(t.target for t in targets) == 70_000
    assert all(t.minimum >= 600 for t in targets)


def test_allocate_targets_cap_per_chapter():
    # 1000 页 ≈ 70 万字，30 章 → 每章约 23333 字，超过 12000 封顶。
    targets = allocate_chapter_targets(700_000, 30)
    assert len(targets) == 30
    assert max(t.target for t in targets) <= 12000
    assert all(t.minimum < t.target < t.maximum for t in targets)


def test_allocate_targets_empty_inputs():
    assert allocate_chapter_targets(0, 5) == []
    assert allocate_chapter_targets(50_000, 0) == []


# ---------------------------------------------------------------- 指令
def test_chapter_length_directive_contains_target():
    targets = allocate_chapter_targets(70_000, 7)
    text = chapter_length_directive(targets[0], chapter_number=1, total_chapters=7)
    assert "第 1/7 章" in text
    assert f"约 {targets[0].target}" in text
    assert "篇幅" in text


def test_chapter_length_directive_empty_when_no_target():
    assert chapter_length_directive(None) == ""


def test_total_length_directive_mentions_pages():
    text = total_length_directive(1000 * CHARS_PER_PAGE, "1000页")
    assert "1000 页" in text
    assert "1000页" in text  # 用户原话保留


# ---------------------------------------------------------------- 续写
class _TruncatingGateway(ModelGateway):
    """首轮回 finish_reason=length，续写轮正常完成。"""

    def __init__(self) -> None:
        self.calls: list[ProviderRequest] = []

    def stream(self, request: ProviderRequest):
        self.calls.append(request)
        if len(self.calls) == 1:
            yield ProviderStreamEvent(PROVIDER_TEXT_DELTA, text="第一章正文" * 80)
            yield ProviderStreamEvent(
                PROVIDER_DONE,
                text="",
                metadata={"finish_reason": "length"},
            )
        else:
            yield ProviderStreamEvent(PROVIDER_TEXT_DELTA, text="续写的内容。")
            yield ProviderStreamEvent(PROVIDER_DONE, text="", metadata={})

    def cancel(self) -> bool:
        return False


class _NormalGateway(ModelGateway):
    def __init__(self) -> None:
        self.calls: list[ProviderRequest] = []

    def stream(self, request: ProviderRequest):
        self.calls.append(request)
        yield ProviderStreamEvent(PROVIDER_TEXT_DELTA, text="正常完成的一章。")
        yield ProviderStreamEvent(PROVIDER_DONE, text="", metadata={})

    def cancel(self) -> bool:
        return False


def _request() -> ProviderRequest:
    return ProviderRequest(
        request_id="r1",
        model="m",
        system_prompt="s",
        messages=({"role": "user", "content": "写第一章"},),
    )


def _collect(gateway: ModelGateway, request: ProviderRequest) -> str:
    return AssistantContentGenerationService._collect_provider_text(
        gateway, request, cancellation=None, delta_callback=None
    )


def test_collect_provider_text_continues_after_truncation():
    gateway = _TruncatingGateway()
    text = _collect(gateway, _request())
    # 两轮拼接，无重复锚点。
    assert text.startswith("第一章正文")
    assert text.endswith("续写的内容。")
    assert len(gateway.calls) == 2
    cont = gateway.calls[1]
    # 续写请求带 assistant 原文 + 续写指令。
    roles = [m["role"] for m in cont.messages]
    assert roles == ["user", "assistant", "user"]
    assert "截断" in cont.messages[-1]["content"]
    assert "第一章正文" in cont.messages[1]["content"]


def test_collect_provider_text_no_continuation_when_complete():
    gateway = _NormalGateway()
    text = _collect(gateway, _request())
    assert text == "正常完成的一章。"
    assert len(gateway.calls) == 1


def test_collect_provider_text_caps_continuation_attempts():
    class _AlwaysTruncated(ModelGateway):
        def __init__(self) -> None:
            self.calls = 0

        def stream(self, request: ProviderRequest):
            self.calls += 1
            yield ProviderStreamEvent(PROVIDER_TEXT_DELTA, text="截断片段。")
            yield ProviderStreamEvent(
                PROVIDER_DONE, text="", metadata={"finish_reason": "length"}
            )

        def cancel(self) -> bool:
            return False

    gateway = _AlwaysTruncated()
    text = _collect(gateway, _request())
    assert len(text) == len("截断片段。") * (MAX_CONTINUATION_ATTEMPTS + 1)
    assert gateway.calls == MAX_CONTINUATION_ATTEMPTS + 1


def test_continuation_tail_takes_last_window():
    tail = _continuation_tail("第一行\n第二行" + "尾" * 700)
    assert tail.startswith("尾")
    assert len(tail) <= 600
