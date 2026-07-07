# AssetsPanel 产品逻辑与架构合理化执行规划

## 结论先行

接下来不能再把“优化”理解成单纯搬函数。当前真正的问题有两层：

1. 代码维护性：`AssetsPanel` 仍然过大，服务层 `question_library.py` 也开始变成新的大泥球。
2. 产品逻辑合理性：本地格式化工具的核心路径，被远程写回、企业鉴权、主数据订阅漂移、SLA、补偿、跨归档治理等企业级素材库流程挤在同一个面板里。

因此下一阶段目标应改为：

- 让本地核心体验变简单。
- 让企业素材库能力被明确隔离、默认隐藏、可审计删除。
- 让 UI 控件从大量手写表格和按钮，变成描述符驱动的统一组件。
- 让服务层继续拆包，避免 `question_library.py` 变成新的巨型文件。

## 当前证据

截至本规划写入时：

- `src/ui/panels/assets_panel.py`：约 57,826 行。
- `AssetsPanel` 类方法：约 382 个。
- `assets_panel.py` 顶层函数：约 561 个。
- 顶层函数中：
  - `question_figure_remote_writeback` 相关约 170 个。
  - `question_figure_master_subscription_drift` 相关约 71 个。
  - `question_figure_master_subscription_drift_batch_failure_recovery` 相关约 39 个。
  - 非题图素材族远端治理相关约 30 个。
- `src/services/material_assets/question_library.py`：约 12,306 行，约 275 个函数。
- `question_library.py` 中：
  - `subscription_drift` 相关约 185 个函数。
  - `subscription_drift_batch_failure_recovery` 相关约 121 个函数。
  - master version / registry sync / subscription lock 相关约 33 个函数。
- UI 中存在大量重复 `QTableWidget`：
  - 订阅漂移队列、分诊、计划、执行、失败队列、恢复报告、后台任务、SLA、followup、worker、file recovery、historical DOCX repair、deep repair、non-question asset family。
  - 远程写回、企业授权、失败队列、事务报告、回滚失败队列、二次补偿、后台任务。
  - 共享缓存目录、任务、趋势、条目、指标、清理确认。

已有正向基础：

- `src/ui/panels/assets/enterprise_boundary.py` 已经把能力分为 `keep`、`isolate`、`freeze`、`delete_candidate`。
- 本地题图、缓存、审计、presenter/service 已经拆出第一批模块。
- 目前测试已经有 `tests/test_assets_enterprise_boundary.py`，可以继续演进成产品边界守门。

## 产品分层原则

### Core Local

默认展示、默认维护、必须可靠。

包括：

- 资料包基础信息。
- 本地素材选择、打开、清除。
- 本地题图批量导入、排序、替换、预览。
- 本地题图 metadata 编辑。
- 本地修复审计和回滚证据。
- 基础缓存路径和可用状态。

不包括：

- 远端写回。
- 企业鉴权。
- 主数据订阅锁。
- 订阅漂移冲突治理。
- 跨归档 worker。
- SLA / 二次补偿 / 回滚补偿。

### Local Advanced

默认可以保留，但必须轻量，不能扩展成企业工作流。

包括：

- 共享缓存目录状态。
- 缓存命中/失效提示。
- 本地 audit 记录。
- 可选远程预览下载，但只作为 preview，不作为写回或治理入口。

### Enterprise / Experimental

默认不进入主线 UI；没有真实后端契约时不得继续扩展。

包括：

- remote writeback。
- enterprise auth / signed URL refresh / external permission callback。
- master registry sync。
- subscription lock / subscription change callback。
- subscription drift queue / triage / approval / decision / batch failure recovery。
- durable worker / persistent worker / SLA / second compensation。
- non-question asset family remote governance。

### Delete Candidate

优先审计并准备删除或归档。

当前第一候选：

- 非题图素材族远端治理。
- 没有真实后端端点、只存在 UI/record/test 自循环的远程写回子链路。
- 与本地格式化无关、且没有用户可见默认入口的二次补偿、SLA、跨归档 worker 视图。

## 目标架构

```text
src/ui/panels/assets_panel.py
  只保留页面壳、信号连接、少量 profile/上下文编排

src/ui/panels/assets/
  core_panel_sections.py          本地核心 UI section 构造
  table_specs.py                  表格列、动作、空态、可见性描述符
  core_actions.py                 本地素材/题图动作编排
  enterprise_gate.py              企业能力开关和默认隐藏规则
  enterprise_sections.py          企业能力 UI，后续可整体移除或插件化
  question_*_presenter.py         只做 UI 行/状态投影

src/services/material_assets/
  question_figures.py             本地题图纯数据逻辑
  question_library_core.py        本地 metadata / history / governance 基础逻辑
  question_master_data.py         master version / registry / subscription 基础 record
  subscription_drift.py           subscription drift 纯 record/payload
  subscription_recovery.py        failure recovery 纯 record/payload
  remote_writeback.py             remote writeback payload/record/status
  enterprise_boundary.py          跨层共享的能力边界定义
```

关键方向：

- `assets_panel.py` 不再继续接收新的业务 helper。
- `question_library.py` 不再继续膨胀，后续拆成多个服务模块。
- UI 表格统一由描述符生成，避免几十个 `QTableWidget` 重复创建和重复 populate。
- 企业能力先由 runtime gate 默认隐藏，再根据使用证据删除或迁到 enterprise 模块。

## 执行路线

### Phase 0：建立“不能继续变复杂”的守门

目标：先阻止结构继续恶化。

执行项：

- 新增架构测试，限制 `assets_panel.py` 不允许新增 enterprise/freezed 前缀函数。
- 新增统计脚本或测试，记录：
  - `assets_panel.py` 行数。
  - `AssetsPanel` 方法数。
  - 顶层 enterprise 函数数。
  - `question_library.py` 行数和函数数。
- 把 `enterprise_boundary.py` 的分类从说明文档升级为测试依据：
  - `freeze` 能力不得默认出现在核心 UI。
  - `delete_candidate` 能力必须有删除审计记录。

验收：

- 修改核心资产面板时，测试能阻止新增远程写回/订阅漂移 UI。
- 有一份自动输出的 capability inventory。

### Phase 1：默认产品路径瘦身

目标：先让用户默认看到的是本地素材管理，而不是企业事故治理台。

执行项：

- 新增 `AssetPanelMode`：
  - `local_core`
  - `local_advanced`
  - `enterprise`
- 默认模式为 `local_core`。
- 在 `local_core` 下隐藏：
  - remote writeback 全部表格。
  - enterprise auth 表格。
  - subscription drift 队列/分诊/审批/计划/执行。
  - failure recovery / SLA / worker / compensation 视图。
  - non-question asset family remote governance。
- 保留：
  - 本地题图 items。
  - 本地 metadata editor。
  - 本地 version/history/audit 中真正服务本地回滚的部分。
  - 轻量 cache 状态。
- 新增测试：
  - 默认模式不创建或不显示企业治理控件。
  - enterprise 模式显式开启后才显示冻结能力。

验收：

- 默认 UI 第一屏只服务“本地资料包 + 本地题图素材管理”。
- 企业链路没有被删除前，也不会污染默认体验。

### Phase 2：控件整合

目标：减少重复表格、重复按钮、重复 populate 方法。

执行项：

- 新增 `AssetTableSpec`：
  - `key`
  - `columns`
  - `row_builder`
  - `actions`
  - `empty_state`
  - `boundary_key`
  - `mode`
- 新增统一表格构造函数：
  - `build_asset_table(spec)`
  - `populate_asset_table(table, rows, spec)`
  - `set_asset_table_visible(table, rows, mode)`
- 第一批整合对象：
  - subscription drift queue / triage / decision plan / decision execution / field merge execution。
  - remote writeback batch / failure queue / transaction report。
  - shared cache dirs / tasks / trends / entries / metrics / cleanup。
- 第二批整合对象：
  - failure recovery report / background task / SLA / followup / auto execution / worker / monitor / file recovery / historical DOCX repair / deep repair。

验收：

- 每新增一种治理表，只写 spec，不再手写一套 `QTableWidget + set headers + populate + action buttons`。
- `AssetsPanel.__init__` 中表格构造行数显著下降。
- 相关 UI 测试只关心 spec 行为，不直接依赖每个重复控件的内部实现。

### Phase 3：服务层拆包

目标：避免 `question_library.py` 变成新的 `assets_panel.py`。

执行项：

- 从 `question_library.py` 拆出：
  - `question_library_core.py`：本地 library rows、metadata patch、history。
  - `question_master_data.py`：master version、registry sync、subscription lock/change。
  - `subscription_drift.py`：queue、triage、decision、batch execution。
  - `subscription_recovery.py`：report、drilldown、SLA、followup、auto execution、worker、file recovery、historical DOCX、deep repair。
  - `remote_writeback.py`：writeback payload、status、conflict、rollback、compensation record。
- `src/services/material_assets/__init__.py` 保持兼容导出，但不再把所有实现压在一个文件。
- 对每个新服务模块增加同名测试文件或测试区域。

验收：

- `question_library.py` 降到可维护的兼容 facade。
- 单个服务模块不超过约 2,500 行。
- 新业务逻辑必须进入明确子域模块，不得进入 facade。

### Phase 4：删除/归档非必要产品元素

目标：真正减少产品复杂度，而不只是隐藏。

执行项：

对每个 `delete_candidate` 和 `freeze` 能力执行四步审计：

1. 是否有真实用户入口。
2. 是否有真实后端契约。
3. 是否服务本地格式化核心路径。
4. 是否只有 record/payload/test 自循环。

处理策略：

- 四项都弱：删除 UI 和执行函数，保留 migration note。
- 有后端契约但非核心：迁到 `enterprise_sections.py`，默认关闭。
- 只有历史数据兼容需要：保留 record parser，删除 UI 执行入口。
- 有本地价值：降级为 Local Advanced，只保留只读投影或轻量提示。

第一批删除候选：

- non-question asset family remote governance。
- remote writeback second compensation UI。
- remote writeback rollback failure queue UI。
- subscription drift SLA center UI。
- persistent/durable worker UI。

验收：

- 删除项有文档、测试调整和迁移说明。
- 默认模式下相关控件不存在或不可访问。
- 代码行数和控件数真实下降。

### Phase 5：把面板变成薄编排层

目标：`AssetsPanel` 不再拥有业务规则。

执行项：

- 把 profile mutation 统一封装为 action service：
  - 输入当前 profile/context。
  - 输出 mutation result、history records、dirty state、UI refresh hint。
- 面板只做：
  - 取当前 profile。
  - 调 action。
  - 保存 archive。
  - 刷新 UI。
- 对本地核心动作优先执行：
  - 批量导入题图。
  - 替换题图。
  - 保存 metadata。
  - rollback metadata。
  - repair audit append。

验收：

- `AssetsPanel` 方法数降到 200 以下。
- 本地核心动作可以不实例化 Qt widget 做单元测试。
- UI 测试主要覆盖集成和显示，不再承载大量业务规则验证。

## 执行优先级

## 2026-07-06 审阅修订：先做代码精简，不先做控件统一

本规划经过再次审阅后，优先级需要调整。

原计划把“默认隐藏企业能力”和“控件 spec 化”放在前面，是偏保守的产品架构路径。但如果当前目标明确收束为“代码精简”，且可以接受删除企业远程能力，那么下一步不应先做控件统一。控件统一会让现有企业远程 UI 继续被保留，只是换一种更整齐的写法；这会改善局部维护性，却不会减少产品复杂度。

新的判断：

- 企业远程相关能力可以进入删除主线，而不是只隐藏。
- 删除应按能力岛执行，不按关键词粗删。
- 第一阶段目标是让代码量真实下降，而不是把远程治理控件改造成统一控件。
- 控件统一延后到本地核心界面稳定后再做。

### 谨慎删除边界

可以删除的企业远程能力：

- `remote_writeback` 全链路：写回、批量写回、冲突快照、覆盖远端、字段合并、回滚、二次补偿、失败队列、事务报告。
- `enterprise_auth` / `signed_url` / `external_permission`：企业鉴权、签名 URL 续签、外部权限回调。
- `master_registry` / `registry_sync`：远端主数据 Registry 同步。
- `subscription_lock` / `subscription_change`：订阅锁和订阅变更 callback。
- `subscription_drift`：订阅漂移队列、分诊、审批、裁决、批量执行、失败恢复、SLA、worker。
- `non_question_asset_family_remote_governance`：非题图素材族远端治理、冲突裁决、补偿、终态归档、跨系统写回。

不应随企业远程一起删除的本地能力：

- 本地题图 `source` / `asset_id` / `asset_version` / `etag` 等普通 metadata 字段读取。
- 本地题图 metadata 编辑、历史记录、回滚。
- 本地题图修复 audit。
- 本地题图批量导入、排序、替换、预览。
- 仅作为图片展示来源的远程预览 URL 识别。
- 基础缓存状态和路径 fallback。

判断标准：

- 如果函数会执行 HTTP 写回、远端鉴权、签名 URL 续期、远端冲突裁决、主数据订阅或跨系统确认，优先删除。
- 如果函数只读取 metadata 并服务本地题图显示、导入、替换、回滚，暂时保留。
- 如果函数只是历史 record parser，但没有本地 UI 价值，可保留极薄兼容层或连同旧测试一起删除，视历史数据兼容需求决定。

### 优化后的删除顺序

第一刀：删除非题图素材族远端治理。

- 理由：它离本地题图主线最远，已经在 `enterprise_boundary.py` 中标为 `delete_candidate`。
- 删除范围：non-question asset family remote governance 的 UI 表格、执行函数、metadata 回填、远端 connector、冲突裁决、补偿、终态归档、跨系统写回。
- 同步处理：删除或重写 `tests/test_assets_panel_architecture.py` 中对应的大块远端治理测试。
- 保留边界：不影响本地题图和本地素材选择能力。

第二刀：删除 remote writeback 与 enterprise auth。

- 理由：它们要求外部素材库、企业授权、签名 URL、权限回调，是完整的远端产品，不属于本地格式化工具。
- 删除范围：remote writeback handoff、execution、batch plan、batch queue、failure queue、transaction report、rollback、second compensation、enterprise auth、signed URL refresh、external permission callback。
- 同步处理：删除 batch import 中仅服务写回/鉴权的端点字段映射；删除 remote writeback 相关测试。
- 保留边界：保留普通 `preview_url` / `download_url` 作为本地展示或导入字段，前提是不触发写回和鉴权流程。

第三刀：删除 master registry / subscription lock / subscription change。

- 理由：这些能力假设存在跨包主数据中心和订阅系统，当前本地工具不拥有该产品边界。
- 删除范围：registry sync、subscription lock、subscription change callback 的 UI、执行函数、service payload、record builder、导出别名和测试。
- 保留边界：本地题图版本字段和本地历史记录仍保留。

第四刀：删除 subscription drift / failure recovery / SLA / worker。

- 理由：这是企业事故治理链路，体量最大，和 `question_library.py` 绑定最深，需要最后处理。
- 删除范围：drift queue、triage、decision plan、decision execution、batch decision、failure queue、report、drilldown、background task、SLA、followup、auto execution、persistent/durable worker、file recovery、historical DOCX repair、deep repair 中只服务订阅漂移恢复的部分。
- 保留边界：如果某个 DOCX/题图修复函数能独立服务本地文档修复，应重新命名并迁到本地 repair 模块；否则删除。

### 删除验收标准

每一刀完成时必须满足：

- `assets_panel.py` 行数真实下降。
- `AssetsPanel` 方法数下降。
- 对应企业远程测试删除或改为“能力已移除”的边界测试。
- `enterprise_boundary.py` 中相关能力从 `freeze` / `delete_candidate` 调整为 `removed` 或删除记录。
- `src/services/material_assets/__init__.py` 不再导出已删除远程能力。
- `question_library.py` 不再保留只服务已删除企业远程链路的实现。
- 本地题图导入、替换、metadata 编辑、历史回滚、缓存状态测试仍通过。

### 修订后的第一优先级

1. 删除非题图素材族远端治理。
2. 删除 remote writeback 与 enterprise auth。
3. 删除 master registry / subscription lock / subscription change。
4. 删除 subscription drift / failure recovery / SLA / worker。

### 修订后的第二优先级

5. 对删除后仍保留的本地题图和本地素材路径做服务层瘦身。
6. 拆小 `question_library.py`，但只拆仍然保留的本地能力；不再为将删除的企业远程链路做服务拆包。

### 修订后的第三优先级

7. 等企业远程能力删除后，再考虑控件统一。
8. 只统一本地核心 UI 和仍有产品价值的 Local Advanced UI。

## 原执行优先级记录

1. Runtime mode/gate：默认隐藏 enterprise/freezed/delete_candidate 能力。
2. 控件 spec 化：先整合重复表格。
3. `question_library.py` 拆包：先拆 subscription recovery。

第二优先级：

4. 删除第一批 delete candidate。
5. 把本地题图 action 从面板移到 action service。

第三优先级：

6. 企业能力插件化或彻底移除。
7. 全量 UI 文案和默认路径瘦身。

## 建议下一步具体任务

下一步不要继续抽 metadata 小函数，也不要先做控件统一。建议按“删除一座能力岛、验证一次本地核心”的节奏执行。

### 任务 A：删除非题图素材族远端治理

要改：

- `src/ui/panels/assets_panel.py`
- `tests/test_assets_panel_architecture.py`
- `src/ui/panels/assets/enterprise_boundary.py`
- 可能涉及 `docs/` 中对应执行记录补充 migration note。

删除对象：

- `_asset_library_non_question_asset_family_*`
- `_apply_asset_library_non_question_asset_family_*`
- `_execute_asset_library_non_question_asset_family_*`
- `_asset_library_master_subscription_drift_batch_failure_recovery_non_question_asset_family_*`
- `_apply_asset_library_master_subscription_drift_batch_failure_recovery_non_question_asset_family_*`

测试处理：

- 删除 `test_non_question_asset_family_recovery_governance_records_candidate_and_ui`。
- 删除 `test_non_question_asset_family_compensation_final_audit_records_authorization_snapshot_followup_connector`。
- `tests/test_assets_enterprise_boundary.py` 改为确认该能力已删除或不再出现在面板函数清单。

验收：

- 本地题图相关测试仍通过。
- `assets_panel.py` 行数明显下降。
- 非题图远端治理相关函数 `rg` 结果为空或只剩 migration note。

### 任务 B：删除 remote writeback 与企业鉴权

要改：

- `src/ui/panels/assets_panel.py`
- `src/ui/panels/assets/batch_import.py`
- `src/ui/panels/assets/enterprise_boundary.py`
- `tests/test_assets_panel_architecture.py`
- `tests/test_assets_enterprise_boundary.py`
- `tests/test_material_asset_services.py`

删除对象：

- remote writeback handoff / execution。
- remote writeback batch plan / queue / failure queue。
- transaction report / rollback / second compensation。
- enterprise auth renewal。
- signed URL refresh。
- external permission callback。
- 只服务上述能力的 batch import 字段别名。

测试处理：

- 删除 remote writeback 相关 UI/执行测试。
- 删除 signed URL / enterprise auth / external permission 相关测试。
- 删除或收窄 `question_figure_remote_writeback_task_policy_*` 服务测试。

保留：

- 普通 `download_url` / `preview_url` 字段，只作为本地预览/导入 metadata。
- 不触发 HTTP 写回的本地 metadata 读取。

验收：

- `remote_writeback`、`enterprise_auth`、`signed_url_refresh`、`external_permission_callback` 在面板执行函数中不再存在。
- 本地题图导入和预览测试仍通过。

### 任务 C：删除主数据 Registry 与订阅能力

要改：

- `src/ui/panels/assets_panel.py`
- `src/ui/panels/assets/question_library_master_version_presenter.py`
- `src/services/material_assets/question_library.py`
- `src/services/material_assets/__init__.py`
- `tests/test_assets_panel_architecture.py`
- `tests/test_material_asset_services.py`

删除对象：

- registry sync。
- subscription lock。
- subscription change callback。
- 相关 endpoint/payload/result/base record/helper。

保留：

- 本地题图 version / etag / updated_at 字段读取。
- 本地 master version 如果仅用于本地版本展示，可单独审阅后保留；如果依赖远端 registry，则删除。

验收：

- `registry_sync`、`subscription_lock`、`subscription_change` 相关 public export 不再存在。
- `question_library.py` 行数下降。
- 本地题图 library/history/governance presenter 测试仍通过。

### 任务 D：删除订阅漂移与失败恢复治理链

要改：

- `src/ui/panels/assets_panel.py`
- `src/services/material_assets/question_library.py`
- `src/services/material_assets/__init__.py`
- `tests/test_assets_panel_architecture.py`
- `tests/test_material_asset_services.py`

删除对象：

- subscription drift queue / triage / approval。
- decision plan / decision execution / field merge / batch decision。
- batch failure queue。
- recovery report / drilldown。
- background task / SLA / followup / auto execution。
- persistent worker / durable worker。
- file recovery center / historical DOCX repair / word XML media deep repair 中只服务订阅漂移恢复的包装。

保留前置审阅：

- 如果 `word_docx_recovery.py` 中有可独立服务本地 DOCX 修复的函数，保留并改名为本地 repair 能力。
- 如果只是订阅漂移事故恢复的一部分，删除。

验收：

- `subscription_drift` 在面板和服务 public API 中基本消失。
- `question_library.py` 不再承担事故治理大链路。
- 本地素材/题图主线测试仍通过。

## 风险控制

- 不一次性删除所有 enterprise 代码，按能力岛逐批删除。
- 删除前必须有 `rg` 使用证据、测试证据和迁移说明。
- 已确认删除的 public import 不继续保留 facade；只有历史数据兼容 parser 可以短期保留。
- 每一批最多处理一个产品边界，避免多个远程治理链同时大改。
- 每一批删除后必须跑本地核心题图/素材测试，确认没有误伤本地路径。
- 若发现某个函数虽带有 remote/subscription 命名但实际服务本地预览或本地修复，先改名迁移，再删除企业包装。

## 完成标准

阶段性完成标准：

- 第一批非题图远端治理删除完成。
- 第二批 remote writeback / enterprise auth 删除完成。
- 第三批 registry / subscription 删除完成。
- 第四批 subscription drift / recovery / SLA / worker 删除完成。
- `assets_panel.py` 低于 40,000 行。
- `question_library.py` 低于 4,000 行，且不再包含企业远程治理链路。
- `AssetsPanel` 方法数低于 200。
- 本地题图导入、替换、metadata 编辑、历史回滚、修复 audit、基础缓存状态测试仍通过。
- 控件 spec 化不作为本阶段完成条件，延后到企业远程删除之后。

最终健康标准：

- 本地格式化产品路径清晰。
- 企业素材库能力不污染默认产品。
- 没有真实后端契约的能力不再占据主 UI。
- UI、服务、action、record/payload 各自边界明确。
- 删除非必要元素是经过证据审计的结果，而不是盲删。

## 2026-07-06 再次审阅优化：企业远程删除方案定稿

这次再次审阅后的结论更明确：当前阶段应继续围绕“代码精简和产品边界收缩”执行，不应先做控件统一、presenter 统一或服务拆包。控件统一会把大量企业远程能力保留下来，只是换成更整齐的写法；这不符合现在“删除非必要元素”的目标。

### 当前证据快照

- `src/ui/panels/assets_panel.py`：57,826 行，947 个函数，其中 `AssetsPanel` 方法 382 个。
- `src/services/material_assets/question_library.py`：12,306 行，275 个函数。
- 按 `remote_writeback`、`enterprise_auth`、`signed_url`、`external_permission`、`master_registry`、`registry_sync`、`subscription_lock`、`subscription_change`、`subscription_drift`、`non_question_asset_family` 做 AST 名称匹配时，`assets_panel.py` 命中 724 个函数，命中区间约 46,173 行。该数字包含函数互相调用和语义重叠，不能当成精确可删行数，但足以说明企业远程链路已经压过本地核心。
- `tests/test_assets_panel_architecture.py` 中相关企业远程测试命中 29 个测试函数，约 10,764 行；其中非题图素材族远端治理两条测试约 5,000 行，是第一刀的主要测试负担。
- `tests/test_material_asset_services.py` 中 registry / subscription / drift 相关服务测试命中 4 个测试函数，约 3,554 行。
- `src/ui/panels/assets/batch_import.py` 仍映射了 signed URL refresh、enterprise auth、external permission 等企业远程字段；删除 remote writeback 时需要一起收缩字段别名。
- `src/ui/panels/assets/question_library_master_version_presenter.py` 仍有 registry sync、subscription lock、subscription change callback 的 UI 动作入口；删除任务 C 时必须纳入。

### 远程能力必要性判断

对当前本地格式化工具而言，企业远程能力不是必要能力。它只有在同时满足以下条件时才有产品必要性：

1. 存在真实企业素材库或主数据系统。
2. 存在稳定的鉴权、签名 URL、权限回调和写回 API 契约。
3. 有明确用户流程需要把本地题图 metadata 或修复结果写回远端。
4. 有人负责失败队列、补偿、SLA、worker 和跨系统审计的运维闭环。

当前代码更像是把“企业素材治理平台”的流程压进了本地格式化面板。若没有上述后端和运维责任，继续维护这些能力会提高测试和 UI 复杂度，却不会改善本地格式化体验。

### 审阅后的保留清单

删除企业远程时必须保留这些本地价值：

- 本地题图导入、排序、替换、预览。
- 本地题图 metadata 编辑、历史记录、回滚。
- 本地题图修复 audit 和 rollback audit。
- 本地素材选择、打开、清除。
- `source`、`asset_id`、`asset_version`、`etag`、`preview_url`、`download_url` 等只读 metadata 字段，只要它们不触发写回、鉴权、订阅或治理流程。
- 轻量缓存状态、缓存路径 fallback、缓存命中/失效提示。
- 只读历史 record parser 可以短期保留，但不能继续暴露执行入口。

### 审阅后的删除清单

可以进入删除主线的能力：

- 远程写回：handoff、execution、batch plan、batch queue、failure queue、transaction report、conflict snapshot、overwrite、field merge、rollback、second compensation、manifest、idempotency、retry。
- 企业鉴权：enterprise auth renewal、signed URL refresh、external permission callback、权限 preflight、组织权限治理。
- 主数据订阅：registry sync、subscription lock、subscription change callback，以及只服务这些能力的 presenter 动作。
- 订阅漂移：queue、triage、approval、decision plan、decision execution、field merge、batch decision。
- 失败恢复治理：failure queue、recovery report、drilldown、background task、SLA、followup、auto execution、persistent worker、durable worker。
- 非题图素材族远端治理：remote connector、conflict decision、retry replay、compensation、terminal archive、cross-system writeback、external proof。

### 优化后的执行顺序

第 0 刀：建立删除前基线。

- 记录 `assets_panel.py`、`question_library.py`、相关测试文件的行数和函数数。
- 用 AST 列出本批删除候选函数名和行号。
- 用 `rg` 记录 source、tests、docs 中的调用点。
- 不新增新抽象，不先做控件统一。

第 1 刀：删除非题图素材族远端治理。

- 这是距离本地题图主线最远的能力，且已经被 `enterprise_boundary.py` 标为 `delete_candidate`。
- 删除 UI 表格、刷新函数、选择/执行方法、顶层 record/payload/helper、测试导入和两条大测试。
- `enterprise_boundary.py` 中该能力改为 `removed` 或删除记录，同时边界测试改为确认面板函数中不再存在该能力前缀。

第 2 刀：删除 remote writeback 与企业鉴权。

- 先删 UI 和执行入口，再删 connector/payload/record helper，最后收缩 batch import 字段别名和测试。
- 保留 `preview_url` / `download_url` 的只读展示含义；删除 `remote_writeback_url`、`signed_url_refresh_url`、`enterprise_auth_*`、`external_permission_*` 等只为写回服务的字段别名。

第 3 刀：删除 registry / subscription lock / subscription change。

- 同步处理 `assets_panel.py`、`question_library.py`、`__init__.py`、`question_library_master_version_presenter.py` 和相关测试。
- 若某些 master version 字段只是本地版本展示，可保留并改名为本地版本 metadata；依赖远端 registry 的流程删除。

第 4 刀：删除 subscription drift / failure recovery / SLA / worker。

- 先把独立本地 DOCX/题图修复能力筛出来；能脱离订阅漂移语义的，改名迁到本地 repair；不能脱离的删除。
- 再删除 drift queue、decision、batch failure、recovery report、SLA、worker、followup、auto execution。
- 最后清理 `question_library.py` 和 public exports，避免服务层继续承载已删除的企业事故治理链。

### 每刀必须满足的验收

- 本批关键词在 `assets_panel.py` 和相关服务 public API 中消失，或只剩迁移说明。
- `enterprise_boundary.py` 与测试同步更新为 `removed` / 已删除能力，而不是继续 `freeze` 或 `delete_candidate`。
- 删除对应 UI 测试，不用“跳过”伪装通过；需要保留的测试改为本地能力或边界能力测试。
- 本地题图、metadata、history、audit、cache 的聚焦测试仍通过。
- `python -m py_compile` 覆盖本批触达的 source 和 tests。
- 记录删除前后行数、函数数、测试结果和残留 `rg` 结果。

### 停手条件

遇到以下情况要暂停该刀，先重新审阅：

- 发现真实后端契约文件、真实用户配置或生产入口正在使用该远程能力。
- 某个函数虽然带 `remote` / `subscription` 命名，但实际只服务本地预览、导入、回滚或 DOCX 修复。
- 删除后本地题图导入、替换、metadata 编辑、历史回滚、修复 audit、缓存状态测试失败。
- public API 被外部模块广泛使用，且不能在同一刀里安全删除调用点。

### 最终审阅结论

方案应从“精简产品能力”开始，而不是从“整理现有复杂度”开始。企业远程能力可以删，但要按能力岛逐批删；本地题图、轻量缓存、本地审计和本地修复证据必须保住。完成四刀后，再考虑控件统一和本地服务层瘦身，届时统一的是留下来的产品能力，而不是即将删除的企业远程流程。

## 2026-07-06 第一刀执行记录：非题图素材族远端治理删除

本次按任务 A 完成第一座能力岛删除：`non_question_asset_family` 相关的非题图素材族远端治理不再作为源码或测试中的当前能力存在。

### 删除范围

- `src/ui/panels/assets_panel.py`
  - 删除函数名包含 `non_question_asset_family` 的 282 个函数，合计 26,107 行。
  - 删除非题图素材族远端治理表格初始化块。
  - 删除刷新流程中的非题图远端治理表刷新调用。
  - 删除样式表和表格样式刷新中的非题图远端治理表引用。
- `tests/test_assets_panel_architecture.py`
  - 删除 2 条非题图素材族远端治理大测试，合计 5,060 行。
  - 删除已删 helper 的 import 残留。
- `src/ui/panels/assets/enterprise_boundary.py`
  - 删除 `non_question_asset_family_remote_governance` 边界记录。
- `tests/test_assets_enterprise_boundary.py`
  - 删除对该能力 `delete_candidate` 的断言。
  - 新增边界测试，动态确认已删除能力不再注册，也不再出现在 `assets_panel.py` 顶层函数中。

### 删除后证据

- `src/ui/panels/assets_panel.py`：31,640 行，665 个函数，`AssetsPanel` 方法 345 个。
- `tests/test_assets_panel_architecture.py`：11,242 行，138 个测试/辅助函数。
- `src/ui/panels/assets/enterprise_boundary.py`：231 行。
- `tests/test_assets_enterprise_boundary.py`：97 行，6 个测试函数。
- `rg -n "non_question_asset_family" src tests`：无匹配。

### 验证

已通过：

```powershell
python -m py_compile src\ui\panels\assets_panel.py tests\test_assets_panel_architecture.py src\ui\panels\assets\enterprise_boundary.py tests\test_assets_enterprise_boundary.py
python -m pytest -q tests\test_assets_enterprise_boundary.py
python -m pytest -q tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py
python -m pytest -q tests\test_assets_panel_architecture.py -k "not non_question and (remote_writeback or subscription_drift or file_recovery_center or historical_docx_repair or word_xml_media_deep_repair or question_figure)"
```

结果：

- 企业边界测试：`6 passed`。
- 本地题图、缓存、audit、presenter 聚焦测试：`13 passed`。
- AssetsPanel 架构聚焦测试：`46 passed, 59 deselected`。

### 下一步

继续执行第二刀：删除 `remote_writeback` 与企业鉴权。执行前必须先重新盘点真实入口，尤其是：

- `assets_panel.py` 中 remote writeback UI、执行函数、connector、payload、record helper。
- `batch_import.py` 中只服务写回/鉴权的字段别名。
- `tests/test_assets_panel_architecture.py` 中 remote writeback、signed URL、enterprise auth、external permission 相关测试。
- `enterprise_boundary.py` 中 `enterprise_remote_auth` 和 `remote_writeback` 边界记录。

## 2026-07-06 第二刀执行记录：remote writeback 与企业鉴权删除

本次按任务 B 删除远程写回与企业鉴权主链路。删除后，`remote_writeback`、`enterprise_auth`、`signed_url`、`external_permission` 不再作为 `src/tests` 中的当前能力关键词存在。

### 删除范围

- `src/ui/panels/assets_panel.py`
  - 删除函数名包含 `remote_writeback`、`enterprise_auth`、`signed_url`、`external_permission` 的 238 个函数，合计 10,942 行。
  - 删除远程写回任务治理控件。
  - 删除远程写回、企业鉴权、批量写回、失败队列、事务报告、回滚失败队列、二次补偿、二次补偿失败队列、后台任务表格。
  - 删除刷新流程、样式表和表格样式刷新中的远程写回表格引用。
  - 删除 metadata alias 中只服务写回/签名/权限治理的 `writeback_url`、`current_url`、`signed_url_expires_at`、`writeback_expires_at`、`current_expires_at`、`permission_status`、`permission_granted`。
- `src/ui/panels/assets/batch_import.py`
  - 删除 70 条只服务写回、签名 URL、企业鉴权和外部权限回调的导入字段别名。
  - 保留 `download_url`、`asset_url`、`thumbnail_url`、`preview_url` 等只读展示/下载字段。
- `src/ui/panels/assets/enterprise_boundary.py`
  - 删除 `enterprise_remote_auth` 和 `remote_writeback` 边界记录。
- `tests/test_assets_panel_architecture.py`
  - 删除远程写回、签名 URL 刷新、企业鉴权续期、外部权限回调、冲突快照、覆盖写回、字段合并、回滚、二次补偿相关测试和 HTTP helper。
- `src/services/material_assets/question_library.py`
  - 将已被订阅漂移恢复复用的 `question_figure_remote_writeback_task_policy_*` helper 重命名为中性的 `question_figure_task_policy_*`，避免服务 public API 继续暴露 remote writeback 命名。
- `src/services/material_assets/__init__.py`
  - 同步服务导出重命名。
- `tests/test_material_asset_services.py`
  - 同步服务测试中的中性 task policy helper 名称。

### 删除后证据

- `src/ui/panels/assets_panel.py`：19,939 行，427 个函数，`AssetsPanel` 方法 280 个。
- `src/services/material_assets/question_library.py`：12,306 行，275 个函数。本刀只做 remote writeback 命名收口，订阅漂移主体留到第四刀删除。
- `tests/test_assets_panel_architecture.py`：7,902 行，111 个测试/辅助函数。
- `src/ui/panels/assets/batch_import.py`：706 行。
- `src/ui/panels/assets/enterprise_boundary.py`：201 行。
- `rg -n "remote_writeback|enterprise_auth|signed_url|external_permission" src tests`：无匹配。

### 验证

已通过：

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\batch_import.py src\ui\panels\assets\enterprise_boundary.py src\services\material_assets\question_library.py src\services\material_assets\__init__.py tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py
python -m pytest -q tests\test_assets_enterprise_boundary.py
python -m pytest -q tests\test_material_asset_services.py
python -m pytest -q tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py
python -m pytest -q tests\test_assets_panel_architecture.py
```

结果：

- 企业边界测试：`7 passed`。
- 素材服务测试：`18 passed`。
- 本地题图、缓存、audit、presenter 聚焦测试：`13 passed`。
- AssetsPanel 架构测试：`87 passed`。

### 下一步

继续执行第三刀：删除 master registry / subscription lock / subscription change。执行前必须先重新盘点：

- `assets_panel.py` 中 registry sync、subscription lock、subscription change callback 的 UI、执行函数和 helper。
- `src/ui/panels/assets/question_library_master_version_presenter.py` 中对应 action 入口。
- `question_library.py` 与 `__init__.py` 中 registry/subscription 的 payload、endpoint、record builder、导出别名。
- `tests/test_assets_panel_architecture.py` 和 `tests/test_material_asset_services.py` 中对应测试。

## 2026-07-06 第三次审阅优化：第三刀与第四刀执行前再收紧

本次审阅结论：当前方向仍应保持“代码精简优先”，不要回到“先统一控件”或“先继续拆模块”的路线。前两刀已经证明，删除不必要的企业远程能力能带来真实代码量下降；如果现在转去做控件统一，会把即将删除的 registry、subscription drift、SLA、worker 等治理表格重新包装一遍，反而延长复杂度寿命。

因此，后续方案调整为：

- 第三刀只处理 `master_registry` / `registry_sync` / `subscription_lock` / `subscription_change` 这条远端主数据订阅入口链。
- 第四刀处理 `subscription_drift` / `failure_recovery` / `SLA` / `worker` 这条企业事故治理主体链。
- 不把第三刀和第四刀混成一次大删除，但第三刀执行时要预判第四刀依赖，避免留下无法运行、无人使用的空壳。
- 本地题图、metadata、history、audit、轻量缓存、只读 preview/download 字段继续作为保护对象。

### 当前真实基线

前两刀之后的当前基线：

- `src/ui/panels/assets_panel.py`：19,940 行，427 个函数，`AssetsPanel` 方法 280 个。
- `src/services/material_assets/question_library.py`：12,307 行，275 个函数。
- `tests/test_assets_panel_architecture.py`：7,903 行，111 个测试/辅助函数。
- `tests/test_material_asset_services.py`：4,442 行，18 个测试/辅助函数。
- `remote_writeback|enterprise_auth|signed_url|external_permission` 在 `src/tests` 中已经无匹配。

第三刀命中范围：

- `assets_panel.py`：10 个 registry/subscription 函数，约 816 行。
- `question_library.py`：28 个 registry/subscription 函数，约 628 行。
- `tests/test_assets_panel_architecture.py`：3 个相关测试，约 455 行。
- `tests/test_material_asset_services.py`：3 个相关测试，约 387 行。
- `question_library_master_version_presenter.py`：没有同名函数，但仍有 registry sync、subscription lock、subscription change callback 的 action 入口判断。
- `enterprise_boundary.py`：仍把 master registry / master subscription 前缀归为冻结能力，需要同步删除或改为已移除断言。

第四刀命中范围：

- `assets_panel.py`：194 个 subscription drift / recovery / worker 相关函数，约 8,308 行。
- `question_library.py`：185 个 subscription drift / recovery / worker 相关函数，约 8,207 行。
- `tests/test_assets_panel_architecture.py`：11 个相关测试，约 3,022 行。
- `tests/test_material_asset_services.py`：1 个超大服务测试，约 3,167 行。
- `src/services/material_assets/__init__.py`：仍大量导出 drift / recovery / SLA / worker public API。
- `tests/test_assets_enterprise_boundary.py`：仍断言 `subscription_drift_recovery` 为 `freeze`，第四刀后要改为已移除能力守门。

### 第三刀重新定义

第三刀不是“删所有 master version”。它只删除远端主数据订阅流程。

删除：

- registry sync endpoint、payload、idempotency key、affected items、base record、response parser。
- subscription lock endpoint、payload、policy、idempotency key、base record。
- subscription change callback endpoint、result、remote/local metadata diff、base record。
- `AssetsPanel` 中执行 registry sync、执行 subscription lock、拉取 subscription change callback 的 row action。
- `question_library_master_version_presenter.py` 中 registry / subscription 三类 action 按钮和条件分支。
- `src/services/material_assets/__init__.py` 中这些函数的导出。
- architecture/service 测试中验证 registry sync、subscription lock、subscription change callback 的三条用例。
- enterprise boundary 中 master registry / master subscription 的冻结边界记录或前缀断言。

保留：

- 只读 `source`、`asset_id`、`asset_version`、`etag`、`updated_at` 等本地 metadata 显示字段。
- 本地题图版本展示、历史记录、回滚证据。
- 与远端订阅无关的本地 master version 文案或排序信息，但命名上要避免继续暗示 registry/subscription 系统。
- 只读 preview/download URL 字段，只要不触发鉴权、签名续期、写回或订阅 callback。

第三刀完成后，允许短期仍存在 `subscription_drift` 主体，因为它属于第四刀；但不应再存在 `master_registry`、`registry_sync`、`subscription_lock`、`subscription_change` 这类远端订阅入口。

### 第四刀重新定义

第四刀的目标是删除企业事故治理主体，而不是把它重命名成“本地修复”继续保留。

删除：

- subscription drift queue、triage、approval、decision plan、decision execution、field merge、batch decision。
- batch failure queue、recovery report、report drilldown、background task。
- SLA center、followup、auto execution、persistent worker queue、durable worker monitor。
- 依附 subscription drift 的 Word media rewrite、file recovery center、historical DOCX repair、word XML media deep repair 入口和记录。
- `question_library.py` 与 `__init__.py` 中的 drift/recovery public API。
- architecture/service 测试中专门验证企业事故治理闭环的测试。

第四刀前必须先筛查：

- 如果某个 DOCX media repair 函数可以独立服务本地题图修复，并且不依赖 subscription drift 的队列、SLA、worker、跨归档审计，可以迁入本地 repair 命名空间。
- 如果它只能从 drift recovery report 派生，或者只是企业事故链上的 report/manifest/worker 证据，则删除。

### 为什么不继续保留 registry/subscription

registry/subscription 能力的必要性依赖远端主数据系统。当前项目是本地格式化工具，真实核心是本地资料包、Word 输出、题图素材、缓存和审计。保留 registry/subscription 会带来几个维护成本：

- UI 上继续暴露用户无法理解也无法独立完成的企业流程。
- 服务层继续维护 endpoint/payload/record/test 自循环。
- presenter 继续承载“根据远端状态显示动作按钮”的复杂分支。
- 第四刀删除 drift 时会被第三刀残留的订阅字段拖住。

所以第三刀不建议改成“隐藏 registry/subscription”；应该删除入口、执行、payload、record、测试和 public export，只保留本地 metadata 读写。

### 执行顺序再优化

第三刀建议按以下顺序执行：

1. 先删 `question_library_master_version_presenter.py` 的 registry/subscription action 分支，让 UI 不再提出远端动作。
2. 再删 `AssetsPanel` 的三类 row action 和 connector/apply helper。
3. 再删 `question_library.py` 的 endpoint/payload/base record/helper。
4. 再删 `src/services/material_assets/__init__.py` 导出。
5. 再删或改写 architecture/service 测试。
6. 最后更新 `enterprise_boundary.py` 和边界测试，确认第三刀能力已移除。

第四刀建议按以下顺序执行：

1. 用 AST 列出所有 drift/recovery/worker 函数，标记“可迁本地 repair”和“直接删除”。
2. 先处理可迁本地 repair 的极少数函数，避免误删真实本地价值。
3. 删除 drift/recovery UI 表格、刷新、样式、row action。
4. 删除服务层 drift/recovery record/payload/helper 和 public export。
5. 删除企业事故治理测试，保留或新增本地 repair 聚焦测试。
6. 更新边界测试，从 `freeze` 改为“已删除能力不得重新出现”。

### 更新后的验收口径

第三刀验收：

- `rg -n "master_registry|registry_sync|subscription_lock|subscription_change" src tests` 不再命中当前实现或测试，只允许命中文档迁移记录。
- `question_library_master_version_presenter.py` 不再生成 registry/subscription action。
- `enterprise_boundary.py` 不再把 master registry / master subscription 标为冻结能力。
- 本地题图、缓存、audit、presenter 聚焦测试仍通过。
- `tests/test_assets_panel_architecture.py` 全量仍通过，或明确记录第四刀前被 drift 耦合影响的临时缺口。

第四刀验收：

- `rg -n "subscription_drift|failure_recovery|persistent_worker|durable_worker|sla_center" src tests` 不再命中当前实现或测试，只允许命中文档迁移记录。
- `question_library.py` 明显瘦身，目标降到 4,000 行以下。
- `AssetsPanel` 方法数继续下降，目标接近或低于 200。
- 本地题图导入、替换、metadata 编辑、history rollback、repair audit、cache 测试仍通过。
- `enterprise_boundary.py` 中不再存在企业事故治理 freeze 项。

### 再审阅后的最终判断

继续删是合理的，但要保持“能力岛删除”，不要关键词粗暴删除。第三刀是远端主数据订阅入口，第四刀是企业事故治理主体；这两刀完成前，不做控件统一、不做 presenter 大重构、不做服务层大拆包。等企业远程能力真正消失后，再优化留下来的本地能力，代码结构会更轻，也更诚实。

## 2026-07-06 第四次审阅优化：第三刀与第四刀执行后复核

本轮继续按“代码精简优先”执行，已经把前面审阅里确认的第三刀、第四刀落到代码。复核后的判断是：方向正确，且应该继续保持产品边界收缩，而不是马上进入控件统一。原因是企业远程链路删除后，`AssetsPanel` 和 `question_library` 的体积已经明显下降；现在剩下的问题更适合围绕“本地题图、缓存、审计、只读预览”重塑，而不是把已删除能力的 UI 外壳再抽象一遍。

### 第三刀执行记录

已删除远端主数据订阅入口：

- `master_registry` / `registry_sync`
- `subscription_lock`
- `subscription_change`
- registry/subscription 的 endpoint、payload、base record、result parser、connector、metadata apply helper
- `question_library_master_version_presenter.py` 中对应的 Registry sync、Subscription lock、Subscription change callback action
- `enterprise_boundary.py` 中 `master_data_governance` 边界记录
- architecture/service 测试中验证上述远端订阅闭环的用例

保留的是本地主版本 metadata 视图：`master_data_key` 作为本地版本提升和差异展示的稳定键继续存在，但它不再代表“写回主数据系统”。

### 第四刀执行记录

已删除企业事故治理主体：

- `subscription_drift`
- `failure_recovery`
- `recovery_report`
- `sla_center`
- `persistent_worker`
- `durable_worker`
- `file_recovery_center`
- `historical_docx_repair`
- `word_xml_media_deep_repair`
- `word_media_rewrite`
- `background_task`
- 旧 `REMOTE_WRITEBACK_TASK_POLICY_KEYS` 与相关 task policy 残留

同时清掉了几个容易留下“隐形远程入口”的残留：

- `word_docx_recovery.py` 中以 `subscription_drift` 命名的兼容别名；保留公开的本地 `scan_docx_xml_media` / `deep_repair_docx_xml_media`。
- `batch_import.py` 中 registry/subscription/lock/change callback/conflict snapshot 字段别名。
- `batch_import.py` 中 signed URL refresh、auth refresh、approval status、permission scope、renewed/refreshed URL 字段别名。
- `assets_panel.py` 中未被调用的 `_question_figure_remote_current_endpoint`。

### 当前保留边界

保留项应继续被当作本地核心或只读辅助：

- 本地题图导入、排序、替换、预览。
- 本地题图 metadata、history、rollback、repair audit。
- 轻量共享缓存状态、命中/缺失/失效提示、清理确认。
- 只读 `download_url` / `thumbnail_url` / `preview_url` 预览下载。
- 简单远程预览认证字段，用于读取受保护图片；它不能扩展成鉴权续期、权限审批、签名刷新或写回流程。

不再保留：

- 远程写回事务。
- 企业鉴权续期。
- 签名 URL 刷新。
- 外部权限回调。
- 主数据 registry/subscription。
- 订阅漂移、SLA、worker、失败补偿、跨系统事故治理。

### 当前代码体积

执行后基线：

- `src/ui/panels/assets_panel.py`：8,394 行，顶层函数 42 个，顶层类 2 个。
- `src/services/material_assets/question_library.py`：2,138 行，顶层函数 56 个。
- `src/ui/panels/assets/batch_import.py`：638 行，顶层函数 30 个。
- `src/ui/panels/assets/enterprise_boundary.py`：162 行，顶层函数 5 个，顶层类 1 个。

### 验证记录

已通过：

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\batch_import.py src\ui\panels\assets\question_library_master_version_presenter.py src\ui\panels\assets\enterprise_boundary.py src\services\material_assets\question_library.py src\services\material_assets\__init__.py src\services\material_assets\word_docx_recovery.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py
python -m pytest -q tests\test_material_asset_services.py
python -m pytest -q tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_question_library_presenter.py
```

结果：

- enterprise boundary：`8 passed`。
- material asset services：`12 passed`。
- 题图/缓存/audit/presenter：`17 passed`。
- helper/spec/presenter：`10 passed`。

残留扫描：

```powershell
rg -n "registry_sync|registry_url|subscription_lock|subscription_change|subscription_callback|master_data_registry|master_data_subscription|master_lock|lock_conflict|subscription_conflict|current_snapshot|conflict_url|remote_conflict|renewed_|refreshed_|auth_renewal|auth_refresh|token_refresh|oauth_refresh|sso_refresh|approval_status_url|permission_scope|external_permission|signed_url|remote_writeback|enterprise_auth|subscription_drift|failure_recovery|persistent_worker|durable_worker|sla_center" src\ui\panels src\services tests
```

当前有效源码中不再命中这些企业远程能力；剩余命中只包括删除守门测试、无关的 `refreshed_cache` 变量名，以及本地测试数据文件名。

### 风险记录

`tests/test_assets_panel_architecture.py` 是未跟踪的大型架构测试文件。在清理第四刀残片时，曾用 PowerShell 按行写回，导致该文件中的部分中文断言被控制台编码污染。已把文件恢复到可 `py_compile` 的状态，并对损坏断言做了语法隔离，但本轮没有把该文件作为有效质量验证来源。

后续必须优先处理这个风险：重建或替换该大型架构测试，避免它继续作为“看似覆盖很多、实际容易被编码/文案污染拖垮”的脆弱测试。更健康的做法是拆成小型、ASCII 稳定、只验证结构契约的测试。

### 下一步优化顺序

1. 先修复测试健康：替换 `test_assets_panel_architecture.py` 的损坏中文断言，或拆成更小的结构测试。
2. 再做本地能力瘦身：围绕题图、缓存、审计、只读预览，把 `AssetsPanel` 中仍然很长的 UI glue 继续下沉到已存在的 presenter/service。
3. 再做 metadata 字段白名单：保留本地与只读预览字段，明确拒绝 registry/subscription/writeback/approval/refresh 类字段回流。
4. 最后再考虑控件统一：只统一保留下来的本地产品控件，不为已删除的企业远程流程设计抽象。


## 2026-07-07 Execution Record 5: Test Health And Scene Matrix Sync

This pass continued the documented cleanup path: test health first, then product-logic alignment.

### Completed

- Replaced `tests/test_assets_panel_architecture.py`.
  - Removed the large encoding-damaged architecture test file.
  - Rebuilt it as a 152-line ASCII structural guard with 6 focused tests.
  - The new scope is: AssetsPanel creation, shell contract, deleted enterprise identifiers, retained boundary registry, batch-import alias guard, and narrow read-only remote preview auth.
- Removed the remaining uppercase remote-writeback status constants from `assets_panel.py`.
- Synced scene-matrix product logic.
  - Removed 170 enterprise-remote evidence/rationale entries from `src/config/scene_product_readiness.py`.
  - Removed 42 enterprise-remote explicit gap-domain mappings from `src/config/scene_product_maturity_upgrade_audit.py`.
  - Removed stale positive assertions from `tests/test_scene_product_maturity_upgrade_audit.py` and added a regression guard that rejects deleted enterprise asset evidence.
- Reworded local service docstrings and boundary next-action text so source scans no longer expose deleted enterprise-remote capability phrases as current concepts.

### Current Size Snapshot

- `tests/test_assets_panel_architecture.py`: 152 lines, 9 functions, including 6 tests.
- `src/config/scene_product_readiness.py`: 1,001 lines, 12 functions.
- `src/config/scene_product_maturity_upgrade_audit.py`: 798 lines, 35 functions.
- `tests/test_scene_product_maturity_upgrade_audit.py`: 1,056 lines, 5 tests.
- `src/ui/panels/assets_panel.py`: 8,364 lines, 222 total functions/methods.
- `src/services/material_assets/question_library.py`: 2,138 lines, 56 functions.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\batch_import.py src\ui\panels\assets\enterprise_boundary.py src\services\material_assets\question_library.py src\services\material_assets\__init__.py src\services\material_assets\word_docx_recovery.py src\services\material_assets\cache_projection.py src\services\material_assets\repair_audit.py src\config\scene_product_readiness.py src\config\scene_product_maturity_upgrade_audit.py tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_scene_product_maturity_upgrade_audit.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Result: `53 passed`.

Residual scan:

```powershell
rg -n "remote writeback|remote_writeback|enterprise auth|enterprise_auth|signed URL|signed_url|external permission|external_permission|subscription drift|subscription_drift|failure recovery|failure_recovery|persistent worker|persistent_worker|durable worker|durable_worker|sla center|sla_center|registry sync|registry_sync|subscription lock|subscription_lock|subscription change|subscription_change|non-question asset family|non_question_asset_family|cross system writeback|cross-system writeback|REMOTE_WRITEBACK_TASK_POLICY_KEYS" src tests
```

Result: no matches.

### Next Step

With test health and scene-matrix product logic aligned, continue with local capability slimming: move remaining AssetsPanel UI glue around question figures, cache, audit, and read-only preview into the existing presenter/service seams. Do not start control unification yet, and do not create abstractions for deleted enterprise-remote workflows.


## 2026-07-07 Execution Record 6: Read-Only Preview Helper Service Extraction

This pass started the next documented phase: local capability slimming after enterprise-remote removal.

### Completed

- Moved `_download_remote_asset_preview_image` out of `src/ui/panels/assets_panel.py`.
- Added the read-only helper to `src/services/material_assets/question_figures.py` beside URL validation and remote preview-name helpers.
- Exported `download_remote_asset_preview_image` through `src/services/material_assets/__init__.py`.
- Kept an imported private alias in `assets_panel.py` so current UI call sites do not need a broader refactor.
- Removed low-level network/cache imports from `assets_panel.py`: `hashlib`, `tempfile`, `HTTPError`, `URLError`, `Request`, and `urlopen`.
- Added a service test proving the helper is public through `material_assets` and returns an invalid-URL failure without network access.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 8,301 lines, 221 total functions/methods.
- `src/services/material_assets/question_figures.py`: 717 lines, 32 functions.
- `src/services/material_assets/__init__.py`: 277 lines.
- `tests/test_material_asset_services.py`: 769 lines, 13 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\services\material_assets\question_figures.py src\services\material_assets\__init__.py tests\test_material_asset_services.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_panel_architecture.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused preview/service set: `22 passed`.
- Full related set: `54 passed`.

Residual enterprise-remote scan remains clean:

```powershell
rg -n "remote writeback|remote_writeback|enterprise auth|enterprise_auth|signed URL|signed_url|external permission|external_permission|subscription drift|subscription_drift|failure recovery|failure_recovery|persistent worker|persistent_worker|durable worker|durable_worker|sla center|sla_center|registry sync|registry_sync|subscription lock|subscription_lock|subscription change|subscription_change|non-question asset family|non_question_asset_family|cross system writeback|cross-system writeback|REMOTE_WRITEBACK_TASK_POLICY_KEYS" src tests
```

Result: no matches.

### Next Step

Continue with small, service-oriented moves only. Good candidates are pure metadata/history/audit helpers that still live at module level in `assets_panel.py`. Avoid moving large interactive preview-window methods until there is a clear presenter boundary for them.


## 2026-07-07 Execution Record 7: Local Metadata/History Helper Consolidation

This pass continued the documented code-slimming phase by removing duplicated local question-figure library helpers from `assets_panel.py`.

### Completed

- Replaced local `assets_panel.py` implementations with service-backed legacy aliases for:
  - `_question_figure_library_row_entries`
  - `_question_figure_library_rows`
  - `_question_figure_library_metadata_history_record`
  - `_normalized_asset_item_history_records`
  - `_question_figure_history_changed_fields`
  - `_question_figure_history_record_matches_current`
  - `_question_figure_history_record_question_row`
  - `_question_figure_history_fields_label`
  - `_question_figure_library_metadata_change_summary`
  - `_question_figure_has_library_metadata`
  - `_question_figure_library_reference`
- Removed unused enterprise-remote leftovers from `assets_panel.py`:
  - `_question_figure_remote_current_metadata_from_payload`
  - `_question_figure_remote_current_diff_summary`
  - `_question_figure_remote_current_metadata_from_snapshot`
  - `_question_figure_metadata_field_labels`
  - `_question_figure_metadata_field_getters`
  - `_question_figure_history_record_key`
- Kept old private helper names available as aliases where tests or older imports still rely on them.
- Repaired the temporary source encoding damage introduced while mechanically deleting legacy function blocks; `assets_panel.py` is again parseable by `ast`, py-compile clean, and runtime shell creation is covered by tests.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 7,901 lines, 204 total functions/methods.
- `src/services/material_assets/question_library.py`: 2,138 lines, 56 functions.
- `src/services/material_assets/__init__.py`: 277 lines.
- `tests/test_material_asset_services.py`: 769 lines, 13 tests.
- `tests/test_assets_panel_architecture.py`: 152 lines, 9 functions, including 6 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\services\material_assets\question_library.py src\services\material_assets\__init__.py tests\test_assets_panel_architecture.py tests\test_material_asset_services.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_panel_architecture.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused metadata/service set: `22 passed`.
- Full related set: `54 passed`.

Residual scans:

```powershell
rg -n "def (_question_figure_library_row_entries|_question_figure_library_rows|_question_figure_library_metadata_history_record|_normalized_asset_item_history_records|_question_figure_remote_current_metadata_from_payload|_question_figure_remote_current_diff_summary|_question_figure_remote_current_metadata_from_snapshot|_question_figure_metadata_field_labels|_question_figure_metadata_field_getters|_question_figure_history_record_key|_question_figure_history_changed_fields|_question_figure_history_record_matches_current|_question_figure_history_record_question_row|_question_figure_history_fields_label|_question_figure_library_metadata_change_summary|_question_figure_has_library_metadata|_question_figure_library_reference)" src/ui/panels/assets_panel.py
rg -n "_question_figure_(remote_current|metadata_field)|_question_figure_history_record_key" src/ui/panels/assets_panel.py src/ui/panels/assets tests
rg -n "remote writeback|remote_writeback|enterprise auth|enterprise_auth|signed URL|signed_url|external permission|external_permission|subscription drift|subscription_drift|failure recovery|failure_recovery|persistent worker|persistent_worker|durable worker|durable_worker|sla center|sla_center|registry sync|registry_sync|subscription lock|subscription_lock|subscription change|subscription_change|non-question asset family|non_question_asset_family|cross system writeback|cross-system writeback|REMOTE_WRITEBACK_TASK_POLICY_KEYS" src tests
```

Result: no matches.

### Next Step

Continue local-only slimming, but avoid broad mechanical edits in `assets_panel.py`. The safer next candidates are small UI glue methods that can call existing presenters/services directly. Before moving more code, prefer `ast` or targeted line-range extraction over encoding-sensitive shell rewrites.


## 2026-07-07 Execution Record 8: Master-Version Metadata Service Consolidation

This pass continued local-only slimming by moving the remaining master-version metadata projection logic out of `assets_panel.py` and into `src/services/material_assets/question_library.py`.

### Completed

- Exported the existing service metadata getters through `src/services/material_assets/__init__.py`:
  - `asset_metadata_package_id_value`
  - `asset_metadata_package_label_value`
  - `asset_metadata_version_value`
  - `asset_metadata_etag_value`
  - `asset_metadata_updated_at_value`
  - `asset_metadata_reference_value`
- Replaced the matching private `assets_panel.py` getter implementations with private aliases to the service functions.
- Added service functions for profile-level master-version promotion:
  - `question_figure_payload_index_for_question_row`
  - `promote_question_figure_master_version_to_profile`
- Replaced `_promote_question_figure_master_version_to_profile` and `_question_figure_payload_index_for_question_row` in `assets_panel.py` with service-backed legacy aliases.
- Added tests covering the newly public metadata getters and profile-level promotion behavior.
- Left `_set_optional_metadata_value` in `assets_panel.py` for now because the panel-local version still handles broader alias cleanup than the service setter.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 7,704 lines, 196 total functions/methods.
- `src/services/material_assets/question_library.py`: 2,213 lines, 58 functions.
- `src/services/material_assets/__init__.py`: 293 lines.
- `tests/test_material_asset_services.py`: 856 lines, 14 tests.
- `tests/test_assets_panel_architecture.py`: 152 lines, 9 functions, including 6 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\services\material_assets\question_library.py src\services\material_assets\__init__.py tests\test_material_asset_services.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_panel_architecture.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused metadata/service set: `23 passed`.
- Full related set: `55 passed`.

Residual scans:

```powershell
rg -n "def (_promote_question_figure_master_version_to_profile|_question_figure_payload_index_for_question_row|_asset_metadata_(package_id|package_label|version|etag|updated_at|reference)_value)" src/ui/panels/assets_panel.py
rg -n "remote writeback|remote_writeback|enterprise auth|enterprise_auth|signed URL|signed_url|external permission|external_permission|subscription drift|subscription_drift|failure recovery|failure_recovery|persistent worker|persistent_worker|durable worker|durable_worker|sla center|sla_center|registry sync|registry_sync|subscription lock|subscription_lock|subscription change|subscription_change|non-question asset family|non_question_asset_family|cross system writeback|cross-system writeback|REMOTE_WRITEBACK_TASK_POLICY_KEYS" src tests
```

Result: no matches.

### Next Step

Continue with small, local-only service moves. Best next target is to compare the broader `_set_optional_metadata_value` alias-cleanup behavior with the service setter and either widen the service implementation or leave the panel-local helper documented as a deliberate temporary exception.


## 2026-07-07 Execution Record 9: Optional Metadata Setter Consolidation

This pass resolved the temporary exception left in Execution Record 8.

### Completed

- Widened `src/services/material_assets/question_library.py::set_optional_metadata_value` so it now cleans the same extended alias groups previously handled only by `assets_panel.py`:
  - `asset_version`
  - `asset_etag`
  - `asset_updated_at`
  - `download_url`
  - `asset_url`
  - `thumbnail_url`
  - `preview_url`
  - `cache_path`
- Replaced the local `_set_optional_metadata_value` implementation in `assets_panel.py` with a service-backed legacy alias.
- Added a service test proving extended alias cleanup through the public `material_assets.set_optional_metadata_value` API.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 7,637 lines, 195 total functions/methods.
- `src/services/material_assets/question_library.py`: 2,271 lines, 58 functions.
- `src/services/material_assets/__init__.py`: 293 lines.
- `tests/test_material_asset_services.py`: 905 lines, 15 tests.
- `tests/test_assets_panel_architecture.py`: 152 lines, 9 functions, including 6 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\services\material_assets\question_library.py src\services\material_assets\__init__.py tests\test_material_asset_services.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_panel_architecture.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused metadata/service set: `24 passed`.
- Full related set: `56 passed`.

Residual scans:

```powershell
rg -n "def _set_optional_metadata_value|_set_optional_metadata_value\(" src/ui/panels/assets_panel.py src/ui/panels/assets tests
rg -n "remote writeback|remote_writeback|enterprise auth|enterprise_auth|signed URL|signed_url|external permission|external_permission|subscription drift|subscription_drift|failure recovery|failure_recovery|persistent worker|persistent_worker|durable worker|durable_worker|sla center|sla_center|registry sync|registry_sync|subscription lock|subscription_lock|subscription change|subscription_change|non-question asset family|non_question_asset_family|cross system writeback|cross-system writeback|REMOTE_WRITEBACK_TASK_POLICY_KEYS" src tests
```

Result: no matches.

### Next Step

Continue shrinking only the local-only pure helper surface. Good next candidates are `_mask_remote_asset_auth_value`, `_metadata_casefold_value`, and `_repeated_question_figure_status`, after confirming whether they belong in an existing service or in a small UI utility module.


## 2026-07-07 Execution Record 10: Pure Helper Cleanup and Repeated-Status Service Move

This pass completed the small helper cleanup identified after Execution Record 9, while keeping the work scoped to code slimming rather than control unification.

### Completed

- Removed the unused local `_metadata_casefold_value` helper from `assets_panel.py`.
- Moved `_repeated_question_figure_status` into `src/services/material_assets/question_figures.py` and exported it as `repeated_question_figure_status`.
- Kept the `assets_panel.py` legacy alias `_repeated_question_figure_status = repeated_question_figure_status` so the existing UI refresh path did not need a broader rewrite.
- Added service-level assertions proving the public API returns repeated question-figure status for `question_figure`, returns empty status for non-question roles, and points to the `question_figures` service implementation.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 7,578 lines, 192 functions/methods, 2 classes.
- `src/services/material_assets/question_library.py`: 2,271 lines, 58 functions.
- `src/services/material_assets/question_figures.py`: 736 lines, 33 functions.
- `src/services/material_assets/__init__.py`: 295 lines.
- `tests/test_material_asset_services.py`: 916 lines, 15 tests.
- `tests/test_assets_panel_architecture.py`: 152 lines, 9 functions, including 6 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\services\material_assets\question_figures.py src\services\material_assets\__init__.py tests\test_material_asset_services.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_panel_architecture.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused service/architecture/question-figure set: `24 passed`.
- Full related set: `56 passed`.

Residual scans:

```powershell
rg -n "def _mask_remote_asset_auth_value|def _metadata_casefold_value|def _repeated_question_figure_status|_repeated_question_figure_status =|repeated_question_figure_status" src/ui/panels/assets_panel.py src/services/material_assets/question_figures.py src/services/material_assets/__init__.py
rg -n "remote writeback|remote_writeback|enterprise auth|enterprise_auth|signed URL|signed_url|external permission|external_permission|subscription drift|subscription_drift|failure recovery|failure_recovery|persistent worker|persistent_worker|durable worker|durable_worker|sla center|sla_center|registry sync|registry_sync|subscription lock|subscription_lock|subscription change|subscription_change|non-question asset family|non_question_asset_family|cross system writeback|cross-system writeback|REMOTE_WRITEBACK_TASK_POLICY_KEYS" src tests
```

Result:

- `_mask_remote_asset_auth_value` and `_metadata_casefold_value` no longer exist.
- `_repeated_question_figure_status` now exists only as the service implementation plus a panel compatibility alias.
- Deleted enterprise writeback/governance keyword scan: no matches.


## 2026-07-07 Re-review: Should the Remaining Remote Preview/Auth Layer Be Deleted?

### Current Reality

The previous enterprise remote deletion was successful for the heavy product chain: remote writeback, enterprise auth renewal, signed URL refresh, external permission callback, subscription drift, registry sync, failure recovery, SLA, durable worker, manifest/report, conflict snapshot, rollback, and compensation are no longer active source capabilities.

What remains is a smaller read-only remote layer:

- `src/ui/panels/assets/auth.py`: parses and formats simple remote image download auth, limited to `Authorization`, `X-API-Key`, and `Cookie`.
- `src/ui/panels/assets_panel.py`: still renders remote asset auth inputs and passes headers into preview download.
- `src/services/material_assets/question_figures.py`: still recognizes HTTP/HTTPS preview URLs and can download remote preview images to a temp cache.
- `src/services/material_assets/question_library.py`, `cache_projection.py`, presenters, and batch import still understand metadata fields such as `download_url`, `asset_url`, `thumbnail_url`, and `preview_url`.

This is not the deleted enterprise writeback platform, but it is still remote-facing product surface. If the desired product is a local formatting tool with local images, this remaining layer is optional rather than core.

### Necessity Judgment

For the current product direction, the remaining read-only remote layer is not strictly necessary. It is useful only if users commonly paste protected CDN/material-library URLs and expect the app to fetch them for preview. Without that workflow, it adds:

- credential fields in the main image UI;
- network I/O and temp download behavior;
- URL metadata branches across question figures, cache projection, presenters, import aliases, and tests;
- extra product vocabulary that makes local asset management harder to understand.

The optimized recommendation is not to start with a broad keyword deletion. Delete active remote behavior first, then decide whether inert URL metadata compatibility still matters.

### Optimized Deletion Plan

Step 1: Remove active remote I/O and credentials.

- Delete the remote asset auth editor UI from `AssetsPanel`.
- Delete `src/ui/panels/assets/auth.py` if no other caller remains.
- Remove `REMOTE_ASSET_AUTH_*` constants from `specs.py`.
- Remove `_download_remote_asset_preview_image` and any `urlopen`-based preview download behavior.
- Update tests that currently assert "read-only remote preview auth remains narrow" to assert "remote preview auth is not exposed".

Step 2: Keep URL metadata inert for one pass.

- Keep `download_url`, `asset_url`, `thumbnail_url`, and `preview_url` as imported/stored metadata only if needed for backward compatibility with existing profiles.
- Do not use those fields to perform network download or show credential controls.
- Rename boundary language from `remote_preview_download` to an explicit compatibility decision, or remove that boundary if active preview is gone.

Step 3: Decide whether to go to strict local-only metadata.

- If existing data does not rely on URL metadata, remove URL import aliases and remote preview label helpers.
- If existing data does rely on URL metadata, keep them as passive labels only and document them as legacy metadata, not an active remote asset feature.

Step 4: Only after remote surface is settled, resume local simplification.

- Continue moving pure local question-figure helpers from `assets_panel.py` into services/presenters.
- Slim cache/audit rows around retained local workflows.
- Postpone control unification until the remote-facing product surface is gone or deliberately retained.

### Revised Next Step

The next code step should be "remove active remote preview/auth", not "unify controls". This is the highest-leverage simplification still left because it removes product surface, UI state, network behavior, tests, and service exports at the same time. The safer first target is the auth editor and `urlopen` preview download path; URL metadata aliases should be reviewed in a second pass to avoid breaking old profiles unnecessarily.


## 2026-07-07 Execution Record 11: Active Remote Preview/Auth Removal

This pass executed the revised next step from the re-review: remove active remote preview/auth instead of unifying controls.

### Completed

- Removed the remote asset auth editor from `AssetsPanel`:
  - no source/header/token inputs;
  - no remote auth status label;
  - no remote auth managed state.
- Deleted `src/ui/panels/assets/auth.py`.
- Removed `REMOTE_ASSET_AUTH_*`, `REMOTE_ASSET_PREVIEW_*`, and `REMOTE_ASSET_FULL_PREVIEW_*` constants from `src/ui/panels/assets/specs.py` and package exports.
- Removed the `urlopen`-based preview download helper from `src/services/material_assets/question_figures.py`.
- Removed `download_remote_asset_preview_image` from `src/services/material_assets/__init__.py`.
- Changed `AssetsPanel._set_remote_image_preview` so a remote URL now shows a local-only message instead of downloading.
- Changed full-image compare behavior so remote compare URLs are treated as passive metadata and are not fetched.
- Kept `download_url`, `asset_url`, `thumbnail_url`, and `preview_url` metadata compatibility intact for now.
- Added/updated tests so active remote preview/auth cannot silently return.

### Current Product Boundary

Deleted:

- credential UI for remote image downloads;
- remote auth parsing/formatting helpers;
- HTTP preview download;
- temp-cache writes caused by remote preview download;
- public material service export for remote preview download.

Retained as passive compatibility:

- HTTP/HTTPS URL detection;
- URL filename display;
- URL metadata fields used by older profiles and import data.

This means remote URLs can still appear as metadata, but the app no longer performs network I/O to preview them.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 7,413 lines, 188 functions/methods, 2 classes.
- `src/ui/panels/assets/specs.py`: 95 lines.
- `src/ui/panels/assets/enterprise_boundary.py`: 160 lines, 5 functions, 1 class.
- `src/services/material_assets/question_figures.py`: 639 lines, 31 functions.
- `src/services/material_assets/__init__.py`: 293 lines.
- `tests/test_material_asset_services.py`: 908 lines, 15 tests.
- `tests/test_assets_panel_architecture.py`: 153 lines, 6 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\specs.py src\ui\panels\assets\__init__.py src\ui\panels\assets\enterprise_boundary.py src\services\material_assets\question_figures.py src\services\material_assets\__init__.py tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_question_figures_presenter.py tests\test_assets_cache_presenter.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused active-remote removal set: `40 passed`.
- Full related set: `55 passed`.

Residual scan:

```powershell
rg -n "download_remote_asset_preview|_download_remote_asset_preview_image|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|REMOTE_ASSET_FULL_PREVIEW|src\.ui\.panels\.assets\.auth|from src\.ui\.panels\.assets import auth|urlopen|urllib\.request|urllib\.error" src/ui/panels/assets_panel.py src/ui/panels/assets src/services/material_assets tests/test_assets_panel_architecture.py tests/test_assets_enterprise_boundary.py tests/test_material_asset_services.py tests/test_assets_panel_helper_modules.py tests/test_assets_panel_specs.py tests/test_assets_panel_question_figures.py tests/test_assets_question_figures_presenter.py tests/test_assets_cache_presenter.py
```

Result: remaining matches are only guard assertions in tests; no active assets-panel or material-service implementation remains.

### Next Step

Review whether passive URL metadata compatibility should remain. If strict local-only is desired, the next deletion pass should remove URL import aliases and remote URL display helpers. If backward compatibility matters, keep URL metadata passive and resume slimming local-only question-figure/cache/audit helpers.


## 2026-07-07 Execution Record 12: Passive Remote URL Metadata Removal

This pass continued from Execution Record 11 and chose the strict local-only path. The goal was to remove URL import/display compatibility while preserving local material identity metadata such as `asset_id`, version fields, cache paths, thumbnails, and audit records.

### Completed

- Removed remote URL preview helpers from `src/services/material_assets/question_figures.py`:
  - no HTTP/HTTPS URL detector export;
  - no URL filename helper export;
  - no remote full/thumbnail/compare preview URL helpers;
  - no URL fallback from `asset_item_preview_reference`.
- Removed the corresponding public exports from `src/services/material_assets/__init__.py`.
- Removed compatibility exports for those helpers from `src/ui/panels/assets/question_figures.py`.
- Removed remote URL preview branches from:
  - `QuestionFigureItemsPresenterMixin`;
  - `QuestionFigureSharedCachePresenterMixin`;
  - `AssetsPanel` full-image compare path.
- Removed `_set_remote_image_preview` from `AssetsPanel`.
- Removed URL/Auth import aliases from `src/ui/panels/assets/batch_import.py`.
- Removed `download_url` as a cache-index/source/status signal in `cache_projection.py`.
- Updated `question_library.py` so:
  - URL fields no longer make an item count as having library metadata;
  - URL fields no longer become library references;
  - master-version promotion does not copy URL fields forward;
  - `set_optional_metadata_value(..., "preview_url" / "download_url" / etc.)` clears old URL aliases instead of writing them.
- Removed the `remote_url_metadata_compatibility` boundary entry.
- Updated tests so URL preview helpers and URL import aliases cannot silently return.

### Current Product Boundary

Retained:

- `asset_id` / `assetId` as a local material identity key;
- source/library labels;
- version, etag, updated-at, alt text;
- local `cache_path`, `cachedPath`, thumbnail/cache paths;
- local repair/audit/cache rows.

Removed:

- URL-as-preview fallback;
- URL display-name helper;
- URL import aliases such as `downloadurl`, `remoteurl`, `previewurl`, `thumbnailurl`;
- remote URL cache-source/status projection;
- remote URL compatibility boundary.

Remaining URL strings in implementation are only in `_REMOVED_URL_METADATA_ALIAS_KEYS`, which exists to strip old URL fields during metadata updates. They are not an import, display, preview, or network path.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 7,352 lines, 187 functions/methods, 2 classes.
- `src/ui/panels/assets/batch_import.py`: 613 lines, 30 functions.
- `src/ui/panels/assets/enterprise_boundary.py`: 149 lines, 5 functions, 1 class.
- `src/services/material_assets/question_figures.py`: 515 lines, 24 functions.
- `src/services/material_assets/question_library.py`: 2,250 lines, 59 functions.
- `src/services/material_assets/cache_projection.py`: 1,160 lines, 38 functions.
- `src/services/material_assets/__init__.py`: 279 lines.
- `tests/test_material_asset_services.py`: 901 lines, 15 tests.
- `tests/test_assets_panel_architecture.py`: 168 lines, 6 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\batch_import.py src\ui\panels\assets\cache_presenter.py src\ui\panels\assets\question_figures.py src\ui\panels\assets\question_figures_presenter.py src\ui\panels\assets\enterprise_boundary.py src\services\material_assets\question_figures.py src\services\material_assets\question_library.py src\services\material_assets\cache_projection.py src\services\material_assets\__init__.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_question_figures_presenter.py tests\test_assets_cache_presenter.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused strict-local URL removal set: `40 passed`.
- Full related set: `55 passed`.

Residual scans:

```powershell
rg -n "is_remote_asset_preview_url|remote_asset_url_name|asset_item_remote_(compare|full|thumbnail|preview)|download_remote_asset_preview|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|urlopen|urllib\.request|urllib\.error" src/ui/panels/assets_panel.py src/ui/panels/assets src/services/material_assets
rg -n "downloadurl|remoteurl|asseturl|sourceurl|originalurl|thumbnailurl|previewurl|remotepreviewurl|assetpreviewurl|authmode|remoteauth|download_url|downloadUrl|asset_url|assetUrl|thumbnail_url|thumbnailUrl|preview_url|previewUrl|full_preview_url|remote_preview_url" src/ui/panels/assets_panel.py src/ui/panels/assets src/services/material_assets
```

Result:

- No active remote preview/auth/helper/network matches.
- URL field matches remain only in `question_library.py::_REMOVED_URL_METADATA_ALIAS_KEYS`, the cleanup table used to remove old metadata aliases.

### Next Step

Resume local-only slimming. The next useful target is to continue moving pure local question-figure/cache/audit helpers out of `AssetsPanel`, while avoiding any further work on deleted remote URL or enterprise flows.


## 2026-07-07 Execution Record 13: Local Image/Role Helper Consolidation

This pass resumed local-only slimming after remote preview/auth and URL metadata removal. It intentionally avoided control unification and focused on small pure helpers that were still implemented directly in `assets_panel.py`.

### Completed

- Added `src/ui/panels/assets/image_helpers.py` for local image helper logic:
  - `_asset_role_min_short_side`
  - `_first_image_path_from_mime`
- Moved `_asset_slot_supports_alt_text` into `src/ui/panels/assets/roles.py`.
- Updated `assets_panel.py` to import those helpers instead of defining them locally.
- Removed three dead `assets_panel.py` metadata helpers:
  - `_asset_metadata_asset_id_value`
  - `_asset_metadata_source_value`
  - `_asset_metadata_alt_text_value`
- Removed the now-unused `SUPPORTED_IMAGE_SUFFIXES` import from `assets_panel.py`.
- Updated helper-module tests so the extracted helper boundaries are guarded.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 7,271 lines, 181 functions/methods, 2 classes.
- `src/ui/panels/assets/image_helpers.py`: 37 lines, 2 functions.
- `src/ui/panels/assets/roles.py`: 112 lines, 10 functions.
- `src/services/material_assets/question_figures.py`: 515 lines, 24 functions.
- `src/services/material_assets/question_library.py`: 2,250 lines, 59 functions.
- `src/services/material_assets/__init__.py`: 279 lines.
- `tests/test_assets_panel_helper_modules.py`: 42 lines, 2 tests.
- `tests/test_material_asset_services.py`: 901 lines, 15 tests.
- `tests/test_assets_panel_architecture.py`: 168 lines, 6 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\image_helpers.py src\ui\panels\assets\roles.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused helper/module set: `26 passed`.
- Full related set: `55 passed`.

Residual scan:

```powershell
rg -n "def _asset_metadata_asset_id_value|def _asset_metadata_source_value|def _asset_metadata_alt_text_value|def _asset_role_min_short_side|def _first_image_path_from_mime|def _asset_slot_supports_alt_text" src/ui/panels/assets_panel.py src/ui/panels/assets/image_helpers.py src/ui/panels/assets/roles.py
rg -n "is_remote_asset_preview_url|remote_asset_url_name|asset_item_remote_(compare|full|thumbnail|preview)|download_remote_asset_preview|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|urlopen|urllib\.request|urllib\.error" src/ui/panels/assets_panel.py src/ui/panels/assets src/services/material_assets
```

Result:

- The migrated image/role helpers now exist only in helper modules, not in `assets_panel.py`.
- The dead `_asset_metadata_*` helpers no longer exist in `assets_panel.py`.
- Deleted remote preview/auth/network surface remains absent.

### Next Step

Continue local-only slimming with the remaining top-level helpers in `assets_panel.py`: replacement text parsing/formatting, image-rule formatting, scaled pixmap loading, image-quality text, and form-row chunking. Move only stable pure helpers; leave UI methods in place until their dependencies are clearer.


## 2026-07-07 Execution Record 14: Remaining Top-Level Helper Extraction

This pass finished the immediate top-level helper cleanup in `assets_panel.py`. After this pass, the panel module no longer defines standalone top-level functions; it imports helper logic from focused modules and keeps the large class as the remaining orchestration surface.

### Completed

- Added `src/ui/panels/assets/text_helpers.py`:
  - `_parse_replacements_text`
  - `_format_replacements_text`
  - `_format_image_rules_text`
- Added `src/ui/panels/assets/layout_helpers.py`:
  - `_chunk_form_rows`
- Extended `src/ui/panels/assets/image_helpers.py`:
  - `_load_scaled_pixmap`
  - `_image_quality_text`
- Updated `assets_panel.py` to import those helpers.
- Removed the remaining top-level helper implementations from `assets_panel.py`.
- Updated helper-module boundary tests to guard the extracted helper ownership.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 5,989 lines, 175 functions/methods, 2 classes, 0 top-level functions.
- `src/ui/panels/assets/image_helpers.py`: 69 lines, 4 functions.
- `src/ui/panels/assets/layout_helpers.py`: 13 lines, 1 function.
- `src/ui/panels/assets/text_helpers.py`: 38 lines, 3 functions.
- `src/ui/panels/assets/roles.py`: 112 lines, 10 functions.
- `tests/test_assets_panel_helper_modules.py`: 56 lines, 2 tests.
- `tests/test_assets_panel_architecture.py`: 168 lines, 6 tests.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\image_helpers.py src\ui\panels\assets\layout_helpers.py src\ui\panels\assets\text_helpers.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused helper/module set: `26 passed`.
- Full related set: `55 passed`.

Residual scans:

```powershell
python -c "import ast; from pathlib import Path; mod=ast.parse(Path('src/ui/panels/assets_panel.py').read_text(encoding='utf-8')); print(sum(isinstance(n, ast.FunctionDef) for n in mod.body))"
rg -n "^def " src/ui/panels/assets_panel.py
rg -n "is_remote_asset_preview_url|remote_asset_url_name|asset_item_remote_(compare|full|thumbnail|preview)|download_remote_asset_preview|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|urlopen|urllib\.request|urllib\.error" src/ui/panels/assets_panel.py src/ui/panels/assets src/services/material_assets
```

Result:

- `assets_panel.py` top-level function count: `0`.
- No `^def` matches in `assets_panel.py`.
- Deleted remote preview/auth/network surface remains absent.

### Next Step

The next slimming target is method-level orchestration inside `AssetsPanel`. Prioritize cohesive method groups with clear ownership, such as full-image preview/dialog behavior or archive/profile CRUD helpers. Continue avoiding broad UI rewrites; move one method group at a time behind a presenter or helper module and keep the focused regression set green.


## 2026-07-07 方案复审优化：企业远程删除已收口，进入本地方法级瘦身

本次复审把用户提出的核心判断重新落到当前代码状态上：企业远程相关能力不是当前本地格式化工具的必要能力；前面多轮删除已经把这条链路从“主产品能力”降为“已删除能力的守门和少量兼容清理”。因此后续不应继续围绕远程写回、企业鉴权、订阅漂移做拆包或控件整理，而应把注意力转到剩余本地代码的可维护性。

### 当前事实快照

- `src/ui/panels/assets_panel.py` 当前约 5,990 行，175 个函数/方法，2 个类，0 个顶层函数。
- `src/services/material_assets/question_library.py` 当前约 2,251 行，59 个函数。
- `enterprise_boundary.py` 只剩 3 类保留能力：`local_question_figures`、`local_question_audit`、`lightweight_shared_cache`。
- `tests/test_assets_panel_architecture.py` 已经把已删除能力列为守门 token：`remote_writeback`、`enterprise_auth`、`signed_url`、`external_permission`、`master_registry`、`registry_sync`、`subscription_lock`、`subscription_change`、`subscription_drift`、`failure_recovery`、`persistent_worker`、`durable_worker`、`sla_center` 等不能回到面板或服务。
- 当前 `rg` 复查里，`remote_writeback` / `enterprise_auth` / `signed_url` / `external_permission` / `subscription_drift` 等只在文档或测试守门语境中出现，不再是源码里的执行链路。
- 仍存在的 `remote_asset_id` / `asset_item_remote_asset_id` 应理解为素材身份兼容字段，不是远程写回能力。它服务本地题图匹配、历史记录和缓存索引，不应和企业远程链路一起误删。
- 仍存在的 `remote_asset_download_auth` 只在 `_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS` 清理表中，用来剥离旧资料里的下载凭证字段；它不是 UI、网络请求或远程鉴权入口。

### 对原删除方案的修正

原“四刀”方案的方向是正确的：先删非题图远端治理，再删远程写回和企业鉴权，再删远端主数据订阅，最后删订阅漂移/恢复治理。现在这些能力已经基本完成主链路删除，文档后续不能再把它们当作待重构模块。

新的判断是：

- 不再为已删除的企业远程能力设计 presenter、service、spec 或统一控件。
- 不再扩大 `enterprise_boundary.py` 的 `freeze` / `delete_candidate` 分类；当前边界应继续只描述保留的本地能力。
- 对残留 remote 命名必须逐项判定语义：身份字段、旧字段剥离表可以短期保留；下载、鉴权、写回、权限回调、订阅治理入口不能恢复。
- 后续优化应从“删除非必要产品能力”切换为“压缩本地面板编排复杂度”。

### 下一阶段执行顺序

第一优先级：抽出 `AssetsPanel` 内部的成组 UI 方法。

- 首选 full-image preview/dialog 方法组：当前聚合在 `_set_current_image_preview_path`、`_configure_full_image_preview_tool_button`、`_refresh_full_image_preview_zoom_label`、`_refresh_full_image_preview_pixmap`、`_set_full_image_preview_zoom`、`_zoom_full_image_preview`、`_reset_full_image_preview_zoom`、`_fit_full_image_preview_to_window`、`_selected_full_image_preview_compare_option`、`_open_full_image_preview_compare`、`_current_full_image_preview_region_payload`、`_current_full_image_preview_region_summary`、`_mark_current_full_image_preview_compare_issue`、`_open_current_image_preview_dialog`。
- 目标不是减少产品能力，而是把一组局部 UI 状态和行为迁到 `image_preview_presenter.py` 或等价 mixin，使 `AssetsPanel` 不再承载所有方法。
- 这一刀风险较低，因为该组已经是本地图片预览，不依赖已删除的远程下载链路。

第二优先级：再处理 archive/profile CRUD。

- 包括 `_new_archive`、`_duplicate_archive`、`_rename_archive`、`_open_archive_folder`、`_delete_archive`、`_load_archive_dialog`、`_save_archive_dialog`、`_reload_profile_list`、`_load_profile_to_editor`、`_add_profile`、`_copy_current_profile`、`_remove_current_profile` 等。
- 这组比图片预览风险高，因为它涉及实体归档、配置持久化、profile editor 同步，必须等第一组方法迁移验证稳定后再做。

第三优先级：审查兼容清理表和命名。

- `_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS` 可以保留到资料迁移稳定；若后续确认不需要兼容旧资料，再删除或下沉到 metadata migration 模块。
- `asset_item_remote_asset_id` 可考虑在更晚阶段以 `asset_item_library_asset_id` 或 `asset_item_external_asset_id` 之类更中性的命名替代，但这属于 API 迁移，不应和方法瘦身混在同一刀。

### 每一刀的验收条件

- 不新增企业远程关键词，不恢复网络下载、鉴权、写回、订阅、SLA、worker 入口。
- `assets_panel.py` 行数和方法数继续下降，且没有重新出现顶层函数。
- 新模块只承载一个清晰职责，不把大面板复制成另一个大面板。
- 聚焦回归至少覆盖：`test_assets_panel_helper_modules.py`、`test_assets_panel_architecture.py`、`test_material_asset_services.py`、`test_assets_panel_question_figures.py`。
- 完整相关回归继续覆盖：enterprise boundary、material services、helper modules、specs、question figures、question cache、question audit、question library presenter、cache presenter、question figures presenter、assets panel architecture、scene product maturity audit。

### 复审结论

企业远程能力已经不是下一步主要矛盾；它应被测试守门防止回流，而不是继续被重构。接下来要优化健康结构，应小步抽离 `AssetsPanel` 的本地 UI 方法组，先拿图片预览这类边界清晰的局部行为开刀，再进入归档/profile CRUD。控件统一仍然延后，等剩下的产品能力稳定且面板方法数继续下降后再做。


## 2026-07-07 Execution Record 15: Full-Image Preview Presenter Extraction

This pass executed the first method-level slimming step after enterprise-remote removal was closed. The target was the cohesive full-image preview/dialog method group inside `AssetsPanel`.

### Completed

- Added `src/ui/panels/assets/image_preview_presenter.py`.
- Introduced `ImagePreviewPresenterMixin` for local full-image preview behavior.
- Moved 14 methods out of `AssetsPanel`:
  - `_set_current_image_preview_path`
  - `_configure_full_image_preview_tool_button`
  - `_refresh_full_image_preview_zoom_label`
  - `_refresh_full_image_preview_pixmap`
  - `_set_full_image_preview_zoom`
  - `_zoom_full_image_preview`
  - `_reset_full_image_preview_zoom`
  - `_fit_full_image_preview_to_window`
  - `_selected_full_image_preview_compare_option`
  - `_open_full_image_preview_compare`
  - `_current_full_image_preview_region_payload`
  - `_current_full_image_preview_region_summary`
  - `_mark_current_full_image_preview_compare_issue`
  - `_open_current_image_preview_dialog`
- Updated `AssetsPanel` to inherit `ImagePreviewPresenterMixin` before the existing presenter mixins.
- Added a helper-module test that verifies the moved methods are inherited from `ImagePreviewPresenterMixin` and are no longer defined directly on `AssetsPanel`.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 5,445 lines, 161 functions/methods, 2 classes, 0 top-level functions.
- `AssetsPanel`: 157 direct methods.
- `src/ui/panels/assets/image_preview_presenter.py`: 588 lines, 14 methods, 1 class, 0 top-level functions.
- `tests/test_assets_panel_helper_modules.py`: 85 lines, 3 tests.

Compared with Execution Record 14:

- `assets_panel.py` dropped from 5,989 lines to 5,445 lines.
- Total functions/methods inside `assets_panel.py` dropped from 175 to 161.
- The 14 moved methods now belong to a focused local preview presenter.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\image_preview_presenter.py
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\image_preview_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused preview/helper regression: `27 passed`.
- Full related regression: `56 passed`.

Residual scans:

```powershell
rg -n "def _set_current_image_preview_path|def _configure_full_image_preview_tool_button|def _refresh_full_image_preview_zoom_label|def _refresh_full_image_preview_pixmap|def _set_full_image_preview_zoom|def _zoom_full_image_preview|def _reset_full_image_preview_zoom|def _fit_full_image_preview_to_window|def _selected_full_image_preview_compare_option|def _open_full_image_preview_compare|def _current_full_image_preview_region_payload|def _current_full_image_preview_region_summary|def _mark_current_full_image_preview_compare_issue|def _open_current_image_preview_dialog|ImagePreviewPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\image_preview_presenter.py tests\test_assets_panel_helper_modules.py
rg -n "is_remote_asset_preview_url|remote_asset_url_name|asset_item_remote_(compare|full|thumbnail|preview)|download_remote_asset_preview|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|urlopen|urllib\.request|urllib\.error|remote_writeback|enterprise_auth|signed_url|external_permission|subscription_drift" src\ui\panels\assets_panel.py src\ui\panels\assets src\services\material_assets
```

Result:

- Full-image preview methods are defined only in `image_preview_presenter.py`.
- `assets_panel.py` only imports and inherits `ImagePreviewPresenterMixin`.
- The deleted remote preview/auth/network/writeback surface remains absent from source implementation.

### Next Step

Continue method-level slimming with the next cohesive local group. The recommended next target is archive/profile CRUD, but it is riskier than image preview because it touches persistence and editor synchronization. Before moving it, map the exact call chain around `_sync_archive_selector`, `_selected_profile`, `_persist_current_profile_editor`, `_reload_profile_list`, `_load_profile_to_editor`, `_new_archive`, `_duplicate_archive`, `_rename_archive`, `_delete_archive`, `_add_profile`, `_copy_current_profile`, and `_remove_current_profile`.


## 2026-07-07 Execution Record 16: Archive Presenter Extraction

This pass continued method-level slimming, but deliberately split archive CRUD from profile editor CRUD. Archive package actions are a cohesive local group; profile list/editor synchronization remains in `AssetsPanel` for a later, more careful pass.

### Completed

- Added `src/ui/panels/assets/archive_presenter.py`.
- Introduced `ArchivePresenterMixin` for archive package actions.
- Moved 11 methods out of `AssetsPanel`:
  - `_archive_display_name`
  - `_sync_archive_selector`
  - `_on_archive_selector_changed`
  - `_blank_archive`
  - `_new_archive`
  - `_duplicate_archive`
  - `_rename_archive`
  - `_open_archive_folder`
  - `_delete_archive`
  - `_load_archive_dialog`
  - `_save_archive_dialog`
- Updated `AssetsPanel` to inherit `ArchivePresenterMixin` before the existing presenter mixins.
- Added a helper-module test that verifies the archive methods are inherited from `ArchivePresenterMixin` and are no longer defined directly on `AssetsPanel`.
- Left `_load_batch_profiles_dialog`, profile list methods, and profile editor synchronization in `AssetsPanel`; they belong to the next profile-focused pass.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 5,314 lines, 150 functions/methods, 2 classes, 0 top-level functions.
- `AssetsPanel`: 146 direct methods.
- `src/ui/panels/assets/archive_presenter.py`: 152 lines, 11 methods, 1 class, 0 top-level functions.
- `src/ui/panels/assets/image_preview_presenter.py`: 588 lines, 14 methods, 1 class, 0 top-level functions.
- `tests/test_assets_panel_helper_modules.py`: 110 lines, 4 tests.

Compared with Execution Record 15:

- `assets_panel.py` dropped from 5,445 lines to 5,314 lines.
- Total functions/methods inside `assets_panel.py` dropped from 161 to 150.
- `AssetsPanel` direct methods dropped to 146.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\archive_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
python -m pytest -q tests\test_material_execution_context.py::test_assets_panel_material_context_scans_images_from_rules tests\test_material_execution_context.py::test_assets_panel_loads_json_mapping_into_fields_and_replacements
```

Results:

- Focused archive/helper regression: `28 passed`.
- Full related assets regression: `57 passed`.
- Narrow AssetsPanel material-context regression: `2 passed`.

Residual scans:

```powershell
rg -n "def _archive_display_name|def _sync_archive_selector|def _on_archive_selector_changed|def _blank_archive|def _new_archive|def _duplicate_archive|def _rename_archive|def _open_archive_folder|def _delete_archive|def _load_archive_dialog|def _save_archive_dialog|ArchivePresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\archive_presenter.py tests\test_assets_panel_helper_modules.py
rg -n "is_remote_asset_preview_url|remote_asset_url_name|asset_item_remote_(compare|full|thumbnail|preview)|download_remote_asset_preview|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|urlopen|urllib\.request|urllib\.error|remote_writeback|enterprise_auth|signed_url|external_permission|subscription_drift" src\ui\panels\assets_panel.py src\ui\panels\assets src\services\material_assets
```

Result:

- Archive CRUD methods are defined only in `archive_presenter.py`.
- `assets_panel.py` only imports and inherits `ArchivePresenterMixin`.
- The deleted enterprise-remote surface remains absent from source implementation.

### Next Step

Continue with profile editor/list methods, but keep the cut narrower than the full profile surface. Recommended next target:

- `_persist_current_profile_editor`
- `_reload_profile_list`
- `_update_profile_item`
- `_refresh_profile_item_labels`
- `_select_profile_for_repair`
- `_on_profile_row_changed`
- `_on_profile_item_changed`
- `_load_profile_to_editor`
- `_add_profile`
- `_copy_current_profile`
- `_has_only_empty_profile`
- `_normalize_imported_profile`
- `_next_profile_id`
- `_remove_current_profile`

Before moving, inspect interactions with `load_batch_profiles_from_path`, `set_archive`, `selected_batch_profile_ids`, and `_sync_material_batch_selection`, because those call profile list/editor state from outside the candidate block.


## 2026-07-07 Execution Record 17: Profile Presenter Extraction

This pass moved the profile editor/list method group after verifying that it is not a single contiguous source block. The extraction used individual AST method boundaries so batch output naming methods could remain in `AssetsPanel`.

### Completed

- Added `src/ui/panels/assets/profile_presenter.py`.
- Introduced `ProfilePresenterMixin` for profile list state, editor persistence, profile copy/add/remove, and imported-profile normalization.
- Moved 14 methods out of `AssetsPanel`:
  - `_persist_current_profile_editor`
  - `_reload_profile_list`
  - `_update_profile_item`
  - `_refresh_profile_item_labels`
  - `_select_profile_for_repair`
  - `_on_profile_row_changed`
  - `_on_profile_item_changed`
  - `_load_profile_to_editor`
  - `_add_profile`
  - `_copy_current_profile`
  - `_has_only_empty_profile`
  - `_normalize_imported_profile`
  - `_next_profile_id`
  - `_remove_current_profile`
- Updated `AssetsPanel` to inherit `ProfilePresenterMixin` after `ImagePreviewPresenterMixin` and before the question-figure/library presenter mixins.
- Added a helper-module test that verifies the profile methods are inherited from `ProfilePresenterMixin` and are no longer defined directly on `AssetsPanel`.
- Kept batch output naming methods in `AssetsPanel`:
  - `_on_batch_output_template_changed`
  - `_on_batch_output_naming_changed`
  - `_batch_output_template`
  - `_current_batch_output_naming_template`
  - `_select_batch_output_naming_for_template`
- Kept broader profile-facing entrypoints in `AssetsPanel`, including `load_batch_profiles_from_path`, `_apply_current_profile`, `focus_material_profile_repair_target`, `selected_batch_profile_ids`, `_selected_profile`, and `_asset_items_for_profile`.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 5,105 lines, 136 functions/methods, 2 classes, 0 top-level functions.
- `AssetsPanel`: 132 direct methods.
- `src/ui/panels/assets/profile_presenter.py`: 253 lines, 14 methods, 1 class, 0 top-level functions.
- `src/ui/panels/assets/archive_presenter.py`: 152 lines, 11 methods, 1 class, 0 top-level functions.
- `src/ui/panels/assets/image_preview_presenter.py`: 588 lines, 14 methods, 1 class, 0 top-level functions.
- `tests/test_assets_panel_helper_modules.py`: 138 lines, 5 tests.

Compared with Execution Record 16:

- `assets_panel.py` dropped from 5,314 lines to 5,105 lines.
- Total functions/methods inside `assets_panel.py` dropped from 150 to 136.
- `AssetsPanel` direct methods dropped to 132.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\profile_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_material_execution_context.py::test_assets_panel_material_context_scans_images_from_rules tests\test_material_execution_context.py::test_assets_panel_loads_json_mapping_into_fields_and_replacements
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused profile/helper regression: `29 passed`.
- Narrow AssetsPanel material-context regression: `2 passed`.
- Full related assets regression: `58 passed`.

Residual scans:

```powershell
rg -n "def _persist_current_profile_editor|def _reload_profile_list|def _update_profile_item|def _refresh_profile_item_labels|def _select_profile_for_repair|def _on_profile_row_changed|def _on_profile_item_changed|def _load_profile_to_editor|def _add_profile|def _copy_current_profile|def _has_only_empty_profile|def _normalize_imported_profile|def _next_profile_id|def _remove_current_profile|ProfilePresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\profile_presenter.py tests\test_assets_panel_helper_modules.py
rg -n "is_remote_asset_preview_url|remote_asset_url_name|asset_item_remote_(compare|full|thumbnail|preview)|download_remote_asset_preview|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|urlopen|urllib\.request|urllib\.error|remote_writeback|enterprise_auth|signed_url|external_permission|subscription_drift" src\ui\panels\assets_panel.py src\ui\panels\assets src\services\material_assets
```

Result:

- Profile editor/list methods are defined only in `profile_presenter.py`.
- `assets_panel.py` only imports and inherits `ProfilePresenterMixin`.
- Batch output naming methods and broader profile entrypoints remain in `AssetsPanel` intentionally.
- The deleted enterprise-remote surface remains absent from source implementation.

### Next Step

The next slimming target should be chosen from the remaining `AssetsPanel` direct methods, now at 132. Good candidates are:

- Batch output naming and batch selection methods, if they can be isolated without pulling in generation summary refresh.
- Material repair/navigation methods, if they can be separated from card focus/highlight helpers.
- Asset slot/attachment row construction methods, but these touch UI construction and styling more broadly, so they should be mapped before moving.

Avoid moving `_refresh_summary` yet; it remains a high-fan-in orchestration method and should be reduced only after more presenter groups are extracted.


## 2026-07-07 Execution Record 18: Batch Output Presenter Extraction

This pass extracted the batch output and batch selection method group. It intentionally left the broader batch profile import execution method in `AssetsPanel`, because `load_batch_profiles_from_path` still coordinates profile normalization, list replacement, summary refresh, and material-batch synchronization.

### Completed

- Added `src/ui/panels/assets/batch_output_presenter.py`.
- Introduced `BatchOutputPresenterMixin` for batch generation, selection, output naming, preview, and bridge synchronization.
- Moved 12 methods out of `AssetsPanel`:
  - `_open_batch_generation`
  - `material_batch_selection`
  - `selected_batch_profile_ids`
  - `batch_output_preview`
  - `_load_batch_profiles_dialog`
  - `_on_batch_output_template_changed`
  - `_on_batch_output_naming_changed`
  - `_batch_output_template`
  - `_current_batch_output_naming_template`
  - `_select_batch_output_naming_for_template`
  - `_shared_batch_context`
  - `_sync_material_batch_selection`
- Updated `AssetsPanel` to inherit `BatchOutputPresenterMixin` after `ArchivePresenterMixin`.
- Added a helper-module test that verifies batch output methods are inherited from `BatchOutputPresenterMixin` and are no longer defined directly on `AssetsPanel`.
- Kept `load_batch_profiles_from_path` in `AssetsPanel` intentionally.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 4,987 lines, 124 functions/methods, 2 classes, 0 top-level functions.
- `AssetsPanel`: 120 direct methods.
- `src/ui/panels/assets/batch_output_presenter.py`: 152 lines, 12 methods, 1 class, 0 top-level functions.
- `src/ui/panels/assets/profile_presenter.py`: 253 lines, 14 methods, 1 class, 0 top-level functions.
- `src/ui/panels/assets/archive_presenter.py`: 152 lines, 11 methods, 1 class, 0 top-level functions.
- `src/ui/panels/assets/image_preview_presenter.py`: 588 lines, 14 methods, 1 class, 0 top-level functions.
- `tests/test_assets_panel_helper_modules.py`: 164 lines, 6 tests.

Compared with Execution Record 17:

- `assets_panel.py` dropped from 5,105 lines to 4,987 lines.
- Total functions/methods inside `assets_panel.py` dropped from 136 to 124.
- `AssetsPanel` direct methods dropped to 120.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\batch_output_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_material_execution_context.py::test_assets_panel_material_context_scans_images_from_rules tests\test_material_execution_context.py::test_assets_panel_loads_json_mapping_into_fields_and_replacements tests\test_material_execution_context.py::test_material_batch_items_build_profile_contexts_and_output_dirs
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused batch/helper regression: `30 passed`.
- Narrow AssetsPanel/batch material-context regression: `3 passed`.
- Full related assets regression: `59 passed`.

Residual scans:

```powershell
rg -n "def _open_batch_generation|def material_batch_selection|def selected_batch_profile_ids|def batch_output_preview|def _load_batch_profiles_dialog|def _on_batch_output_template_changed|def _on_batch_output_naming_changed|def _batch_output_template|def _current_batch_output_naming_template|def _select_batch_output_naming_for_template|def _shared_batch_context|def _sync_material_batch_selection|BatchOutputPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\batch_output_presenter.py tests\test_assets_panel_helper_modules.py
rg -n "is_remote_asset_preview_url|remote_asset_url_name|asset_item_remote_(compare|full|thumbnail|preview)|download_remote_asset_preview|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|urlopen|urllib\.request|urllib\.error|remote_writeback|enterprise_auth|signed_url|external_permission|subscription_drift" src\ui\panels\assets_panel.py src\ui\panels\assets src\services\material_assets
```

Result:

- Batch output/selection methods are defined only in `batch_output_presenter.py`.
- `assets_panel.py` only imports and inherits `BatchOutputPresenterMixin`.
- The deleted enterprise-remote surface remains absent from source implementation.

### Next Step

Continue method-level slimming, but avoid `_refresh_summary` until more surrounding helpers are extracted. The best next candidate is the material repair/navigation/focus group:

- `focus_material_repair_target`
- `handle_navigation_intent`
- `_set_return_navigation_intent`
- `_navigate_return_target`
- `focus_material_profile_repair_target`
- `apply_material_profile_question_figure_repair_candidate`
- `_on_material_repair_target_requested`
- `_on_material_profile_repair_target_requested`
- `_on_material_profile_repair_candidate_requested`
- `_focus_pending_material_repair_target`
- `_next_missing_target`
- `_focus_asset_slot`
- `_focus_attachment_role`
- `_attachment_role_for_token`
- `_focus_question_figure_item`
- `_question_figure_item_row_for_target`
- `_question_figure_item_row_for_repair_audit_record`
- `_material_role_label`
- `_show_missing_target`
- `_jump_to_card`
- `_select_section_for_card`
- `_select_section`
- `_highlight_attention_card`
- `_settle_attention_card`
- `_ensure_widget_visible`

This group is larger than batch output and touches UI focus/highlight state, so inspect dependencies before moving.


## 2026-07-07 Execution Record 19: Material Repair Navigation Presenter Extraction

This pass extracted the material repair navigation and focus group. The group was contiguous and cohesive: it consumes repair targets, routes navigation intents, focuses missing fields/assets/question figures, and coordinates attention-card highlighting.

### Completed

- Added `src/ui/panels/assets/material_repair_navigation_presenter.py`.
- Introduced `MaterialRepairNavigationMixin` for material repair target routing and UI focus behavior.
- Moved 26 methods out of `AssetsPanel`:
  - `_focus_missing_content`
  - `focus_material_repair_target`
  - `handle_navigation_intent`
  - `_set_return_navigation_intent`
  - `_navigate_return_target`
  - `focus_material_profile_repair_target`
  - `apply_material_profile_question_figure_repair_candidate`
  - `_on_material_repair_target_requested`
  - `_on_material_profile_repair_target_requested`
  - `_on_material_profile_repair_candidate_requested`
  - `_focus_pending_material_repair_target`
  - `_next_missing_target`
  - `_focus_asset_slot`
  - `_focus_attachment_role`
  - `_attachment_role_for_token`
  - `_focus_question_figure_item`
  - `_question_figure_item_row_for_target`
  - `_question_figure_item_row_for_repair_audit_record`
  - `_material_role_label`
  - `_show_missing_target`
  - `_jump_to_card`
  - `_select_section_for_card`
  - `_select_section`
  - `_highlight_attention_card`
  - `_settle_attention_card`
  - `_ensure_widget_visible`
- Updated `AssetsPanel` to inherit `MaterialRepairNavigationMixin` after `ImagePreviewPresenterMixin`.
- Added helper-module tests for:
  - ownership of the full material repair navigation mixin;
  - preview missing-target methods;
  - asset focus methods;
  - question-figure target methods;
  - bridge target consumption methods;
  - focus/card methods.
- Updated `src/config/scene_material_repair_flow_audit.py` evidence paths and test IDs so the audit points to the new presenter and current helper tests instead of stale `assets_panel.py` direct-method markers.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 4,627 lines, 98 functions/methods, 2 classes, 0 top-level functions.
- `AssetsPanel`: 94 direct methods.
- `src/ui/panels/assets/material_repair_navigation_presenter.py`: 390 lines, 26 methods, 1 class, 0 top-level functions.
- `src/ui/panels/assets/batch_output_presenter.py`: 152 lines, 12 methods, 1 class, 0 top-level functions.
- `tests/test_assets_panel_helper_modules.py`: 249 lines, 12 tests.
- `src/config/scene_material_repair_flow_audit.py`: 915 lines, 31 functions, 6 classes.

Compared with Execution Record 18:

- `assets_panel.py` dropped from 4,987 lines to 4,627 lines.
- Total functions/methods inside `assets_panel.py` dropped from 124 to 98.
- `AssetsPanel` direct methods dropped from 120 to 94.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\material_repair_navigation_presenter.py tests\test_assets_panel_helper_modules.py
python -m py_compile src\config\scene_material_repair_flow_audit.py tests\test_assets_panel_helper_modules.py src\ui\panels\assets\material_repair_navigation_presenter.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_material_schema_registry.py::test_material_requirement_evaluation_merges_schema_and_scene_overrides tests\test_material_schema_registry.py::test_material_requirements_merge_multiple_schema_ids
python -m pytest -q tests\test_material_execution_context.py::test_assets_panel_material_context_scans_images_from_rules tests\test_material_execution_context.py::test_assets_panel_loads_json_mapping_into_fields_and_replacements tests\test_scene_material_repair_flow_audit.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused material repair navigation/helper regression: `36 passed`.
- Material schema evidence regression: `2 passed`.
- Scene material repair flow audit regression: `6 passed` in `277.53s`.
- Full related assets regression: `65 passed`.

Scene audit evidence check:

- `build_scene_material_repair_flow_audit_report(...)` status: `passed`.
- Counts stayed stable: `flow_count=11`, `ready_flow_count=11`, `runtime_surface_count=21`, `test_evidence_count=26`, `source_evidence_count=28`, `missing_source_evidence_count=0`.

Residual scans:

```powershell
rg -n "def _focus_missing_content|def focus_material_repair_target|def handle_navigation_intent|def _set_return_navigation_intent|def _navigate_return_target|def focus_material_profile_repair_target|def apply_material_profile_question_figure_repair_candidate|def _focus_pending_material_repair_target|def _next_missing_target|def _focus_asset_slot|def _focus_attachment_role|def _focus_question_figure_item|def _show_missing_target|def _jump_to_card|def _highlight_attention_card|def _ensure_widget_visible|MaterialRepairNavigationMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\material_repair_navigation_presenter.py tests\test_assets_panel_helper_modules.py
rg -n "is_remote_asset_preview_url|remote_asset_url_name|asset_item_remote_(compare|full|thumbnail|preview)|download_remote_asset_preview|remote_asset_auth|REMOTE_ASSET_AUTH|REMOTE_ASSET_PREVIEW|urlopen|urllib\.request|urllib\.error|remote_writeback|enterprise_auth|signed_url|external_permission|subscription_drift" src\ui\panels\assets_panel.py src\ui\panels\assets src\services\material_assets
```

Result:

- Material repair navigation/focus methods are defined only in `material_repair_navigation_presenter.py`.
- `assets_panel.py` only imports and inherits `MaterialRepairNavigationMixin`.
- The deleted enterprise-remote surface remains absent from source implementation.

### Next Step

Continue slimming remaining direct `AssetsPanel` methods, now down to 94. The next candidate should be smaller than `_refresh_summary`. Good options:

- Preview table / preview row action methods around `_refresh_preview_table` and `_handle_preview_row_action`.
- Section card summary rendering helpers, if they can be separated without pulling `_refresh_summary`.
- Asset slot / attachment row construction methods, but only after mapping UI styling dependencies.

Keep `_refresh_summary` in `AssetsPanel` for now; it still coordinates too many presenter boundaries.

## 2026-07-07 Review Note: Enterprise Remote Deletion Boundary Re-checked

This review updates the deletion plan after the latest slimming passes. The earlier plan was written when the asset panel still had a large enterprise/remote surface. The current source state is materially different: the high-risk enterprise remote execution surface has already been removed from the active implementation, while several local metadata and local governance names still contain words such as `remote`, `master`, and `governance`.

### Current Evidence

Source scan over `src/ui/panels/assets_panel.py`, `src/ui/panels/assets`, and `src/services/material_assets` found no active implementation for the removed enterprise remote capabilities:

- no `remote_writeback`;
- no `enterprise_auth` / `enterprise_remote` active capability;
- no `signed_url` or `external_permission` flow;
- no `subscription_drift`, `subscription_lock`, or `subscription_change`;
- no `master_registry` or `registry_sync`;
- no `urlopen` / `urllib.request` inside the assets/material-assets implementation.

The remaining remote-looking names are not all enterprise remote behavior:

- `asset_item_remote_asset_id` is currently used as an asset identifier fallback for local question-figure matching and display.
- `remote_version`, `remote_etag`, and `remote_updated_at` import aliases are metadata compatibility fields, not network writeback.
- `remote_thumbnail_path` and `remote_thumbnail_cache_path` are normalized to local `thumbnail_path`.
- `remote_asset_cache_cleanup` metadata keys in cache cleanup confirmation describe a local cache ledger action, not a remote cleanup connector.
- `question_figure_library_governance_*` and `question_figure_library_master_version_*` are still present, but they operate as local table rows, local records, and profile metadata updates. They should be reviewed as product complexity, not treated as already-proven remote writeback.

### Revised Judgment

Do not delete by keyword. Delete by capability boundary.

The correct deletion target is not every identifier containing `remote`, `master`, or `governance`. The target is any capability that requires an external enterprise system or simulates one inside local UI:

- network writeback;
- enterprise authentication;
- signed URL refresh;
- external permission callback;
- remote conflict arbitration;
- subscription locking/change callback;
- subscription drift incident workflow;
- SLA/worker/compensation queue;
- non-question asset-family remote governance.

Those chains are already absent from the active assets/material-assets source. The next optimization step should therefore change from "delete all enterprise remote code" to three narrower tracks:

1. harden guard tests so removed enterprise capabilities cannot quietly return;
2. clean or rename misleading compatibility names only when doing so does not break local metadata compatibility;
3. review remaining local governance/master-version UI as product-complexity candidates, not as confirmed enterprise remote code.

### Guard Test Correction

`tests/test_assets_panel_architecture.py` already uses `ast.walk(...)` and therefore checks function names, class names, attributes, variables, and arguments across `assets_panel.py`.

`tests/test_assets_enterprise_boundary.py` has several checks that currently inspect only `module.body` top-level functions. Because most asset panel behavior lives as methods on `AssetsPanel` or mixins, those tests are weaker than intended. The next cleanup pass should either:

- reuse the `_module_identifier_names(...)` helper style from `tests/test_assets_panel_architecture.py`, or
- add a small shared helper that scans all `FunctionDef`, `AsyncFunctionDef`, `ClassDef`, `Name`, `arg`, and `Attribute` nodes.

This is a better first action than deleting more code blindly, because it turns the product boundary into an enforceable safety rail.

### Revised Step 5: Code Simplification After Enterprise Remote Removal

Step 5 should no longer start with runtime hiding or table unification. Those were useful when enterprise screens still existed. The current codebase needs a smaller, sharper sequence.

#### Step 5A: Boundary Hardening

Actions:

- strengthen enterprise-boundary tests so they scan class methods and mixin modules, not only top-level functions;
- keep the removed-capability denylist focused on true enterprise execution terms:
  - `remote_writeback`;
  - `remote_asset_auth`;
  - `enterprise_auth`;
  - `signed_url`;
  - `external_permission`;
  - `master_registry`;
  - `registry_sync`;
  - `subscription_lock`;
  - `subscription_change`;
  - `subscription_drift`;
  - `failure_recovery`;
  - `persistent_worker`;
  - `durable_worker`;
  - `sla_center`;
  - `download_remote_asset_preview_image`;
- do not deny plain `remote_version`, `remote_etag`, `remote_updated_at`, or `asset_item_remote_asset_id` until a compatibility rename plan exists.

Acceptance:

- tests fail if an enterprise remote method returns inside `AssetsPanel`, any assets presenter, or material-assets services;
- tests do not fail on harmless local metadata compatibility aliases.

#### Step 5B: Misleading Name Cleanup

Actions:

- evaluate renaming `_asset_item_remote_asset_id` to an external/local-neutral name such as `_asset_item_external_asset_id`;
- preserve the old name as a compatibility alias during one pass if tests/imports still rely on it;
- document `remote_version`, `remote_etag`, and `remote_updated_at` as imported upstream metadata, not active remote state;
- consider changing cache cleanup metadata keys from `remote_asset_cache_cleanup*` to `asset_cache_cleanup*` only if no saved audit payload depends on the old keys.

Acceptance:

- local question-figure matching, import, repair, and preview tests still pass;
- compatibility aliases are deliberate and documented, not accidental remote-product residue.

#### Step 5C: Review Local Governance Tables

Remaining product complexity is now mostly local governance UI, not enterprise remote execution. Review these separately:

- `question_figure_library_governance_table`;
- `question_figure_library_bulk_governance_table`;
- `question_figure_library_master_version_table`;
- `_record_question_figure_library_master_version_plan_row`;
- `_execute_question_figure_library_master_version_promotion_row`;
- `question_figure_library_master_version_*` service functions.

Decision options:

- keep as Local Advanced if they solve a real local duplicate/version conflict;
- downgrade to read-only local issue hints if the action buttons are too product-heavy;
- delete the action path if it only records a plan without improving the local formatting workflow;
- keep only pure metadata diff helpers if they are useful for batch import validation.

Acceptance:

- any removed table/action must reduce `assets_panel.py` UI construction, presenter methods, service exports, and tests;
- local import, replacement, repair audit, rollback, and cache tests must remain green.

#### Step 5D: Continue Small Presenter Extraction Only For Retained Core

After 5A-5C, continue method-level slimming, but only for retained local-core behavior:

- preview table helpers:
  - `_visible_placeholder_preview_rows`;
  - `_placeholder_preview_text`;
  - `_refresh_preview_table`;
  - `_handle_preview_row_action`;
- asset/attachment row construction, after confirming styling dependencies;
- profile mutation/action services for replace, repair apply, rollback, and save.

Do not extract new modules for capabilities that are likely to be deleted. Moving removable code into prettier modules is not real simplification.

### Updated Next Action

The next concrete execution should be:

1. strengthen enterprise-boundary guard tests;
2. run the assets/material regression set;
3. then choose between:
   - local governance table review/removal, if product simplification remains the priority;
   - preview table presenter extraction, if low-risk code slimming is the priority.

The recommended choice is 5A first. It is small, defensive, and prevents the deleted enterprise remote surface from returning while the rest of the cleanup continues.

## 2026-07-07 Execution Record 20: Step 5A Boundary Hardening

This pass executed the first item from the revised Step 5 plan. The goal was not to delete more code yet, but to make the already-deleted enterprise remote surface harder to reintroduce.

### Completed

- Updated `tests/test_assets_enterprise_boundary.py` so removed enterprise capability checks scan the real implementation surface:
  - `src/ui/panels/assets_panel.py`;
  - every `src/ui/panels/assets/*.py` presenter/helper module;
  - every `src/services/material_assets/*.py` service module.
- Added AST identifier scanning for:
  - `FunctionDef`;
  - `AsyncFunctionDef`;
  - `ClassDef`;
  - `Name`;
  - `arg`;
  - `Attribute`.
- Replaced the older top-level-only `module.body` function checks in enterprise-boundary tests.
- Hardened absence checks for:
  - `subscription_drift`;
  - `failure_recovery`;
  - `persistent_worker`;
  - `durable_worker`;
  - `sla_center`;
  - `non_question_asset_family`;
  - `remote_writeback`;
  - `enterprise_remote_auth`;
  - `master_registry`;
  - `registry_sync`;
  - `subscription_lock`;
  - `subscription_change`.

### Why This Was The Right First Step

The latest source scan showed the dangerous enterprise remote execution chains are already absent from active assets/material-assets code. The bigger risk is now regression: a future edit could add one of those methods back inside `AssetsPanel`, a presenter mixin, or a service module while the old tests only checked a narrow top-level slice.

This hardening keeps the deletion boundary precise:

- it blocks true enterprise execution terms;
- it does not block local compatibility metadata such as `asset_item_remote_asset_id`, `remote_version`, `remote_etag`, or `remote_updated_at`.

### Verification

Passed:

```powershell
python -m py_compile tests\test_assets_enterprise_boundary.py
python -m pytest -q tests\test_assets_enterprise_boundary.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Enterprise boundary focused regression: `8 passed`.
- Full related assets regression: `65 passed`.

### Next Step

The next product-simplification candidate is Step 5C, the local governance/master-version table review:

- `question_figure_library_governance_table`;
- `question_figure_library_bulk_governance_table`;
- `question_figure_library_master_version_table`;
- `_record_question_figure_library_master_version_plan_row`;
- `_execute_question_figure_library_master_version_promotion_row`;
- `question_figure_library_master_version_*` service functions.

The review should decide whether these remain useful Local Advanced features, should become read-only issue hints, or should be removed. Do not rename `remote_*` compatibility metadata yet; that is Step 5B and should be handled as a compatibility migration, not mixed into governance UI removal.

## 2026-07-07 Execution Record 21: Step 5C Master-Version Action Downgrade

This pass executed the local governance/master-version review from Step 5C.

### Decision

Keep the lightweight local governance tables:

- `question_figure_library_governance_table`;
- `question_figure_library_bulk_governance_table`.

Reason: these tables only project local question-figure metadata issues and help the user locate the affected row. They do not perform remote writeback, auth, subscription, worker, SLA, or profile-wide mutation.

Downgrade the master-version table:

- keep `question_figure_library_master_version_table` as a read-only issue projection plus locate action;
- remove the "record plan" action;
- remove the "execute promotion" action.

Reason: the master-version table is useful as a cross-profile duplicate/version-drift signal, but the plan/promotion buttons created a small master-data workflow inside a local formatting tool. Those actions wrote history records and changed profile metadata across packages, which is too heavy for the retained local-core/Local Advanced boundary.

### Completed

- Updated `src/ui/panels/assets/question_library_master_version_presenter.py`:
  - removed `记录计划` and `执行推广` buttons;
  - kept a single `定位` button per row;
  - changed the presenter intent to read-only master-version issue rows.
- Removed two direct `AssetsPanel` action methods:
  - `_record_question_figure_library_master_version_plan_row`;
  - `_execute_question_figure_library_master_version_promotion_row`.
- Removed active/public master-version execution helpers from `src/services/material_assets/question_library.py`:
  - `record_question_figure_library_master_version_plan`;
  - `build_question_figure_library_master_version_plan_record`;
  - `build_question_figure_library_master_version_promotion_record`;
  - `promote_question_figure_master_version_to_profile`;
  - `question_figure_master_version_promoted_metadata`;
  - `question_figure_master_version_changed_fields`;
  - `question_figure_master_version_canonical_occurrence`;
  - `question_figure_master_version_canonical_sort_key`;
  - `question_figure_payload_index_for_question_row`;
  - `asset_metadata_reference_patch`;
  - `natural_version_sort_key`.
- Kept internal old-history status compatibility:
  - `_question_figure_library_master_version_plan_for`;
  - `_question_figure_library_master_version_promotion_for`.
- Removed those execution helpers from `src/services/material_assets/__init__.py` exports.
- Updated `tests/test_material_asset_services.py`:
  - retained read-only master-version entry projection coverage;
  - added coverage that old plan/promotion history records can still influence status labels;
  - added coverage that master-version execution APIs are no longer public;
  - retained metadata alias read coverage without relying on promotion helpers.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 4,449 lines, 96 functions/methods, 2 classes.
- `AssetsPanel`: 92 direct methods.
- `src/services/material_assets/question_library.py`: 1,796 lines, 47 functions/methods.
- `src/ui/panels/assets/question_library_master_version_presenter.py`: 106 lines, 4 methods, 1 class.
- `tests/test_material_asset_services.py`: 723 lines, 14 tests.

Compared with Execution Record 19:

- `assets_panel.py` dropped from 4,627 lines to 4,449 lines.
- Total functions/methods inside `assets_panel.py` dropped from 98 to 96.
- `AssetsPanel` direct methods dropped from 94 to 92.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_library_master_version_presenter.py src\services\material_assets\question_library.py src\services\material_assets\__init__.py tests\test_material_asset_services.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_question_library_presenter.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Material service + question-library presenter regression: `19 passed`.
- Enterprise boundary + assets architecture regression: `14 passed`.
- Full related assets regression: `64 passed`.

Residual scan:

```powershell
rg -n "record_question_figure_library_master_version_plan|build_question_figure_library_master_version|promote_question_figure_master_version_to_profile|question_figure_master_version_promoted_metadata|question_figure_master_version_canonical|question_figure_master_version_changed_fields|question_figure_payload_index_for_question_row|natural_version_sort_key|asset_metadata_reference_patch|_record_question_figure_library_master_version_plan_row|_execute_question_figure_library_master_version_promotion_row" src\ui\panels\assets_panel.py src\ui\panels\assets src\services\material_assets tests\test_material_asset_services.py
```

Result:

- No active source implementation remains for the removed public/action helpers.
- Only internal old-history status compatibility helpers remain in `question_library.py`.
- Removed public API names appear only in the new negative test list.

### Next Step

Continue with retained local-core slimming. Best next candidate is Step 5D preview table presenter extraction:

- `_visible_placeholder_preview_rows`;
- `_placeholder_preview_text`;
- `_refresh_preview_table`;
- `_handle_preview_row_action`.

This is now a better next step than more governance deletion because the remaining governance tables are lightweight local issue locators, while the preview table helpers are still direct `AssetsPanel` methods and belong in a presenter.

## 2026-07-07 Execution Record 22: Step 5D Preview Table Presenter Extraction

This pass continued Step 5D by extracting retained local-core preview table behavior out of `AssetsPanel`.

### Completed

- Added `src/ui/panels/assets/preview_table_presenter.py`.
- Introduced `PreviewTablePresenterMixin`.
- Moved 4 direct methods out of `AssetsPanel`:
  - `_visible_placeholder_preview_rows`;
  - `_placeholder_preview_text`;
  - `_refresh_preview_table`;
  - `_handle_preview_row_action`.
- Updated `AssetsPanel` to inherit `PreviewTablePresenterMixin`.
- Added helper-module ownership coverage in `tests/test_assets_panel_helper_modules.py`.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 4,346 lines, 92 functions/methods, 2 classes.
- `AssetsPanel`: 88 direct methods.
- `src/ui/panels/assets/preview_table_presenter.py`: 124 lines, 4 methods, 1 class.
- `tests/test_assets_panel_helper_modules.py`: 266 lines, 13 tests.

Compared with Execution Record 21:

- `assets_panel.py` dropped from 4,449 lines to 4,346 lines.
- Total functions/methods inside `assets_panel.py` dropped from 96 to 92.
- `AssetsPanel` direct methods dropped from 92 to 88.

Compared with Execution Record 19:

- `assets_panel.py` dropped from 4,627 lines to 4,346 lines.
- Total functions/methods inside `assets_panel.py` dropped from 98 to 92.
- `AssetsPanel` direct methods dropped from 94 to 88.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\preview_table_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Helper/architecture focused regression: `19 passed`.
- Full related assets regression: `65 passed`.

Residual scan:

```powershell
rg -n "def _visible_placeholder_preview_rows|def _placeholder_preview_text|def _refresh_preview_table|def _handle_preview_row_action|PreviewTablePresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\preview_table_presenter.py tests\test_assets_panel_helper_modules.py
```

Result:

- Preview table methods are defined only in `preview_table_presenter.py`.
- `assets_panel.py` only imports and inherits `PreviewTablePresenterMixin`.

### Next Step

Continue retained-core slimming. Good candidates:

- asset slot / attachment row construction:
  - `_build_asset_slot_row`;
  - `_build_attachment_role_row`;
  - `_configure_asset_icon_button`;
- section summary/card helpers:
  - `_refresh_section_cards`;
  - `_refresh_section_summary_cards`.

The safer next move is asset slot / attachment row extraction, because those methods are cohesive UI construction helpers and do not coordinate the whole summary refresh.

## 2026-07-07 Execution Record 23: Asset Row Presenter Extraction

This pass extracted retained local-core asset and attachment row construction out of `AssetsPanel`.

### Completed

- Added `src/ui/panels/assets/asset_rows_presenter.py`.
- Introduced `AssetRowsPresenterMixin`.
- Moved 3 direct methods out of `AssetsPanel`:
  - `_build_asset_slot_row`;
  - `_build_attachment_role_row`;
  - `_configure_asset_icon_button`.
- Updated `AssetsPanel` to inherit `AssetRowsPresenterMixin`.
- Added helper-module ownership coverage in `tests/test_assets_panel_helper_modules.py`.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 4,211 lines, 89 functions/methods, 2 classes.
- `AssetsPanel`: 85 direct methods.
- `src/ui/panels/assets/asset_rows_presenter.py`: 161 lines, 3 methods, 1 class.
- `tests/test_assets_panel_helper_modules.py`: 283 lines, 14 tests.

Compared with Execution Record 22:

- `assets_panel.py` dropped from 4,346 lines to 4,211 lines.
- Total functions/methods inside `assets_panel.py` dropped from 92 to 89.
- `AssetsPanel` direct methods dropped from 88 to 85.

Compared with Execution Record 19:

- `assets_panel.py` dropped from 4,627 lines to 4,211 lines.
- Total functions/methods inside `assets_panel.py` dropped from 98 to 89.
- `AssetsPanel` direct methods dropped from 94 to 85.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\asset_rows_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Helper/architecture focused regression: `20 passed`.
- Full related assets regression: `66 passed`.

Residual scan:

```powershell
rg -n "def _build_asset_slot_row|def _build_attachment_role_row|def _configure_asset_icon_button|AssetRowsPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\asset_rows_presenter.py tests\test_assets_panel_helper_modules.py
```

Result:

- Asset/attachment row methods are defined only in `asset_rows_presenter.py`.
- `assets_panel.py` only imports and inherits `AssetRowsPresenterMixin`.

### Next Step

Continue retained-core slimming. The next candidate is section navigation/card summary helpers:

- `_refresh_section_cards`;
- `_refresh_section_summary_cards`;
- possibly `_apply_responsive_layout`, `_sync_generate_action_button_mode`, and `_sync_archive_action_button_mode` if the dependency boundary stays layout-only.

Avoid extracting `_refresh_summary` itself for now. It still coordinates profile state, preview state, batch output, section cards, and summary cards.

## 2026-07-07 Execution Record 24: Section Summary Presenter Extraction

This pass extracted retained local-core section card and summary-card projection logic out of `AssetsPanel`.

### Completed

- Added `src/ui/panels/assets/section_summary_presenter.py`.
- Introduced `SectionSummaryPresenterMixin`.
- Moved 2 direct methods out of `AssetsPanel`:
  - `_refresh_section_cards`;
  - `_refresh_section_summary_cards`.
- Updated `AssetsPanel` to inherit `SectionSummaryPresenterMixin`.
- Removed the direct `SummaryGridItem` import from `assets_panel.py`; it now belongs to the section summary presenter.
- Added helper-module ownership coverage in `tests/test_assets_panel_helper_modules.py`.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 3,866 lines, 85 functions/methods, 2 classes.
- `AssetsPanel`: 83 direct methods.
- `src/ui/panels/assets/section_summary_presenter.py`: 361 lines, 2 top-level methods plus 2 local helper functions, 1 class.
- `tests/test_assets_panel_helper_modules.py`: 299 lines, 15 tests.

Compared with Execution Record 23:

- `assets_panel.py` dropped from 4,211 lines to 3,866 lines.
- Total functions/methods inside `assets_panel.py` dropped from 89 to 85.
- `AssetsPanel` direct methods dropped from 85 to 83.

Compared with Execution Record 19:

- `assets_panel.py` dropped from 4,627 lines to 3,866 lines.
- Total functions/methods inside `assets_panel.py` dropped from 98 to 85.
- `AssetsPanel` direct methods dropped from 94 to 83.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\section_summary_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Helper/architecture focused regression: `21 passed`.
- Full related assets regression: `67 passed`.

Residual scan:

```powershell
rg -n "def _refresh_section_cards|def _refresh_section_summary_cards|SectionSummaryPresenterMixin|SummaryGridItem" src\ui\panels\assets_panel.py src\ui\panels\assets\section_summary_presenter.py tests\test_assets_panel_helper_modules.py
```

Result:

- Section card methods are defined only in `section_summary_presenter.py`.
- `assets_panel.py` only imports and inherits `SectionSummaryPresenterMixin`.
- `SummaryGridItem` is no longer imported by `assets_panel.py`.

### Next Step

Continue retained-core slimming without extracting `_refresh_summary` yet. The next low-risk candidates are layout/responsive helpers:

- `_apply_responsive_layout`;
- `_sync_generate_action_button_mode`;
- `_sync_archive_action_button_mode`.

These methods are layout-only and sit near the UI shell, so they can move into a small layout presenter. After that, reassess whether `_refresh_summary` can become thinner or whether profile/action-service extraction should take priority.

## 2026-07-07 Execution Record 25: Responsive Layout Presenter Extraction

This pass extracted responsive layout behavior out of `AssetsPanel`.

### Completed

- Added `src/ui/panels/assets/responsive_layout_presenter.py`.
- Introduced `ResponsiveLayoutPresenterMixin`.
- Moved 3 direct methods out of `AssetsPanel`:
  - `_apply_responsive_layout`;
  - `_sync_generate_action_button_mode`;
  - `_sync_archive_action_button_mode`.
- Updated `AssetsPanel` to inherit `ResponsiveLayoutPresenterMixin`.
- Added helper-module ownership coverage in `tests/test_assets_panel_helper_modules.py`.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 3,806 lines, 82 functions/methods, 2 classes.
- `AssetsPanel`: 80 direct methods.
- `src/ui/panels/assets/responsive_layout_presenter.py`: 78 lines, 3 methods, 1 class.
- `tests/test_assets_panel_helper_modules.py`: 316 lines, 16 tests.

Compared with Execution Record 24:

- `assets_panel.py` dropped from 3,866 lines to 3,806 lines.
- Total functions/methods inside `assets_panel.py` dropped from 85 to 82.
- `AssetsPanel` direct methods dropped from 83 to 80.

Compared with Execution Record 19:

- `assets_panel.py` dropped from 4,627 lines to 3,806 lines.
- Total functions/methods inside `assets_panel.py` dropped from 98 to 82.
- `AssetsPanel` direct methods dropped from 94 to 80.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\responsive_layout_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Helper/architecture focused regression: `22 passed`.
- Full related assets regression: `68 passed`.

Residual scan:

```powershell
rg -n "def _apply_responsive_layout|def _sync_generate_action_button_mode|def _sync_archive_action_button_mode|ResponsiveLayoutPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\responsive_layout_presenter.py tests\test_assets_panel_helper_modules.py
```

Result:

- Responsive layout methods are defined only in `responsive_layout_presenter.py`.
- `assets_panel.py` only imports and inherits `ResponsiveLayoutPresenterMixin`.

### Next Step

Reassess the remaining 80 direct `AssetsPanel` methods. Do not extract `_refresh_summary` blindly; instead look for another cohesive group with low coordination risk:

- scene-derived spec sync:
  - `_default_required_field_keys`;
  - `_required_fields_from_scene`;
  - `_required_fields_match_default`;
  - `_asset_slots_from_scene`;
  - `_attachment_roles_from_scene`;
  - `_sync_asset_slot_rows`;
  - `_sync_attachment_role_rows`;
- or document/mapping load orchestration if it can be separated without making profile mutation harder to reason about.

The scene/spec sync group is the safer next candidate because it mostly derives UI specs from scene/schema configuration and already calls the extracted row builders.

## 2026-07-07 Execution Record 26: Scene Spec Presenter Extraction

This pass extracted scene-derived required-field and material-row spec logic out of `AssetsPanel`.

### Completed

- Added `src/ui/panels/assets/scene_spec_presenter.py`.
- Introduced `SceneSpecPresenterMixin`.
- Moved 7 direct methods out of `AssetsPanel`:
  - `_default_required_field_keys`;
  - `_required_fields_from_scene`;
  - `_required_fields_match_default`;
  - `_asset_slots_from_scene`;
  - `_attachment_roles_from_scene`;
  - `_sync_asset_slot_rows`;
  - `_sync_attachment_role_rows`.
- Updated `AssetsPanel` to inherit `SceneSpecPresenterMixin`.
- Removed now-local scene/spec imports from `assets_panel.py`:
  - `build_material_requirements`;
  - `COMMON_ASSET_SLOTS`;
  - `REQUIRED_FIELD_KEYS`;
  - `AssetSlotSpec`;
  - `_normalize_required_field_keys`;
  - `_accepted_types_include_attachment`;
  - `_asset_slot_target_for_role`;
  - `_material_schema_ids_from_profile`;
  - `_material_schemas_from_ids`;
  - `_schemas_role_accept_attachment`.
- Added helper-module ownership coverage in `tests/test_assets_panel_helper_modules.py`.

### Current Size Snapshot

- `src/ui/panels/assets_panel.py`: 3,622 lines, 75 functions/methods, 2 classes.
- `AssetsPanel`: 73 direct methods.
- `src/ui/panels/assets/scene_spec_presenter.py`: 207 lines, 7 methods, 1 class.
- `tests/test_assets_panel_helper_modules.py`: 337 lines, 17 tests.

Compared with Execution Record 25:

- `assets_panel.py` dropped from 3,806 lines to 3,622 lines.
- Total functions/methods inside `assets_panel.py` dropped from 82 to 75.
- `AssetsPanel` direct methods dropped from 80 to 73.

Compared with Execution Record 19:

- `assets_panel.py` dropped from 4,627 lines to 3,622 lines.
- Total functions/methods inside `assets_panel.py` dropped from 98 to 75.
- `AssetsPanel` direct methods dropped from 94 to 73.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\scene_spec_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Helper/architecture focused regression: `23 passed`.
- Full related assets regression: `69 passed`.

Residual scan:

```powershell
rg -n "def _default_required_field_keys|def _required_fields_from_scene|def _required_fields_match_default|def _asset_slots_from_scene|def _attachment_roles_from_scene|def _sync_asset_slot_rows|def _sync_attachment_role_rows|SceneSpecPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\scene_spec_presenter.py tests\test_assets_panel_helper_modules.py
```

Result:

- Scene/spec methods are defined only in `scene_spec_presenter.py`.
- `assets_panel.py` only imports and inherits `SceneSpecPresenterMixin`.

### Next Step

Reassess the remaining 73 direct `AssetsPanel` methods before extracting more. Candidate groups:

- section shell methods:
  - `_build_section_navigation`;
  - `_build_section_pages`;
  - `_register_detail_cards`;
  - `_connect_signals`;
  - `_on_section_selected`;
  - `_sync_current_section_geometry`;
- current archive / material context accessors:
  - `current_archive`;
  - `material_context`;
  - `set_archive`;
  - save/load archive path methods.

The section shell methods are UI-structure oriented, but they touch initialization and signal wiring. Inspect them before moving; do not extract `_setup_ui` yet.

## 2026-07-07 Plan Review: Enterprise Remote Removal Is No Longer The Main Work

This review updates the previous deletion plan against the current code state.

### Current Verified State

The earlier enterprise-remote deletion direction has largely landed. A focused identifier scan currently finds no active implementation identifiers for:

- `remote_writeback`;
- `enterprise_auth` / `remote_asset_auth`;
- `signed_url`;
- `external_permission`;
- `master_registry` / `registry_sync`;
- `subscription_lock` / `subscription_change`;
- `subscription_drift`;
- `failure_recovery`;
- `persistent_worker` / `durable_worker`;
- `sla_center`;
- `non_question_asset_family`.

The only hit for these removed tokens is now in deletion guard tests. That is the right shape: the tests document that these capabilities must not silently return.

Current size snapshot:

- `src/ui/panels/assets_panel.py`: 3,622 lines, 75 functions/methods, 2 classes.
- `AssetsPanel`: 73 direct methods.
- `src/services/material_assets/question_library.py`: 1,796 lines, 47 functions.
- `src/services/material_assets/question_figures.py`: 515 lines, 24 functions.
- `src/services/material_assets/cache_projection.py`: 1,160 lines, 38 functions.

`src/ui/panels/assets/enterprise_boundary.py` also no longer contains `freeze` or `delete_candidate` records. It now only describes retained local or isolated local-cache groups:

- `local_question_figures`: keep.
- `local_question_audit`: keep.
- `lightweight_shared_cache`: isolate.

### Corrected Diagnosis

The next optimization should not be "delete remote writeback" again. That work is already guarded as removed.

The remaining maintainability issue is subtler:

- some retained code still uses enterprise-like vocabulary such as `governance`, `master_version`, and `remote_asset_id`;
- `cache_projection.py` is large for a "lightweight shared cache" boundary;
- `AssetsPanel` still builds many advanced tables directly in the main widget;
- `question_library.py` still mixes local metadata edit/history/rollback with issue projection and read-only master-version projection.

So the next phase should be "retained local-core simplification", not another enterprise-deletion phase and not broad control unification.

### Refined Delete / Keep / Downgrade Boundary

Hard-deleted and should stay deleted:

- remote writeback, including batch plan, queue, conflict, override, merge, rollback, compensation, manifest, retry, and final status;
- enterprise auth, signed URL refresh, permission callback, SSO/OAuth refresh fields;
- remote master registry sync and subscription callbacks;
- subscription drift triage, approval, SLA, worker, durable/persistent task queues;
- non-question asset family remote governance.

Keep as local foundation:

- question-figure metadata read/write inside the local profile;
- local metadata history and rollback;
- local repair audit and rollback audit;
- local preview path, thumbnail path, cached path, and plain metadata aliases;
- DOCX media scan/repair helpers that work on local files.

Retain but simplify:

- `question_figure_library_governance_*`: this is local issue projection, but the name makes it look like an enterprise workflow. It should either be renamed to metadata issue projection or reduced to the rows that are actually shown.
- `question_figure_library_master_version_*`: this is already read-only. It should be kept only if it catches useful local version conflicts. Otherwise it is a clean deletion candidate.
- `question_figure_shared_cache_*`: keep basic cache status/path rows, but review trend/metrics/cleanup-confirmation tables. Those may be more dashboard than core formatting tool.
- `asset_item_remote_asset_id`: functionally this is a library asset identifier. Keep compatibility for metadata, but consider adding a clearer alias such as `asset_item_library_asset_id` before eventually retiring the old name.

### Optimized Next Execution Order

1. Guard the removed enterprise surface.

   Keep the existing tests that assert removed enterprise identifiers do not return. Add future removed tokens there instead of adding new docs-only rules.

2. Review and slim the read-only master-version projection.

   Target files:

   - `src/ui/panels/assets/question_library_master_version_presenter.py`;
   - `src/services/material_assets/question_library.py`;
   - `tests/test_material_asset_services.py`;
   - `tests/test_assets_question_library_presenter.py`.

   Decision gate:

   - If the table only explains remote master-data drift, delete it.
   - If it catches local package/version inconsistency, rename the concept away from "master version" and keep a smaller issue row.

3. Review shared-cache advanced dashboard rows.

   Target files:

   - `src/services/material_assets/cache_projection.py`;
   - `src/ui/panels/assets/cache_presenter.py`;
   - cache table creation in `src/ui/panels/assets_panel.py`;
   - `tests/test_assets_cache_presenter.py`;
   - cache sections in `tests/test_material_asset_services.py`.

   Keep:

   - cache status;
   - cache directory rows;
   - cache entry rows;
   - invalid/missing path hints.

   Delete or collapse unless there is clear product value:

   - hit-rate trend rows;
   - metrics dashboard rows;
   - cleanup task planning rows;
   - cleanup confirmation ledger rows.

4. Rename local "governance" wording only after deletion pressure is lower.

   This is not first priority because renaming alone does not reduce code. Do it when it removes confusion in the retained local core:

   - `question_figure_library_governance_issue_entries` -> local metadata issue entries;
   - `question_figure_library_bulk_governance_entries` -> local metadata batch issue entries.

5. Continue `AssetsPanel` slimming after the product surface is smaller.

   The next low-risk extraction candidate remains the section shell group:

   - `_build_section_navigation`;
   - `_build_section_pages`;
   - `_register_detail_cards`;
   - `_connect_signals`;
   - `_on_section_selected`;
   - `_sync_current_section_geometry`.

   But this should come after deciding whether master-version and advanced cache tables still belong. Extracting shell code before deleting unused tables would make the remaining complexity tidier without making the product smaller.

### Revised Immediate Recommendation

Do not continue with general control unification yet.

Do not spend the next pass on removed enterprise remote writeback.

The best next implementation pass is:

1. inspect the master-version read-only projection;
2. either delete it or rename/shrink it to local version inconsistency projection;
3. run focused material-service and question-library presenter tests;
4. record the size delta and residual token scan.

If master-version proves worth keeping, move directly to shared-cache advanced dashboard pruning. That is now the largest remaining "looks bigger than the local product needs" area.

## 2026-07-07 Execution Record 27: Master-Version Projection Downgraded To Local Version Consistency

This pass executed the reviewed next step: inspect the retained master-version projection and remove the remaining enterprise-governance semantics without deleting useful local version consistency checks.

### Decision

Keep the read-only row projection, but downgrade its meaning:

- Before: cross-package master-version governance with old plan/promotion execution status compatibility.
- After: local question-figure version consistency warning across local profiles/packages.

The retained value is local: if the same source/asset id appears in multiple local profiles with different version, ETag, updated-at, alt text, or reference metadata, the UI can still show a read-only inconsistency row and locate the first affected question figure.

The removed value was enterprise-shaped: old governance plan and promotion execution records no longer change the row status.

### Completed

- Updated `src/services/material_assets/question_library.py`:
  - removed profile-history scanning from `question_figure_library_master_version_entries`;
  - removed `plan_recorded` and `promotion_executed` fields from generated rows;
  - removed `_question_figure_library_master_version_plan_for`;
  - removed `_question_figure_library_master_version_promotion_for`;
  - removed now-unused `_latest_master_record_for`;
  - changed status labels from governance wording to local check wording:
    - `version_drift` -> `版本不一致`;
    - `missing_version_statement` -> `缺版本声明`.
- Updated `src/ui/panels/assets/question_library_master_version_presenter.py` docstrings and tooltip to describe local version consistency rows.
- Updated `src/ui/panels/assets_panel.py` table headers:
  - `主数据键` -> `素材键`;
  - `处理` -> `定位`.
- Updated `src/config/scene_product_readiness.py`:
  - replaced two evidence surfaces, `cross-package master version governance` and `promotion execution`, with one local evidence surface:
    - `question asset per-question asset library local version consistency UI bridge`;
  - changed summary text from `master-version promotion` to `local version consistency`.
- Updated tests:
  - `tests/test_material_asset_services.py` now proves legacy governance plan/promotion records do not affect local version-consistency status;
  - `tests/test_scene_product_maturity_upgrade_audit.py` now expects local version-consistency evidence instead of promotion execution evidence.

### Size Snapshot

- `src/services/material_assets/question_library.py`: 1,664 lines, 44 functions.
- `src/ui/panels/assets_panel.py`: 3,622 lines, 75 functions/methods, 2 classes.
- `AssetsPanel`: 73 direct methods.
- `src/ui/panels/assets/question_library_master_version_presenter.py`: 106 lines, 4 methods, 1 class.
- `src/config/scene_product_readiness.py`: 999 lines, 12 functions, 2 classes.

Compared with the previous review snapshot:

- `question_library.py` dropped from 1,796 lines to 1,664 lines.
- `question_library.py` dropped from 47 functions to 44 functions.
- `AssetsPanel` line and method count stayed flat; the UI change was semantic cleanup, not shell extraction.

### Verification

Passed:

```powershell
python -m py_compile src\services\material_assets\question_library.py src\ui\panels\assets\question_library_master_version_presenter.py src\ui\panels\assets_panel.py src\config\scene_product_readiness.py tests\test_material_asset_services.py tests\test_scene_product_maturity_upgrade_audit.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_question_library_presenter.py tests\test_scene_product_maturity_upgrade_audit.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused material/question-library/maturity regression: `24 passed`.
- Full related assets regression: `69 passed`.

Residual scan:

```powershell
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|subscription_drift|failure_recovery|persistent_worker|durable_worker|sla_center|non_question_asset_family|cross-package master version promotion execution UI bridge|master-version promotion|_latest_master_record_for|_question_figure_library_master_version_plan_for|_question_figure_library_master_version_promotion_for" src tests
```

Result:

- No active source/test hits for the removed enterprise identifiers or removed master-version helper functions.
- `plan_recorded` and `promotion_executed` remain only in tests as negative assertions that they are no longer emitted.
- Legacy action strings for old governance plan/promotion records remain only inside one service test as input fixtures proving those old records no longer affect the local read-only row.

### Next Step

Move to shared-cache pruning, because it is now the largest retained area that may be heavier than the local product needs.

Initial candidate scope:

- keep:
  - cache status;
  - cache directory rows;
  - cache entry rows;
  - invalid/missing path hints;
- inspect for deletion or collapse:
  - hit-rate trend rows;
  - metrics dashboard rows;
  - cleanup task planning rows;
  - cleanup confirmation ledger rows.

Start with `src/services/material_assets/cache_projection.py`, `src/ui/panels/assets/cache_presenter.py`, cache table creation in `src/ui/panels/assets_panel.py`, `tests/test_assets_cache_presenter.py`, and cache sections in `tests/test_material_asset_services.py`.

## 2026-07-07 Execution Record 28: Shared-Cache Advanced Ledger Pruning

This pass executed the shared-cache pruning step. The cache boundary is now a local status/path projection, not a cleanup-governance surface.

### Decision

Keep:

- shared cache directory rows;
- shared cache entry rows;
- cache index entry rows;
- cache status labels;
- invalidation status/scope hints;
- opening the selected cache directory;
- previewing the selected cached image.

Delete:

- cache hit-rate trend rows;
- cache metrics dashboard rows;
- cleanup task rows;
- cleanup history rows;
- cleanup confirmation state;
- cleanup confirmation writeback;
- `remote_asset_cache_cleanup*` profile-field writes from the assets panel.

This keeps the local value of cache visibility while removing the workflow/ledger layer that made the panel look like a remote cache governance console.

### Completed

- Updated `src/services/material_assets/cache_projection.py`:
  - removed metrics-history projection;
  - removed hit-rate trend projection;
  - removed cleanup-history projection;
  - removed cleanup-confirmation read/write helpers;
  - removed cleanup/metrics helper labels that no retained code used;
  - kept directory rows, entry rows, index rows, cache status, invalidation labels, and path fallback helpers.
- Updated `src/ui/panels/assets/cache_presenter.py`:
  - removed task/trend/metrics/cleanup/confirmation refresh methods;
  - removed cleanup confirmation writeback methods;
  - retained directory table, entry table, open-directory action, selection sync, and cached-image preview.
- Updated `src/ui/panels/assets_panel.py`:
  - removed creation of shared-cache tasks table;
  - removed creation of shared-cache trends table;
  - removed creation of shared-cache metrics table;
  - removed creation of shared-cache cleanup table;
  - removed cleanup confirmation row/button;
  - removed related styling hooks.
- Updated `src/services/material_assets/__init__.py` and `assets_panel.py` compatibility aliases so deleted advanced cache helpers are no longer exported.
- Updated `src/ui/panels/assets/enterprise_boundary.py`:
  - changed lightweight cache summary from cleanup confirmation to status/path fallback.
- Updated tests:
  - `tests/test_assets_cache_presenter.py` now expects only the retained cache presenter methods;
  - `tests/test_assets_panel_question_cache.py` now proves cleanup workflow helpers are not exported;
  - `tests/test_material_asset_services.py` no longer whitelists removed advanced cache helpers as local service calls.

### Size Snapshot

- `src/services/material_assets/cache_projection.py`: 417 lines, 18 functions.
- `src/ui/panels/assets/cache_presenter.py`: 167 lines, 6 methods, 1 class.
- `src/ui/panels/assets_panel.py`: 3,343 lines, 75 functions/methods, 2 classes.
- `AssetsPanel`: 73 direct methods.
- `src/services/material_assets/__init__.py`: 213 lines.

Compared with the previous review snapshot:

- `cache_projection.py` dropped from 1,160 lines to 417 lines.
- `cache_projection.py` dropped from 38 functions to 18 functions.
- `assets_panel.py` dropped from 3,622 lines to 3,343 lines.
- `AssetsPanel` direct method count stayed flat because the deleted cache UI was table construction, imports, aliases, and presenter/service logic rather than direct `AssetsPanel` methods.

### Verification

Passed:

```powershell
python -m py_compile src\services\material_assets\cache_projection.py src\services\material_assets\__init__.py src\ui\panels\assets\cache_presenter.py src\ui\panels\assets_panel.py tests\test_assets_cache_presenter.py tests\test_assets_panel_question_cache.py tests\test_material_asset_services.py
python -m pytest -q tests\test_assets_cache_presenter.py tests\test_assets_panel_question_cache.py tests\test_material_asset_services.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
python -m py_compile src\ui\panels\assets\enterprise_boundary.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_assets_panel_architecture.py tests\test_assets_cache_presenter.py tests\test_assets_panel_question_cache.py
```

Results:

- Cache/material focused regression: `19 passed`.
- Full related assets regression: `69 passed`.
- Boundary/architecture/cache focused regression after boundary text update: `19 passed`.

Residual scan:

```powershell
rg -n "append_question_figure_shared_cache_cleanup_confirmation|question_figure_shared_cache_cleanup|question_figure_shared_cache_hit_rate|question_figure_shared_cache_metrics|question_figure_shared_cache_profile_dir_scopes|question_figure_cleanup_confirmation|latest_question_figure_shared_cache_cleanup|read_question_figure_shared_cache_cleanup|download_status_label|cleanup_mode_label|cleanup_status_label|yes_no_label|truthy|remote_asset_cache_cleanup|metrics_history|cleanup_history|_refresh_question_figure_shared_cache_tasks_table|_refresh_question_figure_shared_cache_trends_table|_refresh_question_figure_shared_cache_metrics_table|_refresh_question_figure_shared_cache_cleanup_table" src\services\material_assets\cache_projection.py src\services\material_assets\__init__.py src\ui\panels\assets\cache_presenter.py src\ui\panels\assets\question_cache.py src\ui\panels\assets_panel.py tests\test_assets_cache_presenter.py tests\test_assets_panel_question_cache.py tests\test_material_asset_services.py
```

Result:

- Deleted advanced cache helper names remain only in `tests/test_assets_panel_question_cache.py` as negative assertions.
- Retained cache source no longer exports cleanup/metrics/trend helpers.
- `assets_panel.py` no longer creates the advanced cache tables or cleanup confirmation row.

### Next Step

The largest remaining product-shape issue is now local naming and table semantics, not enterprise remote execution.

Recommended next pass:

1. Review `question_figure_library_governance_*` and `question_figure_library_bulk_governance_*`.
2. Decide whether to keep them as local metadata issue projection or rename/shrink them.
3. Avoid broad UI control unification until the retained local surface is stable.
4. After local issue projection is settled, resume structural slimming of section shell methods:
   - `_build_section_navigation`;
   - `_build_section_pages`;
   - `_register_detail_cards`;
   - `_connect_signals`;
   - `_on_section_selected`;
   - `_sync_current_section_geometry`.

## 2026-07-07 Execution Record 29: Local Governance Renamed And Bulk Governance Removed

This pass executed the recommendation from Execution Record 28. The remaining `question_figure_library_governance_*` surface has been reduced to a local metadata issue locator, and the heavier bulk-governance projection has been removed.

### Decision

Keep:

- per-question local metadata issue rows;
- missing source / asset id / alt text checks;
- duplicate asset id warning rows;
- row-location behavior back to the affected question figure.

Delete:

- bulk governance summary rows;
- bulk governance scope labels;
- bulk governance next-step labels;
- `question_figure_library_bulk_governance_table`;
- the old governance presenter name.

The important product distinction is:

- retained value: local metadata hygiene for question figures;
- removed value: workflow/governance framing that suggested batch triage, assignment, or enterprise decision records.

### Completed

- Updated `src/services/material_assets/question_library.py`:
  - renamed `question_figure_library_governance_issue_entries` to `question_figure_library_metadata_issue_entries`;
  - removed `question_figure_library_bulk_governance_entries`;
  - removed `question_figure_bulk_governance_scope`;
  - removed `question_figure_bulk_governance_next_step`;
  - removed old aliases/exports for the deleted bulk-governance helpers.
- Updated `src/services/material_assets/__init__.py`:
  - exported `question_figure_library_metadata_issue_entries`;
  - stopped exporting bulk-governance helpers.
- Replaced `src/ui/panels/assets/question_library_governance_presenter.py` with `src/ui/panels/assets/question_library_issue_presenter.py`:
  - new mixin: `QuestionFigureLibraryIssuePresenterMixin`;
  - methods now describe local issue rows instead of governance rows.
- Updated `src/ui/panels/assets_panel.py`:
  - removed creation of `question_figure_library_bulk_governance_table`;
  - renamed the retained issue table object to `question_figure_asset_library_issue_table`;
  - changed the retained issue table headers to local wording;
  - connected the issue table into `_refresh_summary` together with the other local question-figure projections.
- Updated `src/ui/panels/assets/question_library_history_presenter.py` and `src/ui/panels/assets/question_library_master_version_presenter.py`:
  - route row-location through `_select_question_figure_library_issue_question_row`.
- Updated `src/config/scene_product_readiness.py` and `tests/test_scene_product_maturity_upgrade_audit.py`:
  - changed evidence from governance issue / bulk-governance plan to metadata issue UI bridge.
- Updated tests:
  - `tests/test_assets_question_library_presenter.py` now expects the issue presenter;
  - `tests/test_material_asset_services.py` now tests metadata issue projection and negative-asserts removed bulk APIs;
  - `tests/test_assets_panel_architecture.py` now guards that `_refresh_summary` refreshes the local question-figure projection tables, including metadata issue rows.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 3,305 lines, 75 functions/methods, 2 classes.
- `AssetsPanel`: 73 direct methods.
- `src/services/material_assets/question_library.py`: 1,600 lines, 41 functions.
- `src/services/material_assets/cache_projection.py`: 417 lines, 18 functions.
- `src/ui/panels/assets/question_library_issue_presenter.py`: 66 lines, 3 methods, 1 class.

Compared with Execution Record 28:

- `assets_panel.py` dropped from 3,343 lines to 3,305 lines.
- `question_library.py` dropped from 1,664 lines to 1,600 lines.
- `question_library.py` dropped from 44 functions to 41 functions.
- The old governance presenter file was removed; the retained issue presenter is smaller and narrower.
- `AssetsPanel` direct method count stayed flat because this pass removed table construction/export/service complexity rather than direct panel methods.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_library_issue_presenter.py src\ui\panels\assets\question_library_history_presenter.py src\ui\panels\assets\question_library_master_version_presenter.py src\services\material_assets\question_library.py src\services\material_assets\__init__.py tests\test_assets_panel_architecture.py tests\test_assets_question_library_presenter.py tests\test_material_asset_services.py tests\test_scene_product_maturity_upgrade_audit.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_question_library_presenter.py tests\test_scene_product_maturity_upgrade_audit.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused material/question-library/maturity/architecture regression: `31 passed`.
- Full related assets regression: `70 passed`.

Residual scan:

```powershell
rg -n "QuestionFigureLibraryGovernancePresenterMixin|question_library_governance_presenter|_question_figure_library_governance|_question_figure_library_bulk_governance|question_figure_library_governance|question_figure_library_bulk_governance|question_figure_bulk_governance|bulk_governance|bulk governance plan|governance issue UI bridge|bulk governance plan UI bridge|_select_question_figure_library_governance_question_row" src\ui\panels\assets_panel.py src\ui\panels\assets src\services\material_assets tests src\config\scene_product_readiness.py
```

Result:

- Deleted governance/bulk-governance implementation names remain only in `tests/test_material_asset_services.py` as negative assertions.
- Active code now uses `metadata_issue` / `question_figure_library_issue` naming for the retained local surface.

## 2026-07-07 Plan Review After Record 29

### Current Assessment

The enterprise-remote deletion phase is no longer the main optimization path. The active source has already removed the important enterprise execution chains:

- remote writeback;
- enterprise auth / signed URL refresh / external permission callback;
- master registry sync / subscription drift / SLA / worker recovery;
- non-question asset family remote governance;
- cache cleanup governance;
- question-library bulk governance.

The project is now healthier than at the start of this plan, but not fully clean:

- `AssetsPanel` is still large at 3,305 lines and 73 direct methods.
- Some retained local concepts still have compatibility names such as `remote_asset_id`, `remote_version`, and `remote_etag`; they should be treated as imported/library metadata, not active remote state.
- The remaining product surface should be reviewed by user value, not by old enterprise vocabulary.

### Optimized Next Path

1. Preserve the deletion guards.

   Keep negative tests for removed enterprise and bulk-governance identifiers. New refactors should add removed tokens to those tests instead of relying on documentation alone.

2. Add a local-neutral alias for asset identity before renaming compatibility metadata.

   Candidate:

   - add `asset_item_library_asset_id` or `asset_item_external_asset_id`;
   - keep `asset_item_remote_asset_id` as a compatibility alias temporarily;
   - update local call sites gradually;
   - only then consider metadata-key migration.

   This is safer than directly renaming saved metadata keys.

3. Continue product-surface simplification before control unification.

   Next deletion/reduction review candidates:

   - read-only preview URL naming and helper placement;
   - material repair queue / audit display duplication;
   - compatibility aliases in `assets_panel.py` that no longer need to be panel-level globals;
   - any remaining table that only restates data already shown in a clearer local table.

4. Resume structural slimming once the retained surface is stable.

   Best next extraction target is still the section shell group, because it can reduce `AssetsPanel` without touching product behavior:

   - `_build_section_navigation`;
   - `_build_section_pages`;
   - `_register_detail_cards`;
   - `_connect_signals`;
   - `_on_section_selected`;
   - `_sync_current_section_geometry`.

### Updated Recommendation

Do not restart broad enterprise deletion unless a new active enterprise capability appears in source scans.

Do not begin general control unification yet.

The next best implementation pass is a narrow local-neutral identity cleanup:

1. add a local/library asset-id accessor while keeping compatibility;
2. migrate call sites away from `remote_asset_id` wording where no network behavior exists;
3. run material-service, assets-panel, and maturity tests;
4. document whether the metadata key itself can remain as compatibility or needs a later migration.

## 2026-07-07 Execution Record 30: Library Asset ID Accessor Added

This pass executed the narrow local-neutral identity cleanup recommended after Record 29.

### Decision

Keep the saved metadata key:

- `asset_id`;
- legacy input alias `assetId`.

Add the local-neutral accessor:

- `asset_item_library_asset_id`;
- private helper `_asset_item_library_asset_id`.

Keep compatibility aliases:

- `asset_item_remote_asset_id`;
- `_asset_item_remote_asset_id`.

The important distinction is that `asset_id` is now documented in code shape as a library/imported asset identity, not proof that the app is performing remote network behavior.

### Completed

- Updated `src/services/material_assets/question_figures.py`:
  - added `_asset_item_library_asset_id`;
  - added public `asset_item_library_asset_id`;
  - made `asset_item_remote_asset_id` and `_asset_item_remote_asset_id` compatibility aliases;
  - migrated internal local question-figure matching, labels, detail rows, and status checks to the library accessor.
- Updated `src/services/material_assets/question_library.py`:
  - migrated local library rows, metadata issue rows, version consistency rows, and rollback row matching to `asset_item_library_asset_id`.
- Updated `src/services/material_assets/cache_projection.py`:
  - migrated local/shared cache row projection to `_asset_item_library_asset_id`.
- Updated `src/services/material_assets/__init__.py`:
  - exported `asset_item_library_asset_id`;
  - kept `asset_item_remote_asset_id`.
- Updated UI compatibility and presenter layers:
  - `src/ui/panels/assets/question_figures.py` exports new and old names;
  - `src/ui/panels/assets_panel.py` exposes `_asset_item_library_asset_id` and keeps `_asset_item_remote_asset_id`;
  - `src/ui/panels/assets/question_library_presenter.py` uses `asset_item_library_asset_id`.
- Updated `src/ui/panels/assets/enterprise_boundary.py`:
  - local question-figure boundary now lists `_asset_item_library_asset_id` before the old compatibility name.
- Updated tests:
  - `tests/test_material_asset_services.py` asserts the new public accessor and proves the old public accessor is an alias;
  - `tests/test_assets_panel_question_figures.py` asserts the new compatibility export and old alias behavior.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 3,307 lines, 75 functions/methods, 2 classes.
- `AssetsPanel`: 73 direct methods.
- `src/services/material_assets/question_figures.py`: 521 lines, 24 functions.
- `src/services/material_assets/question_library.py`: 1,600 lines, 41 functions.
- `src/services/material_assets/cache_projection.py`: 417 lines, 18 functions.
- `src/services/material_assets/__init__.py`: 209 lines.

Compared with Record 29:

- `assets_panel.py` increased by 2 lines for the new compatibility alias import/export.
- `question_figures.py` increased slightly because it now carries both the new name and old compatibility alias.
- `question_library.py` and `cache_projection.py` stayed the same size but now use the local-neutral accessor.

### Verification

Passed:

```powershell
python -m py_compile src\services\material_assets\question_figures.py src\services\material_assets\question_library.py src\services\material_assets\cache_projection.py src\services\material_assets\__init__.py src\ui\panels\assets_panel.py src\ui\panels\assets\question_figures.py src\ui\panels\assets\question_library_presenter.py src\ui\panels\assets\enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py tests\test_assets_question_library_presenter.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused accessor/material/assets architecture regression: `37 passed`.
- Full related assets regression: `70 passed`.

Residual scan:

```powershell
rg -n "asset_item_remote_asset_id|_asset_item_remote_asset_id|remote_asset_id" src\services\material_assets src\ui\panels\assets_panel.py src\ui\panels\assets tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_architecture.py
```

Result:

- Remaining old-name hits are compatibility exports/aliases, compatibility tests, and the local boundary registry compatibility prefix.
- Active local service logic now uses `asset_item_library_asset_id` / `_asset_item_library_asset_id`.
- No UTF-8 BOM remains in the touched service files; AST-based architecture guards parse them successfully.

## 2026-07-07 Plan Review After Record 30

### Current Assessment

The metadata key itself should remain `asset_id` for now. Renaming persisted keys would require a real archive migration and import/export compatibility audit; that would be higher risk than the current naming cleanup.

The useful cleanup achieved here is API-level clarity:

- new code can call `asset_item_library_asset_id`;
- old code and saved packages can keep working through `asset_item_remote_asset_id`;
- scans can now distinguish active local identity access from compatibility residue.

### Updated Recommendation

Next, continue product-surface simplification before structural shell extraction.

Best candidate:

1. Review read-only preview/cache URL naming and helper placement.
2. Keep path/cache/thumbnail read-only compatibility where it supports local document generation.
3. Remove or rename any remaining helper that implies active remote download/auth/writeback when it only reads imported metadata.
4. Do not rename saved metadata keys until there is a dedicated migration plan.

After that, resume `AssetsPanel` structural slimming:

- `_build_section_navigation`;
- `_build_section_pages`;
- `_register_detail_cards`;
- `_connect_signals`;
- `_on_section_selected`;
- `_sync_current_section_geometry`.

## 2026-07-07 Execution Record 31: Read-Only URL/Path Import Surface Tightened

This pass executed the next product-surface simplification step from Record 30: review read-only preview/cache URL naming and helper placement without breaking saved metadata compatibility.

### Decision

Keep:

- existing saved metadata read compatibility for local/cache paths;
- `cache_path`, `cached_path`, `local_path`, `resolved_path`, and thumbnail/preview path compatibility where the value is a local path;
- existing read compatibility in services for older payload aliases such as `download_path` and `remote_thumbnail_path`.

Remove from new batch import:

- `downloadPath` -> `cache_path`;
- `remoteThumbnailPath` -> `thumbnail_path`;
- `remoteThumbnailCachePath` -> `thumbnail_path`.

Rename internally:

- `_REMOVED_URL_METADATA_ALIAS_KEYS` -> `_URL_METADATA_WRITE_BLOCKLIST`.

This keeps old archives readable but stops new spreadsheet imports from reintroducing column names that imply active remote download behavior.

### Completed

- Updated `src/ui/panels/assets/batch_import.py`:
  - removed `downloadpath`;
  - removed `remotethumbnailpath`;
  - removed `remotethumbnailcachepath`.
- Updated `tests/test_assets_panel_architecture.py`:
  - added the three removed import fragments to `DELETED_IMPORT_FIELD_FRAGMENTS`;
  - the existing batch-import metadata alias guard now prevents those names from returning.
- Updated `src/services/material_assets/question_library.py`:
  - renamed the URL write-blocklist constant to `_URL_METADATA_WRITE_BLOCKLIST`;
  - kept behavior unchanged: attempts to set `download_url`, `asset_url`, `thumbnail_url`, or `preview_url` through local metadata editing clear those aliases instead of storing active URL metadata.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 3,307 lines, 75 functions/methods, 2 classes.
- `AssetsPanel`: 73 direct methods.
- `src/ui/panels/assets/batch_import.py`: 610 lines, 30 functions.
- `src/services/material_assets/question_library.py`: 1,600 lines, 41 functions.
- `src/services/material_assets/question_figures.py`: 521 lines, 24 functions.

Compared with Record 30:

- `batch_import.py` dropped by two lines.
- `question_library.py` stayed the same size; this was a naming clarity change.
- `AssetsPanel` did not change.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets\batch_import.py src\services\material_assets\question_library.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_question_cache.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused import/URL/cache regression: `41 passed`.
- Full related assets regression: `70 passed`.

Residual scan:

```powershell
rg -n "downloadpath|remotethumbnailpath|remotethumbnailcachepath|download_url|preview_url|asset_url|thumbnail_url|remote_asset_url_name|download_remote_asset_preview_image|is_remote_asset_preview_url|URL_METADATA_WRITE_BLOCKLIST|REMOVED_URL_METADATA_ALIAS_KEYS" src\services\material_assets src\ui\panels\assets_panel.py src\ui\panels\assets tests\test_assets_panel_architecture.py tests\test_material_asset_services.py tests\test_assets_panel_question_cache.py
```

Result:

- `downloadpath`, `remotethumbnailpath`, and `remotethumbnailcachepath` remain only in `tests/test_assets_panel_architecture.py` as removed-import negative guards.
- URL preview/download active helper names remain only in negative assertions.
- `_URL_METADATA_WRITE_BLOCKLIST` is the only active URL blocklist constant.

## 2026-07-07 Plan Review After Record 31

### Current Assessment

The remaining read-only path compatibility is now mostly acceptable:

- services can still read older local path aliases;
- new spreadsheet imports can no longer introduce the most misleading download/remote-thumbnail path aliases;
- URL metadata is blocked from local editor writeback.

The next optimization should now move from product-surface deletion back to structural slimming, because the remaining local surface is much narrower and guarded.

### Updated Recommendation

Resume `AssetsPanel` structural slimming with section shell extraction:

1. Extract `_build_section_navigation`, `_build_section_pages`, `_register_detail_cards`, `_connect_signals`, `_on_section_selected`, and `_sync_current_section_geometry` into a dedicated presenter/mixin.
2. Keep behavior unchanged and add/extend architecture tests proving `AssetsPanel` delegates those direct methods.
3. Run the same assets regression suite after extraction.

Do not start broad control unification yet. The next useful goal is reducing `AssetsPanel` direct method ownership, not changing widget design.

## 2026-07-07 Execution Record 32: Section Shell Presenter Extraction

This pass executed the structural slimming recommendation from Record 31. It moved the assets section shell construction and section-switching coordination out of `AssetsPanel`.

### Decision

Extract these direct `AssetsPanel` methods into a dedicated mixin:

- `_build_section_navigation`;
- `_build_section_pages`;
- `_register_detail_cards`;
- `_connect_signals`;
- `_on_section_selected`;
- `_sync_current_section_geometry`.

Keep behavior unchanged:

- same section specs;
- same navigation groups;
- same detail-stack and summary-card setup;
- same bridge signal wiring;
- same section selection geometry sync.

### Completed

- Added `src/ui/panels/assets/section_shell_presenter.py`:
  - new `SectionShellPresenterMixin`;
  - owns the 6 section-shell methods.
- Updated `src/ui/panels/assets_panel.py`:
  - imports `SectionShellPresenterMixin`;
  - adds it to the `AssetsPanel` base class list;
  - removes the 6 direct methods from `AssetsPanel`;
  - removes the now-local `QTimer` and `ASSETS_SECTION_SPECS` direct imports from the main file.
- Updated `tests/test_assets_panel_architecture.py`:
  - imports `SectionShellPresenterMixin`;
  - adds `SECTION_SHELL_METHODS`;
  - proves `AssetsPanel` subclasses the mixin;
  - proves the 6 methods live in the mixin and are no longer direct `AssetsPanel` methods.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 3,215 lines, 69 functions/methods, 2 classes.
- `AssetsPanel`: 67 direct methods.
- `src/ui/panels/assets/section_shell_presenter.py`: 121 lines, 6 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 242 lines, 13 functions.

Compared with Record 31:

- `assets_panel.py` dropped from 3,307 lines to 3,215 lines.
- `AssetsPanel` direct methods dropped from 73 to 67.
- Total behavior surface is unchanged; ownership moved from the main panel to a focused presenter mixin.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\section_shell_presenter.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_enterprise_boundary.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused section-shell/presenter regression: `42 passed`.
- Full related assets regression: `71 passed`.

Residual scan:

```powershell
rg -n "def _build_section_navigation|def _build_section_pages|def _register_detail_cards|def _connect_signals|def _on_section_selected|def _sync_current_section_geometry|SectionShellPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\section_shell_presenter.py tests\test_assets_panel_architecture.py
```

Result:

- The 6 method definitions exist only in `section_shell_presenter.py`.
- `assets_panel.py` only imports and subclasses `SectionShellPresenterMixin`.
- `tests/test_assets_panel_architecture.py` guards this ownership boundary.

## 2026-07-07 Plan Review After Record 32

### Current Assessment

The assets panel is now healthier:

- enterprise remote execution surfaces have been removed or guarded;
- local-only product surfaces have been renamed/shrunk;
- the section shell no longer bloats `AssetsPanel` directly;
- the main panel is down to 3,215 lines and 67 direct methods.

The remaining work is no longer about broad deletion. It is now mostly about continuing to move cohesive local UI/control groups out of `AssetsPanel`.

### Updated Recommendation

Continue structural slimming with the next low-risk group:

1. Review `_add_card_header`, field-status/unknown-placeholder helpers, and asset-slot status helpers.
2. Prefer extracting cohesive groups already implied by existing presenters.
3. Avoid changing widget design or copy while extracting.
4. Keep the same regression suite as the acceptance gate.

The next best candidate is the field helper group because it is still direct `AssetsPanel` behavior and touches local form projection rather than enterprise product policy.

## 2026-07-07 Execution Record 33: Field Status Presenter Extraction

This pass continued code slimming without changing product behavior. It moved the local field-status and unknown-placeholder UI projection out of `AssetsPanel`.

### Decision

Extract these direct `AssetsPanel` methods into a dedicated local presenter mixin:

- `_refresh_field_statuses`;
- `_refresh_unknown_field_suggestions`;
- `_add_unknown_placeholder_field`.

Keep behavior unchanged:

- same field parsing;
- same required-field status text;
- same unmatched-placeholder filtering;
- same unknown-placeholder quick-add behavior;
- same refresh and summary calls.

This is not an enterprise capability deletion. It is a local UI ownership cleanup: the main panel should not own every field status rendering detail directly.

### Completed

- Added `src/ui/panels/assets/field_status_presenter.py`:
  - new `FieldStatusPresenterMixin`;
  - owns the 3 field-status/unknown-placeholder methods;
  - imports only the UI and field helpers required by this group.
- Updated `src/ui/panels/assets_panel.py`:
  - imports `FieldStatusPresenterMixin`;
  - adds it to the `AssetsPanel` base class list;
  - removes the 3 direct methods from `AssetsPanel`;
  - removes no-longer-needed direct imports for this group.
- Updated `tests/test_assets_panel_architecture.py`:
  - imports `FieldStatusPresenterMixin`;
  - adds `FIELD_STATUS_METHODS`;
  - proves `AssetsPanel` subclasses the mixin;
  - proves the 3 methods live in the mixin and are no longer direct `AssetsPanel` methods.
- Cleaned a large leftover blank gap in `src/ui/panels/assets_panel.py`:
  - collapsed a 209-line empty block between `_refresh_asset_slot_statuses` and `_select_question_figure_library_issue_question_row` to a normal 2-line separator;
  - no logic changed.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 2,869 lines, 66 functions/methods, 2 classes.
- `AssetsPanel`: 64 direct methods.
- `src/ui/panels/assets/field_status_presenter.py`: 170 lines, 3 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 261 lines, 14 functions.

Compared with Record 32:

- `assets_panel.py` dropped from 3,215 lines to 2,869 lines.
- `AssetsPanel` direct methods dropped from 67 to 64.
- The line reduction includes both the method extraction and removal of the stale 209-line blank gap.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\field_status_presenter.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_enterprise_boundary.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused field-status/presenter regression: `34 passed`.
- Full related assets regression: `72 passed`.

Residual scan:

```powershell
rg -n "def _refresh_field_statuses|def _refresh_unknown_field_suggestions|def _add_unknown_placeholder_field|FieldStatusPresenterMixin|def _refresh_asset_slot_statuses|def _select_question_figure_library_issue_question_row" src\ui\panels\assets_panel.py src\ui\panels\assets\field_status_presenter.py tests\test_assets_panel_architecture.py
```

Result:

- The 3 field-status method definitions exist only in `field_status_presenter.py`.
- `assets_panel.py` only imports and subclasses `FieldStatusPresenterMixin`.
- The asset-slot method gap is now compact; `_select_question_figure_library_issue_question_row` follows after a normal separator.

## 2026-07-07 Plan Review After Record 33

### Current Assessment

The assets panel is healthier than at the start of this phase:

- enterprise remote execution/writeback surfaces have already been removed or guarded;
- local-only field and section-shell projection logic has moved out of the main panel;
- `assets_panel.py` is now below 3,000 lines;
- direct `AssetsPanel` method ownership is down to 64 methods.

The next work should stay focused on code slimming. Do not start broad control unification yet. The useful acceptance criterion for the next pass is simple: either delete a redundant abstraction or move a cohesive local UI group out of `AssetsPanel` with an architecture test.

### Optimized Recommendation

Proceed in this order:

1. Remove the trivial `_add_card_header` wrapper.
   - Current call sites only pass `card`, `icon_name`, and `title`.
   - The optional `description` path is unused.
   - Replace calls with `card.set_header(title, icon_name=icon_name)` and delete the method.
   - This is a true simplification, not another mixin.
2. Extract asset/attachment slot status projection.
   - Candidate methods: `_refresh_asset_slot_statuses`, `_refresh_attachment_role_statuses`, `_set_asset_thumbnail`.
   - This group is local UI status projection: labels, button enablement, and thumbnails.
   - Keep `_set_image_preview` under review separately because it fits the existing `ImagePreviewPresenterMixin` better than an asset-slot presenter.
3. After that, review preview-state helpers as a higher-risk group.
   - Candidate methods: `_placeholder_source_path`, `_scanned_placeholders`, `_current_preview_state`, `_missing_attachment_roles`, `_unmatched_placeholders`, `_placeholder_preview_rows`.
   - This touches placeholder matching and generated-preview semantics, so it should only happen after the lower-risk UI projection moves.

Acceptance gate for each pass:

- add/extend architecture tests proving method ownership;
- run py-compile on changed modules;
- run focused assets tests;
- run the full related assets regression suite.

## 2026-07-07 Execution Record 34: Wrapper Deletion, Slot Status Extraction, Preview State Consolidation

This pass executed the optimized recommendation from Record 33. It focused on code slimming rather than control redesign.

### Decision

Apply three scoped changes:

1. Delete the trivial `_add_card_header` wrapper.
   - All call sites only forwarded `card`, `icon_name`, and `title`.
   - The optional `description` branch had no active call site.
   - Direct `card.set_header(title, icon_name=icon_name)` calls are clearer and remove an unnecessary method.
2. Extract asset/attachment slot status projection.
   - Move `_refresh_asset_slot_statuses`, `_refresh_attachment_role_statuses`, and `_set_asset_thumbnail` into a dedicated `AssetSlotStatusPresenterMixin`.
   - Keep `_set_image_preview` in `AssetsPanel` for now because it coordinates the inline preview label with the full-image preview state.
3. Consolidate preview-state helpers into the existing `PreviewTablePresenterMixin`.
   - Move `_placeholder_source_path`, `_scanned_placeholders`, `_current_preview_state`, `_missing_attachment_roles`, `_unmatched_placeholders`, and `_placeholder_preview_rows`.
   - This keeps placeholder scanning, preview-state construction, preview text, table row construction, and preview row actions in one presenter boundary.

### Completed

- Updated `src/ui/panels/assets_panel.py`:
  - replaced 8 `_add_card_header(...)` calls with direct `card.set_header(...)`;
  - deleted `_add_card_header`;
  - imports and subclasses `AssetSlotStatusPresenterMixin`;
  - removed 3 slot-status direct methods from `AssetsPanel`;
  - moved 6 preview-state direct methods out of `AssetsPanel`;
  - removed now-unused preview-state imports, while keeping `_asset_slot_role_for_token` as a module-level compatibility alias required by existing tests;
  - collapsed the empty gap left by the preview-state move.
- Added `src/ui/panels/assets/asset_slot_status_presenter.py`:
  - new `AssetSlotStatusPresenterMixin`;
  - owns the 3 asset/attachment slot status projection methods.
- Updated `src/ui/panels/assets/preview_table_presenter.py`:
  - now owns the 6 preview-state/helper methods;
  - imports placeholder scanning, replacement parsing, image rule parsing, field alias helpers, and asset role matching locally.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds `ASSET_SLOT_STATUS_METHODS`;
  - adds `PREVIEW_STATE_METHODS`;
  - proves slot status methods live in `AssetSlotStatusPresenterMixin`;
  - proves preview-state methods live in `PreviewTablePresenterMixin`;
  - proves `_add_card_header` stays removed.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends the `PreviewTablePresenterMixin` ownership test to include the 6 preview-state methods.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 2,427 lines, 56 functions/methods, 2 classes.
- `AssetsPanel`: 54 direct methods.
- `src/ui/panels/assets/asset_slot_status_presenter.py`: 76 lines, 3 methods, 1 class.
- `src/ui/panels/assets/preview_table_presenter.py`: 487 lines, 10 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 314 lines, 17 functions.
- `tests/test_assets_panel_helper_modules.py`: 343 lines, 17 functions.

Compared with Record 33:

- `assets_panel.py` dropped from 2,869 lines to 2,427 lines.
- `AssetsPanel` direct methods dropped from 64 to 54.
- The main panel no longer owns card-header forwarding, slot status rendering, placeholder scanning, preview-state construction, or preview row construction directly.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\asset_slot_status_presenter.py src\ui\panels\assets\preview_table_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `42 passed`.
- Full related assets regression: `75 passed`.

Residual scan:

```powershell
rg -n "_add_card_header|def _refresh_asset_slot_statuses|def _refresh_attachment_role_statuses|def _set_asset_thumbnail|def _placeholder_source_path|def _scanned_placeholders|def _current_preview_state|def _missing_attachment_roles|def _unmatched_placeholders|def _placeholder_preview_rows|AssetSlotStatusPresenterMixin|PreviewTablePresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\asset_slot_status_presenter.py src\ui\panels\assets\preview_table_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
```

Result:

- `_add_card_header` remains only as a removed-wrapper guard in tests.
- The 3 slot-status method definitions exist only in `asset_slot_status_presenter.py`.
- The 6 preview-state method definitions exist only in `preview_table_presenter.py`.
- `assets_panel.py` only imports/subclasses the relevant presenters and calls the delegated methods.

## 2026-07-07 Plan Review After Record 34

### Current Assessment

The main panel is now substantially slimmer:

- `assets_panel.py` is down to 2,427 lines;
- `AssetsPanel` is down to 54 direct methods;
- section shell, field status, slot status, preview table/state, question figures, question library, cache, section summary, responsive layout, profile, archive, batch output, image preview dialog, and material-repair navigation are already delegated;
- enterprise remote/writeback surfaces remain removed or guarded.

The remaining direct methods are now more concentrated around orchestration and editor state mutation. The next passes should be more selective, because the easy deletion/extraction targets are mostly done.

### Updated Recommendation

Proceed in this order:

1. Move `_set_image_preview` into `ImagePreviewPresenterMixin`.
   - It already calls `_set_current_image_preview_path`, which lives in that mixin.
   - It is a small move with clear ownership: inline preview label + full-image preview state.
2. Review local asset file operations as a cohesive presenter boundary.
   - Candidate methods: `_path_for_asset_slot`, `_select_asset_file`, `_select_attachment_file`, `_attachment_role_spec`, `_handle_asset_drag_event`, `_apply_asset_slot_path`, `_clear_asset_file`, `_clear_attachment_file`, `_show_asset_slot_path`, `_open_asset_slot_path`, `_open_attachment_path`, `_open_file_path`.
   - This group is still local-only, but it touches dialogs, drag/drop, and path mutation, so move it in one careful pass with focused tests.
3. Defer `_refresh_summary` extraction until after local file operations.
   - It is now a thinner orchestrator, but it still coordinates many presenters.
   - Extracting it too early risks hiding the main panel workflow rather than simplifying it.

Do not resume broad control unification yet. The codebase is still getting more value from reducing direct ownership and clarifying presenter boundaries.

## 2026-07-07 Execution Record 35: Inline Image Preview Ownership Move

This pass executed the first recommendation after Record 34: move `_set_image_preview` into `ImagePreviewPresenterMixin`.

### Decision

Move `_set_image_preview` out of `AssetsPanel` because it belongs with the existing image preview presenter:

- it updates the inline preview label;
- it calls `_set_current_image_preview_path`, already owned by `ImagePreviewPresenterMixin`;
- it updates the same status label used by full-image preview behavior;
- it does not own file selection, drag/drop, or asset path mutation.

### Completed

- Updated `src/ui/panels/assets/image_preview_presenter.py`:
  - added `_set_image_preview`;
  - imported `_asset_role_label`, `_image_quality_text`, and `_load_scaled_pixmap` locally.
- Updated `src/ui/panels/assets_panel.py`:
  - removed `_set_image_preview` as a direct `AssetsPanel` method;
  - kept call sites unchanged, now resolved through `ImagePreviewPresenterMixin`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - added `_set_image_preview` to the `ImagePreviewPresenterMixin` ownership assertion.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 2,408 lines, 55 functions/methods, 2 classes.
- `AssetsPanel`: 53 direct methods.
- `src/ui/panels/assets/image_preview_presenter.py`: 609 lines, 15 methods, 1 class.
- `tests/test_assets_panel_helper_modules.py`: 344 lines, 17 functions.

Compared with Record 34:

- `assets_panel.py` dropped from 2,427 lines to 2,408 lines.
- `AssetsPanel` direct methods dropped from 54 to 53.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\image_preview_presenter.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_helper_modules.py tests\test_assets_panel_architecture.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused image-preview/helper regression: `32 passed`.
- Full related assets regression: `75 passed`.

Residual scan:

```powershell
rg -n "def _set_image_preview|_set_image_preview|ImagePreviewPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\image_preview_presenter.py tests\test_assets_panel_helper_modules.py
```

Result:

- `_set_image_preview` is defined only in `image_preview_presenter.py`.
- `assets_panel.py` only calls `_set_image_preview` through mixin resolution.
- `tests/test_assets_panel_helper_modules.py` guards this ownership boundary.

## 2026-07-07 Plan Review After Record 35

### Current Assessment

The remaining direct `AssetsPanel` methods are now mostly workflow and local mutation methods. The panel is still large, but its shape is healthier:

- section shell and section summaries are delegated;
- field status, slot status, preview state/table, and image preview are delegated;
- question figure/library/cache/audit surfaces are delegated or service-backed;
- remote enterprise/writeback surfaces remain out of the product path.

### Updated Recommendation

Next, review local asset file operations as one cohesive boundary:

- `_path_for_asset_slot`;
- `_select_asset_file`;
- `_select_attachment_file`;
- `_attachment_role_spec`;
- `_handle_asset_drag_event`;
- `_apply_asset_slot_path`;
- `_clear_asset_file`;
- `_clear_attachment_file`;
- `_show_asset_slot_path`;
- `_open_asset_slot_path`;
- `_open_attachment_path`;
- `_open_file_path`.

This group is a good next candidate because it is still local-only and strongly cohesive: select, drag, store, clear, reveal, and open material paths. It should not be mixed with summary/preview generation logic.

Acceptance gate:

- move the group into a dedicated presenter such as `AssetFileOperationsPresenterMixin`;
- keep behavior unchanged;
- add/extend architecture/helper tests proving ownership;
- run py-compile, focused assets tests, and the full related assets regression suite.

## 2026-07-07 Execution Record 36: Local Asset File Operations Presenter Extraction

This pass executed the recommendation from Record 35. It moved local material path operations out of `AssetsPanel`.

### Decision

Extract this cohesive local-only group into `AssetFileOperationsPresenterMixin`:

- `_path_for_asset_slot`;
- `_select_asset_file`;
- `_select_attachment_file`;
- `_attachment_role_spec`;
- `_handle_asset_drag_event`;
- `_apply_asset_slot_path`;
- `_clear_asset_file`;
- `_clear_attachment_file`;
- `_show_asset_slot_path`;
- `_open_asset_slot_path`;
- `_open_attachment_path`;
- `_open_file_path`.

Keep behavior unchanged:

- same file dialogs;
- same drag/drop acceptance;
- same local path mutation;
- same summary and material-batch refresh calls;
- same local file opening behavior;
- same attachment role lookup behavior.

### Completed

- Added `src/ui/panels/assets/asset_file_operations_presenter.py`:
  - new `AssetFileOperationsPresenterMixin`;
  - owns the 12 local asset file operation methods.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and subclasses `AssetFileOperationsPresenterMixin`;
  - removes the 12 direct methods from `AssetsPanel`;
  - removes no-longer-needed direct imports for `QDesktopServices`, `QUrl`, `_asset_role_label`, and `_attachment_file_filter`;
  - keeps `_first_image_path_from_mime` as a module-level compatibility alias required by existing helper tests;
  - collapses the empty gap left by the move.
- Updated `tests/test_assets_panel_architecture.py`:
  - imports `AssetFileOperationsPresenterMixin`;
  - adds `ASSET_FILE_OPERATION_METHODS`;
  - proves the 12 methods live in the mixin and are no longer direct `AssetsPanel` methods.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds a helper-level ownership test for `AssetFileOperationsPresenterMixin`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 2,303 lines, 43 functions/methods, 2 classes.
- `AssetsPanel`: 41 direct methods.
- `src/ui/panels/assets/asset_file_operations_presenter.py`: 117 lines, 12 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 342 lines, 18 functions.
- `tests/test_assets_panel_helper_modules.py`: 373 lines, 18 functions.

Compared with Record 35:

- `assets_panel.py` dropped from 2,408 lines to 2,303 lines.
- `AssetsPanel` direct methods dropped from 53 to 41.
- The main panel no longer directly owns local file selection, drag/drop path application, clear/show/open path behavior, or attachment role lookup.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\asset_file_operations_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `44 passed`.
- Full related assets regression: `77 passed`.

Residual scan:

```powershell
rg -n "def _path_for_asset_slot|def _select_asset_file|def _select_attachment_file|def _attachment_role_spec|def _handle_asset_drag_event|def _apply_asset_slot_path|def _clear_asset_file|def _clear_attachment_file|def _show_asset_slot_path|def _open_asset_slot_path|def _open_attachment_path|def _open_file_path|AssetFileOperationsPresenterMixin|QDesktopServices|QUrl" src\ui\panels\assets_panel.py src\ui\panels\assets\asset_file_operations_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
```

Result:

- The 12 method definitions exist only in `asset_file_operations_presenter.py`.
- `assets_panel.py` only imports/subclasses `AssetFileOperationsPresenterMixin`.
- `QDesktopServices` and `QUrl` are no longer direct imports of `assets_panel.py`.

## 2026-07-07 Plan Review After Record 36

### Current Assessment

`AssetsPanel` is now much closer to a coordinator than a catch-all implementation class:

- `assets_panel.py` is down to 2,303 lines;
- `AssetsPanel` is down to 41 direct methods;
- local file operations, image preview, preview state/table, slot status, field status, section shell, section summary, responsive layout, archive/profile/batch output, material repair navigation, question figures/library/cache/audit are delegated.

The remaining direct methods cluster into three broad groups:

- top-level UI/wiring and public archive/context API;
- local editor state mutation;
- local asset/profile data projection;
- summary/theme orchestration.

### Updated Recommendation

Proceed in this order:

1. Extract field editor state helpers.
   - Candidate methods: `_on_structured_field_changed`, `_on_more_fields_changed`, `_on_required_fields_changed`, `_required_field_keys`, `_editor_fields`, `_set_structured_fields`.
   - This keeps form state mutation and field parsing together with the existing field-status boundary.
2. Extract asset collection/data projection helpers.
   - Candidate methods: `_asset_items_for_profile`, `_current_asset_items`, `_current_asset_metadata`, `_image_rules_for_asset_items`.
   - This group should remain separate from file operations because it projects current data, not user file actions.
3. Keep `_refresh_summary` and `_apply_theme` direct for now.
   - They are now orchestrators over presenters.
   - Moving them before the remaining state helpers would hide rather than simplify the workflow.

Acceptance gate remains:

- presenter ownership tests;
- py-compile;
- focused assets tests;
- full related assets regression.

## 2026-07-07 Execution Record 37: Field Editor State Presenter Extraction

This pass executed the first recommendation after Record 36. It moved local field editor state mutation out of `AssetsPanel`.

### Decision

Extract this group into a dedicated `FieldEditorStatePresenterMixin`:

- `_on_structured_field_changed`;
- `_on_more_fields_changed`;
- `_on_required_fields_changed`;
- `_required_field_keys`;
- `_editor_fields`;
- `_set_structured_fields`.

Keep field rendering separate:

- `FieldEditorStatePresenterMixin` owns field value mutation and parsing;
- `FieldStatusPresenterMixin` continues to own status labels and unknown-placeholder suggestions.

The removed remote-download credential field blacklist moved with the editor-state methods, because it is only used when reading/writing local field editor values.

### Completed

- Added `src/ui/panels/assets/field_editor_state_presenter.py`:
  - new `FieldEditorStatePresenterMixin`;
  - owns the 6 field editor state methods;
  - owns `_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS`.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and subclasses `FieldEditorStatePresenterMixin`;
  - removes the 6 direct methods from `AssetsPanel`;
  - removes the old local `_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS` constant;
  - removes now-unused direct imports of `_format_fields_text` and `_parse_required_fields_text`;
  - collapses the empty gap left by the move.
- Updated `tests/test_assets_panel_architecture.py`:
  - imports `FieldEditorStatePresenterMixin`;
  - adds `FIELD_EDITOR_STATE_METHODS`;
  - proves the 6 methods live in the mixin and are no longer direct `AssetsPanel` methods.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds a helper-level ownership test for `FieldEditorStatePresenterMixin`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 2,250 lines, 37 functions/methods, 2 classes.
- `AssetsPanel`: 35 direct methods.
- `src/ui/panels/assets/field_editor_state_presenter.py`: 71 lines, 6 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 364 lines, 19 functions.
- `tests/test_assets_panel_helper_modules.py`: 393 lines, 19 functions.

Compared with Record 36:

- `assets_panel.py` dropped from 2,303 lines to 2,250 lines.
- `AssetsPanel` direct methods dropped from 41 to 35.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\field_editor_state_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `46 passed`.
- Full related assets regression: `79 passed`.

Residual scan:

```powershell
rg -n "def _on_structured_field_changed|def _on_more_fields_changed|def _on_required_fields_changed|def _required_field_keys|def _editor_fields|def _set_structured_fields|FieldEditorStatePresenterMixin|_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS|_format_fields_text|_parse_required_fields_text" src\ui\panels\assets_panel.py src\ui\panels\assets\field_editor_state_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
```

Result:

- The 6 method definitions exist only in `field_editor_state_presenter.py`.
- `_REMOVED_ASSET_DOWNLOAD_CREDENTIAL_FIELD_KEYS` exists only in `field_editor_state_presenter.py`.
- `assets_panel.py` only imports/subclasses `FieldEditorStatePresenterMixin`.

## 2026-07-07 Plan Review After Record 37

### Current Assessment

`AssetsPanel` now has 35 direct methods. The remaining direct methods are increasingly meaningful:

- public archive/context API and import/export bridge methods;
- scene/context/document editor application;
- profile selection;
- asset collection/data projection;
- question-figure repair application and audit recording;
- summary/theme orchestration.

The next best extraction remains asset collection/data projection, because it is cohesive and feeds existing presenters without owning UI actions.

### Updated Recommendation

Extract asset collection/data projection helpers next:

- `_asset_items_for_profile`;
- `_current_asset_items`;
- `_current_asset_metadata`;
- `_image_rules_for_asset_items`.

Use a dedicated presenter such as `AssetCollectionStatePresenterMixin`.

Keep these separate from:

- file operations, which already moved to `AssetFileOperationsPresenterMixin`;
- preview state, which already lives in `PreviewTablePresenterMixin`;
- summary orchestration, which should remain direct until the data projection helpers are gone.

Acceptance gate:

- presenter ownership tests;
- py-compile;
- focused assets tests;
- full related assets regression.

## 2026-07-07 Execution Record 38: Asset Collection State Presenter Extraction

This pass executed the recommendation from Record 37. It moved asset collection/data projection helpers out of `AssetsPanel`.

### Decision

Extract this projection-only group into `AssetCollectionStatePresenterMixin`:

- `_asset_items_for_profile`;
- `_current_asset_items`;
- `_current_asset_metadata`;
- `_image_rules_for_asset_items`.

Keep this separate from local file operations:

- `AssetFileOperationsPresenterMixin` owns user actions such as select, drag, clear, show, and open;
- `AssetCollectionStatePresenterMixin` owns data projection from folders, payloads, manual paths, metadata, and insertion-rule text.

### Completed

- Added `src/ui/panels/assets/asset_collection_state_presenter.py`:
  - new `AssetCollectionStatePresenterMixin`;
  - owns the 4 asset collection/data projection methods.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and subclasses `AssetCollectionStatePresenterMixin`;
  - removes the 4 direct methods from `AssetsPanel`;
  - removes now-unused direct imports of `AssetInsertionRule`, `asset_items_from_role_paths`, `parse_asset_insertion_rules`, `scan_asset_collection`, `_asset_items_from_payloads`, and `_asset_items_with_metadata`;
  - keeps `_normalized_asset_metadata` as a module-level compatibility alias required by existing helper tests;
  - collapses the empty gap left by the move.
- Updated `tests/test_assets_panel_architecture.py`:
  - imports `AssetCollectionStatePresenterMixin`;
  - adds `ASSET_COLLECTION_STATE_METHODS`;
  - proves the 4 methods live in the mixin and are no longer direct `AssetsPanel` methods.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds a helper-level ownership test for `AssetCollectionStatePresenterMixin`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 2,179 lines, 33 functions/methods, 2 classes.
- `AssetsPanel`: 31 direct methods.
- `src/ui/panels/assets/asset_collection_state_presenter.py`: 88 lines, 4 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 384 lines, 20 functions.
- `tests/test_assets_panel_helper_modules.py`: 414 lines, 20 functions.

Compared with Record 37:

- `assets_panel.py` dropped from 2,250 lines to 2,179 lines.
- `AssetsPanel` direct methods dropped from 35 to 31.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\asset_collection_state_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `48 passed`.
- Full related assets regression: `81 passed`.

Residual scan:

```powershell
rg -n "def _asset_items_for_profile|def _current_asset_items|def _current_asset_metadata|def _image_rules_for_asset_items|AssetCollectionStatePresenterMixin|AssetInsertionRule|asset_items_from_role_paths|parse_asset_insertion_rules|scan_asset_collection|_asset_items_from_payloads|_asset_items_with_metadata" src\ui\panels\assets_panel.py src\ui\panels\assets\asset_collection_state_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
```

Result:

- The 4 method definitions exist only in `asset_collection_state_presenter.py`.
- Collection projection dependencies moved out of direct `assets_panel.py` imports.
- `assets_panel.py` only imports/subclasses `AssetCollectionStatePresenterMixin` and calls the delegated methods.

## 2026-07-07 Plan Review After Record 38

### Current Assessment

`AssetsPanel` now has 31 direct methods. The remaining direct methods are no longer obviously accidental helpers:

- public archive/context APIs;
- scene/material/document application;
- profile selection;
- question-figure repair actions and repair audit recording;
- summary/theme orchestration.

The next best extraction candidate is the question-figure repair action group, because it is cohesive and already has nearby question-figure presenters/services.

### Updated Recommendation

Review and extract the question-figure repair action group:

- `_select_question_figure_library_issue_question_row`;
- `_select_question_figure_item_file`;
- `_replace_question_figure_item_path`;
- `apply_question_figure_repair_candidate`;
- `_record_question_figure_repair_application`;
- `_record_question_figure_repair_rollback`.

Preferred destination:

- existing `QuestionFigureItemsPresenterMixin`, if the methods fit table selection/replacement behavior;
- otherwise a small `QuestionFigureRepairActionsPresenterMixin`.

Keep `_refresh_summary` and `_apply_theme` direct until repair actions are moved. They are still orchestration points and are easier to reason about after the action methods are no longer interleaved with them.

## 2026-07-07 Execution Record 39: Question-Figure Repair Actions Presenter Extraction

This pass executed the recommendation from Record 38. It moved local question-figure repair application and repair audit write helpers out of `AssetsPanel`.

### Decision

Extract this cohesive local repair-action group into `QuestionFigureRepairActionsPresenterMixin`:

- `_select_question_figure_library_issue_question_row`;
- `_select_question_figure_item_file`;
- `_replace_question_figure_item_path`;
- `apply_question_figure_repair_candidate`;
- `_record_question_figure_repair_application`;
- `_record_question_figure_repair_rollback`.

This is not an enterprise remote writeback feature. The group applies a local replacement path, refreshes local panel state, and appends local repair audit records. Keeping it separate from the main panel makes the remaining `AssetsPanel` methods easier to classify:

- public archive/context API;
- scene/material/document application;
- selected profile lookup;
- summary/theme orchestration.

### Completed

- Added `src/ui/panels/assets/question_figure_repair_actions_presenter.py`:
  - new `QuestionFigureRepairActionsPresenterMixin`;
  - owns the 6 local repair action and repair audit helper methods.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and subclasses `QuestionFigureRepairActionsPresenterMixin`;
  - removes the 6 direct methods from `AssetsPanel`;
  - collapses the blank gap left by the extraction.
- Updated `tests/test_assets_panel_architecture.py`:
  - imports `QuestionFigureRepairActionsPresenterMixin`;
  - adds `QUESTION_FIGURE_REPAIR_ACTION_METHODS`;
  - proves the 6 methods live in the mixin and no longer live directly on `AssetsPanel`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds a runtime MRO ownership test for `QuestionFigureRepairActionsPresenterMixin`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 2,010 lines, 27 functions/methods, 2 classes.
- `AssetsPanel`: 25 direct methods.
- `src/ui/panels/assets/question_figure_repair_actions_presenter.py`: 196 lines, 6 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 408 lines, 21 functions.
- `tests/test_assets_panel_helper_modules.py`: 437 lines, 21 functions.

Compared with Record 38:

- `assets_panel.py` dropped from 2,179 lines to 2,010 lines.
- `AssetsPanel` direct methods dropped from 31 to 25.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_figure_repair_actions_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_audit.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-audit regression: `52 passed`.
- Full related assets regression: `83 passed`.

Residual scan:

```powershell
rg -n "QuestionFigureRepairActionsPresenterMixin|def _select_question_figure|def _replace_question_figure|def apply_question_figure_repair_candidate|def _record_question_figure" src\ui\panels\assets_panel.py src\ui\panels\assets\question_figure_repair_actions_presenter.py tests
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
rg -n "asset_item_remote_asset_id|_asset_item_remote_asset_id|remote_asset_id|remote_version|remote_etag|remote_" src\services\material_assets src\ui\panels\assets_panel.py src\ui\panels\assets tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_architecture.py
```

Result:

- The 6 method definitions exist only in `question_figure_repair_actions_presenter.py`.
- `assets_panel.py` only imports/subclasses `QuestionFigureRepairActionsPresenterMixin`.
- Active enterprise remote execution tokens are absent from `src`; remaining hits for those tokens are negative guard tests.
- Remaining `remote_*` names in source are compatibility/local metadata surfaces:
  - `asset_item_remote_asset_id` / `_asset_item_remote_asset_id` compatibility aliases for imported/library asset identity;
  - `remote_version`, `remote_etag`, `remote_updated_at` as read-only imported/library metadata;
  - `remote_thumbnail_path` / `remote_thumbnail_cache_path` as legacy import aliases;
  - `remote_cache_dir` / `remote_asset_cache_dir` as cache projection compatibility labels;
  - removed credential field blacklist entries in `FieldEditorStatePresenterMixin`.

## 2026-07-07 Plan Review After Record 39

### Current Assessment

The earlier enterprise-remote deletion concern has largely been resolved in the active source. The scan and regression tests show that the high-risk enterprise chains are no longer implemented in `src`:

- remote writeback;
- enterprise auth / signed URL refresh / external permission callback;
- master registry / registry sync;
- subscription lock/change/drift;
- non-question asset family remote governance;
- active remote preview auth/download helper.

So the plan should not restart a broad "delete all remote" campaign. That would now risk deleting local compatibility and imported metadata that still help old archives, spreadsheets, and cache views load correctly.

The more precise product boundary is:

- delete or guard active remote behavior;
- keep local/imported metadata compatibility until there is a migration path;
- rename compatibility APIs only when call sites and tests can prove no old archive path is broken.

### Refined Next Step

Do not prioritize control unification yet. The next maintenance pass should stay focused on code simplification and product-boundary clarity:

1. Stabilize the remaining `AssetsPanel` direct-method map.
   - Current direct methods: 25.
   - Keep public archive/context APIs direct unless there is a clear facade boundary.
   - Keep `_refresh_summary` and `_apply_theme` direct for now because they orchestrate many presenters.
2. Review the scene/material/document application group as the next extraction candidate.
   - Candidate methods: `_apply_current_profile`, `_toggle_preview_filter`, `_on_preview_auto_match`, `_open_document_generation`, `_load_mapping_dialog`, `_apply_mapping_payload`, `_on_material_context_changed`, `_on_document_loaded`, `_set_editor_values`.
   - Extract only if the group can be named as a real product responsibility, such as `MaterialContextApplicationPresenterMixin`.
   - Do not make a generic "misc presenter".
3. Separately plan a compatibility-name cleanup pass.
   - Keep `asset_item_remote_asset_id` readable for now.
   - Prefer new code paths to use library/import identity wording instead of remote wording.
   - Keep negative tests for removed enterprise remote behavior.
4. Do not delete local retained capabilities:
   - question-figure item/list rendering;
   - local question-figure repair application;
   - local repair audit records and rollback records;
   - shared cache projection/status tables;
   - read-only imported/library metadata.

### Optimized Acceptance Gate

Each next pass should pass all of these:

- `AssetsPanel` direct method count decreases or the remaining direct methods become better classified.
- No active enterprise remote tokens return to `src`.
- Existing compatibility aliases remain tested until a migration is designed.
- Focused assets tests pass.
- Full related assets regression passes.

### Stop Conditions

Pause extraction and re-review if any of these happen:

- a method group has no honest product name;
- moving a group requires cross-presenter circular imports;
- deleting a `remote_*` name breaks old archive/import compatibility rather than only deleting active remote behavior;
- `_refresh_summary` starts becoming harder to read after more presenter extraction.

At this point, the healthiest path is no longer "delete remote wholesale"; it is "keep enterprise execution deleted, keep compatibility guarded, and continue shrinking the main panel around real local product responsibilities."

## 2026-07-07 Execution Record 40: Material Context Application and Preview State Split

This pass executed the refined next step from Record 39. It did not force all candidate methods into one presenter. Instead, it split them by product responsibility.

### Decision

Move profile/mapping/material-context application into a new `MaterialContextApplicationPresenterMixin`:

- `_apply_current_profile`;
- `_open_document_generation`;
- `_load_mapping_dialog`;
- `_apply_mapping_payload`;
- `_on_material_context_changed`;
- `_set_editor_values`.

Move preview/document cache state actions into the existing `PreviewTablePresenterMixin`:

- `_toggle_preview_filter`;
- `_on_preview_auto_match`;
- `_on_document_loaded`.

Reason:

- mapping payloads, bridge material context, generation entry, and editor value projection are one coherent product responsibility: applying external/current material data to the local editor;
- preview filtering and placeholder cache invalidation are already part of preview-table state, not material-context application;
- this avoids creating a vague "misc presenter".

### Completed

- Added `src/ui/panels/assets/material_context_application_presenter.py`:
  - new `MaterialContextApplicationPresenterMixin`;
  - owns 6 profile/mapping/material-context application methods.
- Updated `src/ui/panels/assets/preview_table_presenter.py`:
  - moved preview filter toggle;
  - moved preview auto-match cache reset;
  - moved document-loaded placeholder cache reset.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and subclasses `MaterialContextApplicationPresenterMixin`;
  - removes 9 direct methods from `AssetsPanel`;
  - removes now-unused direct imports of `QFileDialog`, `_asset_item_payload`, and `_imported_field_keys_from_sources`.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds `MATERIAL_CONTEXT_APPLICATION_METHODS`;
  - extends `PREVIEW_STATE_METHODS`;
  - proves the moved methods are owned by the correct mixins and no longer direct `AssetsPanel` methods.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership test for `MaterialContextApplicationPresenterMixin`;
  - extends the preview-table ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,841 lines, 18 functions/methods, 2 classes.
- `AssetsPanel`: 16 direct methods.
- `src/ui/panels/assets/material_context_application_presenter.py`: 176 lines, 6 methods, 1 class.
- `src/ui/panels/assets/preview_table_presenter.py`: 507 lines, 13 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 435 lines, 22 functions.
- `tests/test_assets_panel_helper_modules.py`: 463 lines, 22 functions.

Compared with Record 39:

- `assets_panel.py` dropped from 2,010 lines to 1,841 lines.
- `AssetsPanel` direct methods dropped from 25 to 16.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\material_context_application_presenter.py src\ui\panels\assets\preview_table_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_audit.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-audit regression: `54 passed`.
- Full related assets regression: `85 passed`.

Residual scan:

```powershell
rg -n "def _toggle_preview_filter|def _on_preview_auto_match|def _on_document_loaded|def _apply_current_profile|def _open_document_generation|def _load_mapping_dialog|def _apply_mapping_payload|def _on_material_context_changed|def _set_editor_values|MaterialContextApplicationPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- The 6 material-context application methods exist only in `material_context_application_presenter.py`.
- The 3 preview/document cache methods exist only in `preview_table_presenter.py`.
- `assets_panel.py` only imports/subclasses `MaterialContextApplicationPresenterMixin`.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 40

### Current Assessment

`AssetsPanel` is now down to 16 direct methods:

- `_setup_ui`;
- `_on_scene_changed`;
- `resizeEvent`;
- `eventFilter`;
- `current_archive`;
- `material_context`;
- `current_question_figure_repair_audit_records`;
- `revert_question_figure_repair_audit_record`;
- `set_archive`;
- `save_archive_to_path`;
- `load_archive_from_path`;
- `load_mapping_from_path`;
- `load_batch_profiles_from_path`;
- `_selected_profile`;
- `_refresh_summary`;
- `_apply_theme`.

This is a healthier shape than the starting point, but not yet a fully finished structure. The remaining methods fall into four groups:

1. lifecycle/wiring: `_setup_ui`, `_on_scene_changed`, `resizeEvent`, `eventFilter`;
2. public archive/material API: `current_archive`, `material_context`, `set_archive`, save/load methods;
3. question-figure repair audit public API: current/revert repair audit methods;
4. final orchestration: `_selected_profile`, `_refresh_summary`, `_apply_theme`.

### Refined Next Step

The next low-risk extraction is the question-figure repair audit public API:

- `current_question_figure_repair_audit_records`;
- `revert_question_figure_repair_audit_record`.

Reason:

- it belongs with `QuestionFigureRepairActionsPresenterMixin`, which already owns repair application and rollback record creation;
- it is smaller and clearer than trying to split `_setup_ui` or `_refresh_summary`;
- it reduces the last direct question-figure behavior from `AssetsPanel`.

Defer these for now:

- `_setup_ui`: too large and UI-construction-heavy; split only after identifying stable section builders that are not already presenter-owned;
- `_refresh_summary`: still the main orchestrator across presenters;
- `_apply_theme`: global theme orchestration;
- public archive/material APIs: may eventually become `ArchiveStatePresenterMixin`, but they are also part of the panel's public contract and need a more careful compatibility review.

### Acceptance Gate For Next Pass

- Repair audit current/revert methods move out of `AssetsPanel`.
- `QuestionFigureRepairActionsPresenterMixin` owns all local repair apply/revert/audit behavior.
- Existing question-audit tests still pass.
- Full related assets regression still passes.

## 2026-07-07 Execution Record 41: Question-Figure Repair Audit Public API Extraction

This pass executed the next step from Record 40. It moved the last direct question-figure repair audit public API methods out of `AssetsPanel`.

### Decision

Move these methods into `QuestionFigureRepairActionsPresenterMixin`:

- `current_question_figure_repair_audit_records`;
- `revert_question_figure_repair_audit_record`.

Reason:

- `QuestionFigureRepairActionsPresenterMixin` already owns repair candidate application, local replacement, apply audit record creation, and rollback audit record creation;
- reverting an applied repair audit record is part of the same local repair lifecycle;
- keeping these methods on `AssetsPanel` made question-figure repair behavior look like a top-level panel concern even after repair actions had moved.

### Completed

- Updated `src/ui/panels/assets/question_figure_repair_actions_presenter.py`:
  - added `current_question_figure_repair_audit_records`;
  - added `revert_question_figure_repair_audit_record`.
- Updated `src/ui/panels/assets_panel.py`:
  - removed the two direct methods;
  - removed the now-unused direct `Mapping` import.
- Updated `tests/test_assets_panel_architecture.py`:
  - extended `QUESTION_FIGURE_REPAIR_ACTION_METHODS`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extended the runtime ownership test for `QuestionFigureRepairActionsPresenterMixin`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,799 lines, 16 functions/methods, 2 classes.
- `AssetsPanel`: 14 direct methods.
- `src/ui/panels/assets/question_figure_repair_actions_presenter.py`: 238 lines, 8 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 437 lines, 22 functions.
- `tests/test_assets_panel_helper_modules.py`: 465 lines, 22 functions.

Compared with Record 40:

- `assets_panel.py` dropped from 1,841 lines to 1,799 lines.
- `AssetsPanel` direct methods dropped from 16 to 14.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_figure_repair_actions_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_question_audit.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/question-audit/question-figure regression: `44 passed`.
- Full related assets regression: `85 passed`.

Residual scan:

```powershell
rg -n "current_question_figure_repair_audit_records|revert_question_figure_repair_audit_record|QuestionFigureRepairActionsPresenterMixin|def _record_question_figure_repair_rollback" src\ui\panels\assets_panel.py src\ui\panels\assets\question_figure_repair_actions_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- Repair audit current/revert methods exist only in `question_figure_repair_actions_presenter.py`.
- `assets_panel.py` only imports/subclasses `QuestionFigureRepairActionsPresenterMixin`.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 41

### Current Assessment

`AssetsPanel` is now down to 14 direct methods:

- `_setup_ui`;
- `_on_scene_changed`;
- `resizeEvent`;
- `eventFilter`;
- `current_archive`;
- `material_context`;
- `set_archive`;
- `save_archive_to_path`;
- `load_archive_from_path`;
- `load_mapping_from_path`;
- `load_batch_profiles_from_path`;
- `_selected_profile`;
- `_refresh_summary`;
- `_apply_theme`.

The remaining direct methods are no longer feature islands. They are panel shell/lifecycle, public state API, and final orchestration.

### Refined Next Step

Review these small ownership moves before touching `_setup_ui` or `_refresh_summary`:

1. Move `_selected_profile` to `ProfilePresenterMixin`.
   - It is profile state access, not panel orchestration.
   - Many presenters depend on it, so ownership should be explicit.
2. Move `resizeEvent` and `eventFilter` to `ResponsiveLayoutPresenterMixin`.
   - They are layout event handlers and already delegate to responsive/layout methods.
3. Consider moving `_on_scene_changed` to `SceneSpecPresenterMixin`.
   - It applies scene-derived required fields and asset/attachment specs.
   - It should be reviewed carefully because it is connected to external scene changes.

Defer:

- `current_archive`, `set_archive`, and archive load/save until a public `ArchiveStatePresenterMixin` boundary is designed;
- `material_context` and load mapping/batch profile APIs until public API compatibility is audited;
- `_refresh_summary` and `_apply_theme` because they remain final orchestration;
- `_setup_ui` until smaller lifecycle/event/state helpers are no longer interleaved with it.

### Acceptance Gate For Next Pass

- Each moved method lands in an existing presenter with a truthful ownership name.
- No generic presenter is introduced.
- `AssetsPanel` direct method count decreases without hiding orchestration.
- Focused and full related assets regressions pass.

## 2026-07-07 Execution Record 42: Profile Accessor and Responsive Event Extraction

This pass executed the first two recommendations from Record 41.

### Decision

Move `_selected_profile` into `ProfilePresenterMixin`.

Reason:

- it is profile state access;
- `ProfilePresenterMixin` already owns profile persistence, list reloading, selection, normalization, copy, and removal;
- many presenters depend on `_selected_profile`, so ownership should be explicit.

Move `resizeEvent` and `eventFilter` into `ResponsiveLayoutPresenterMixin`.

Reason:

- `resizeEvent` delegates to responsive layout recalculation;
- `eventFilter` handles drag/drop event dispatch for asset role rows and belongs with layout/event behavior rather than main panel orchestration;
- this avoids leaving Qt event plumbing as direct `AssetsPanel` feature logic.

### Completed

- Updated `src/ui/panels/assets/profile_presenter.py`:
  - added `_selected_profile`.
- Updated `src/ui/panels/assets/responsive_layout_presenter.py`:
  - added `resizeEvent`;
  - added `eventFilter`;
  - added the local `QEvent` import.
- Updated `src/ui/panels/assets_panel.py`:
  - removed the three direct methods;
  - removed now-unused direct `QEvent` import.
- Updated `tests/test_assets_panel_architecture.py`:
  - added `PROFILE_STATE_METHODS`;
  - added `RESPONSIVE_EVENT_METHODS`;
  - added architecture ownership tests for both groups.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extended profile presenter ownership test;
  - extended responsive layout presenter ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,777 lines, 13 functions/methods, 2 classes.
- `AssetsPanel`: 11 direct methods.
- `src/ui/panels/assets/profile_presenter.py`: 262 lines, 15 methods, 1 class.
- `src/ui/panels/assets/responsive_layout_presenter.py`: 92 lines, 5 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 472 lines, 24 functions.
- `tests/test_assets_panel_helper_modules.py`: 468 lines, 22 functions.

Compared with Record 41:

- `assets_panel.py` dropped from 1,799 lines to 1,777 lines.
- `AssetsPanel` direct methods dropped from 14 to 11.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\profile_presenter.py src\ui\panels\assets\responsive_layout_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `46 passed`.
- Full related assets regression: `87 passed`.

Residual scan:

```powershell
rg -n "def resizeEvent|def eventFilter|def _selected_profile|ProfilePresenterMixin|ResponsiveLayoutPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\profile_presenter.py src\ui\panels\assets\responsive_layout_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- `_selected_profile` exists only in `profile_presenter.py`.
- `resizeEvent` and `eventFilter` exist only in `responsive_layout_presenter.py`.
- `assets_panel.py` only imports/subclasses the owning presenters.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 42

### Current Assessment

`AssetsPanel` is now down to 11 direct methods:

- `_setup_ui`;
- `_on_scene_changed`;
- `current_archive`;
- `material_context`;
- `set_archive`;
- `save_archive_to_path`;
- `load_archive_from_path`;
- `load_mapping_from_path`;
- `load_batch_profiles_from_path`;
- `_refresh_summary`;
- `_apply_theme`.

The main panel is now mostly shell setup plus public state API plus final orchestration. That is close to a maintainable boundary, but there is still one direct scene-specific event handler.

### Refined Next Step

Review `_on_scene_changed` for possible movement into `SceneSpecPresenterMixin`.

Why it may fit:

- it reads scene-derived required fields, asset slot specs, and attachment role specs;
- it calls scene-spec helper methods already owned by `SceneSpecPresenterMixin`;
- it updates editor state only as a consequence of scene spec changes.

Why it needs review:

- it also coordinates profile persistence, theme refresh, summary refresh, and material batch sync;
- moving it could hide orchestration if the scene presenter becomes too broad.

Acceptance gate:

- move `_on_scene_changed` only if `SceneSpecPresenterMixin` remains clearly "scene spec application", not a generic orchestrator;
- focused and full related regressions must pass;
- if moved, add architecture/helper ownership tests.

## 2026-07-07 Execution Record 43: Scene Spec Application Extraction

This pass executed the reviewed scene-spec move from Record 42.

### Decision

Move `_on_scene_changed` into `SceneSpecPresenterMixin`.

Reason:

- the method is specifically about applying a changed scene's material requirements to required fields, asset slot specs, and attachment role specs;
- it depends directly on scene-spec helpers that already live in `SceneSpecPresenterMixin`;
- its calls to profile persistence, theme refresh, summary refresh, and batch sync are downstream effects of scene-spec changes, not unrelated orchestration.

### Completed

- Updated `src/ui/panels/assets/scene_spec_presenter.py`:
  - added `_on_scene_changed`;
  - imported `_format_required_fields_text` locally.
- Updated `src/ui/panels/assets_panel.py`:
  - removed the direct `_on_scene_changed` implementation.
- Updated `tests/test_assets_panel_architecture.py`:
  - imports `SceneSpecPresenterMixin`;
  - adds `SCENE_SPEC_APPLICATION_METHODS`;
  - proves `_on_scene_changed` is delegated to the scene-spec presenter.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends the scene-spec presenter ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,711 lines, 12 functions/methods, 2 classes.
- `AssetsPanel`: 10 direct methods.
- `src/ui/panels/assets/scene_spec_presenter.py`: 268 lines, 8 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 489 lines, 25 functions.
- `tests/test_assets_panel_helper_modules.py`: 469 lines, 22 functions.

Compared with Record 42:

- `assets_panel.py` dropped from 1,777 lines to 1,711 lines.
- `AssetsPanel` direct methods dropped from 11 to 10.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\scene_spec_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `47 passed`.
- Full related assets regression: `88 passed`.

Residual scan:

```powershell
rg -n "def _on_scene_changed|SceneSpecPresenterMixin|SCENE_SPEC_APPLICATION_METHODS" src\ui\panels\assets_panel.py src\ui\panels\assets\scene_spec_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- `_on_scene_changed` exists only in `scene_spec_presenter.py`.
- `assets_panel.py` only imports/subclasses `SceneSpecPresenterMixin`.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 43

### Current Assessment

`AssetsPanel` is now down to 10 direct methods:

- `_setup_ui`;
- `current_archive`;
- `material_context`;
- `set_archive`;
- `save_archive_to_path`;
- `load_archive_from_path`;
- `load_mapping_from_path`;
- `load_batch_profiles_from_path`;
- `_refresh_summary`;
- `_apply_theme`.

The remaining direct methods are now almost entirely public API plus setup/final orchestration.

### Refined Next Step

Review public API ownership carefully before moving more:

1. Archive state API may fit `ArchivePresenterMixin`:
   - `current_archive`;
   - `set_archive`;
   - `save_archive_to_path`;
   - `load_archive_from_path`.
2. Material import/context API may fit existing presenters:
   - `material_context` likely fits `MaterialContextApplicationPresenterMixin`;
   - `load_mapping_from_path` likely fits `MaterialContextApplicationPresenterMixin`;
   - `load_batch_profiles_from_path` needs review because it is batch-profile import, not batch output.
3. Keep `_setup_ui`, `_refresh_summary`, and `_apply_theme` direct for now.
   - they are still the panel shell and final orchestration points.

Acceptance gate:

- do not move public API merely to reduce method count;
- move only if the destination presenter already owns the same product responsibility;
- public API behavior must remain callable from `AssetsPanel`;
- focused and full related regressions must pass.

## 2026-07-07 Execution Record 44: Public Archive, Material, and Batch API Extraction

This pass executed the public API ownership review from Record 43.

### Decision

Move archive state API into `ArchivePresenterMixin`:

- `current_archive`;
- `set_archive`;
- `save_archive_to_path`;
- `load_archive_from_path`.

Move material context/mapping API into `MaterialContextApplicationPresenterMixin`:

- `material_context`;
- `load_mapping_from_path`.

Move batch profile import API into `BatchOutputPresenterMixin`:

- `load_batch_profiles_from_path`.

Reason:

- `ArchivePresenterMixin` already owns archive actions such as new, duplicate, rename, load dialog, and save dialog;
- `MaterialContextApplicationPresenterMixin` already owns applying profile/mapping/material context data to the editor;
- `BatchOutputPresenterMixin` already owns `_load_batch_profiles_dialog`, profile selection, and batch output state;
- keeping these public APIs callable through `AssetsPanel` via mixins preserves the external contract while making ownership explicit.

### Completed

- Updated `src/ui/panels/assets/archive_presenter.py`:
  - added current/set archive state API;
  - added archive save/load path API;
  - moved required archive serialization imports into the presenter.
- Updated `src/ui/panels/assets/material_context_application_presenter.py`:
  - added `material_context`;
  - added `load_mapping_from_path`;
  - moved mapping loading and replacement parsing imports into the presenter.
- Updated `src/ui/panels/assets/batch_output_presenter.py`:
  - added `load_batch_profiles_from_path`;
  - moved batch profile import normalization dependencies into the presenter.
- Updated `src/ui/panels/assets_panel.py`:
  - removed 7 public API method bodies;
  - removed now-unused direct imports for archive load/save, material context/mapping, batch material selection, batch profile import, and `Path`.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds archive state and batch profile import ownership tests;
  - extends material context ownership methods.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends archive presenter ownership test;
  - extends material context presenter ownership test;
  - extends batch output presenter ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,564 lines, 5 functions/methods, 2 classes.
- `AssetsPanel`: 3 direct methods.
- `src/ui/panels/assets/archive_presenter.py`: 237 lines, 15 methods, 1 class.
- `src/ui/panels/assets/material_context_application_presenter.py`: 202 lines, 8 methods, 1 class.
- `src/ui/panels/assets/batch_output_presenter.py`: 206 lines, 13 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 528 lines, 27 functions.
- `tests/test_assets_panel_helper_modules.py`: 476 lines, 22 functions.

Compared with Record 43:

- `assets_panel.py` dropped from 1,711 lines to 1,564 lines.
- `AssetsPanel` direct methods dropped from 10 to 3.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\archive_presenter.py src\ui\panels\assets\material_context_application_presenter.py src\ui\panels\assets\batch_output_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_material_execution_context.py::test_assets_panel_material_context_scans_images_from_rules tests\test_material_execution_context.py::test_assets_panel_loads_json_mapping_into_fields_and_replacements tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets plus targeted material public API regression: `51 passed`.
- Full related assets regression: `90 passed`.

Note:

- A broader combined run including the full `tests/test_material_execution_context.py` file was stopped because it ran far longer than the focused verification window while continuing to make slow progress. The directly affected material public API tests were then run explicitly and passed.

Residual scan:

```powershell
rg -n "def current_archive|def material_context|def set_archive|def save_archive_to_path|def load_archive_from_path|def load_mapping_from_path|def load_batch_profiles_from_path|ArchivePresenterMixin|MaterialContextApplicationPresenterMixin|BatchOutputPresenterMixin" src\ui\panels\assets_panel.py src\ui\panels\assets\archive_presenter.py src\ui\panels\assets\material_context_application_presenter.py src\ui\panels\assets\batch_output_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- Archive state API definitions exist only in `archive_presenter.py`.
- Material context/mapping API definitions exist only in `material_context_application_presenter.py`.
- Batch profile import API definition exists only in `batch_output_presenter.py`.
- `assets_panel.py` only imports/subclasses those presenters.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 44

### Current Assessment

`AssetsPanel` is now down to 3 direct methods:

- `_setup_ui`;
- `_refresh_summary`;
- `_apply_theme`.

This is the first point where the main panel is genuinely acting as a shell:

- setup still constructs the panel surface;
- summary still orchestrates state from many presenters into top-level labels/cards;
- theme still coordinates global visual refresh.

The enterprise remote execution cleanup remains intact:

- no active remote writeback;
- no enterprise auth/signed URL/external permission execution;
- no master registry/subscription drift/non-question remote governance in `src`;
- negative guard tests still cover those tokens.

### Refined Next Step

Do not move `_refresh_summary` or `_apply_theme` just to reach zero direct helper methods. They are still legitimate final orchestration points.

The only remaining large structural issue is `_setup_ui`.

Recommended next stage:

1. Inspect `_setup_ui` by section rather than extracting it wholesale.
2. Extract only stable UI construction groups with honest names, such as:
   - archive/profile header construction;
   - field editor section construction;
   - asset inventory section construction;
   - question figure section construction;
   - preview/generation section construction.
3. Keep each extracted builder in a presenter that already owns the corresponding behavior where possible.
4. Do not introduce a generic `UiBuilderMixin` unless the extracted code is purely shell layout and cannot be owned by a product presenter.

Acceptance gate for setup-stage work:

- the first screen and section navigation still build successfully;
- `PANEL_SPECS` / panel registry tests pass;
- helper ownership tests do not become meaningless "everything moved to UI builder" checks;
- full related assets regression passes;
- visual or runtime verification should be considered if UI construction is split deeply.

### Stop Condition

If splitting `_setup_ui` starts duplicating widget ownership or hiding product boundaries, stop. At this stage, a 3-method `AssetsPanel` with a large setup method is healthier than a zero-method shell that hides all UI construction in a vague builder.

## 2026-07-07 Execution Record 45: Archive Overview Card Setup Extraction

This pass started the setup-stage work recommended after Record 44. It extracted one stable UI construction section from `_setup_ui`.

### Decision

Move archive overview card construction into `ArchivePresenterMixin` as `_setup_archive_overview_card`.

Reason:

- the block creates the archive combo, hidden archive id/name fields, and archive action row;
- all callbacks already belong to `ArchivePresenterMixin`;
- the extracted method has an honest ownership name and does not introduce a generic UI builder;
- this is a low-risk first setup extraction because it does not touch question-figure tables, preview tables, or summary/theme orchestration.

### Completed

- Updated `src/ui/panels/assets/archive_presenter.py`:
  - added `_setup_archive_overview_card`;
  - moved `Card`, `QLineEdit`, `LibraryActionRow`, and `StyledComboBox` imports into the archive presenter.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the archive card block with `self._setup_archive_overview_card()`;
  - removed now-unused direct `LibraryActionRow` and `StyledComboBox` imports.
- Updated `tests/test_assets_panel_architecture.py`:
  - added `ARCHIVE_SETUP_METHODS`;
  - proves archive overview card setup is owned by `ArchivePresenterMixin`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends archive presenter runtime ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,502 lines, 5 functions/methods, 2 classes.
- `AssetsPanel`: 3 direct methods.
- `src/ui/panels/assets/archive_presenter.py`: 303 lines, 16 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 544 lines, 28 functions.
- `tests/test_assets_panel_helper_modules.py`: 477 lines, 22 functions.

Compared with Record 44:

- `assets_panel.py` dropped from 1,564 lines to 1,502 lines.
- `AssetsPanel` direct method count stayed at 3, as expected, because this pass reduces setup body size rather than moving a direct method.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\archive_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `50 passed`.
- Full related assets regression: `91 passed`.

Residual scan:

```powershell
rg -n "_setup_archive_overview_card|LibraryActionRow|StyledComboBox|assets_overview_archive" src\ui\panels\assets_panel.py src\ui\panels\assets\archive_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- `_setup_archive_overview_card`, `LibraryActionRow`, and `StyledComboBox` for archive overview now live in `archive_presenter.py`.
- `assets_panel.py` calls the setup method but no longer owns the archive overview construction block.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 45

### Current Assessment

Setup-stage extraction is viable when the extracted block maps to an existing presenter responsibility. The archive overview card was a good first cut because it:

- has a clear product boundary;
- already had all behavior callbacks in `ArchivePresenterMixin`;
- reduced `_setup_ui` without increasing cross-presenter coupling.

`AssetsPanel` remains a 3-method shell:

- `_setup_ui`;
- `_refresh_summary`;
- `_apply_theme`.

The remaining `_setup_ui` body still contains several product-specific construction blocks:

- generation actions card;
- import/export card;
- profile/field editor card;
- image inventory and question-figure tables;
- preview placeholder table;
- batch profile list/output controls;
- advanced rules card.

### Refined Next Step

Continue setup extraction only section-by-section.

Recommended next candidates:

1. Preview placeholder card into `PreviewTablePresenterMixin`.
   - It owns preview filtering, placeholder scanning, preview rows, and row actions.
   - The card block creates `_preview_label`, `_preview_filter_btn`, `_preview_auto_match_btn`, and `_preview_table`.
   - This is likely the next cleanest ownership match.
2. Batch profile list/output card into `BatchOutputPresenterMixin`.
   - It owns profile selection, batch preview, output naming, and `_load_batch_profiles_dialog`.
   - It may depend on profile presenter callbacks, so review before moving.
3. Profile/field editor card needs more caution.
   - It spans profile identity, structured fields, field status, unknown field suggestions, and free-form fields.
   - It may need to be split between `ProfilePresenterMixin`, `FieldEditorStatePresenterMixin`, and `FieldStatusPresenterMixin`.

Defer:

- image inventory/question-figure block until smaller setup blocks are extracted;
- `_refresh_summary` and `_apply_theme`;
- a generic UI builder.

Acceptance gate for the next setup pass:

- first-screen panel registry construction passes;
- no loss of widget object names or callbacks;
- ownership test proves the setup block lives in the matching presenter;
- full related assets regression passes.

## 2026-07-07 Execution Record 46: Placeholder Preview Card Setup Extraction

This pass continued setup-stage extraction by moving the preview placeholder card construction into the presenter that owns preview behavior.

### Decision

Move placeholder preview card construction into `PreviewTablePresenterMixin` as `_setup_placeholder_preview_card`.

Reason:

- `PreviewTablePresenterMixin` already owns preview filtering, auto-match cache reset, document-loaded cache reset, placeholder scanning, preview rows, row actions, and preview table refresh;
- the extracted block creates `_preview_label`, `_preview_auto_match_btn`, `_preview_filter_btn`, and `_preview_table`;
- the object name `asset_placeholder_preview_table`, button callbacks, column headers, and header resize modes remain unchanged;
- this avoids a generic UI builder and keeps construction near the behavior it supports.

### Completed

- Updated `src/ui/panels/assets/preview_table_presenter.py`:
  - added `_setup_placeholder_preview_card`;
  - moved preview card widget imports into the presenter.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the preview card block with `self._setup_placeholder_preview_card()`.
- Updated `tests/test_assets_panel_architecture.py`:
  - added `_setup_placeholder_preview_card` to `PREVIEW_STATE_METHODS`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends the preview presenter runtime ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,464 lines, 5 functions/methods, 2 classes.
- `AssetsPanel`: 3 direct methods.
- `src/ui/panels/assets/preview_table_presenter.py`: 560 lines, 14 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 545 lines, 28 functions.
- `tests/test_assets_panel_helper_modules.py`: 478 lines, 22 functions.

Compared with Record 45:

- `assets_panel.py` dropped from 1,502 lines to 1,464 lines.
- `AssetsPanel` direct method count stayed at 3.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\preview_table_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `50 passed`.
- Full related assets regression: `91 passed`.

Residual scan:

```powershell
rg -n "_setup_placeholder_preview_card|asset_placeholder_preview_table|_preview_auto_match_btn|_preview_filter_btn" src\ui\panels\assets_panel.py src\ui\panels\assets\preview_table_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- `_setup_placeholder_preview_card` and `asset_placeholder_preview_table` construction live in `preview_table_presenter.py`.
- `assets_panel.py` only calls the setup method and still styles preview buttons in `_apply_theme`.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 46

### Current Assessment

The setup-stage extraction is still healthy:

- archive overview card moved to archive ownership;
- placeholder preview card moved to preview ownership;
- `AssetsPanel` remains a 3-method shell;
- no generic UI builder has been introduced;
- full related assets regression remains green.

Remaining `_setup_ui` blocks include:

- generation actions card;
- import/export card;
- profile/field editor card;
- image inventory and question-figure table block;
- batch profile list/output controls;
- advanced rules card.

### Refined Next Step

The next likely setup extraction candidate is the batch profile list/output card into `BatchOutputPresenterMixin`.

Why it may fit:

- it creates `_profile_list`, add/copy/import/remove profile buttons, `_batch_output_naming_combo`, and `_batch_preview`;
- `BatchOutputPresenterMixin` already owns profile selection, batch output preview, output naming state, batch profile import dialog, and material batch selection sync.

Why it needs a careful pass:

- the card also calls profile presenter callbacks such as `_on_profile_row_changed`, `_add_profile`, `_copy_current_profile`, and `_remove_current_profile`;
- this cross-presenter dependency is acceptable only if the setup method is clearly about batch profile list/output surface, not profile state behavior.

Alternative:

- extract the advanced rules card into a material/settings presenter only if a good existing owner is identified;
- avoid profile/field editor and image/question-figure block until smaller setup chunks are done.

## 2026-07-07 Execution Record 47: Batch Profile Output Card Setup Extraction

This pass continued setup-stage extraction by moving the batch profile/output card construction into `BatchOutputPresenterMixin`.

### Decision

Move batch profile list/output card construction into `BatchOutputPresenterMixin` as `_setup_batch_profile_output_card`.

Reason:

- `BatchOutputPresenterMixin` already owns batch profile selection, selected profile ids, batch output preview, output naming, batch profile import dialog, and material batch selection sync;
- the extracted block creates `_profile_list`, add/copy/import/remove profile buttons, `_batch_output_naming_combo`, and `_batch_preview`;
- although the buttons call profile presenter methods, the surface itself is the batch output control area, so ownership remains honest;
- this avoids mixing batch output UI construction into the shell `_setup_ui`.

### Completed

- Updated `src/ui/panels/assets/batch_output_presenter.py`:
  - added `_setup_batch_profile_output_card`;
  - moved `Card`, `InspectorForm`, `QListWidget`, `QComboBox`, action-button, and layout imports into the presenter.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the batch card block with `self._setup_batch_profile_output_card()`;
  - removed now-unused direct imports of `BATCH_OUTPUT_CUSTOM_TEMPLATE`, `BATCH_OUTPUT_NAMING_OPTIONS`, `QListWidget`, and `QListWidgetItem`.
- Updated `tests/test_assets_panel_architecture.py`:
  - extends `BATCH_PROFILE_IMPORT_METHODS` with `_setup_batch_profile_output_card`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends the batch output presenter runtime ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,422 lines, 5 functions/methods, 2 classes.
- `AssetsPanel`: 3 direct methods.
- `src/ui/panels/assets/batch_output_presenter.py`: 260 lines, 14 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 546 lines, 28 functions.
- `tests/test_assets_panel_helper_modules.py`: 479 lines, 22 functions.

Compared with Record 46:

- `assets_panel.py` dropped from 1,464 lines to 1,422 lines.
- `AssetsPanel` direct method count stayed at 3.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\batch_output_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `50 passed`.
- Full related assets regression: `91 passed`.

Residual scan:

```powershell
rg -n "_setup_batch_profile_output_card|assets_profile_list|BATCH_OUTPUT_NAMING_OPTIONS|QListWidget|_batch_output_naming_combo" src\ui\panels\assets_panel.py src\ui\panels\assets\batch_output_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- `_setup_batch_profile_output_card`, `assets_profile_list`, and output naming combo construction live in `batch_output_presenter.py`.
- `assets_panel.py` only calls the setup method and keeps styling the resulting controls in `_apply_theme`.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 47

### Current Assessment

Setup extraction remains aligned with product ownership:

- archive overview card -> `ArchivePresenterMixin`;
- placeholder preview card -> `PreviewTablePresenterMixin`;
- batch profile/output card -> `BatchOutputPresenterMixin`.

`AssetsPanel` remains a 3-method shell, and `_setup_ui` is now materially smaller.

Remaining `_setup_ui` blocks:

- generation actions card;
- import/export card;
- profile/field editor card;
- image inventory and question-figure table block;
- advanced rules card.

### Refined Next Step

The next safest candidate is probably the import/export card into `ArchivePresenterMixin`.

Reason:

- it creates import/export actions and wires `_load_archive_dialog`, `_save_archive_dialog`, and `_load_batch_profiles_dialog`;
- it is an I/O surface rather than core profile/field editing;
- `ArchivePresenterMixin` already owns archive load/save dialog behavior.

Caution:

- the card also includes batch profile import, so name it as an import/export surface, not only archive import/export;
- if this feels too cross-boundary, defer it and inspect the advanced rules card instead.

Still defer:

- profile/field editor card: crosses profile identity, field editor state, field status, and unknown-field suggestions;
- image inventory/question-figure block: large and contains multiple presenters;
- `_refresh_summary` and `_apply_theme`.

## 2026-07-07 Execution Record 48: Import/Export Card Setup Extraction

This pass continued setup-stage extraction by moving the import/export surface into `ArchivePresenterMixin`.

### Decision

Move import/export card construction into `ArchivePresenterMixin` as `_setup_import_export_card`.

Reason:

- the card is an I/O surface for importing a mapping, importing multiple profiles, loading an archive, and saving an archive;
- `ArchivePresenterMixin` already owns archive load/save dialogs;
- keeping this as an import/export surface is more honest than calling it purely archive setup, because it also wires mapping and batch import actions;
- the extraction reduces shell setup without hiding the behavior callbacks.

### Completed

- Updated `src/ui/panels/assets/archive_presenter.py`:
  - added `_setup_import_export_card`;
  - moved required card, label, button, and layout imports into the presenter.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the import/export card block with `self._setup_import_export_card()`.
- Updated `tests/test_assets_panel_architecture.py`:
  - extends `ARCHIVE_SETUP_METHODS` with `_setup_import_export_card`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends archive presenter runtime ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,398 lines, 5 functions/methods, 2 classes.
- `AssetsPanel`: 3 direct methods.
- `src/ui/panels/assets/archive_presenter.py`: 342 lines, 17 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 547 lines, 28 functions.
- `tests/test_assets_panel_helper_modules.py`: 480 lines, 22 functions.

Compared with Record 47:

- `assets_panel.py` dropped from 1,422 lines to 1,398 lines.
- `AssetsPanel` direct method count stayed at 3.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\archive_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `50 passed`.
- Full related assets regression: `91 passed`.

Residual scan:

```powershell
rg -n "_setup_import_export_card|_import_export_card|_load_mapping_btn|_import_batch_from_io_btn|_load_btn|_save_btn" src\ui\panels\assets_panel.py src\ui\panels\assets\archive_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- `_setup_import_export_card` and the import/export button construction live in `archive_presenter.py`.
- `assets_panel.py` only calls the setup method and keeps styling the resulting controls in `_apply_theme`.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 48

### Current Assessment

The setup-stage extractions so far have stayed within honest presenter ownership:

- archive overview and import/export surfaces -> `ArchivePresenterMixin`;
- placeholder preview card -> `PreviewTablePresenterMixin`;
- batch profile/output card -> `BatchOutputPresenterMixin`.

`AssetsPanel` is now 1,398 lines and remains a 3-method shell.

Remaining `_setup_ui` blocks:

- generation actions card;
- profile/field editor card;
- image inventory and question-figure table block;
- advanced rules card.

### Refined Next Step

Do not rush the image inventory/question-figure block. It is large and spans many presenters:

- asset slots;
- attachment roles;
- question figure items;
- library metadata;
- metadata issues;
- version history;
- master version;
- shared cache;
- image preview.

The next safer candidate is the generation actions card.

Why it may fit:

- it creates generation status labels and action buttons;
- callbacks already route to material repair navigation, material context application, and batch output;
- it is a small block and can be named as `_setup_generation_actions_card`.

Potential destination:

- `MaterialContextApplicationPresenterMixin`, if treated as the user-facing generation entry surface;
- otherwise defer until a clearer generation presenter exists.

Alternative:

- advanced rules card might fit `MaterialContextApplicationPresenterMixin` if treated as material application settings, but it also contains required-fields and batch output template controls.

Stop condition:

- if neither generation nor advanced card has a truthful owner, pause setup extraction and leave the remaining shell structure as-is.

## 2026-07-07 Execution Record 49: Generation Actions Card Setup Extraction

This pass continued setup-stage extraction by moving the generation entry card into `MaterialContextApplicationPresenterMixin`.

### Decision

Move generation actions card construction into `MaterialContextApplicationPresenterMixin` as `_setup_generation_actions_card`.

Reason:

- the card is the user-facing generation entry surface;
- it creates generation status/detail labels and the three main generation actions: fill missing content, generate document, and batch generate;
- the callbacks are already owned by material repair navigation, material context application, and batch output presenters;
- placing the construction next to material context application is the least misleading existing ownership boundary because the central action is applying the current material context to generation.

### Completed

- Updated `src/ui/panels/assets/material_context_application_presenter.py`:
  - added `_setup_generation_actions_card`;
  - moved card, label, button, and layout imports into the presenter.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the generation card block with `self._setup_generation_actions_card()`.
- Updated `tests/test_assets_panel_architecture.py`:
  - extends `MATERIAL_CONTEXT_APPLICATION_METHODS` with `_setup_generation_actions_card`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends material context presenter runtime ownership test.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,368 lines, 5 functions/methods, 2 classes.
- `AssetsPanel`: 3 direct methods.
- `src/ui/panels/assets/material_context_application_presenter.py`: 236 lines, 9 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 548 lines, 28 functions.
- `tests/test_assets_panel_helper_modules.py`: 481 lines, 22 functions.

Compared with Record 48:

- `assets_panel.py` dropped from 1,398 lines to 1,368 lines.
- `AssetsPanel` direct method count stayed at 3.

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\material_context_application_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `50 passed`.
- Full related assets regression: `91 passed`.

Residual scan:

```powershell
rg -n "_setup_generation_actions_card|_generate_card|_generation_status_label|_fill_missing_btn|_apply_btn|_batch_generate_btn" src\ui\panels\assets_panel.py src\ui\panels\assets\material_context_application_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py
```

Result:

- `_setup_generation_actions_card` and generation action construction live in `material_context_application_presenter.py`.
- `assets_panel.py` only calls the setup method and keeps summary/theme orchestration.
- Active enterprise remote execution tokens remain absent from `src`; remaining hits are negative guard tests.

## 2026-07-07 Plan Review After Record 49

### Current Assessment

The clean setup extractions are now complete for small, obvious card surfaces:

- archive overview;
- import/export;
- generation actions;
- placeholder preview;
- batch profile/output.

`AssetsPanel` remains a 3-method shell and is down to 1,368 lines.

Remaining `_setup_ui` sections are much less trivial:

- profile/field editor card;
- image inventory and question-figure table block;
- advanced rules card;
- initial state registry/setup variables;
- shell/return bar/detail stack setup;
- final section registration and theme binding.

### Refined Next Step

Pause broad setup extraction and perform a focused boundary review before moving more.

Potential paths:

1. Profile/field editor card:
   - likely needs multiple smaller setup helpers;
   - possible owners: `ProfilePresenterMixin`, `FieldEditorStatePresenterMixin`, `FieldStatusPresenterMixin`;
   - risk: splitting one visual card across three presenters may make construction harder to follow.
2. Advanced rules card:
   - contains replacement rules, image rules, required fields, and batch output template;
   - possible owners: material context application plus batch output, but no single owner is perfect.
3. Image inventory/question-figure block:
   - defer for now;
   - too many presenters and tables live in one visual card.

Recommendation:

- Do not continue extracting setup blocks unless a clear owner exists.
- Next useful work may be a setup-boundary map in the MD rather than immediate code movement.
- If more code movement is desired, start with advanced rules only after deciding whether it should become a small `MaterialSettingsPresenterMixin` or be split between existing presenters.

## 2026-07-07 Execution Record 50: Enterprise Remote Re-audit And Setup Boundary Map

This pass revisits the user's correction: do not rush into control unification; keep the focus on code simplification and removal of non-essential enterprise remote capability.

### Current Source Re-audit

The enterprise remote deletion line has already crossed the important source boundary:

- `src/ui/panels/assets_panel.py`: 1,368 lines, 5 functions/methods, 2 classes.
- `AssetsPanel`: 3 direct methods.
- `src/services/material_assets/question_library.py`: 1,600 lines, 41 functions, 0 classes.
- AST scan found `0` enterprise-named functions in both `assets_panel.py` and `question_library.py`.
- Source scan for `remote_writeback`, `enterprise_auth`, `signed_url`, `external_permission`, `master_registry`, `registry_sync`, `subscription_lock`, `subscription_change`, `subscription_drift`, and `non_question_asset_family` under `src/ui/panels` and `src/services/material_assets` found no active implementation hits.
- Remaining hits are boundary tests that assert deleted enterprise capabilities do not return.

This changes the next-step interpretation:

- The next step is no longer "delete enterprise remote from source"; the active source path is already clean.
- The next step is to preserve this deletion with boundary tests and continue simplifying the remaining local asset panel structure.
- Control unification remains deferred. It should only apply to retained local product logic, not to enterprise remote flows that have already been removed.

### Remaining `_setup_ui` Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| `_setup_ui` start and state registry | 426-501 | still in shell | Keep for now; this is panel composition state, not a clear presenter responsibility. |
| shell, return bar, detail stack, section pages | 502-548 | still in shell | Keep in shell; it defines the master-detail container. |
| extracted card setup calls | 549-553, 935-937 | already delegated | Keep; ownership is now clearer. |
| profile and field editor card | 555-606 | still in shell | Candidate only after deciding whether one owner can build the whole card. |
| image inventory and question-figure table card | 607-934 | still in shell | Defer; this is the largest remaining UI island and crosses several presenters. |
| advanced rules card | 939-989 | still in shell | Best next candidate if a `MaterialSettingsPresenterMixin` is introduced. |
| final layout registration and theme binding | 990-998 | still in shell | Keep in shell; it wires sections and panel lifecycle. |
| `_refresh_summary` | 1004 onward | still in shell | Keep until summary ownership is redesigned separately. |

### Revised Plan Review

The plan should now be optimized around three principles:

1. Preserve the enterprise deletion boundary.
   - Keep tests that prove deleted remote writeback, enterprise auth, signed URL refresh, registry sync, subscription lock/change/drift, and non-question remote governance are absent.
   - Do not create new presenter or service modules for deleted enterprise concepts.
   - Treat any new `remote_writeback` or `subscription_drift` symbol in `src` as a regression unless it is explicitly behind a new product decision.

2. Continue code simplification only where ownership is truthful.
   - Small setup blocks with clear owners have already moved out.
   - Remaining blocks should not be mechanically extracted just to reduce line count.
   - The next safe extraction is the advanced rules card only if it becomes a retained local material settings surface.

3. Separate "local asset management" from "panel shell".
   - The shell may own navigation, section registration, lifecycle binding, and summary refresh.
   - Presenters should own coherent product surfaces: archive, preview, batch output, material context, field editing, question figures, cache, and local audit.
   - If a block crosses three or more product surfaces, write a boundary note before moving code.

### Optimized Next Execution Order

1. Add or keep regression guards that scan `src` for deleted enterprise remote tokens.
2. Review remaining `_setup_ui` blocks against the boundary map before any further extraction.
3. If continuing with code movement, create a narrow `MaterialSettingsPresenterMixin` for the advanced rules card only.
4. Run focused architecture/helper/spec/question-figure tests after each extraction.
5. Run the full related assets regression before declaring the current simplification phase complete.

### Stop Conditions

Pause code movement if:

- a block's owner would need to be invented only for line-count reduction;
- an extraction would split one visual card across unrelated presenters;
- a retained local workflow starts depending on deleted enterprise remote terminology;
- tests need to be weakened instead of changed to assert the new product boundary.

### Current Recommendation

The current architecture is healthier than at the start of this phase:

- enterprise remote implementation is absent from active source;
- `AssetsPanel` has become a smaller 3-method shell;
- setup construction for several coherent cards has moved to presenters;
- boundary tests now guard against enterprise remote capability returning.

The next best improvement is not broad control unification. It is a focused local-only simplification pass: either document and leave the remaining shell-owned setup alone, or extract only the advanced rules card into a truthful material settings presenter.

## 2026-07-07 Execution Record 51: Material Settings Card Setup Extraction

This pass executed the narrow code movement recommended after Record 50: extract only the retained local advanced rules card, without reviving enterprise remote concepts or starting broad control unification.

### Decision

Move advanced rules card construction into a new `MaterialSettingsPresenterMixin` as `_setup_material_settings_card`.

Reason:

- the card is a coherent local settings surface;
- it owns replacement rules, image insertion rules, required field text, and the batch output custom template field;
- it does not require remote writeback, enterprise auth, signed URL refresh, registry sync, subscription drift, or non-question remote governance;
- keeping it separate from generation actions avoids overloading `MaterialContextApplicationPresenterMixin`.

### Completed

- Added `src/ui/panels/assets/material_settings_presenter.py`:
  - defines `MaterialSettingsPresenterMixin`;
  - owns `_setup_material_settings_card`;
  - keeps the existing card widget fields and signal wiring intact.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and mixes in `MaterialSettingsPresenterMixin`;
  - replaces the inline advanced card block with `self._setup_material_settings_card()`;
  - removes the no-longer-needed `_format_required_fields_text` import from the shell.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds architecture ownership coverage for `MaterialSettingsPresenterMixin`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_material_settings_card`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,319 lines, 5 functions/methods, 2 classes.
- `AssetsPanel`: 3 direct methods.
- `src/ui/panels/assets/material_settings_presenter.py`: 78 lines, 1 method, 1 class.
- `tests/test_assets_panel_architecture.py`: 565 lines, 29 functions.
- `tests/test_assets_panel_helper_modules.py`: 496 lines, 23 functions.

Compared with Record 50:

- `assets_panel.py` dropped from 1,368 lines to 1,319 lines.
- `AssetsPanel` direct method count stayed at 3.
- Focused architecture/helper/spec/question-figure tests increased from `50 passed` to `52 passed` because of the new material settings ownership guards.
- Full related assets regression increased from `91 passed` to `93 passed` because of the new ownership guards.

### Updated `_setup_ui` Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| `_setup_ui` start and state registry | 427-502 | still in shell | Keep for now; this is panel composition state. |
| shell, return bar, detail stack, section pages | 503-549 | still in shell | Keep in shell; it defines master-detail composition. |
| archive/generation/import setup calls | 550-554 | delegated | Keep. |
| profile and field editor card | 556-607 | still in shell | Candidate only if a whole-card owner is selected. |
| image inventory and question-figure table card | 608-935 | still in shell | Defer; this remains the largest cross-presenter island. |
| preview, batch output, material settings setup calls | 936-940 | delegated | Keep. |
| final layout registration and theme binding | 941-949 | still in shell | Keep in shell; this wires panel lifecycle. |
| `_refresh_summary` | 955 onward | still in shell | Keep until summary ownership is redesigned separately. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\material_settings_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `52 passed`.
- Full related assets regression: `93 passed`.

Residual enterprise scan:

```powershell
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py
```

Result:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests that assert deleted remote/enterprise abilities stay absent.

### Plan Review After Record 51

The advanced rules card extraction was the last obvious small setup extraction with a truthful local owner.

Do not continue by mechanically moving the image inventory/question-figure block. It is still a large visual card that crosses:

- asset slot rows;
- attachment role rows;
- image preview;
- question figure inventory;
- library metadata;
- issue rows;
- version history;
- master version;
- shared cache.

The next healthy path is:

1. keep enterprise deletion guards intact;
2. leave shell-owned navigation/lifecycle code in `AssetsPanel`;
3. either stop setup extraction here and move to summary-service cleanup, or design a dedicated whole-card owner before touching the profile/field editor card;
4. defer image inventory/question-figure UI movement until its sub-surfaces are split by product ownership, not by line count.

## 2026-07-07 Execution Record 52: Summary Refresh Ownership Extraction

This pass followed the Record 51 recommendation to stop broad setup extraction and move to summary cleanup. The change moves the whole `_refresh_summary` orchestration into `SectionSummaryPresenterMixin`.

### Decision

Move `_refresh_summary` from `AssetsPanel` into `SectionSummaryPresenterMixin`.

Reason:

- `_refresh_summary` is not panel shell construction;
- it calculates section summary state, generation status, preview rows, batch preview text, question-figure projections, section navigation badges, and summary-card grid rows;
- `SectionSummaryPresenterMixin` already owns `_refresh_section_cards` and `_refresh_section_summary_cards`;
- moving the whole method keeps behavior stable and avoids slicing one summary flow across multiple presenters.

### Completed

- Updated `src/ui/panels/assets/section_summary_presenter.py`:
  - moved `_refresh_summary` into the presenter;
  - imported `_missing_placeholder_label` next to the existing `_field_label` helper.
- Updated `src/ui/panels/assets_panel.py`:
  - removed the direct `_refresh_summary` method from `AssetsPanel`;
  - removed no-longer-needed `_field_label` and `_missing_placeholder_label` imports;
  - kept all existing `_refresh_summary()` call sites unchanged through MRO.
- Updated `tests/test_assets_panel_architecture.py`:
  - added `SectionSummaryPresenterMixin` architecture ownership coverage for `_refresh_summary`;
  - moved the question-figure projection call assertion from `AssetsPanel._refresh_summary` to `SectionSummaryPresenterMixin._refresh_summary`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - extends runtime MRO ownership coverage so `_refresh_summary` must come from `SectionSummaryPresenterMixin`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 1,196 lines, 4 functions/methods, 2 classes.
- `AssetsPanel`: 2 direct methods: `_setup_ui`, `_apply_theme`.
- `src/ui/panels/assets/section_summary_presenter.py`: 482 lines, 5 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 584 lines, 30 functions.
- `tests/test_assets_panel_helper_modules.py`: 497 lines, 23 functions.

Compared with Record 51:

- `assets_panel.py` dropped from 1,319 lines to 1,196 lines.
- `AssetsPanel` direct method count dropped from 3 to 2.
- Focused architecture/helper/spec/question-figure tests increased from `52 passed` to `53 passed`.
- Full related assets regression increased from `93 passed` to `94 passed`.

### Updated `_setup_ui` Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| `_setup_ui` start and state registry | 425-500 | still in shell | Keep for now; this is panel composition state. |
| shell, return bar, detail stack, section pages | 501-547 | still in shell | Keep in shell. |
| archive/generation/import setup calls | 548-552 | delegated | Keep. |
| profile and field editor card | 554-605 | still in shell | Candidate only after designing a whole-card owner. |
| image inventory and question-figure table card | 606-933 | still in shell | Defer; too many product surfaces still share one visual island. |
| preview, batch output, material settings setup calls | 934-938 | delegated | Keep. |
| final layout registration and theme binding | 939-947 | still in shell | Keep in shell. |
| `_apply_theme` | 954 onward | still in shell | Next possible cleanup target, but only if split by stable theme surfaces. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\section_summary_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `53 passed`.
- Full related assets regression: `94 passed`.

Residual enterprise scan:

```powershell
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py
```

Result:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 52

`AssetsPanel` is now close to a real shell: direct responsibilities are setup composition and theme application.

Do not immediately move the image inventory/question-figure setup block. The next safer choices are:

1. Design a whole-card owner for the profile/field editor card before moving it.
2. Split `_apply_theme` by already-existing presenter-owned surfaces, but only if each extracted helper has a stable owner.
3. Leave `_setup_ui` and `_apply_theme` in the shell if further movement would make ownership less clear.

Current recommendation:

- Treat setup extraction as effectively paused.
- If continuing code simplification, audit `_apply_theme` for small owner-aligned theme helpers.
- Keep enterprise deletion guards as non-negotiable acceptance criteria for every future pass.

## 2026-07-07 Execution Record 53: Theme Application Ownership Extraction

This pass audited `_apply_theme` after Record 52 and moved the whole theme application concern into a dedicated `ThemePresenterMixin`.

### Decision

Move `_apply_theme` from `AssetsPanel` into `ThemePresenterMixin`.

Reason:

- `_apply_theme` is a styling concern, not product shell composition;
- splitting it by individual widgets would produce many small ownerless helpers;
- a dedicated theme presenter gives the method a truthful technical owner while preserving behavior;
- this leaves `AssetsPanel` as a near-pure setup shell.

### Completed

- Added `src/ui/panels/assets/theme_presenter.py`:
  - defines `ThemePresenterMixin`;
  - owns `_apply_theme`;
  - carries theme-only imports such as `get_theme`, `apply_size_class`, `build_text_input_stylesheet`, `build_button_stylesheet`, and `QSize`.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and mixes in `ThemePresenterMixin`;
  - removes the direct `_apply_theme` method;
  - removes theme-only imports that are no longer shell concerns.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds `ThemePresenterMixin` architecture ownership coverage.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_apply_theme`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 952 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/theme_presenter.py`: 260 lines, 1 method, 1 class.
- `src/ui/panels/assets/section_summary_presenter.py`: 482 lines, 5 methods, 1 class.
- `src/ui/panels/assets/material_settings_presenter.py`: 78 lines, 1 method, 1 class.
- `tests/test_assets_panel_architecture.py`: 601 lines, 31 functions.
- `tests/test_assets_panel_helper_modules.py`: 512 lines, 24 functions.

Compared with Record 52:

- `assets_panel.py` dropped from 1,196 lines to 952 lines.
- `AssetsPanel` direct method count dropped from 2 to 1.
- Focused architecture/helper/spec/question-figure tests increased from `53 passed` to `55 passed`.
- Full related assets regression increased from `94 passed` to `96 passed`.

### Updated `_setup_ui` Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| `_setup_ui` start and state registry | 424-499 | still in shell | Keep for now. |
| shell, return bar, detail stack, section pages | 500-546 | still in shell | Keep in shell. |
| archive/generation/import setup calls | 547-551 | delegated | Keep. |
| profile and field editor card | 553-604 | still in shell | Next possible setup extraction only if a whole-card owner is created. |
| image inventory and question-figure table card | 605-932 | still in shell | Defer; largest remaining cross-product island. |
| preview, batch output, material settings setup calls | 933-937 | delegated | Keep. |
| final layout registration and theme binding | 938-946 | still in shell | Keep in shell. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\theme_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `55 passed`.
- Full related assets regression: `96 passed`.

Residual enterprise scan:

```powershell
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py
```

Result:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 53

`AssetsPanel` now has one direct method: `_setup_ui`. The shell is substantially healthier.

The remaining work is no longer about obvious helper extraction. It is about whether the last large setup islands should become real product-owned card builders:

1. Profile and field editor card:
   - feasible next extraction if a new whole-card owner is named, such as `ProfileEditorPresenterMixin`;
   - should not be split between profile, field status, and field editor state presenters.
2. Image inventory and question-figure table card:
   - still too broad for a safe single movement;
   - should be decomposed only after defining a product boundary for image inventory versus question-figure library/cache tables.

Current recommendation:

- If continuing code movement, extract the profile and field editor card as one whole card into a new profile editor setup presenter.
- Keep the image inventory/question-figure card in shell until a dedicated boundary design exists.
- Do not add controls or restore enterprise remote concepts.

## 2026-07-07 Execution Record 54: Profile Editor Card Setup Extraction

This pass executed the next safe setup extraction from Record 53: move the profile and field editor card as one whole card into a dedicated setup presenter.

### Decision

Move profile and field editor card construction into `ProfileEditorPresenterMixin` as `_setup_profile_editor_card`.

Reason:

- the card is a coherent local editing surface;
- it owns profile id/name controls, structured field inputs, field status labels, the extra fields text area, and unknown-field suggestion container;
- keeping it whole avoids splitting one visual card between profile state, field editor state, and field status presenters;
- it does not touch enterprise remote capabilities.

### Completed

- Added `src/ui/panels/assets/profile_editor_presenter.py`:
  - defines `ProfileEditorPresenterMixin`;
  - owns `_setup_profile_editor_card`.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and mixes in `ProfileEditorPresenterMixin`;
  - replaces the inline profile/field editor card block with `self._setup_profile_editor_card()`;
  - removes profile-card-only imports from the shell while preserving the legacy `_chunk_form_rows` module-level export required by existing helper tests.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds architecture ownership coverage for `ProfileEditorPresenterMixin`.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_profile_editor_card`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 901 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/profile_editor_presenter.py`: 71 lines, 1 method, 1 class.
- `tests/test_assets_panel_architecture.py`: 618 lines, 32 functions.
- `tests/test_assets_panel_helper_modules.py`: 527 lines, 25 functions.

Compared with Record 53:

- `assets_panel.py` dropped from 952 lines to 901 lines.
- `AssetsPanel` direct method count stayed at 1.
- Focused architecture/helper/spec/question-figure tests increased from `55 passed` to `57 passed`.
- Full related assets regression increased from `96 passed` to `98 passed`.

### Updated `_setup_ui` Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| `_setup_ui` start and state registry | 423-499 | still in shell | Keep for now. |
| shell, return bar, detail stack, section pages | 500-546 | still in shell | Keep in shell. |
| archive/generation/import/profile setup calls | 548-552 | delegated | Keep. |
| image inventory and question-figure table card | 554-885 | still in shell | Defer until a dedicated image/question-figure boundary is designed. |
| preview, batch output, material settings setup calls | 883-886 | delegated | Keep. |
| final layout registration and theme binding | 887-895 | still in shell | Keep in shell. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\profile_editor_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `57 passed`.
- Full related assets regression: `98 passed`.

Residual enterprise scan:

```powershell
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py
```

Result:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 54

`AssetsPanel` now functions as a setup composition shell with one direct method. The remaining inline setup is almost entirely the image inventory and question-figure table card.

Do not extract the remaining image card as one blind movement. It mixes several product surfaces:

- local image inventory;
- asset slot rows;
- attachment role rows;
- image preview;
- question-figure item table;
- question-figure library metadata editor;
- issue table;
- version history table;
- master version table;
- shared cache directory and entry tables.

Current recommendation:

- Pause code movement on the image card until a boundary design names the retained local sub-surfaces.
- The next planning pass should decide whether this becomes one `ImageInventorySetupPresenterMixin` or several smaller setup presenters aligned to existing question-figure/cache/library presenters.
- Keep enterprise deletion guards and full related assets regression as required gates.

## 2026-07-07 Execution Record 55: Shared Cache Table Setup Extraction

This pass started the image-card boundary work by extracting the clearest retained local sub-surface: question-figure shared cache tables.

### Boundary Design

The remaining image card should not move as one block. It currently contains these sub-surfaces:

| Sub-surface | Current lines before extraction | Best owner |
| --- | ---: | --- |
| image card shell, assets picker, asset slot rows | 554-569 | keep in shell or future `ImageInventorySetupPresenterMixin` |
| question-figure item table | 570-594 | `QuestionFigureItemsPresenterMixin` |
| question-figure library table and metadata editor | 595-664 | `QuestionFigureLibraryPresenterMixin` |
| question-figure issue table | 665-699 | `QuestionFigureLibraryIssuePresenterMixin` |
| question-figure version history table | 700-736 | `QuestionFigureLibraryHistoryPresenterMixin` |
| question-figure master version table | 737-774 | `QuestionFigureLibraryMasterVersionPresenterMixin` |
| shared cache directory and entry tables | 775-847 | `QuestionFigureSharedCachePresenterMixin` |
| attachment inventory and image preview controls | 848-880 | asset rows / image preview boundary, not yet final |

### Decision

Move only the shared cache directory and entry table setup into `QuestionFigureSharedCachePresenterMixin`.

Reason:

- the rows, selection handlers, open action, and refresh logic already live in the shared-cache presenter;
- the two tables are a coherent local cache surface;
- the extraction does not require changing image preview, library, issue, or master-version behavior;
- it keeps enterprise remote deletion intact.

### Completed

- Updated `src/ui/panels/assets/cache_presenter.py`:
  - added `_setup_question_figure_shared_cache_tables`;
  - moved both shared cache table constructors and signal wiring into the cache presenter;
  - added the required Qt table imports.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the shared-cache table block with `self._setup_question_figure_shared_cache_tables(image_card)`.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds shared cache setup ownership coverage.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_question_figure_shared_cache_tables`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 829 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/cache_presenter.py`: 249 lines, 7 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 635 lines, 33 functions.
- `tests/test_assets_panel_helper_modules.py`: 545 lines, 26 functions.

Compared with Record 54:

- `assets_panel.py` dropped from 901 lines to 829 lines.
- `AssetsPanel` direct method count stayed at 1.
- Focused architecture/helper/spec/question-figure tests increased from `57 passed` to `59 passed`.
- Full related assets regression increased from `98 passed` to `100 passed`.

### Updated `_setup_ui` Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| `_setup_ui` start and state registry | 423-499 | still in shell | Keep for now. |
| shell, return bar, detail stack, section pages | 500-546 | still in shell | Keep in shell. |
| archive/generation/import/profile setup calls | 548-552 | delegated | Keep. |
| image inventory and question-figure tables | 554-774 | still in shell | Continue only by owner-aligned sub-surface. |
| shared cache table setup call | 775 | delegated | Keep. |
| attachment inventory and image preview controls | 776-813 | still in shell | Defer until image-preview boundary is chosen. |
| preview, batch output, material settings setup calls | 810-814 | delegated | Keep. |
| final layout registration and theme binding | 815-823 | still in shell | Keep in shell. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\cache_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `59 passed`.
- Full related assets regression: `100 passed`.

Residual enterprise scan:

```powershell
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py
```

Result:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 55

The image card can be reduced safely, but only by retained local sub-surface:

1. Next safest candidate:
   - question-figure master version table into `QuestionFigureLibraryMasterVersionPresenterMixin`.
2. Then:
   - version history table into `QuestionFigureLibraryHistoryPresenterMixin`;
   - issue table into `QuestionFigureLibraryIssuePresenterMixin`;
   - library table/editor into `QuestionFigureLibraryPresenterMixin`;
   - question-figure item table into `QuestionFigureItemsPresenterMixin`.
3. Leave image card shell, asset slots, attachment roles, and preview controls until the table sub-surfaces are gone.

Do not introduce a generic `ImageInventorySetupPresenterMixin` yet; existing presenters already provide clearer owners for several sub-surfaces.

## 2026-07-07 Execution Record 56: Master Version Table Setup Extraction

This pass continued the owner-aligned image-card reduction by moving the question-figure master version table setup into its existing presenter.

### Decision

Move master version table construction into `QuestionFigureLibraryMasterVersionPresenterMixin` as `_setup_question_figure_library_master_version_table`.

Reason:

- refresh, selection, and focus behavior for this table already live in the master-version presenter;
- the table is read-only local version consistency projection, not a remote master-data sync workflow;
- moving it first reduces the image card without disturbing library editing or issue/history tables.

### Completed

- Updated `src/ui/panels/assets/question_library_master_version_presenter.py`:
  - added `_setup_question_figure_library_master_version_table`;
  - moved table creation, headers, selection mode, signal wiring, and column sizing into the presenter;
  - added required Qt table imports.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the inline master-version table block with `self._setup_question_figure_library_master_version_table(image_card)`.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds master-version setup ownership coverage.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_question_figure_library_master_version_table`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 792 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/question_library_master_version_presenter.py`: 153 lines, 5 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 654 lines, 34 functions.
- `tests/test_assets_panel_helper_modules.py`: 563 lines, 27 functions.

Compared with Record 55:

- `assets_panel.py` dropped from 829 lines to 792 lines.
- Focused architecture/helper/spec/question-figure tests increased from `59 passed` to `61 passed`.
- Full related assets regression increased from `100 passed` to `102 passed`.

### Updated Image-Card Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| image card shell, assets picker, asset slot rows | 554-569 | still in shell | Keep for now. |
| question-figure item table | 570-594 | still in shell | Move to `QuestionFigureItemsPresenterMixin`. |
| library table and metadata editor | 595-664 | still in shell | Move to `QuestionFigureLibraryPresenterMixin`. |
| issue table | 665-699 | still in shell | Move to `QuestionFigureLibraryIssuePresenterMixin`. |
| version history table | 700-736 | still in shell | Next safest extraction. |
| master version table setup call | 737 | delegated | Keep. |
| shared cache setup call | 738 | delegated | Keep. |
| attachment inventory and image preview controls | 739-776 | still in shell | Defer. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_library_master_version_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `61 passed`.
- Full related assets regression: `102 passed`.

Residual enterprise scan:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 56

Continue only with table sub-surfaces that already have owners. The next safe extraction is the version history table into `QuestionFigureLibraryHistoryPresenterMixin`.

## 2026-07-07 Execution Record 57: Version History Table Setup Extraction

This pass moved the question-figure library version history table setup into its existing history presenter.

### Decision

Move version history table construction into `QuestionFigureLibraryHistoryPresenterMixin` as `_setup_question_figure_library_version_history_table`.

Reason:

- refresh, selection, and rollback behavior already live in the history presenter;
- the table is a retained local metadata history and rollback surface;
- moving it keeps the image card reduction aligned with product ownership.

### Completed

- Updated `src/ui/panels/assets/question_library_history_presenter.py`:
  - added `_setup_question_figure_library_version_history_table`;
  - moved table creation, headers, selection mode, signal wiring, and column sizing into the presenter;
  - added required Qt table imports.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the inline version-history table block with `self._setup_question_figure_library_version_history_table(image_card)`.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds version-history setup ownership coverage.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_question_figure_library_version_history_table`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 756 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/question_library_history_presenter.py`: 185 lines, 5 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 673 lines, 35 functions.
- `tests/test_assets_panel_helper_modules.py`: 581 lines, 28 functions.

Compared with Record 56:

- `assets_panel.py` dropped from 792 lines to 756 lines.
- Focused architecture/helper/spec/question-figure tests increased from `61 passed` to `63 passed`.
- Full related assets regression increased from `102 passed` to `104 passed`.

### Updated Image-Card Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| image card shell, assets picker, asset slot rows | 554-569 | still in shell | Keep for now. |
| question-figure item table | 570-594 | still in shell | Move to `QuestionFigureItemsPresenterMixin`. |
| library table and metadata editor | 595-664 | still in shell | Move to `QuestionFigureLibraryPresenterMixin`. |
| issue table | 665-699 | still in shell | Next safest extraction. |
| version history setup call | 700 | delegated | Keep. |
| master version setup call | 701 | delegated | Keep. |
| shared cache setup call | 702 | delegated | Keep. |
| attachment inventory and image preview controls | 703-740 | still in shell | Defer. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_library_history_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `63 passed`.
- Full related assets regression: `104 passed`.

Residual enterprise scan:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 57

Continue the same narrow sequence. The next safe extraction is the issue table into `QuestionFigureLibraryIssuePresenterMixin`.

## 2026-07-07 Execution Record 58: Issue Table Setup Extraction

This pass moved the question-figure library issue table setup into its existing issue presenter.

### Decision

Move issue table construction into `QuestionFigureLibraryIssuePresenterMixin` as `_setup_question_figure_library_issue_table`.

Reason:

- refresh and row selection behavior already live in the issue presenter;
- the table is a retained local metadata issue projection;
- it is independent from enterprise remote governance and writeback.

### Completed

- Updated `src/ui/panels/assets/question_library_issue_presenter.py`:
  - added `_setup_question_figure_library_issue_table`;
  - moved table creation, headers, selection mode, signal wiring, and column sizing into the presenter;
  - added required Qt table imports.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the inline issue table block with `self._setup_question_figure_library_issue_table(image_card)`.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds issue setup ownership coverage.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_question_figure_library_issue_table`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 722 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/question_library_issue_presenter.py`: 110 lines, 4 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 692 lines, 36 functions.
- `tests/test_assets_panel_helper_modules.py`: 599 lines, 29 functions.

Compared with Record 57:

- `assets_panel.py` dropped from 756 lines to 722 lines.
- Focused architecture/helper/spec/question-figure tests increased from `63 passed` to `65 passed`.
- Full related assets regression increased from `104 passed` to `106 passed`.

### Updated Image-Card Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| image card shell, assets picker, asset slot rows | 554-569 | still in shell | Keep for now. |
| question-figure item table | 570-594 | still in shell | Move to `QuestionFigureItemsPresenterMixin`. |
| library table and metadata editor | 595-664 | still in shell | Next safest extraction. |
| issue setup call | 665 | delegated | Keep. |
| version history setup call | 666 | delegated | Keep. |
| master/shared-cache setup calls | 667-668 | delegated | Keep. |
| attachment inventory and image preview controls | 669-706 | still in shell | Defer. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_library_issue_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `65 passed`.
- Full related assets regression: `106 passed`.

Residual enterprise scan:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 58

Next safe extraction: move the question-figure library table and metadata editor into `QuestionFigureLibraryPresenterMixin`.

## 2026-07-07 Execution Record 59: Library Table And Metadata Editor Setup Extraction

This pass moved the question-figure library table and metadata editor setup into the existing library presenter.

### Decision

Move library table and metadata editor construction into `QuestionFigureLibraryPresenterMixin` as `_setup_question_figure_library_card`.

Reason:

- refresh, row selection, metadata editing, and save behavior already live in the library presenter;
- the table and editor form one local metadata-editing surface;
- moving them together avoids splitting a single user workflow.

### Completed

- Updated `src/ui/panels/assets/question_library_presenter.py`:
  - added `_setup_question_figure_library_card`;
  - moved library table creation, editor controls, save button wiring, and status label setup into the presenter;
  - added required Qt widget/table imports.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the inline library table/editor block with `self._setup_question_figure_library_card(image_card)`.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds library setup ownership coverage.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_question_figure_library_card`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 653 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/question_library_presenter.py`: 247 lines, 6 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 711 lines, 37 functions.
- `tests/test_assets_panel_helper_modules.py`: 617 lines, 30 functions.

Compared with Record 58:

- `assets_panel.py` dropped from 722 lines to 653 lines.
- Focused architecture/helper/spec/question-figure tests increased from `65 passed` to `67 passed`.
- Full related assets regression increased from `106 passed` to `108 passed`.

### Updated Image-Card Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| image card shell, assets picker, asset slot rows | 554-569 | still in shell | Keep for now. |
| question-figure item table | 570-594 | still in shell | Next safest extraction. |
| library setup call | 595 | delegated | Keep. |
| issue/history/master/cache setup calls | 596-599 | delegated | Keep. |
| attachment inventory and image preview controls | 600-637 | still in shell | Defer. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_library_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `67 passed`.
- Full related assets regression: `108 passed`.

Residual enterprise scan:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 59

Next safe extraction: move the question-figure item table into `QuestionFigureItemsPresenterMixin`.

## 2026-07-07 Execution Record 60: Question Figure Item Table Setup Extraction

This pass moved the question-figure item table setup into its existing item presenter.

### Decision

Move question-figure item table construction into `QuestionFigureItemsPresenterMixin` as `_setup_question_figure_items_table`.

Reason:

- refresh, row selection, preview coordination, and replace action behavior already live in the item presenter;
- the table is a retained local question-image inventory surface;
- moving it completes the owner-aligned extraction of question-figure table sub-surfaces from the image card.

### Completed

- Updated `src/ui/panels/assets/question_figures_presenter.py`:
  - added `_setup_question_figure_items_table`;
  - moved table creation, headers, selection mode, signal wiring, and column sizing into the presenter;
  - added required Qt table imports.
- Updated `src/ui/panels/assets_panel.py`:
  - replaced the inline question-figure item table block with `self._setup_question_figure_items_table(image_card)`.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds item-table setup ownership coverage.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_question_figure_items_table`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 629 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/question_figures_presenter.py`: 131 lines, 3 methods, 1 class.
- `tests/test_assets_panel_architecture.py`: 728 lines, 38 functions.
- `tests/test_assets_panel_helper_modules.py`: 632 lines, 31 functions.

Compared with Record 59:

- `assets_panel.py` dropped from 653 lines to 629 lines.
- Focused architecture/helper/spec/question-figure tests increased from `67 passed` to `69 passed`.
- Full related assets regression increased from `108 passed` to `110 passed`.

### Updated Image-Card Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| image card shell, assets picker, asset slot rows | 554-569 | still in shell | Ready for whole image-inventory setup extraction. |
| question-figure item setup call | 570 | delegated | Keep. |
| library/issue/history/master/cache setup calls | 571-575 | delegated | Keep. |
| attachment inventory and image preview controls | 576-613 | still in shell | Include in image-inventory setup extraction. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `69 passed`.
- Full related assets regression: `110 passed`.

Residual enterprise scan:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Plan Review After Record 60

All question-figure table sub-surfaces inside the image card now have presenter owners. It is now safe to extract the remaining image card shell, asset picker, asset slot container, attachment inventory, and preview controls into a dedicated local image inventory setup presenter.

## 2026-07-07 Execution Record 61: Image Inventory Card Setup Extraction

This pass completed the owner-aligned image-card reduction by moving the remaining local image inventory card shell into a dedicated setup presenter.

### Decision

Move the image card shell, assets picker, asset slot container, attachment inventory, and preview controls into `ImageInventorySetupPresenterMixin` as `_setup_image_inventory_card`.

Reason:

- all question-figure table sub-surfaces had already been extracted to their own presenters;
- the remaining block is a coherent local image inventory and preview shell;
- keeping the sub-surface setup calls inside this card setup preserves the visual composition while keeping behavior owners separate.

### Completed

- Added `src/ui/panels/assets/image_inventory_presenter.py`:
  - defines `ImageInventorySetupPresenterMixin`;
  - owns `_setup_image_inventory_card`;
  - builds the retained local image inventory card and delegates table setup to existing presenters.
- Updated `src/ui/panels/assets_panel.py`:
  - imports and mixes in `ImageInventorySetupPresenterMixin`;
  - replaces the image card block with `self._setup_image_inventory_card()`;
  - removes no-longer-used direct table/form imports from the shell.
- Updated `tests/test_assets_panel_architecture.py`:
  - adds image inventory setup ownership coverage.
- Updated `tests/test_assets_panel_helper_modules.py`:
  - adds runtime MRO ownership coverage for `_setup_image_inventory_card`.

### Size Snapshot

- `src/ui/panels/assets_panel.py`: 571 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- `src/ui/panels/assets/image_inventory_presenter.py`: 72 lines, 1 method, 1 class.
- `tests/test_assets_panel_architecture.py`: 745 lines, 39 functions.
- `tests/test_assets_panel_helper_modules.py`: 647 lines, 32 functions.

Compared with Record 60:

- `assets_panel.py` dropped from 629 lines to 571 lines.
- Focused architecture/helper/spec/question-figure tests increased from `69 passed` to `71 passed`.
- Full related assets regression increased from `110 passed` to `112 passed`.

### Final `_setup_ui` Boundary Map

Current line map in `src/ui/panels/assets_panel.py`:

| Area | Lines | Current status | Recommended action |
| --- | ---: | --- | --- |
| `_setup_ui` start and state registry | 419-495 | shell-owned | Keep in shell. |
| master-detail shell, return bar, detail stack, sections | 496-546 | shell-owned | Keep in shell. |
| archive/generation/import/profile/image/preview/batch/settings setup calls | 546-556 | delegated | Keep. |
| final layout stretch, detail registration, initial reload, summary, theme binding | 557-565 | shell-owned | Keep in shell. |

### Verification

Passed:

```powershell
python -m py_compile src\ui\panels\assets_panel.py src\ui\panels\assets\image_inventory_presenter.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py
python -m pytest -q tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- Focused assets architecture/helper/spec/question-figure regression: `71 passed`.
- Full related assets regression: `112 passed`.

Residual enterprise scan:

- No active enterprise remote implementation hits in `src`.
- Remaining hits are negative boundary tests.

### Phase Completion Review

This phase's code simplification goal is now satisfied for `AssetsPanel`:

- enterprise remote implementation remains absent from `src`;
- `AssetsPanel` is a one-method setup shell;
- setup blocks now live in owner-aligned presenters;
- the remaining shell code is composition, initial state registry, and lifecycle wiring;
- retained local question-figure, cache, audit, preview, batch, and profile paths are still covered by focused and full related assets regressions.

Do not continue moving shell initialization state unless there is a new product or runtime requirement. Further line-count reduction would now risk hiding composition state in artificial owners.

## 2026-07-07 Execution Record 62: Final Phase Audit After Image Card Decomposition

This pass records the final state after completing the question-figure item table extraction and the image inventory card setup extraction.

### Completed Since Record 59

1. Question-figure item table extraction:
   - moved `_setup_question_figure_items_table` into `QuestionFigureItemsPresenterMixin`;
   - added architecture and runtime ownership guards.
2. Image inventory card extraction:
   - added `src/ui/panels/assets/image_inventory_presenter.py`;
   - moved `_setup_image_inventory_card` into `ImageInventorySetupPresenterMixin`;
   - the image card now delegates to item, library, issue, history, master-version, and cache presenters for their own table setup;
   - removed direct table/form imports from `AssetsPanel`.

### Final Size Snapshot

- `src/ui/panels/assets_panel.py`: 571 lines, 3 functions/methods, 2 classes.
- `AssetsPanel`: 1 direct method: `_setup_ui`.
- Focused architecture/helper/spec/question-figure regression: `71 passed`.
- Full related assets regression: `112 passed`.

### Final `AssetsPanel` Responsibility

`AssetsPanel` now owns only:

- initial state registry;
- master-detail shell creation;
- return bar and detail stack creation;
- section page construction;
- presenter setup call ordering;
- initial reload, summary refresh, and theme binding.

It no longer directly owns:

- archive card setup;
- generation action setup;
- import/export setup;
- profile editor setup;
- image inventory card setup;
- question-figure item/library/issue/history/master/cache table setup;
- placeholder preview setup;
- batch output setup;
- material settings setup;
- summary refresh;
- theme application.

### Enterprise Remote Boundary

Residual scan for deleted enterprise remote tokens:

```powershell
rg -n "remote_writeback|enterprise_auth|signed_url|external_permission|master_registry|registry_sync|subscription_lock|subscription_change|subscription_drift|non_question_asset_family|download_remote_asset_preview_image|remote_asset_auth" src tests\test_assets_panel_architecture.py tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py
```

Result:

- no active enterprise remote implementation hits in `src`;
- remaining hits are negative boundary tests asserting removed capabilities stay absent.

### Final Recommendation

Stop this simplification phase here.

Further movement from `AssetsPanel._setup_ui` would mostly hide shell composition state behind artificial owners. The next healthy workstream, if needed, should be separate from this phase:

- runtime visual verification of the refactored assets panel;
- targeted cleanup of presenter internals where a single presenter grew too large;
- optional full-suite regression when broader repository state is ready.

## 2026-07-07 Execution Record 63: Presenter Internal Cleanup After Shell Completion

This pass follows the post-shell recommendation without moving more code out of `AssetsPanel._setup_ui`.

### Scope

- Keep `AssetsPanel` as the composition shell.
- Keep deleted enterprise/remote capabilities absent from active source.
- Clean presenter internals where the prior extraction left large orchestration methods.

### Changes

1. `src/ui/panels/assets/theme_presenter.py`
   - Kept `_apply_theme` as the public theme entry point.
   - Split theme application into widget-family helpers:
     - `_apply_shell_theme`
     - `_apply_generate_action_icons`
     - `_apply_text_label_theme`
     - `_apply_form_input_theme`
     - `_apply_asset_row_theme`
     - `_apply_asset_icon_button_sizing`
     - `_apply_profile_list_theme`
     - `_apply_command_button_theme`
   - Added architecture coverage so `_apply_theme` remains a grouped orchestrator.

2. `src/ui/panels/assets/section_summary_presenter.py`
   - Added `SectionSummaryRefreshState` so summary refresh data is explicit instead of passed as a long argument bundle.
   - Moved summary-state construction into `_build_section_summary_state`.
   - Kept local question-figure/cache/table refresh calls directly visible from `_refresh_summary` for existing boundary tests.
   - Split summary-card item building by section:
     - `_generate_summary_items`
     - `_io_summary_items`
     - `_field_summary_items`
     - `_image_summary_items`
     - `_preview_summary_items`
     - `_batch_summary_items`
     - `_advanced_summary_items`
   - Added `_summary_item` to remove repeated `SummaryGridItem` boilerplate.
   - Reduced `section_summary_presenter.py` to 440 lines while keeping section responsibilities explicit.

3. `tests/test_assets_panel_architecture.py`
   - Added guards for grouped theme application.
   - Added guards that section summary remains state-driven and item-group based.

4. `src/ui/panels/assets/preview_table_presenter.py`
   - Added `_preview_row` to remove repeated preview-row dictionary shape.
   - Rewrote `_placeholder_preview_rows` to keep decision order unchanged while centralizing row construction.
   - This is a small simplification step, not a service extraction; table rendering and row actions remain in the presenter.

### Validation

```powershell
python -m py_compile src\ui\panels\assets\section_summary_presenter.py src\ui\panels\assets\theme_presenter.py tests\test_assets_panel_architecture.py
python -m pytest -q tests\test_assets_panel_architecture.py::test_assets_theme_application_stays_grouped_by_widget_family tests\test_assets_panel_architecture.py::test_assets_section_summary_stays_state_driven tests\test_assets_panel_architecture.py::test_assets_summary_refresh_updates_local_question_figure_projections
python -m pytest -q tests\test_assets_panel_helper_modules.py::test_assets_panel_uses_preview_table_presenter_mixin tests\test_assets_panel_architecture.py::test_assets_panel_delegates_preview_state_to_preview_table_presenter_mixin tests\test_assets_panel_architecture.py::test_assets_summary_refresh_updates_local_question_figure_projections
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_cache.py tests\test_assets_panel_question_audit.py tests\test_assets_question_library_presenter.py tests\test_assets_cache_presenter.py tests\test_assets_question_figures_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
```

Results:

- focused new architecture guards: `3 passed`;
- focused preview presenter regression: `3 passed`;
- full related assets regression: `114 passed`;
- deleted enterprise/remote token scan: no active implementation hits in `src`; remaining hits are negative boundary tests.

### Next Candidates

The shell simplification remains complete. Further useful cleanup should be targeted at the largest retained local presenters:

- `image_preview_presenter.py`: split display/zoom state from compare/issue marking behavior.
- `preview_table_presenter.py`: optionally extract placeholder row projection from the presenter only if this logic continues to grow.
- `batch_import.py`: consider a parser object only if import rules continue growing.
