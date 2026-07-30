import ast
import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QLineEdit
from src.shared.ui.input_metrics import (
    build_framed_input_stylesheet,
    build_input_editor_stylesheet,
    configure_input_line_edit,
    input_border_color,
)
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.material_name_edit import MaterialNameEdit
from src.shared.ui.placeholder_edit import PlaceholderEdit
from src.shared.ui.projected_text_edit import ProjectedTextEdit
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.theme import LIGHT
from src.shared.ui.typography_policy import TextRole, font_for_role
from src.ui.panels.heading_numbering_panel import HeadingNumberingPanel
from src.ui.panels import theme_panel


def test_shared_input_stylesheet_supports_font_family_override():
    qss = build_text_input_stylesheet(LIGHT, font_family="Consolas, monospace")

    assert "font-family: Consolas, monospace;" in qss
    assert f"border-radius: {LIGHT.input_radius}px;" in qss


def test_default_input_stylesheets_do_not_own_font_size_or_weight():
    for qss in (
        build_input_editor_stylesheet(LIGHT),
        build_framed_input_stylesheet(LIGHT),
        build_text_input_stylesheet(LIGHT),
    ):
        assert "font-size:" not in qss
        assert "font-weight:" not in qss


def test_styled_spin_box_uses_body_role_without_qss_font_override(qapp):
    spin = StyledSpinBox()
    expected = font_for_role(TextRole.BODY)

    try:
        qapp.processEvents()
        editor = spin.lineEdit()

        assert editor is not None
        for actual in (spin.font(), editor.font()):
            assert tuple(actual.families()) == tuple(expected.families())
            assert actual.pixelSize() == expected.pixelSize()
            assert actual.weight() == expected.weight()
        assert "font-size:" not in spin.styleSheet()
        assert "font-weight:" not in spin.styleSheet()
        assert "font-family:" not in spin.styleSheet()
        assert "font-size:" not in editor.styleSheet()
        assert "font-weight:" not in editor.styleSheet()
        assert "font-family:" not in editor.styleSheet()
    finally:
        spin.deleteLater()


def test_default_input_font_qss_escape_hatches_are_explicitly_allowlisted():
    """Prevent new default inputs from silently bypassing semantic QFont roles."""

    builders = {
        "build_input_editor_stylesheet",
        "build_framed_input_stylesheet",
        "build_text_input_stylesheet",
    }
    actual: list[tuple[str, str, tuple[str, ...]]] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else ""
            )
            if name not in builders:
                continue
            font_keywords = tuple(
                keyword.arg
                for keyword in node.keywords
                if keyword.arg in {"font_size", "font_family"}
            )
            if font_keywords:
                actual.append(
                    (
                        path.relative_to(ROOT).as_posix(),
                        name,
                        font_keywords,
                    )
                )

    assert actual == [
        (
            "src/shared/ui/command_palette.py",
            "build_input_editor_stylesheet",
            ("font_size",),
        ),
        (
            "src/shared/ui/input_style.py",
            "build_framed_input_stylesheet",
            ("font_family",),
        ),
        (
            "src/shared/ui/placeholder_edit.py",
            "build_text_input_stylesheet",
            ("font_family",),
        ),
    ]


def test_input_type_selector_blocks_do_not_override_semantic_fonts():
    """Catch ancestor/type QSS that wins over widget-level QFont on Qt."""

    block = re.compile(
        r"(?ms)^[ \t]*(?P<selector>[^\n{}]*"
        r"(?:QLineEdit|QComboBox|QDoubleSpinBox|QSpinBox)"
        r"[^\n{}]*)\s*\{\{?(?P<body>.*?)^[ \t]*\}\}?"
    )
    leaks: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        source = path.read_text(encoding="utf-8-sig")
        for match in block.finditer(source):
            declarations = re.findall(
                r"font-(?:size|weight|family)\s*:",
                match.group("body"),
            )
            if declarations:
                line = source.count("\n", 0, match.start()) + 1
                selector = " ".join(match.group("selector").split())
                leaks.append(f"{path.relative_to(ROOT).as_posix()}:{line}: {selector}")

    assert leaks == []


def test_configured_input_editor_uses_body_role_without_qss_font_override(qapp):
    editor = QLineEdit()
    expected = font_for_role(TextRole.BODY)

    try:
        configure_input_line_edit(editor, LIGHT)
        actual = editor.font()

        assert tuple(actual.families()) == tuple(expected.families())
        assert actual.pixelSize() == expected.pixelSize()
        assert actual.weight() == expected.weight()
        assert actual.hintingPreference() == expected.hintingPreference()
        assert "font-size:" not in editor.styleSheet()
        assert "font-weight:" not in editor.styleSheet()
    finally:
        editor.deleteLater()


def test_painted_inputs_share_text_input_border_contract():
    normal_color, normal_width = input_border_color(
        LIGHT,
        enabled=True,
        active=False,
    )
    focus_color, focus_width = input_border_color(
        LIGHT,
        enabled=True,
        active=True,
    )

    assert normal_color.name().upper() == LIGHT.border.upper()
    assert normal_width == 1.0
    assert focus_color.name().upper() == LIGHT.border_focus.upper()
    assert focus_width == 1.0

def test_placeholder_edit_uses_shared_text_input_stylesheet():
    source = inspect.getsource(PlaceholderEdit._apply_theme)

    assert "build_text_input_stylesheet" in source
    assert "QLineEdit {" not in source


def test_material_name_edit_uses_shared_text_input_surface():
    source = inspect.getsource(ProjectedTextEdit._apply_theme)

    assert issubclass(MaterialNameEdit, ProjectedTextEdit)
    assert "build_text_input_stylesheet" in source
    assert "border: 1px" not in source
    assert "background:" not in source


def test_heading_numbering_panel_uses_shared_text_input_and_selection_helpers():
    source = inspect.getsource(HeadingNumberingPanel._build_stylesheet)

    assert "build_text_input_stylesheet" in source
    assert "build_checkbox_stylesheet" in source
    assert "QLineEdit {" not in source


def test_theme_editor_dialog_uses_shared_framed_input_stylesheet():
    source = inspect.getsource(theme_panel._ThemeEditorDialog._apply_theme)

    assert "build_framed_input_stylesheet" in source
    assert "QLineEdit {" not in source
    assert "font_size=" not in source
