"""Create a user-only exam plan from an existing complete exam DOCX."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config.library import (
    ConfigLibraryEntry,
    load_scene_from_library,
    save_scene_to_library,
)
from src.config.master_library import EXAM_PLACEHOLDER_CONTRACT, MasterSpec
from src.config.master_preflight import check_master_preflight
from src.config.scene import ExamBlankStyleConfig
from src.config.scene_identity import allocate_scene_id
from src.shared.engine.exam_master_conversion import (
    ExamMasterConversionResult,
    convert_exam_docx_to_user_master,
)
from src.shared.engine.exam_paper_style import (
    PROJECT_ROOT,
    USER_EXAM_MASTER_DIR,
    write_exam_blank_style_sample_docx,
)

PlanActivator = Callable[[ConfigLibraryEntry, Any], None]


@dataclass(frozen=True, slots=True)
class ExamUserPlanCreationResult:
    plan_id: str
    plan_name: str
    plan_path: Path
    master_id: str
    master_path: Path
    master_sha256: str
    source_sha256: str
    sample_path: Path | None
    preflight_status: str
    activation_attempted: bool
    activation_succeeded: bool
    activation_error: str
    conversion: ExamMasterConversionResult


def create_exam_user_plan_from_docx(
    source_docx_path: Path | str,
    *,
    plan_name: str | None = None,
    preview_output_dir: Path | str | None = None,
    activate: PlanActivator | None = None,
) -> ExamUserPlanCreationResult:
    """Create one user master and one user plan with compensating rollback.

    The source document is read-only.  The master is published with a
    no-replace hard link, then the plan is committed with the library's
    create-only transaction.  A failed plan commit removes only the unchanged
    master published by this call.
    """

    source = Path(source_docx_path).expanduser().resolve()
    if source.suffix.casefold() != ".docx" or not source.is_file():
        raise ValueError("existing_exam_docx_required")
    normalized_name = str(plan_name or f"{source.stem} 用户方案").strip()
    if not normalized_name:
        raise ValueError("plan_name_required")
    if len(normalized_name) > 120:
        raise ValueError("plan_name_too_long")

    plan_id = allocate_scene_id(name=normalized_name, mode_id="exam")
    master_id, master_path = _allocate_master_identity(plan_id)
    USER_EXAM_MASTER_DIR.mkdir(parents=True, exist_ok=True)
    source_sha256 = _file_sha256(source)

    with tempfile.NamedTemporaryFile(
        prefix=f".{master_id}-",
        suffix=".stage.docx",
        dir=USER_EXAM_MASTER_DIR,
        delete=False,
    ) as stage_handle:
        stage_path = Path(stage_handle.name)
    published_master = False
    master_sha256 = ""
    conversion: ExamMasterConversionResult | None = None
    sample_path: Path | None = None
    try:
        conversion = convert_exam_docx_to_user_master(source, stage_path)
        master_sha256 = _file_sha256(stage_path)
        style = ExamBlankStyleConfig(
            style_id=master_id,
            label=f"{normalized_name}卷面",
            base_style_id="default_exam",
            master_docx_path=str(stage_path),
        )

        scene = deepcopy(load_scene_from_library("exam_term", mode_id="exam"))
        scene.name = normalized_name
        scene.description = f"由现用试卷“{source.name}”生成的用户方案"
        scene.scene_id = plan_id
        scene.mode_id = "exam"
        scene.display_order = 0
        scene.template_id = "default"
        scene.compatible_template_ids = ["default"]
        scene.master_id = master_id
        scene.exam_paper.custom_blank_styles.append(style)
        scene.exam_paper.__post_init__()

        staged_master = MasterSpec(
            master_id=master_id,
            mode_id="exam",
            label=style.label,
            family="exam_blank",
            source_type="user",
            docx_path=stage_path,
            readonly=False,
            base_master_id="default_exam",
            placeholder_contract=EXAM_PLACEHOLDER_CONTRACT,
        )
        preflight = check_master_preflight(staged_master)
        if not preflight.ok:
            missing = ",".join(preflight.missing_required_placeholders)
            raise ValueError(
                f"exam_master_preflight_failed:{preflight.status}:{missing}"
            )

        if preview_output_dir is None:
            with tempfile.TemporaryDirectory(prefix="exam-master-preview-") as temp_dir:
                write_exam_blank_style_sample_docx(
                    master_id,
                    temp_dir,
                    config=scene.exam_paper,
                )
        else:
            preview_dir = Path(preview_output_dir).expanduser().resolve()
            preview_dir.mkdir(parents=True, exist_ok=True)
            sample_path = write_exam_blank_style_sample_docx(
                master_id,
                preview_dir,
                config=scene.exam_paper,
            )

        scene.exam_paper.custom_blank_styles[-1].master_docx_path = (
            _stored_master_path(master_path)
        )
        os.link(stage_path, master_path)
        published_master = True
        entry = save_scene_to_library(
            scene,
            plan_id,
            mode_id="exam",
            expected_absent=True,
        )
    except Exception:
        if (
            published_master
            and master_path.is_file()
            and master_sha256
            and _file_sha256(master_path) == master_sha256
        ):
            master_path.unlink()
        raise
    finally:
        stage_path.unlink(missing_ok=True)

    activation_attempted = activate is not None
    activation_succeeded = False
    activation_error = ""
    if activate is not None:
        try:
            activate(entry, scene)
            activation_succeeded = True
        except Exception as exc:  # noqa: BLE001 - activation cannot revoke publication
            activation_error = str(exc) or type(exc).__name__

    if conversion is None:  # pragma: no cover - guarded by successful publication
        raise RuntimeError("exam_master_conversion_result_missing")
    return ExamUserPlanCreationResult(
        plan_id=plan_id,
        plan_name=normalized_name,
        plan_path=entry.path,
        master_id=master_id,
        master_path=master_path,
        master_sha256=master_sha256,
        source_sha256=source_sha256,
        sample_path=sample_path,
        preflight_status="ok",
        activation_attempted=activation_attempted,
        activation_succeeded=activation_succeeded,
        activation_error=activation_error,
        conversion=conversion,
    )


def _allocate_master_identity(plan_id: str) -> tuple[str, Path]:
    digest = hashlib.sha256(str(plan_id).encode("utf-8")).hexdigest()[:12]
    base_id = f"user_exam_{digest}"
    for index in range(1, 1001):
        suffix = "" if index == 1 else f"_{index}"
        master_id = f"{base_id}{suffix}"
        target = USER_EXAM_MASTER_DIR / f"{master_id}.docx"
        if not target.exists():
            return master_id, target
    raise RuntimeError("exam_master_identity_allocation_exhausted")


def _stored_master_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ExamUserPlanCreationResult",
    "PlanActivator",
    "create_exam_user_plan_from_docx",
]
