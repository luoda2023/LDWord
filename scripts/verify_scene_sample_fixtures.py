from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from zipfile import is_zipfile


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_sample_fixture_registry import (  # noqa: E402
    REQUIRED_SAMPLE_PACK_IDS,
    list_scene_sample_fixtures,
)
from src.config.scene_high_frequency_request_samples import (  # noqa: E402
    list_high_frequency_request_samples,
)
from src.config.scene_request_cell_fixture_registry import (  # noqa: E402
    audit_scene_request_cell_fixtures,
)
from src.shared.engine.scene_sample_docx_builder import (  # noqa: E402
    build_scene_sample_docx_library,
)


def verify_scene_sample_fixture_library(output_dir: Path) -> list[str]:
    library = build_scene_sample_docx_library(output_dir)
    manifest_path = Path(library.manifest_path)
    issues: list[str] = []
    if not manifest_path.exists():
        issues.append(f"Missing manifest: {manifest_path}")
        return issues
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        issues.append(f"Cannot read manifest: {exc}")
        return issues

    artifacts = list(payload.get("artifacts") or [])
    request_cells = list(payload.get("request_cells") or [])
    request_cell_report_path = Path(str(payload.get("request_cell_report_path") or ""))
    expected_fixture_count = len(list_scene_sample_fixtures())
    expected_cell_count = len(list_high_frequency_request_samples())
    if int(payload.get("artifact_count") or 0) != expected_fixture_count:
        issues.append("Manifest artifact_count does not match fixture registry count.")
    if len(artifacts) != expected_fixture_count:
        issues.append("Manifest artifacts list does not match fixture registry count.")
    if int(payload.get("request_cell_count") or 0) != expected_cell_count:
        issues.append("Manifest request_cell_count does not match request sample count.")
    if len(request_cells) != expected_cell_count:
        issues.append("Manifest request_cells list does not match request sample count.")
    report_text = ""
    if not request_cell_report_path.exists():
        issues.append(f"Missing request-cell report: {request_cell_report_path}")
    else:
        report_text = request_cell_report_path.read_text(encoding="utf-8")
    request_cell_audit_issues = audit_scene_request_cell_fixtures()
    if request_cell_audit_issues:
        issues.append("Request-cell fixture audit is not clean.")
    pack_ids = {
        str(item.get("pack_id") or "")
        for item in artifacts
        if isinstance(item, dict)
    }
    if pack_ids != set(REQUIRED_SAMPLE_PACK_IDS):
        issues.append("Manifest pack set does not match required packs.")

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            issues.append("Manifest contains non-object artifact entry.")
            continue
        path = Path(str(artifact.get("path") or ""))
        if not path.exists():
            issues.append(f"Missing sample docx: {path}")
            continue
        if path.suffix.lower() != ".docx":
            issues.append(f"Sample path is not a docx: {path}")
        if not is_zipfile(path):
            issues.append(f"Sample docx is not an openable zip package: {path}")

    for cell in request_cells:
        if not isinstance(cell, dict):
            issues.append("Manifest contains non-object request-cell entry.")
            continue
        if not str(cell.get("sample_id") or "").strip():
            issues.append("Request-cell entry is missing sample_id.")
        report_path = Path(str(cell.get("report_path") or ""))
        report_anchor = str(cell.get("report_anchor") or "").strip()
        if report_path != request_cell_report_path:
            issues.append(
                f"Request-cell entry has wrong report path: {cell.get('sample_id')}"
            )
        if not report_anchor:
            issues.append(
                f"Request-cell entry is missing report anchor: {cell.get('sample_id')}"
            )
        elif report_text and f'id="{report_anchor}"' not in report_text:
            issues.append(
                f"Request-cell report is missing anchor: {cell.get('sample_id')}"
            )
        status = str(cell.get("expected_status") or "").strip()
        fixture_ids = list(cell.get("fixture_ids") or [])
        if status != "unmatched" and not fixture_ids:
            issues.append(
                f"Request-cell entry has no fixture evidence: {cell.get('sample_id')}"
            )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate and verify scene sample DOCX fixtures for CI/release checks.",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        help="Optional output directory. Defaults to a temporary directory.",
    )
    args = parser.parse_args()

    if args.output_dir:
        output_dir = Path(args.output_dir)
        issues = verify_scene_sample_fixture_library(output_dir)
        print(f"Verified scene sample fixtures at {output_dir}")
    else:
        with tempfile.TemporaryDirectory(prefix="scene_sample_fixtures_") as temp_dir:
            output_dir = Path(temp_dir)
            issues = verify_scene_sample_fixture_library(output_dir)
            print(f"Verified scene sample fixtures in temporary directory: {output_dir}")

    if issues:
        print("[FAIL] Scene sample fixture verification failed.")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        f"[OK] {len(list_scene_sample_fixtures())} scene sample fixtures covering "
        f"{len(REQUIRED_SAMPLE_PACK_IDS)} packs and "
        f"{len(list_high_frequency_request_samples())} request cells verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
