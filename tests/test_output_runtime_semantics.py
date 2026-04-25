import sys
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config.resolver import resolve_config
from src.config.scene import SceneWorkspace
from src.config.template import TemplateConfig
from src.modules.basic.header_footer import HeaderFooterModule
from src.modules.basic.section_format import SectionFormatModule
from src.modules.structure.heading_recognition import HeadingRecognitionModule
from src.pipeline.result import PipelineResult
from src.pipeline.tracker import ChangeTracker
from src.pipeline.runner import Pipeline
from src.shared.engine.field_builder import iter_field_instructions
import src.ui.panels.workbench.execution_runtime as execution_runtime
from src.ui.panels.workbench.execution_runtime import WorkbenchProductionRunner


def test_pipeline_skips_final_output_when_final_docx_is_disabled(tmp_path):
    source = tmp_path / "source.docx"
    Document().save(source)

    template = TemplateConfig()
    template.output.final_docx = False
    config = resolve_config(template, SceneWorkspace())

    output_dir = tmp_path / "out"
    result = Pipeline(
        modules=[],
        config=config,
        output_dir=str(output_dir),
        output_suffix="_formatted",
    ).execute(str(source))

    assert result.success is True
    assert result.output_paths == {}
    assert (output_dir / "source_formatted.docx").exists() is False


def test_workbench_runner_can_emit_json_report_without_final_docx(tmp_path, monkeypatch):
    source = tmp_path / "source.docx"
    Document().save(source)

    template = TemplateConfig()
    template.output.final_docx = False
    template.output.report_json = True
    template.output.report_markdown = False

    monkeypatch.setattr(execution_runtime, "create_all_modules", lambda: [])
    monkeypatch.setattr(
        execution_runtime,
        "select_enabled_modules",
        lambda modules, predicate: ([], {}),
    )

    payload = WorkbenchProductionRunner(
        doc_path=str(source),
        template=template,
        scene=SceneWorkspace(),
    ).run(lambda *_args: None, lambda: False)

    report_json = source.parent / "output" / "source_changes.json"
    report_md = source.parent / "output" / "source_changes.md"

    assert payload["status"] == "success"
    assert payload["output_path"] == ""
    assert payload["report_paths"] == [str(report_json)]
    assert report_json.exists() is True
    assert report_md.exists() is False
    assert '"output": ""' in report_json.read_text(encoding="utf-8")


def test_workbench_runner_surfaces_diagnostics_summary(tmp_path, monkeypatch):
    source = tmp_path / "source.docx"
    Document().save(source)

    template = TemplateConfig()
    template.output.final_docx = False
    template.output.report_json = False
    template.output.report_markdown = False

    tracker = ChangeTracker()
    tracker.record(
        rule_name="equation_table_format",
        target="1 个公式编号",
        section="global",
        change_type="skip",
        before="chapter-aware numbering normalization",
        after="skipped due to missing chapter context",
    )

    class _StubPipeline:
        def __init__(self, **_kwargs):
            pass

        def execute(self, _doc_path: str) -> PipelineResult:
            return PipelineResult(
                success=True,
                status="success",
                tracker=tracker,
                output_paths={},
            )

    monkeypatch.setattr(execution_runtime, "create_all_modules", lambda: [])
    monkeypatch.setattr(
        execution_runtime,
        "select_enabled_modules",
        lambda modules, predicate: ([], {}),
    )
    monkeypatch.setattr(execution_runtime, "Pipeline", _StubPipeline)

    payload = WorkbenchProductionRunner(
        doc_path=str(source),
        template=template,
        scene=SceneWorkspace(),
    ).run(lambda *_args: None, lambda: False)

    assert payload["status"] == "success"
    assert payload["diagnostics_count"] == 1
    assert "missing chapter context" in payload["diagnostics_summary"]


def test_workbench_runner_applies_session_overrides_before_pipeline(tmp_path, monkeypatch):
    source = tmp_path / "source.docx"
    Document().save(source)

    captured = {}

    class _StubPipeline:
        def __init__(self, **kwargs):
            captured["config"] = kwargs["config"]

        def execute(self, _doc_path: str) -> PipelineResult:
            return PipelineResult(
                success=True,
                status="success",
                output_paths={},
            )

    monkeypatch.setattr(execution_runtime, "create_all_modules", lambda: [])
    monkeypatch.setattr(
        execution_runtime,
        "select_enabled_modules",
        lambda modules, predicate: ([], {}),
    )
    monkeypatch.setattr(execution_runtime, "Pipeline", _StubPipeline)

    payload = WorkbenchProductionRunner(
        doc_path=str(source),
        template=TemplateConfig(),
        scene=SceneWorkspace(),
        session_overrides={"header_footer.suppress_header_footer_selectors": []},
    ).run(lambda *_args: None, lambda: False)

    config = captured["config"]
    assert payload["status"] == "success"
    assert config.header_footer.suppress_header_footer_selectors == []
    assert config.get_with_source("header_footer.suppress_header_footer_selectors").source == "session"


def test_workbench_runner_session_override_changes_cover_page_number_visibility(tmp_path, monkeypatch):
    source = tmp_path / "thesis.docx"
    doc = Document()
    for text in ["博士学位论文", "原创性声明", "摘要", "目录"]:
        doc.add_paragraph(text)
    doc.add_heading("第一章 绪论", level=1)
    doc.add_paragraph("正文内容")
    doc.save(source)

    monkeypatch.setattr(
        execution_runtime,
        "create_all_modules",
        lambda: [
            HeadingRecognitionModule(),
            SectionFormatModule(),
            HeaderFooterModule(),
        ],
    )

    default_payload = WorkbenchProductionRunner(
        doc_path=str(source),
        template=TemplateConfig(),
        scene=SceneWorkspace(),
    ).run(lambda *_args: None, lambda: False)
    default_doc = Document(default_payload["output_path"])

    override_payload = WorkbenchProductionRunner(
        doc_path=str(source),
        template=TemplateConfig(),
        scene=SceneWorkspace(),
        session_overrides={"header_footer.suppress_header_footer_selectors": []},
    ).run(lambda *_args: None, lambda: False)
    override_doc = Document(override_payload["output_path"])

    assert default_payload["status"] in {"success", "partial_success"}
    assert override_payload["status"] in {"success", "partial_success"}
    assert _section_has_page_field(default_doc.sections[0]) is False
    assert _section_has_page_field(override_doc.sections[0]) is True


def _section_has_page_field(section) -> bool:
    footer = section.footer
    for para in footer.paragraphs:
        for _kind, _elem, instr in iter_field_instructions(para._element):
            if "PAGE" in str(instr or "").upper():
                return True
    return False
