from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

from docx import Document
import pytest

from src.services.execution_session import resolution as execution_session_resolution
from src.services.execution_session.support import object_revision
from src.config.entity import EntityArchive, EntityProfile
from src.services.execution_session import build_execution_session_snapshot
from src.config.library import load_scene_from_library, load_template_from_library
from src.config.material_context import MaterialExecutionContext
from src.config.object_preflight_evidence import build_object_preflight_evidence
from src.config.scene import DeliveryPreset, SceneWorkspace
from src.config.template import TemplateConfig
from src.ui.panels.workbench.execution_worker import ExecutionWorker
from src.ui.panels.workbench.execution_session_controller import (
    WorkbenchExecutionSessionController,
)
import src.ui.panels.workbench.execution_session_controller as session_controller_module
import src.ui.panels.workbench.execution_thread_handle as execution_thread_handle
import src.ui.panels.workbench.execution_worker as execution_worker


def _write_docx(path: Path, text: str = "input") -> bytes:
    document = Document()
    document.add_paragraph(text)
    document.save(path)
    return path.read_bytes()


def _install_resource_entries(monkeypatch, *, plan_path: Path, template_path: Path):
    monkeypatch.setattr(
        execution_session_resolution,
        "get_scene_entry",
        lambda resource_id, *, mode_id: SimpleNamespace(
            path=plan_path,
            source_type="user",
        ),
    )
    monkeypatch.setattr(
        execution_session_resolution,
        "get_template_entry",
        lambda resource_id, *, mode_id: SimpleNamespace(
            path=template_path,
            source_type="user",
        ),
    )


def _snapshot(
    tmp_path: Path,
    *,
    scene: SceneWorkspace,
    template: TemplateConfig,
    material_context: MaterialExecutionContext | None = None,
):
    source = tmp_path / "input.docx"
    _write_docx(source)
    evidence = build_object_preflight_evidence(scene, source)
    return build_execution_session_snapshot(
        mode_id="custom",
        scene=scene,
        template=template,
        material_context=(
            material_context
            if material_context is not None
            else MaterialExecutionContext(mode_id="custom")
        ),
        input_path=source,
        output_root=tmp_path / "runs",
        plan_id="plan_a",
        template_id="template_a",
        object_preflight_confirmation_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )


def test_plan_ref_tracks_effective_object_when_disk_identity_is_unchanged(
    tmp_path,
    monkeypatch,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    first_scene = SceneWorkspace(
        name="runtime plan v1",
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
    )
    second_scene = copy.deepcopy(first_scene)
    second_scene.name = "runtime plan v2"

    first = _snapshot(tmp_path, scene=first_scene, template=TemplateConfig())
    second = _snapshot(tmp_path, scene=second_scene, template=TemplateConfig())

    assert first.plan_ref.source_revision == second.plan_ref.source_revision
    assert first.plan_ref.effective_revision != second.plan_ref.effective_revision
    assert first.plan_ref.revision == first.plan_ref.effective_revision
    assert second.plan_ref.revision == second.plan_ref.effective_revision


def test_template_ref_tracks_effective_object_when_disk_identity_is_unchanged(
    tmp_path,
    monkeypatch,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    scene = SceneWorkspace(
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
    )

    first = _snapshot(
        tmp_path,
        scene=scene,
        template=TemplateConfig(name="runtime template v1"),
    )
    second = _snapshot(
        tmp_path,
        scene=scene,
        template=TemplateConfig(name="runtime template v2"),
    )

    assert first.template_ref.source_revision == second.template_ref.source_revision
    assert first.template_ref.effective_revision != second.template_ref.effective_revision
    assert first.template_ref.revision == first.template_ref.effective_revision
    assert second.template_ref.revision == second.template_ref.effective_revision


def test_execution_session_rejects_unknown_material_schema_before_ready(
    tmp_path,
    monkeypatch,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    scene = SceneWorkspace(
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
    )
    scene.input_source_profile.material_schema_id = "unknown_schema_v1"

    snapshot = _snapshot(
        tmp_path,
        scene=scene,
        template=TemplateConfig(),
    )

    assert snapshot.ready is False
    assert "unknown_material_schema:unknown_schema_v1" in snapshot.issues


def test_execution_session_rejects_declared_journal_rule_source_error(
    tmp_path,
    monkeypatch,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    scene = SceneWorkspace(
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
    )
    scene.input_source_profile.material_schema_id = (
        "journal_submission_materials_v1"
    )
    scene.compliance_profile.profile_id = "journal_submission"
    scene.compliance_profile.rule_family = "journal_en"
    scene.compliance_profile.count_profile_id = "journal_words"
    material_context = MaterialExecutionContext(
        mode_id="custom",
        entity_data={"journal_rule_source_id": "definitely_unknown"},
    )

    snapshot = _snapshot(
        tmp_path,
        scene=scene,
        template=TemplateConfig(),
        material_context=material_context,
    )

    assert snapshot.ready is False
    assert (
        "journal_rule_source_governance_error:"
        "unregistered_rule_source:definitely_unknown"
    ) in snapshot.issues
    assert snapshot.input_ref.frozen_path == ""


def test_execution_session_rejects_missing_journal_count_profile_before_freeze(
    tmp_path,
    monkeypatch,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    scene = SceneWorkspace(
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
    )
    scene.input_source_profile.material_schema_id = (
        "journal_submission_materials_v1"
    )
    scene.compliance_profile.profile_id = "journal_submission"
    scene.compliance_profile.rule_family = "journal_en"
    scene.compliance_profile.count_profile_id = ""

    snapshot = _snapshot(
        tmp_path,
        scene=scene,
        template=TemplateConfig(),
    )

    assert snapshot.ready is False
    assert (
        "journal_rule_source_governance_error:count_profile_missing:-"
        in snapshot.issues
    )
    assert snapshot.input_ref.frozen_path == ""


def test_execution_session_rejects_unknown_count_profile_before_ready(
    tmp_path,
    monkeypatch,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    scene = SceneWorkspace(
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
    )
    scene.compliance_profile.count_profile_id = "not_registered"

    snapshot = _snapshot(
        tmp_path,
        scene=scene,
        template=TemplateConfig(),
    )

    assert snapshot.ready is False
    assert "unknown_count_profile:not_registered" in snapshot.issues


@pytest.mark.parametrize(
    "profile_name",
    ("input_source_profile", "compliance_profile"),
)
def test_execution_session_rejects_invalid_failure_policy_before_ready(
    tmp_path,
    monkeypatch,
    profile_name,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    scene = SceneWorkspace(
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
    )
    getattr(scene, profile_name).failure_policy = "blok"

    snapshot = _snapshot(
        tmp_path,
        scene=scene,
        template=TemplateConfig(),
    )

    assert snapshot.ready is False
    assert (
        f"{profile_name}.failure_policy:execution_failure_policy_invalid:blok"
        in snapshot.issues
    )


def test_execution_session_rejects_duplicate_delivery_identity_before_ready(
    tmp_path,
    monkeypatch,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    scene = SceneWorkspace(
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
        default_delivery_preset_id="same",
        delivery_presets=[
            DeliveryPreset(preset_id="same"),
            DeliveryPreset(preset_id="same"),
        ],
    )

    snapshot = _snapshot(
        tmp_path,
        scene=scene,
        template=TemplateConfig(),
    )

    assert snapshot.ready is False
    assert "duplicate_delivery_preset_id:same" in snapshot.issues


def test_normal_library_snapshot_separates_source_and_effective_revisions(tmp_path):
    source = tmp_path / "input.docx"
    _write_docx(source)
    scene = load_scene_from_library("official", mode_id="official")
    template = load_template_from_library("official_gbt", mode_id="official")
    evidence = build_object_preflight_evidence(scene, source)

    snapshot = build_execution_session_snapshot(
        mode_id="official",
        scene=scene,
        template=template,
        material_context=MaterialExecutionContext(mode_id="official"),
        input_path=source,
        output_root=tmp_path / "runs",
        plan_id="official",
        template_id="official_gbt",
        document_type_id="notice",
        object_preflight_confirmation_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )

    assert snapshot.ready
    for resource_ref in (snapshot.plan_ref, snapshot.template_ref):
        assert Path(resource_ref.path).is_file()
        assert resource_ref.source_revision.startswith("sha256:")
        assert resource_ref.effective_revision.startswith("sha256:")
        assert resource_ref.revision == resource_ref.effective_revision


@pytest.mark.parametrize(
    ("material_profile_id", "scene_default_profile_id"),
    (
        ("official:letter", "official:notice"),
        ("", "official:notice"),
    ),
)
def test_official_snapshot_does_not_infer_document_type_from_material_or_scene(
    tmp_path,
    material_profile_id,
    scene_default_profile_id,
):
    source = tmp_path / "input.docx"
    _write_docx(source)
    scene = load_scene_from_library("official", mode_id="official")
    scene.default_material_profile_id = scene_default_profile_id
    template = load_template_from_library("official_gbt", mode_id="official")
    evidence = build_object_preflight_evidence(scene, source)

    snapshot = build_execution_session_snapshot(
        mode_id="official",
        scene=scene,
        template=template,
        material_context=MaterialExecutionContext(
            mode_id="official",
            profile_id=material_profile_id,
        ),
        input_path=source,
        output_root=tmp_path / "runs",
        plan_id="official",
        template_id="official_gbt",
        object_preflight_confirmation_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )

    assert snapshot.document_type_id == ""
    assert snapshot.ready is False
    assert "official_document_type_missing" in snapshot.issues


def test_official_snapshot_preserves_unknown_explicit_document_type_for_validation(
    tmp_path,
):
    source = tmp_path / "input.docx"
    _write_docx(source)
    scene = load_scene_from_library("official", mode_id="official")
    template = load_template_from_library("official_gbt", mode_id="official")
    evidence = build_object_preflight_evidence(scene, source)

    snapshot = build_execution_session_snapshot(
        mode_id="official",
        scene=scene,
        template=template,
        material_context=MaterialExecutionContext(
            mode_id="official",
            profile_id="official:letter",
        ),
        input_path=source,
        output_root=tmp_path / "runs",
        plan_id="official",
        template_id="official_gbt",
        document_type_id="not_registered",
        object_preflight_confirmation_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )

    assert snapshot.document_type_id == "not_registered"
    assert snapshot.ready is False
    assert "official_document_type_unknown:not_registered" in snapshot.issues
    assert "official_document_type_missing" not in snapshot.issues


@pytest.mark.parametrize("mode_id", ("custom", "exam"))
def test_headless_non_official_snapshot_rejects_official_document_type(
    tmp_path,
    mode_id,
):
    source = tmp_path / f"{mode_id}.docx"
    _write_docx(source)
    scene = load_scene_from_library(mode_id, mode_id=mode_id)
    template = load_template_from_library("default", mode_id=mode_id)
    evidence = build_object_preflight_evidence(scene, source)

    snapshot = build_execution_session_snapshot(
        mode_id=mode_id,
        scene=scene,
        template=template,
        material_context=MaterialExecutionContext(mode_id=mode_id),
        input_path=source,
        output_root=tmp_path / "runs",
        plan_id=mode_id,
        template_id="default",
        document_type_id="notice",
        object_preflight_confirmation_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )

    assert snapshot.document_type_id == "notice"
    assert snapshot.ready is False
    assert (
        f"official_document_type_not_applicable:{mode_id}:notice"
        in snapshot.issues
    )


@pytest.mark.parametrize(
    ("scene_mode_id", "expected_mode_id", "expected_issue"),
    (
        (
            "official_document",
            "official",
            "execution_mode_not_canonical:scene.mode_id:official_document:official",
        ),
        ("", "", "execution_mode_missing:scene.mode_id"),
    ),
)
def test_snapshot_rejects_missing_or_aliased_scene_mode(
    tmp_path,
    scene_mode_id,
    expected_mode_id,
    expected_issue,
):
    source = tmp_path / "source.docx"
    _write_docx(source)
    scene = load_scene_from_library("official", mode_id="official")
    scene.mode_id = scene_mode_id
    template = load_template_from_library("official_gbt", mode_id="official")
    evidence = build_object_preflight_evidence(scene, source)

    snapshot = build_execution_session_snapshot(
        mode_id="",
        scene=scene,
        template=template,
        material_context=MaterialExecutionContext(),
        input_path=source,
        output_root=tmp_path / "runs",
        plan_id="official",
        template_id="official_gbt",
        document_type_id="notice",
        object_preflight_confirmation_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )

    assert not snapshot.ready
    assert expected_issue in snapshot.issues
    assert snapshot.mode_id == expected_mode_id
    assert snapshot.plan_ref.mode_id == expected_mode_id
    assert snapshot.template_ref.mode_id == expected_mode_id


def test_controller_single_run_rejects_noncanonical_requested_mode_before_projection(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.docx"
    _write_docx(source)
    scene = load_scene_from_library("official", mode_id="official")
    scene.mode_id = "custom"
    template = load_template_from_library("official_gbt", mode_id="official")
    evidence = build_object_preflight_evidence(scene, source)
    resolve_calls: list[str] = []
    real_resolve = session_controller_module.resolve_work_mode_id

    def resolve_once(value, *, requested_mode_id=""):
        resolve_calls.append(str(requested_mode_id or ""))
        return real_resolve(value, requested_mode_id=requested_mode_id)

    class _Worker:
        def __init__(self, runner, parent=None):
            self.runner = runner

    class _Handle:
        def __init__(self, worker, parent=None):
            self.worker = worker

    monkeypatch.setattr(
        session_controller_module,
        "resolve_work_mode_id",
        resolve_once,
    )
    monkeypatch.setattr(execution_worker, "ExecutionWorker", _Worker)
    monkeypatch.setattr(execution_thread_handle, "ThreadedExecutionHandle", _Handle)

    build = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: source,
    ).build_worker(
        template=template,
        scene=scene,
        material_context=MaterialExecutionContext(),
        document_type_id="notice",
        mode_id="official_document",
        plan_id="official",
        template_id="official_gbt",
        output_root=str(tmp_path / "runs"),
        material_gate_confirmed=True,
        expected_input_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )

    assert build.worker is None
    assert build.error_text == (
        "execution_mode_not_canonical:requested_mode_id:"
        "official_document:official"
    )
    assert resolve_calls == []


def test_controller_batch_rejects_missing_scene_mode_before_gate_and_snapshot(
    tmp_path,
    monkeypatch,
):
    scene = load_scene_from_library("official", mode_id="official")
    scene.mode_id = ""
    scene.scene_id = "category_only_plan"
    scene.category = "official_document"
    template = load_template_from_library("official_gbt", mode_id="official")
    resolve_calls: list[str] = []
    selection_modes: list[str] = []
    real_resolve = session_controller_module.resolve_work_mode_id
    real_gate = session_controller_module.material_batch_readiness_gate_decision

    def resolve_once(value, *, requested_mode_id=""):
        resolve_calls.append(str(requested_mode_id or ""))
        return real_resolve(value, requested_mode_id=requested_mode_id)

    def capture_gate(value, selection):
        selection_modes.append(selection.mode_id)
        return real_gate(value, selection)

    class _Worker:
        def __init__(self, runner, parent=None):
            self.runner = runner

    class _Handle:
        def __init__(self, worker, parent=None):
            self.worker = worker

    monkeypatch.setattr(
        session_controller_module,
        "resolve_work_mode_id",
        resolve_once,
    )
    monkeypatch.setattr(
        session_controller_module,
        "material_batch_readiness_gate_decision",
        capture_gate,
    )
    monkeypatch.setattr(execution_worker, "ExecutionWorker", _Worker)
    monkeypatch.setattr(execution_thread_handle, "ThreadedExecutionHandle", _Handle)

    build = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: None,
    ).build_batch_worker(
        template=template,
        scene=scene,
        archive=EntityArchive(
            profiles=[
                EntityProfile(
                    profile_id="row_1",
                    fields={"document_type": "notice"},
                )
            ]
        ),
        profile_ids=["row_1"],
        source_kind="official_document_table",
        source_path=str(tmp_path / "official.csv"),
        mode_id="",
        plan_id="official",
        template_id="official_gbt",
        base_output_dir=str(tmp_path / "runs"),
        material_gate_confirmed=True,
    )

    assert build.worker is None
    assert build.error_text == "execution_mode_missing:scene.mode_id"
    assert resolve_calls == []
    assert selection_modes == []
    assert build.session_snapshot is None


def test_execution_session_receipt_roundtrip_preserves_effective_identity(tmp_path):
    source = tmp_path / "input.docx"
    _write_docx(source)
    scene = load_scene_from_library("official", mode_id="official")
    template = load_template_from_library("official_gbt", mode_id="official")
    evidence = build_object_preflight_evidence(scene, source)
    snapshot = build_execution_session_snapshot(
        mode_id="official",
        scene=scene,
        template=template,
        material_context=MaterialExecutionContext(mode_id="official"),
        input_path=source,
        output_root=tmp_path / "runs",
        plan_id="official",
        template_id="official_gbt",
        document_type_id="notice",
        object_preflight_confirmation_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )

    class Runner:
        execution_session_snapshot = snapshot

    payload = ExecutionWorker(Runner())._normalize_result(
        {"status": "success"},
        "success",
    )
    saved = json.loads(
        Path(payload["execution_session_path"]).read_text(encoding="utf-8")
    )

    assert saved == snapshot.to_dict()
    assert saved["plan_ref"]["revision"] == saved["plan_ref"]["effective_revision"]
    assert saved["template_ref"]["revision"] == saved["template_ref"][
        "effective_revision"
    ]


def test_controller_passes_the_snapshotted_plan_and_template_to_runner(
    tmp_path,
    monkeypatch,
):
    plan_path = tmp_path / "plan_a.json"
    template_path = tmp_path / "template_a.json"
    plan_path.write_text('{"name":"disk plan"}', encoding="utf-8")
    template_path.write_text('{"name":"disk template"}', encoding="utf-8")
    _install_resource_entries(
        monkeypatch,
        plan_path=plan_path,
        template_path=template_path,
    )
    source = tmp_path / "input.docx"
    source_bytes = _write_docx(source)
    scene = SceneWorkspace(
        name="effective plan",
        scene_id="plan_a",
        mode_id="custom",
        template_id="template_a",
        compatible_template_ids=["template_a"],
    )
    template = TemplateConfig(name="effective template")

    class _Worker:
        def __init__(self, runner, parent=None):
            self.runner = runner

    class _Handle:
        def __init__(self, worker, parent=None):
            self.worker = worker

    monkeypatch.setattr(execution_worker, "ExecutionWorker", _Worker)
    monkeypatch.setattr(execution_thread_handle, "ThreadedExecutionHandle", _Handle)
    evidence = build_object_preflight_evidence(scene, source)
    build = WorkbenchExecutionSessionController(
        resolve_document_path=lambda: source,
    ).build_worker(
        template=template,
        scene=scene,
        material_context=MaterialExecutionContext(mode_id="custom"),
        mode_id="custom",
        plan_id="plan_a",
        template_id="template_a",
        material_gate_confirmed=True,
        expected_input_revision=evidence.source_revision,
        object_preflight_confirmation_digest=evidence.evidence_digest,
    )

    assert build.worker is not None
    runner = build.worker.worker.runner
    assert build.session_snapshot is runner.execution_session_snapshot
    frozen_input = Path(build.session_snapshot.input_ref.frozen_path)
    assert frozen_input.is_file()
    assert Path(runner.doc_path) == frozen_input
    _write_docx(source, "input-v2")
    assert Path(runner.doc_path).read_bytes() == source_bytes
    assert build.session_snapshot.plan_ref.effective_revision == (
        object_revision(runner._scene)
    )
    assert build.session_snapshot.template_ref.effective_revision == (
        object_revision(runner._template)
    )
