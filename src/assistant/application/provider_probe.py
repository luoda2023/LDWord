"""Minimal provider handshake that never includes document or workspace content."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.assistant.runtime.provider_contract import (
    PROVIDER_DONE,
    PROVIDER_ERROR,
    PROVIDER_TEXT_DELTA,
    ModelGateway,
    ProviderRequest,
)


@dataclass(frozen=True, slots=True)
class ProviderProbeResult:
    success: bool
    message: str


def probe_provider(gateway: ModelGateway, *, model_id: str) -> ProviderProbeResult:
    request = ProviderRequest(
        request_id=uuid4().hex,
        model=model_id,
        system_prompt="This is a connection test. Reply with OK only.",
        messages=({"role": "user", "content": "OK"},),
        metadata={"purpose": "connection_test", "contains_document_content": False},
    )
    saw_done = False
    saw_text = False
    for event in gateway.stream(request):
        if event.type == PROVIDER_ERROR:
            return ProviderProbeResult(False, event.text or "provider_connection_failed")
        if event.type == PROVIDER_TEXT_DELTA:
            saw_text = saw_text or bool(event.text)
        elif event.type == PROVIDER_DONE:
            saw_done = True
            saw_text = saw_text or bool(event.text)
    if not saw_done:
        return ProviderProbeResult(False, "provider_stream_incomplete")
    if not saw_text:
        return ProviderProbeResult(False, "provider_returned_empty_response")
    return ProviderProbeResult(True, "provider_connection_ok")


__all__ = ["ProviderProbeResult", "probe_provider"]
