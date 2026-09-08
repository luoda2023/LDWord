"""OpenAI-compatible Chat Completions streaming adapter.

This is a dependency-light extraction of the MIT-licensed Alavette Flow
adapter.  It uses the standard library, supports bounded pre-output retries,
and exposes no product-specific behavior.
"""

from __future__ import annotations

import json
import select
import socket
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from src.assistant.runtime.provider_contract import (
    PROVIDER_DONE,
    PROVIDER_ERROR,
    PROVIDER_START,
    PROVIDER_TEXT_DELTA,
    ProviderRequest,
    ProviderStreamEvent,
)
from src.assistant.runtime.providers.endpoint_security import (
    provider_origin,
    validate_provider_endpoint,
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
            base_url=validate_provider_endpoint(
                str(base_url or DEFAULT_OPENAI_COMPATIBLE_BASE_URL)
            ),
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
                for payload in _iter_sse_payloads_cancellable(
                    response,
                    self._cancel_event.is_set,
                ):
                    if payload is _SSE_DONE:
                        saw_done = True
                        break
                    _raise_for_provider_error(payload)
                    done_metadata.update(_usage_metadata(payload))
                    done_metadata.update(_finish_reason_metadata(payload))
                    text = _extract_delta_text(payload)
                    if text:
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
        opener = urllib_request.build_opener(_CredentialSafeRedirectHandler())
        return opener.open(request, timeout=http_request.timeout_seconds)
    except urllib_error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise OpenAICompatibleTransportError(
            _provider_error_message(text) or f"Provider HTTP {exc.code}",
            status_code=int(exc.code),
            retryable=_retryable_status(int(exc.code)),
        ) from exc
    except TimeoutError as exc:
        raise OpenAICompatibleTransportError("Provider request timed out", retryable=True) from exc
    except urllib_error.URLError as exc:
        raise OpenAICompatibleTransportError(
            f"Provider connection failed: {exc.reason}", retryable=True
        ) from exc


class _CredentialSafeRedirectHandler(urllib_request.HTTPRedirectHandler):
    """Reject redirects that could move a Bearer credential to another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            source_origin = provider_origin(req.full_url)
            target_origin = provider_origin(newurl)
        except ValueError as exc:
            raise OpenAICompatibleTransportError(
                f"Provider redirect was rejected: {exc}",
                retryable=False,
            ) from exc
        if req.has_header("Authorization") and source_origin != target_origin:
            raise OpenAICompatibleTransportError(
                "Provider redirect changed origin while authorization was present",
                retryable=False,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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
            data_lines.append(value.removeprefix(" "))
            continue
        raise OpenAICompatibleProtocolError(f"Malformed SSE field: {line[:80]}")
    if data_lines:
        yield _parse_sse_data("\n".join(data_lines))


def _iter_sse_payloads_cancellable(
    response: Any,
    cancel: Callable[[], bool],
) -> Iterator[Mapping[str, Any] | object]:
    """Yield SSE payloads from a urllib response with prompt cancellation.

    A blocking ``read()`` on an http.client socket cannot be interrupted from
    another thread on Windows, which is why clicking stop could hang until the
    whole 60s socket timeout fired.  This reader drives the raw socket with a
    short ``select`` poll and checks ``cancel`` between polls, so a cancel is
    observed within ~0.2s.  It re-implements only the body framing urllib
    normally hides (chunked de-chunking when needed); HTTP handshake, headers
    and redirects stay urllib's job.
    """

    sock = _response_raw_socket(response)
    if sock is None:
        # No usable raw socket (some transports).  Fall back to the blocking
        # iterator; cancellation degrades to the socket timeout only.
        for payload in _iter_sse_payloads(response):
            yield payload
        return
    chunked = _response_is_chunked(response)
    framing = _ChunkedFraming() if chunked else _RawFraming()
    data_lines: list[str] = []

    for raw_line in framing.iter_lines(sock, cancel):
        if cancel():
            raise _Cancelled("Provider request was cancelled")
        line = raw_line.decode("utf-8", errors="replace").removesuffix("\r")
        if line == "":
            if data_lines:
                yield _parse_sse_data("\n".join(data_lines))
                data_lines.clear()
            continue
        if line.startswith(":") or line.startswith(("event:", "id:", "retry:")):
            continue
        if line.startswith("data:"):
            value = line[5:]
            data_lines.append(value.removeprefix(" "))
            continue
        raise OpenAICompatibleProtocolError(f"Malformed SSE field: {line[:80]}")
    if data_lines:
        yield _parse_sse_data("\n".join(data_lines))


def _response_raw_socket(response: Any) -> Any | None:
    try:
        return response.fp.raw._sock  # type: ignore[attr-defined]
    except Exception:
        return None


def _response_is_chunked(response: Any) -> bool:
    try:
        transfer = str(
            response.headers.get("Transfer-Encoding") or ""  # type: ignore[attr-defined]
        ).casefold()
    except Exception:
        return False
    return "chunked" in transfer


class _RawFraming:
    """Yield body lines from a non-chunked byte stream."""

    def iter_lines(self, sock: Any, cancel: Callable[[], bool]):
        buf = b""
        while True:
            r, _, _ = select.select([sock], [], [], 0.2)
            if not r:
                if cancel():
                    return
                continue
            try:
                chunk = sock.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                yield line


class _ChunkedFraming:
    """Yield body lines from an HTTP chunked byte stream."""

    def iter_lines(self, sock: Any, cancel: Callable[[], bool]):
        buf = b""
        size_remaining = 0
        while True:
            r, _, _ = select.select([sock], [], [], 0.2)
            if not r:
                if cancel():
                    return
                continue
            try:
                chunk = sock.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while True:
                if size_remaining == 0:
                    if b"\n" not in buf:
                        break
                    sizeline, buf = buf.split(b"\n", 1)
                    sizeline = sizeline.strip()
                    if not sizeline:
                        continue
                    try:
                        size_remaining = int(sizeline.split(b";")[0].strip(), 16)
                    except ValueError:
                        return
                    if size_remaining == 0:
                        return  # last-chunk
                else:
                    if len(buf) < size_remaining + 2:
                        break
                    body = buf[:size_remaining]
                    buf = buf[size_remaining + 2:]  # drop body + CRLF
                    size_remaining = 0
                    acc = body
                    while b"\n" in acc:
                        line, acc = acc.split(b"\n", 1)
                        yield line


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
            yield line.removesuffix("\r")
    if pending:
        yield pending.removesuffix("\r")


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


def _finish_reason_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Surface ``choices[0].finish_reason`` so callers can detect truncation."""
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, Mapping) and first.get("finish_reason"):
            return {"finish_reason": str(first["finish_reason"])}
    return {}


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
    if (
        isinstance(exc, OpenAICompatibleProtocolError)
        and str(exc) == "Provider stream ended before [DONE]"
    ):
        return True
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
