import ast
from pathlib import Path

from src.ui.panels import assets_panel
from src.ui.panels.assets.question_library_presenter import (
    QuestionFigureLibraryPresenterMixin,
)
from src.ui.panels.assets.question_library_history_presenter import (
    QuestionFigureLibraryHistoryPresenterMixin,
)
from src.ui.panels.assets.question_library_issue_presenter import (
    QuestionFigureLibraryIssuePresenterMixin,
)
from src.ui.panels.assets.question_library_master_version_presenter import (
    QuestionFigureLibraryMasterVersionPresenterMixin,
)


QUESTION_FIGURE_LIBRARY_METHODS = {
    "_refresh_question_figure_library_editor",
    "_refresh_question_figure_library_table",
    "_on_question_figure_library_selection_changed",
    "_save_question_figure_library_metadata",
    "_select_question_figure_library_row",
}

QUESTION_FIGURE_LIBRARY_HISTORY_METHODS = {
    "_refresh_question_figure_library_version_history_table",
    "_on_question_figure_library_version_history_selection_changed",
    "_select_question_figure_library_version_history_row",
    "_rollback_question_figure_library_version_history_row",
}

QUESTION_FIGURE_LIBRARY_ISSUE_METHODS = {
    "_refresh_question_figure_library_issue_table",
    "_on_question_figure_library_issue_selection_changed",
    "_select_question_figure_library_issue_row",
}

QUESTION_FIGURE_LIBRARY_MASTER_VERSION_METHODS = {
    "_refresh_question_figure_library_master_version_table",
    "_on_question_figure_library_master_version_selection_changed",
    "_question_figure_library_master_version_entry_for_row",
    "_select_question_figure_library_master_version_row",
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


def test_assets_panel_uses_question_library_presenter_mixin():
    assert issubclass(
        assets_panel.AssetsPanel,
        QuestionFigureLibraryPresenterMixin,
    )
    assert issubclass(
        assets_panel.AssetsPanel,
        QuestionFigureLibraryHistoryPresenterMixin,
    )
    assert issubclass(
        assets_panel.AssetsPanel,
        QuestionFigureLibraryIssuePresenterMixin,
    )
    assert issubclass(
        assets_panel.AssetsPanel,
        QuestionFigureLibraryMasterVersionPresenterMixin,
    )


def test_question_library_presenter_owns_local_library_methods():
    panel_methods = _class_methods("src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        "src/ui/panels/assets/question_library_presenter.py",
        "QuestionFigureLibraryPresenterMixin",
    )

    assert QUESTION_FIGURE_LIBRARY_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_LIBRARY_METHODS & panel_methods)


def test_question_library_history_presenter_owns_local_version_history_methods():
    panel_methods = _class_methods("src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        "src/ui/panels/assets/question_library_history_presenter.py",
        "QuestionFigureLibraryHistoryPresenterMixin",
    )

    assert QUESTION_FIGURE_LIBRARY_HISTORY_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_LIBRARY_HISTORY_METHODS & panel_methods)


def test_question_library_issue_presenter_owns_local_issue_methods():
    panel_methods = _class_methods("src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        "src/ui/panels/assets/question_library_issue_presenter.py",
        "QuestionFigureLibraryIssuePresenterMixin",
    )

    assert QUESTION_FIGURE_LIBRARY_ISSUE_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_LIBRARY_ISSUE_METHODS & panel_methods)


def test_question_library_master_version_presenter_owns_table_methods():
    panel_methods = _class_methods("src/ui/panels/assets_panel.py", "AssetsPanel")
    presenter_methods = _class_methods(
        "src/ui/panels/assets/question_library_master_version_presenter.py",
        "QuestionFigureLibraryMasterVersionPresenterMixin",
    )

    assert QUESTION_FIGURE_LIBRARY_MASTER_VERSION_METHODS <= presenter_methods
    assert not (QUESTION_FIGURE_LIBRARY_MASTER_VERSION_METHODS & panel_methods)
