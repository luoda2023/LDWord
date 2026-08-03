from __future__ import annotations

import builtins
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import ModuleType

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
from src.assistant.runtime.providers.profiles import (
    GLM_5_2_MAX_OUTPUT_TOKENS,
    ProviderProfile,
    ProviderProfileStore,
)
from src.assistant.runtime.providers.router import (
    ProviderResolutionError,
    ProviderRouter,
)
from src.assistant.runtime.providers.secrets import (
    EnvironmentSecretStore,
    MemorySecretStore,
    WindowsCredentialSecretStore,
)


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


def test_profile_store_persists_active_profile_and_migrates_legacy_selection(tmp_path):
    path = tmp_path / "providers.json"
    store = ProviderProfileStore(path)
    first = ProviderProfile(
        profile_id="cloud-first",
        label="云端模型一",
        kind="openai_compatible",
        model_id="example-model-1",
        base_url="https://example.invalid/v1",
    )
    second = ProviderProfile(
        profile_id="cloud-second",
        label="云端模型二",
        kind="openai_compatible",
        model_id="example-model-2",
        base_url="https://example.invalid/v1",
    )

    store.upsert(first)
    store.upsert(second, make_active=True)

    assert ProviderProfileStore(path).active_profile_id() == "cloud-second"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["active_profile_id"] == "cloud-second"

    payload.pop("active_profile_id")
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert ProviderProfileStore(path).active_profile_id() == "cloud-second"

    store.set_active_profile_id("cloud-first")
    assert ProviderProfileStore(path).active_profile_id() == "cloud-first"
    store.delete("cloud-first")
    assert ProviderProfileStore(path).active_profile_id() == "cloud-second"


@pytest.mark.parametrize(
    "extra_body",
    (
        {"api_key": "secret"},
        {"Authorization": "Bearer secret"},
        {"vendor": {"access_token": "secret"}},
    ),
)
def test_provider_profile_rejects_secrets_hidden_in_extra_body(extra_body):
    with pytest.raises(ValueError, match="secret-like key"):
        ProviderProfile(
            profile_id="unsafe-extra-body",
            label="Unsafe",
            kind="openai_compatible",
            model_id="example-model",
            base_url="https://example.invalid/v1",
            extra_body=extra_body,
        )


@pytest.mark.parametrize(
    "base_url",
    (
        "http://provider.example.invalid/v1",
        "http://192.0.2.10/v1",
        "http://localhost.example.invalid/v1",
    ),
)
def test_provider_profile_rejects_plain_http_outside_loopback(base_url):
    with pytest.raises(ValueError, match="only for localhost or loopback"):
        ProviderProfile(
            profile_id="insecure",
            label="Insecure",
            kind="openai_compatible",
            model_id="example-model",
            base_url=base_url,
        )


def test_glm_5_2_defaults_to_official_max_output_tokens(tmp_path):
    profiles = ProviderProfileStore(tmp_path / "providers.json")
    profiles.upsert(
        ProviderProfile(
            profile_id="glm-max",
            label="GLM 5.2",
            kind="openai_compatible",
            model_id="glm-5.2",
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        )
    )
    router = ProviderRouter(
        profiles=profiles,
        secrets=MemorySecretStore({"glm-max": "secret"}),
    )

    gateway = router.resolve("glm-max")

    assert gateway.config.extra_body["max_tokens"] == GLM_5_2_MAX_OUTPUT_TOKENS


def test_glm_5_2_preserves_explicit_max_output_tokens(tmp_path):
    profiles = ProviderProfileStore(tmp_path / "providers.json")
    profiles.upsert(
        ProviderProfile(
            profile_id="glm-explicit",
            label="GLM 5.2 explicit",
            kind="openai_compatible",
            model_id="glm-5.2",
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            extra_body={"max_tokens": 4096},
        )
    )
    router = ProviderRouter(
        profiles=profiles,
        secrets=MemorySecretStore({"glm-explicit": "secret"}),
    )

    gateway = router.resolve("glm-explicit")

    assert gateway.config.extra_body["max_tokens"] == 4096


@pytest.mark.parametrize(
    "base_url",
    (
        "http://localhost:11434/v1",
        "http://127.0.0.1:11434/v1",
        "http://[::1]:11434/v1",
    ),
)
def test_provider_profile_allows_plain_http_only_on_loopback(base_url):
    profile = ProviderProfile(
        profile_id="loopback-policy",
        label="Loopback",
        kind="openai_compatible",
        model_id="example-model",
        base_url=base_url,
    )

    assert profile.base_url == base_url


def test_environment_secret_store_uses_profile_scoped_name():
    store = EnvironmentSecretStore({"ALAVETTE_FORM_AI_KEY_CLOUD_MAIN": "secret-value"})
    assert store.get("cloud-main") == "secret-value"


def test_windows_credential_store_passes_unicode_blob_to_pywin32(monkeypatch):
    captured: dict[str, object] = {}
    fake_win32cred = ModuleType("win32cred")
    fake_win32cred.CRED_TYPE_GENERIC = 1
    fake_win32cred.CRED_PERSIST_LOCAL_MACHINE = 2

    def cred_write(credential, flags):
        captured["credential"] = dict(credential)
        captured["flags"] = flags

    fake_win32cred.CredWrite = cred_write
    monkeypatch.setitem(sys.modules, "win32cred", fake_win32cred)
    monkeypatch.setattr(
        WindowsCredentialSecretStore,
        "available",
        property(lambda _self: True),
    )

    WindowsCredentialSecretStore().set("cloud-main", "secret-密钥")

    credential = captured["credential"]
    assert isinstance(credential, dict)
    assert credential["CredentialBlob"] == "secret-密钥"
    assert isinstance(credential["CredentialBlob"], str)
    assert captured["flags"] == 0


def test_windows_credential_store_decodes_pywin32_utf16_blob(monkeypatch):
    fake_win32cred = ModuleType("win32cred")
    fake_win32cred.CRED_TYPE_GENERIC = 1
    fake_win32cred.CredRead = lambda _target, _kind: {
        "CredentialBlob": "secret-密钥".encode("utf-16-le")
    }
    fake_pywintypes = ModuleType("pywintypes")
    fake_pywintypes.error = RuntimeError
    monkeypatch.setitem(sys.modules, "win32cred", fake_win32cred)
    monkeypatch.setitem(sys.modules, "pywintypes", fake_pywintypes)
    monkeypatch.setattr(
        WindowsCredentialSecretStore,
        "available",
        property(lambda _self: True),
    )

    assert WindowsCredentialSecretStore().get("cloud-main") == "secret-密钥"


def test_windows_credential_store_requires_timezone_runtime(monkeypatch):
    real_import = builtins.__import__

    def import_without_timezone(name, *args, **kwargs):
        if name == "win32timezone":
            raise ModuleNotFoundError("No module named 'win32timezone'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_timezone)

    assert WindowsCredentialSecretStore().available is False


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


def test_provider_readiness_degrades_when_credential_dependency_is_missing(tmp_path):
    class MissingDependencySecretStore:
        def get(self, _profile_id):
            raise ModuleNotFoundError("No module named 'win32timezone'")

    profiles = ProviderProfileStore(tmp_path / "profiles.json")
    profiles.upsert(
        ProviderProfile(
            profile_id="cloud-missing-runtime",
            label="Cloud",
            kind="openai_compatible",
            model_id="example-model",
            base_url="https://example.invalid/v1",
        )
    )
    router = ProviderRouter(
        profiles=profiles,
        secrets=MissingDependencySecretStore(),
    )

    readiness = router.readiness("cloud-missing-runtime")

    assert readiness.ready is False
    assert readiness.reason_code == "credential_unavailable"


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
        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            captured["path"] = self.path
            captured["authorization"] = self.headers.get("Authorization")
            captured["payload"] = json.loads(self.rfile.read(size).decode("utf-8"))
            body = (
                b'data: {"id":"probe-1","choices":[{"delta":{"content":"OK"}}]}\n\n'
                b"data: [DONE]\n\n"
            )
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


def test_openai_compatible_blocks_authorized_cross_origin_redirect():
    target_requests: list[str | None] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(size)
            target_requests.append(self.headers.get("Authorization"))
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            # Consume the request body before replying.  On Windows, closing a
            # POST socket with unread bytes can surface as WSAECONNABORTED
            # before urllib receives the redirect response, making this
            # credential-boundary test nondeterministic.
            size = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(size)
            self.send_response(307)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{target.server_port}/v1/chat/completions",
            )
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    source = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    threads = [
        Thread(target=target.serve_forever, daemon=True),
        Thread(target=source.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        gateway = OpenAICompatibleModelGateway(
            model="example-model",
            api_key="must-not-cross-origin",
            base_url=f"http://127.0.0.1:{source.server_port}/v1",
            retry_max_attempts=1,
        )

        events = list(gateway.stream(_request()))

        assert events[-1].type == PROVIDER_ERROR
        assert "redirect changed origin" in events[-1].text
        assert "must-not-cross-origin" not in events[-1].text
        assert target_requests == []
    finally:
        source.shutdown()
        target.shutdown()
        source.server_close()
        target.server_close()
        for thread in threads:
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
