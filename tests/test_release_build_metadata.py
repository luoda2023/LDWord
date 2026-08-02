import json
from pathlib import Path

import pytest

from scripts import build_release as release_builder
from scripts.check_public_release import (
    validate_binary_release_manifest,
    validate_binary_sbom,
)
from scripts.generate_windows_version_info import render_windows_version_info
from src.app_meta import APP_DISPLAY_NAME, APP_PACKAGE_NAME, APP_SEMVER

ROOT = Path(__file__).resolve().parent.parent


def test_windows_version_resource_comes_from_app_metadata():
    rendered = render_windows_version_info()

    assert "filevers=(1, 0, 0, 0)" in rendered
    assert "prodvers=(1, 0, 0, 0)" in rendered
    assert f"StringStruct('ProductName', '{APP_DISPLAY_NAME}')" in rendered
    assert f"StringStruct('ProductVersion', '{APP_SEMVER}')" in rendered
    assert f"StringStruct('OriginalFilename', '{APP_PACKAGE_NAME}.exe')" in rendered


def test_unsigned_qa_is_explicit_and_official_signing_fails_closed(monkeypatch):
    monkeypatch.delenv("ALAVETTE_SIGN_CERT_SHA1", raising=False)
    monkeypatch.setattr(release_builder.shutil, "which", lambda _name: None)

    assert release_builder._signing_configuration(unsigned_qa=True) == {}
    with pytest.raises(
        release_builder.ReleaseBuildError,
        match="ALAVETTE_SIGN_CERT_SHA1 is required",
    ):
        release_builder._signing_configuration(unsigned_qa=False)


def test_fast_packaging_is_rejected_for_official_release(monkeypatch):
    monkeypatch.setattr(
        release_builder,
        "_require_release_python",
        lambda: pytest.fail("release environment must not be inspected"),
    )

    with pytest.raises(
        release_builder.ReleaseBuildError,
        match="only allowed with --unsigned-qa",
    ):
        release_builder.build_release(skip_full_regression=True)


def test_skipped_full_regression_evidence_is_explicit(tmp_path):
    log = tmp_path / "evidence" / "03-full-regression.log"

    release_builder._write_skipped_full_regression_log(log)

    assert log.read_text(encoding="utf-8").splitlines() == [
        "status=skipped",
        "scope=full_pytest_suite",
        "reason=explicit_unsigned_qa_fast_packaging",
        "requested_by=user",
        "release_ready=false",
        (
            "note=Engineering gate, scene matrix, and targeted regressions passed; "
            "this candidate is not a formal release."
        ),
    ]


def test_release_gate_caches_are_removed_without_touching_source(tmp_path):
    source_root = tmp_path / "source"
    keep = source_root / "src" / "module.py"
    keep.parent.mkdir(parents=True)
    keep.write_text("VALUE = 1\n", encoding="utf-8")
    for cache_file in (
        source_root / ".pytest_cache" / "v" / "cache" / "nodeids",
        source_root / ".ruff_cache" / "content",
        source_root / "src" / "__pycache__" / "module.pyc",
    ):
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"cache")

    release_builder._remove_release_gate_caches(source_root)

    assert keep.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert not (source_root / ".pytest_cache").exists()
    assert not (source_root / ".ruff_cache").exists()
    assert not (source_root / "src" / "__pycache__").exists()


def test_official_signing_rejects_malformed_certificate_thumbprint(monkeypatch):
    monkeypatch.setenv("ALAVETTE_SIGN_CERT_SHA1", "not-a-thumbprint")
    monkeypatch.setattr(
        release_builder.shutil,
        "which",
        lambda _name: r"C:\\Windows\\signtool.exe",
    )

    with pytest.raises(release_builder.ReleaseBuildError, match="40-character"):
        release_builder._signing_configuration(unsigned_qa=False)


def test_sbom_and_release_manifest_are_machine_verifiable(tmp_path, monkeypatch):
    package_root = tmp_path / "payload"
    package_root.mkdir()
    executable = package_root / f"{APP_PACKAGE_NAME}.exe"
    executable.write_bytes(b"MZ-test")
    lock_path = tmp_path / "requirements-release.lock"
    lock_path.write_text("example-package==2.3.4\n", encoding="utf-8")
    sbom_path = package_root / "SBOM.cdx.json"

    release_builder._write_sbom(sbom_path, lock_path)
    monkeypatch.setattr(release_builder, "version", lambda _name: "6.21.0")
    release_builder._write_release_manifest(
        package_root / "RELEASE_MANIFEST.json",
        package_root,
        commit="a" * 40,
        signed=True,
    )

    assert validate_binary_sbom(sbom_path) == []
    assert validate_binary_release_manifest(package_root) == []
    payload = json.loads(sbom_path.read_text(encoding="utf-8"))
    assert payload["components"] == [
        {
            "name": "example-package",
            "purl": "pkg:pypi/example-package@2.3.4",
            "type": "library",
            "version": "2.3.4",
        }
    ]

    executable.write_bytes(b"tampered")
    assert validate_binary_release_manifest(package_root) == [
        "Binary release manifest does not match payload files"
    ]


def test_binary_sbom_describes_runtime_payload_not_test_or_build_tools(tmp_path):
    sbom_path = tmp_path / "SBOM.cdx.json"
    license_manifest = ROOT / "licenses" / "manifest.json"

    release_builder._write_sbom(
        sbom_path,
        ROOT / "requirements-release.lock",
        license_manifest_path=license_manifest,
    )

    assert (
        validate_binary_sbom(
            sbom_path,
            license_manifest_path=license_manifest,
        )
        == []
    )
    payload = json.loads(sbom_path.read_text(encoding="utf-8"))
    names = {component["name"].casefold() for component in payload["components"]}
    assert {"pytest", "ruff", "pyinstaller"}.isdisjoint(names)
    assert {"python-docx", "pyside6_essentials", "shiboken6"}.issubset(names)


def test_release_cli_reports_staging_failures_without_traceback(monkeypatch, capsys):
    def fail_build(*, unsigned_qa, skip_full_regression):
        assert unsigned_qa is True
        assert skip_full_regression is True
        raise RuntimeError("worktree is dirty")

    monkeypatch.setattr(release_builder, "build_release", fail_build)

    assert (
        release_builder.main(["--unsigned-qa", "--skip-full-regression"]) == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "[ERROR] worktree is dirty\n"
