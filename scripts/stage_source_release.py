"""Export one clean Git revision into an isolated source-release tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
SOURCE_MANIFEST_NAME = "RELEASE_SOURCE_MANIFEST.json"


def stage_source_revision(
    repository_root: Path,
    destination: Path,
    *,
    revision: str = "HEAD",
) -> dict[str, object]:
    """Export a clean tracked revision and write its immutable file manifest."""

    root = repository_root.resolve()
    target = destination.resolve()
    _require_clean_worktree(root)
    git_directory = root / ".git"
    if target == root or target == git_directory or git_directory in target.parents:
        raise ValueError("Release staging destination must not replace the repository")
    if target.exists():
        raise FileExistsError(f"Release staging destination already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    commit = _git(root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    with tempfile.NamedTemporaryFile(
        prefix="alavette-source-",
        suffix=".zip",
        dir=target.parent,
        delete=False,
    ) as handle:
        archive_path = Path(handle.name)
    try:
        subprocess.run(
            (
                "git",
                "archive",
                "--format=zip",
                f"--output={archive_path}",
                commit,
            ),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        with tempfile.TemporaryDirectory(
            prefix=".alavette-source-tree-",
            dir=target.parent,
        ) as temporary_directory:
            staged_tree = Path(temporary_directory) / "tree"
            staged_tree.mkdir()
            with zipfile.ZipFile(archive_path) as archive:
                _extract_archive_safely(archive, staged_tree)
            files = _file_manifest(staged_tree)
            payload: dict[str, object] = {
                "schema_version": 1,
                "kind": "tracked_source_release",
                "commit": commit,
                "revision": revision,
                "file_count": len(files),
                "files": files,
            }
            (staged_tree / SOURCE_MANIFEST_NAME).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            staged_tree.replace(target)
        return payload
    finally:
        archive_path.unlink(missing_ok=True)


def verify_source_manifest(root: Path) -> list[str]:
    """Return manifest-integrity errors for an exported source tree."""

    manifest_path = root / SOURCE_MANIFEST_NAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"Invalid source release manifest: {exc}"]
    expected = payload.get("files")
    if payload.get("schema_version") != 1 or not isinstance(expected, list):
        return ["Invalid source release manifest schema"]
    actual = _file_manifest(root, exclude=(SOURCE_MANIFEST_NAME,))
    if expected != actual:
        return ["Source release manifest does not match staged files"]
    if payload.get("file_count") != len(actual):
        return ["Source release manifest file_count is invalid"]
    return []


def _require_clean_worktree(root: Path) -> None:
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise RuntimeError(
            "Release source export requires a clean Git worktree; "
            f"found {len(status.splitlines())} changed paths"
        )


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def _extract_archive_safely(archive: zipfile.ZipFile, target: Path) -> None:
    for info in archive.infolist():
        relative = PurePosixPath(info.filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe Git archive member: {info.filename}")
        resolved = (target / Path(*relative.parts)).resolve()
        if target not in resolved.parents and resolved != target:
            raise ValueError(f"Git archive member escapes staging: {info.filename}")
    archive.extractall(target)


def _file_manifest(
    root: Path,
    *,
    exclude: tuple[str, ...] = (),
) -> list[dict[str, object]]:
    excluded = set(exclude)
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.relative_to(root).as_posix() not in excluded
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export a clean tracked Git revision for source-release checks."
    )
    parser.add_argument("destination", type=Path)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    payload = stage_source_revision(
        args.repository_root,
        args.destination,
        revision=args.revision,
    )
    print(
        f"Staged {payload['file_count']} tracked files from "
        f"{payload['commit']} to {args.destination.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
