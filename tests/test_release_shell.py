from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_release_shell_files_exist():
    required_files = [
        ROOT / "README.md",
        ROOT / "install_env.bat",
        ROOT / "package_release.bat",
        ROOT / "check_public_release.bat",
        ROOT / "clean_public_release.bat",
        ROOT / "scripts" / "windows" / "install_env.bat",
        ROOT / "scripts" / "windows" / "package_release.bat",
        ROOT / "scripts" / "windows" / "check_public_release.bat",
        ROOT / "scripts" / "windows" / "clean_public_release.bat",
        ROOT / "scripts" / "check_public_release.py",
        ROOT / "docs" / "OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md",
    ]

    for path in required_files:
        assert path.exists(), f"Missing release-shell file: {path}"


def test_root_batch_wrappers_delegate_to_windows_scripts():
    install_wrapper = (ROOT / "install_env.bat").read_text(encoding="utf-8")
    package_wrapper = (ROOT / "package_release.bat").read_text(encoding="utf-8")
    public_wrapper = (ROOT / "check_public_release.bat").read_text(encoding="utf-8")
    clean_wrapper = (ROOT / "clean_public_release.bat").read_text(encoding="utf-8")

    assert 'call "%~dp0scripts\\windows\\install_env.bat" %*' in install_wrapper
    assert 'call "%~dp0scripts\\windows\\package_release.bat" %*' in package_wrapper
    assert 'call "%~dp0scripts\\windows\\check_public_release.bat" %*' in public_wrapper
    assert 'call "%~dp0scripts\\windows\\clean_public_release.bat" %*' in clean_wrapper


def test_windows_install_script_bootstraps_env_from_requirements():
    script = (ROOT / "scripts" / "windows" / "install_env.bat").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert 'py -3.14 --version' in script
    assert 'python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"' in script
    assert '".venv\\Scripts\\python.exe" -m pip install -r requirements.txt' in script
    assert "pyinstaller" in requirements.lower()
    assert "Environment is ready" in script


def test_windows_package_script_builds_pyside6_release_and_copies_notices():
    script = (ROOT / "scripts" / "windows" / "package_release.bat").read_text(encoding="utf-8")

    assert "PyInstaller" in script
    assert "main.py" in script
    assert "Lark-Formatter_V1.0" in script
    assert "--collect-submodules PySide6" not in script
    assert '--hidden-import PySide6.QtCore' in script
    assert '--hidden-import PySide6.QtGui' in script
    assert '--hidden-import PySide6.QtWidgets' in script
    assert '--hidden-import PySide6.QtSvg' in script
    assert '--hidden-import shiboken6' in script
    assert '--exclude-module PySide6.QtGraphs' in script
    assert '--exclude-module PySide6.QtGraphsWidgets' in script
    assert '--exclude-module PySide6.QtHttpServer' in script
    assert '--exclude-module PySide6.QtNetworkAuth' in script
    assert '--exclude-module PySide6.QtQuick3D' in script
    assert '-m pip install pyinstaller' not in script
    assert "PyInstaller is missing in .venv" in script
    assert "THIRD_PARTY_NOTICES.md" in script
    assert "LICENSE" in script
    assert "defaults" in script


def test_windows_clean_script_removes_local_release_artifacts():
    script = (ROOT / "scripts" / "windows" / "clean_public_release.bat").read_text(encoding="utf-8")

    assert 'rmdir /s /q ".venv"' in script
    assert 'rmdir /s /q "build"' in script
    assert 'rmdir /s /q "dist"' in script
    assert 'del /q "crash.log"' in script
    assert 'del /q "demo_crash.log"' in script
    assert 'del /q "lark_formatter.log"' in script
    assert 'for %%F in (*.spec)' in script


def test_public_release_checker_and_readme_document_mit_source_release():
    checker = (ROOT / "scripts" / "check_public_release.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    assert "--strict" in checker
    assert "THIRD_PARTY_NOTICES.md" in checker
    assert "README.md" in checker

    assert "PySide6" in readme
    assert "MIT" in readme
    assert "THIRD_PARTY_NOTICES.md" in readme
    assert ".\\install_env.bat" in readme
    assert ".\\package_release.bat" in readme
    assert ".\\check_public_release.bat" in readme
    assert ".\\clean_public_release.bat" in readme

    assert "MIT" in checklist
    assert "THIRD_PARTY_NOTICES.md" in checklist
    assert "clean_public_release.bat" in checklist


def test_gitignore_covers_local_release_artifacts():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for entry in [
        ".venv/",
        "build/",
        "dist/",
        "crash.log",
        "demo_crash.log",
        "lark_formatter.log",
        "*_new.docx",
        ".pytest_cache/",
    ]:
        assert entry in gitignore


def test_no_local_release_artifacts_remain_in_workspace():
    unwanted_paths = [
        ROOT / "crash.log",
        ROOT / "demo_crash.log",
        ROOT / "lark_formatter.log",
        ROOT / "tests" / "test_input_new.docx",
        ROOT / "tests" / "TEST-1" / "测试文档_new.docx",
    ]

    for path in unwanted_paths:
        assert not path.exists(), f"Local artifact should be removed before public release: {path}"
