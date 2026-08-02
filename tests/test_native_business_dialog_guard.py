from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _production_python_files() -> tuple[Path, ...]:
    return (ROOT / "main.py", *sorted((ROOT / "src").rglob("*.py")))


def test_production_ui_does_not_call_native_business_dialogs() -> None:
    violations: list[str] = []
    for path in _production_python_files():
        if path == ROOT / "src/qt_api.py":
            continue
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name):
                continue
            if node.id in {"QMessageBox", "QInputDialog"}:
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.id}")

    assert violations == []


def test_feature_dialogs_use_shared_dialog_shells() -> None:
    allowed_qdialog_bases = {
        Path("src/shared/ui/base_dialog.py"),
        Path("src/shared/ui/preview_dialog.py"),
    }
    violations: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        relative = path.relative_to(ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {
                ast.unparse(base)
                for base in node.bases
            }
            if "QDialog" in bases and relative not in allowed_qdialog_bases:
                violations.append(f"{relative}:{node.lineno}:{node.name}")

    assert violations == []
