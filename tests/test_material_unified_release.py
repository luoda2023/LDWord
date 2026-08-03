from __future__ import annotations

import hashlib
import json
import multiprocessing
from pathlib import Path

import pytest
from docx import Document

from src.application.materials import (
    ExecutionMaterialFinalizeRequest,
    bind_repository_material_run,
    execution_material_snapshot_from_payload,
    finalize_execution_material_snapshot,
)
from src.config.material_package_library import (
    CANONICAL_MATERIAL_PACKAGE_LIBRARY_DIR,
    DEFAULT_MATERIAL_PACKAGE_IDENTITIES,
    material_package_repository,
)
from src.config.work_mode import list_work_modes
from src.domain.materials import (
    MaterialContract,
    MaterialDerivationSpec,
    MaterialFieldContract,
    MaterialPackage,
    MaterialPackageRef,
    MaterialRecord,
    MaterialResolver,
    MaterialRunSelection,
    MaterialScope,
    MaterialTimelineSpec,
    clone_material_package,
    generate_package_id,
    generate_record_id,
)
from src.infrastructure.materials.codec import material_package_revision
from src.infrastructure.materials.repository import MaterialPackageRepository
from src.material_suite.plan import (
    compile_material_suite_plan,
    discover_material_suite_bundle,
)
from src.material_suite.runner import MaterialSuiteGenerationRunner

ROOT = Path(__file__).resolve().parents[1]


def _concurrent_save_worker(
    root: str,
    package_id: str,
    expected_revision: str,
    display_name: str,
    start,
    ready,
    results,
) -> None:
    repository = MaterialPackageRepository(root)
    current = repository.load(
        work_mode_id="custom",
        source_type="user",
        package_id=package_id,
    )
    updated = clone_material_package(
        current.package,
        display_name=display_name,
    )
    ready.put(display_name)
    start.wait(10)
    try:
        saved = repository.save_user(
            updated,
            expected_revision=expected_revision,
        )
    except Exception as exc:
        results.put(("failed", type(exc).__name__, str(exc)))
    else:
        results.put(("saved", saved.package.display_name, ""))


def test_release_tree_has_one_material_model_and_only_schema_v1_packages() -> None:
    forbidden = (
        "MaterialPackageV3",
        "MaterialPackageV4",
        "MaterialPackageV5",
        "MaterialPackageV6",
        "EntityArchive",
        "EntityProfile",
        "MaterialBatchSelection",
        "MaterialExecutionContext",
        "load_material_package_any",
        "material_package_v6_from_archive",
        "synchronize_material_package_from_archive",
        "official_document_material_package",
        "material_package_sample_selector_options",
        "default_material_profile_id",
        "retry_eligible_profile_ids",
        "failed_batch_profile_ids",
        "src.config.material_snapshot",
        "material-snapshot-v5",
    )
    offenders = {
        token: [
            str(path.relative_to(ROOT))
            for path in (ROOT / "src").rglob("*.py")
            if token in path.read_text(encoding="utf-8")
        ]
        for token in forbidden
    }
    assert not {key: value for key, value in offenders.items() if value}

    package_paths = tuple(
        CANONICAL_MATERIAL_PACKAGE_LIBRARY_DIR.glob("*/builtin/*/package.json")
    )
    assert len(package_paths) == 9
    assert {
        path.relative_to(CANONICAL_MATERIAL_PACKAGE_LIBRARY_DIR).parts[0]
        for path in package_paths
    } == {"custom", "exam", "thesis", "official"}
    for path in package_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["kind"] == "alavette.material_package"
        assert payload["schema_version"] == 1
        assert path.parent.name == payload["package_id"]


def test_only_four_product_modes_are_visible() -> None:
    assert tuple(item.mode_id for item in list_work_modes()) == (
        "custom",
        "exam",
        "thesis",
        "official",
    )
    inactive = {
        item.mode_id: item.status
        for item in list_work_modes(include_inactive=True)
        if item.status != "active"
    }
    assert inactive == {
        "bidding": "hidden",
        "technical": "hidden",
        "report": "hidden",
    }


@pytest.mark.parametrize("mode_id", ("custom", "exam", "thesis", "official"))
def test_each_visible_mode_default_package_strictly_loads_and_binds(
    mode_id: str,
) -> None:
    repository = material_package_repository()
    package_id = DEFAULT_MATERIAL_PACKAGE_IDENTITIES[mode_id]
    entry = next(
        item
        for item in repository.list_entries(work_mode_id=mode_id)
        if item.package_id == package_id
    )
    assert entry.is_available
    package_snapshot = repository.load(
        work_mode_id=mode_id,
        source_type=entry.source_type,
        package_id=package_id,
    )
    selection = MaterialRunSelection(
        package_ref=package_snapshot.ref,
        selected_record_ids=tuple(
            item.record_id for item in package_snapshot.package.records
        ),
    )
    result = bind_repository_material_run(
        repository,
        selection,
        work_mode_id=mode_id,
        recipe_id="document_batch",
    )
    assert result.ok
    assert result.snapshot is not None
    restored = execution_material_snapshot_from_payload(
        result.snapshot.to_payload()
    )
    assert restored == result.snapshot


def test_execution_snapshot_payload_tampering_is_rejected() -> None:
    repository = material_package_repository()
    mode_id = "custom"
    package_id = DEFAULT_MATERIAL_PACKAGE_IDENTITIES[mode_id]
    snapshot = repository.load(
        work_mode_id=mode_id,
        source_type="builtin",
        package_id=package_id,
    )
    bound = bind_repository_material_run(
        repository,
        MaterialRunSelection(
            package_ref=snapshot.ref,
            selected_record_ids=(snapshot.package.records[0].record_id,),
        ),
        work_mode_id=mode_id,
        recipe_id="document_batch",
    ).snapshot
    assert bound is not None
    payload = bound.to_payload()
    payload["package_display_name"] = "被篡改"
    with pytest.raises(
        ValueError,
        match="execution_material_snapshot_digest_mismatch",
    ):
        execution_material_snapshot_from_payload(payload)


def test_execution_snapshot_schema_v1_remains_readable() -> None:
    repository = material_package_repository()
    package_id = DEFAULT_MATERIAL_PACKAGE_IDENTITIES["custom"]
    package = repository.load(
        work_mode_id="custom",
        source_type="builtin",
        package_id=package_id,
    )
    snapshot = bind_repository_material_run(
        repository,
        MaterialRunSelection(
            package_ref=package.ref,
            selected_record_ids=(package.package.records[0].record_id,),
        ),
        work_mode_id="custom",
        recipe_id="document_batch",
    ).snapshot
    assert snapshot is not None
    payload = snapshot.to_payload()
    payload["schema_version"] = 1
    payload.pop("resource_domains")
    payload.pop("content_policy")
    payload.pop("image_policy")
    for record in payload["records"]:
        record.pop("timeline_field_keys")
    payload["snapshot_id"] = ""
    payload["snapshot_id"] = "sha256:" + hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    restored = execution_material_snapshot_from_payload(payload)

    assert restored.schema_version == 1
    assert not restored.resource_domains
    assert restored.records[0].timeline_field_keys == ()


def test_derivation_and_timeline_are_typed_deterministic_and_cycle_safe() -> None:
    contract = MaterialContract(
        contract_id="calculation_v1",
        work_mode_id="custom",
        label="计算资料",
        fields=tuple(
            MaterialFieldContract(
                key=key,
                label=key,
                allowed_scopes=("record",),
            )
            for key in ("first", "last", "full", "start", "deadline")
        ),
    )
    record = MaterialRecord(
        record_id=generate_record_id(),
        display_name="计算记录",
        lifecycle="active",
        scope=MaterialScope(
            fields={
                "first": "张",
                "last": "三",
                "start": "2026-07-31",
            },
            derivations={
                "full": MaterialDerivationSpec(
                    output_field="full",
                    preset_id="join",
                    preset_version=1,
                    input_fields=("first", "last"),
                    parameters={"separator": ""},
                )
            },
            timelines={
                "deadline": MaterialTimelineSpec(
                    output_field="deadline",
                    preset_id="date_offset_days",
                    preset_version=1,
                    anchor_field="start",
                    parameters={"days": "5"},
                )
            },
        ),
    )
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="计算资料包",
        work_mode_id="custom",
        material_contract_id=contract.contract_id,
        records=(record,),
    )
    resolved = MaterialResolver(package, contract).resolve_record(record.record_id)
    assert resolved.ok
    assert resolved.record is not None
    assert resolved.record.field_values["full"] == "张三"
    assert resolved.record.field_values["deadline"] == "2026-08-05"
    assert resolved.record.field_owners["full"] == "derivation:record"

    cyclic_record = MaterialRecord(
        record_id=generate_record_id(),
        display_name="循环记录",
        lifecycle="active",
        scope=MaterialScope(
            derivations={
                "first": MaterialDerivationSpec(
                    output_field="first",
                    preset_id="copy",
                    preset_version=1,
                    input_fields=("last",),
                ),
                "last": MaterialDerivationSpec(
                    output_field="last",
                    preset_id="copy",
                    preset_version=1,
                    input_fields=("first",),
                ),
            }
        ),
    )
    cyclic_package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="循环资料包",
        work_mode_id="custom",
        material_contract_id=contract.contract_id,
        records=(cyclic_record,),
    )
    cyclic = MaterialResolver(cyclic_package, contract).resolve_record(
        cyclic_record.record_id
    )
    assert not cyclic.ok
    assert "material.calculation.cycle" in {
        item.code for item in cyclic.issues
    }


def test_finalize_fails_before_write_on_casefold_output_collision(
    tmp_path: Path,
) -> None:
    repository = material_package_repository()
    package_id = DEFAULT_MATERIAL_PACKAGE_IDENTITIES["custom"]
    package = repository.load(
        work_mode_id="custom",
        source_type="builtin",
        package_id=package_id,
    )
    bound = bind_repository_material_run(
        repository,
        MaterialRunSelection(
            package_ref=package.ref,
            selected_record_ids=(package.package.records[0].record_id,),
        ),
        work_mode_id="custom",
        recipe_id="document_batch",
    ).snapshot
    assert bound is not None
    result = finalize_execution_material_snapshot(
        ExecutionMaterialFinalizeRequest(
            snapshot=bound,
            template_id="template",
            template_revision="sha256:" + "1" * 64,
            master_id="master",
            master_revision="sha256:" + "2" * 64,
            recipe_version=1,
            output_root=str(tmp_path.resolve()),
            output_paths=(
                str((tmp_path / "A.docx").resolve()),
                str((tmp_path / "a.docx").resolve()),
            ),
            supported_field_keys=tuple(bound.records[0].field_values),
        )
    )
    assert not result.ok
    assert "material.bind.output_path_collision" in {
        item.code for item in result.issues
    }
    assert not tuple(tmp_path.iterdir())


def test_repository_two_process_cas_allows_exactly_one_save(
    tmp_path: Path,
) -> None:
    repository = MaterialPackageRepository(tmp_path / "library")
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="并发资料包",
        work_mode_id="custom",
        material_contract_id="generic_document_v1",
        records=(
            MaterialRecord(
                record_id=generate_record_id(),
                display_name="记录",
                lifecycle="active",
            ),
        ),
    )
    created = repository.create_user(package)
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    ready = context.Queue()
    results = context.Queue()
    processes = [
        context.Process(
            target=_concurrent_save_worker,
            args=(
                str(repository.root),
                package.package_id,
                created.ref.revision,
                display_name,
                start,
                ready,
                results,
            ),
        )
        for display_name in ("窗口一", "窗口二")
    ]
    for process in processes:
        process.start()
    assert {ready.get(timeout=20), ready.get(timeout=20)} == {
        "窗口一",
        "窗口二",
    }
    start.set()
    outcomes = [results.get(timeout=20), results.get(timeout=20)]
    for process in processes:
        process.join(20)
        assert process.exitcode == 0
    assert [item[0] for item in outcomes].count("saved") == 1
    assert [item[0] for item in outcomes].count("failed") == 1
    assert any(
        "material_package_revision_conflict" in item[2]
        for item in outcomes
        if item[0] == "failed"
    )


def test_repository_json_publish_failure_preserves_old_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MaterialPackageRepository(tmp_path / "library")
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="旧名称",
        work_mode_id="custom",
        material_contract_id="generic_document_v1",
    )
    created = repository.create_user(package)
    import src.infrastructure.materials.repository as repository_module

    def fail_publish(_path, _payload):
        raise OSError("injected_publish_failure")

    monkeypatch.setattr(repository_module, "_atomic_write", fail_publish)
    with pytest.raises(OSError, match="injected_publish_failure"):
        repository.save_user(
            clone_material_package(package, display_name="不应提交"),
            expected_revision=created.ref.revision,
        )
    loaded = repository.load(
        work_mode_id="custom",
        source_type="user",
        package_id=package.package_id,
    )
    assert loaded.ref.revision == created.ref.revision
    assert loaded.package.display_name == "旧名称"


def test_suite_failure_rolls_back_the_entire_delivery_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "templates" / "Word文档"
    source_root.mkdir(parents=True)
    for name in ("一.docx", "二.docx"):
        document = Document()
        document.add_paragraph("{{title}}")
        document.save(source_root / name)
    contract = MaterialContract(
        contract_id="suite_v1",
        work_mode_id="custom",
        label="成套",
        fields=(
            MaterialFieldContract(
                key="title",
                label="标题",
                required=True,
                allowed_scopes=("record",),
            ),
        ),
    )
    record = MaterialRecord(
        record_id=generate_record_id(),
        display_name="项目",
        lifecycle="active",
        scope=MaterialScope(fields={"title": "项目"}),
    )
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="成套",
        work_mode_id="custom",
        material_contract_id=contract.contract_id,
        records=(record,),
    )
    revision = material_package_revision(package)
    from src.application.materials import MaterialRunBindRequest, bind_material_run

    snapshot = bind_material_run(
        MaterialRunBindRequest(
            package=package,
            package_revision=revision,
            source_type="user",
            selection=MaterialRunSelection(
                package_ref=MaterialPackageRef(
                    package_id=package.package_id,
                    revision=revision,
                ),
                selected_record_ids=(record.record_id,),
            ),
            contract=contract,
            recipe_id="material_suite",
            scene_id="custom",
            work_mode_id="custom",
        ),
        object_path=lambda _ref: "",
    ).snapshot
    assert snapshot is not None
    output = tmp_path / "output"
    plan = compile_material_suite_plan(
        snapshot,
        discover_material_suite_bundle(tmp_path / "templates"),
        output_root=output,
    )
    assert plan.ok
    import src.material_suite.runner as runner_module

    original = runner_module._generate_artifact
    calls = 0

    def fail_second(artifact, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected_failure")
        return original(artifact, target)

    monkeypatch.setattr(runner_module, "_generate_artifact", fail_second)
    result = MaterialSuiteGenerationRunner(plan).run(
        lambda *_args: None,
        lambda: False,
    )
    assert result["status"] == "failed"
    assert result["output_paths"] == {}
    assert not any(path.is_dir() and not path.name.startswith(".") for path in output.iterdir())
