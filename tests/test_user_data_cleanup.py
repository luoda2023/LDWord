from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from src.assistant.runtime.providers.profiles import ProviderProfile, ProviderProfileStore
from src.assistant.runtime.providers.secrets import (
    MemorySecretStore,
    WindowsCredentialSecretStore,
)
from src.services.user_data_cleanup import clear_current_user_data


def test_cleanup_removes_application_data_and_known_profile_secrets(tmp_path) -> None:
    root = tmp_path / "Alavette-Form"
    profiles = ProviderProfileStore(root / "assistant" / "providers.json")
    profiles.upsert(
        ProviderProfile(
            profile_id="cloud-main",
            label="Cloud",
            kind="openai_compatible",
            model_id="example-model",
            base_url="https://example.invalid/v1",
        )
    )
    (root / "logs").mkdir(parents=True)
    (root / "logs" / "app.log").write_text("log", encoding="utf-8")
    secrets = MemorySecretStore({"cloud-main": "secret"})

    result = clear_current_user_data(root=root, secret_store=secrets)

    assert result.succeeded
    assert result.credentials_removed == 1
    assert result.data_removed
    assert secrets.get("cloud-main") == ""
    assert not root.exists()


def test_cleanup_refuses_non_application_directory(tmp_path) -> None:
    unsafe = tmp_path / "unrelated-user-files"
    unsafe.mkdir()

    with pytest.raises(ValueError, match="outside the application data root"):
        clear_current_user_data(root=unsafe, secret_store=MemorySecretStore())

    assert unsafe.is_dir()


def test_windows_credential_cleanup_is_limited_to_application_prefix(monkeypatch) -> None:
    deleted: list[tuple[str, int]] = []
    fake_win32cred = ModuleType("win32cred")
    fake_win32cred.CRED_TYPE_GENERIC = 1
    fake_win32cred.CredEnumerate = lambda pattern, flags: (
        {"TargetName": "Alavette-Form/assistant/provider/cloud-main"},
        {"TargetName": "Unrelated/Product/credential"},
    )
    fake_win32cred.CredDelete = lambda target, kind: deleted.append((target, kind))
    fake_pywintypes = ModuleType("pywintypes")
    fake_pywintypes.error = RuntimeError
    monkeypatch.setitem(sys.modules, "win32cred", fake_win32cred)
    monkeypatch.setitem(sys.modules, "pywintypes", fake_pywintypes)
    monkeypatch.setattr(
        WindowsCredentialSecretStore,
        "available",
        property(lambda _self: True),
    )

    removed = WindowsCredentialSecretStore().delete_all()

    assert removed == 1
    assert deleted == [("Alavette-Form/assistant/provider/cloud-main", 1)]
