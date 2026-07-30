"""Regression coverage for Scene publication race and recovery windows.

The suite locks the no-clobber contract for conditional publish, rollback,
cleanup retry, external-winner preservation, and close-time finalization.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from src.config import library as config_library
from src.ui.bridge import PanelBridge
from src.ui.panels.scene_session_coordinator import (
    SCENE_PENDING_SAVE,
    SceneProjectionCallbacks,
    SceneSessionCoordinator,
)


@pytest.fixture
def isolated_scene_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "config_library"
    monkeypatch.setattr(config_library, "TEMPLATE_LIBRARY_DIR", root / "templates")
    monkeypatch.setattr(config_library, "SCENE_LIBRARY_DIR", root / "plans")
    config_library.ensure_scene_library()
    return root


def _scene_for_exam(*, scene_id: str, name: str):
    scene = copy.deepcopy(
        config_library.load_scene_from_library("exam", mode_id="exam")
    )
    scene.scene_id = scene_id
    scene.name = name
    return scene


def _new_user_scene(*, scene_id: str, name: str):
    entry = config_library.save_scene_to_library(
        _scene_for_exam(scene_id=scene_id, name=name),
        scene_id=scene_id,
        mode_id="exam",
        expected_absent=True,
    )
    return entry


def _coordinator_for_user_scene(*, scene_id: str, name: str):
    entry = _new_user_scene(scene_id=scene_id, name=name)
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    bridge.set_current_scene(
        config_library.load_scene_from_library(scene_id, mode_id="exam"),
        config_id=scene_id,
        path=str(entry.path),
        source="library",
        source_type="user",
        emit_signal=False,
    )
    bridge.commit_pending_work_mode_transition()
    projection = SceneProjectionCallbacks(
        apply_scene=lambda _scene, _template: None,
        refresh_scene_selector=lambda: None,
        selected_card_id=lambda: "overview",
        restore_selected_card=lambda _card_id: None,
        refresh_navigation_cards=lambda: None,
    )
    coordinator = SceneSessionCoordinator(bridge, projection)
    draft = copy.deepcopy(bridge.current_scene())
    draft.description = "local transaction draft"
    bridge.set_current_scene(
        draft,
        config_id=scene_id,
        path=str(entry.path),
        source="library",
        source_type="user",
        emit_signal=False,
    )
    bridge.set_scene_dirty(True, emit_signal=False)
    prepared = coordinator.prepare_pending_changes(
        SCENE_PENDING_SAVE,
        mode_id="exam",
    )
    assert prepared.success is True
    return bridge, coordinator, entry


def _coordinator_for_builtin_fork(*, fork_id: str):
    entry = config_library.get_scene_entry("exam", mode_id="exam")
    assert entry is not None
    assert entry.source_type == "builtin"
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    bridge.set_current_scene(
        config_library.load_scene_from_library("exam", mode_id="exam"),
        config_id="exam",
        path=str(entry.path),
        source="library",
        source_type="builtin",
        emit_signal=False,
    )
    bridge.commit_pending_work_mode_transition()
    projection = SceneProjectionCallbacks(
        apply_scene=lambda _scene, _template: None,
        refresh_scene_selector=lambda: None,
        selected_card_id=lambda: "overview",
        restore_selected_card=lambda _card_id: None,
        refresh_navigation_cards=lambda: None,
    )
    coordinator = SceneSessionCoordinator(bridge, projection)
    draft = copy.deepcopy(bridge.current_scene())
    draft.description = "local built-in fork draft"
    bridge.set_current_scene(
        draft,
        config_id="exam",
        path=str(entry.path),
        source="library",
        source_type="builtin",
        emit_signal=False,
    )
    bridge.set_scene_dirty(True, emit_signal=False)
    prepared = coordinator.prepare_pending_changes(
        SCENE_PENDING_SAVE,
        mode_id="exam",
        fork_name=fork_id,
        force_fork=True,
    )
    assert prepared.success is True
    return bridge, coordinator, config_library.scene_user_target_path(
        fork_id,
        mode_id="exam",
    )


def test_update_cas_does_not_overwrite_winner_in_compare_replace_gap(
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="cas_gap", name="initial")
    external_path = tmp_path / "cas-gap-external.json"
    config_library.save_scene(
        _scene_for_exam(scene_id="cas_gap", name="external winner"),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_replace = config_library.os.replace
    real_rename = config_library.os.rename
    injected = False

    def move_with_race(source, destination, *args, **kwargs):
        nonlocal injected
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not injected
            and source_path == initial.path
            and destination_path.name == "displaced.json"
        ):
            real_replace(external_path, destination_path)
            real_replace(destination_path, source_path)
            injected = True
        return real_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(config_library.os, "rename", move_with_race)

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.save_scene_to_library(
            _scene_for_exam(scene_id="cas_gap", name="local update"),
            scene_id="cas_gap",
            mode_id="exam",
            expected_revision=initial.revision,
        )

    assert injected is True
    assert initial.path.read_bytes() == external_payload


def test_update_rollback_does_not_overwrite_winner_after_ownership_check(
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="rollback_gap", name="initial")
    external_path = tmp_path / "rollback-gap-external.json"
    config_library.save_scene(
        _scene_for_exam(scene_id="rollback_gap", name="external winner"),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_link = config_library.os.link
    winner_injected = False

    def recreate_before_publish(source, destination, *args, **kwargs):
        nonlocal winner_injected
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not winner_injected
            and source_path.name == "replacement.json"
            and destination_path == initial.path
        ):
            config_library.os.replace(external_path, destination_path)
            winner_injected = True
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(config_library.os, "link", recreate_before_publish)

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.save_scene_to_library(
            _scene_for_exam(scene_id="rollback_gap", name="local update"),
            scene_id="rollback_gap",
            mode_id="exam",
            expected_revision=initial.revision,
        )

    assert winner_injected is True
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path)


def test_update_post_move_read_failure_restores_or_reports_recovery_evidence(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="update_post_move_read", name="initial")
    original_payload = initial.path.read_bytes()
    real_read_bytes = Path.read_bytes
    failed = False

    def fail_displaced_once(path, *args, **kwargs):
        nonlocal failed
        if not failed and Path(path).name == "displaced.json":
            failed = True
            raise PermissionError("injected displaced Scene read failure")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", fail_displaced_once)

    try:
        receipt = config_library.save_scene_to_library(
            _scene_for_exam(
                scene_id="update_post_move_read",
                name="local update",
            ),
            scene_id="update_post_move_read",
            mode_id="exam",
            expected_revision=initial.revision,
        )
    except Exception as exc:
        recovery_path = getattr(exc, "recovery_path", None)
        mutation_receipt = getattr(exc, "mutation_receipt", None)
        assert initial.path.exists() or recovery_path is not None
        if initial.path.exists():
            assert initial.path.read_bytes() == original_payload
        else:
            assert recovery_path in config_library.scene_recovery_artifacts(
                initial.path
            )
            assert isinstance(
                mutation_receipt,
                config_library.SceneFileMutationReceipt,
            )
            config_library.rollback_scene_file_mutation(mutation_receipt)
            assert initial.path.read_bytes() == original_payload
            assert config_library.scene_recovery_artifacts(initial.path) == ()
    else:
        assert failed is True
        assert receipt.revision == config_library.scene_file_revision(initial.path)


def test_conditional_post_move_read_failure_restores_or_reports_recovery_evidence(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(
        scene_id="conditional_post_move_read",
        name="initial",
    )
    original_payload = initial.path.read_bytes()
    real_read_bytes = Path.read_bytes
    failed = False

    def fail_displaced_once(path, *args, **kwargs):
        nonlocal failed
        if not failed and Path(path).name == "displaced.json":
            failed = True
            raise PermissionError("injected displaced conditional read failure")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", fail_displaced_once)

    try:
        receipt = config_library.replace_scene_file_if_revision(
            initial.path,
            expected_revision=initial.revision,
            replacement_payload=None,
            retain_recovery=True,
        )
    except Exception as exc:
        recovery_path = getattr(exc, "recovery_path", None)
        mutation_receipt = getattr(exc, "mutation_receipt", None)
        assert initial.path.exists() or recovery_path is not None
        if initial.path.exists():
            assert initial.path.read_bytes() == original_payload
        else:
            assert recovery_path in config_library.scene_recovery_artifacts(
                initial.path
            )
            assert isinstance(
                mutation_receipt,
                config_library.SceneFileMutationReceipt,
            )
            config_library.rollback_scene_file_mutation(mutation_receipt)
            assert initial.path.read_bytes() == original_payload
            assert config_library.scene_recovery_artifacts(initial.path) == ()
    else:
        assert isinstance(receipt, config_library.SceneFileMutationReceipt)
        config_library.rollback_scene_file_mutation(receipt)
        assert initial.path.read_bytes() == original_payload
        assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_post_move_recovery_restores_the_actual_captured_external_occupant(
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(
        scene_id="post_move_external_occupant",
        name="initial",
    )
    external_path = tmp_path / "post-move-external-occupant.json"
    config_library.save_scene(
        _scene_for_exam(
            scene_id="post_move_external_occupant",
            name="external winner",
        ),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_rename = config_library.os.rename
    real_read_bytes = Path.read_bytes
    injected = False
    failed_read = False

    def move_external_winner(source, destination, *args, **kwargs):
        nonlocal injected
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not injected
            and source_path == initial.path
            and destination_path.name == "displaced.json"
        ):
            config_library.os.replace(external_path, source_path)
            injected = True
        return real_rename(source, destination, *args, **kwargs)

    def fail_displaced_once(path, *args, **kwargs):
        nonlocal failed_read
        if not failed_read and Path(path).name == "displaced.json":
            failed_read = True
            raise PermissionError("injected unreadable captured external occupant")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(config_library.os, "rename", move_external_winner)
    monkeypatch.setattr(Path, "read_bytes", fail_displaced_once)

    with pytest.raises(config_library.SceneTargetRevisionChangedError) as captured:
        config_library.replace_scene_file_if_revision(
            initial.path,
            expected_revision=initial.revision,
            replacement_payload=None,
            retain_recovery=True,
        )

    receipt = getattr(captured.value, "mutation_receipt", None)
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    assert injected is True
    assert failed_read is True
    assert initial.path.exists() is False

    try:
        config_library.rollback_scene_file_mutation(receipt)
    except config_library.SceneTargetRevisionChangedError:
        pass

    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_captured_external_recovery_cleanup_failure_is_retryable(
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(
        scene_id="retry_captured_external_cleanup",
        name="initial",
    )
    external_path = tmp_path / "retry-captured-external.json"
    config_library.save_scene(
        _scene_for_exam(
            scene_id="retry_captured_external_cleanup",
            name="external winner",
        ),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_rename = config_library.os.rename
    real_read_bytes = Path.read_bytes
    injected = False
    failed_read = False

    def move_external_winner(source, destination, *args, **kwargs):
        nonlocal injected
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not injected
            and source_path == initial.path
            and destination_path.name == "displaced.json"
        ):
            config_library.os.replace(external_path, source_path)
            injected = True
        return real_rename(source, destination, *args, **kwargs)

    def fail_displaced_once(path, *args, **kwargs):
        nonlocal failed_read
        if not failed_read and Path(path).name == "displaced.json":
            failed_read = True
            raise PermissionError("injected unreadable captured external occupant")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(config_library.os, "rename", move_external_winner)
    monkeypatch.setattr(Path, "read_bytes", fail_displaced_once)
    with pytest.raises(config_library.SceneTargetRevisionChangedError) as captured:
        config_library.replace_scene_file_if_revision(
            initial.path,
            expected_revision=initial.revision,
            replacement_payload=None,
            retain_recovery=True,
        )
    receipt = getattr(captured.value, "mutation_receipt", None)
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)

    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            raise OSError("injected captured-winner terminal GC failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_once,
    )

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.rollback_scene_file_mutation(receipt)
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path)

    restored_expected = config_library.rollback_scene_file_mutation(receipt)

    assert restored_expected is False
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_coordinator_can_close_after_restoring_expected_post_move_occupant(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="coordinator_expected_occupant",
        name="initial",
    )
    original_payload = initial.path.read_bytes()
    real_read_bytes = Path.read_bytes
    failed_read = False

    def fail_displaced_once(path, *args, **kwargs):
        nonlocal failed_read
        if not failed_read and Path(path).name == "displaced.json":
            failed_read = True
            raise PermissionError("injected unreadable expected occupant")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", fail_displaced_once)

    committed = coordinator.commit_prepared_changes()

    assert committed.success is False
    assert committed.rollback_error is None
    assert failed_read is True
    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()

    rolled_back = coordinator.rollback_prepared_changes()

    assert rolled_back.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False
    assert coordinator.authoritative_user_conflict() is False


def test_coordinator_closes_after_transient_post_publish_verification_failure(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="coordinator_post_publish_probe",
        name="initial",
    )
    original_payload = initial.path.read_bytes()
    real_assert_unique = config_library._assert_scene_publication_is_unique
    failed_probe = False

    def fail_unique_once(*args, **kwargs):
        nonlocal failed_probe
        if not failed_probe:
            failed_probe = True
            raise PermissionError("injected transient post-publish uniqueness failure")
        return real_assert_unique(*args, **kwargs)

    monkeypatch.setattr(
        config_library,
        "_assert_scene_publication_is_unique",
        fail_unique_once,
    )

    committed = coordinator.commit_prepared_changes()

    assert committed.success is False
    assert committed.rollback_error is None
    assert failed_probe is True
    receipt = getattr(committed.error, "mutation_receipt", None)
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    assert receipt.intent == "published_mutation"
    assert receipt.before_revision == initial.revision
    assert receipt.after_revision not in {"", "missing", initial.revision}
    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()

    rolled_back = coordinator.rollback_prepared_changes()

    assert rolled_back.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False
    assert coordinator.authoritative_user_conflict() is False
    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_published_mutation_rollback_preserves_external_exact_path_winner(
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(
        scene_id="published_rollback_external_winner",
        name="initial",
    )
    external_path = tmp_path / "published-rollback-external-winner.json"
    config_library.save_scene(
        _scene_for_exam(
            scene_id="published_rollback_external_winner",
            name="external winner",
        ),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_assert_unique = config_library._assert_scene_publication_is_unique
    injected = False

    def replace_candidate_then_fail(*args, **kwargs):
        nonlocal injected
        if not injected:
            config_library.os.replace(external_path, initial.path)
            injected = True
            raise PermissionError("injected external winner after publication")
        return real_assert_unique(*args, **kwargs)

    monkeypatch.setattr(
        config_library,
        "_assert_scene_publication_is_unique",
        replace_candidate_then_fail,
    )

    with pytest.raises(config_library.SceneTargetRevisionChangedError) as captured:
        config_library.save_scene_to_library(
            _scene_for_exam(
                scene_id="published_rollback_external_winner",
                name="local candidate",
            ),
            scene_id="published_rollback_external_winner",
            mode_id="exam",
            expected_revision=initial.revision,
        )

    receipt = getattr(captured.value, "mutation_receipt", None)
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    assert receipt.intent == "published_mutation"
    assert injected is True
    assert initial.path.read_bytes() == external_payload

    restored_expected = config_library.rollback_scene_file_mutation(receipt)

    assert restored_expected is False
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_coordinator_closes_after_published_external_exact_path_winner(
    qapp,
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="coordinator_published_external_winner",
        name="initial",
    )
    external_path = tmp_path / "coordinator-published-external-winner.json"
    config_library.save_scene(
        _scene_for_exam(
            scene_id="coordinator_published_external_winner",
            name="external winner",
        ),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_assert_unique = config_library._assert_scene_publication_is_unique
    injected = False

    def replace_candidate_then_fail(*args, **kwargs):
        nonlocal injected
        if not injected:
            config_library.os.replace(external_path, initial.path)
            injected = True
            raise PermissionError("injected external winner after publication")
        return real_assert_unique(*args, **kwargs)

    monkeypatch.setattr(
        config_library,
        "_assert_scene_publication_is_unique",
        replace_candidate_then_fail,
    )

    committed = coordinator.commit_prepared_changes()
    prepared = coordinator.prepared_changes

    assert committed.success is False
    assert committed.rollback_error is None
    receipt = getattr(committed.error, "mutation_receipt", None)
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    assert receipt.intent == "published_mutation"
    assert injected is True
    assert prepared is not None
    assert prepared.external_revision_conflict is True
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()

    rolled_back = coordinator.rollback_prepared_changes()

    assert rolled_back.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False
    assert coordinator.authoritative_user_conflict() is True
    assert initial.path.read_bytes() == external_payload


def test_published_mutation_rollback_cleanup_failure_is_retryable(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(
        scene_id="published_rollback_cleanup_retry",
        name="initial",
    )
    original_payload = initial.path.read_bytes()
    real_assert_unique = config_library._assert_scene_publication_is_unique
    failed_probe = False

    def fail_unique_once(*args, **kwargs):
        nonlocal failed_probe
        if not failed_probe:
            failed_probe = True
            raise PermissionError("injected transient post-publish verification")
        return real_assert_unique(*args, **kwargs)

    monkeypatch.setattr(
        config_library,
        "_assert_scene_publication_is_unique",
        fail_unique_once,
    )
    with pytest.raises(config_library.SceneTargetRevisionChangedError) as captured:
        config_library.save_scene_to_library(
            _scene_for_exam(
                scene_id="published_rollback_cleanup_retry",
                name="local candidate",
            ),
            scene_id="published_rollback_cleanup_retry",
            mode_id="exam",
            expected_revision=initial.revision,
        )
    receipt = getattr(captured.value, "mutation_receipt", None)
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    assert receipt.intent == "published_mutation"

    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            raise OSError("injected published rollback evidence cleanup failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_once,
    )

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.rollback_scene_file_mutation(receipt)
    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path)

    restored_expected = config_library.rollback_scene_file_mutation(receipt)

    assert restored_expected is True
    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_published_external_winner_cleanup_failure_is_retryable(
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(
        scene_id="published_external_cleanup_retry",
        name="initial",
    )
    external_path = tmp_path / "published-external-cleanup-retry.json"
    config_library.save_scene(
        _scene_for_exam(
            scene_id="published_external_cleanup_retry",
            name="external winner",
        ),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_assert_unique = config_library._assert_scene_publication_is_unique
    injected = False

    def replace_candidate_then_fail(*args, **kwargs):
        nonlocal injected
        if not injected:
            config_library.os.replace(external_path, initial.path)
            injected = True
            raise PermissionError("injected external winner after publication")
        return real_assert_unique(*args, **kwargs)

    monkeypatch.setattr(
        config_library,
        "_assert_scene_publication_is_unique",
        replace_candidate_then_fail,
    )
    with pytest.raises(config_library.SceneTargetRevisionChangedError) as captured:
        config_library.save_scene_to_library(
            _scene_for_exam(
                scene_id="published_external_cleanup_retry",
                name="local candidate",
            ),
            scene_id="published_external_cleanup_retry",
            mode_id="exam",
            expected_revision=initial.revision,
        )
    receipt = getattr(captured.value, "mutation_receipt", None)
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)

    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            raise OSError("injected external-winner cleanup failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_once,
    )

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.rollback_scene_file_mutation(receipt)
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path)

    restored_expected = config_library.rollback_scene_file_mutation(receipt)

    assert restored_expected is False
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_coordinator_closes_after_restoring_captured_external_winner(
    qapp,
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="coordinator_captured_winner",
        name="initial",
    )
    external_path = tmp_path / "coordinator-captured-winner.json"
    config_library.save_scene(
        _scene_for_exam(
            scene_id="coordinator_captured_winner",
            name="external winner",
        ),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_rename = config_library.os.rename
    real_read_bytes = Path.read_bytes
    injected = False
    failed_read = False

    def move_external_winner(source, destination, *args, **kwargs):
        nonlocal injected
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not injected
            and source_path == initial.path
            and destination_path.name == "displaced.json"
        ):
            config_library.os.replace(external_path, source_path)
            injected = True
        return real_rename(source, destination, *args, **kwargs)

    def fail_displaced_once(path, *args, **kwargs):
        nonlocal failed_read
        if not failed_read and Path(path).name == "displaced.json":
            failed_read = True
            raise PermissionError("injected unreadable captured external winner")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(config_library.os, "rename", move_external_winner)
    monkeypatch.setattr(Path, "read_bytes", fail_displaced_once)

    committed = coordinator.commit_prepared_changes()
    prepared = coordinator.prepared_changes

    assert committed.success is False
    assert committed.rollback_error is None
    assert injected is True
    assert failed_read is True
    assert prepared is not None
    assert prepared.external_revision_conflict is True
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()

    rolled_back = coordinator.rollback_prepared_changes()

    assert rolled_back.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False
    assert coordinator.authoritative_user_conflict() is True
    assert initial.path.read_bytes() == external_payload


def test_restore_captured_receipt_cannot_be_finalized_as_a_delete(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(
        scene_id="restore_receipt_direction",
        name="initial",
    )
    original_payload = initial.path.read_bytes()
    real_read_bytes = Path.read_bytes
    failed = False

    def fail_displaced_once(path, *args, **kwargs):
        nonlocal failed
        if not failed and Path(path).name == "displaced.json":
            failed = True
            raise PermissionError("injected unreadable captured occupant")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", fail_displaced_once)
    with pytest.raises(config_library.SceneTargetRevisionChangedError) as captured:
        config_library.replace_scene_file_if_revision(
            initial.path,
            expected_revision=initial.revision,
            replacement_payload=None,
            retain_recovery=True,
        )
    receipt = getattr(captured.value, "mutation_receipt", None)
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    assert receipt.intent == "restore_captured"

    with pytest.raises(
        (ValueError, config_library.SceneTargetRevisionChangedError)
    ):
        config_library.finalize_scene_file_mutation(receipt)

    assert receipt.displaced_path.read_bytes() == original_payload
    assert receipt.recovery_dir in config_library.scene_recovery_artifacts(
        initial.path
    )


def test_create_cleanup_does_not_unlink_replacement_after_samefile_check(
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    target = config_library.scene_user_target_path("create_cleanup_gap", mode_id="exam")
    external_path = tmp_path / "create-cleanup-external.json"
    config_library.save_scene(
        _scene_for_exam(
            scene_id="create_cleanup_gap",
            name="external winner",
        ),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_rename = config_library.os.rename
    replacement_injected = False

    def replace_before_withdraw(source, destination, *args, **kwargs):
        nonlocal replacement_injected
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not replacement_injected
            and source_path == target
            and destination_path.name == "captured.json"
        ):
            config_library.os.replace(external_path, source_path)
            replacement_injected = True
        return real_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(config_library.os, "rename", replace_before_withdraw)
    monkeypatch.setattr(
        config_library,
        "_assert_scene_publication_is_unique",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("injected create verification failure")
        ),
    )

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.save_scene_to_library(
            _scene_for_exam(
                scene_id="create_cleanup_gap",
                name="local create",
            ),
            scene_id="create_cleanup_gap",
            mode_id="exam",
            expected_absent=True,
        )

    assert replacement_injected is True
    assert target.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(target) == ()


def test_create_post_link_verification_error_never_leaves_published_orphan(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    target = config_library.scene_user_target_path(
        "create_verification_orphan",
        mode_id="exam",
    )

    monkeypatch.setattr(
        config_library,
        "_assert_scene_publication_is_unique",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("injected directory verification failure")
        ),
    )

    with pytest.raises(ValueError, match="directory verification failure"):
        config_library.save_scene_to_library(
            _scene_for_exam(
                scene_id="create_verification_orphan",
                name="local create",
            ),
            scene_id="create_verification_orphan",
            mode_id="exam",
            expected_absent=True,
        )

    assert target.exists() is False


def test_committed_update_is_not_reported_as_failed_when_evidence_gc_fails_once(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="gc_after_commit", name="initial")
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            raise OSError("injected evidence GC failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_once,
    )

    receipt = config_library.save_scene_to_library(
        _scene_for_exam(scene_id="gc_after_commit", name="local update"),
        scene_id="gc_after_commit",
        mode_id="exam",
        expected_revision=initial.revision,
    )

    assert receipt.revision == config_library.scene_file_revision(initial.path)


def test_post_commit_recovery_enumeration_error_does_not_hide_the_save_receipt(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="post_commit_enumeration", name="initial")
    real_artifacts = config_library.scene_recovery_artifacts
    artifact_calls = 0

    def fail_after_publication(path):
        nonlocal artifact_calls
        artifact_calls += 1
        if artifact_calls == 2:
            raise PermissionError("injected post-commit recovery enumeration failure")
        return real_artifacts(path)

    monkeypatch.setattr(
        config_library,
        "scene_recovery_artifacts",
        fail_after_publication,
    )

    receipt = config_library.save_scene_to_library(
        _scene_for_exam(
            scene_id="post_commit_enumeration",
            name="local update",
        ),
        scene_id="post_commit_enumeration",
        mode_id="exam",
        expected_revision=initial.revision,
    )

    assert artifact_calls >= 2
    assert receipt.revision == config_library.scene_file_revision(initial.path)
    assert (
        config_library.load_scene_from_library(
            "post_commit_enumeration",
            mode_id="exam",
        ).name
        == "local update"
    )


def test_create_cleanup_value_error_does_not_hide_the_save_receipt(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    target = config_library.scene_user_target_path(
        "create_cleanup_value_error",
        mode_id="exam",
    )
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            raise ValueError("injected create cleanup path validation failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_once,
    )

    receipt = config_library.save_scene_to_library(
        _scene_for_exam(
            scene_id="create_cleanup_value_error",
            name="local create",
        ),
        scene_id="create_cleanup_value_error",
        mode_id="exam",
        expected_absent=True,
    )

    assert receipt.path == target
    assert receipt.revision == config_library.scene_file_revision(target)
    assert config_library.scene_recovery_artifacts(target) == ()


def test_unreadable_post_commit_recovery_namespace_blocks_outer_finalize(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="unreadable_post_commit_recovery",
        name="initial",
    )
    real_artifacts = config_library.scene_recovery_artifacts

    def fail_after_publication(path):
        if config_library.scene_file_revision(path) != initial.revision:
            raise PermissionError("injected unreadable recovery namespace")
        return real_artifacts(path)

    monkeypatch.setattr(
        config_library,
        "scene_recovery_artifacts",
        fail_after_publication,
    )

    committed = coordinator.commit_prepared_changes()

    assert committed.success is True
    assert coordinator.prepared_changes is not None
    assert coordinator.prepared_changes.recovery_path is not None
    assert coordinator.recovery_required() is True

    finalized = coordinator.finalize_prepared_changes()

    assert finalized.success is False
    assert isinstance(finalized.error, PermissionError)
    assert coordinator.prepared_changes is not None
    assert coordinator.recovery_required() is True


def test_recovered_post_commit_recovery_namespace_can_finalize(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="recovered_post_commit_recovery",
        name="initial",
    )
    real_artifacts = config_library.scene_recovery_artifacts
    namespace_unreadable = True

    def fail_after_publication(path):
        if (
            namespace_unreadable
            and config_library.scene_file_revision(path) != initial.revision
        ):
            raise PermissionError("injected unreadable recovery namespace")
        return real_artifacts(path)

    monkeypatch.setattr(
        config_library,
        "scene_recovery_artifacts",
        fail_after_publication,
    )

    committed = coordinator.commit_prepared_changes()
    assert committed.success is True
    assert coordinator.recovery_required() is True
    assert coordinator.finalize_prepared_changes().success is False

    namespace_unreadable = False
    finalized = coordinator.finalize_prepared_changes()

    assert finalized.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False


def test_successful_commit_cannot_finalize_with_hidden_cleanup_artifacts(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="hidden_cleanup_evidence",
        name="initial",
    )
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            raise OSError("injected cleanup failure after commit")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_once,
    )

    result = coordinator.commit_prepared_changes()
    artifacts = config_library.scene_recovery_artifacts(initial.path)

    if artifacts:
        finalized = coordinator.finalize_prepared_changes()
        remaining = config_library.scene_recovery_artifacts(initial.path)
        assert not (finalized.success and remaining)
        if remaining:
            assert coordinator.prepared_changes is not None
            assert coordinator.recovery_required() is True
    else:
        assert result.success is True
        assert coordinator.recovery_required() is False


def test_persistent_committed_cleanup_evidence_blocks_outer_finalize(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="persistent_cleanup_evidence",
        name="initial",
    )

    def always_fail_discard(_recovery_dir, *, ignore_errors=False):
        del ignore_errors
        raise OSError("injected persistent evidence GC failure")

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        always_fail_discard,
    )

    committed = coordinator.commit_prepared_changes()
    artifacts = config_library.scene_recovery_artifacts(initial.path)

    assert artifacts
    assert not isinstance(committed.error, NameError)
    assert committed.success is False or coordinator.recovery_required() is True
    finalized = coordinator.finalize_prepared_changes()
    assert finalized.success is False
    assert coordinator.prepared_changes is not None
    assert config_library.scene_recovery_artifacts(initial.path)


def test_committed_cleanup_finalize_retry_clears_recovery_state(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="retry_committed_cleanup",
        name="initial",
    )
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_three_times(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls <= 3:
            raise OSError("injected retryable committed cleanup failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_three_times,
    )

    committed = coordinator.commit_prepared_changes()
    assert committed.success is True
    assert config_library.scene_recovery_artifacts(initial.path)

    first_finalize = coordinator.finalize_prepared_changes()
    assert first_finalize.success is False
    second_finalize = coordinator.finalize_prepared_changes()

    assert second_finalize.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_finalize_cleanup_failure_can_then_roll_back_the_committed_save(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="rollback_after_cleanup_failure",
        name="initial",
    )
    original_payload = initial.path.read_bytes()
    real_discard = config_library._discard_scene_recovery_directory

    def always_fail_discard(_recovery_dir, *, ignore_errors=False):
        del ignore_errors
        raise OSError("injected committed cleanup failure")

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        always_fail_discard,
    )

    committed = coordinator.commit_prepared_changes()
    assert committed.success is True
    assert config_library.scene_recovery_artifacts(initial.path)
    assert coordinator.finalize_prepared_changes().success is False

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        real_discard,
    )
    rolled_back = coordinator.rollback_prepared_changes()

    assert rolled_back.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False
    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_rollback_cleanup_failure_can_be_retried_to_completion(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="retry_rollback_cleanup",
        name="initial",
    )
    original_payload = initial.path.read_bytes()
    assert coordinator.commit_prepared_changes().success is True
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_twice(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls <= 2:
            raise OSError("injected rollback evidence GC failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_twice,
    )

    first_rollback = coordinator.rollback_prepared_changes()
    prepared = coordinator.prepared_changes

    assert first_rollback.success is False
    assert prepared is not None
    assert prepared.file_rollback_completed is True
    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path)

    second_rollback = coordinator.rollback_prepared_changes()

    assert second_rollback.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False
    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_create_rollback_cleanup_failure_can_be_retried_to_completion(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, target = _coordinator_for_builtin_fork(
        fork_id="retry_create_rollback_cleanup",
    )
    assert target.exists() is False
    assert coordinator.commit_prepared_changes().success is True
    assert target.exists() is True
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_twice(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls <= 2:
            raise OSError("injected create rollback evidence GC failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_twice,
    )

    first_rollback = coordinator.rollback_prepared_changes()
    prepared = coordinator.prepared_changes

    assert first_rollback.success is False
    assert prepared is not None
    assert prepared.file_rollback_completed is True
    assert target.exists() is False
    assert config_library.scene_recovery_artifacts(target)

    second_rollback = coordinator.rollback_prepared_changes()

    assert second_rollback.success is True
    assert coordinator.prepared_changes is None
    assert coordinator.recovery_required() is False
    assert target.exists() is False
    assert config_library.scene_recovery_artifacts(target) == ()


def test_stale_update_that_restores_winner_does_not_permanently_lock_identity(
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="stale_writer", name="initial")
    external_path = tmp_path / "stale-writer-winner.json"
    config_library.save_scene(
        _scene_for_exam(scene_id="stale_writer", name="external winner"),
        external_path,
    )
    external_payload = external_path.read_bytes()
    real_rename = config_library.os.rename
    injected = False

    def move_winner(source, destination, *args, **kwargs):
        nonlocal injected
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not injected
            and source_path == initial.path
            and destination_path.name == "displaced.json"
        ):
            config_library.os.replace(external_path, source_path)
            injected = True
        return real_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(config_library.os, "rename", move_winner)

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.save_scene_to_library(
            _scene_for_exam(scene_id="stale_writer", name="stale local update"),
            scene_id="stale_writer",
            mode_id="exam",
            expected_revision=initial.revision,
        )

    assert injected is True
    assert initial.path.read_bytes() == external_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_conditional_scene_mutation_refuses_a_casefold_neighbor(
    isolated_scene_library: Path,
) -> None:
    del isolated_scene_library
    scene_id = "StraßeConditional"
    neighbor_id = "STRASSECONDITIONAL"
    assert scene_id.casefold() == neighbor_id.casefold()
    initial = _new_user_scene(scene_id=scene_id, name="initial")
    initial_payload = initial.path.read_bytes()
    neighbor = initial.path.parent / f"{neighbor_id}.json"
    config_library.save_scene(
        _scene_for_exam(scene_id=neighbor_id, name="external neighbor"),
        neighbor,
    )
    neighbor_payload = neighbor.read_bytes()

    with pytest.raises(
        (
            config_library.ConfigReferenceResolutionError,
            config_library.SceneTargetRevisionChangedError,
        )
    ):
        config_library.replace_scene_file_if_revision(
            initial.path,
            expected_revision=initial.revision,
            replacement_payload=initial_payload,
        )

    assert initial.path.read_bytes() == initial_payload
    assert neighbor.read_bytes() == neighbor_payload


def test_retained_delete_rollback_refuses_a_casefold_neighbor(
    isolated_scene_library: Path,
) -> None:
    del isolated_scene_library
    scene_id = "StraßeRetainedDelete"
    neighbor_id = "STRASSERETAINEDDELETE"
    initial = _new_user_scene(scene_id=scene_id, name="initial")
    receipt = config_library.replace_scene_file_if_revision(
        initial.path,
        expected_revision=initial.revision,
        replacement_payload=None,
        retain_recovery=True,
    )
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    neighbor = initial.path.parent / f"{neighbor_id}.json"
    config_library.save_scene(
        _scene_for_exam(scene_id=neighbor_id, name="external neighbor"),
        neighbor,
    )
    neighbor_payload = neighbor.read_bytes()

    with pytest.raises(
        (
            config_library.ConfigReferenceResolutionError,
            config_library.SceneTargetRevisionChangedError,
        )
    ):
        config_library.rollback_scene_file_mutation(receipt)

    assert initial.path.exists() is False
    assert neighbor.read_bytes() == neighbor_payload
    assert config_library.scene_recovery_artifacts(initial.path)


def test_retained_delete_finalize_is_idempotent_after_cleanup_failure(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="retry_finalize_delete", name="initial")
    receipt = config_library.replace_scene_file_if_revision(
        initial.path,
        expected_revision=initial.revision,
        replacement_payload=None,
        retain_recovery=True,
    )
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            manifest = Path(recovery_dir) / "manifest.json"
            if manifest.exists():
                manifest.unlink()
            raise OSError("injected retained finalize GC failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_once,
    )

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.finalize_scene_file_mutation(receipt)
    config_library.finalize_scene_file_mutation(receipt)

    assert initial.path.exists() is False
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_retained_delete_rollback_is_idempotent_after_cleanup_failure(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="retry_rollback_delete", name="initial")
    original_payload = initial.path.read_bytes()
    receipt = config_library.replace_scene_file_if_revision(
        initial.path,
        expected_revision=initial.revision,
        replacement_payload=None,
        retain_recovery=True,
    )
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    real_discard = config_library._discard_scene_recovery_directory
    discard_calls = 0

    def fail_once(recovery_dir, *, ignore_errors=False):
        nonlocal discard_calls
        discard_calls += 1
        if discard_calls == 1:
            manifest = Path(recovery_dir) / "manifest.json"
            if manifest.exists():
                manifest.unlink()
            raise OSError("injected retained rollback GC failure")
        return real_discard(recovery_dir, ignore_errors=ignore_errors)

    monkeypatch.setattr(
        config_library,
        "_discard_scene_recovery_directory",
        fail_once,
    )

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.rollback_scene_file_mutation(receipt)
    config_library.rollback_scene_file_mutation(receipt)

    assert initial.path.read_bytes() == original_payload
    assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_retained_delete_manifest_failure_restores_or_reports_recovery_path(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="retained_manifest_failure", name="initial")
    original_payload = initial.path.read_bytes()
    real_write_manifest = config_library._write_scene_recovery_manifest

    def fail_retained_manifest(recovery_dir, **kwargs):
        if kwargs.get("phase") == "conditional_delete_retained":
            raise OSError("injected retained manifest failure")
        return real_write_manifest(recovery_dir, **kwargs)

    monkeypatch.setattr(
        config_library,
        "_write_scene_recovery_manifest",
        fail_retained_manifest,
    )

    try:
        receipt = config_library.replace_scene_file_if_revision(
            initial.path,
            expected_revision=initial.revision,
            replacement_payload=None,
            retain_recovery=True,
        )
    except Exception as exc:
        recovery_path = getattr(exc, "recovery_path", None)
        assert initial.path.exists() or recovery_path is not None
        if initial.path.exists():
            assert initial.path.read_bytes() == original_payload
        else:
            assert recovery_path in config_library.scene_recovery_artifacts(
                initial.path
            )
    else:
        assert isinstance(receipt, config_library.SceneFileMutationReceipt)
        assert initial.path.exists() is False
        assert receipt.recovery_dir in config_library.scene_recovery_artifacts(
            initial.path
        )
        config_library.rollback_scene_file_mutation(receipt)
        assert initial.path.read_bytes() == original_payload
        assert config_library.scene_recovery_artifacts(initial.path) == ()


def test_committed_delete_cleanup_never_consumes_an_unrelated_retained_receipt(
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(
        scene_id="unrelated_retained_delete",
        name="initial",
    )
    original_payload = initial.path.read_bytes()
    real_write_manifest = config_library._write_scene_recovery_manifest

    def interrupt_retained_manifest(recovery_dir, **kwargs):
        if kwargs.get("phase") == "conditional_delete_retained":
            raise KeyboardInterrupt("injected interruption before retained marker")
        return real_write_manifest(recovery_dir, **kwargs)

    monkeypatch.setattr(
        config_library,
        "_write_scene_recovery_manifest",
        interrupt_retained_manifest,
    )
    with pytest.raises(KeyboardInterrupt):
        config_library.replace_scene_file_if_revision(
            initial.path,
            expected_revision=initial.revision,
            replacement_payload=None,
            retain_recovery=True,
        )
    artifacts = config_library.scene_recovery_artifacts(initial.path)
    assert len(artifacts) == 1
    displaced_path = artifacts[0] / "displaced.json"
    assert displaced_path.read_bytes() == original_payload

    with pytest.raises(ValueError):
        config_library.finalize_committed_scene_recovery(
            initial.path,
            expected_revision="missing",
        )

    assert displaced_path.read_bytes() == original_payload
    assert artifacts[0] in config_library.scene_recovery_artifacts(initial.path)


def test_retained_delete_rollback_never_succeeds_when_target_and_evidence_are_missing(
    isolated_scene_library: Path,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="missing_delete_evidence", name="initial")
    receipt = config_library.replace_scene_file_if_revision(
        initial.path,
        expected_revision=initial.revision,
        replacement_payload=None,
        retain_recovery=True,
    )
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)
    config_library._discard_scene_recovery_directory(receipt.recovery_dir)

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.rollback_scene_file_mutation(receipt)

    assert initial.path.exists() is False


def test_rolled_back_delete_receipt_cannot_later_report_finalize_success(
    isolated_scene_library: Path,
) -> None:
    del isolated_scene_library
    initial = _new_user_scene(scene_id="finalize_after_rollback", name="initial")
    original_payload = initial.path.read_bytes()
    receipt = config_library.replace_scene_file_if_revision(
        initial.path,
        expected_revision=initial.revision,
        replacement_payload=None,
        retain_recovery=True,
    )
    assert isinstance(receipt, config_library.SceneFileMutationReceipt)

    config_library.rollback_scene_file_mutation(receipt)
    assert initial.path.read_bytes() == original_payload

    with pytest.raises(config_library.SceneTargetRevisionChangedError):
        config_library.finalize_scene_file_mutation(receipt)

    assert initial.path.read_bytes() == original_payload


def test_casefold_update_preserves_the_persisted_scene_id_spelling(
    isolated_scene_library: Path,
) -> None:
    del isolated_scene_library
    persisted_id = "PersistedCase"
    initial = _new_user_scene(scene_id=persisted_id, name="initial")

    with pytest.raises(
        config_library.ConfigReferenceResolutionError,
        match="plan_update_identity_case_mismatch",
    ):
        config_library.save_scene_to_library(
            _scene_for_exam(scene_id=persisted_id.lower(), name="updated"),
            scene_id=persisted_id.lower(),
            mode_id="exam",
            expected_revision=initial.revision,
        )

    assert initial.path.stem == persisted_id
    assert config_library.load_scene(initial.path).scene_id == persisted_id
    assert (
        config_library.load_scene_from_library(persisted_id, mode_id="exam").scene_id
        == persisted_id
    )


def test_receipt_mismatch_rollback_preserves_external_target_and_evidence(
    qapp,
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="receipt_race",
        name="initial",
    )
    external_path = tmp_path / "receipt-race-external.json"
    config_library.save_scene(
        _scene_for_exam(scene_id="receipt_race", name="external winner"),
        external_path,
    )
    external_payload = external_path.read_bytes()
    original_record = coordinator._record_commit_candidate

    def replace_before_receipt_snapshot(prepared, entry) -> None:
        config_library.os.replace(external_path, initial.path)
        original_record(prepared, entry)

    monkeypatch.setattr(
        coordinator,
        "_record_commit_candidate",
        replace_before_receipt_snapshot,
    )

    result = coordinator.commit_prepared_changes()
    prepared = coordinator.prepared_changes

    assert result.success is False
    assert prepared is not None
    assert initial.path.read_bytes() == external_payload
    assert prepared.recovery_required is True


def test_directory_rollback_never_deletes_adjacent_external_create(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="adjacent_race",
        name="initial",
    )
    adjacent = initial.path.parent / "external_neighbor.json"
    external_scene = _scene_for_exam(
        scene_id="external_neighbor",
        name="external neighbor",
    )
    original_record = coordinator._record_commit_candidate

    def create_neighbor_before_directory_snapshot(prepared, entry) -> None:
        config_library.save_scene(external_scene, adjacent)
        original_record(prepared, entry)

    monkeypatch.setattr(
        coordinator,
        "_record_commit_candidate",
        create_neighbor_before_directory_snapshot,
    )

    result = coordinator.commit_prepared_changes()
    prepared = coordinator.prepared_changes

    assert result.success is False
    assert prepared is not None
    assert adjacent.exists() is True
    assert config_library.load_scene(adjacent).name == "external neighbor"
    assert prepared.recovery_required is True


def test_external_replace_before_adoption_cannot_report_commit_success(
    qapp,
    isolated_scene_library: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="adoption_race",
        name="initial",
    )
    external_path = tmp_path / "adoption-race-external.json"
    config_library.save_scene(
        _scene_for_exam(scene_id="adoption_race", name="external winner"),
        external_path,
    )
    external_payload = external_path.read_bytes()
    original_adopt = coordinator._adopt_committed_scene

    def replace_before_adoption(*args, **kwargs) -> None:
        config_library.os.replace(external_path, initial.path)
        original_adopt(*args, **kwargs)

    monkeypatch.setattr(coordinator, "_adopt_committed_scene", replace_before_adoption)

    result = coordinator.commit_prepared_changes()

    assert initial.path.read_bytes() == external_payload
    assert result.success is False
    assert bridge.is_scene_dirty() is True
    assert coordinator.authoritative_user_conflict() is True


def test_completed_rollback_cannot_reclaim_later_identical_external_bytes(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="stale_receipt",
        name="initial",
    )

    def fail_adoption(*_args, **_kwargs) -> None:
        raise RuntimeError("injected adoption failure")

    monkeypatch.setattr(coordinator, "_adopt_committed_scene", fail_adoption)
    first_result = coordinator.commit_prepared_changes()
    prepared = coordinator.prepared_changes

    assert first_result.success is False
    assert first_result.rollback_error is None
    assert prepared is not None
    assert prepared.committed_after is not None
    assert prepared.committed_after.payload is not None
    externally_recreated = prepared.committed_after.payload
    config_library.atomic_write_bytes(initial.path, externally_recreated)

    second_result = coordinator.rollback_prepared_changes()

    assert second_result.success is True
    assert initial.path.read_bytes() == externally_recreated


def test_successful_rollback_cas_consumes_receipt_before_live_verification(
    qapp,
    isolated_scene_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, initial = _coordinator_for_user_scene(
        scene_id="rollback_receipt_consumption",
        name="initial",
    )

    monkeypatch.setattr(
        coordinator,
        "_adopt_committed_scene",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("injected adoption failure")
        ),
    )
    real_replace = config_library.replace_scene_file_if_revision
    rollback_calls = 0
    external_payload = b""

    def replace_then_recreate_same_receipt(path, **kwargs):
        nonlocal rollback_calls, external_payload
        rollback_calls += 1
        target = Path(path)
        if rollback_calls == 1:
            external_payload = target.read_bytes()
        result = real_replace(path, **kwargs)
        if rollback_calls == 1:
            config_library.atomic_write_bytes(target, external_payload)
        return result

    monkeypatch.setattr(
        config_library,
        "replace_scene_file_if_revision",
        replace_then_recreate_same_receipt,
    )

    first_result = coordinator.commit_prepared_changes()
    prepared = coordinator.prepared_changes

    assert first_result.success is False
    assert first_result.rollback_error is not None
    assert prepared is not None
    assert initial.path.read_bytes() == external_payload

    second_result = coordinator.rollback_prepared_changes()

    assert second_result.success is True
    assert rollback_calls == 1
    assert initial.path.read_bytes() == external_payload


def test_update_user_reuses_authoritative_uppercase_json_path(
    qapp,
    isolated_scene_library: Path,
) -> None:
    del qapp, isolated_scene_library
    scene_id = "UpperSuffixPlan"
    path = config_library.scene_user_dir("exam") / f"{scene_id}.JSON"
    config_library.save_scene(
        _scene_for_exam(scene_id=scene_id, name="uppercase suffix"),
        path,
    )
    bridge = PanelBridge()
    bridge.set_current_work_mode("exam", emit_signal=False)
    bridge.set_current_scene(
        config_library.load_scene_from_library(scene_id, mode_id="exam"),
        config_id=scene_id,
        path=str(path),
        source="library",
        source_type="user",
        emit_signal=False,
    )
    bridge.commit_pending_work_mode_transition()
    coordinator = SceneSessionCoordinator(
        bridge,
        SceneProjectionCallbacks(
            apply_scene=lambda _scene, _template: None,
            refresh_scene_selector=lambda: None,
            selected_card_id=lambda: "overview",
            restore_selected_card=lambda _card_id: None,
            refresh_navigation_cards=lambda: None,
        ),
    )

    target = coordinator.build_save_target(mode_id="exam")

    assert str(target.target_path) == str(path)


def test_recovery_required_transaction_rejects_second_commit(
    qapp,
    isolated_scene_library: Path,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, _entry = _coordinator_for_user_scene(
        scene_id="recovery_recommit",
        name="initial",
    )
    prepared = coordinator.prepared_changes
    assert prepared is not None
    prepared.recovery_required = True
    save_called = False

    def forbidden_save(*_args, **_kwargs):
        nonlocal save_called
        save_called = True
        raise AssertionError("recovery evidence must block a second publication")

    prepared.save_callable = forbidden_save

    result = coordinator.commit_prepared_changes()

    assert result.success is False
    assert save_called is False
    assert coordinator.prepared_changes is prepared
    assert prepared.recovery_required is True


def test_finalize_never_clears_recovery_required_evidence(
    qapp,
    isolated_scene_library: Path,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, _entry = _coordinator_for_user_scene(
        scene_id="recovery_finalize",
        name="initial",
    )
    prepared = coordinator.prepared_changes
    assert prepared is not None
    prepared.recovery_required = True

    result = coordinator.finalize_prepared_changes()

    assert result.success is False
    assert coordinator.prepared_changes is prepared
    assert prepared.recovery_required is True


def test_release_never_clears_recovery_required_evidence(
    qapp,
    isolated_scene_library: Path,
) -> None:
    del qapp, isolated_scene_library
    _bridge, coordinator, _entry = _coordinator_for_user_scene(
        scene_id="recovery_release",
        name="initial",
    )
    prepared = coordinator.prepared_changes
    assert prepared is not None
    prepared.committed = True
    prepared.recovery_required = True

    result = coordinator.release_finalized_changes()

    assert result.success is False
    assert coordinator.prepared_changes is prepared
    assert prepared.recovery_required is True
