import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, Qt, QWidget
from src.shared.ui import DesignSystemCard, FlowLayout, MasterDetailShell
from src.shared.ui.card import Card
from src.shared.ui.form_row import FormRow
from src.shared.ui.surface_card import SurfaceCard
from src.shared.ui.theme import get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.bridge import PanelBridge
from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def _app():
    return QApplication.instance() or QApplication([])


def test_card_names_converge_on_design_system_card():
    assert Card is DesignSystemCard
    assert SurfaceCard is DesignSystemCard
    assert issubclass(Card, DesignSystemCard)
    assert issubclass(SurfaceCard, DesignSystemCard)
    assert MasterDetailShell.__name__ == "MasterDetailShell"
    assert FlowLayout.__name__ == "FlowLayout"


def test_design_system_card_exposes_header_action_slot():
    _app()
    card = DesignSystemCard()
    action = QWidget(card)

    try:
        title = card.set_header("配置", icon_name="save")
        card.add_header_action(action)

        assert title.text() == "配置"
        assert card._header_widget is not None
        assert card._header_actions_layout is not None
        assert card._header_actions_layout.count() == 1
        assert card._sep is not None
        assert card._show_header_separator is False

        card.set_header("閰嶇疆", show_separator=True)
        assert card._show_header_separator is True
    finally:
        card.close()


def test_master_detail_panels_use_shared_shell():
    for path in (
        ROOT / "src/ui/panels/template_panel.py",
        ROOT / "src/ui/panels/scene_panel.py",
        ROOT / "src/ui/panels/workbench/panel_v2.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert "MasterDetailShell(" in source
        assert "setFixedWidth(260)" not in source


def test_master_detail_detail_scrollbar_matches_navigation_thumb_height():
    shell_source = (ROOT / "src/shared/ui/master_detail_shell.py").read_text(encoding="utf-8")
    rail_source = (ROOT / "src/shared/ui/dynamic_navigation_rail.py").read_text(encoding="utf-8")

    assert "QScrollBar::handle:vertical" in shell_source
    assert "min-height: 24px;" in shell_source
    assert "min-height: 24px;" in rail_source


def test_scene_panel_uses_template_form_baseline():
    source = (ROOT / "src/ui/panels/scene_panel.py").read_text(encoding="utf-8")

    assert "template_form_row(" in source
    assert "from src.shared.ui.form_row import FormRow" not in source


def test_template_library_actions_use_icon_system_not_emoji():
    panel_source = (ROOT / "src/ui/panels/template_panel.py").read_text(
        encoding="utf-8"
    )
    overview_source = (
        ROOT / "src/ui/panels/template_overview_detail.py"
    ).read_text(encoding="utf-8")
    source = panel_source + overview_source

    assert "📥" not in source
    assert "📤" not in source
    assert "♻" not in source
    assert 'icon_name="folder-open"' in overview_source
    assert 'icon_name="plus"' in overview_source
    assert 'icon_name="copy"' in overview_source
    assert 'icon_name="pencil-line"' in overview_source
    assert 'icon_name="trash-2"' in overview_source


def test_heading_numbering_pair_rows_delegate_to_template_form_grid():
    source = (ROOT / "src/ui/panels/heading_numbering_panel.py").read_text(encoding="utf-8")

    assert "TemplateFormGrid" in source
    assert "_build_pair_row(" not in source
    assert "def _normalize_form_rows" not in source


def test_quick_execution_and_theme_panel_share_flow_and_tokens():
    quick_source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")
    feedback_source = (
        ROOT / "src/ui/panels/workbench/quick_execution_feedback_mixin.py"
    ).read_text(encoding="utf-8")
    drop_source = (ROOT / "src/ui/panels/workbench/quick_execution_drop_area.py").read_text(encoding="utf-8")
    theme_source = (ROOT / "src/ui/panels/theme_panel.py").read_text(encoding="utf-8")

    assert "from src.shared.ui.flow_layout import FlowLayout" in theme_source
    assert "FlowLayout" not in quick_source
    assert "_FlowLayout =" not in quick_source
    assert "_FlowLayout =" not in theme_source
    assert "_FlowLayout(" not in quick_source
    assert "_FlowLayout(" not in theme_source
    assert "class _FlowLayout(QHBoxLayout)" not in quick_source
    assert "class _FlowLayout(QLayout)" not in theme_source
    assert '"warning": theme.warning' in feedback_source
    assert '"error": theme.error' in feedback_source
    assert '"success": theme.success' in feedback_source
    assert "#D97706" not in quick_source
    assert "#DC2626" not in quick_source
    assert "#16A34A" not in quick_source
    assert "#64748B" not in quick_source
    assert "#FFFFFF" not in quick_source
    assert "#ffffff" not in drop_source
    assert "get_theme().text_on_primary" in quick_source
    assert "theme.text_on_primary" in drop_source


def test_quick_execution_plain_card_headers_use_design_system_card_slots():
    source = (ROOT / "src/ui/panels/workbench/quick_execution_detail.py").read_text(encoding="utf-8")

    assert 'self._scene_card.set_header("处理方案与模板", icon_name="boxes")' in source
    assert 'row.setObjectName("wb_strategy_selector_row")' in source
    assert "self._scene_card.add_widget(self._scene_template_selector_row)" in source
    assert 'self._output_card.set_header("输出目录", icon_name="square-arrow-out-up-right")' in source
    assert 'self._execution_card.set_header("执行输出", icon_name="terminal")' in source
    assert "_scene_card_icon" not in source
    assert "_output_card_icon" not in source
    assert "_exec_card_icon" not in source


def test_form_row_keeps_fixed_controls_left_aligned():
    app = _app()
    host = QWidget()
    row = FormRow("启用", ToggleSwitch(host), parent=host)
    host.resize(420, 80)
    row.resize(420, 44)
    host.show()
    app.processEvents()

    try:
        assert row.layout().alignment() & Qt.AlignLeft
        assert row._label.x() <= 4
    finally:
        host.close()
        app.processEvents()


def test_workbench_shell_uses_neutral_navigation_background():
    app = _app()
    panel = WorkbenchPanel(PanelBridge())

    try:
        theme = get_theme()
        panel.resize(1200, 800)
        panel.show()
        app.processEvents()

        assert panel._shell.nav_background_role == "nav"
        nav_style = panel._nav_rail.styleSheet()
        assert theme.bg_nav_rail in nav_style
        assert theme.bg_sidebar not in nav_style
    finally:
        panel.close()
        app.processEvents()
