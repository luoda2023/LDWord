# Workbench「执行输出 / 问题处理」收敛执行记录

> 日期：2026-07-10  
> 来源审计：[Workbench「执行输出 / 问题处理」必要性深度审计](../audits/Workbench执行输出问题处理必要性深度审计_2026-07-10.md)  
> 状态：已完成  
> 范围：快速执行主区、资料门禁、对象预检确认、运行结果详情、执行日志、相关静态治理与测试契约

## 1. 执行结论

审计结论已经落地。拖入题稿后，快速执行页不再自动创建、展开和选中一套内嵌「问题处理」工作台；主区现在只表达用户下一步：

| 场景 | 主区状态 | 生成动作 | 条件动作 |
|---|---|---|---|
| 无资料问题 | 可生成 | 可用 | 无 |
| 非阻断资料提醒 | 可生成；部分信息将使用默认值 | 可用 | 补充信息（可选） |
| 真阻断 | 无法生成：缺少必需资料 | 禁用 | 去补齐 |
| 需人工确认 | 生成前需确认资料缺口 | 确认并生成 | 补充信息 |
| 对象风险 | 紧凑显示风险与跳过结果 | 确认并继续 | 取消 |
| 运行完成 | 已完成；N 项提醒 | 已完成 | 查看结果详情 |

这次删除的是前台过度设计的问题管理器；资料预检、Word 对象预检、Pipeline 保护、结果诊断和修复导航仍然保留。

## 2. 四阶段闭环

| 审计阶段 | 落地结果 | 状态 |
|---|---|---|
| 阶段 1：立即止血 | 静态 coverage / parameter / sample / control 审计退出当前文件主区；删除“已处理 / 忽略”；资料状态遵循 `failure_policy`；Markdown 使用解析后的有效资料上下文 | 完成 |
| 阶段 2：替换主界面 | 新增统一 `ExecutionGateDecision`；主区收敛为按钮、单一状态和一个条件动作；对象预检改为紧凑确认；日志默认折叠、失败自动展开 | 完成 |
| 阶段 3：迁移结果能力 | `ExecutionResultState.issue_items` 迁入固定的“执行结果”详情；保留修复路由；主区只显示结果详情入口 | 完成 |
| 阶段 4：清理遗留 | 删除 Quick 内联问题面板、筛选、列表、证据、状态变更和 active issue 往返 API；重写旧队列测试与源码证据型审计；完成五类状态回归 | 完成 |

## 3. 关键实现

### 3.1 唯一资料门禁

- `src/ui/adapters/workbench_execution_gate.py` 新增 `ExecutionGateAction`、`ExecutionGateDecision`、策略归一化和统一决策函数。
- `src/ui/adapters/workbench_material_issues.py` 同时向界面与运行链路提供 `material_readiness_gate_decision()`；资料 issue 不再一律标成 blocker。
- `src/ui/panels/workbench/material_preflight.py` 使用同一套 `warn / block / confirm` 策略归一化。
- `src/ui/panels/workbench/execution_runtime.py` 在 Markdown 运行路径中也执行 block 门禁，避免 UI 与 Runner 得出相反结论。

门禁模型的权威字段为：

| 字段 | 用途 |
|---|---|
| `can_run` | 是否允许进入运行 |
| `requires_confirmation` | 是否必须由用户显式确认 |
| `blocking_reasons` | 真正阻断原因 |
| `warning_reasons` | 不阻断提醒 |
| `primary_action` | 当前唯一修复动作 |

### 3.2 Markdown 假阻断修复

`QuickExecutionDetail._effective_material_context()` 会解析考试 Markdown，并合并 `exam_markdown_import_entity_data`。标题、学科、年级、时长和分值已经从题稿识别时，不会再因为空的 `_material_context` 被重复报告为缺失。

同时保留两条真实约束：

1. `failure_policy=warn` 时，缺少可选信息不阻断生成；
2. `failure_policy=block` 时，页面与 Markdown Runner 同时阻断。

### 3.3 快速执行区收敛

`src/ui/panels/workbench/quick_execution_detail.py` 已移除：

- 问题处理面板及默认展开逻辑；
- 问题与动作双筛选器；
- 问题列表、自动选择第一项和详情区；
- evidence 逐行展开；
- “已处理 / 忽略”虚假状态；
- Quick 层的 active issue、过滤、状态修改和修复信号 API；
- 静态产品边界与开发审计向当前文件主区的注入。

静态扫描确认该文件中已不存在 `_issue_panel`、`_issue_list`、`_issue_filter`、`mark_resolved`、`mark_ignored`、`issue_repair_requested` 或 `static_audit` 等旧入口。

Quick 仍保留两个必要的按需出口：

- `result_details_requested`：打开运行结果详情；
- `object_preflight_cancel_requested`：取消对象风险确认。

执行日志默认折叠；运行失败时自动展开，用户也可主动切换。

### 3.4 结果问题迁移

- `ExecutionHistoryDetailPane` 现在接收完整 `ExecutionResultState`，展示运行结果 issue，并支持搜索、定位与修复导航。
- `WorkbenchExecutionController` 同步执行进度、模块状态与最终结果。
- `WorkbenchPanel` 注册固定 `execution_history` 详情卡，连接主区的“查看结果详情”和结果修复路由。
- `WorkbenchNavigationController` 把执行结果纳入正常导航，不再借用 Quick 的 active issue 往返状态。

结果 issue 的数据模型与转换 adapter 继续存在，因为它们属于运行后诊断能力，而不是被删除的内联问题管理器。

### 3.5 静态治理契约迁移

下列治理模块已从“必须存在问题队列控件”改为验证真实产品目标：统一门禁、唯一资料动作、紧凑对象确认和可访问的结果详情。

- `control_contract_registry.py`
- `scene_control_consistency_audit.py`
- `scene_control_runtime_consistency_audit.py`
- `scene_coverage_manifest.py`
- `scene_material_repair_flow_audit.py`
- `scene_object_preflight_action_audit.py`
- `scene_repair_routing.py`
- `scene_report_artifact_drilldown_audit.py`
- `scene_rule_source_governance.py`

底层 coverage、参数归属、样本和控件契约审计没有删除；它们继续服务于发布检查、方案治理和开发诊断，但不再冒充当前文件的运行问题。

## 4. 测试与视觉证据

### 4.1 自动化验证

| 验证组 | 结果 |
|---|---|
| Quick、执行会话、统一门禁、结果详情、资料上下文、worker 等核心回归 | `251 passed` |
| 控件一致性、资料修复流、对象预检、路由、覆盖清单、发布聚合等治理审计 | `62 passed` |
| Python 编译检查 | 通过 |
| `git diff --check` | 通过 |
| Quick 旧问题队列 API 静态扫描 | 0 命中 |

新增或重写的核心契约覆盖：

1. ready / warn / block / confirm 四种资料门禁；
2. Markdown 已识别字段不会产生假缺失；
3. Markdown block 策略在 Runner 侧同样生效；
4. 静态产品边界不进入当前文件执行主区；
5. 主区只有一个资料 CTA；
6. 拖入预检不会以内联面板撑高执行卡；
7. 对象 warning 必须确认、可取消，strict finding 仍阻断；
8. 结果 issue 可从执行结果详情访问并继续修复路由；
9. 日志默认折叠，失败自动展开。

### 4.2 视觉回归

在 Qt offscreen 环境以微软雅黑完成了紧凑状态渲染检查：

- warning 与 block 状态的执行卡高度均约 96 px；
- 对象确认状态约 138 px；
- ready、warning、block、对象确认、完成和失败状态均未再出现截图中的大型内联诊断区域；
- 文案、按钮与日志切换无重叠。

## 5. 全量测试边界

全量测试初跑为 `2007 passed, 51 failed`。本次引入的旧审计证据和聚合计数不一致已全部修复；随后失败复核只剩以下 3 项：

1. `test_meeting_policy_family_application_builds_official_archive_defaults`：会议资料 schema 默认集合差异；
2. `test_heading_detail_restore_recomputes_template_dirty_state`：模板标题恢复后的 dirty 状态；
3. `test_heading_detail_preset_change_enters_save_restore_state_machine`：标题预设切换未进入 dirty 状态。

这 3 项涉及会议方案默认资料与模板标题状态机，本次没有修改其实现或测试，也不经过 Workbench 执行输出链路。为避免覆盖工作区中已有的大量未提交改动，本次记录它们但不越界修复。当前任务范围内的核心回归与治理审计均已通过。

## 6. 保留项说明

以下代码看似与“问题”有关，但不应因删除主区面板而一并删除：

- `WorkbenchIssueItem`：仍是运行结果、批量结果和修复导航的数据结构；
- `workbench_issue_navigation.py`：仍承担结果详情的目标定位；
- `EvidenceLineList`：被执行结果详情复用；
- coverage / sample / parameter / control adapter：仍被治理与发布审计调用；
- 资料预检、对象预检与 Pipeline guard：是真正的运行安全边界。

通用 `EvidenceActionBar` 和 `IssueDetailSection` 没有重新接入 Quick；它们属于共享 UI 库并有独立契约，不是本次内联问题面板残留。若后续要精简整个共享组件库，应另做消费者与兼容性审计。

## 7. 最终验收

- [x] 拖入题稿后不再突然出现大型问题处理区
- [x] 同一资料问题不再在主区重复六次
- [x] 可选元数据缺失不再伪装成硬阻断
- [x] 真 blocker 在 UI 与 Runner 两侧一致
- [x] 静态治理信息退出普通用户主流程
- [x] “已处理 / 忽略”虚假控制已删除
- [x] 对象风险仍需显式确认且可取消
- [x] 运行后问题可从结果详情访问
- [x] 执行日志默认折叠，失败可见
- [x] 旧队列测试与源码证据审计已迁移

最终界面遵循同一原则：主流程只表达用户下一步，检测继续在后台运行，证据按需出现，安全门禁由同一个权威模型决定。
