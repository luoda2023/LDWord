import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.workbench.config_management_detail import (
    ConfigManagementDetail,
    _SessionConfigSection,
    _TemplateExportSection,
)


def test_config_management_detail_splits_template_export_and_session_config_sections():
    module_source = (ROOT / "src/ui/panels/workbench/config_management_detail.py").read_text(encoding="utf-8")
    detail_source = inspect.getsource(ConfigManagementDetail)

    assert "class _TemplateExportSection" in module_source
    assert "class _SessionConfigSection" in module_source
    assert "self._template_export_section = _TemplateExportSection" in detail_source
    assert "self._session_config_section = _SessionConfigSection" in detail_source
    assert "def save_current_template_to_path" in detail_source
    assert "self._template_export_section.save_current_template_to_path" in detail_source
    assert "self._session_config_section.navigation_snapshot" in detail_source


def test_config_management_sections_keep_focused_public_helpers():
    export_source = inspect.getsource(_TemplateExportSection)
    session_source = inspect.getsource(_SessionConfigSection)

    assert "def save_current_template_to_path" in export_source
    assert "def navigation_snapshot" in export_source
    assert "ConfigListWidget" not in export_source

    assert "ConfigListWidget" in session_source
    assert "def navigation_snapshot" in session_source
    assert "save_template(" not in session_source
