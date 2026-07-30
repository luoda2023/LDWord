from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.shared.ui.icons.catalog import get_app_logo, get_icon, get_icon_names
from src.ui.icons.catalog import get_icon as get_legacy_icon
from src.ui.panel_registry import PANEL_SPECS


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "src"


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _expression_icon_literals(node: ast.AST | None) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value} if node.value else set()
    if isinstance(node, ast.IfExp):
        return {
            *_expression_icon_literals(node.body),
            *_expression_icon_literals(node.orelse),
        }
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Dict)
    ):
        values: set[str] = set()
        for value in node.func.value.values:
            values.update(_expression_icon_literals(value))
        if len(node.args) >= 2:
            values.update(_expression_icon_literals(node.args[1]))
        return values
    return set()


def _catalog_map_values(node: ast.Dict) -> set[str]:
    values: set[str] = set()
    for value in node.values:
        if isinstance(value, (ast.Tuple, ast.List)) and value.elts:
            values.update(_expression_icon_literals(value.elts[0]))
        else:
            values.update(_expression_icon_literals(value))
    return values


def _static_icon_references() -> dict[str, set[str]]:
    references: dict[str, set[str]] = {}
    positional_icon_arguments = {
        "_PromptAction": 3,
        "PathActionPresentation": 0,
    }

    def remember(name: str, path: Path, line: int) -> None:
        if name:
            references.setdefault(name, set()).add(
                f"{path.relative_to(ROOT).as_posix()}:{line}"
            )

    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name == "get_icon" and node.args:
                    for icon_name in _expression_icon_literals(node.args[0]):
                        remember(icon_name, path, node.lineno)
                for keyword in node.keywords:
                    if keyword.arg == "icon_name":
                        for icon_name in _expression_icon_literals(keyword.value):
                            remember(icon_name, path, node.lineno)
                    if name == "PanelSpec" and keyword.arg == "icon":
                        for icon_name in _expression_icon_literals(keyword.value):
                            remember(icon_name, path, node.lineno)
                positional_index = positional_icon_arguments.get(name)
                if positional_index is not None and len(node.args) > positional_index:
                    for icon_name in _expression_icon_literals(
                        node.args[positional_index]
                    ):
                        remember(icon_name, path, node.lineno)

            if isinstance(node, ast.AnnAssign):
                target_name = (
                    node.target.id if isinstance(node.target, ast.Name) else ""
                )
                if target_name == "icon_name":
                    for icon_name in _expression_icon_literals(node.value):
                        remember(icon_name, path, node.lineno)

            if isinstance(node, ast.Assign):
                target_names = {
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                }
                target_names.update(
                    target.attr
                    for target in node.targets
                    if isinstance(target, ast.Attribute)
                )
                if "panel_icon" in target_names or any(
                    name.endswith("icon_name") for name in target_names
                ):
                    for icon_name in _expression_icon_literals(node.value):
                        remember(icon_name, path, node.lineno)
                if (
                    isinstance(node.value, ast.Dict)
                    and any(name.endswith("ICON_MAP") for name in target_names)
                ):
                    for icon_name in _catalog_map_values(node.value):
                        remember(icon_name, path, node.lineno)
                if isinstance(node.value, ast.Dict) and "STATUS_ICONS" in target_names:
                    for icon_name in _catalog_map_values(node.value):
                        remember(icon_name, path, node.lineno)

            if isinstance(node, ast.FunctionDef) and node.name.casefold().endswith(
                "icon_name"
            ):
                for child in ast.walk(node):
                    if isinstance(child, ast.Return):
                        for icon_name in _expression_icon_literals(child.value):
                            remember(icon_name, path, child.lineno)

    return references


def test_every_static_icon_reference_is_registered():
    registered = set(get_icon_names())
    references = _static_icon_references()
    missing = {
        name: sorted(locations)
        for name, locations in references.items()
        if name not in registered
    }

    assert missing == {}


def test_every_registered_icon_and_app_logo_render(qapp):
    for name in get_icon_names():
        for size in (14, 16, 18, 20, 24):
            icon = get_icon(name, size, "#1677FF", strict=True)
            assert not icon.isNull(), name
            assert not icon.pixmap(size, size).isNull(), (name, size)

    logo = get_app_logo(24)
    assert not logo.isNull()
    assert not logo.pixmap(24, 24).isNull()


def test_unknown_icon_has_visible_fallback_and_strict_validation(qapp):
    fallback = get_icon("__missing_test_icon__", 18, "#1677FF")
    assert not fallback.isNull()
    assert not fallback.pixmap(18, 18).isNull()

    with pytest.raises(KeyError, match="Unknown icon name"):
        get_icon("__missing_test_icon__", strict=True)


def test_legacy_icon_catalog_path_reexports_canonical_api():
    assert get_legacy_icon is get_icon


def test_panel_registry_is_the_sidebar_icon_source():
    registered = set(get_icon_names())
    assert {spec.icon for spec in PANEL_SPECS} <= registered

    sidebar_source = (SOURCE_ROOT / "ui" / "sidebar.py").read_text(encoding="utf-8")
    catalog_source = (
        SOURCE_ROOT / "shared" / "ui" / "icons" / "catalog.py"
    ).read_text(encoding="utf-8")
    assert "spec.icon" in sidebar_source
    assert "SIDEBAR_ICONS" not in sidebar_source
    assert "SIDEBAR_ICONS" not in catalog_source


def test_shared_icon_controls_do_not_depend_on_unicode_glyphs():
    guarded_sources = {
        SOURCE_ROOT / "shared" / "ui" / "command_palette.py": {"🔍"},
        SOURCE_ROOT / "shared" / "ui" / "empty_state.py": {"📄", "📁"},
        SOURCE_ROOT / "shared" / "ui" / "inline_alert.py": {"ℹ️", "✓", "⚠️", "✕", "×"},
        SOURCE_ROOT / "shared" / "ui" / "result.py": {"✓", "✕", "⚠", "ℹ"},
        SOURCE_ROOT
        / "ui"
        / "panels"
        / "workbench"
        / "quick_execution_drop_area.py": {"✕"},
    }

    violations = {
        path.relative_to(ROOT).as_posix(): sorted(glyphs & set(path.read_text("utf-8")))
        for path, glyphs in guarded_sources.items()
        if glyphs & set(path.read_text("utf-8"))
    }
    assert violations == {}


def test_icon_button_uses_catalog_names_instead_of_file_paths():
    source = (SOURCE_ROOT / "shared" / "ui" / "icon_button.py").read_text(
        encoding="utf-8"
    )
    assert "icon_name" in source
    assert "QIcon(icon_path)" not in source
