"""Provider-neutral request and streaming event contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.assistant.contracts.serialization import plain_data


PROVIDER_START = "start"
PROVIDER_TEXT_DELTA = "text_delta"
PROVIDER_DONE = "done"
PROVIDER_ERROR = "error"


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    request_id: str
    model: str
    system_prompt: str
    messages: tuple[dict[str, str], ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id or not self.model:
            raise ValueError("Provider request id and model are required")
        normalized: list[dict[str, str]] = []
        for item in self.messages:
            if not isinstance(item, Mapping):
                raise TypeError("Provider message must be a mapping")
            role = str(item.get("role") or "user")
            content = str(item.get("content") or "")
            normalized.append({"role": role, "content": content})
        object.__setattr__(self, "messages", tuple(normalized))
        object.__setattr__(self, "metadata", dict(plain_data(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProviderStreamEvent:
    type: str
    text: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in {PROVIDER_START, PROVIDER_TEXT_DELTA, PROVIDER_DONE, PROVIDER_ERROR}:
            raise ValueError(f"Unsupported provider event: {self.type!r}")
        object.__setattr__(self, "metadata", dict(plain_data(self.metadata)))


class ModelGateway(Protocol):
    def stream(self, request: ProviderRequest) -> Iterable[ProviderStreamEvent]: ...

    def cancel(self) -> bool: ...


def provider_messages(values: Sequence[Mapping[str, object]]) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "role": str(item.get("role") or "user"),
            "content": str(item.get("content") or ""),
        }
        for item in values
    )


__all__ = [name for name in globals() if name.startswith("PROVIDER_")] + [
    "ModelGateway",
    "ProviderRequest",
    "ProviderStreamEvent",
    "provider_messages",
]
