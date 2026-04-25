import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.execution_diagnostics import build_execution_diagnostics
from src.pipeline.result import PipelineResult
from src.pipeline.tracker import ChangeTracker
from src.report_writer import write_json_report, write_markdown_report


def _build_result_with_diagnostics() -> PipelineResult:
    tracker = ChangeTracker()
    tracker.record(
        rule_name="equation_table_format",
        target="3 个公式编号",
        section="global",
        change_type="skip",
        before="chapter-aware numbering normalization",
        after="skipped due to missing chapter context",
    )
    tracker.record(
        rule_name="table_format",
        target="pipeline",
        section="global",
        change_type="error",
        success=False,
        failure_reason="table layout explosion",
    )
    return PipelineResult(
        success=True,
        status="partial_success",
        tracker=tracker,
        failed_items=[
            {
                "rule_name": "table_format",
                "target": "pipeline",
                "section": "global",
                "change_type": "error",
                "paragraph_index": -1,
                "reason": "table layout explosion",
            }
        ],
    )


def test_build_execution_diagnostics_collects_skip_and_failure_records():
    result = _build_result_with_diagnostics()

    diagnostics = build_execution_diagnostics(result, summary_limit=2)

    assert diagnostics["count"] == 2
    assert diagnostics["items"][0]["change_type"] == "skip"
    assert diagnostics["items"][0]["reason"] == "skipped due to missing chapter context"
    assert diagnostics["items"][1]["reason"] == "table layout explosion"
    assert "诊断提示（2）" in diagnostics["summary"]


def test_report_writer_emits_diagnostics_into_json_and_markdown(tmp_path):
    result = _build_result_with_diagnostics()
    report_json = tmp_path / "changes.json"
    report_md = tmp_path / "changes.md"

    write_json_report(
        result,
        input_path=tmp_path / "sample.docx",
        output_path=None,
        report_path=report_json,
        elapsed=1.23,
        modules_enabled=3,
        modules_total=5,
    )
    write_markdown_report(
        result,
        input_path=tmp_path / "sample.docx",
        report_path=report_md,
        elapsed=1.23,
        modules_enabled=3,
        modules_total=5,
    )

    report_data = json.loads(report_json.read_text(encoding="utf-8"))
    markdown = report_md.read_text(encoding="utf-8")

    assert report_data["diagnostics"]["count"] == 2
    assert report_data["diagnostics"]["items"][0]["reason"] == "skipped due to missing chapter context"
    assert "## 诊断提示 (2 项)" in markdown
    assert "[equation_table_format] 3 个公式编号: skipped due to missing chapter context" in markdown
