import subprocess
from pathlib import Path

import pytest

from scripts.check_public_release import (
    iter_repo_files,
    scan_binary_release_tree,
    scan_release_tree,
)
from scripts.stage_source_release import (
    SOURCE_MANIFEST_NAME,
    stage_source_revision,
    verify_source_manifest,
)
from src.app_meta import APP_PACKAGE_NAME


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _clean_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--initial-branch=main")
    (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(
        repository,
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    return repository


def test_source_release_stage_contains_only_committed_files_and_manifest(tmp_path):
    repository = _clean_repository(tmp_path)
    destination = tmp_path / "release-source"

    payload = stage_source_revision(repository, destination)

    assert (destination / "tracked.txt").read_text(encoding="utf-8") == "tracked\n"
    assert (destination / SOURCE_MANIFEST_NAME).is_file()
    assert payload["file_count"] == 1
    assert verify_source_manifest(destination) == []

    (destination / "tracked.txt").write_text("tampered\n", encoding="utf-8")
    assert verify_source_manifest(destination) == [
        "Source release manifest does not match staged files"
    ]


def test_source_release_stage_rejects_dirty_or_untracked_worktree(tmp_path):
    repository = _clean_repository(tmp_path)
    (repository / "untracked.txt").write_text("not releasable\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="requires a clean Git worktree"):
        stage_source_revision(repository, tmp_path / "release-source")


def test_release_scan_prunes_local_environment_contents(tmp_path):
    hidden = tmp_path / ".venv" / "Lib" / "hidden.spec"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("local dependency", encoding="utf-8")
    visible = tmp_path / "src" / "visible.py"
    visible.parent.mkdir()
    visible.write_text("print('visible')\n", encoding="utf-8")

    scanned = {
        path.relative_to(tmp_path).as_posix() for path in iter_repo_files(tmp_path)
    }

    assert "src/visible.py" in scanned
    assert ".venv/Lib/hidden.spec" not in scanned


def test_source_release_scan_rejects_local_profile_paths_but_allows_test_fixtures(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("scripts.check_public_release.REQUIRED_DOCS", [])
    documentation = tmp_path / "docs" / "audit.md"
    documentation.parent.mkdir()
    documentation.write_text(
        "local root: " + "C:" + r"\Users\real-user\Desktop\private",
        encoding="utf-8",
    )
    fixture = tmp_path / "tests" / "fixture.py"
    fixture.parent.mkdir()
    fixture.write_text(
        'path = r"C:\\Users\\Alice\\synthetic.docx"\n',
        encoding="utf-8",
    )

    errors, _warnings = scan_release_tree(tmp_path)

    assert errors == ["Local user profile path remains in: docs/audit.md"]


def test_binary_release_scan_requires_identity_files_and_rejects_raw_source(
    tmp_path,
):
    (tmp_path / f"{APP_PACKAGE_NAME}.exe").write_bytes(b"MZ")
    raw_source = tmp_path / "accidental.py"
    raw_source.write_text("secret = 'not-for-binary'\n", encoding="utf-8")

    errors, warnings = scan_binary_release_tree(tmp_path)

    assert "Missing required binary release file: LICENSE" in errors
    assert "Raw Python source present in binary package: accidental.py" in warnings
