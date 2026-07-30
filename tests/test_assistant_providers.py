from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from src.assistant.application.provider_probe import probe_provider
from src.assistant.runtime.mock_provider import MockModelGateway
from src.assistant.runtime.provider_contract import (
    PROVIDER_DONE,
    PROVIDER_ERROR,
    PROVIDER_TEXT_DELTA,
    ProviderRequest,
)
from src.assistant.runtime.providers.openai_compatible import (
    OpenAICompatibleModelGateway,
    OpenAICompatibleTransportError,
)
from src.assistant.runtime.providers.profiles import ProviderProfile, ProviderProfileStore
from src.assistant.runtime.providers.router import ProviderResolutionError, ProviderRouter
from src.assistant.runtime.providers.secrets import EnvironmentSecretStore, MemorySecretStore


def _request() -> ProviderRequest:
    return ProviderRequest(
        request_id="request-1",
        model="ignored-by-profile",
        system_prompt="只输出可审阅计划",
        messages=({"role": "user", "content": "统一格式"},),
    )


def test_profile_store_keeps_secret_out_of_json(tmp_path):
    path = tmp_path / "providers.json"
    store = ProviderProfileStore(path)
    profile = ProviderProfile(
        profile_id="cloud-main",
        label="云端模型",
        kind="openai_compatible",
        model_id="example-model",
        base_url="https://example.invalid/v1",
    )

    store.upsert(profile)

    text = path.read_text(encoding="utf-8")
    assert "cloud-main" in text
    assert "api_key" not in text
    assert store.get("cloud-main") == profile
    assert store.get("mock-default").kind == "mock"


def test_environment_secret_store_uses_profile_scoped_name():
    store = EnvironmentSecretStore({"ALAVETTE_FORM_AI_KEY_CLOUD_MAIN": "secret-value"})
    assert store.get("cloud-main") == "secret-value"


def test_provider_router_resolves_mock_without_secret(tmp_path):
    router = ProviderRouter(
        profiles=ProviderProfileStore(tmp_path / "profiles.json"),
        secrets=MemorySecretStore(),
    )
    assert isinstance(router.resolve("mock-default"), MockModelGateway)


def test_corrupt_profile_store_still_allows_builtin_offline_mock(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{not-json", encoding="utf-8")
    router = ProviderRouter(
        profiles=ProviderProfileStore(path),
        secrets=MemorySecretStore(),
    )

    assert isinstance(router.resolve("mock-default"), MockModelGateway)


def test_provider_router_fails_closed_when_cloud_secret_is_missing(tmp_path):
    profiles = ProviderProfileStore(tmp_path / "profiles.json")
    profiles.upsert(
        ProviderProfile(
            profile_id="cloud-main",
            label="云端模型",
            kind="openai_compatible",
            model_id="example-model",
            base_url="https://example.invalid/v1",
        )
    )
    router = ProviderRouter(profiles=profiles, secrets=MemorySecretStore())

    with pytest.raises(ProviderResolutionError, match="no API key"):
        router.resolve("cloud-main")


def test_provider_readiness_is_local_safe_and_tracks_secret_state(tmp_path):
    profiles = ProviderProfileStore(tmp_path / "profiles.json")
    profiles.upsert(
        ProviderProfile(
            profile_id="cloud-ready-check",
            label="公司模型",
            kind="openai_compatible",
            model_id="example-model",
            base_url="https://example.invalid/v1",
        )
    )
    secrets = MemorySecretStore()
    router = ProviderRouter(profiles=profiles, secrets=secrets)

    missing = router.readiness("cloud-ready-check")
    assert missing.ready is False
    assert missing.reason_code == "missing_api_key"
    assert "API Key" in missing.message

    secrets.set("cloud-ready-check", "secret-value")
    ready = router.readiness("cloud-ready-check")
    assert ready.ready is True
    assert ready.reason_code == ""


def test_openai_compatible_stream_parses_sse_and_never_emits_secret():
    captured = []

    def transport(request):
        captured.append(request)
        return [
            b'data: {"id":"resp-1","choices":[{"delta":{"content":"\xe8\xae\xa1\xe5\x88\x92"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"\xe5\xae\x8c\xe6\x88\x90"}}],"usage":{"total_tokens":3}}\n\n',
            b"data: [DONE]\n\n",
        ]

    gateway = OpenAICompatibleModelGateway(
        model="example-model",
        api_key="super-secret",
        base_url="https://example.invalid/v1",
        streaming_transport=transport,
    )

    events = list(gateway.stream(_request()))

    assert [event.text for event in events if event.type == PROVIDER_TEXT_DELTA] == ["计划", "完成"]
    assert events[-1].type == PROVIDER_DONE
    assert events[-1].text == "计划完成"
    assert captured[0].url == "https://example.invalid/v1/chat/completions"
    assert captured[0].headers["Authorization"] == "Bearer super-secret"
    public_events = json.dumps(
        [{"text": event.text, "metadata": dict(event.metadata)} for event in events],
        ensure_ascii=False,
    )
    assert "super-secret" not in public_events


def test_provider_configuration_reaches_real_http_sse_boundary(tmp_path):
    captured: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - stdlib callback name
            size = int(self.headers.get("Content-Length", "0"))
            captured["path"] = self.path
            captured["authorization"] = self.headers.get("Authorization")
            captured["payload"] = json.loads(self.rfile.read(size).decode("utf-8"))
            body = (
                'data: {"id":"probe-1","choices":[{"delta":{"content":"OK"}}]}\n\n'
                "data: [DONE]\n\n"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        profile = ProviderProfile(
            profile_id="loopback",
            label="Loopback",
            kind="openai_compatible",
            model_id="document-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
        )
        profiles = ProviderProfileStore(tmp_path / "profiles.json")
        profiles.upsert(profile)
        router = ProviderRouter(
            profiles=profiles,
            secrets=MemorySecretStore({"loopback": "loopback-secret"}),
        )

        result = probe_provider(
            router.resolve("loopback", timeout_seconds=2.0),
            model_id=profile.model_id,
        )

        assert result.success is True
        assert captured["path"] == "/v1/chat/completions"
        assert captured["authorization"] == "Bearer loopback-secret"
        payload = captured["payload"]
        assert isinstance(payload, dict)
        assert payload["model"] == "document-model"
        assert payload["stream"] is True
        assert payload["messages"][-1] == {"role": "user", "content": "OK"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_openai_compatible_retries_only_before_visible_delta():
    attempts = []
    sleeps = []

    def transport(_request):
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            raise OpenAICompatibleTransportError("rate limited", status_code=429, retryable=True)
        return [
            'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n',
            "data: [DONE]\n\n",
        ]

    gateway = OpenAICompatibleModelGateway(
        model="example-model",
        api_key="secret",
        streaming_transport=transport,
        sleep=sleeps.append,
        retry_backoff_seconds=0.1,
    )

    events = list(gateway.stream(_request()))

    assert attempts == [1, 2]
    assert sleeps == [0.1]
    assert events[-1].type == PROVIDER_DONE


def test_openai_compatible_reports_protocol_failure_after_delta_without_retry():
    attempts = []

    def transport(_request):
        attempts.append(1)
        return ['data: {"choices":[{"delta":{"content":"partial"}}]}\n\n']

    gateway = OpenAICompatibleModelGateway(
        model="example-model",
        api_key="secret",
        streaming_transport=transport,
    )

    events = list(gateway.stream(_request()))

    assert attempts == [1]
    assert events[-1].type == PROVIDER_ERROR
    assert "before [DONE]" in events[-1].text


def test_openai_compatible_redacts_api_key_from_provider_errors():
    def transport(_request):
        raise OpenAICompatibleTransportError(
            "request rejected for super-secret",
            retryable=False,
        )

    gateway = OpenAICompatibleModelGateway(
        model="example-model",
        api_key="super-secret",
        streaming_transport=transport,
    )

    events = list(gateway.stream(_request()))

    assert events[-1].type == PROVIDER_ERROR
    assert "super-secret" not in events[-1].text
    assert "<redacted>" in events[-1].text
