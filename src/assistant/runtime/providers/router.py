"""Resolve provider profiles into neutral gateways."""

from __future__ import annotations

from dataclasses import dataclass

from src.assistant.runtime.mock_provider import MockModelGateway
from src.assistant.runtime.provider_contract import ModelGateway
from src.assistant.runtime.providers.openai_compatible import OpenAICompatibleModelGateway
from src.assistant.runtime.providers.profiles import (
    ProviderProfileStore,
    provider_extra_body_with_model_defaults,
)
from src.assistant.runtime.providers.secrets import HybridSecretStore, ProviderSecretStore


class ProviderResolutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderReadiness:
    """Display-safe availability state without exposing provider secrets."""

    profile_id: str
    ready: bool
    reason_code: str = ""
    message: str = ""


class ProviderRouter:
    def __init__(
        self,
        *,
        profiles: ProviderProfileStore | None = None,
        secrets: ProviderSecretStore | None = None,
    ) -> None:
        self.profiles = profiles or ProviderProfileStore()
        self.secrets = secrets or HybridSecretStore()

    def readiness(self, profile_id: str) -> ProviderReadiness:
        """Inspect whether a profile can start a request without network I/O."""

        normalized = str(profile_id or "").strip()
        try:
            profile = self.profiles.get(normalized)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ProviderReadiness(
                normalized,
                False,
                "profile_unavailable",
                "模型配置不存在或配置文件不可读取",
            )
        if not profile.enabled:
            return ProviderReadiness(
                profile.profile_id,
                False,
                "profile_disabled",
                "模型配置已停用",
            )
        if profile.kind == "mock":
            return ProviderReadiness(profile.profile_id, True)
        if profile.kind != "openai_compatible":
            return ProviderReadiness(
                profile.profile_id,
                False,
                "provider_unsupported",
                "当前版本不支持该模型类型",
            )
        try:
            secret = str(self.secrets.get(profile.profile_id) or "").strip()
        except (OSError, RuntimeError, TypeError, ValueError):
            return ProviderReadiness(
                profile.profile_id,
                False,
                "credential_unavailable",
                "无法读取 API Key，请检查 Windows 凭据管理器",
            )
        if not secret:
            return ProviderReadiness(
                profile.profile_id,
                False,
                "missing_api_key",
                "缺少 API Key，请先在偏好设置中补齐",
            )
        return ProviderReadiness(profile.profile_id, True)

    def resolve(
        self,
        profile_id: str,
        *,
        timeout_seconds: float | None = None,
    ) -> ModelGateway:
        try:
            profile = self.profiles.get(profile_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            if profile_id == "mock-default":
                return MockModelGateway()
            raise ProviderResolutionError(str(exc)) from exc
        if not profile.enabled:
            raise ProviderResolutionError(f"Provider profile is disabled: {profile.label}")
        if profile.kind == "mock":
            return MockModelGateway()
        if profile.kind == "openai_compatible":
            try:
                secret = str(self.secrets.get(profile.profile_id) or "").strip()
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise ProviderResolutionError(
                    f"Provider credential is unavailable: {profile.label}"
                ) from exc
            if not secret:
                raise ProviderResolutionError(f"Provider profile has no API key: {profile.label}")
            return OpenAICompatibleModelGateway(
                model=profile.model_id,
                api_key=secret,
                base_url=profile.base_url,
                timeout_seconds=(
                    profile.timeout_seconds
                    if timeout_seconds is None
                    else min(profile.timeout_seconds, max(1.0, float(timeout_seconds)))
                ),
                extra_body=provider_extra_body_with_model_defaults(
                    profile.model_id,
                    profile.extra_body,
                ),
            )
        raise ProviderResolutionError(f"Unsupported provider kind: {profile.kind}")


__all__ = ["ProviderReadiness", "ProviderResolutionError", "ProviderRouter"]
