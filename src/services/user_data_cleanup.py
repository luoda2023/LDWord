"""Conservative current-user data cleanup used by the Windows uninstaller."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from src.app_meta import APP_DATA_DIR_NAME, APP_HOME_DIR_NAME
from src.app_paths import default_app_data_root
from src.assistant.runtime.providers.profiles import ProviderProfileStore
from src.assistant.runtime.providers.secrets import (
    ProviderSecretStore,
    WindowsCredentialSecretStore,
)


@dataclass(frozen=True, slots=True)
class UserDataCleanupResult:
    root: Path
    credentials_removed: int
    data_removed: bool
    errors: tuple[str, ...]

    @property
    def succeeded(self) -> bool:
        return not self.errors


def _validated_user_data_root(root: Path) -> Path:
    raw_target = Path(root).expanduser()
    is_junction = getattr(raw_target, "is_junction", lambda: False)
    if raw_target.is_symlink() or is_junction():
        raise ValueError("Refusing to follow a linked application data root")
    target = raw_target.resolve(strict=False)
    if target.name not in {APP_DATA_DIR_NAME, APP_HOME_DIR_NAME}:
        raise ValueError("Refusing to remove a directory outside the application data root")
    if target == Path(target.anchor) or target == Path.home().resolve(strict=False):
        raise ValueError("Refusing to remove a broad filesystem location")
    return target


def clear_current_user_data(
    *,
    root: Path | None = None,
    secret_store: ProviderSecretStore | None = None,
) -> UserDataCleanupResult:
    """Remove default local data and application-owned provider credentials.

    The default deliberately ignores ``LDWORD_FORM_HOME``: an uninstaller must
    never recursively delete an arbitrary developer-supplied override path.
    """

    target = _validated_user_data_root(root or default_app_data_root())
    errors: list[str] = []
    credentials_removed = 0
    store = secret_store or WindowsCredentialSecretStore()

    delete_all = getattr(store, "delete_all", None)
    if callable(delete_all):
        try:
            credentials_removed = int(delete_all())
        except Exception as exc:  # noqa: BLE001 - uninstall cleanup boundary
            errors.append(f"credential cleanup failed: {type(exc).__name__}: {exc}")
    else:
        try:
            profiles = ProviderProfileStore(
                target / "assistant" / "providers.json"
            ).list_profiles()
            for profile in profiles:
                if profile.requires_secret and store.delete(profile.profile_id):
                    credentials_removed += 1
        except Exception as exc:  # noqa: BLE001 - uninstall cleanup boundary
            errors.append(f"credential cleanup failed: {type(exc).__name__}: {exc}")

    data_removed = False
    if target.exists():
        try:
            shutil.rmtree(target)
            data_removed = True
        except Exception as exc:  # noqa: BLE001 - uninstall cleanup boundary
            errors.append(f"data cleanup failed: {type(exc).__name__}: {exc}")

    return UserDataCleanupResult(
        root=target,
        credentials_removed=credentials_removed,
        data_removed=data_removed,
        errors=tuple(errors),
    )


__all__ = ["UserDataCleanupResult", "clear_current_user_data"]
