import ast
from pathlib import Path

from src.ui.panels import assets_panel
from src.ui.panels.assets.question_figures_presenter import (
    QuestionFigureItemsPresenterMixin,
)


QUESTION_FIGURE_ITEM_METHODS = {
    "_refresh_question_figure_items_table",
    "_on_question_figure_item_selection_changed",
}


def _class_methods(module_path: str, class_name: str) -> set[str]:
    module = ast.parse(Path(module_path).read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, ast.FunctionDef)
            }
    raise AssertionError(f"{class_name} not found in {module_path}")


def test_assets_panel_uses_question_figure_items_presenter_mixin():
    assert issubclass(
        assets_panel.AssetsPanel,
        QuestionFigureItemsPresenterMixin,
    )


def test_question_figure_items_presenter_owns_item_table_methods():
    panel_methods = _class_methods("src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        "src/ui/panels/assets/question_figures_presenter.py",
        "QuestionFigureItemsPresenterMixin",
    )

    assert QUESTION_FIGURE_ITEM_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_ITEM_METHODS & panel_methods)
