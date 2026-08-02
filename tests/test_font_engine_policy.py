from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from src.shared.ui.font_engine_policy import (
    FONT_ENGINE_ENV_VAR,
    QT_PLATFORM_ENV_VAR,
    WINDOWS_YAHEI_FONT_FILES,
    configure_application_windows_font_engine,
    configure_windows_font_engine,
    requested_font_engine_from_argv,
)

ROOT = Path(__file__).resolve().parent.parent


def test_windows_production_default_is_freetype():
    environment: dict[str, str] = {}

    result = configure_windows_font_engine(environ=environment, platform="win32")

    assert result.engine == "freetype"
    assert result.source == "production-default"
    assert result.changed is True
    assert environment[QT_PLATFORM_ENV_VAR] == "windows:fontengine=freetype"


def test_environment_can_explicitly_select_directwrite():
    environment = {FONT_ENGINE_ENV_VAR: " DirectWrite "}

    result = configure_windows_font_engine(environ=environment, platform="win32")

    assert result.engine == "directwrite"
    assert result.source == "environment"
    assert QT_PLATFORM_ENV_VAR not in environment


def test_command_line_selection_overrides_environment_and_keeps_windows_options():
    environment = {
        FONT_ENGINE_ENV_VAR: "freetype",
        QT_PLATFORM_ENV_VAR: "windows:darkmode=2,fontengine=freetype",
    }

    result = configure_windows_font_engine(
        "directwrite",
        environ=environment,
        platform="win32",
    )

    assert result.engine == "directwrite"
    assert result.source == "command-line"
    assert environment[QT_PLATFORM_ENV_VAR] == "windows:darkmode=2"


def test_system_selection_is_a_true_no_policy_opt_out():
    environment = {
        QT_PLATFORM_ENV_VAR: "windows:darkmode=2,fontengine=freetype",
    }

    result = configure_windows_font_engine(
        "system",
        environ=environment,
        platform="win32",
    )

    assert result.engine == "system"
    assert result.changed is False
    assert environment[QT_PLATFORM_ENV_VAR] == (
        "windows:darkmode=2,fontengine=freetype"
    )


def test_existing_windows_font_engine_is_respected_without_app_override():
    environment = {
        QT_PLATFORM_ENV_VAR: "windows:fontengine=freetype,darkmode=2",
    }

    result = configure_windows_font_engine(environ=environment, platform="win32")

    assert result.engine == "freetype"
    assert result.source == "qt-platform"
    assert result.changed is False
    assert environment[QT_PLATFORM_ENV_VAR] == (
        "windows:fontengine=freetype,darkmode=2"
    )


def test_legacy_directwrite_option_is_repaired_to_qt_native_default():
    environment = {
        QT_PLATFORM_ENV_VAR: "windows:darkmode=2:fontengine=directwrite",
    }

    result = configure_windows_font_engine(environ=environment, platform="win32")

    assert result.engine == "directwrite"
    assert result.source == "qt-platform"
    assert result.changed is True
    assert environment[QT_PLATFORM_ENV_VAR] == "windows:darkmode=2"


def test_freetype_uses_qt_canonical_comma_delimited_platform_options():
    environment = {QT_PLATFORM_ENV_VAR: "windows:darkmode=2"}

    result = configure_windows_font_engine(
        "freetype",
        environ=environment,
        platform="win32",
    )

    assert result.engine == "freetype"
    assert environment[QT_PLATFORM_ENV_VAR] == (
        "windows:darkmode=2,fontengine=freetype"
    )


def test_directwrite_removes_freetype_and_nodirectwrite_options():
    environment = {
        QT_PLATFORM_ENV_VAR: (
            "windows:darkmode=2,fontengine=freetype,nodirectwrite,nocolorfonts"
        )
    }

    configure_windows_font_engine(
        "directwrite",
        environ=environment,
        platform="win32",
    )

    assert environment[QT_PLATFORM_ENV_VAR] == ("windows:darkmode=2,nocolorfonts")


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--gui", "--font-engine", "directwrite"], "directwrite"),
        (["--font-engine=freetype"], "freetype"),
        (["document.docx"], None),
    ],
)
def test_runtime_hook_reads_only_the_startup_font_engine_option(argv, expected):
    assert requested_font_engine_from_argv(argv) == expected


def test_application_policy_falls_back_before_qt_when_yahei_faces_are_missing(
    tmp_path,
):
    environment: dict[str, str] = {}

    result = configure_application_windows_font_engine(
        environ=environment,
        platform="win32",
        windows_dir=tmp_path,
    )

    assert result.engine == "directwrite"
    assert result.source == "missing-yahei-fonts-fallback"
    assert QT_PLATFORM_ENV_VAR not in environment


def test_application_policy_keeps_freetype_when_all_required_faces_exist(tmp_path):
    fonts_dir = tmp_path / "Fonts"
    fonts_dir.mkdir()
    for filename in WINDOWS_YAHEI_FONT_FILES:
        (fonts_dir / filename).touch()
    environment: dict[str, str] = {}

    result = configure_application_windows_font_engine(
        environ=environment,
        platform="win32",
        windows_dir=tmp_path,
    )

    assert result.engine == "freetype"
    assert environment[QT_PLATFORM_ENV_VAR] == "windows:fontengine=freetype"


@pytest.mark.parametrize("platform_name", ["offscreen", "minimal:enable_fonts=0"])
def test_headless_qpa_platform_is_never_overwritten(platform_name):
    environment = {
        FONT_ENGINE_ENV_VAR: "directwrite",
        QT_PLATFORM_ENV_VAR: platform_name,
    }

    result = configure_windows_font_engine(
        "freetype",
        environ=environment,
        platform="win32",
    )

    assert result.engine is None
    assert result.source == "headless-platform"
    assert result.changed is False
    assert environment[QT_PLATFORM_ENV_VAR] == platform_name


def test_non_windows_platform_is_not_changed():
    environment = {QT_PLATFORM_ENV_VAR: "xcb"}

    result = configure_windows_font_engine(
        "freetype",
        environ=environment,
        platform="linux",
    )

    assert result.source == "non-windows"
    assert environment[QT_PLATFORM_ENV_VAR] == "xcb"


def test_invalid_environment_value_fails_fast_on_native_windows():
    environment = {FONT_ENGINE_ENV_VAR: "cleartype-ish"}

    with pytest.raises(ValueError, match=FONT_ENGINE_ENV_VAR):
        configure_windows_font_engine(environ=environment, platform="win32")


def test_policy_module_has_no_qt_import_and_frozen_build_uses_runtime_hook():
    policy_source = (
        ROOT / "src" / "shared" / "ui" / "font_engine_policy.py"
    ).read_text(encoding="utf-8")
    spec_source = (ROOT / "Alavette-Form_V1.0.spec").read_text(encoding="utf-8")
    hook_source = (
        ROOT / "scripts" / "windows" / "pyinstaller_font_engine_hook.py"
    ).read_text(encoding="utf-8")

    assert "import PySide6" not in policy_source
    assert "from PySide6" not in policy_source
    assert r"runtime_hooks=['scripts\\windows\\pyinstaller_font_engine_hook.py']" in (
        spec_source
    )
    assert "configure_application_windows_font_engine(" in hook_source
    assert "requested_font_engine_from_argv(sys.argv[1:])" in hook_source


def test_importing_startup_policy_through_ui_package_does_not_import_qt():
    command = (
        "import sys; import src.shared.ui.font_engine_policy; "
        "print(int('PySide6' in sys.modules), "
        "int('PySide6.QtGui' in sys.modules), int('src.qt_api' in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stdout.strip() == "0 0 0"


@pytest.mark.parametrize("script_name", ["start_app.bat", "start_app_debug.bat"])
def test_windows_launchers_forward_font_engine_override(script_name):
    launcher_source = (ROOT / "scripts" / "windows" / script_name).read_text(
        encoding="utf-8"
    )

    assert "main.py --gui %*" in launcher_source
