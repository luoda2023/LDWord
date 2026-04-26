import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.ui.base_dialog import BaseDialog
from src.ui.main_window import MainWindow
from src.ui.sidebar import Sidebar
from src.ui.title_bar import TitleBar


def test_main_window_and_base_dialog_use_shared_rounded_surface_component():
    main_source = inspect.getsource(MainWindow)
    dialog_source = inspect.getsource(BaseDialog)
    surface_source = (ROOT / "src/shared/ui/rounded_surface.py").read_text(encoding="utf-8")

    assert "class RoundedSurfaceFrame" in surface_source
    assert "RoundedSurfaceFrame" in main_source
    assert "RoundedSurfaceFrame" in dialog_source
    assert "configure_surface(" in main_source
    assert "configure_surface(" in dialog_source


def test_shell_radius_token_drives_window_dialog_and_shell_edge_rounding():
    main_module = (ROOT / "src/ui/main_window.py").read_text(encoding="utf-8")
    dialog_module = (ROOT / "src/shared/ui/base_dialog.py").read_text(encoding="utf-8")
    title_source = inspect.getsource(TitleBar._apply_theme)
    sidebar_source = inspect.getsource(Sidebar._apply_theme)
    master_detail_shell = (ROOT / "src/shared/ui/master_detail_shell.py").read_text(encoding="utf-8")
    theme_panel_source = (ROOT / "src/ui/panels/theme_panel.py").read_text(encoding="utf-8")
    theme_source = (ROOT / "src/shared/ui/theme.py").read_text(encoding="utf-8")

    assert "shell_radius: int =" in theme_source
    assert "radius=t.shell_radius" in main_module
    assert "radius=t.shell_radius" in dialog_module
    assert "border-top-left-radius: {t.shell_radius}px;" in title_source
    assert "border-bottom-left-radius: {t.shell_radius}px;" in sidebar_source
    assert "theme.shell_radius" in master_detail_shell
    assert "t.shell_radius" in theme_panel_source
