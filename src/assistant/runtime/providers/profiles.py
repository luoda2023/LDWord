"""Versioned provider profiles without embedded secrets."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.assistant.contracts.serialization import plain_data
from src.assistant.runtime.providers.endpoint_security import (
    validate_provider_endpoint,
)
from src.assistant.storage.paths import assistant_storage_root

PROVIDER_PROFILE_STORE_SCHEMA_VERSION = "form-provider-profiles-v1"
PROVIDER_KINDS = frozenset({"mock", "openai_compatible"})
PROVIDER_CONNECTION_STATUSES = frozenset({"local", "untested", "success", "failed"})
GLM_5_2_MAX_OUTPUT_TOKENS = 131_072
_SAFE_PROFILE_ID = re.compile(r"^[A-Za-z0-9_-]{1,96}$")
_SECRET_LIKE_EXTRA_BODY_KEY = re.compile(
    r"(?:^|[_-])(?:api[_-]?key|authorization|access[_-]?token|token|secret|password)(?:$|[_-])",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    profile_id: str
    label: str
    kind: str
    model_id: str
    base_url: str = ""
    timeout_seconds: float = 60.0
    enabled: bool = True
    extra_body: Mapping[str, Any] = field(default_factory=dict)
    connection_status: str = "untested"
    last_checked_at: str = ""
    last_check_message: str = ""

    def __post_init__(self) -> None:
        if not _SAFE_PROFILE_ID.fullmatch(str(self.profile_id or "")):
            raise ValueError("Unsafe provider profile id")
        if self.kind not in PROVIDER_KINDS:
            raise ValueError(f"Unsupported provider kind: {self.kind!r}")
        if not str(self.label or "").strip() or not str(self.model_id or "").strip():
            raise ValueError("Provider profile label and model_id are required")
        if float(self.timeout_seconds) <= 0:
            raise ValueError("Provider timeout must be positive")
        if self.connection_status not in PROVIDER_CONNECTION_STATUSES:
            raise ValueError(
                f"Unsupported provider connection status: {self.connection_status!r}"
            )
        if self.kind == "mock" and self.connection_status not in {"local", "success"}:
            raise ValueError(
                "Mock providers must use a local or success connection status"
            )
        if self.kind == "openai_compatible":
            validate_provider_endpoint(self.base_url)
        normalized_extra_body = dict(plain_data(self.extra_body))
        _reject_secret_like_extra_body(normalized_extra_body)
        object.__setattr__(self, "extra_body", normalized_extra_body)

    @property
    def requires_secret(self) -> bool:
        return self.kind != "mock"

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "label": self.label,
            "kind": self.kind,
            "model_id": self.model_id,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "enabled": self.enabled,
            "extra_body": dict(self.extra_body),
            "connection_status": self.connection_status,
            "last_checked_at": self.last_checked_at,
            "last_check_message": self.last_check_message,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ProviderProfile:
        return cls(
            profile_id=str(value.get("profile_id") or ""),
            label=str(value.get("label") or ""),
            kind=str(value.get("kind") or ""),
            model_id=str(value.get("model_id") or ""),
            base_url=str(value.get("base_url") or ""),
            timeout_seconds=float(value.get("timeout_seconds") or 60.0),
            enabled=bool(value.get("enabled", True)),
            extra_body=value.get("extra_body")
            if isinstance(value.get("extra_body"), Mapping)
            else {},
            connection_status=str(
                value.get("connection_status")
                or ("local" if str(value.get("kind") or "") == "mock" else "untested")
            ),
            last_checked_at=str(value.get("last_checked_at") or ""),
            last_check_message=str(value.get("last_check_message") or ""),
        )


def default_mock_profile() -> ProviderProfile:
    return ProviderProfile(
        profile_id="mock-default",
        label="本地演示",
        kind="mock",
        model_id="form-assistant-mock",
        connection_status="local",
    )


LUODA_OFFICIAL_PROFILE_ID = "luoda-official"
LUODA_OFFICIAL_LABEL = "LUODA 官方服务"
LUODA_OFFICIAL_BASE_URL = "http://47.114.75.115:40000/v1"
LUODA_OFFICIAL_MODEL_ID = "neizhiAPI"


def default_luoda_profile() -> ProviderProfile:
    """Built-in LUODA cloud AI profile shipped with fresh installs.

    Uses the official proxy endpoint.  The host is covered by the built-in
    HTTP trust list in endpoint_security, so no manual env allow-list entry
    is required for this specific official endpoint.
    """
    return ProviderProfile(
        profile_id=LUODA_OFFICIAL_PROFILE_ID,
        label=LUODA_OFFICIAL_LABEL,
        kind="openai_compatible",
        model_id=LUODA_OFFICIAL_MODEL_ID,
        base_url=LUODA_OFFICIAL_BASE_URL,
        timeout_seconds=90.0,
        enabled=True,
        connection_status="untested",
    )


def provider_extra_body_with_model_defaults(
    model_id: str,
    extra_body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply official model defaults without replacing explicit user values."""

    defaults: dict[str, Any] = {}
    if str(model_id or "").strip().casefold() == "glm-5.2":
        defaults["max_tokens"] = GLM_5_2_MAX_OUTPUT_TOKENS
    defaults.update(dict(plain_data(extra_body or {})))
    return defaults


def _reject_secret_like_extra_body(
    value: Mapping[str, Any],
    *,
    prefix: str = "extra_body",
) -> None:
    for key, item in value.items():
        normalized_key = str(key or "")
        if _SECRET_LIKE_EXTRA_BODY_KEY.search(normalized_key):
            raise ValueError(
                f"Provider {prefix} cannot persist secret-like key: {normalized_key}"
            )
        if isinstance(item, Mapping):
            _reject_secret_like_extra_body(
                item,
                prefix=f"{prefix}.{normalized_key}",
            )


class ProviderProfileStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = (
            Path(path)
            if path is not None
            else assistant_storage_root() / "providers.json"
        )

    def list_profiles(self) -> tuple[ProviderProfile, ...]:
        if not self.path.is_file():
            self._seed_if_fresh()
        payload = self._read_payload()
        raw_profiles = payload.get("profiles", ())
        if not isinstance(raw_profiles, list):
            raise TypeError("Provider profiles must be a list")
        profiles = tuple(
            ProviderProfile.from_dict(item)
            for item in raw_profiles
            if isinstance(item, Mapping)
        )
        if not any(item.profile_id == "mock-default" for item in profiles):
            profiles = (default_mock_profile(), *profiles)
        return profiles

    def _seed_if_fresh(self) -> None:
        """Create the store file on first run with built-in profiles.

        Fresh installs get the LUODA official cloud profile plus the local
        mock demo so AI works out of the box.  Existing user files are never
        rewritten here; callers wanting a reset use delete_all instead.
        """
        if self.path.is_file():
            return
        seeded = (
            default_luoda_profile(),
            default_mock_profile(),
        )
        active = LUODA_OFFICIAL_PROFILE_ID
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_payload({"profiles": seeded, "active_profile_id": active})

    def get(self, profile_id: str) -> ProviderProfile:
        for profile in self.list_profiles():
            if profile.profile_id == profile_id:
                return profile
        raise KeyError(f"Unknown provider profile: {profile_id}")

    def active_profile_id(self) -> str:
        profiles = self.list_profiles()
        stored_profile_id = ""
        if self.path.is_file():
            payload = self._read_payload()
            stored_profile_id = str(payload.get("active_profile_id") or "").strip()
        return self._resolve_active_profile_id(profiles, stored_profile_id)

    def set_active_profile_id(self, profile_id: str) -> None:
        normalized = str(profile_id or "").strip()
        profiles = list(self.list_profiles())
        if not any(item.profile_id == normalized for item in profiles):
            raise KeyError(f"Unknown provider profile: {normalized}")
        self._write_profiles(profiles, active_profile_id=normalized)

    def upsert(
        self,
        profile: ProviderProfile,
        *,
        make_active: bool = False,
    ) -> None:
        profiles = list(self.list_profiles())
        active_profile_id = self.active_profile_id()
        for index, current in enumerate(profiles):
            if current.profile_id == profile.profile_id:
                profiles[index] = profile
                break
        else:
            profiles.append(profile)
        self._write_profiles(
            profiles,
            active_profile_id=(
                profile.profile_id if make_active else active_profile_id
            ),
        )

    def delete(self, profile_id: str) -> bool:
        if profile_id == "mock-default":
            raise ValueError("The built-in mock profile cannot be deleted")
        current_profiles = list(self.list_profiles())
        active_profile_id = self.active_profile_id()
        profiles = [item for item in current_profiles if item.profile_id != profile_id]
        if len(profiles) == len(current_profiles):
            return False
        if active_profile_id == profile_id:
            active_profile_id = self._resolve_active_profile_id(profiles, "")
        self._write_profiles(profiles, active_profile_id=active_profile_id)
        return True

    @staticmethod
    def _resolve_active_profile_id(
        profiles: list[ProviderProfile] | tuple[ProviderProfile, ...],
        stored_profile_id: str,
    ) -> str:
        profile_ids = {item.profile_id for item in profiles}
        if stored_profile_id in profile_ids:
            return stored_profile_id
        for profile in reversed(profiles):
            if profile.kind != "mock" and profile.enabled:
                return profile.profile_id
        if "mock-default" in profile_ids:
            return "mock-default"
        return profiles[0].profile_id if profiles else "mock-default"

    def _read_payload(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise TypeError("Provider profile store root must be an object")
        schema = str(payload.get("schema_version") or "")
        if schema != PROVIDER_PROFILE_STORE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported provider profile schema: {schema!r}")
        return payload

    def _write_profiles(
        self,
        profiles: list[ProviderProfile],
        *,
        active_profile_id: str,
    ) -> None:
        self._write_payload(
            {
                "profiles": profiles,
                "active_profile_id": active_profile_id,
            }
        )

    def _write_payload(self, values: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": PROVIDER_PROFILE_STORE_SCHEMA_VERSION,
            "contract_kind": "provider_profile_store",
            "active_profile_id": str(values.get("active_profile_id") or ""),
            "profiles": [item.to_dict() for item in values.get("profiles", ())],
        }
        temporary = self.path.with_suffix(f".json.{os.getpid()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    plain_data(payload),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def ensure_luoda_official_ready(
    *,
    profiles: ProviderProfileStore | None = None,
    secret: str = "",
    secret_store=None,
) -> bool:
    """Bootstrap the built-in LUODA cloud AI on first run.

    The provider-profile store seeds the official profile automatically when
    the store file is absent.  This helper additionally records the factory
    secret into the writable secure store when the official profile exists but
    has no secret yet, so a fresh install can talk to the LUODA cloud AI out
    of the box.  Customer edits in the settings UI are never overwritten: the
    helper only fills an empty slot.

    Returns True when the official profile is present and ready (secret set).
    """
    store = profiles or ProviderProfileStore()
    official = None
    for item in store.list_profiles():
        if item.profile_id == LUODA_OFFICIAL_PROFILE_ID:
            official = item
            break
    if official is None:
        return False
    if secret_store is not None and str(secret or "").strip():
        try:
            existing = str(secret_store.get(LUODA_OFFICIAL_PROFILE_ID) or "").strip()
        except Exception:  # noqa: BLE001 - secure store may be unavailable
            existing = ""
        if not existing:
            try:
                secret_store.set(LUODA_OFFICIAL_PROFILE_ID, str(secret).strip())
            except Exception:  # noqa: BLE001 - best-effort bootstrap
                return False
            return True
    return bool(official.enabled)


__all__ = [
    "GLM_5_2_MAX_OUTPUT_TOKENS",
    "PROVIDER_CONNECTION_STATUSES",
    "LUODA_OFFICIAL_BASE_URL",
    "LUODA_OFFICIAL_LABEL",
    "LUODA_OFFICIAL_MODEL_ID",
    "LUODA_OFFICIAL_PROFILE_ID",
    "PROVIDER_KINDS",
    "PROVIDER_PROFILE_STORE_SCHEMA_VERSION",
    "ProviderProfile",
    "ProviderProfileStore",
    "default_luoda_profile",
    "default_mock_profile",
    "ensure_luoda_official_ready",
    "provider_extra_body_with_model_defaults",
]
