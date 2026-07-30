import os
from pathlib import Path

import pytest

from src.config.resolved import ResolvedConfig
from src.config.scene import DeliveryPreset, InputSourceProfile
from src.shared.io.artifact_publication import (
    publish_staged_artifacts as publish_staged_artifacts_transactionally,
)
from src.shared.engine import exam_question_schema as exam_runtime_module
from src.shared.engine.exam_question_schema import build_exam_delivery_runtime


def _config(*, answered: bool = True) -> ResolvedConfig:
    question = {
        "stem": "1 + 1 = ?",
        "score": 1,
    }
    if answered:
        question["answer"] = "2"
    payload = {
        "paper_title": "Atomic exam",
        "total_score": 1,
        "sections": [
            {
                "title": "Questions",
                "questions": [question],
            }
        ],
    }
    return ResolvedConfig(
        input_source_profile=InputSourceProfile(
            accepted_formats=["json"],
            structured_formats=["json"],
            material_schema_id="exam_items_v1",
        ),
        entity_data={"exam_items": payload},
        delivery_presets=[DeliveryPreset(preset_id="student", label="Student")],
    )


def _old_finals(output_root: Path) -> tuple[Path, Path]:
    artifact_dir = output_root / "exam_runtime"
    artifact_dir.mkdir(parents=True)
    preview = artifact_dir / "atomic_preview.md"
    docx = artifact_dir / "atomic_student.docx"
    preview.write_bytes(b"old-preview")
    docx.write_bytes(b"old-docx")
    return preview, docx


def _assert_no_exam_staging(output_root: Path) -> None:
    assert not list(output_root.glob(".exam-runtime-*"))


def test_exam_runtime_publishes_preview_and_docx_as_one_final_set(
    tmp_path: Path,
) -> None:
    runtime = build_exam_delivery_runtime(
        _config(),
        output_dir=tmp_path,
        source_stem="atomic",
    )

    preview = (tmp_path / "exam_runtime" / "atomic_preview.md").resolve()
    docx = (tmp_path / "exam_runtime" / "atomic_student.docx").resolve()
    assert runtime.status == "ok"
    assert Path(runtime.markdown_preview_path) == preview
    assert Path(runtime.rendered_versions[0].docx_path) == docx
    assert preview.is_file()
    assert docx.is_file()
    _assert_no_exam_staging(tmp_path)


def test_exam_validation_error_does_not_publish_or_replace_old_finals(
    tmp_path: Path,
) -> None:
    preview, docx = _old_finals(tmp_path)

    runtime = build_exam_delivery_runtime(
        _config(answered=False),
        output_dir=tmp_path,
        source_stem="atomic",
    )

    assert runtime.status == "blocked"
    assert runtime.skipped_reason == "schema_validation_errors"
    assert runtime.markdown_preview_path == ""
    assert runtime.rendered_versions == ()
    assert preview.read_bytes() == b"old-preview"
    assert docx.read_bytes() == b"old-docx"
    _assert_no_exam_staging(tmp_path)


def test_exam_render_failure_leaves_no_partial_final_and_preserves_old_finals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview, docx = _old_finals(tmp_path)

    def fail_after_partial_stage(_payload, _preset, docx_path, *, label):
        del label
        Path(docx_path).write_bytes(b"partial-staging-docx")
        raise RuntimeError("injected render failure")

    monkeypatch.setattr(
        exam_runtime_module,
        "_render_exam_version_docx",
        fail_after_partial_stage,
    )

    with pytest.raises(RuntimeError, match="injected render failure"):
        build_exam_delivery_runtime(
            _config(),
            output_dir=tmp_path,
            source_stem="atomic",
        )

    assert preview.read_bytes() == b"old-preview"
    assert docx.read_bytes() == b"old-docx"
    _assert_no_exam_staging(tmp_path)


def test_exam_publish_failure_rolls_back_every_old_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview, docx = _old_finals(tmp_path)

    class FailSecondCandidateReplace:
        def __init__(self) -> None:
            self.candidate_replaces = 0

        def __call__(self, source: str | Path, target: str | Path) -> None:
            if ".stage" in Path(source).name:
                self.candidate_replaces += 1
                if self.candidate_replaces == 2:
                    raise PermissionError("injected second publish failure")
            os.replace(source, target)

    failing_replace = FailSecondCandidateReplace()

    def publish_with_failure(artifacts, **kwargs):
        return publish_staged_artifacts_transactionally(
            artifacts,
            **kwargs,
            atomic_replace=failing_replace,
        )

    monkeypatch.setattr(
        exam_runtime_module,
        "publish_staged_artifacts",
        publish_with_failure,
    )

    with pytest.raises(PermissionError, match="injected second publish failure"):
        build_exam_delivery_runtime(
            _config(),
            output_dir=tmp_path,
            source_stem="atomic",
        )

    assert failing_replace.candidate_replaces == 2
    assert preview.read_bytes() == b"old-preview"
    assert docx.read_bytes() == b"old-docx"
    _assert_no_exam_staging(tmp_path)
