from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields, replace
import json
from pathlib import Path
from threading import Event
import time

import pytest

from src.config import library
from src.config.builtin_templates import create_builtin_template
from src.config.loader import load_template, save_template
from src.config.template import TemplateConfig
from src.config.template_authoring_workspace import (
    AUTHORING_BASELINE_KIND,
    AUTHORING_SCHEMA_VERSION,
    BASELINE_FILENAME,
    INBOX_NAME,
    PROMPT_FILENAME,
    WORKBENCH_INDEX_FILENAME,
    ensure_template_authoring_workspace,
    list_template_authoring_workspace_descriptors,
    process_template_import_inbox,
    refresh_template_authoring_workbench_index,
    template_authoring_state_path,
    template_authoring_workbench_path,
)
from src.config.work_mode import list_template_authoring_work_modes


@pytest.fixture
def isolated_config_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_root = tmp_path / "config_library"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", config_root / "templates")
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", config_root / "plans")
    return config_root


def test_singular_ensure_exposes_only_three_user_facing_entries(
    isolated_config_library: Path,
) -> None:
    workspace = ensure_template_authoring_workspace("thesis")

    assert workspace.workbench_root == isolated_config_library / "template_workbench"
    assert workspace.workbench_root == template_authoring_workbench_path()
    assert workspace.state_root == template_authoring_state_path() / "thesis"
    assert workspace.root == workspace.workbench_root / "thesis"
    assert {path.name for path in workspace.workbench_root.iterdir() if path.is_dir()} == {
        "thesis"
    }
    assert {path.name for path in workspace.root.iterdir()} == {
        PROMPT_FILENAME,
        BASELINE_FILENAME,
        INBOX_NAME,
    }
    assert (workspace.workbench_root / WORKBENCH_INDEX_FILENAME).is_file()
    assert workspace.prompt_path.is_file()
    assert workspace.baseline_path.is_file()
    assert workspace.inbox_path.is_dir()
    for internal_path in (
        workspace.processing_dir,
        workspace.archive_dir,
        workspace.records_dir,
        workspace.success_dir,
        workspace.failed_dir,
    ):
        assert internal_path.resolve().is_relative_to(workspace.state_root.resolve())
        assert not internal_path.resolve().is_relative_to(workspace.root.resolve())

    prompt = workspace.prompt_path.read_text(encoding="utf-8")
    assert "{{" not in prompt
    assert all(f"`{field.name}`" in prompt for field in fields(TemplateConfig))
    baseline = json.loads(workspace.baseline_path.read_text(encoding="utf-8"))
    assert baseline["kind"] == AUTHORING_BASELINE_KIND
    assert baseline["schema_version"] == AUTHORING_SCHEMA_VERSION
    assert baseline["mode_id"] == "thesis"


def test_workspace_ensure_is_idempotent_without_migration_copies(
    isolated_config_library: Path,
) -> None:
    for _ in range(20):
        workspace = ensure_template_authoring_workspace("custom")

    assert {path.name for path in workspace.root.iterdir()} == {
        PROMPT_FILENAME,
        BASELINE_FILENAME,
        INBOX_NAME,
    }
    assert not list(workspace.root.glob("*旧目录迁移保留*"))


def test_opening_template_workbench_does_not_seed_plan_library(
    isolated_config_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        library,
        "_seed_scene_library",
        lambda: pytest.fail("template workbench must not mutate the plan library"),
    )

    workspace = ensure_template_authoring_workspace("thesis")

    assert workspace.root.is_dir()
    assert not library.SCENE_LIBRARY_DIR.exists()


def test_registry_descriptors_do_not_materialize_all_modes(
    isolated_config_library: Path,
) -> None:
    descriptors = list_template_authoring_workspace_descriptors()
    expected_mode_ids = {
        mode.mode_id for mode in list_template_authoring_work_modes()
    }

    assert {workspace.mode_id for workspace in descriptors} == expected_mode_ids
    assert not template_authoring_workbench_path().exists()
    assert not template_authoring_state_path().exists()


def test_new_mode_without_exact_canonical_baseline_fails_without_partial_workspace(
    isolated_config_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.config.work_mode as work_mode_module

    source_mode = work_mode_module.get_work_mode("report")
    assert source_mode is not None
    extra = replace(
        source_mode,
        mode_id="research_report",
        label="调研报告版",
        display_order=75,
        status="active",
        aliases=("调研报告",),
    )
    monkeypatch.setattr(
        work_mode_module,
        "_WORK_MODES",
        (*work_mode_module._WORK_MODES, extra),
    )

    descriptors = list_template_authoring_workspace_descriptors()
    assert "research_report" in {workspace.mode_id for workspace in descriptors}
    assert not template_authoring_workbench_path().exists()

    with pytest.raises(
        ValueError,
        match=r"unknown built-in template id: research_report/report_default",
    ):
        ensure_template_authoring_workspace("research_report")

    assert not template_authoring_workbench_path().exists()
    assert not library.TEMPLATE_LIBRARY_DIR.exists()


def test_deprecated_mode_user_data_is_preserved_without_materializing_peers(
    isolated_config_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.config.work_mode as work_mode_module

    root = isolated_config_library / "template_workbench"
    historical = root / "thesis"
    historical.mkdir(parents=True)
    evidence = historical / "用户历史资料.json"
    evidence.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        work_mode_module,
        "_WORK_MODES",
        tuple(
            replace(mode, status="deprecated")
            if mode.mode_id == "thesis"
            else mode
            for mode in work_mode_module._WORK_MODES
        ),
    )

    refresh_template_authoring_workbench_index()

    assert evidence.is_file()
    assert {path.name for path in root.iterdir() if path.is_dir()} == {"thesis"}
    root_index = (root / WORKBENCH_INDEX_FILENAME).read_text(encoding="utf-8")
    assert "已停用（deprecated），已创建" in root_index


def test_unregistered_historical_mode_directory_is_indexed_not_deleted(
    isolated_config_library: Path,
) -> None:
    root = isolated_config_library / "template_workbench"
    historical = root / "retired_mode"
    historical.mkdir(parents=True)
    evidence = historical / "用户历史资料.json"
    evidence.write_text("{}", encoding="utf-8")

    refresh_template_authoring_workbench_index()

    assert evidence.is_file()
    root_index = (root / WORKBENCH_INDEX_FILENAME).read_text(encoding="utf-8")
    assert "`retired_mode`" in root_index
    assert "保留、不监听" in root_index


def test_raw_template_import_has_structured_success_and_internal_archive(
    isolated_config_library: Path,
) -> None:
    workspace = ensure_template_authoring_workspace("thesis")
    template = create_builtin_template("default")
    template.name = "校级论文模板"
    source = workspace.inbox_path / "default_format (1).json"
    save_template(template, source)

    result = process_template_import_inbox("thesis", settle_seconds=0)

    assert len(result.successes) == 1
    assert not result.rejections
    assert not result.warnings
    assert result.successes[0].contract is None
    assert not source.exists()
    assert load_template(result.successes[0].entry.path).name == "校级论文模板"
    assert list(workspace.archive_dir.glob("*.json"))
    record = next(workspace.success_dir.glob("*.md")).read_text(encoding="utf-8")
    assert "兼容版裸 TemplateConfig（无模式指纹）" in record
    assert {path.name for path in workspace.root.iterdir()} == {
        PROMPT_FILENAME,
        BASELINE_FILENAME,
        INBOX_NAME,
    }


def test_assistant_commit_and_recovery_scan_are_serialized(
    isolated_config_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.config.template_import_service as import_service

    ensure_template_authoring_workspace("thesis")
    original_load = import_service._load_external_template_strict
    direct_load_entered = Event()
    release_direct_load = Event()

    def blocking_load(path: Path, **kwargs):
        if path.name.startswith("assistant-"):
            direct_load_entered.set()
            assert release_direct_load.wait(timeout=2)
        return original_load(path, **kwargs)

    monkeypatch.setattr(
        import_service,
        "_load_external_template_strict",
        blocking_load,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        direct = executor.submit(
            import_service.import_template_authoring_result_text,
            "thesis",
            "{",
        )
        assert direct_load_entered.wait(timeout=2)
        recovery = executor.submit(
            import_service.process_template_import_inbox,
            "thesis",
            settle_seconds=0,
        )
        time.sleep(0.05)
        assert recovery.done() is False
        release_direct_load.set()

        direct_batch = direct.result(timeout=2)
        recovery_batch = recovery.result(timeout=2)

    assert len(direct_batch.rejections) == 1
    assert recovery_batch.has_activity is False


def test_processing_file_recovers_after_crash_before_library_commit(
    isolated_config_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.config.template_import_service as import_service

    class SimulatedCrash(BaseException):
        pass

    workspace = ensure_template_authoring_workspace("thesis")
    template = create_builtin_template("default")
    template.name = "提交前崩溃恢复模板"
    source = workspace.inbox_path / "before-commit.json"
    save_template(template, source)
    original_save = import_service.save_template_to_library

    def crash_before_commit(*_args, **_kwargs):
        raise SimulatedCrash

    monkeypatch.setattr(
        import_service,
        "save_template_to_library",
        crash_before_commit,
    )
    with pytest.raises(SimulatedCrash):
        process_template_import_inbox("thesis", settle_seconds=0)

    assert not source.exists()
    assert len(list(workspace.processing_dir.glob("*.json"))) == 1
    assert not [
        entry
        for entry in library.list_template_entries(mode_id="thesis")
        if entry.source_type == "user" and entry.name == template.name
    ]

    monkeypatch.setattr(
        import_service,
        "save_template_to_library",
        original_save,
    )
    recovered = process_template_import_inbox("thesis", settle_seconds=0)

    assert len(recovered.successes) == 1
    assert not list(workspace.processing_dir.glob("*.json"))
    assert len(list(workspace.archive_dir.glob("*.json"))) == 1
    assert recovered.successes[0].entry.name == template.name


def test_processing_file_recovers_after_crash_between_commit_and_archive(
    isolated_config_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.config.template_import_service as import_service

    class SimulatedCrash(BaseException):
        pass

    workspace = ensure_template_authoring_workspace("thesis")
    template = create_builtin_template("default")
    template.name = "归档前崩溃恢复模板"
    source = workspace.inbox_path / "after-commit.json"
    save_template(template, source)
    original_move = import_service._move_to_unique_destination

    def crash_before_archive(source_path: Path, directory: Path) -> Path:
        if directory == workspace.archive_dir:
            raise SimulatedCrash
        return original_move(source_path, directory)

    monkeypatch.setattr(
        import_service,
        "_move_to_unique_destination",
        crash_before_archive,
    )
    with pytest.raises(SimulatedCrash):
        process_template_import_inbox("thesis", settle_seconds=0)

    committed = [
        entry
        for entry in library.list_template_entries(mode_id="thesis")
        if entry.source_type == "user" and entry.name == template.name
    ]
    assert len(committed) == 1
    assert len(list(workspace.processing_dir.glob("*.json"))) == 1

    monkeypatch.setattr(
        import_service,
        "_move_to_unique_destination",
        original_move,
    )
    recovered = process_template_import_inbox("thesis", settle_seconds=0)

    assert len(recovered.successes) == 1
    assert not list(workspace.processing_dir.glob("*.json"))
    assert len(list(workspace.archive_dir.glob("*.json"))) == 1
    committed_after_recovery = [
        entry
        for entry in library.list_template_entries(mode_id="thesis")
        if entry.source_type == "user" and entry.name == template.name
    ]
    assert len(committed_after_recovery) == 1


def test_invalid_import_has_structured_internal_failure_explanation(
    isolated_config_library: Path,
) -> None:
    workspace = ensure_template_authoring_workspace("thesis")
    payload = asdict(create_builtin_template("default"))
    payload.update({"category": "thesis", "pipeline": ["page_setup"]})
    source = workspace.inbox_path / "ai-result.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = process_template_import_inbox("thesis", settle_seconds=0)

    assert not result.successes
    assert len(result.rejections) == 1
    assert result.rejections[0].stage == "validation"
    assert not source.exists()
    assert list(workspace.failed_dir.glob("*.json"))
    assert list(workspace.failed_dir.glob("*.错误说明.txt"))
    assert not (workspace.root / "导入记录").exists()


@pytest.mark.parametrize("case", ["empty", "array", "nested_typo"])
def test_import_rejects_payloads_compatibility_loader_would_drop(
    isolated_config_library: Path,
    case: str,
) -> None:
    workspace = ensure_template_authoring_workspace("thesis")
    if case == "empty":
        payload: object = {}
    elif case == "array":
        payload = []
    else:
        payload = asdict(create_builtin_template("default"))
        payload["name"] = "含拼写错误的模板"
        payload["styles"]["body"]["font_cnn"] = "错误字段"
    source = workspace.inbox_path / f"{case}.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = process_template_import_inbox("thesis", settle_seconds=0)

    assert not result.successes
    assert len(result.rejections) == 1


def test_global_template_listing_ignores_workbench_and_internal_state_json(
    isolated_config_library: Path,
) -> None:
    workspace = ensure_template_authoring_workspace("thesis")
    archived_template = create_builtin_template("default")
    archived_template.name = "不应进入模板列表的归档"
    archive = workspace.archive_dir / "download-result.json"
    failure = workspace.failed_dir / "rejected-result.json"
    save_template(archived_template, archive)
    save_template(archived_template, failure)

    listed_paths = {entry.path.resolve() for entry in library.list_template_entries()}

    assert workspace.baseline_path.resolve() not in listed_paths
    assert archive.resolve() not in listed_paths
    assert failure.resolve() not in listed_paths
    assert not library.is_template_library_path(workspace.baseline_path)
