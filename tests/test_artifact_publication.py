import os
from pathlib import Path

import pytest

from src.shared.io.artifact_publication import (
    StagedArtifact,
    publish_staged_artifacts,
)


def test_publish_staged_artifacts_commits_mixed_file_set(tmp_path):
    stage_root = tmp_path / "render"
    stage_root.mkdir()
    preview = stage_root / "preview.md"
    document = stage_root / "document.docx"
    preview.write_text("preview", encoding="utf-8")
    document.write_bytes(b"document")
    final_preview = tmp_path / "final" / "preview.md"
    final_document = tmp_path / "final" / "document.docx"

    published = publish_staged_artifacts(
        (
            StagedArtifact("preview", preview, final_preview),
            StagedArtifact("document", document, final_document),
        ),
        execution_id="artifact-set-success",
    )

    assert published == {
        "preview": str(final_preview.resolve()),
        "document": str(final_document.resolve()),
    }
    assert final_preview.read_text(encoding="utf-8") == "preview"
    assert final_document.read_bytes() == b"document"
    assert not tuple(final_preview.parent.glob("*.stage.*"))
    assert not tuple(final_preview.parent.glob("*.backup"))
    state_directory = final_preview.parent / ".lark-material-transactions"
    assert state_directory.is_dir()
    if os.name == "nt":
        import ctypes

        attributes = ctypes.windll.kernel32.GetFileAttributesW(
            str(state_directory)
        )
        assert attributes != 0xFFFFFFFF
        assert attributes & 0x2


def test_publish_staged_artifacts_restores_all_finals_on_second_replace_failure(
    tmp_path,
):
    stage_root = tmp_path / "render"
    stage_root.mkdir()
    first_stage = stage_root / "first.json"
    second_stage = stage_root / "second.md"
    first_stage.write_text("new-first", encoding="utf-8")
    second_stage.write_text("new-second", encoding="utf-8")
    first_final = tmp_path / "final" / "first.json"
    second_final = tmp_path / "final" / "second.md"
    first_final.parent.mkdir()
    first_final.write_text("old-first", encoding="utf-8")
    second_final.write_text("old-second", encoding="utf-8")
    injected = False

    def fail_second_publish(source, target):
        nonlocal injected
        source_path = Path(source)
        target_path = Path(target)
        if (
            not injected
            and target_path.resolve() == second_final.resolve()
            and ".stage" in source_path.name
        ):
            injected = True
            raise PermissionError("injected second publish failure")
        return os.replace(source, target)

    with pytest.raises(PermissionError, match="second publish failure"):
        publish_staged_artifacts(
            (
                StagedArtifact("first", first_stage, first_final),
                StagedArtifact("second", second_stage, second_final),
            ),
            execution_id="artifact-set-rollback",
            atomic_replace=fail_second_publish,
        )

    assert first_final.read_text(encoding="utf-8") == "old-first"
    assert second_final.read_text(encoding="utf-8") == "old-second"
    assert not tuple(first_final.parent.glob("*.stage.*"))
    assert not tuple(first_final.parent.glob("*.backup"))


def test_publish_staged_artifacts_rejects_final_symlink_without_touching_target(
    tmp_path,
):
    stage = tmp_path / "rendered.docx"
    stage.write_bytes(b"new artifact")
    protected = tmp_path / "protected-source.docx"
    protected.write_bytes(b"protected source")
    final_link = tmp_path / "final.docx"
    try:
        final_link.symlink_to(protected)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="symbolic link or junction"):
        publish_staged_artifacts(
            (StagedArtifact("document", stage, final_link),),
            execution_id="artifact-final-symlink",
        )

    assert protected.read_bytes() == b"protected source"
    assert final_link.is_symlink()


def test_publish_staged_artifacts_rejects_symlinked_final_parent(
    tmp_path,
):
    stage = tmp_path / "rendered.docx"
    stage.write_bytes(b"new artifact")
    protected_dir = tmp_path / "protected"
    protected_dir.mkdir()
    protected = protected_dir / "document.docx"
    protected.write_bytes(b"protected source")
    linked_parent = tmp_path / "linked-output"
    try:
        linked_parent.symlink_to(protected_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="symbolic link or junction"):
        publish_staged_artifacts(
            (StagedArtifact("document", stage, linked_parent / "document.docx"),),
            execution_id="artifact-parent-symlink",
        )

    assert protected.read_bytes() == b"protected source"
    assert linked_parent.is_symlink()


def test_publish_staged_artifacts_checks_symbolic_final_before_any_replace(
    tmp_path,
    monkeypatch,
):
    stage = tmp_path / "rendered.docx"
    stage.write_bytes(b"new artifact")
    final = tmp_path / "final.docx"
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path):
        return path == final or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
    replace_calls: list[tuple[object, object]] = []

    with pytest.raises(ValueError, match="symbolic link or junction"):
        publish_staged_artifacts(
            (StagedArtifact("document", stage, final),),
            execution_id="artifact-symbolic-preflight",
            atomic_replace=lambda source, target: replace_calls.append((source, target)),
        )

    assert replace_calls == []
    assert not final.exists()
