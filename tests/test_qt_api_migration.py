import sys
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_qt_api_uses_pyside6_signal_and_property_symbols():
    from src import qt_api

    assert qt_api.Signal.__module__.startswith("PySide6.")
    assert qt_api.Property.__module__.startswith("PySide6.")
    assert qt_api.QSvgRenderer.__module__.startswith("PySide6.")


def test_dependency_manifests_use_pyside6_essentials_runtime_binding():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "PySide6_Essentials>=6.6.0" in requirements
    assert '"PySide6_Essentials>=6.6.0"' in pyproject
    assert "PySide6>=6.6.0" not in requirements
    assert '"PySide6>=6.6.0"' not in pyproject
    assert "PyQt5" not in requirements


def test_release_notices_clarify_mit_source_but_not_relicense_dependencies():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert "MIT" in notices
    assert "PySide6" in notices
    assert "项目自身代码：MIT" in notices
    assert "第三方软件、图标和二进制：保留各自原始许可" in notices
    assert "PySide6、Shiboken6 与 Qt 并非 MIT" in notices


def test_project_license_file_exists_and_is_mit():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert license_text.startswith("MIT License")


def test_shared_ui_tree_no_longer_references_pyqt5():
    for path in (ROOT / "src" / "shared" / "ui").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "PyQt5" not in text, f"{path} still references PyQt5"


def test_main_runtime_tree_no_longer_references_pyqt5():
    targets = [ROOT / "main.py", ROOT / "src" / "ui"]
    for target in targets:
        files = [target] if target.is_file() else list(target.rglob("*.py"))
        for path in files:
            text = path.read_text(encoding="utf-8")
            assert "PyQt5" not in text, f"{path} still references PyQt5"


def test_repository_python_files_no_longer_import_pyqt5_outside_vendor_dirs():
    skip_parts = {".venv", "__pycache__", ".agents"}
    pyqt5_import_re = re.compile(r"^\s*(from|import)\s+PyQt5\b", re.M)

    for path in ROOT.rglob("*.py"):
        if any(part in skip_parts for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not pyqt5_import_re.search(text), f"{path} still imports PyQt5"
