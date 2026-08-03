"""Silent install/reinstall/uninstall smoke test for an Inno Setup artifact."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


class InstallerVerificationError(RuntimeError):
    pass


def verify_installer(setup: Path, work_root: Path) -> dict[str, object]:
    setup = setup.resolve()
    work_root = work_root.resolve()
    if not setup.is_file():
        raise InstallerVerificationError(f"Setup executable is missing: {setup}")
    if work_root.exists():
        raise InstallerVerificationError(
            f"Installer QA directory already exists: {work_root}"
        )

    install_root = work_root / "installed"
    logs = work_root / "logs"
    logs.mkdir(parents=True)
    common = (
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
        "/CURRENTUSER",
        f"/DIR={install_root}",
        "/NOICONS",
    )
    _run((str(setup), *common, f"/LOG={logs / 'install-1.log'}"))

    executable = install_root / "app" / "Alavette-Form.exe"
    if not executable.is_file():
        raise InstallerVerificationError(
            f"Installed executable is missing: {executable}"
        )
    _verify_startup(executable, work_root / "runtime-data")

    stale_probe = install_root / "app" / "installer-stale-payload.probe"
    stale_probe.write_text("must be removed by the next upgrade\n", encoding="utf-8")
    _run((str(setup), *common, f"/LOG={logs / 'install-2.log'}"))
    if stale_probe.exists():
        raise InstallerVerificationError(
            "In-place reinstall left stale application payload behind"
        )
    if not executable.is_file():
        raise InstallerVerificationError(
            "In-place reinstall removed the application executable"
        )

    uninstaller = install_root / "unins000.exe"
    if not uninstaller.is_file():
        raise InstallerVerificationError(f"Uninstaller is missing: {uninstaller}")
    _run(
        (
            str(uninstaller),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            f"/LOG={logs / 'uninstall.log'}",
        )
    )
    deadline = time.monotonic() + 15
    while executable.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    if executable.exists():
        raise InstallerVerificationError(
            "Uninstall completed but the application payload still exists"
        )

    result = {
        "schema_version": 1,
        "setup": str(setup),
        "install_root": str(install_root),
        "initial_install": "passed",
        "installed_application_startup": "passed",
        "in_place_reinstall": "passed",
        "stale_payload_cleanup": "passed",
        "uninstall": "passed",
    }
    (work_root / "INSTALLER_QA.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(install_root, ignore_errors=True)
    return result


def _run(command: tuple[str, ...]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise InstallerVerificationError(
            f"Installer command failed ({completed.returncode}): "
            + subprocess.list2cmdline(command)
        )


def _verify_startup(executable: Path, data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    ready_file = data_root / "startup-ready.txt"
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "APPDATA": str(data_root / "AppData"),
            "LOCALAPPDATA": str(data_root / "LocalAppData"),
            "ALAVETTE_STARTUP_READY_FILE": str(ready_file),
        }
    )
    Path(environment["APPDATA"]).mkdir(parents=True)
    Path(environment["LOCALAPPDATA"]).mkdir(parents=True)
    process = subprocess.Popen(
        (str(executable),),
        cwd=executable.parent,
        env=environment,
    )
    try:
        deadline = time.monotonic() + 20
        ready_seen_at: float | None = None
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code is not None:
                raise InstallerVerificationError(
                    "Installed application exited before startup readiness "
                    f"with code {return_code}"
                )
            if ready_file.is_file():
                if ready_file.read_text(encoding="utf-8").strip() != "ready":
                    raise InstallerVerificationError(
                        "Installed application wrote an invalid startup readiness marker"
                    )
                if ready_seen_at is None:
                    ready_seen_at = time.monotonic()
                elif time.monotonic() - ready_seen_at >= 2:
                    return
            time.sleep(0.1)
        raise InstallerVerificationError(
            "Installed application did not report startup readiness within 20 seconds"
        )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("setup", type=Path)
    parser.add_argument("work_root", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_installer(args.setup, args.work_root)
    except InstallerVerificationError as exc:
        print(f"[ERROR] {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
