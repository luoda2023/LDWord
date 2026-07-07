# 远程题图缓存删除后的下一步结构优化规划（2026-07-07）

## 当前状态

远程题图缓存链路已经从活跃代码中移除。当前复查结果：

- Workbench 不再下载远程题图，不再创建 `_remote_asset_cache`。
- manifest/package/archive report 不再输出 `remote_asset_cache`。
- adapter 不再透传 `remote_asset_items`。
- 资产面板不再创建共享缓存目录/条目表。
- `src/ui/panels/assets/cache_presenter.py`、`src/ui/panels/assets/question_cache.py`、`src/services/material_assets/cache_projection.py` 已删除。
- 聚焦验证已通过：
  - `132 passed in 535.17s`
  - 追加小回归 `5 passed in 115.67s`

当前源码中仍有少量远程相关字符串，但它们不是活跃远程缓存能力：

- `src/ui/panels/assets/field_editor_state_presenter.py` 中保留旧下载鉴权字段黑名单，用于把历史凭证字段从编辑器剔除。
- `src/services/material_assets/question_library.py` 中 `download_url` / `asset_url` 仍在写入黑名单中，用于防止旧 URL 元数据被写回本地题图库。
- `tests` 中远程缓存字符串主要是反向守门测试。

## 当前结构风险

### 1. Workbench 运行时仍然过大

`src/ui/panels/workbench/execution_runtime.py` 删除远程缓存后仍约 6151 行，职责仍包括：

- 单文档执行。
- 批量执行。
- material preflight。
- 题图本地诊断。
- exam question figure 注入。
- material manifest/package/archive report。
- batch report。
- 题图批量修复队列。
- 题图修复事务、审计、回滚。
- delivery preset 输出。
- threaded execution handle。

这已经不是“一个运行时文件”，而是多个子系统挤在一个模块里。下一步最有价值的结构优化，是把 Workbench material 相关逻辑拆出明确模块。

### 2. Workbench adapter 仍然偏大

`src/ui/adapters/workbench_execution_adapter.py` 约 3275 行，承担大量 issue/item/view-model 投影。远程缓存删除后它已经少了一条分支，但仍需要后续按 issue family 拆分。

不过 adapter 拆分建议放在 Workbench runtime 第一轮拆分之后，因为 adapter 依赖 runtime payload 形态。先稳定产物，再稳定展示。

### 3. 题图库仍有“主版本/远程版本”治理语义

`src/services/material_assets/question_library.py` 约 1141 行，仍包含：

- `master_version`
- `remote_version`
- `remote_etag`
- `remote_updated_at`
- version drift
- master version presenter

这些不是远程缓存，也没有网络下载行为。它们更像“本地题图库多 profile 元数据一致性检查”。是否删除取决于产品取舍：

- 如果题图库只作为本地图片清单，应考虑删除 master version 面板和相关服务。
- 如果需要跨资料包追踪素材版本，它可以保留，但需要重命名成更本地化的“库版本/来源版本”，避免继续暗示远端主数据系统。

本轮不建议马上删除它们。先做边界记录和使用面审查。

### 4. 测试已经更健康，但仍集中

`tests/test_material_execution_context.py` 从远程缓存删除后约 2956 行，仍覆盖多个主题：

- material context。
- Workbench material artifacts。
- exam question figure runtime。
- batch runner。
- question figure repair queue。
- transaction/rollback。

下一步拆 runtime 时，应同步拆测试。否则实现文件拆开了，测试仍是巨型文件，会继续拖慢维护。

## 下一步推荐目标

建议下一步目标定义为：

> 稳定远程缓存删除成果，并把 Workbench material/runtime 逻辑从 `execution_runtime.py` 拆出首批边界模块。

不建议下一步目标定义为：

- 继续做控件统一。
- 直接重构 `scene_panel.py`。
- 继续盲删所有带 `remote` / `master` 字段的题图库逻辑。
- 直接做全量架构大搬迁。

原因：刚刚删除的是 Workbench material 链路的一条大分支，此时继续沿同一上下文做模块拆分，风险最低、收益最大。

## 分阶段执行方案

### 阶段 0：删除成果稳定化

目标：确认删除远程缓存没有留下隐藏分支或输出污染。

操作：

- 运行源码扫描：

```powershell
rg -n "remote_question_asset|remote_asset_cache|remote_asset_download_auth|asset_auth|urlopen|Request\(|remote_asset_items" src\ui\panels\workbench src\ui\adapters src\services\material_assets src\ui\panels\assets -g "*.py"
rg -n "QuestionFigureSharedCache|question_figure_shared_cache|asset_item_shared_cache_dir|asset_item_cache_status|cache_projection|asset_item_remote_asset_id|_asset_item_remote_asset_id" src tests -g "*.py"
```

- 明确允许项：
  - `field_editor_state_presenter.py` 的旧 auth 字段清洗黑名单。
  - `question_library.py` 的 URL 写入黑名单。
  - tests 中的反向守门字符串。

- 运行补充回归：

```powershell
python -m pytest -q tests/test_output_runtime_semantics.py tests/test_workbench_execution_center.py tests/test_execution_diagnostics_reporting.py
```

验收：

- 没有活跃远程下载、缓存、package/report 分支。
- Workbench 执行仍能生成本地题图输出。
- 批量报告不再出现 `remote_asset_items`。

### 阶段 1：抽出 Workbench material preflight 与题图诊断

目标：先从 `execution_runtime.py` 中抽出最靠近刚才删除点、风险最低的一组纯逻辑。

建议新增模块：

- `src/ui/panels/workbench/material_preflight.py`

迁移范围：

- `_material_requirement_diagnostics`
- `_question_figure_file_diagnostics`
- `_question_figure_manual_comparison_issue_diagnostic`
- `_question_figure_filename_mismatch`
- `_question_figure_item_repair_target_key`
- `_missing_asset_rule_diagnostics`
- `_material_context_asset_roles`
- `_material_failure_policy`
- `_material_preflight_error_text`

保留策略：

- `execution_runtime.py` 只 import 公开函数，不再保留同名实现。
- 如果测试还 import 私有函数，优先改测试导入新模块，不在旧文件里留下兼容 re-export。
- 不改变 payload 字段，除非字段是远程缓存残留。

验收：

- `execution_runtime.py` 至少减少 300-500 行。
- preflight/diagnostic 测试仍通过。
- 新模块不依赖 Qt，不依赖 `WorkbenchProductionRunner`。

建议测试：

```powershell
python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_treats_remote_question_figure_url_as_missing_local_file
python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_blocks_missing_required_asset
python -m pytest -q tests/test_material_execution_context.py::test_workbench_batch_runner_reports_missing_question_figure_file_repair_target
```

### 阶段 2：抽出 exam question figure runtime

目标：把“本地题图注入 exam payload”的逻辑从 Workbench 执行器里拿出来。

建议新增模块：

- `src/ui/panels/workbench/exam_question_assets.py`

迁移范围：

- `_material_context_with_exam_question_assets`
- `_material_asset_items`
- `_material_asset_item`
- `_material_asset_path`
- `_coerce_exam_material_payload`
- `_inject_question_figure_path`
- `_inject_question_figure_assets`
- `_append_question_figure_payload`
- `_question_figure_payload_identity`
- `_question_figure_asset_sort_key`
- `_target_question_for_asset`
- `_question_figure_payload_from_asset`
- `_asset_metadata`
- `_asset_render_path`
- `_asset_cached_path`
- `_asset_identity_id`
- `_asset_question_key`
- `_asset_question_index`
- `_asset_figure_order`
- `_question_identity_values`
- `_normalize_question_identity`
- `_asset_title_text`
- `_asset_alt_text`
- `_iter_exam_question_payloads`
- `_question_has_figure_path`

验收：

- `execution_runtime.py` 再减少约 400-600 行。
- 题图注入逻辑仍只处理本地路径/本地 fallback path，不恢复远程下载语义。
- 远程 URL 型题图仍被视为本地缺失。

建议测试：

```powershell
python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_injects_question_figure_asset_into_exam_runtime
python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_maps_multiple_question_figure_assets_by_question_metadata
python -m pytest -q tests/test_exam_question_schema_runtime.py
```

### 阶段 3：抽出 material manifest/package/archive report

目标：把交付产物逻辑从执行器中剥离，避免运行调度和产物打包继续混在一起。

建议新增模块：

- `src/ui/panels/workbench/material_artifacts.py`

迁移范围：

- `_material_manifest_artifact_enabled`
- `_material_package_artifact_enabled`
- `_output_artifact_enabled`
- `_write_material_manifest`
- `_write_material_package_artifacts`
- `_copy_material_package_asset_reference`
- `_material_package_asset_source`
- `_material_package_asset_source_text`
- `_copy_package_path_map`
- `_material_package_asset_subdir`
- `_reset_material_package_dir`
- `_copy_package_reference`
- `_material_package_status`
- `_render_material_archive_report`
- `_write_package_zip`
- `_package_relative_path`
- `_unique_package_path`
- `_safe_package_filename`
- `_material_manifest_should_write`
- `_material_manifest_payload`
- `_material_manifest_field_payload`
- `_material_manifest_asset_role_payload`
- `_material_manifest_asset_item_payload`
- `_material_manifest_asset_archive_dir`
- `_material_manifest_asset_package_subdir`
- `_safe_archive_dir`
- `_material_manifest_asset_kind`
- `_path_map`
- `_unique_manifest_values`
- `_normalize_manifest_key`

注意：

- 这一阶段要继续守住删除成果：package manifest 不得重新出现 `remote_asset_cache`。
- `_material_package_asset_source` 仍应拒绝远程 URL 作为可复制文件。

验收：

- `execution_runtime.py` 再减少约 700-900 行。
- material manifest/package 测试通过。
- archive report 不包含远程缓存章节。

建议测试：

```powershell
python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_writes_material_manifest_for_attachment_inventory
python -m pytest -q tests/test_material_execution_context.py::test_contract_family_signing_copy_writes_material_package_with_missing_seal
python -m pytest -q tests/test_material_execution_context.py::test_contract_family_signing_copy_places_seal_and_packages_manifest
```

### 阶段 4：题图批量修复队列独立成模块

目标：把最大、最重的题图批量修复事务逻辑从执行器里拿出来。

建议新增模块：

- `src/ui/panels/workbench/question_figure_repair_runtime.py`

迁移范围：

- `_batch_question_figure_comparison_matrix`
- `_batch_question_figure_repair_queue`
- `_apply_question_figure_repair_queue_conflict_guard`
- `_question_figure_repair_batch_confirmation_plan`
- `_freeze_question_figure_repair_batch_confirmation_plan`
- `_dry_run_question_figure_repair_batch_apply_guard`
- `_plan_question_figure_repair_batch_apply_execution`
- `_apply_question_figure_repair_batch_execution_to_docx`
- `_question_figure_batch_apply_audit_record`
- `_append_question_figure_batch_apply_audit_record`
- `_read_question_figure_batch_apply_audit_payload`
- `_question_figure_batch_apply_transaction_manifest_from_audit`
- `_write_question_figure_batch_apply_transaction_manifest`
- `_rollback_question_figure_repair_batch_apply_from_audit`
- `_question_figure_batch_apply_rollback_audit_record`
- `_resolve_question_figure_repair_queue_conflict`
- `_refresh_question_figure_repair_queue_status`
- `_question_figure_repair_apply_plan`

验收：

- `execution_runtime.py` 明显下降到更合理的体量。
- 题图批量修复测试可以独立运行。
- 回滚、审计、事务 manifest 语义不变。

建议测试：

```powershell
python -m pytest -q tests/test_material_execution_context.py -k "question_figure_repair or batch_apply or rollback"
```

### 阶段 5：测试拆分

目标：让测试结构跟代码结构同步。

建议拆分：

- `tests/test_workbench_material_preflight.py`
- `tests/test_exam_question_figure_runtime.py`
- `tests/test_material_artifacts.py`
- `tests/test_question_figure_repair_runtime.py`

保留：

- `tests/test_material_execution_context.py` 只保留跨模块集成路径和少量端到端用例。

验收：

- 单个测试文件不再承担过多主题。
- 修改 material artifacts 不必跑完整题图修复事务测试。
- 修改题图修复不必跑 material manifest/package 全部测试。

## 关于 master version / remote version 的处理建议

当前不建议马上删除 `master_version` / `remote_version` 相关能力。

原因：

- 它们没有联网行为，不属于刚删除的远程缓存链路。
- 它们可能仍被本地题图库用作“跨 profile 素材元数据一致性检查”。
- 直接删除会影响 `question_library_master_version_presenter.py`、`question_library.py`、`batch_import.py` 和相关测试，范围会从 Workbench material runtime 跳到资产元数据产品定义。

建议先做一次独立判定：

1. 如果产品不需要“跨资料包题图版本一致性”，则删除 master version 表、服务函数、batch import remote/master version alias。
2. 如果产品需要一致性检查，则重命名为本地语义：
   - `remote_version` -> `library_version`
   - `remote_etag` -> `library_etag`
   - `remote_updated_at` -> `library_updated_at`
   - `master_version` -> `canonical_version`

这个判定应放在 Workbench runtime 首轮拆分之后执行，避免两个高风险方向同时展开。

## 推荐执行顺序

推荐下一次执行只做阶段 0 + 阶段 1：

1. 先跑补充回归和扫描，稳定远程缓存删除成果。
2. 抽出 `material_preflight.py`。
3. 改测试导入和架构守门。
4. 运行聚焦测试。
5. 回填执行记录。

阶段 1 完成后再决定是否继续阶段 2。这样每次变更都有明确边界，且失败时容易回退定位。

## 验收口径

阶段 1 完成后的最低验收：

- `execution_runtime.py` 行数下降。
- `execution_runtime.py` 不再定义 material preflight/题图文件诊断细节函数。
- 新模块不依赖 Qt。
- 远程缓存扫描仍只有允许项。
- 关键测试通过。

建议命令：

```powershell
python -m compileall -q src tests\test_material_execution_context.py tests\test_assets_panel_architecture.py
python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_treats_remote_question_figure_url_as_missing_local_file tests/test_material_execution_context.py::test_workbench_runner_blocks_missing_required_asset tests/test_material_execution_context.py::test_workbench_batch_runner_reports_missing_question_figure_file_repair_target
python -m pytest -q tests/test_assets_panel_architecture.py tests/test_material_asset_services.py
```

## 执行记录

### 2026-07-07 阶段 0 + 阶段 1

已完成：

- 新增 `src/ui/panels/workbench/material_preflight.py`。
- `execution_runtime.py` 不再定义 material preflight / 题图文件诊断细节函数。
- `execution_runtime.py` 改为 import `material_preflight.py` 的纯逻辑函数。
- 新增 `tests/test_workbench_execution_architecture.py` 静态守门，防止 preflight 逻辑回流到运行时大文件。
- `tests/test_execution_diagnostics_reporting.py` 对齐当前架构：
  - 表格布局场景来源走 `scene.template_overrides["table.layout_mode"]`。
  - 样式来源报告使用当前统一文案“格式例外”。

结构结果：

- `execution_runtime.py` 当前约 6215 行。
- `material_preflight.py` 当前约 490 行。
- 新模块不依赖 Qt。
- 远程题图缓存扫描仍只有允许项：
  - `field_editor_state_presenter.py` 旧鉴权字段清洗黑名单。
  - tests 中反向守门字符串。

验证结果：

```powershell
python -m compileall -q src tests\test_material_execution_context.py tests\test_assets_panel_architecture.py tests\test_workbench_execution_architecture.py
# passed

python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_treats_remote_question_figure_url_as_missing_local_file tests/test_material_execution_context.py::test_workbench_runner_blocks_missing_required_asset tests/test_material_execution_context.py::test_workbench_batch_runner_reports_missing_question_figure_file_repair_target
# 3 passed in 79.44s

python -m pytest -q tests/test_assets_panel_architecture.py tests/test_material_asset_services.py tests/test_workbench_execution_architecture.py
# 53 passed in 2.10s

python -m pytest -q tests/test_output_runtime_semantics.py tests/test_workbench_execution_center.py tests/test_execution_diagnostics_reporting.py
# 134 passed in 12.58s

python -m pytest -q tests/test_config_feature_hosting.py
# 6 passed in 0.50s
```

下一步进入阶段 2：抽出 `exam_question_assets.py`，把本地题图注入 exam payload 的逻辑从 Workbench 执行器中移出。

### 2026-07-07 阶段 2

已完成：

- 新增 `src/ui/panels/workbench/exam_question_assets.py`。
- `execution_runtime.py` 不再定义 exam question figure runtime 注入细节函数。
- `execution_runtime.py` 只调用 `material_context_with_exam_question_assets(...)`。
- 删除 `_material_asset_item` / `_material_asset_path` 两个未使用残留 helper。
- 新增 Workbench 执行架构守门，防止 exam 注入逻辑回流到运行时大文件。

结构结果：

- `execution_runtime.py` 当前约 5831 行。
- `exam_question_assets.py` 当前约 383 行。
- 新模块不依赖 Qt。
- 远程 URL 型题图仍由 `looks_like_remote_asset_path(...)` 排除，不恢复远程下载语义。

验证结果：

```powershell
python -m compileall -q src\ui\panels\workbench\exam_question_assets.py src\ui\panels\workbench\execution_runtime.py tests\test_workbench_execution_architecture.py
# passed

python -m pytest -q tests/test_workbench_execution_architecture.py
# 4 passed in 0.52s

python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_injects_question_figure_asset_into_exam_runtime tests/test_material_execution_context.py::test_workbench_runner_maps_multiple_question_figure_assets_by_question_metadata tests/test_exam_question_schema_runtime.py
# 12 passed in 82.70s
```

下一步进入阶段 3：抽出 `material_artifacts.py`，把 material manifest/package/archive report 逻辑从执行器中移出。

### 2026-07-07 阶段 3

已完成：

- 新增 `src/ui/panels/workbench/material_artifacts.py`。
- `execution_runtime.py` 不再定义 material manifest/package/archive report 细节函数。
- `execution_runtime.py` 继续负责运行调度，只 import material artifact 写入函数。
- material artifact 模块保留 `_write_material_manifest` / `_write_material_package_artifacts` 等 surface 名称，兼容现有场景审计。
- 更新审计证据路径：
  - `scene_delivery_preset_execution_audit.py`
  - `scene_material_repair_flow_audit.py`
  - `scene_parameter_ownership.py`
  - `scene_input_source_audit.py`
- 新增 Workbench 执行架构守门，防止 material artifact 逻辑回流到运行时大文件。

结构结果：

- `execution_runtime.py` 当前约 5001 行。
- `material_artifacts.py` 当前约 865 行。
- 新模块不依赖 Qt。
- package 复制逻辑仍通过 `looks_like_remote_asset_path(...)` 拒绝远程 URL，不恢复远程缓存语义。

验证结果：

```powershell
python -m compileall -q src tests\test_workbench_execution_architecture.py
# passed

python -m pytest -q tests/test_workbench_execution_architecture.py
# 5 passed in 0.47s

python -m pytest -q tests/test_material_execution_context.py::test_workbench_runner_writes_material_manifest_for_attachment_inventory tests/test_material_execution_context.py::test_contract_family_signing_copy_writes_material_package_with_missing_seal tests/test_material_execution_context.py::test_contract_family_signing_copy_places_seal_and_packages_manifest
# 3 passed in 115.68s

python -m pytest -q tests/test_scene_input_source_audit.py::test_scene_input_source_audit_baseline_counts
# 1 passed in 0.33s

python -m pytest -q tests/test_scene_delivery_preset_execution_audit.py::test_release_gate_includes_scene_delivery_preset_execution_audit
# 1 passed in 269.29s
```

下一步进入阶段 4：抽出 `question_figure_repair_runtime.py`，把题图批量修复队列、确认计划、执行计划、审计、事务 manifest 和回滚逻辑从执行器中移出。

### 2026-07-07 阶段 4

已完成：

- 新增 `src/ui/panels/workbench/question_figure_repair_runtime.py`。
- `execution_runtime.py` 不再定义题图批量修复队列、冲突裁决、确认计划、dry-run、执行计划、Word media 写入、审计、事务 manifest 和回滚细节函数。
- `execution_runtime.py` 只导入 `_batch_question_figure_comparison_matrix` / `_batch_question_figure_repair_queue` 用于 batch report 拼装。
- `tests/test_material_execution_context.py` 的题图修复事务函数导入改到新模块。
- 新增 Workbench 执行架构守门，防止题图修复运行时逻辑回流。
- 新增专项规划与执行记录：`docs/refactor-records/workbench_question_figure_repair_runtime_phase4_plan_2026-07-07.md`。

结构结果：

- `execution_runtime.py` 当前约 2294 行。
- `question_figure_repair_runtime.py` 当前约 2733 行。
- 新模块不依赖 Qt，也不依赖 `WorkbenchProductionRunner`。
- 题图修复 payload、审计 artifact 和事务 manifest 名称保持兼容。

验证结果：

```powershell
python -m compileall -q src\ui\panels\workbench\question_figure_repair_runtime.py src\ui\panels\workbench\execution_runtime.py tests\test_workbench_execution_architecture.py tests\test_material_execution_context.py
# passed

python -m pytest -q tests/test_workbench_execution_architecture.py
# 6 passed in 0.47s

python -m pytest -q tests/test_material_execution_context.py -k "question_figure_repair or batch_apply or rollback"
# 8 passed, 39 deselected in 39.17s

python -m pytest -q tests/test_workbench_execution_center.py -k "question_figure_repair_queue or batch_apply_transaction"
# 6 passed, 74 deselected in 0.90s

python -m pytest -q tests/test_quick_execution_detail_architecture.py::test_quick_execution_detail_emits_question_figure_repair_candidate_action tests/test_quick_execution_detail_architecture.py::test_quick_execution_detail_emits_transaction_task_summary_action tests/test_quick_execution_detail_architecture.py::test_quick_execution_detail_emits_question_figure_conflict_selection_action
# 3 passed in 0.94s

python -m pytest -q tests/test_recent_run_panel.py -k "question_figure_repair_queue or batch_apply_transaction"
# 1 passed, 21 deselected in 0.69s

python -m pytest -q tests/test_scene_report_artifact_drilldown_audit.py
# 4 passed in 276.39s
```

### 2026-07-07 阶段 5

已完成：

- 新增 `tests/test_question_figure_repair_runtime.py`。
- 从 `tests/test_material_execution_context.py` 迁出 7 个题图修复事务直接单元测试。
- `tests/test_material_execution_context.py` 保留 Workbench material 执行上下文和跨模块集成路径。
- 旧集成测试文件不再直接导入题图修复事务私有函数。

结构结果：

- `tests/test_material_execution_context.py` 当前约 2176 行。
- `tests/test_question_figure_repair_runtime.py` 当前约 1087 行。

验证结果：

```powershell
python -m compileall -q tests\test_material_execution_context.py tests\test_question_figure_repair_runtime.py src\ui\panels\workbench\question_figure_repair_runtime.py src\ui\panels\workbench\execution_runtime.py
# passed

python -m pytest -q tests/test_question_figure_repair_runtime.py
# 7 passed in 0.74s

python -m pytest -q tests/test_material_execution_context.py -k "question_figure_repair or batch_apply or rollback"
# 1 passed, 39 deselected in 37.01s

python -m pytest -q tests/test_material_execution_context.py tests/test_question_figure_repair_runtime.py
# 47 passed in 534.62s

python -m pytest -q tests/test_workbench_execution_architecture.py tests/test_material_asset_services.py::test_material_asset_service_does_not_expose_shared_cache_projection_api tests/test_assets_panel_architecture.py::test_assets_panel_does_not_reintroduce_question_figure_shared_cache_presenter tests/test_assets_panel_helper_modules.py::test_assets_panel_does_not_expose_question_figure_shared_cache_helpers tests/test_assets_panel_question_figures.py
# 12 passed in 0.60s
```

远程缓存删除守门复核：

```powershell
rg -n "remote_question_asset|remote_asset_cache|remote_asset_download_auth|asset_auth|urlopen|Request\(|remote_asset_items" src\ui\panels\workbench src\ui\adapters src\services\material_assets src\ui\panels\assets -g "*.py"
# only field_editor_state_presenter.py legacy auth blacklist entries

rg -n "QuestionFigureSharedCache|question_figure_shared_cache|asset_item_shared_cache_dir|asset_item_cache_status|cache_projection|asset_item_remote_asset_id|_asset_item_remote_asset_id" src tests -g "*.py"
# only negative guard tests
```

至此，本轮“远程题图缓存删除后的 Workbench material/runtime 首轮结构拆分”已完成阶段 0-5。后续若继续优化，应进入新一轮目标：优先评估 `workbench_execution_adapter.py` 的 issue family 拆分，以及题图库 `master_version` / `remote_version` 语义是否重命名为本地库版本语义。
