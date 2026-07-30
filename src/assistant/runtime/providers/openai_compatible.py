"""OpenAI-compatible Chat Completions streaming adapter.

This is a dependency-light extraction of the MIT-licensed Alavette Flow
adapter.  It uses the standard library, supports bounded pre-output retries,
and exposes no product-specific behavior.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from src.assistant.runtime.provider_contract import (
    MAX_PROVIDER_OUTPUT_CHARACTERS,
    PROVIDER_DONE,
    PROVIDER_ERROR,
    PROVIDER_START,
    PROVIDER_TEXT_DELTA,
    ProviderRequest,
    ProviderStreamEvent,
)


DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "https://api.openai.com/v1"
_MAX_SSE_PENDING_CHARACTERS = 1_000_000


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    model: str
    api_key: str
    base_url: str = DEFAULT_OPENAI_COMPATIBLE_BASE_URL
    timeout_seconds: float = 60.0
    extra_body: Mapping[str, Any] = field(default_factory=dict)
    retry_max_attempts: int = 3
    retry_backoff_seconds: float = 0.25
    retry_max_backoff_seconds: float = 2.0


@dataclass(frozen=True, slots=True)
class OpenAICompatibleHttpRequest:
    url: str
    headers: Mapping[str, str]
    payload: Mapping[str, Any]
    timeout_seconds: float


class OpenAICompatibleTransportError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = bool(retryable)


class OpenAICompatibleProtocolError(RuntimeError):
    pass


class _Cancelled(RuntimeError):
    pass


StreamingTransport = Callable[[OpenAICompatibleHttpRequest], Iterable[str | bytes]]


class OpenAICompatibleModelGateway:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = DEFAULT_OPENAI_COMPATIBLE_BASE_URL,
        timeout_seconds: float = 60.0,
        extra_body: Mapping[str, Any] | None = None,
        streaming_transport: StreamingTransport | None = None,
        retry_max_attempts: int = 3,
        retry_backoff_seconds: float = 0.25,
        retry_max_backoff_seconds: float = 2.0,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if not str(model or "").strip():
            raise ValueError("OpenAI-compatible provider requires a model")
        if not str(api_key or "").strip():
            raise ValueError("OpenAI-compatible provider requires an API key")
        self.config = OpenAICompatibleConfig(
            model=str(model),
            api_key=str(api_key),
            base_url=str(base_url or DEFAULT_OPENAI_COMPATIBLE_BASE_URL),
            timeout_seconds=float(timeout_seconds),
            extra_body=dict(extra_body or {}),
            retry_max_attempts=max(1, int(retry_max_attempts)),
            retry_backoff_seconds=max(0.0, float(retry_backoff_seconds)),
            retry_max_backoff_seconds=max(0.0, float(retry_max_backoff_seconds)),
        )
        self._transport = streaming_transport or _post_sse
        self._sleep = sleep or time.sleep
        self._cancel_event = threading.Event()
        self._active_response: Any = None
        self._active_response_lock = threading.Lock()

    def stream(self, request: ProviderRequest) -> Iterable[ProviderStreamEvent]:
        self._cancel_event.clear()
        metadata = {"provider": "openai_compatible", "model": self.config.model}
        yield ProviderStreamEvent(PROVIDER_START, metadata=metadata)
        emitted_delta = False
        parts: list[str] = []
        output_character_count = 0
        for attempt in range(1, self.config.retry_max_attempts + 1):
            response: Any = None
            try:
                if self._cancel_event.is_set():
                    raise _Cancelled("Provider request was cancelled")
                response = self._transport(self.http_request(request))
                self._set_active_response(response)
                _raise_for_stream_status(response)
                saw_done = False
                done_metadata = {**metadata, "attempt": attempt}
                for payload in _iter_sse_payloads(response):
                    if self._cancel_event.is_set():
                        raise _Cancelled("Provider request was cancelled")
                    if payload is _SSE_DONE:
                        saw_done = True
                        break
                    _raise_for_provider_error(payload)
                    done_metadata.update(_usage_metadata(payload))
                    text = _extract_delta_text(payload)
                    if text:
                        output_character_count += len(text)
                        if output_character_count > MAX_PROVIDER_OUTPUT_CHARACTERS:
                            raise OpenAICompatibleProtocolError(
                                "Provider output exceeded the configured character limit"
                            )
                        emitted_delta = True
                        parts.append(text)
                        yield ProviderStreamEvent(
                            PROVIDER_TEXT_DELTA,
                            text=text,
                            metadata={**metadata, "attempt": attempt},
                        )
                if not saw_done:
                    raise OpenAICompatibleProtocolError("Provider stream ended before [DONE]")
                yield ProviderStreamEvent(PROVIDER_DONE, text="".join(parts), metadata=done_metadata)
                return
            except Exception as exc:
                if isinstance(exc, _Cancelled) or self._cancel_event.is_set():
                    yield ProviderStreamEvent(
                        PROVIDER_ERROR,
                        text="Provider request was cancelled",
                        metadata={**metadata, "cancelled": True, "attempt": attempt},
                    )
                    return
                retryable = _is_retryable(exc)
                if retryable and not emitted_delta and attempt < self.config.retry_max_attempts:
                    delay = min(
                        self.config.retry_backoff_seconds * (2 ** max(0, attempt - 1)),
                        self.config.retry_max_backoff_seconds,
                    )
                    if delay:
                        self._sleep(delay)
                    continue
                yield ProviderStreamEvent(
                    PROVIDER_ERROR,
                    text=self._safe_error_text(
                        str(exc) or "OpenAI-compatible provider failed"
                    ),
                    metadata={
                        **metadata,
                        "attempt": attempt,
                        "retryable": retryable,
                        "retry_exhausted": bool(retryable and attempt >= self.config.retry_max_attempts),
                    },
                )
                return
            finally:
                if response is not None:
                    self._release_active_response(response)
                    _close_response(response)

    def cancel(self) -> bool:
        self._cancel_event.set()
        with self._active_response_lock:
            response = self._active_response
        if response is None:
            return False
        _close_response(response)
        return True

    def http_request(self, request: ProviderRequest) -> OpenAICompatibleHttpRequest:
        messages: list[dict[str, str]] = []
        if request.system_prompt.strip():
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(dict(item) for item in request.messages)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
        }
        payload.update(dict(self.config.extra_body))
        payload.update({"model": self.config.model, "messages": messages, "stream": True})
        return OpenAICompatibleHttpRequest(
            url=_chat_completions_url(self.config.base_url),
            headers={
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            payload=payload,
            timeout_seconds=self.config.timeout_seconds,
        )

    def _set_active_response(self, response: Any) -> None:
        with self._active_response_lock:
            self._active_response = response

    def _safe_error_text(self, value: str) -> str:
        text = str(value or "")
        secret = self.config.api_key
        return text.replace(secret, "<redacted>") if secret else text

    def _release_active_response(self, response: Any) -> None:
        with self._active_response_lock:
            if self._active_response is response:
                self._active_response = None


def _chat_completions_url(base_url: str) -> str:
    normalized = str(base_url or DEFAULT_OPENAI_COMPATIBLE_BASE_URL).rstrip("/")
    return normalized if normalized.endswith("/chat/completions") else f"{normalized}/chat/completions"


def _post_sse(http_request: OpenAICompatibleHttpRequest) -> Iterable[str | bytes]:
    body = json.dumps(dict(http_request.payload)).encode("utf-8")
    request = urllib_request.Request(
        http_request.url,
        data=body,
        headers=dict(http_request.headers),
        method="POST",
    )
    try:
        return urllib_request.urlopen(request, timeout=http_request.timeout_seconds)
    except urllib_error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise OpenAICompatibleTransportError(
            _provider_error_message(text) or f"Provider HTTP {exc.code}",
            status_code=int(exc.code),
            retryable=_retryable_status(int(exc.code)),
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise OpenAICompatibleTransportError("Provider request timed out", retryable=True) from exc
    except urllib_error.URLError as exc:
        raise OpenAICompatibleTransportError(
            f"Provider connection failed: {exc.reason}", retryable=True
        ) from exc


_SSE_DONE = object()


def _iter_sse_payloads(response: Iterable[str | bytes]) -> Iterator[Mapping[str, Any] | object]:
    data_lines: list[str] = []
    for line in _decoded_sse_lines(response):
        if line == "":
            if data_lines:
                yield _parse_sse_data("\n".join(data_lines))
                data_lines.clear()
            continue
        if line.startswith(":") or line.startswith(("event:", "id:", "retry:")):
            continue
        if line.startswith("data:"):
            value = line[5:]
            data_lines.append(value[1:] if value.startswith(" ") else value)
            continue
        raise OpenAICompatibleProtocolError(f"Malformed SSE field: {line[:80]}")
    if data_lines:
        yield _parse_sse_data("\n".join(data_lines))


def _decoded_sse_lines(chunks: Iterable[str | bytes]) -> Iterator[str]:
    pending = ""
    for chunk in chunks:
        if isinstance(chunk, bytes):
            text = chunk.decode("utf-8", errors="replace")
        elif isinstance(chunk, str):
            text = chunk
        else:
            raise OpenAICompatibleProtocolError("Provider returned a non-text SSE chunk")
        pending += text
        if len(pending) > _MAX_SSE_PENDING_CHARACTERS and "\n" not in pending:
            raise OpenAICompatibleProtocolError(
                "Provider returned an oversized SSE line"
            )
        while "\n" in pending:
            line, pending = pending.split("\n", 1)
            yield line[:-1] if line.endswith("\r") else line
    if pending:
        yield pending[:-1] if pending.endswith("\r") else pending


def _parse_sse_data(data: str) -> Mapping[str, Any] | object:
    raw = str(data).strip()
    if raw == "[DONE]":
        return _SSE_DONE
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpenAICompatibleProtocolError("Provider returned malformed SSE JSON") from exc
    if not isinstance(payload, Mapping):
        raise OpenAICompatibleProtocolError("Provider returned non-object SSE data")
    return payload


def _extract_delta_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, Mapping):
        return ""
    delta = first.get("delta")
    if isinstance(delta, Mapping):
        content = delta.get("content")
        if isinstance(content, str):
            return content
    return ""


def _usage_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if payload.get("id"):
        metadata["response_id"] = str(payload["id"])
    if isinstance(payload.get("usage"), Mapping):
        metadata["usage"] = dict(payload["usage"])
    return metadata


def _raise_for_provider_error(payload: Mapping[str, Any]) -> None:
    error = payload.get("error")
    if not error:
        return
    if isinstance(error, Mapping):
        message = str(error.get("message") or error.get("code") or "Provider error")
    else:
        message = str(error)
    raise OpenAICompatibleTransportError(message, retryable=False)


def _raise_for_stream_status(response: Any) -> None:
    status = getattr(response, "status", None)
    if status is None and callable(getattr(response, "getcode", None)):
        status = response.getcode()
    if status is not None and int(status) >= 400:
        raise OpenAICompatibleTransportError(
            f"Provider HTTP {int(status)}",
            status_code=int(status),
            retryable=_retryable_status(int(status)),
        )


def _retryable_status(status: int) -> bool:
    return status == 429 or 500 <= status <= 599


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, OpenAICompatibleTransportError):
        return exc.retryable
    return isinstance(exc, (TimeoutError, socket.timeout, ConnectionError, urllib_error.URLError))


def _close_response(response: Any) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def _provider_error_message(text: str) -> str:
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError:
        return str(text or "").strip()
    if not isinstance(payload, Mapping):
        return str(text or "").strip()
    error = payload.get("error")
    if isinstance(error, Mapping):
        return str(error.get("message") or error.get("code") or "").strip()
    return str(error or "").strip()


__all__ = [
    "DEFAULT_OPENAI_COMPATIBLE_BASE_URL",
    "OpenAICompatibleConfig",
    "OpenAICompatibleHttpRequest",
    "OpenAICompatibleModelGateway",
    "OpenAICompatibleProtocolError",
    "OpenAICompatibleTransportError",
]
