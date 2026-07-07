# AssetsPanel 第五步拆分规划

日期：2026-07-06

## 背景

第四步已经把 `AssetsPanel` 中低耦合的规格常量、字段解析、远程鉴权、素材 item 归一化、角色解析、批量导入 helper 拆到 `src/ui/panels/assets/` 包下，并保留 `src.ui.panels.assets_panel._xxx` 兼容导入。

当前 `src/ui/panels/assets_panel.py` 仍约 68920 行。剩余体量主要来自题图素材库、远程写回、共享缓存、治理记录、订阅漂移恢复、Word 媒体修复、审计记录等业务流程函数。这些函数大多不是 Qt UI 控件逻辑，而是业务状态投影、记录生成、远端交互 payload、文件修复和审计证据生成，适合继续从面板文件中下沉。

## 第五步目标

第五步不追求一次性拆完 `AssetsPanel`，而是建立题图/远程素材子域的稳定模块边界：

1. 将题图素材的元数据、排序、标签、匹配、预览引用等纯 helper 下沉。
2. 将共享缓存行数据、指标、清理确认、缓存状态 helper 下沉。
3. 只在边界清晰时迁移远程写回的纯 payload/record helper，暂不优先移动实际网络 connector。
4. 保留 `assets_panel.py` 的模块级兼容导入，避免旧测试或内部引用断裂。
5. 为每个新模块补定向测试，再跑工程门禁。

## 当前函数群职责地图

基于当前 `assets_panel.py` 的顶层函数扫描，重点函数群大致如下。数量有重叠，仅用于判断规模和拆分优先级。

| 函数群 | 规模 | 主要职责 | 第五步建议 |
| --- | ---: | --- | --- |
| `_question_figure_*` 基础 helper | 约 39 个 | 题图素材筛选、标签、排序、比较选项、修复目标匹配、列表行投影 | 第一批迁移 |
| 题图素材库/治理 row helper | 约 19 个 | 素材库表格行、治理 issue、批量治理、主版本/注册表/订阅锁记录投影 | 第二批迁移 |
| `subscription_drift` | 约 227 个 | 主数据订阅漂移队列、分诊、审批、决策、执行、失败队列、恢复报告、SLA、后台任务、Word 媒体修复 | 第五步只做边界规划，少量低风险 helper 可迁 |
| `remote_writeback` | 约 173 个 | 企业鉴权、外部权限、签名 URL 刷新、批量写回计划/执行/报告、回滚、二次补偿、冲突处理、单项 connector payload | 第五步先抽纯 payload/record，connector 暂缓 |
| `shared_cache` | 约 26 个 | 共享缓存目录/条目/索引/指标/命中率/清理任务/确认状态/失效提示 | 第一或第二批迁移 |
| `audit` | 约 21 个 | 修复审计、回滚审计、最终闭环审计的 ID、目录、读写、证据 payload | 第二批迁移 |
| `metadata_history` | 约 8 个 | 元数据历史、版本历史、回滚记录、字段变更摘要 | 可和题图元数据 helper 同批 |
| `non_question_asset_family` | 约 245 个 | 非题图素材族的跨归档恢复、Word XML/header/footer 改写、远端冲突裁决、补偿、终态归档 | 第五步不主动迁移，另开第六步/第七步 |

## 建议模块结构

第五步建议新增这些模块：

```text
src/ui/panels/assets/
  question_figures.py        # 题图 item、metadata、label、排序、匹配、比较选项
  question_cache.py          # 共享缓存 row、指标、清理确认、缓存状态
  question_audit.py          # 修复审计、回滚审计、审计文件读写
  remote_writeback.py        # 远程写回纯 payload/record/status helper
```

暂不建议把所有 `remote_writeback` connector 和 `subscription_drift` 恢复流程一口气迁移。它们依赖 `urlopen`、文件系统、profile metadata、历史记录、批量事务状态、Word 媒体修复输出，风险比基础 helper 高。

## 执行顺序

### 1. 题图基础 helper 下沉

优先迁移这些纯函数：

- `_question_figure_collection_summary`
- `_question_figure_item_summary`
- `_question_figure_target_label`
- `_question_figure_payload_matches_item`
- `_question_figure_repair_target_payload`
- `_question_figure_item_matches_repair_target`
- `_question_figure_target_cache_path`
- `_question_figure_target_value`
- `_question_figure_asset_items`
- `_question_figure_compare_options`
- `_question_figure_compare_index_label`
- `_question_figure_compare_display_name`
- `_question_figure_asset_sort_key`
- `_question_figure_order_value`
- `_asset_item_remote_asset_id`
- `_asset_item_source`
- `_asset_item_cached_path`
- `_asset_item_remote_full_preview_url`
- `_asset_item_remote_thumbnail_preview_url`
- `_asset_item_remote_preview_url`
- `_asset_item_remote_compare_preview_url`
- `_asset_item_remote_preview_kind`
- `_asset_item_preview_reference`
- `_asset_item_thumbnail_path`
- `_asset_item_preview_path`
- `_asset_item_alt_text`

目标模块：`src/ui/panels/assets/question_figures.py`

迁移后在 `assets_panel.py` 顶部继续导入这些函数，保持原模块命名空间不变。

### 2. 共享缓存 helper 下沉

迁移这些缓存状态/表格投影函数：

- `_question_figure_shared_cache_dir_rows`
- `_question_figure_shared_cache_entry_rows`
- `_question_figure_shared_cache_index_entry_rows`
- `_question_figure_shared_cache_entry_row_from_item`
- `_question_figure_shared_cache_entry_identity`
- `_question_figure_shared_cache_entry_sort_key`
- `_question_figure_shared_cache_metrics_rows`
- `_question_figure_shared_cache_hit_rate_trend_rows`
- `_question_figure_shared_cache_hit_rate_trend_row`
- `_question_figure_shared_cache_hit_rate_trend_label`
- `_question_figure_shared_cache_cleanup_task_rows`
- `_question_figure_shared_cache_profile_dir_scopes`
- `_question_figure_shared_cache_cleanup_task_row`
- `_question_figure_shared_cache_cleanup_task_confirmation_label`
- `_question_figure_shared_cache_cleanup_rows`
- `_question_figure_shared_cache_cleanup_confirmation_state`
- `_latest_question_figure_shared_cache_cleanup_record`
- `_question_figure_shared_cache_cleanup_confirmed`
- `_append_question_figure_shared_cache_cleanup_confirmation`
- `_read_question_figure_shared_cache_cleanup_confirmation_payload`
- `_question_figure_cache_question_label`
- `_question_figure_shared_cache_index_source`
- `_question_figure_context_cache_source`
- `_question_figure_cache_invalidation_text`
- `_asset_item_shared_cache_dir`
- `_asset_item_cache_status`

目标模块：`src/ui/panels/assets/question_cache.py`

其中读写确认记录的函数涉及文件系统，应测试临时目录和异常 fallback。

### 3. 审计 helper 下沉

迁移题图修复审计相关函数：

- `_question_figure_repair_audit_record`
- `_question_figure_repair_rollback_audit_record`
- `_question_figure_repair_audit_dir`
- `_append_question_figure_repair_audit_record`
- `_read_question_figure_repair_audit_payload`
- `_question_figure_repair_audit_id`
- `_question_figure_repair_rollback_audit_id`

目标模块：`src/ui/panels/assets/question_audit.py`

这部分职责是形成“修复前后、候选、目标、动作、回滚依据”的证据记录。它是业务审计，不应继续和 Qt 面板放在一起。

### 4. 远程写回先抽纯 helper

只迁移不发网络请求、不直接写文件的函数：

- 状态/文案：`_question_figure_remote_writeback_batch_status_category`、`_question_figure_remote_writeback_batch_status_summary`、`_question_figure_remote_writeback_batch_next_step`
- payload/idempotency：`_question_figure_remote_writeback_payload`、`_question_figure_remote_writeback_overwrite_payload`、`_question_figure_remote_writeback_field_merge_payload`、`_question_figure_remote_writeback_idempotency_key`
- endpoint/匹配：`_question_figure_remote_writeback_endpoint`、`_question_figure_remote_current_endpoint`、`_question_figure_remote_writeback_record_matches_source`
- 元数据合并：`_question_figure_remote_writeback_merge_field_sources`、`_question_figure_remote_writeback_merged_metadata`、`_question_figure_remote_writeback_merge_sources_label`
- 历史/摘要：`_question_figure_history_record_key`、`_question_figure_history_changed_fields`、`_question_figure_history_record_matches_current`、`_question_figure_library_metadata_change_summary`

目标模块：`src/ui/panels/assets/remote_writeback.py`

暂缓迁移：

- `_fetch_*`
- `_execute_*connector`
- manifest 文件写入
- rollback connector
- second compensation connector

这些函数涉及网络、文件或事务副作用，等纯 helper 稳住后再拆。

## 测试计划

新增测试：

```text
tests/test_assets_panel_question_figures.py
tests/test_assets_panel_question_cache.py
tests/test_assets_panel_question_audit.py
tests/test_assets_panel_remote_writeback_helpers.py
```

覆盖重点：

1. helper 经 `src.ui.panels.assets_panel` 兼容暴露。
2. 题图 item 筛选、排序、label、preview reference 的 fallback。
3. 缓存状态、缓存行 identity、清理确认状态。
4. 审计 ID 稳定性、append/read JSON payload。
5. 远程写回 payload、idempotency key、endpoint 选择、metadata merge。
6. 空 metadata、缺字段、未知状态时必须安全 fallback。

## 验收标准

第五步完成时满足：

1. `assets_panel.py` 再减少约 1000-2000 行。
2. 新增 2-4 个 helper 模块，且模块之间没有反向 import `assets_panel.py`。
3. 原 `assets_panel.py` 模块级 helper 名字继续可用。
4. 新增定向测试通过。
5. `python scripts\engineering_gate.py` 通过。
6. `tests/test_assets_panel_architecture.py` 相关定向测试通过。

## 风险控制

1. 不移动 Qt widget 构造、信号绑定、toast/dialog 展示逻辑。
2. 不移动网络 connector，除非先补 mock 测试。
3. 不合并题图和非题图素材族，二者流程相似但命名和业务状态已经分叉。
4. 不做行为改名，只做边界迁移。
5. 每一批迁移后立即跑 py_compile、定向测试和 engineering gate。

## 下一刀建议

第五步第一刀建议执行 `question_figures.py`：

1. 迁移题图 item/metadata/preview/排序相关 helper。
2. 在 `assets_panel.py` 顶部导入，保持兼容命名。
3. 新增 `tests/test_assets_panel_question_figures.py`。
4. 跑 `py_compile`、helper 测试、`AssetsPanel` 架构测试、engineering gate。

这是收益最高、风险最低的入口；缓存、审计、远程写回可以作为第五步后续小批次推进。

## 补充复盘：远程写回、缓存、治理是否应作为主线

这次复盘后需要调整第五步的默认判断：远程写回、共享缓存治理、订阅漂移、主数据治理并不是本地格式化工具的天然主线能力。它们更像后期为了“企业级考试题目图片素材库/主数据中心”场景连续扩展出来的能力。

### 设计来源判断

从现有文档和代码命名看，这批能力大概率是在 2026-06-21 到 2026-06-23 左右的 `高层场景能力矩阵N2_277...N2_3xx` 文档中连续设计并落入 `AssetsPanel` 的：

- `N2_277` 到 `N2_282`：题目图片素材库索引、metadata 编辑、治理问题、版本历史、版本回滚。
- `N2_283` 到 `N2_291`：题目图片素材库远端写回、执行 Connector、幂等重试、冲突处理。
- `N2_292` 到 `N2_311`：批量事务、失败队列、事务报告、批量回滚、二次补偿、企业鉴权、签名 URL、外部权限。
- `N2_312` 到 `N2_336`：跨包主数据版本、注册表同步、订阅锁、订阅漂移、失败恢复、Word 媒体修复。
- `N2_337` 之后：非题图素材族也被纳入类似的跨归档恢复和远端冲突闭环。

因此它不是项目初始核心功能，而是后期叠加的企业素材库治理功能。

### 为什么会需要远程

远程能力只有在一种业务前提下成立：项目背后存在一个中心化素材库或主数据系统。

这种场景下，很多模板、很多试卷、很多操作者共用同一批题图素材；题图不仅是本地文件，还带有 `asset_id`、版本、etag、远程下载地址、预览地址、写回地址、当前快照地址、鉴权信息等 metadata。本地修复题图或调整 metadata 后，可能需要同步回中心系统，保证其他人后续拿到的是同一份修正后的素材。

但当前代码没有内置明确后端服务，而是依赖 profile/asset metadata 中携带的 `writeback_url`、`current_url`、`refresh_url`、鉴权 payload 等字段。换句话说：如果没有外部素材库系统配合，这套能力不会自然产生价值。

### 必要性判断

对当前本地格式化工具而言，远程写回、订阅漂移、企业鉴权、事务回滚、二次补偿、SLA 治理不是核心必要能力。

核心必要能力应收敛为：

1. 本地选择图片和附件。
2. 从批量导入文件读取素材路径和基础 metadata。
3. 远程图片只作为可选预览/下载来源。
4. 题图与模板占位符正确匹配。
5. Word 生成时图片替换稳定。
6. 基础缓存能避免重复下载，但不需要复杂治理台账。

可降级为企业版/实验性/历史兼容的能力：

1. 远程写回。
2. 企业鉴权和外部权限回调。
3. 批量事务回滚。
4. 二次补偿。
5. 主数据版本推广。
6. 注册表同步。
7. 订阅漂移队列。
8. SLA/后台任务/失败队列治理。
9. 非题图素材族远端冲突闭环。

### 第五步策略调整

第五步不应继续默认“细拆并保留所有远程/治理能力为主线”。更健康的执行方式是：

1. 先拆并保留本地题图/素材基础能力。
2. 对远程写回、治理、订阅漂移做边界标记，归入 enterprise/legacy/experimental 子域。
3. 暂停扩大远程写回相关测试面，只保留现有行为不破坏。
4. 如果没有真实后端需求，后续考虑隐藏入口、冻结功能、逐步删除。
5. 如果未来确实需要企业素材库，应从 `AssetsPanel` 中移出，变成独立 service 层和 connector 层，而不是继续放在 UI 面板中。

### 调整后的第五步优先级

新的第五步优先级如下：

1. `question_figures.py`：保留，优先拆。它是本地题图基础能力。
2. `question_cache.py`：只保留轻量缓存状态和路径 fallback，复杂缓存治理先不扩大。
3. `question_audit.py`：只保留本地修复/回滚审计，终态闭环审计暂缓。
4. `remote_writeback.py`：仅做隔离边界，不作为主线增强。
5. `subscription_drift` 和 `non_question_asset_family`：暂不拆入主线，后续单独做“删除/冻结/企业化迁移”评估。

结论：远程/治理代码目前最大的工程价值，不是继续扩展，而是提示我们需要先做产品边界瘦身。

## 第五步执行记录

执行日期：2026-07-06

本次按“先保留本地题图/素材基础能力，远程写回不作为主线增强”的策略完成第五步优化。

### 实际落地模块

新增并落地 4 个模块：

```text
src/ui/panels/assets/common.py
src/ui/panels/assets/question_figures.py
src/ui/panels/assets/question_cache.py
src/ui/panels/assets/question_audit.py
```

模块职责：

- `common.py`：跨遗留流程共用的时间戳、数值解析、fallback 文本 helper。
- `question_figures.py`：题图 item、metadata、标签、排序、匹配、preview reference、远程预览 URL 识别。该模块不执行网络写回。
- `question_cache.py`：共享缓存目录/条目/指标/清理任务/前台确认状态。该模块只做轻量本地缓存台账，不扩大企业治理能力。
- `question_audit.py`：本地题图修复和回滚审计记录读写。该模块不覆盖远程写回、SLA、订阅漂移。

`assets_panel.py` 保留原模块级 helper 名字，通过 import 指向新模块，避免旧测试和内部引用断裂。

### 本次没有迁移的内容

本次没有迁移远程写回 connector、订阅漂移恢复、非题图素材族远端冲突闭环。原因：

1. 这些能力需要外部素材库/主数据系统配合，不是当前本地格式化工具的核心主线。
2. 大量函数涉及 `urlopen`、远端鉴权、签名 URL、事务回滚、二次补偿、失败队列、SLA 和 Word 媒体修复副作用。
3. 继续把它们拆成“主线模块”会强化错误产品边界；更合适的下一步是做 enterprise/legacy/experimental 隔离评估。

### 体量变化

第五步完成后：

- `src/ui/panels/assets_panel.py`：约 67421 行。
- `src/ui/panels/assets/question_figures.py`：约 514 行。
- `src/ui/panels/assets/question_cache.py`：约 1055 行。
- `src/ui/panels/assets/question_audit.py`：约 288 行。
- `src/ui/panels/assets/common.py`：约 49 行。

相对第四步后的约 68920 行，主文件减少约 1499 行，满足第五步“再减少约 1000-2000 行”的目标。

### 新增测试

新增：

```text
tests/test_assets_panel_question_figures.py
tests/test_assets_panel_question_cache.py
tests/test_assets_panel_question_audit.py
```

测试覆盖：

1. 新 helper 经 `src.ui.panels.assets_panel` 兼容暴露。
2. 题图筛选、排序、metadata 匹配、preview reference、远程预览 URL 名称。
3. 共享缓存目录行、索引行、清理确认状态和确认记录读写。
4. 本地题图修复审计和回滚审计记录读写。

### 验证结果

已通过：

```text
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\common.py src\ui\panels\assets\question_figures.py src\ui\panels\assets\question_cache.py src\ui\panels\assets\question_audit.py
python -m pytest -q tests/test_assets_panel_question_figures.py tests/test_assets_panel_question_cache.py tests/test_assets_panel_question_audit.py tests/test_assets_panel_helper_modules.py tests/test_assets_panel_specs.py
python -m pytest -q tests/test_assets_panel_architecture.py::test_panel_registry_creates_real_assets_panel tests/test_assets_panel_architecture.py::test_assets_panel_derives_image_slots_and_required_roles_from_current_scene_schema tests/test_assets_panel_architecture.py::test_assets_panel_splits_attachment_inventory_roles_from_image_slots
python -m pytest -q tests/test_assets_panel_architecture.py::test_assets_panel_audits_conflict_selected_question_figure_candidate tests/test_assets_panel_architecture.py::test_assets_panel_applies_profile_question_figure_repair_candidate_from_bridge tests/test_assets_panel_architecture.py::test_assets_panel_rolls_back_question_figure_repair_audit_record tests/test_assets_panel_architecture.py::test_assets_panel_shows_shared_remote_question_figure_cache_directory_summary tests/test_assets_panel_architecture.py::test_assets_panel_shows_archive_wide_remote_question_figure_cleanup_task_list tests/test_assets_panel_architecture.py::test_assets_panel_shows_archive_wide_remote_question_figure_hit_rate_trends tests/test_assets_panel_architecture.py::test_assets_panel_does_not_open_missing_shared_remote_question_figure_cache_directory
python scripts\engineering_gate.py
```

工程门禁结果：

```text
1830 tests collected
10 smoke tests passed
Engineering gate passed
```

### 第五步完成判断

第五步的本地题图基础能力拆分、轻量缓存边界、本地审计边界、兼容导入和定向测试均已完成。

远程写回、订阅漂移、非题图素材族治理没有作为第五步主线继续拆分；它们保留在 `assets_panel.py` 中作为后续 enterprise/legacy/experimental 边界评估对象。
