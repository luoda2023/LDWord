from dataclasses import replace
import json

import pytest

from src.config.master_library import MasterManifestError, default_master
from src.config.master_placeholder_index import (
    MASTER_PLACEHOLDER_SCANNER_VERSION,
    placeholder_index_matches_payload,
    scan_master_placeholder_index,
)
from src.config.master_preflight import check_master_preflight


def test_official_master_placeholder_index_is_stable_and_excludes_reference_page():
    master = default_master("official")
    assert master is not None

    snapshots = [
        scan_master_placeholder_index(master.docx_path, use_cache=False)
        for _index in range(100)
    ]
    first = snapshots[0]

    assert all(item == first for item in snapshots)
    assert first.scanner_version == MASTER_PLACEHOLDER_SCANNER_VERSION
    assert first.reference_page_excluded is False
    assert first.raw_counts["@text:official_title"] == 1
    assert first.replaceable_counts["@text:official_title"] == 1
    assert first.replaceable_counts["@text:official_copy_scope"] == 1
    assert "@text:official_meeting_time" not in first.placeholder_ids
    assert "@text:official_meeting_attendees" not in first.replaceable_placeholder_ids
    assert len(first.replaceable_placeholder_ids) == 13


def test_official_master_registered_index_matches_versioned_inventory():
    master = default_master("official")
    assert master is not None
    manifest = json.loads(master.manifest_path.read_text(encoding="utf-8"))
    index = scan_master_placeholder_index(master.docx_path)

    assert placeholder_index_matches_payload(
        index,
        manifest["placeholder_index"],
    )
    assert master.placeholder_contract.runtime_inserted_placeholders == ()

    preflight = check_master_preflight(master)
    assert preflight.status == "ok"
    assert preflight.placeholder_index_status == "ok"
    assert preflight.placeholder_index_sha256 == index.sha256
    assert preflight.missing_required_placeholders == ()
    assert preflight.missing_optional_placeholders == ()
    assert preflight.unexpected_placeholders == ()


def test_exam_master_registered_index_matches_versioned_inventory():
    master = default_master("exam")
    assert master is not None
    manifest = json.loads(master.manifest_path.read_text(encoding="utf-8"))
    index = scan_master_placeholder_index(master.docx_path, use_cache=False)

    assert placeholder_index_matches_payload(index, manifest["placeholder_index"])
    assert index.replaceable_placeholder_ids == (
        "af_title",
        "af_version",
        "af_subject",
        "af_grade",
        "af_duration",
        "af_total_score",
        "af_questions",
        "af_answer_area",
    )

    preflight = check_master_preflight(master)
    assert preflight.status == "ok"
    assert preflight.placeholder_index_status == "ok"
    assert preflight.placeholder_index_sha256 == index.sha256
    assert preflight.missing_required_placeholders == ()
    assert preflight.missing_optional_placeholders == ()


def test_preflight_reports_stale_registered_index(tmp_path):
    master = default_master("official")
    assert master is not None
    manifest_payload = json.loads(master.manifest_path.read_text(encoding="utf-8"))
    manifest_payload["placeholder_index"]["sha256"] = "stale"
    manifest_path = tmp_path / "stale.master.json"
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    result = check_master_preflight(replace(master, manifest_path=manifest_path))

    assert result.status == "placeholder_index_stale"
    assert result.placeholder_index_status == "stale"


def test_preflight_does_not_hide_manifest_corruption_as_unregistered(tmp_path):
    master = default_master("official")
    assert master is not None
    manifest_path = tmp_path / "corrupt.master.json"
    manifest_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(MasterManifestError, match="master_manifest_unreadable"):
        check_master_preflight(replace(master, manifest_path=manifest_path))
