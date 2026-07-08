import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
)

REGISTERED_EXPORT_WRAPPER_SPECS = SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
REGISTERED_EXPORT_WRAPPER_PATHS = tuple(
    ROOT / spec.export_script_path for spec in REGISTERED_EXPORT_WRAPPER_SPECS
)


def test_generic_scene_audit_exporter_dispatches_registered_release_audit(tmp_path):
    output_path = tmp_path / "terminal_release_exception.json"

    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_audit.py",
            "--audit",
            "scene_terminal_release_exception_audit",
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert json_result.stdout == ""
    assert payload["source_id"] == "scene_terminal_release_exception_audit"
    assert payload["status"] == "passed"
    assert payload["counts"]["issue_count"] == 0

    markdown_result = subprocess.run(
        [
            sys.executable,
            "scripts/export_scene_audit.py",
            "--audit",
            "scene_terminal_release_exception_audit",
            "--format",
            "markdown",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Scene Terminal Release Exception Audit" in markdown_result.stdout


def test_registered_release_governance_wrappers_delegate_to_generic_exporter():
    direct_builder = re.compile(r"build_scene_.*_audit_report")

    for spec, path in zip(
        REGISTERED_EXPORT_WRAPPER_SPECS,
        REGISTERED_EXPORT_WRAPPER_PATHS,
        strict=True,
    ):
        source = path.read_text(encoding="utf-8")

        assert "run_registered_scene_audit_export" in source
        assert f'"{spec.report_id}"' in source
        assert "import argparse" not in source
        assert "import json" not in source
        assert direct_builder.search(source) is None


def test_registered_export_wrapper_paths_match_release_governance_registry():
    assert len(REGISTERED_EXPORT_WRAPPER_PATHS) == len(REGISTERED_EXPORT_WRAPPER_SPECS)
    assert all(path.exists() for path in REGISTERED_EXPORT_WRAPPER_PATHS)
    assert tuple(
        path.relative_to(ROOT).as_posix() for path in REGISTERED_EXPORT_WRAPPER_PATHS
    ) == tuple(
        spec.export_script_path
        for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    )
