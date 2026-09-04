"""Deterministic provider for UI demos, tests and offline operation."""

from __future__ import annotations

from collections.abc import Iterable

from src.assistant.runtime.provider_contract import (
    PROVIDER_DONE,
    PROVIDER_START,
    PROVIDER_TEXT_DELTA,
    ProviderRequest,
    ProviderStreamEvent,
)


class MockModelGateway:
    def __init__(self, reply: str | None = None, *, chunk_size: int = 18) -> None:
        self.reply = reply
        self.chunk_size = max(1, int(chunk_size))
        self._cancelled = False

    def stream(self, request: ProviderRequest) -> Iterable[ProviderStreamEvent]:
        self._cancelled = False
        metadata = {"provider": "mock", "model": request.model}
        yield ProviderStreamEvent(PROVIDER_START, metadata=metadata)
        reply = self.reply or self._default_reply(request)
        parts: list[str] = []
        for start in range(0, len(reply), self.chunk_size):
            if self._cancelled:
                return
            chunk = reply[start : start + self.chunk_size]
            parts.append(chunk)
            yield ProviderStreamEvent(PROVIDER_TEXT_DELTA, text=chunk, metadata=metadata)
        if not self._cancelled:
            yield ProviderStreamEvent(PROVIDER_DONE, text="".join(parts), metadata=metadata)

    def cancel(self) -> bool:
        was_active = not self._cancelled
        self._cancelled = True
        return was_active

    @staticmethod
    def _default_reply(request: ProviderRequest) -> str:
        latest = request.messages[-1]["content"] if request.messages else ""
        if str(request.metadata.get("purpose") or "") == "content_generation":
            return (
                "# 文档草稿\n\n"
                "## 目标\n\n"
                f"围绕以下需求形成可继续编辑的初稿：{latest}\n\n"
                "## 核心内容\n\n"
                "- 明确背景、目标与适用范围。\n"
                "- 按主题组织关键事实和行动建议。\n"
                "- 对需要补充的数据保留清晰占位，不虚构引用。\n\n"
                "## 下一步\n\n"
                "请审阅事实、名称和时间信息，再进入正式排版。\n"
            )
        return (
            "我已收到你的文档目标。下一步会先在本地匹配工作模式、场景和模板，"
            "形成可审阅计划；涉及读取正文、发送给云端模型或生成文件时，都会单独请求确认。\n\n"
            f"当前需求：{latest}"
        )


__all__ = ["MockModelGateway"]
