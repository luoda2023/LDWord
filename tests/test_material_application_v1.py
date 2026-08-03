from __future__ import annotations

from src.application.materials import (
    MaterialPackageService,
    MaterialRunBindRequest,
    bind_material_run,
    bind_repository_material_run,
    default_material_contract_id,
    get_package_material_contract,
    project_material_preview,
)
from src.domain.materials import (
    MaterialContract,
    MaterialFieldContract,
    MaterialObjectRef,
    MaterialPackage,
    MaterialPackageRef,
    MaterialRecord,
    MaterialResolver,
    MaterialResourceBinding,
    MaterialRunSelection,
    MaterialScope,
    MaterialTimelineSpec,
    clone_material_package,
    generate_package_id,
    generate_record_id,
)
from src.infrastructure.materials.codec import material_package_revision
from src.infrastructure.materials.repository import MaterialPackageRepository


def _contract() -> MaterialContract:
    return MaterialContract(
        contract_id="official_document_v1",
        work_mode_id="official",
        label="公文",
        fields=(
            MaterialFieldContract(
                key="title",
                label="标题",
                required=True,
                allowed_scopes=("record", "run"),
                allow_run_override=True,
            ),
            MaterialFieldContract(
                key="document_type",
                label="文种",
                allowed_scopes=("record",),
            ),
        ),
    )


def _package() -> MaterialPackage:
    return MaterialPackage(
        package_id=generate_package_id(),
        display_name="公文资料",
        work_mode_id="official",
        material_contract_id="official_document_v1",
        records=(
            MaterialRecord(
                record_id=generate_record_id(),
                display_name="通知",
                lifecycle="active",
                scope=MaterialScope(
                    fields={
                        "title": "关于测试的通知",
                        "document_type": "notice",
                    }
                ),
            ),
        ),
    )


def test_commands_target_stable_ids_and_preserve_explicit_empty(tmp_path) -> None:
    package = _package()
    service = MaterialPackageService(MaterialPackageRepository(tmp_path))
    record_id = package.records[0].record_id

    renamed = service.rename_record(
        package,
        record_id=record_id,
        display_name="新显示名",
    )
    assert renamed.ok
    assert renamed.package is not None
    assert renamed.package.records[0].record_id == record_id

    cleared = service.set_field(
        renamed.package,
        owner_scope="record",
        owner_id=record_id,
        key="title",
        value="",
    )
    assert cleared.ok
    assert cleared.package is not None
    assert "title" in cleared.package.records[0].scope.fields
    assert cleared.package.records[0].scope.fields["title"] == ""


def test_package_owned_dynamic_contract_survives_save_and_resolution(
    tmp_path,
) -> None:
    repository = MaterialPackageRepository(
        tmp_path,
        contract_provider=get_package_material_contract,
    )
    record_id = generate_record_id()
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="动态资料",
        work_mode_id="custom",
        material_contract_id=default_material_contract_id("custom"),
        records=(
            MaterialRecord(
                record_id=record_id,
                display_name="第一份",
                lifecycle="active",
            ),
        ),
    )
    created = repository.create_user(package)
    service = MaterialPackageService(repository)
    with_field = service.add_field_definition(
        created.package,
        key="客户名称",
        label="客户名称",
    )
    assert with_field.ok and with_field.package is not None
    with_role = service.add_resource_role_definition(
        with_field.package,
        role="文件1",
        label="文件1",
        domain="content",
    )
    assert with_role.ok and with_role.package is not None
    with_value = service.set_field(
        with_role.package,
        owner_scope="record",
        owner_id=record_id,
        key="客户名称",
        value="甲方单位",
    )
    assert with_value.ok and with_value.package is not None

    saved = service.save(
        with_value.package,
        expected_revision=created.ref.revision,
    )

    assert saved.ok and saved.snapshot is not None
    reloaded = repository.load(
        work_mode_id="custom",
        source_type="user",
        package_id=package.package_id,
    )
    contract = get_package_material_contract(reloaded.package)
    assert contract.get_field("客户名称") is not None
    assert contract.get_resource_role("文件1").domain == "content"
    resolution = MaterialResolver(
        reloaded.package,
        contract,
    ).resolve_record(record_id)
    assert resolution.record is not None
    assert resolution.record.field_values["客户名称"] == "甲方单位"


def test_dynamic_file_role_reaches_exact_v1_execution_snapshot(
    tmp_path,
) -> None:
    repository = MaterialPackageRepository(
        tmp_path,
        contract_provider=get_package_material_contract,
    )
    record_id = generate_record_id()
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="动态文件执行",
        work_mode_id="custom",
        material_contract_id=default_material_contract_id("custom"),
        records=(
            MaterialRecord(
                record_id=record_id,
                display_name="第一份",
                lifecycle="active",
            ),
        ),
    )
    created = repository.create_user(package)
    service = MaterialPackageService(repository)
    current = service.add_resource_role_definition(
        created.package,
        role="文件1",
        label="文件1",
        domain="content",
    ).package
    assert current is not None
    for field_key in ("项目开始", "项目结束", "中间节点"):
        extended = service.add_field_definition(
            current,
            key=field_key,
            label=field_key,
        )
        assert extended.ok and extended.package is not None
        current = extended.package
    for field in get_package_material_contract(current).fields:
        if not field.required:
            continue
        updated = service.set_field(
            current,
            owner_scope="record",
            owner_id=record_id,
            key=field.key,
            value=f"{field.label}值",
        )
        assert updated.ok and updated.package is not None
        current = updated.package
    for field_key, value in (
        ("项目开始", "2026-08-01"),
        ("项目结束", "2026-08-11"),
    ):
        updated = service.set_field(
            current,
            owner_scope="record",
            owner_id=record_id,
            key=field_key,
            value=value,
        )
        assert updated.ok and updated.package is not None
        current = updated.package
    timed = service.set_timeline(
        current,
        owner_scope="record",
        owner_id=record_id,
        key="中间节点",
        specification=MaterialTimelineSpec(
            output_field="中间节点",
            preset_id="timeline_ratio",
            preset_version=1,
            anchor_field="项目开始",
            parameters={
                "end_field": "项目结束",
                "ratio": "0.5",
                "weekend_adjust": "none",
                "output_format": "yyyy-MM-dd",
                "segment_id": "segment_1",
                "node_index": "2",
                "node_count": "3",
                "input_scope": "fixed",
            },
        ),
    )
    assert timed.ok and timed.package is not None
    current = timed.package
    source = tmp_path / "dynamic-source.docx"
    source.write_bytes(b"dynamic content")
    object_ref = repository.import_object(
        work_mode_id="custom",
        package_id=package.package_id,
        source_path=source,
    )
    bound = service.bind_resource(
        current,
        owner_scope="record",
        owner_id=record_id,
        binding=MaterialResourceBinding(
            role="文件1",
            items=(object_ref,),
        ),
    )
    assert bound.ok and bound.package is not None
    saved = service.save(
        bound.package,
        expected_revision=created.ref.revision,
    )
    assert saved.ok and saved.snapshot is not None
    selection = MaterialRunSelection(
        package_ref=saved.snapshot.ref,
        selected_record_ids=(record_id,),
    )

    execution = bind_repository_material_run(
        repository,
        selection,
        work_mode_id="custom",
        recipe_id="document_batch",
    )

    assert execution.ok and execution.snapshot is not None
    resources = execution.snapshot.records[0].resources["文件1"]
    assert len(resources) == 1
    assert resources[0].object_ref.object_id == object_ref.object_id
    assert resources[0].source_path.endswith(object_ref.object_id.split(":")[1])
    assert execution.snapshot.records[0].field_values["中间节点"] == "2026-08-06"
    assert execution.snapshot.schema_version == 3
    assert execution.snapshot.resource_domains["文件1"] == "content"
    assert execution.snapshot.content_policy == {
        "format_mode": "target_document",
        "page_break_policy": "drop",
    }
    assert execution.snapshot.records[0].timeline_field_keys == (
        "中间节点",
        "项目开始",
        "项目结束",
    )


def test_dynamic_definition_rename_and_remove_migrate_every_v1_scope(
    tmp_path,
) -> None:
    repository = MaterialPackageRepository(
        tmp_path,
        contract_provider=get_package_material_contract,
    )
    record_id = generate_record_id()
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="动态定义迁移",
        work_mode_id="custom",
        material_contract_id=default_material_contract_id("custom"),
        records=(
            MaterialRecord(
                record_id=record_id,
                display_name="第一份",
                lifecycle="active",
            ),
        ),
    )
    created = repository.create_user(package)
    service = MaterialPackageService(repository)
    with_field = service.add_field_definition(
        created.package,
        key="旧字段",
        label="旧字段",
    ).package
    assert with_field is not None
    with_role = service.add_resource_role_definition(
        with_field,
        role="旧文件",
        label="旧文件",
        domain="content",
    ).package
    assert with_role is not None
    with_shared_value = service.set_field(
        with_role,
        owner_scope="shared",
        owner_id="",
        key="旧字段",
        value="共享值",
    ).package
    assert with_shared_value is not None
    with_record_value = service.set_field(
        with_shared_value,
        owner_scope="record",
        owner_id=record_id,
        key="旧字段",
        value="记录值",
    ).package
    assert with_record_value is not None
    object_ref = MaterialObjectRef(
        object_id=f"sha256:{'0' * 64}",
        media_type="application/octet-stream",
        original_name="dynamic.bin",
        size=1,
    )
    with_shared_resource = service.bind_resource(
        with_record_value,
        owner_scope="shared",
        owner_id="",
        binding=MaterialResourceBinding(
            role="旧文件",
            items=(object_ref,),
        ),
    ).package
    assert with_shared_resource is not None
    with_record_resource = service.bind_resource(
        with_shared_resource,
        owner_scope="record",
        owner_id=record_id,
        binding=MaterialResourceBinding(
            role="旧文件",
            items=(object_ref,),
        ),
    ).package
    assert with_record_resource is not None

    renamed_field = service.rename_field_definition(
        with_record_resource,
        current_key="旧字段",
        key="新字段",
        label="新字段",
    ).package
    assert renamed_field is not None
    renamed_role = service.rename_resource_role_definition(
        renamed_field,
        current_role="旧文件",
        role="新文件",
        label="新文件",
    ).package
    assert renamed_role is not None
    assert renamed_role.shared_scope.fields["新字段"] == "共享值"
    assert renamed_role.records[0].scope.fields["新字段"] == "记录值"
    assert renamed_role.shared_scope.resources["新文件"].role == "新文件"
    assert renamed_role.records[0].scope.resources["新文件"].role == "新文件"
    assert get_package_material_contract(renamed_role).get_field("新字段")
    assert get_package_material_contract(renamed_role).get_resource_role(
        "新文件"
    )

    without_field = service.remove_field_definition(
        renamed_role,
        key="新字段",
    ).package
    assert without_field is not None
    without_role = service.remove_resource_role_definition(
        without_field,
        role="新文件",
    ).package
    assert without_role is not None
    assert "新字段" not in without_role.shared_scope.fields
    assert "新字段" not in without_role.records[0].scope.fields
    assert "新文件" not in without_role.shared_scope.resources
    assert "新文件" not in without_role.records[0].scope.resources
    assert get_package_material_contract(without_role).get_field(
        "新字段"
    ) is None
    assert get_package_material_contract(without_role).get_resource_role(
        "新文件"
    ) is None


def test_image_policy_is_package_owned_and_survives_v1_save(
    tmp_path,
) -> None:
    repository = MaterialPackageRepository(
        tmp_path,
        contract_provider=get_package_material_contract,
    )
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="图片规则",
        work_mode_id="custom",
        material_contract_id=default_material_contract_id("custom"),
        records=(
            MaterialRecord(
                record_id=generate_record_id(),
                display_name="第一份",
                lifecycle="active",
            ),
        ),
    )
    created = repository.create_user(package)
    service = MaterialPackageService(repository)
    updated = service.set_image_policy(
        created.package,
        adaptive=False,
        watermark_enabled=True,
        watermark_source="fixed",
        watermark_text="内部资料",
        watermark_font="黑体",
        show_single_image_name=True,
        show_multi_image_name=False,
        page_break_after_images=True,
    )
    assert updated.ok and updated.package is not None
    saved = service.save(
        updated.package,
        expected_revision=created.ref.revision,
    )
    assert saved.ok and saved.snapshot is not None

    reloaded = repository.load(
        work_mode_id="custom",
        source_type="user",
        package_id=package.package_id,
    )
    policy = reloaded.package.metadata[
        "material_contract_extensions"
    ]["image_policy"]
    assert dict(policy) == {
        "adaptive": False,
        "watermark_enabled": True,
        "watermark_source": "fixed",
        "watermark_text": "内部资料",
        "watermark_font": "黑体",
        "show_single_image_name": True,
        "show_multi_image_name": False,
        "page_break_after_images": True,
    }


def test_folder_authoring_source_survives_v1_save_without_changing_resources(
    tmp_path,
) -> None:
    repository = MaterialPackageRepository(
        tmp_path,
        contract_provider=get_package_material_contract,
    )
    created = repository.create_user(_package())
    service = MaterialPackageService(repository)
    source_path = str(tmp_path / "原始多图文件夹")

    updated = service.set_resource_authoring_source(
        created.package,
        owner_scope="record",
        owner_id=created.package.records[0].record_id,
        role="多图文件夹1",
        source_path=source_path,
    )

    assert updated.ok and updated.package is not None
    assert updated.package.records[0].scope.resources == created.package.records[0].scope.resources
    saved = service.save(
        updated.package,
        expected_revision=created.ref.revision,
    )
    assert saved.ok and saved.snapshot is not None
    reloaded = repository.load(
        work_mode_id=created.package.work_mode_id,
        source_type="user",
        package_id=created.package.package_id,
    )
    assert reloaded.package.metadata["material_resource_authoring_sources"] == {
        "多图文件夹1": {
            f"record:{created.package.records[0].record_id}": source_path,
        }
    }


def test_legacy_image_name_policy_freezes_both_independent_switches() -> None:
    package = clone_material_package(
        _package(),
        metadata={
            "material_contract_extensions": {
                "image_policy": {"show_image_name": True}
            }
        },
    )
    revision = material_package_revision(package)
    bound = bind_material_run(
        MaterialRunBindRequest(
            package=package,
            package_revision=revision,
            source_type="user",
            selection=MaterialRunSelection(
                package_ref=MaterialPackageRef(package.package_id, revision),
                selected_record_ids=(package.records[0].record_id,),
            ),
            contract=_contract(),
            recipe_id="document_batch",
            scene_id="official",
            work_mode_id="official",
        ),
        object_path=lambda _item: "",
    )

    assert bound.ok and bound.snapshot is not None
    assert bound.snapshot.image_policy["show_single_image_name"] is True
    assert bound.snapshot.image_policy["show_multi_image_name"] is True


def test_v1_timeline_ratio_supports_weekend_and_output_format() -> None:
    contract = MaterialContract(
        contract_id="timeline_ratio_v1",
        work_mode_id="custom",
        label="时间段",
        fields=(
            MaterialFieldContract(key="start", label="开始"),
            MaterialFieldContract(key="end", label="结束"),
            MaterialFieldContract(key="node", label="节点"),
        ),
    )
    record_id = generate_record_id()
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="比例时间段",
        work_mode_id="custom",
        material_contract_id=contract.contract_id,
        records=(
            MaterialRecord(
                record_id=record_id,
                display_name="第一份",
                lifecycle="active",
                scope=MaterialScope(
                    fields={
                        "start": "2026-08-01",
                        "end": "2026-08-09",
                    },
                    timelines={
                        "node": MaterialTimelineSpec(
                            output_field="node",
                            preset_id="timeline_ratio",
                            preset_version=1,
                            anchor_field="start",
                            parameters={
                                "end_field": "end",
                                "ratio": "1",
                                "weekend_adjust": "forward",
                                "output_format": "yyyy年MM月dd日",
                                "segment_id": "segment_1",
                                "node_index": "1",
                                "node_count": "1",
                                "input_scope": "fixed",
                            },
                        )
                    },
                ),
            ),
        ),
    )

    resolution = MaterialResolver(package, contract).resolve_record(record_id)

    assert resolution.ok
    assert resolution.record is not None
    assert resolution.record.field_values["node"] == "2026年08月10日"


def test_preview_is_a_projection_of_package_and_contract() -> None:
    package = _package()
    revision = material_package_revision(package)

    preview = project_material_preview(
        package,
        revision=revision,
        source_type="builtin",
        contract=_contract(),
    )

    assert preview.package_id == package.package_id
    assert preview.package_revision == revision
    assert preview.current_record_id == package.records[0].record_id
    assert preview.filled_required_field_count == 1


def test_floating_timeline_and_watermark_values_flow_into_run_snapshot() -> None:
    contract = MaterialContract(
        contract_id="floating_runtime_v1",
        work_mode_id="custom",
        label="运行时字段",
        fields=tuple(
            MaterialFieldContract(
                key=key,
                label=label,
                allowed_scopes=("record", "run"),
                allow_run_override=True,
            )
            for key, label in (
                ("start", "开始日期"),
                ("end", "结束日期"),
                ("node", "中间节点"),
            )
        ),
    )
    record = MaterialRecord(
        record_id=generate_record_id(),
        display_name="运行记录",
        lifecycle="active",
        scope=MaterialScope(
            timelines={
                "node": MaterialTimelineSpec(
                    output_field="node",
                    preset_id="timeline_ratio",
                    preset_version=1,
                    anchor_field="start",
                    parameters={
                        "end_field": "end",
                        "ratio": "0.5",
                        "weekend_adjust": "none",
                        "output_format": "yyyy-MM-dd",
                        "segment_id": "segment_1",
                        "node_index": "1",
                        "node_count": "1",
                        "input_scope": "floating",
                    },
                )
            }
        ),
    )
    package = MaterialPackage(
        package_id=generate_package_id(),
        display_name="运行时资料",
        work_mode_id="custom",
        material_contract_id=contract.contract_id,
        records=(record,),
        metadata={
            "material_contract_extensions": {
                "fields": [],
                "resource_roles": [],
                "image_policy": {
                    "adaptive": True,
                    "watermark_enabled": True,
                    "watermark_source": "free",
                    "watermark_text": "",
                    "show_single_image_name": True,
                    "show_multi_image_name": False,
                },
            }
        },
    )
    revision = material_package_revision(package)

    preview = project_material_preview(
        package,
        revision=revision,
        source_type="user",
        contract=contract,
    )

    assert [item.key for item in preview.runtime_fields] == [
        "start",
        "end",
        "__image_watermark_text__",
    ]
    assert all(item.editor_kind == "date" for item in preview.runtime_fields[:2])

    selection = MaterialRunSelection(
        package_ref=MaterialPackageRef(package.package_id, revision),
        selected_record_ids=(record.record_id,),
        runtime_field_overrides={
            "start": "2026-08-01",
            "end": "2026-08-09",
        },
        runtime_image_watermark_text="仅限内部",
    )
    bound = bind_material_run(
        MaterialRunBindRequest(
            package=package,
            package_revision=revision,
            source_type="user",
            selection=selection,
            contract=contract,
            recipe_id="document_batch",
            scene_id="custom",
            work_mode_id="custom",
        ),
        object_path=lambda _item: "",
    )

    assert bound.ok and bound.snapshot is not None
    assert bound.snapshot.records[0].field_values["node"] == "2026-08-05"
    assert bound.snapshot.image_policy["runtime_watermark_text"] == "仅限内部"
    assert bound.snapshot.image_policy["watermark_font"] == "宋体"
    assert bound.snapshot.image_policy["show_single_image_name"] is True
    assert bound.snapshot.image_policy["show_multi_image_name"] is False


def test_binder_freezes_one_identity_and_rejects_document_type_conflict() -> None:
    package = _package()
    revision = material_package_revision(package)
    selection = MaterialRunSelection(
        package_ref=MaterialPackageRef(
            package_id=package.package_id,
            revision=revision,
        ),
        selected_record_ids=(package.records[0].record_id,),
    )
    request = MaterialRunBindRequest(
        package=package,
        package_revision=revision,
        source_type="builtin",
        selection=selection,
        contract=_contract(),
        recipe_id="document_batch",
        scene_id="official",
        work_mode_id="official",
        document_type="letter",
    )

    result = bind_material_run(request, object_path=lambda _item: "")

    assert not result.ok
    assert result.snapshot is None
    assert "material.bind.document_type_mismatch" in {
        item.code for item in result.issues
    }


def test_binder_requires_explicit_nonempty_selection() -> None:
    package = _package()
    revision = material_package_revision(package)
    selection = MaterialRunSelection(
        package_ref=MaterialPackageRef(
            package_id=package.package_id,
            revision=revision,
        ),
        selected_record_ids=(),
    )

    result = bind_material_run(
        MaterialRunBindRequest(
            package=package,
            package_revision=revision,
            source_type="builtin",
            selection=selection,
            contract=_contract(),
            recipe_id="document_batch",
            scene_id="official",
            work_mode_id="official",
        ),
        object_path=lambda _item: "",
    )

    assert not result.ok
    assert {item.code for item in result.issues} == {
        "material.bind.selection_empty"
    }
