from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest

from src.config import library
from src.config.scene import SceneWorkspace
from src.config.scene_identity import (
    SceneIdentityAllocationError,
    allocate_scene_id,
    require_canonical_scene_id,
    safe_scene_file_stem,
)


def _isolate_scene_library(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> None:
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", root)
    monkeypatch.setattr(library, "ensure_scene_library", lambda: None)


def _scene(*, scene_id: str, name: str = "User plan") -> SceneWorkspace:
    return SceneWorkspace(
        name=name,
        scene_id=scene_id,
        mode_id="custom",
        template_id="default",
        compatible_template_ids=["default"],
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", "plan"),
        ("  CON  ", "plan_CON"),
        ("\x00LPT1.txt", "plan_LPT1.txt"),
        ("folder/name:*?", "folder_name"),
    ],
)
def test_safe_scene_file_stem_is_portable(raw: str, expected: str) -> None:
    assert safe_scene_file_stem(raw) == expected


def test_safe_scene_file_stem_replaces_controls_and_bounds_length() -> None:
    result = safe_scene_file_stem("A\n\x7f\u200bB" + "界" * 200)

    assert result.startswith("A___B")
    assert len(result) == 96
    assert not any(ord(character) < 32 for character in result)


@pytest.mark.parametrize(
    "scene_id",
    [
        " hidden",
        "hidden. ",
        "A\x7fB",
        "A\u200bB",
        "Ａ",
        "A  B",
        "CON",
        "LPT1.txt",
        "x" * 97,
    ],
)
def test_explicit_scene_identity_requires_the_canonical_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scene_id: str,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)

    with pytest.raises(ValueError, match="invalid scene id"):
        require_canonical_scene_id(scene_id)
    with pytest.raises(ValueError, match="invalid scene id"):
        library.scene_user_target_path(scene_id, mode_id="custom")
    with pytest.raises(ValueError, match="invalid scene id"):
        library.save_scene_to_library(
            _scene(scene_id="source"),
            scene_id=scene_id,
            mode_id="custom",
        )

    assert not root.exists()


def test_scene_identity_contract_does_not_change_template_identity_rules(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    template_root = tmp_path / "templates"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_root)
    monkeypatch.setattr(library, "ensure_template_library", lambda: None)
    template_id = "T" * 120

    target = library.template_user_target_path(template_id, mode_id="custom")

    assert target.name == f"{template_id}.json"
    assert target.parent == template_root / "custom" / "user"


def test_allocate_scene_id_is_casefolded_and_mode_scoped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    for relative in (
        "exam/builtin/Exam.json",
        "exam/user/EXAM_2.json",
        # A collision in another mode deliberately does not reserve the ID.
        "custom/builtin/exam_3.json",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    assert allocate_scene_id(name="exam", mode_id="exam") == "exam_3"


def test_allocate_scene_id_raises_after_bounded_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    for scene_id in ("plan", "plan_2", "plan_3"):
        path = root / "custom" / "user" / f"{scene_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    with pytest.raises(SceneIdentityAllocationError, match="allocation_exhausted"):
        allocate_scene_id(name="plan", mode_id="custom", max_attempts=3)


def test_scene_runtime_library_ignores_yaml_but_template_yaml_remains_valid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scene_root = tmp_path / "plans"
    template_root = tmp_path / "templates"
    _isolate_scene_library(monkeypatch, scene_root)
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", template_root)
    monkeypatch.setattr(library, "ensure_template_library", lambda: None)
    scene_yaml = scene_root / "custom" / "user" / "legacy.yaml"
    template_yaml = template_root / "custom" / "user" / "legacy.yaml"
    for path in (scene_yaml, template_yaml):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    assert library.list_scene_entries(mode_id="custom") == []
    assert library.get_scene_entry("legacy", mode_id="custom") is None
    assert library.is_scene_library_path(scene_yaml) is False
    assert library.is_template_library_path(template_yaml) is True
    with pytest.raises(ValueError, match="invalid config library write path"):
        library.validate_scene_library_write_path(scene_yaml)


def test_casefold_duplicate_scene_identity_is_rejected_by_list_and_get(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    paths = (
        root / "custom" / "user" / "EXAM.JSON",
        root / "custom" / "builtin" / "exam.json",
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    with pytest.raises(library.ConfigReferenceResolutionError):
        library.list_scene_entries(mode_id="custom")
    with pytest.raises(library.ConfigReferenceResolutionError):
        library.get_scene_entry("Exam", mode_id="custom")


def test_casefold_lookup_returns_the_persisted_scene_identity_and_upper_suffix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    path = root / "custom" / "user" / "MyPlan.JSON"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")

    entries = library.list_scene_entries(mode_id="custom")
    entry = library.get_scene_entry("myplan", mode_id="custom")

    assert [item.config_id for item in entries] == ["MyPlan"]
    assert entry is not None
    assert entry.config_id == "MyPlan"
    assert entry.path == path
    assert entry.source_type == "user"
    assert library.is_scene_library_path(path) is True
    assert library.is_scene_user_library_path(path) is True


def test_template_enumeration_accepts_uppercase_yaml_suffix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "templates"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", root)
    monkeypatch.setattr(library, "ensure_template_library", lambda: None)
    path = root / "custom" / "user" / "Upper.YAML"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")

    entries = library.list_template_entries(mode_id="custom")
    entry = library.get_template_entry("upper", mode_id="custom")

    assert [item.config_id for item in entries] == ["Upper"]
    assert entry is not None
    assert entry.path == path
    assert library.is_template_library_path(path) is True


def test_create_only_scene_save_never_replaces_existing_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )

    first = library.save_scene_to_library(
        _scene(scene_id="builtin"),
        scene_id="UserPlan",
        mode_id="custom",
        expected_absent=True,
    )
    original_bytes = first.path.read_bytes()

    with pytest.raises(
        library.SceneTargetAlreadyExistsError,
        match="scene_target_already_exists",
    ):
        library.save_scene_to_library(
            _scene(scene_id="other", name="replacement"),
            scene_id="userplan",
            mode_id="custom",
            expected_absent=True,
        )

    assert first.path.read_bytes() == original_bytes
    assert list(first.path.parent.glob("*.json")) == [first.path]


def test_create_only_scene_save_serializes_casefolded_identity_in_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )
    barrier = threading.Barrier(2)

    def publish(scene_id: str):
        barrier.wait()
        try:
            return library.save_scene_to_library(
                _scene(scene_id="source", name=scene_id),
                scene_id=scene_id,
                mode_id="custom",
                expected_absent=True,
            )
        except BaseException as exc:  # Return both outcomes to the test thread.
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(publish, ("RacePlan", "raceplan")))

    successes = [
        result for result in results if isinstance(result, library.ConfigLibraryEntry)
    ]
    collisions = [
        result
        for result in results
        if isinstance(result, library.SceneTargetAlreadyExistsError)
    ]
    user_dir = root / "custom" / "user"
    published = [
        path
        for path in user_dir.iterdir()
        if path.suffix.casefold() == ".json"
    ]

    assert len(successes) == 1
    assert len(collisions) == 1
    assert len(published) == 1
    assert library.load_scene(published[0]).scene_id in {"RacePlan", "raceplan"}
    assert not any(path.name.startswith(".scene-create-") for path in user_dir.iterdir())


def test_create_only_scene_save_detects_replacement_after_link_without_deleting_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )
    target = root / "custom" / "user" / "reviewed.json"
    real_link = library.os.link

    def replace_after_link(source, destination, *, follow_symlinks=False):
        real_link(source, destination, follow_symlinks=follow_symlinks)
        Path(destination).unlink()
        Path(destination).write_bytes(b"competitor")

    monkeypatch.setattr(library.os, "link", replace_after_link)

    with pytest.raises(library.SceneTargetAlreadyExistsError):
        library.save_scene_to_library(
            _scene(scene_id="source"),
            scene_id="reviewed",
            mode_id="custom",
            expected_absent=True,
        )

    assert target.read_bytes() == b"competitor"


def test_create_only_scene_save_sees_uppercase_json_collision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )
    existing = root / "custom" / "user" / "CasePlan.JSON"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")

    with pytest.raises(library.SceneTargetAlreadyExistsError):
        library.save_scene_to_library(
            _scene(scene_id="source"),
            scene_id="caseplan",
            mode_id="custom",
            expected_absent=True,
        )

    assert existing.read_bytes() == b"existing"


def test_matching_expected_revision_updates_and_receipt_matches_disk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )
    initial = library.save_scene_to_library(
        _scene(scene_id="source", name="initial"),
        scene_id="RevisionPlan",
        mode_id="custom",
        expected_absent=True,
    )

    updated = library.save_scene_to_library(
        _scene(scene_id="source", name="updated"),
        scene_id="RevisionPlan",
        mode_id="custom",
        expected_revision=initial.revision,
    )

    assert initial.revision
    assert updated.revision
    assert updated.revision != initial.revision
    assert updated.revision == library.scene_file_revision(updated.path)
    assert library.load_scene(updated.path).name == "updated"


def test_stale_expected_revision_never_overwrites_external_winner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )
    initial = library.save_scene_to_library(
        _scene(scene_id="source", name="initial"),
        scene_id="StalePlan",
        mode_id="custom",
        expected_absent=True,
    )
    external_path = tmp_path / "external-winner.json"
    library.save_scene(
        _scene(scene_id="StalePlan", name="external winner"),
        external_path,
    )
    external_payload = external_path.read_bytes()
    library.os.replace(external_path, initial.path)

    with pytest.raises(
        library.SceneTargetRevisionChangedError,
        match="scene_target_revision_changed",
    ):
        library.save_scene_to_library(
            _scene(scene_id="source", name="stale local writer"),
            scene_id="StalePlan",
            mode_id="custom",
            expected_revision=initial.revision,
        )

    assert initial.path.read_bytes() == external_payload
    assert library.load_scene(initial.path).name == "external winner"
    assert not any(
        path.name.startswith(".scene-update-")
        for path in initial.path.parent.iterdir()
    )


def test_create_only_scene_save_rejects_expected_revision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )

    with pytest.raises(
        ValueError,
        match="create-only Scene save cannot declare an expected revision",
    ):
        library.save_scene_to_library(
            _scene(scene_id="source"),
            scene_id="ImpossibleContract",
            mode_id="custom",
            expected_absent=True,
            expected_revision=f"sha256:{'0' * 64}",
        )

    user_dir = root / "custom" / "user"
    assert not list(user_dir.glob("*.json"))


def test_update_post_publication_external_replacement_is_never_rolled_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )
    initial = library.save_scene_to_library(
        _scene(scene_id="source", name="initial"),
        scene_id="PostPublishPlan",
        mode_id="custom",
        expected_absent=True,
    )
    external_path = tmp_path / "post-publication-winner.json"
    library.save_scene(
        _scene(scene_id="PostPublishPlan", name="external winner"),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_scene_file_revision = library.scene_file_revision
    replaced = False
    target_revision_checks = 0

    def replace_at_post_publication_review(path: str | Path) -> str:
        nonlocal replaced, target_revision_checks
        candidate = Path(path)
        if candidate == initial.path:
            target_revision_checks += 1
        if (
            not replaced
            and candidate == initial.path
            and target_revision_checks == 2
        ):
            library.os.replace(external_path, candidate)
            replaced = True
        return real_scene_file_revision(candidate)

    monkeypatch.setattr(
        library,
        "scene_file_revision",
        replace_at_post_publication_review,
    )

    with pytest.raises(
        library.SceneTargetRevisionChangedError,
        match="scene_target_changed_after_publication",
    ):
        library.save_scene_to_library(
            _scene(scene_id="source", name="local replacement"),
            scene_id="PostPublishPlan",
            mode_id="custom",
            expected_revision=initial.revision,
        )

    assert replaced is True
    assert initial.path.read_bytes() == external_payload
    assert library.load_scene(initial.path).name == "external winner"
    assert real_scene_file_revision(initial.path) != initial.revision


def test_create_only_scene_save_closes_publish_race_without_deleting_winner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    monkeypatch.setattr(
        library,
        "_normalize_scene_templates",
        lambda scene, *, mode_id=None: scene,
    )
    target = root / "custom" / "user" / "raced.json"

    def competing_link(source, destination, *, follow_symlinks=False):
        del source, follow_symlinks
        Path(destination).write_bytes(b"competitor")
        raise FileExistsError(destination)

    monkeypatch.setattr(library.os, "link", competing_link)

    with pytest.raises(library.SceneTargetAlreadyExistsError):
        library.save_scene_to_library(
            _scene(scene_id="builtin"),
            scene_id="raced",
            mode_id="custom",
            expected_absent=True,
        )

    assert target.read_bytes() == b"competitor"


def test_shadow_guard_still_rejects_builtin_scene_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "plans"
    _isolate_scene_library(monkeypatch, root)
    builtin = root / "custom" / "builtin" / "CUSTOM.json"
    builtin.parent.mkdir(parents=True)
    builtin.write_text("{}", encoding="utf-8")

    with pytest.raises(
        library.ConfigReferenceResolutionError,
        match="plan_id_shadowed",
    ):
        library.save_scene_to_library(
            _scene(scene_id="custom"),
            scene_id="custom",
            mode_id="custom",
            expected_absent=True,
        )
