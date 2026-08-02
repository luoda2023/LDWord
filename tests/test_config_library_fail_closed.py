from __future__ import annotations

import builtins
import json
import os
from pathlib import Path
import subprocess

import pytest

import src.config.library as library
import src.config.master_library as master_library
import src.config.migration as migration
import src.config.work_mode as work_mode
from src.config.library import SceneLibraryDescriptor
from src.config.scene import SceneWorkspace
from src.config.builtin_templates import create_builtin_template


def _raise_runtime_error(message: str):
    def _raise(*_args, **_kwargs):
        raise RuntimeError(message)

    return _raise


def _create_directory_link_or_skip(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (NotImplementedError, OSError) as symlink_error:
        if os.name != "nt":
            pytest.skip(f"directory symlink unavailable: {symlink_error}")
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(
            "directory junction unavailable: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


def test_scene_descriptor_does_not_project_internal_normalization_bug_as_load_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "custom" / "user" / "plan.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", tmp_path)
    monkeypatch.setattr(
        library,
        "load_scene",
        lambda _path: SceneWorkspace(scene_id="plan", mode_id="custom"),
    )
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        _raise_runtime_error("normalizer programming error"),
    )

    with pytest.raises(RuntimeError, match="normalizer programming error"):
        library._build_scene_descriptor_from_path(path)


@pytest.mark.parametrize("error_type", (RuntimeError, TypeError))
def test_scene_descriptor_does_not_project_internal_loader_bug_as_load_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error_type: type[Exception],
) -> None:
    path = tmp_path / "custom" / "user" / "plan.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", tmp_path)
    def _broken_loader(_path: Path) -> None:
        raise error_type("loader programming error")

    monkeypatch.setattr(library, "load_scene", _broken_loader)

    with pytest.raises(error_type, match="loader programming error"):
        library._build_scene_descriptor_from_path(path)


def test_scene_identity_assignment_error_is_not_silenced() -> None:
    class RejectingScene:
        scene_id = "old"

        def __setattr__(self, name: str, value: object) -> None:
            if name == "scene_id":
                raise RuntimeError("scene identity write failed")
            super().__setattr__(name, value)

    with pytest.raises(RuntimeError, match="scene identity write failed"):
        library._set_scene_identity(RejectingScene(), "new")


@pytest.mark.parametrize(
    ("scene_id", "mode_id", "error_code"),
    (
        ("other_plan", "custom", "plan_storage_identity_mismatch"),
        ("plan", "exam", "plan_storage_mode_mismatch"),
    ),
)
def test_scene_storage_identity_drift_is_rejected_before_normalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scene_id: str,
    mode_id: str,
    error_code: str,
) -> None:
    path = tmp_path / "custom" / "user" / "plan.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", tmp_path)
    monkeypatch.setattr(
        library,
        "load_scene",
        lambda _path: SceneWorkspace(scene_id=scene_id, mode_id=mode_id),
    )
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        _raise_runtime_error("identity drift reached normalization"),
    )

    descriptor = library._build_scene_descriptor_from_path(path)

    assert descriptor is not None
    assert not descriptor.is_available
    assert error_code in descriptor.load_error


def test_plan_validation_does_not_attach_runtime_resource_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = SceneWorkspace(
        scene_id="custom",
        mode_id="custom",
        template_id="default",
        compatible_template_ids=["default"],
    )
    monkeypatch.setattr(library, "_template_id_is_available", lambda *_args, **_kwargs: True)

    normalized = library._normalize_scene_templates(scene, mode_id="custom")

    assert normalized is not scene
    assert not hasattr(normalized, "template_ref")
    assert not hasattr(normalized, "master_ref")


def test_master_registry_error_is_not_downgraded_to_not_applicable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = SceneWorkspace(
        mode_id="official",
        template_id="official_gbt",
        master_id="official_gbt_standard",
    )
    monkeypatch.setattr(
        master_library,
        "get_master",
        _raise_runtime_error("master registry programming error"),
    )

    with pytest.raises(RuntimeError, match="master registry programming error"):
        library._validate_scene_master_id(scene, mode_id="official")
    assert scene.master_id == "official_gbt_standard"


def test_unknown_requested_master_does_not_fall_back_to_mode_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = SceneWorkspace(
        mode_id="official",
        template_id="official_gbt",
        master_id="missing_master",
    )
    monkeypatch.setattr(master_library, "get_master", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        master_library,
        "default_master",
        _raise_runtime_error("master fallback was consulted"),
    )

    with pytest.raises(
        library.ConfigReferenceResolutionError,
        match="plan_master_ref_unresolved",
    ):
        library._validate_scene_master_id(scene, mode_id="official")
    assert scene.master_id == "missing_master"


@pytest.mark.parametrize(
    ("helper", "args", "registry_name"),
    (
        ("_normalize_mode_id", ("exam",), "get_work_mode"),
        ("_normalize_mode_id", (None,), "default_work_mode"),
        ("_mode_id_for_scene_id", ("exam",), "work_mode_for_scene_id"),
        ("_default_scene_id_for_mode", ("exam",), "get_work_mode"),
        ("_default_template_id_for_mode", ("exam",), "get_work_mode"),
    ),
)
def test_work_mode_registry_programming_error_is_not_silently_defaulted(
    monkeypatch: pytest.MonkeyPatch,
    helper: str,
    args: tuple[object, ...],
    registry_name: str,
) -> None:
    monkeypatch.setattr(
        work_mode,
        registry_name,
        _raise_runtime_error("work-mode registry programming error"),
    )

    with pytest.raises(RuntimeError, match="work-mode registry programming error"):
        getattr(library, helper)(*args)


def test_unknown_explicit_mode_does_not_inherit_custom_defaults() -> None:
    with pytest.raises(ValueError, match="unknown work mode"):
        library._normalize_mode_id("not-registered")
    with pytest.raises(ValueError, match="unknown work mode"):
        library._default_template_id_for_mode("not-registered")
    with pytest.raises(ValueError, match="unknown work mode"):
        library._default_scene_id_for_mode("not-registered")


def test_unknown_template_id_never_consults_mode_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        library,
        "get_template_entry",
        lambda _template_id, *, mode_id=None: None,
    )
    monkeypatch.setattr(
        library,
        "default_template_entry",
        _raise_runtime_error("implicit template fallback was consulted"),
    )

    with pytest.raises(FileNotFoundError, match="template_ref_unresolved"):
        library.load_template_from_library(
            "not_registered",
            mode_id="exam",
        )


def test_template_library_api_exposes_no_implicit_fallback_switch() -> None:
    with pytest.raises(TypeError, match="allow_fallback"):
        library.load_template_from_library(
            "not_registered",
            mode_id="exam",
            allow_fallback=True,
        )


def test_missing_declared_defaults_do_not_select_arbitrary_library_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        library,
        "_default_template_id_for_mode",
        lambda _mode_id=None: "declared_template",
    )
    monkeypatch.setattr(
        library,
        "_default_scene_id_for_mode",
        lambda _mode_id=None: "declared_plan",
    )
    monkeypatch.setattr(library, "get_template_entry", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(library, "get_scene_entry", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(library, "get_scene_descriptor", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        library,
        "list_template_entries",
        _raise_runtime_error("arbitrary template fallback was consulted"),
    )
    monkeypatch.setattr(
        library,
        "list_scene_entries",
        _raise_runtime_error("arbitrary plan fallback was consulted"),
    )
    monkeypatch.setattr(
        library,
        "list_scene_descriptors",
        _raise_runtime_error("arbitrary descriptor fallback was consulted"),
    )

    assert library.default_template_entry("exam") is None
    assert library.default_scene_entry("exam") is None
    assert library.default_scene_descriptor("exam") is None


def test_scene_workspace_has_no_legacy_material_profile_identity() -> None:
    scene = SceneWorkspace(mode_id="official")

    assert not hasattr(scene, "default_material_profile_id")
    assert not hasattr(library, "_validate_scene_material_contract")


def test_official_plan_load_preserves_source_bytes_without_legacy_schema_mutation(
    tmp_path: Path,
) -> None:
    builtin_path = (
        Path(__file__).resolve().parents[1]
        / "config_library"
        / "plans"
        / "official"
        / "builtin"
        / "official.json"
    )
    payload = json.loads(builtin_path.read_text(encoding="utf-8"))
    payload["input_source_profile"]["material_schema_ids"] = []
    source_path = tmp_path / "official.json"
    source_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    source_bytes = source_path.read_bytes()
    entry = library.ConfigLibraryEntry(
        kind="plan",
        config_id="official",
        name="Official plan without legacy material binding",
        path=source_path,
        mode_id="official",
        source_type="user",
    )

    loaded = library._load_scene_entry(entry)

    assert loaded.input_source_profile.material_schema_ids == []
    assert source_path.read_bytes() == source_bytes


def test_unavailable_plan_blocks_template_dependency_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    descriptor = SceneLibraryDescriptor(
        config_id="broken",
        scene_id="broken",
        name="Broken",
        description="",
        template_id="",
        compatible_template_ids=(),
        path=tmp_path / "broken.json",
        load_error="JSONDecodeError: malformed",
        mode_id="official",
        source_type="user",
    )
    monkeypatch.setattr(
        library,
        "list_scene_descriptors",
        lambda *, mode_id: [descriptor],
    )

    with pytest.raises(RuntimeError, match="plan_dependency_unresolved:broken"):
        library.template_dependent_scene_descriptors(
            "official_gbt",
            mode_id="official",
        )


def test_malformed_external_plan_remains_a_visible_load_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "official" / "user" / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", tmp_path)

    descriptor = library._build_scene_descriptor_from_path(path)

    assert descriptor is not None
    assert descriptor.config_id == "broken"
    assert descriptor.is_available is False
    assert descriptor.load_error


@pytest.mark.parametrize("kind", ("template", "scene"))
def test_library_save_rejects_explicit_path_traversal_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kind: str,
) -> None:
    template_root = tmp_path / "templates"
    scene_root = tmp_path / "plans"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_root)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_root)
    monkeypatch.setattr(library, "ensure_template_library", lambda: None)
    monkeypatch.setattr(library, "ensure_scene_library", lambda: None)
    escaped = tmp_path / "escaped.json"

    with pytest.raises(ValueError, match="config id"):
        if kind == "template":
            library.save_template_to_library(
                create_builtin_template("default"),
                template_id="../../escaped",
                mode_id="custom",
            )
        else:
            library.save_scene_to_library(
                SceneWorkspace(scene_id="custom", template_id="default"),
                scene_id="../../escaped",
                mode_id="custom",
            )

    assert not escaped.exists()


@pytest.mark.parametrize("kind", ("template", "scene"))
def test_library_save_rejects_user_directory_link_to_sibling_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kind: str,
) -> None:
    root = tmp_path / kind
    builtin_dir = root / "custom" / "builtin"
    user_dir = root / "custom" / "user"
    builtin_dir.mkdir(parents=True)
    _create_directory_link_or_skip(builtin_dir, user_dir)

    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", root)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", root)
    monkeypatch.setattr(library, "ensure_template_library", lambda: None)
    monkeypatch.setattr(library, "ensure_scene_library", lambda: None)

    with pytest.raises(ValueError, match="symbolic library path"):
        if kind == "template":
            library.save_template_to_library(
                create_builtin_template("default"),
                template_id="victim",
                mode_id="custom",
            )
        else:
            library.save_scene_to_library(
                SceneWorkspace(scene_id="custom", template_id="default"),
                scene_id="victim",
                mode_id="custom",
            )

    assert not (builtin_dir / "victim.json").exists()


@pytest.mark.parametrize("kind", ("template", "scene"))
def test_library_listing_rejects_linked_runtime_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kind: str,
) -> None:
    root = tmp_path / kind
    builtin_dir = root / "custom" / "builtin"
    user_dir = root / "custom" / "user"
    builtin_dir.mkdir(parents=True)
    _create_directory_link_or_skip(builtin_dir, user_dir)

    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", root)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", root)
    monkeypatch.setattr(library, "ensure_template_library", lambda: None)
    monkeypatch.setattr(library, "ensure_scene_library", lambda: None)

    with pytest.raises(ValueError, match="symbolic library path"):
        if kind == "template":
            library.list_template_entries(mode_id="custom")
        else:
            library.list_scene_descriptors(mode_id="custom")
    with pytest.raises(ValueError, match="symbolic library path"):
        if kind == "template":
            library.template_library_watch_dirs(mode_id="custom")
        else:
            library.scene_library_watch_dirs(mode_id="custom")


def test_canonical_builtin_loader_rejects_linked_resource_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import src.config.builtin_templates as builtin_templates
    from src.config.loader import save_template

    canonical_root = tmp_path / "canonical"
    external = tmp_path / "external"
    external.mkdir()
    save_template(create_builtin_template("default"), external / "default.json")
    mode_dir = canonical_root / "custom"
    mode_dir.mkdir(parents=True)
    _create_directory_link_or_skip(external, mode_dir / "builtin")
    monkeypatch.setattr(
        builtin_templates,
        "_CANONICAL_TEMPLATE_ROOT",
        canonical_root,
    )

    with pytest.raises(ValueError, match="symbolic canonical template path"):
        builtin_templates.create_builtin_template("default", mode_id="custom")


def test_plan_save_rejects_cross_mode_template_without_mutating_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    template_root = tmp_path / "templates"
    scene_root = tmp_path / "plans"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_root)
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", scene_root)
    library.ensure_config_library()
    scene = SceneWorkspace(
        scene_id="broken_exam_plan",
        mode_id="official",
        template_id="official_gbt",
        compatible_template_ids=["official_gbt"],
    )

    with pytest.raises(
        library.ConfigReferenceResolutionError,
        match="plan_template_ref_unresolved",
    ):
        library.save_scene_to_library(
            scene,
            scene_id="broken_exam_plan",
            mode_id="exam",
        )

    assert scene.mode_id == "official"
    assert scene.template_id == "official_gbt"
    assert not (scene_root / "exam" / "user" / "broken_exam_plan.json").exists()


def test_stale_user_source_claim_does_not_authorize_external_template_delete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.ui.template_library_controller import TemplateLibraryController

    template_root = tmp_path / "templates"
    external = tmp_path / "external.json"
    external.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_root)
    controller = TemplateLibraryController()

    assert controller.manageable_path(path=str(external), source_type="user") is None
    with pytest.raises(ValueError, match="not an owned user template"):
        controller.delete_user_template(external)
    assert external.exists()


def test_default_module_switches_do_not_import_implementation_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "src.modules.registry":
            raise ImportError("module registry programming error")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    monkeypatch.setattr(migration, "_default_switches_cache", None)

    switches = migration.get_default_module_switches()

    assert len(switches) == 23
    assert switches["page_setup"] is True
    assert switches["entity_fill"] is False


def test_default_module_catalog_failure_is_not_an_empty_switch_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        migration,
        "default_module_switches",
        _raise_runtime_error("module default catalog programming error"),
    )
    monkeypatch.setattr(migration, "_default_switches_cache", None)

    with pytest.raises(RuntimeError, match="module default catalog programming error"):
        migration.get_default_module_switches()


def test_in_place_builtin_validation_is_cached_and_invalidated_by_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.config.loader import load_template, save_template
    from src.config.template import TemplateConfig

    template_root = tmp_path / "templates"
    canonical = template_root / "custom" / "builtin" / "default.json"
    canonical.parent.mkdir(parents=True)
    save_template(TemplateConfig(name="First"), canonical)

    calls: list[str] = []

    def _load_builtin(template_id: str, *, mode_id: str | None = None):
        calls.append(f"{mode_id}/{template_id}")
        return load_template(canonical)

    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_root)
    monkeypatch.setattr(library, "canonical_template_root", lambda: template_root)
    monkeypatch.setattr(
        library,
        "list_builtin_template_resources",
        lambda: (("custom", "default", canonical),),
    )
    monkeypatch.setattr(library, "create_builtin_template", _load_builtin)
    library._IN_PLACE_TEMPLATE_VALIDATION_DIGESTS.clear()

    library.ensure_template_library()
    library.ensure_template_library()

    assert calls == ["custom/default"]

    changed = load_template(canonical)
    changed.name = "Changed"
    save_template(changed, canonical)

    library.ensure_template_library()

    assert calls == ["custom/default", "custom/default"]


def test_module_implementations_use_the_cycle_free_default_catalog() -> None:
    from src.modules.default_switches import default_module_switches
    from src.modules.registry import ALL_MODULES

    assert {
        module.meta.name: module.meta.enabled_by_default for module in ALL_MODULES
    } == default_module_switches()
