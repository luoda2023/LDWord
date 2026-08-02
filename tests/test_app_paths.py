from __future__ import annotations

from pathlib import Path

from src.app_paths import (
    APP_HOME_ENV,
    app_data_root,
    config_library_data_root,
    log_data_root,
)


def test_app_data_root_prefers_explicit_override() -> None:
    root = app_data_root(
        env={
            APP_HOME_ENV: "C:/isolated/alavette",
            "LOCALAPPDATA": "C:/ignored",
        }
    )

    assert root == Path("C:/isolated/alavette")
    assert config_library_data_root(env={APP_HOME_ENV: str(root)}) == (
        root / "config_library"
    )


def test_app_data_root_uses_local_app_data_without_project_dependency() -> None:
    root = app_data_root(env={"LOCALAPPDATA": "C:/Users/Test/AppData/Local"})

    assert root == Path("C:/Users/Test/AppData/Local/Alavette-Form")
    assert "Lark-Formatter" not in str(root)


def test_log_data_root_is_scoped_beneath_application_data() -> None:
    root = Path("C:/isolated/alavette")

    assert log_data_root(env={APP_HOME_ENV: str(root)}) == root / "logs"
