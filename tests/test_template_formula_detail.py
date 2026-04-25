import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.template import TemplateConfig
from src.qt_api import QApplication
from src.ui.panels.template_formula_detail import FormulaDetail


def _app():
    return QApplication.instance() or QApplication([])


def test_formula_detail_preserves_non_dot_equation_numbering_format_on_unrelated_edit():
    _app()
    detail = FormulaDetail()
    template = TemplateConfig()
    template.equation_numbering.numbering_format = "chapter-seq"

    try:
        detail.set_template(template)

        assert detail._numbering_combo.currentData() == "chapter-seq"

        detail._unify_spacing.setChecked(False)

        assert template.equation_numbering.numbering_format == "chapter-seq"
    finally:
        detail.close()
