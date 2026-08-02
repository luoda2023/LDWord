"""Build one traceable Windows release from an isolated clean Git revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_public_release import scan_binary_release_tree, scan_release_tree
from scripts.generate_windows_version_info import write_windows_version_info
from scripts.stage_source_release import stage_source_revision
from scripts.verify_release_environment import release_environment_issues
from src.app_meta import (
    APP_DISPLAY_NAME,
    APP_FILE_VERSION,
    APP_PACKAGE_NAME,
    APP_SEMVER,
)

DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"
WINDOWS_ARCH = "x64"
INSTALLER_SCRIPT = Path("installer/Alavette-Form.iss")
_LOCK_LINE = re.compile(r"^([A-Za-z0-9_.-]+)==([^;\s]+)")


class ReleaseBuildError(RuntimeError):
    pass


def build_release(
    *,
    unsigned_qa: bool = False,
    skip_full_regression: bool = False,
) -> Path:
    """Run all release gates and atomically publish a signed or QA-only ZIP."""

    if skip_full_regression and not unsigned_qa:
        raise ReleaseBuildError(
            "--skip-full-regression is only allowed with --unsigned-qa"
        )
    _require_release_python()
    dependency_issues = release_environment_issues(ROOT / "requirements-release.lock")
    if dependency_issues:
        raise ReleaseBuildError(
            "Release environment does not match requirements-release.lock: "
            + "; ".join(dependency_issues)
        )
    signer = _signing_configuration(unsigned_qa=unsigned_qa)
    installer_compiler = _find_inno_setup_compiler()
    commit = _git("rev-parse", "HEAD")
    short_commit = commit[:12]
    build_root = ROOT / "build" / "release" / short_commit
    source_root = build_root / "source"
    evidence_root = build_root / "evidence"
    package_dist_root = build_root / "package-dist"
    pyinstaller_work_root = build_root / "pyinstaller"
    installer_dist_root = build_root / "installer-dist"
    if build_root.exists():
        raise ReleaseBuildError(
            f"Release build directory already exists; preserve or remove it explicitly: {build_root}"
        )

    stage_source_revision(ROOT, source_root, revision=commit)
    evidence_root.mkdir(parents=True)
    for relative in (
        "RELEASE_SOURCE_MANIFEST.json",
        "requirements-release.lock",
        "Alavette-Form_V1.0.spec",
        INSTALLER_SCRIPT.as_posix(),
    ):
        destination = evidence_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative, destination)
    environment = _release_environment(source_root)
    python = Path(sys.executable).resolve()

    _run_logged(
        (str(python), "scripts/engineering_gate.py"),
        cwd=source_root,
        log=evidence_root / "01-engineering-gate.log",
        env=environment,
    )
    _run_logged(
        (str(python), "scripts/verify_scene_matrix_release_gate.py"),
        cwd=source_root,
        log=evidence_root / "02-scene-release-gate.log",
        env=environment,
    )
    full_regression_log = evidence_root / "03-full-regression.log"
    if skip_full_regression:
        _write_skipped_full_regression_log(full_regression_log)
    else:
        _run_logged(
            (str(python), "-m", "pytest", "-q", "tests"),
            cwd=source_root,
            log=full_regression_log,
            env=environment,
        )
    _run_logged(
        (str(python), "-m", "pip", "check"),
        cwd=source_root,
        log=evidence_root / "04-pip-check.log",
        env=environment,
    )
    _remove_release_gate_caches(source_root)

    errors, warnings = scan_release_tree(source_root, kind="source")
    _write_scan_log(
        evidence_root / "05-source-release-scan.log",
        errors,
        warnings,
    )
    if errors or warnings:
        raise ReleaseBuildError("Isolated source release scan failed")

    _run_logged(
        (str(python), "scripts/build_user_documentation.py"),
        cwd=source_root,
        log=evidence_root / "06-user-documentation.log",
        env=environment,
    )
    _run_logged(
        (
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/windows/export_user_documentation_pdf.ps1",
            "-RepositoryRoot",
            str(source_root),
        ),
        cwd=source_root,
        log=evidence_root / "07-user-documentation-pdf.log",
        env=environment,
    )
    _run_logged(
        (str(python), "scripts/build_license_bundle.py"),
        cwd=source_root,
        log=evidence_root / "08-license-bundle.log",
        env=environment,
    )
    _run_logged(
        (str(python), "scripts/stage_release_config_library.py"),
        cwd=source_root,
        log=evidence_root / "09-config-staging.log",
        env=environment,
    )
    write_windows_version_info(source_root / "build" / "windows_version_info.txt")

    _run_logged(
        (
            str(python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(package_dist_root),
            "--workpath",
            str(pyinstaller_work_root),
            str(source_root / "Alavette-Form_V1.0.spec"),
        ),
        cwd=source_root,
        log=evidence_root / "10-pyinstaller.log",
        env=environment,
    )
    package_root = package_dist_root / APP_PACKAGE_NAME
    executable = package_root / f"{APP_PACKAGE_NAME}.exe"
    if not executable.is_file():
        raise ReleaseBuildError(f"PyInstaller executable is missing: {executable}")

    _run_logged(
        (
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/windows/stage_user_documentation.ps1",
            "-RepositoryRoot",
            str(source_root),
            "-DestinationRoot",
            str(package_root),
        ),
        cwd=source_root,
        log=evidence_root / "11-documentation-staging.log",
        env=environment,
    )
    _trim_qt_addons(package_root)
    _sign_and_verify(executable, signer=signer)
    _verify_windows_version(executable)
    _write_sbom(
        package_root / "SBOM.cdx.json",
        source_root / "requirements-release.lock",
        license_manifest_path=package_root / "licenses" / "manifest.json",
    )
    _write_release_manifest(
        package_root / "RELEASE_MANIFEST.json",
        package_root,
        commit=commit,
        signed=not unsigned_qa,
    )

    errors, warnings = scan_binary_release_tree(package_root)
    _write_scan_log(
        evidence_root / "12-binary-release-scan.log",
        errors,
        warnings,
    )
    if errors or warnings:
        raise ReleaseBuildError("Final binary release scan failed")

    qualifier = "-UNSIGNED-QA" if unsigned_qa else ""
    portable_base_name = (
        f"Alavette-Form-Portable-{APP_SEMVER}-{WINDOWS_ARCH}{qualifier}"
    )
    setup_base_name = (
        f"Alavette-Form-Setup-{APP_SEMVER}-{WINDOWS_ARCH}{qualifier}"
    )
    setup_path = _build_installer(
        compiler=installer_compiler,
        script=source_root / INSTALLER_SCRIPT,
        source_dir=package_root,
        output_dir=installer_dist_root,
        output_base_name=setup_base_name,
        signer=signer,
        log=evidence_root / "13-inno-setup.log",
        env=environment,
    )
    _verify_signature(setup_path, signer=signer)
    installer_qa_root = build_root / "installer-qa"
    _run_logged(
        (
            str(python),
            "scripts/verify_windows_installer.py",
            str(setup_path),
            str(installer_qa_root),
        ),
        cwd=source_root,
        log=evidence_root / "14-installer-smoke.log",
        env=environment,
    )
    shutil.copy2(
        installer_qa_root / "INSTALLER_QA.json",
        evidence_root / "INSTALLER_QA.json",
    )

    publish_parent = ROOT / "artifacts" / ("release-qa" if unsigned_qa else "releases")
    publish_parent.mkdir(parents=True, exist_ok=True)
    published = publish_parent / short_commit
    if published.exists():
        raise ReleaseBuildError(
            f"Published release directory already exists: {published}"
        )
    temporary_publish = publish_parent / f".{short_commit}.{uuid.uuid4().hex}.tmp"
    temporary_publish.mkdir()
    try:
        shutil.copytree(package_root, temporary_publish / APP_PACKAGE_NAME)
        archive_name = f"{portable_base_name}.zip"
        archive_path = temporary_publish / archive_name
        _write_zip(temporary_publish / APP_PACKAGE_NAME, archive_path)
        setup_publish_path = temporary_publish / setup_path.name
        shutil.copy2(setup_path, setup_publish_path)
        for artifact in (archive_path, setup_publish_path):
            (temporary_publish / f"{artifact.name}.sha256").write_text(
                f"{_sha256(artifact)}  {artifact.name}\n",
                encoding="ascii",
            )
        shutil.copytree(evidence_root, temporary_publish / "evidence")
        temporary_publish.replace(published)
    except Exception:
        _remove_generated_tree(temporary_publish, allowed_parent=publish_parent)
        raise
    return published


def _require_release_python() -> None:
    if sys.platform != "win32":
        raise ReleaseBuildError("Windows release builds must run on Windows")
    if sys.version_info[:2] != (3, 12):
        raise ReleaseBuildError("V1.0 release builds require CPython 3.12")
    try:
        installed = version("pyinstaller")
    except PackageNotFoundError as exc:
        raise ReleaseBuildError("PyInstaller is not installed") from exc
    if installed != "6.21.0":
        raise ReleaseBuildError(
            f"PyInstaller version mismatch: expected 6.21.0, got {installed}"
        )


def _signing_configuration(*, unsigned_qa: bool) -> dict[str, str]:
    if unsigned_qa:
        return {}
    certificate = str(os.environ.get("ALAVETTE_SIGN_CERT_SHA1") or "").strip()
    sign_tool = shutil.which("signtool")
    if not certificate:
        raise ReleaseBuildError(
            "ALAVETTE_SIGN_CERT_SHA1 is required for an official release"
        )
    if not re.fullmatch(r"[0-9A-Fa-f]{40}", certificate):
        raise ReleaseBuildError(
            "ALAVETTE_SIGN_CERT_SHA1 must be a 40-character SHA-1 thumbprint"
        )
    if not sign_tool:
        raise ReleaseBuildError("signtool.exe is required for an official release")
    return {
        "certificate": certificate,
        "signtool": sign_tool,
        "timestamp_url": str(
            os.environ.get("ALAVETTE_TIMESTAMP_URL") or DEFAULT_TIMESTAMP_URL
        ).strip(),
    }


def _find_inno_setup_compiler() -> str:
    candidates = (
        shutil.which("ISCC"),
        Path(os.environ.get("ProgramFiles(x86)", ""))
        / "Inno Setup 6"
        / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "Inno Setup 6"
        / "ISCC.exe",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise ReleaseBuildError(
        "Inno Setup 6 compiler (ISCC.exe) is required for Windows release builds"
    )


def _release_environment(source_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONPATH": str(source_root),
            "QT_QPA_PLATFORM": "offscreen",
        }
    )
    return environment


def _run_logged(
    command: tuple[str, ...],
    *,
    cwd: Path,
    log: Path,
    env: dict[str, str],
) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("$ " + subprocess.list2cmdline(command) + "\n")
        handle.flush()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            handle.write(line)
        return_code = process.wait()
    if return_code:
        raise ReleaseBuildError(
            f"Release command failed ({return_code}): {subprocess.list2cmdline(command)}"
        )


def _write_scan_log(path: Path, errors: list[str], warnings: list[str]) -> None:
    lines = [
        "status=" + ("passed" if not errors and not warnings else "failed"),
        *(f"ERROR {item}" for item in errors),
        *(f"WARNING {item}" for item in warnings),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_skipped_full_regression_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "status=skipped\n"
        "scope=full_pytest_suite\n"
        "reason=explicit_unsigned_qa_fast_packaging\n"
        "requested_by=user\n"
        "release_ready=false\n"
        "note=Engineering gate, scene matrix, and targeted regressions passed; "
        "this candidate is not a formal release.\n",
        encoding="utf-8",
    )


def _remove_release_gate_caches(source_root: Path) -> None:
    cache_names = {"__pycache__", ".pytest_cache", ".ruff_cache"}
    cache_directories = sorted(
        (
            path
            for path in source_root.rglob("*")
            if path.is_dir() and path.name in cache_names
        ),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for cache_directory in cache_directories:
        _remove_generated_tree(cache_directory, allowed_parent=source_root)


def _trim_qt_addons(package_root: Path) -> None:
    for py_side_root in (
        package_root / "_internal" / "PySide6",
        package_root / "PySide6",
    ):
        if not py_side_root.is_dir():
            continue
        for file_name in (
            "Qt6WebEngineCore.dll",
            "Qt6WebEngineQuick.dll",
            "Qt6WebEngineWidgets.dll",
            "Qt6QmlMeta.dll",
            "Qt6QmlModels.dll",
            "Qt6QmlWorkerScript.dll",
            "Qt6Qml.dll",
            "Qt6Quick.dll",
            "Qt6Quick3D.dll",
            "Qt6Multimedia.dll",
            "Qt6Charts.dll",
            "Qt6Pdf.dll",
        ):
            (py_side_root / file_name).unlink(missing_ok=True)
        for directory_name in ("qml", "resources", "translations"):
            _remove_generated_tree(
                py_side_root / directory_name,
                allowed_parent=py_side_root,
            )


def _sign_and_verify(executable: Path, *, signer: dict[str, str]) -> None:
    if not signer:
        return
    subprocess.run(
        (
            signer["signtool"],
            "sign",
            "/sha1",
            signer["certificate"],
            "/fd",
            "SHA256",
            "/tr",
            signer["timestamp_url"],
            "/td",
            "SHA256",
            str(executable),
        ),
        check=True,
    )
    _verify_signature(executable, signer=signer)


def _verify_signature(executable: Path, *, signer: dict[str, str]) -> None:
    if not signer:
        return
    subprocess.run(
        (signer["signtool"], "verify", "/pa", "/all", str(executable)),
        check=True,
    )


def _build_installer(
    *,
    compiler: str,
    script: Path,
    source_dir: Path,
    output_dir: Path,
    output_base_name: str,
    signer: dict[str, str],
    log: Path,
    env: dict[str, str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        compiler,
        f"/DAppVersion={APP_SEMVER}",
        f"/DSourceDir={source_dir.resolve()}",
        f"/DOutputDir={output_dir.resolve()}",
        f"/DOutputBaseFilename={output_base_name}",
    ]
    if signer:
        sign_command = (
            f'"{signer["signtool"]}" sign '
            f'/sha1 {signer["certificate"]} /fd SHA256 '
            f'/tr "{signer["timestamp_url"]}" /td SHA256 "$f"'
        )
        command.extend((f"/Srelease={sign_command}", "/DSignedBuild=1"))
    command.append(str(script.resolve()))
    _run_logged(tuple(command), cwd=script.parent.parent, log=log, env=env)
    output = output_dir / f"{output_base_name}.exe"
    if not output.is_file():
        raise ReleaseBuildError(f"Inno Setup output is missing: {output}")
    return output


def _verify_windows_version(executable: Path) -> None:
    try:
        import win32api
    except ImportError as exc:
        raise ReleaseBuildError(
            "pywin32 is required for version-resource checks"
        ) from exc
    info = win32api.GetFileVersionInfo(str(executable), "\\")
    actual = (
        info["FileVersionMS"] >> 16,
        info["FileVersionMS"] & 0xFFFF,
        info["FileVersionLS"] >> 16,
        info["FileVersionLS"] & 0xFFFF,
    )
    if actual != tuple(APP_FILE_VERSION):
        raise ReleaseBuildError(
            f"Windows FileVersion mismatch: expected {APP_FILE_VERSION}, got {actual}"
        )


def _write_sbom(
    path: Path,
    lock_path: Path,
    *,
    license_manifest_path: Path | None = None,
) -> None:
    locked_versions: dict[str, tuple[str, str]] = {}
    for raw_line in lock_path.read_text(encoding="utf-8").splitlines():
        match = _LOCK_LINE.match(raw_line.strip())
        if not match:
            continue
        name, component_version = match.groups()
        normalized = re.sub(r"[-_.]+", "-", name).casefold()
        locked_versions[normalized] = (name, component_version)

    components: list[dict[str, object]] = []
    if license_manifest_path is not None:
        license_payload = json.loads(license_manifest_path.read_text(encoding="utf-8"))
        for license_component in license_payload.get("components", []):
            component_id = str(license_component.get("id") or "").strip()
            distributions = license_component.get("python_distributions") or []
            component_names = distributions or [license_component.get("name")]
            for raw_name in component_names:
                name = str(raw_name or "").strip()
                if not name:
                    continue
                normalized = re.sub(r"[-_.]+", "-", name).casefold()
                locked = locked_versions.get(normalized)
                component_version = (
                    locked[1]
                    if locked is not None
                    else str(license_component.get("version") or "unknown")
                )
                component: dict[str, object] = {
                    "type": "library",
                    "name": name,
                    "version": component_version,
                    "scope": "required",
                    "properties": [
                        {
                            "name": "alavette:license-component-id",
                            "value": component_id,
                        }
                    ],
                }
                if distributions:
                    component["purl"] = f"pkg:pypi/{normalized}@{component_version}"
                license_expression = str(
                    license_component.get("license_expression") or ""
                ).strip()
                if license_expression:
                    component["licenses"] = [{"license": {"name": license_expression}}]
                components.append(component)
    else:
        for normalized, (name, component_version) in locked_versions.items():
            components.append(
                {
                    "type": "library",
                    "name": name,
                    "version": component_version,
                    "purl": f"pkg:pypi/{normalized}@{component_version}",
                }
            )
    payload = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {
                "type": "application",
                "name": APP_DISPLAY_NAME,
                "version": APP_SEMVER,
            },
        },
        "components": components,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_release_manifest(
    path: Path,
    package_root: Path,
    *,
    commit: str,
    signed: bool,
) -> None:
    files = [
        {
            "path": item.relative_to(package_root).as_posix(),
            "size": item.stat().st_size,
            "sha256": _sha256(item),
        }
        for item in sorted(
            candidate for candidate in package_root.rglob("*") if candidate.is_file()
        )
        if item != path
    ]
    payload = {
        "schema_version": 1,
        "product": APP_DISPLAY_NAME,
        "version": APP_SEMVER,
        "commit": commit,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "pyinstaller": version("pyinstaller"),
        "signed": signed,
        "release_ready": signed,
        "file_count": len(files),
        "files": files,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_zip(package_root: Path, destination: Path) -> None:
    with zipfile.ZipFile(
        destination,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
            archive.write(
                path,
                (Path(APP_PACKAGE_NAME) / path.relative_to(package_root)).as_posix(),
            )


def _remove_generated_tree(path: Path, *, allowed_parent: Path) -> None:
    target = path.resolve()
    parent = allowed_parent.resolve()
    if target == parent or parent not in target.parents:
        raise ReleaseBuildError(f"Refusing to remove path outside build root: {target}")
    if target.exists():
        shutil.rmtree(target)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a gated, traceable Alavette Form Windows release."
    )
    parser.add_argument(
        "--unsigned-qa",
        action="store_true",
        help="Build a clearly labelled QA artifact without a signing certificate.",
    )
    parser.add_argument(
        "--skip-full-regression",
        action="store_true",
        help="Skip the full pytest suite; only valid with --unsigned-qa.",
    )
    args = parser.parse_args(argv)
    try:
        output = build_release(
            unsigned_qa=args.unsigned_qa,
            skip_full_regression=args.skip_full_regression,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Release artifacts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
