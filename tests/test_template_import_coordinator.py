from __future__ import annotations

import os
from pathlib import Path
import threading
import time

import pytest

from src.config import library
from src.config.builtin_templates import create_builtin_template
from src.config.loader import load_template, save_template
from src.config.template_authoring_workspace import (
    TemplateImportBatch,
    template_authoring_workspace_descriptor,
)
from src.ui.template_import_coordinator import (
    CoordinatorPhase,
    TemplateImportCoordinator,
)


@pytest.fixture
def isolated_config_library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    config_root = tmp_path / "config_library"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", config_root / "templates")
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", config_root / "plans")
    return config_root


def _wait_until(qapp, predicate, *, timeout_seconds: float = 8.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for coordinator")


def test_coordinator_materializes_and_watches_current_mode_only(
    isolated_config_library: Path,
    qapp,
) -> None:
    coordinator = TemplateImportCoordinator()
    try:
        coordinator.start("thesis")
        _wait_until(qapp, lambda: coordinator.is_idle)

        workspace = template_authoring_workspace_descriptor("thesis")
        watched_paths = {path.resolve() for path in coordinator.watched_inbox_paths()}
        assert coordinator.active_mode_id == "thesis"
        assert watched_paths == {workspace.inbox_path.resolve()}
        assert {path.name for path in workspace.workbench_root.iterdir() if path.is_dir()} == {
            "thesis"
        }
        assert not watched_paths.pop().is_relative_to(
            library.TEMPLATE_LIBRARY_DIR.resolve()
        )
    finally:
        coordinator.stop()

    assert coordinator.is_running is False
    assert coordinator.watched_inbox_paths() == ()


def test_coordinator_switches_modes_without_cross_writes(
    isolated_config_library: Path,
    qapp,
) -> None:
    processed: list[tuple[str, TemplateImportBatch]] = []
    coordinator = TemplateImportCoordinator()
    coordinator.batch_processed.connect(
        lambda mode_id, batch: processed.append((mode_id, batch))
    )
    try:
        coordinator.start("thesis")
        _wait_until(qapp, lambda: coordinator.is_idle)
        thesis_workspace = template_authoring_workspace_descriptor("thesis")
        thesis_template = create_builtin_template("thesis_gbt")
        thesis_template.name = "校级论文模板"
        thesis_source = thesis_workspace.inbox_path / "thesis-result.json"
        save_template(thesis_template, thesis_source)
        stable_time = time.time() - 2
        os.utime(thesis_source, (stable_time, stable_time))
        assert coordinator.queue_mode("thesis")
        _wait_until(qapp, lambda: len(processed) == 1 and coordinator.is_idle)

        assert coordinator.activate_mode("official")
        _wait_until(
            qapp,
            lambda: coordinator.is_idle and coordinator.active_mode_id == "official",
        )
        official_workspace = template_authoring_workspace_descriptor("official")
        assert coordinator.watched_inbox_paths() == (official_workspace.inbox_path,)
        official_template = create_builtin_template("official_gbt")
        official_template.name = "机关公文模板"
        official_source = official_workspace.inbox_path / "official-result.json"
        save_template(official_template, official_source)
        os.utime(official_source, (stable_time, stable_time))
        assert coordinator.queue_mode("official")
        _wait_until(qapp, lambda: len(processed) == 2 and coordinator.is_idle)
    finally:
        coordinator.stop()

    assert [mode_id for mode_id, _batch in processed] == ["thesis", "official"]
    assert all(len(batch.successes) == 1 for _mode_id, batch in processed)
    assert all(not batch.rejections for _mode_id, batch in processed)
    assert load_template(
        library.template_user_dir("thesis") / "校级论文模板.json"
    ).name == thesis_template.name
    assert load_template(
        library.template_user_dir("official") / "机关公文模板.json"
    ).name == official_template.name
    assert not (
        library.template_user_dir("official") / "校级论文模板.json"
    ).exists()


def test_coordinator_emits_structured_rejection_for_current_mode(
    isolated_config_library: Path,
    qapp,
) -> None:
    processed: list[tuple[str, TemplateImportBatch]] = []
    coordinator = TemplateImportCoordinator()
    coordinator.batch_processed.connect(
        lambda mode_id, batch: processed.append((mode_id, batch))
    )
    try:
        coordinator.start("official")
        _wait_until(qapp, lambda: coordinator.is_idle)
        workspace = template_authoring_workspace_descriptor("official")
        source = workspace.inbox_path / "invalid-result.json"
        source.write_text('{"name": "不完整公文模板"}', encoding="utf-8")
        stable_time = time.time() - 2
        os.utime(source, (stable_time, stable_time))
        assert coordinator.queue_mode("official")
        _wait_until(qapp, lambda: len(processed) == 1 and coordinator.is_idle)
    finally:
        coordinator.stop()

    mode_id, batch = processed[0]
    assert mode_id == "official"
    assert not batch.successes
    assert len(batch.rejections) == 1
    assert batch.rejections[0].stage == "validation"
    assert not list(library.template_user_dir("official").glob("*.json"))
    assert list(workspace.failed_dir.glob("*.错误说明.txt"))


def test_coordinator_recovers_processing_file_on_startup(
    isolated_config_library: Path,
    qapp,
) -> None:
    workspace = template_authoring_workspace_descriptor("thesis")
    workspace.processing_dir.mkdir(parents=True)
    template = create_builtin_template("default")
    template.name = "启动恢复模板"
    save_template(template, workspace.processing_dir / "interrupted.json")
    processed: list[tuple[str, TemplateImportBatch]] = []
    coordinator = TemplateImportCoordinator()
    coordinator.batch_processed.connect(
        lambda mode_id, batch: processed.append((mode_id, batch))
    )
    try:
        coordinator.start("thesis")
        _wait_until(qapp, lambda: len(processed) == 1 and coordinator.is_idle)
    finally:
        coordinator.stop()

    assert processed[0][0] == "thesis"
    assert len(processed[0][1].successes) == 1
    assert not list(workspace.processing_dir.glob("*.json"))
    assert len(list(workspace.archive_dir.glob("*.json"))) == 1


def test_mode_switch_during_prepare_coalesces_to_latest_mode(
    isolated_config_library: Path,
    qapp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ui.template_import_coordinator as coordinator_module

    original_ensure = coordinator_module.ensure_template_authoring_workspace
    thesis_started = threading.Event()
    release_thesis = threading.Event()
    prepared_modes: list[str] = []

    def delayed_ensure(mode_id: str):
        prepared_modes.append(mode_id)
        if mode_id == "thesis":
            thesis_started.set()
            assert release_thesis.wait(timeout=5)
        return original_ensure(mode_id)

    monkeypatch.setattr(
        coordinator_module,
        "ensure_template_authoring_workspace",
        delayed_ensure,
    )
    coordinator = TemplateImportCoordinator()
    try:
        coordinator.start("thesis")
        assert thesis_started.wait(timeout=3)
        assert coordinator.phase == CoordinatorPhase.PREPARING
        assert coordinator.activate_mode("official")
        release_thesis.set()
        _wait_until(
            qapp,
            lambda: coordinator.is_idle and coordinator.active_mode_id == "official",
        )

        official = template_authoring_workspace_descriptor("official")
        assert coordinator.phase == CoordinatorPhase.WATCHING
        assert coordinator.watched_inbox_paths() == (official.inbox_path,)
        assert prepared_modes == ["thesis", "official"]
    finally:
        release_thesis.set()
        coordinator.stop()
