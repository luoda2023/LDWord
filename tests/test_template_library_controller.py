from __future__ import annotations

from pathlib import Path

import pytest

from src.config import library
from src.config.builtin_templates import create_builtin_template
from src.ui.template_library_controller import TemplateLibraryController


@pytest.fixture
def isolated_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        library,
        "TEMPLATE_LIBRARY_DIR",
        tmp_path / "config_library" / "templates",
    )
    monkeypatch.setattr(
        library,
        "SCENE_LIBRARY_DIR",
        tmp_path / "config_library" / "plans",
    )


def test_controller_creates_copy_in_requested_mode_only(isolated_library) -> None:
    controller = TemplateLibraryController()
    source = create_builtin_template("default")

    selection = controller.create_copy(
        mode_id="exam",
        source_template=source,
        name="校级试卷模板",
    )

    assert selection.source_type == "user"
    assert Path(selection.path).parent == library.template_user_dir("exam")
    assert not (library.template_user_dir("custom") / Path(selection.path).name).exists()


def test_controller_options_keep_session_template_without_persisting_it(
    isolated_library,
) -> None:
    controller = TemplateLibraryController()
    session = create_builtin_template("default")
    session.name = "会话临时模板"

    options = controller.options(
        mode_id="custom",
        current_template_id="__session__",
        current_template=session,
        include_current=True,
    )

    assert options[0].template_id == "__session__"
    assert options[0].name == "会话临时模板"
    assert not list(library.template_user_dir("custom").glob("__session__.*"))


def test_controller_keeps_user_template_management_for_unique_id(
    isolated_library,
) -> None:
    controller = TemplateLibraryController()
    user = create_builtin_template("default")
    user.name = "校级试卷模板"
    saved = library.save_template_to_library(
        user,
        template_id="school_exam_format",
        mode_id="exam",
    )

    assert controller.is_builtin(
        mode_id="exam",
        template_id="school_exam_format",
        path=str(saved.path),
        source="library",
        source_type="user",
    ) is False
    assert controller.manageable_path(
        path=str(saved.path),
        source_type="user",
    ) == saved.path


def test_controller_allocates_collision_free_ids_from_one_identity_policy(
    isolated_library,
) -> None:
    controller = TemplateLibraryController()
    first = controller.create_copy(
        mode_id="report",
        source_template=create_builtin_template("report_default"),
        name="季度报告模板",
    )
    second = controller.create_copy(
        mode_id="report",
        source_template=create_builtin_template("report_default"),
        name="季度报告模板",
    )

    assert first.template_id == "季度报告模板"
    assert second.template_id == "季度报告模板_2"
