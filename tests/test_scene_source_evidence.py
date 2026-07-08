import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.scene_source_evidence import (  # noqa: E402
    scan_scene_source_markers,
    scene_source_marker_issue_message,
)


def test_scan_scene_source_markers_reports_missing_markers(tmp_path):
    source_path = tmp_path / "source.txt"
    source_path.write_text("alpha\nbeta\n", encoding="utf-8")

    result = scan_scene_source_markers(
        tmp_path,
        (
            (
                "sample",
                "source.txt",
                ("alpha", "gamma"),
            ),
        ),
    )

    assert len(result) == 1
    assert result[0].source_id == "sample"
    assert result[0].source_path == "source.txt"
    assert result[0].source_exists
    assert result[0].markers == ("alpha", "gamma")
    assert result[0].missing_markers == ("gamma",)


def test_scan_scene_source_markers_keeps_missing_file_visible(tmp_path):
    result = scan_scene_source_markers(
        tmp_path,
        (
            (
                "missing",
                "missing.txt",
                (),
            ),
        ),
    )

    assert len(result) == 1
    assert not result[0].source_exists
    assert result[0].missing_markers == ()


def test_scene_source_marker_issue_message_keeps_audit_wording():
    assert (
        scene_source_marker_issue_message("src/config/example.py", ("alpha", "gamma"))
        == "src/config/example.py missing markers: alpha, gamma"
    )
