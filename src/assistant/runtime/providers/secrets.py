"""Provider secret stores; profiles and session files never contain API keys."""

from __future__ import annotations

from collections.abc import Mapping
import os
import sys
from typing import Protocol


SECRET_SERVICE_PREFIX = "Alavette-Form/assistant/provider"


class ProviderSecretStore(Protocol):
    def get(self, profile_id: str) -> str: ...

    def set(self, profile_id: str, secret: str) -> None: ...

    def delete(self, profile_id: str) -> bool: ...


class MemorySecretStore:
    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def get(self, profile_id: str) -> str:
        return str(self._values.get(profile_id, ""))

    def set(self, profile_id: str, secret: str) -> None:
        normalized = str(secret or "")
        if not normalized:
            raise ValueError("Provider secret cannot be empty")
        self._values[str(profile_id)] = normalized

    def delete(self, profile_id: str) -> bool:
        return self._values.pop(str(profile_id), None) is not None


class EnvironmentSecretStore:
    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = os.environ if env is None else env

    def get(self, profile_id: str) -> str:
        key = "ALAVETTE_FORM_AI_KEY_" + str(profile_id).upper().replace("-", "_")
        return str(self._env.get(key, "") or "")

    def set(self, profile_id: str, secret: str) -> None:
        raise RuntimeError("Environment secret store is read-only")

    def delete(self, profile_id: str) -> bool:
        return False


class WindowsCredentialSecretStore:
    """Windows Credential Manager backed secret storage via pywin32."""

    def __init__(self, *, service_prefix: str = SECRET_SERVICE_PREFIX) -> None:
        self.service_prefix = service_prefix.rstrip("/")

    @property
    def available(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import win32cred  # noqa: F401
        except ImportError:
            return False
        return True

    def get(self, profile_id: str) -> str:
        if not self.available:
            return ""
        import pywintypes
        import win32cred

        try:
            credential = win32cred.CredRead(self._target(profile_id), win32cred.CRED_TYPE_GENERIC)
        except pywintypes.error as exc:
            if getattr(exc, "winerror", None) == 1168:
                return ""
            raise
        blob = credential.get("CredentialBlob", b"")
        if isinstance(blob, bytes):
            return blob.decode("utf-16-le")
        return str(blob or "")

    def set(self, profile_id: str, secret: str) -> None:
        if not self.available:
            raise RuntimeError("Windows Credential Manager is unavailable")
        normalized = str(secret or "")
        if not normalized:
            raise ValueError("Provider secret cannot be empty")
        import win32cred

        win32cred.CredWrite(
            {
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": self._target(profile_id),
                # pywin32 accepts a Unicode value here and performs the
                # CREDENTIALW UTF-16 conversion itself. Passing pre-encoded
                # bytes fails with "cannot be converted to Unicode".
                "CredentialBlob": normalized,
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                "UserName": "Alavette Form",
                "Comment": "Alavette Form AI provider secret",
            },
            0,
        )

    def delete(self, profile_id: str) -> bool:
        if not self.available:
            return False
        import pywintypes
        import win32cred

        try:
            win32cred.CredDelete(self._target(profile_id), win32cred.CRED_TYPE_GENERIC)
        except pywintypes.error as exc:
            if getattr(exc, "winerror", None) == 1168:
                return False
            raise
        return True

    def _target(self, profile_id: str) -> str:
        normalized = str(profile_id or "").strip()
        if not normalized or any(char in normalized for char in "\\/\x00"):
            raise ValueError("Unsafe provider profile id for secret storage")
        return f"{self.service_prefix}/{normalized}"


class HybridSecretStore:
    """Read environment overrides first, then use the writable secure store."""

    def __init__(
        self,
        *,
        environment: EnvironmentSecretStore | None = None,
        secure: ProviderSecretStore | None = None,
    ) -> None:
        self.environment = environment or EnvironmentSecretStore()
        self.secure = secure or WindowsCredentialSecretStore()

    def get(self, profile_id: str) -> str:
        return self.environment.get(profile_id) or self.secure.get(profile_id)

    def set(self, profile_id: str, secret: str) -> None:
        self.secure.set(profile_id, secret)

    def delete(self, profile_id: str) -> bool:
        return self.secure.delete(profile_id)


__all__ = [
    "EnvironmentSecretStore",
    "HybridSecretStore",
    "MemorySecretStore",
    "ProviderSecretStore",
    "SECRET_SERVICE_PREFIX",
    "WindowsCredentialSecretStore",
]
