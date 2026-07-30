from __future__ import annotations

import ast
from copy import deepcopy
import json
import os
from pathlib import Path
from shutil import copy2
import subprocess
import sys
import textwrap

from docx import Document
import pytest

from src.shared.io.artifact_transaction import (
    OwnedAssemblyTransaction,
    TransactionViolation,
    stable_file_evidence,
)
from src.shared.io import artifact_transaction as transaction_module
from src.shared.engine.office_image_layout import (
    LAYOUT_SHADOW_PREFIX,
    build_controlled_layout_shadow_path,
    layout_shadow_source_id,
)


def _save_docx(path: Path, text: str = "owned stage") -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(path)


def _subprocess_environment(finals: tuple[Path, ...], work_root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment["LARK_TRANSACTION_FINALS"] = json.dumps(
        [str(path) for path in finals]
    )
    environment["LARK_TRANSACTION_WORK_ROOT"] = str(work_root)
    return environment


def _claim_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.json")
        if path.parent.name == "claims"
        and path.parent.parent.name == ".lark-material-transactions"
    ]


@pytest.fixture
def valid_journal_payload(tmp_path: Path):
    final = tmp_path / "final.docx"
    _save_docx(final, "old-final")
    transaction = OwnedAssemblyTransaction(
        execution_id="journal-parser",
        final_paths=(final,),
        work_root=tmp_path,
    )
    stage = transaction.allocate_stage("final", final)
    _save_docx(stage, "candidate")
    candidate = stable_file_evidence(stage)
    baseline = transaction._baselines[0]
    assert baseline.evidence is not None
    assert baseline.backup_path is not None
    assert baseline.backup_evidence is not None
    payload = {
        "schema": transaction_module._JOURNAL_SCHEMA,
        "schema_version": transaction_module._JOURNAL_SCHEMA_VERSION,
        "final_set_id": transaction.final_set_id,
        "execution_id": transaction.execution_id,
        "status": "prepared",
        "final_paths": [str(final.resolve())],
        "work_dir": str(transaction.work_dir),
        "owned_paths": [
            str(path)
            for path in sorted(transaction._owned_files, key=str)
        ],
        "active_replace_final_path": None,
        "published_final_paths": [],
        "finals": [
            {
                "path": str(final.resolve()),
                "existed": True,
                "baseline": baseline.evidence.to_dict(),
                "backup_path": str(baseline.backup_path),
                "backup": baseline.backup_evidence.to_dict(),
                "candidate": candidate.to_dict(),
                "progress": "pending",
            }
        ],
    }
    journal = tmp_path / "journal-under-test.json"
    journal.write_text(json.dumps(payload), encoding="utf-8")
    transaction._load_journal_record(
        journal,
        expected_final_set_id=transaction.final_set_id,
        expected_final_paths=transaction.final_paths,
    )
    try:
        yield transaction, journal, payload, final, stage
    finally:
        transaction.cleanup_owned()


def _assert_journal_invalid(
    fixture,
    payload: dict[str, object],
    message: str,
) -> None:
    transaction, journal, _valid, _final, _stage = fixture
    journal.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TransactionViolation, match=message) as captured:
        transaction._load_journal_record(
            journal,
            expected_final_set_id=transaction.final_set_id,
            expected_final_paths=transaction.final_paths,
        )
    assert captured.value.code == "JOURNAL_INVALID"


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("invalid_json", "cannot read publish journal"),
        ("root_not_object", "root is not an object"),
        ("wrong_schema", "identity or schema does not match"),
        ("empty_execution", "execution_id is invalid"),
        ("unknown_status", "status is invalid"),
        ("status_not_scalar", "status is invalid"),
        ("wrong_final_identity", "final-set identity is invalid"),
    ),
)
def test_journal_parser_rejects_malformed_root_header_and_identity(
    valid_journal_payload,
    case: str,
    message: str,
) -> None:
    transaction, journal, valid, _final, _stage = valid_journal_payload
    payload = deepcopy(valid)
    if case == "invalid_json":
        journal.write_text("{", encoding="utf-8")
    elif case == "root_not_object":
        journal.write_text("[]", encoding="utf-8")
    else:
        if case == "wrong_schema":
            payload["schema_version"] = -1
        elif case == "empty_execution":
            payload["execution_id"] = ""
        elif case == "unknown_status":
            payload["status"] = "unknown"
        elif case == "status_not_scalar":
            payload["status"] = []
        else:
            payload["final_set_id"] = "0" * 64
        journal.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TransactionViolation, match=message) as captured:
        transaction._load_journal_record(
            journal,
            expected_final_set_id=transaction.final_set_id,
            expected_final_paths=transaction.final_paths,
        )
    assert captured.value.code == "JOURNAL_INVALID"


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("candidate_not_object", "candidate is invalid"),
        ("backup_mismatch", "backup does not match baseline"),
        ("backup_for_new_final", "backup data for a new final"),
        ("candidate_not_owned", "candidate or backup is not transaction-owned"),
        ("candidate_outside_final", "candidate is outside its final directory"),
    ),
)
def test_journal_parser_rejects_malformed_candidate_and_backup_state(
    valid_journal_payload,
    case: str,
    message: str,
) -> None:
    transaction, _journal, valid, final, stage = valid_journal_payload
    payload = deepcopy(valid)
    entry = payload["finals"][0]
    if case == "candidate_not_object":
        entry["candidate"] = []
    elif case == "backup_mismatch":
        entry["backup"]["sha256"] = "0" * 64
    elif case == "backup_for_new_final":
        entry["existed"] = False
    elif case == "candidate_not_owned":
        payload["owned_paths"].remove(str(stage.resolve()))
    else:
        foreign = final.parent / "foreign" / "candidate.docx"
        entry["candidate"]["path"] = str(foreign)
        payload["owned_paths"].append(str(foreign))

    _assert_journal_invalid(valid_journal_payload, payload, message)
    assert transaction.final_paths == (final.resolve(),)


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("published_disagrees", "progress disagrees with replaced-final set"),
        ("replacing_without_active", "active replace state is invalid"),
        ("active_without_replacing", "active replace state is invalid"),
        ("commit_without_all_finals", "reached commit without every final"),
        ("progress_not_scalar", "baseline state is invalid"),
    ),
)
def test_journal_parser_rejects_inconsistent_publish_progress(
    valid_journal_payload,
    case: str,
    message: str,
) -> None:
    _transaction, _journal, valid, final, _stage = valid_journal_payload
    payload = deepcopy(valid)
    entry = payload["finals"][0]
    if case == "progress_not_scalar":
        entry["progress"] = []
    elif case == "published_disagrees":
        payload["published_final_paths"] = [str(final.resolve())]
    elif case == "replacing_without_active":
        entry["progress"] = "replacing"
    elif case == "active_without_replacing":
        payload["active_replace_final_path"] = str(final.resolve())
    else:
        payload["status"] = "commit_ready"

    _assert_journal_invalid(valid_journal_payload, payload, message)


@pytest.mark.parametrize(
    ("status", "progress", "published", "active"),
    (
        ("publishing", "replacing", False, True),
        ("publishing", "published", True, False),
        ("commit_ready", "published", True, False),
        ("completed", "published", True, False),
    ),
)
def test_journal_parser_accepts_consistent_active_and_published_states(
    valid_journal_payload,
    status: str,
    progress: str,
    published: bool,
    active: bool,
) -> None:
    transaction, journal, valid, final, _stage = valid_journal_payload
    payload = deepcopy(valid)
    payload["status"] = status
    payload["finals"][0]["progress"] = progress
    payload["published_final_paths"] = (
        [str(final.resolve())] if published else []
    )
    payload["active_replace_final_path"] = (
        str(final.resolve()) if active else None
    )
    journal.write_text(json.dumps(payload), encoding="utf-8")

    record = transaction._load_journal_record(
        journal,
        expected_final_set_id=transaction.final_set_id,
        expected_final_paths=transaction.final_paths,
    )

    assert record.status == status
    assert record.finals[0].progress == progress


def test_journal_parser_validates_final_evidence_before_progress_state(
    valid_journal_payload,
) -> None:
    _transaction, _journal, valid, final, _stage = valid_journal_payload
    payload = deepcopy(valid)
    payload["finals"][0]["candidate"] = []
    payload["published_final_paths"] = [str(final.resolve())]

    _assert_journal_invalid(
        valid_journal_payload,
        payload,
        "candidate is invalid",
    )


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("final_as_owned", "claims a final as an owned temporary"),
        ("unowned_cleanup", "contains an unowned cleanup path"),
    ),
)
def test_journal_parser_rejects_unowned_cleanup_paths(
    valid_journal_payload,
    case: str,
    message: str,
) -> None:
    _transaction, _journal, valid, final, _stage = valid_journal_payload
    payload = deepcopy(valid)
    payload["owned_paths"].append(
        str(final.resolve())
        if case == "final_as_owned"
        else str(final.parent / "foreign-cleanup.tmp")
    )

    _assert_journal_invalid(valid_journal_payload, payload, message)


def test_journal_loader_remains_a_bounded_staged_parser() -> None:
    path = Path(transaction_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    transaction_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "OwnedAssemblyTransaction"
    )
    loader = next(
        node
        for node in transaction_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_load_journal_record"
    )
    helpers = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and (
            node.name.startswith("_journal_")
            or node.name in {"_read_journal_payload", "_validate_journal_progress"}
        )
    }

    assert loader.end_lineno - loader.lineno + 1 <= 100
    assert {
        "_read_journal_payload",
        "_journal_header",
        "_journal_final_identity",
        "_journal_work_dir",
        "_journal_finals",
        "_validate_journal_progress",
        "_journal_owned_paths",
    } <= set(helpers)
    assert all(
        helper.end_lineno - helper.lineno + 1 <= 100
        for helper in helpers.values()
    )


_CRASH_AFTER_FIRST_REPLACE = textwrap.dedent(
    """
    import json
    import os
    from pathlib import Path

    from src.shared.io.artifact_transaction import (
        OwnedAssemblyTransaction,
        stable_file_evidence,
    )

    finals = tuple(
        Path(item)
        for item in json.loads(os.environ["LARK_TRANSACTION_FINALS"])
    )
    work_root = Path(os.environ["LARK_TRANSACTION_WORK_ROOT"])

    def crash_replace(source, target):
        os.replace(source, target)
        if Path(target).resolve() == finals[0].resolve():
            os._exit(73)

    transaction = OwnedAssemblyTransaction(
        execution_id="crash-publisher",
        final_paths=finals,
        work_root=work_root,
        atomic_replace=crash_replace,
    )
    candidates = {}
    for index, final in enumerate(finals):
        stage = transaction.allocate_stage(f"variant-{index}", final)
        stage.write_bytes(f"new-{index}".encode("ascii"))
        candidates[final] = stable_file_evidence(stage)
    transaction.publish(candidates)
    """
)


_TRY_TRANSACTION_LOCK = textwrap.dedent(
    """
    import json
    import os
    from pathlib import Path
    import sys

    from src.shared.io.artifact_transaction import (
        OwnedAssemblyTransaction,
        TransactionViolation,
    )

    finals = tuple(
        Path(item)
        for item in json.loads(os.environ["LARK_TRANSACTION_FINALS"])
    )
    try:
        transaction = OwnedAssemblyTransaction(
            execution_id="lock-contender",
            final_paths=tuple(reversed(finals)),
            work_root=Path(os.environ["LARK_TRANSACTION_WORK_ROOT"]),
            lock_timeout_seconds=0.25,
            lock_poll_seconds=0.02,
        )
    except TransactionViolation as exc:
        print(json.dumps(exc.to_dict(), sort_keys=True))
        sys.exit(41 if exc.code == "LOCK_TIMEOUT" else 42)
    transaction.cleanup_owned()
    print("acquired")
    """
)


_CRASH_AFTER_DURABLE_COMMIT = textwrap.dedent(
    """
    import json
    import os
    from pathlib import Path

    from src.shared.io.artifact_transaction import (
        OwnedAssemblyTransaction,
        stable_file_evidence,
    )

    class CrashAfterCommit(OwnedAssemblyTransaction):
        def _remove_current_journal_artifacts(self):
            os._exit(74)

    finals = tuple(
        Path(item)
        for item in json.loads(os.environ["LARK_TRANSACTION_FINALS"])
    )
    transaction = CrashAfterCommit(
        execution_id="committed-publisher",
        final_paths=finals,
        work_root=Path(os.environ["LARK_TRANSACTION_WORK_ROOT"]),
    )
    candidates = {}
    for index, final in enumerate(finals):
        stage = transaction.allocate_stage(f"variant-{index}", final)
        stage.write_bytes(f"committed-{index}".encode("ascii"))
        candidates[final] = stable_file_evidence(stage)
    transaction.publish(candidates)
    transaction.release_backups()
    """
)


def test_long_owned_stage_accepts_only_short_source_bound_layout_shadow(
    tmp_path: Path,
) -> None:
    final = tmp_path / (("delivery-name-" * 7) + ".docx")
    transaction = OwnedAssemblyTransaction(
        execution_id="execution-long-path",
        final_paths=(final,),
        work_root=tmp_path,
    )
    foreign: list[Path] = []
    try:
        stage = transaction.allocate_stage("variant-main", final)
        _save_docx(stage)
        shadow = build_controlled_layout_shadow_path(stage, nonce="a" * 32)
        legacy = stage.parent / f".{stage.stem}.lark-layout-{'a' * 32}.docx"

        assert len(str(legacy)) > 260
        assert len(shadow.name) <= 72
        assert len(str(shadow)) < len(str(legacy))
        copy2(stage, shadow)
        assert transaction.accept_layout_shadow(stage, shadow) == shadow.resolve()

        source_id = layout_shadow_source_id(stage)
        wrong_id = ("0" if source_id[0] != "0" else "1") + source_id[1:]
        wrong_source_shadow = stage.parent / (
            f"{LAYOUT_SHADOW_PREFIX}{wrong_id}-{'b' * 32}.docx"
        )
        copy2(stage, wrong_source_shadow)
        foreign.append(wrong_source_shadow)
        with pytest.raises(TransactionViolation, match="ownership contract"):
            transaction.accept_layout_shadow(stage, wrong_source_shadow)

        copy2(stage, legacy)
        foreign.append(legacy)
        with pytest.raises(TransactionViolation, match="ownership contract"):
            transaction.accept_layout_shadow(stage, legacy)

        assert wrong_source_shadow.is_file()
        assert legacy.is_file()
    finally:
        transaction.cleanup_owned()
        for path in foreign:
            path.unlink(missing_ok=True)


def test_layout_shadow_bound_to_one_owned_stage_cannot_cross_variants(
    tmp_path: Path,
) -> None:
    first_final = tmp_path / "first.docx"
    second_final = tmp_path / "second.docx"
    transaction = OwnedAssemblyTransaction(
        execution_id="execution-cross-variant",
        final_paths=(first_final, second_final),
        work_root=tmp_path,
    )
    shadow: Path | None = None
    try:
        first_stage = transaction.allocate_stage("first", first_final)
        second_stage = transaction.allocate_stage("second", second_final)
        _save_docx(first_stage, "first")
        _save_docx(second_stage, "second")
        shadow = build_controlled_layout_shadow_path(first_stage, nonce="c" * 32)
        copy2(first_stage, shadow)

        with pytest.raises(TransactionViolation, match="ownership contract"):
            transaction.accept_layout_shadow(second_stage, shadow)
        assert shadow.is_file()
        assert transaction.accept_layout_shadow(first_stage, shadow) == shadow.resolve()
    finally:
        transaction.cleanup_owned()
        if shadow is not None:
            shadow.unlink(missing_ok=True)


def test_same_final_set_is_exclusively_locked_across_processes(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "a-output"
    second_dir = tmp_path / "b-output"
    first_dir.mkdir()
    second_dir.mkdir()
    finals = (first_dir / "first.docx", second_dir / "second.docx")
    transaction = OwnedAssemblyTransaction(
        execution_id="lock-owner",
        final_paths=finals,
        work_root=tmp_path / "owner-work",
    )
    environment = _subprocess_environment(finals, tmp_path / "contender-work")
    try:
        blocked = subprocess.run(
            [sys.executable, "-c", _TRY_TRANSACTION_LOCK],
            cwd=Path.cwd(),
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert blocked.returncode == 41, blocked.stderr
        diagnostic = json.loads(blocked.stdout.strip().splitlines()[-1])
        assert diagnostic["code"] == "LOCK_TIMEOUT"
        assert Path(diagnostic["details"]["lock_path"]).is_file()
    finally:
        transaction.cleanup_owned()

    acquired = subprocess.run(
        [sys.executable, "-c", _TRY_TRANSACTION_LOCK],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert acquired.returncode == 0, acquired.stderr
    assert acquired.stdout.strip().endswith("acquired")


def test_next_transaction_recovers_process_crash_after_first_final_replace(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "a-output"
    second_dir = tmp_path / "b-output"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "first.docx"
    second = second_dir / "second.docx"
    first.write_bytes(b"old-first")
    second.write_bytes(b"old-second")
    finals = (first, second)
    old_evidence = tuple(stable_file_evidence(path) for path in finals)
    environment = _subprocess_environment(finals, tmp_path / "crash-work")

    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_AFTER_FIRST_REPLACE],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert crashed.returncode == 73, crashed.stderr
    assert first.read_bytes() == b"new-0"
    assert second.read_bytes() == b"old-second"

    recovered = OwnedAssemblyTransaction(
        execution_id="recovery-owner",
        final_paths=tuple(reversed(finals)),
        work_root=tmp_path / "recovery-work",
    )
    try:
        assert tuple(
            stable_file_evidence(path).sha256 for path in finals
        ) == tuple(item.sha256 for item in old_evidence)
        assert not recovered.journal_path.exists()
        assert not list(first_dir.glob("*.stage.docx"))
        assert not list(second_dir.glob("*.stage.docx"))
    finally:
        recovered.cleanup_owned()


def test_completed_journal_keeps_new_finals_and_finishes_cleanup(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    first.write_bytes(b"old-first")
    second.write_bytes(b"old-second")
    finals = (first, second)

    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_AFTER_DURABLE_COMMIT],
        cwd=Path.cwd(),
        env=_subprocess_environment(finals, tmp_path / "commit-work"),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert crashed.returncode == 74, crashed.stderr
    assert first.read_bytes() == b"committed-0"
    assert second.read_bytes() == b"committed-1"

    cleanup = OwnedAssemblyTransaction(
        execution_id="committed-cleanup",
        final_paths=finals,
        work_root=tmp_path / "cleanup-work",
    )
    try:
        assert first.read_bytes() == b"committed-0"
        assert second.read_bytes() == b"committed-1"
        assert not cleanup.journal_path.exists()
        assert not _claim_files(tmp_path)
    finally:
        cleanup.cleanup_owned()


def test_crash_recovery_removes_final_created_without_a_baseline(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    finals = (first, second)

    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_AFTER_FIRST_REPLACE],
        cwd=Path.cwd(),
        env=_subprocess_environment(finals, tmp_path / "crash-work"),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert crashed.returncode == 73, crashed.stderr
    assert first.read_bytes() == b"new-0"
    assert not second.exists()

    recovery = OwnedAssemblyTransaction(
        execution_id="new-final-recovery",
        final_paths=finals,
        work_root=tmp_path / "recovery-work",
    )
    try:
        assert not first.exists()
        assert not second.exists()
        assert not _claim_files(tmp_path)
    finally:
        recovery.cleanup_owned()


def test_subset_final_set_discovers_and_recovers_larger_crashed_publish(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    first.write_bytes(b"old-first")
    second.write_bytes(b"old-second")
    crashed_finals = (first, second)

    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_AFTER_FIRST_REPLACE],
        cwd=Path.cwd(),
        env=_subprocess_environment(crashed_finals, tmp_path / "crash-work"),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert crashed.returncode == 73, crashed.stderr
    assert first.read_bytes() == b"new-0"

    subset = OwnedAssemblyTransaction(
        execution_id="subset-recovery",
        final_paths=(first,),
        work_root=tmp_path / "subset-work",
    )
    try:
        assert first.read_bytes() == b"old-first"
        assert second.read_bytes() == b"old-second"
        assert not _claim_files(tmp_path)
    finally:
        subset.cleanup_owned()


def test_partial_overlap_final_set_recovers_old_set_before_new_baseline(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    third = tmp_path / "third.docx"
    first.write_bytes(b"old-first")
    second.write_bytes(b"old-second")
    third.write_bytes(b"old-third")
    crashed_finals = (first, second)

    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_AFTER_FIRST_REPLACE],
        cwd=Path.cwd(),
        env=_subprocess_environment(crashed_finals, tmp_path / "crash-work"),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert crashed.returncode == 73, crashed.stderr

    partial_overlap = OwnedAssemblyTransaction(
        execution_id="partial-overlap-recovery",
        final_paths=(first, third),
        work_root=tmp_path / "partial-work",
    )
    try:
        assert first.read_bytes() == b"old-first"
        assert second.read_bytes() == b"old-second"
        assert third.read_bytes() == b"old-third"
        assert not _claim_files(tmp_path)
    finally:
        partial_overlap.cleanup_owned()


def test_crash_recovery_blocks_external_final_rewrite(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    first.write_bytes(b"old-first")
    second.write_bytes(b"old-second")
    finals = (first, second)
    environment = _subprocess_environment(finals, tmp_path / "crash-work")

    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_AFTER_FIRST_REPLACE],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert crashed.returncode == 73, crashed.stderr
    first.write_bytes(b"external-writer")

    with pytest.raises(TransactionViolation) as captured:
        OwnedAssemblyTransaction(
            execution_id="conflicted-recovery",
            final_paths=finals,
            work_root=tmp_path / "conflicted-work",
        )
    assert captured.value.code == "RECOVERY_CONFLICT"
    assert first.read_bytes() == b"external-writer"
    assert second.read_bytes() == b"old-second"

    # Put back the exact interrupted candidate so a subsequent holder can
    # complete the deterministic recovery and leave no crash artifacts.
    first.write_bytes(b"new-0")
    cleanup = OwnedAssemblyTransaction(
        execution_id="conflict-cleanup",
        final_paths=finals,
        work_root=tmp_path / "cleanup-work",
    )
    try:
        assert first.read_bytes() == b"old-first"
        assert second.read_bytes() == b"old-second"
    finally:
        cleanup.cleanup_owned()
