from __future__ import annotations

from pathlib import Path

from src.app_meta import APP_PACKAGE_NAME, APP_SEMVER, APP_VERSION


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer" / "Alavette-Form.iss"


def test_hotfix_identity_is_stable_and_semver_is_visible() -> None:
    assert APP_PACKAGE_NAME == "Alavette-Form"
    assert APP_VERSION == f"V{APP_SEMVER}"
    assert APP_SEMVER.count(".") == 2


def test_installer_uses_one_v1_product_identity_and_per_user_location() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    assert "AppId={{5C548E6B-72CF-4A77-B8E4-7D2A94B777D4}" in source
    assert "DefaultDirName={localappdata}\\Programs\\Alavette Form" in source
    assert "PrivilegesRequired=lowest" in source
    assert "UsePreviousAppDir=yes" in source


def test_installer_replaces_only_owned_payload_and_preserves_user_data() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    assert 'Type: filesandordirs; Name: "{app}\\app"' in source
    assert "%LOCALAPPDATA%\\Alavette-Form" in source
    assert 'Name: "{localappdata}\\Alavette-Form"' not in source


def test_installer_signs_setup_and_uninstaller_in_official_mode() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    assert "#ifdef SignedBuild" in source
    assert "SignTool=release" in source
    assert "SignedUninstaller=yes" in source
