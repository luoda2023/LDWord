from __future__ import annotations

from pathlib import Path

from src.app_meta import APP_PACKAGE_NAME, APP_SEMVER, APP_VERSION


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer" / "Alavette-Form.iss"
SIMPLIFIED_CHINESE_MESSAGES = (
    ROOT / "installer" / "languages" / "ChineseSimplified.isl"
)


def test_hotfix_identity_is_stable_and_semver_is_visible() -> None:
    assert APP_PACKAGE_NAME == "Alavette-Form"
    assert APP_VERSION == f"V{APP_SEMVER}"
    assert APP_SEMVER.count(".") == 2


def test_installer_uses_one_v1_product_identity_and_per_user_location() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    assert "AppId={{5C548E6B-72CF-4A77-B8E4-7D2A94B777D4}" in source
    assert "DefaultDirName={autopf}\\Alavette Form" in source
    assert "PrivilegesRequired=lowest" in source
    assert "UsePreviousAppDir=yes" in source
    assert "UsePreviousTasks=yes" in source


def test_installer_creates_start_menu_and_offers_desktop_shortcut_by_default() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert (
        'Name: "{group}\\Alavette Form"; '
        'Filename: "{app}\\app\\{#AppExeName}"'
    ) in source
    assert (
        'Name: "{autodesktop}\\Alavette Form"; '
        'Filename: "{app}\\app\\{#AppExeName}"'
    ) in source
    task_line = next(
        line for line in source.splitlines() if line.startswith('Name: "desktopicon"')
    )
    assert "Flags: checkedonce" in task_line
    assert "unchecked" not in task_line


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


def test_installer_defaults_to_simplified_chinese_and_keeps_english_available() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    language_lines = [
        line for line in source.splitlines() if line.startswith('Name: "')
    ]

    assert language_lines[:2] == [
        'Name: "chinesesimplified"; '
        'MessagesFile: "languages\\ChineseSimplified.isl"',
        'Name: "english"; MessagesFile: "compiler:Default.isl"',
    ]
    messages = SIMPLIFIED_CHINESE_MESSAGES.read_text(encoding="utf-8")
    assert "LanguageName=简体中文" in messages
    assert "LanguageID=$0804" in messages
    assert "ButtonInstall=安装(&I)" in messages


def test_installer_uses_the_distinct_setup_icon() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert "SetupIconFile=assets\\Alavette-Form-Setup.ico" in source
    assert (ROOT / "installer" / "assets" / "Alavette-Form-Setup.ico").is_file()
