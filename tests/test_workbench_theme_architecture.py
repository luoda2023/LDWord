import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.panel_v2 import WorkbenchPanel


def test_workbench_panel_uses_styles_helper_for_v2_shell_theme():
    panel_source = inspect.getsource(WorkbenchPanel)
    module_source = (ROOT / "src/ui/panels/workbench/panel_v2.py").read_text(encoding="utf-8")
    styles_source = (ROOT / "src/ui/panels/workbench/styles.py").read_text(encoding="utf-8")

    assert "from .styles import apply_workbench_v2_shell_theme" in module_source
    assert "def apply_workbench_v2_shell_theme" in styles_source
    assert "apply_workbench_v2_shell_theme(" in panel_source
