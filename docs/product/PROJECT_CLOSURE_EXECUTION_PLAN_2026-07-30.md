# Alavette Form V1.0 项目收口执行总账

> 状态：执行中  
> 建立日期：2026-07-30  
> 适用分支：`codex/code-structure-health-staging`  
> 基线提交：`9284471e0f182d9ee2174b631f53dbb726ded740`  
> 产品验收明细：`docs/product/Alavette_Form_V1.0_P0_Execution_Tracker.md`

## 1. 权威边界

本文件是当前项目收口工作的唯一总账。其他审计、规划和重构记录只提供历史背景或专项证据，不再分别维护项目总体完成状态。

本轮只做：

- 建立可审阅、可回退的版本控制边界；
- 恢复工程、测试、发布和公开发布门禁；
- 完成 P0 AC-03 至 AC-11；
- 收口有效文档状态。

本轮不做：

- 新增产品功能；
- 恢复已经裁决删除的兼容链；
- 为通过审计伪造源码标记或统计结果；
- 把全部工作区变化合并为一个不可审阅提交；
- 在归属未确认前批量删除本地或未跟踪文件。

### 文档生命周期

- 当前权威：本总账、P0 执行追踪表、V1.0 PRD、架构与发布规范；
- `docs/audits/`：按文件日期冻结的历史审计证据，不表达当前完成状态；
- `docs/refactor-records/`：已执行或已被后续实现取代的历史记录；
- `docs/superpowers/plans/`：历史实施计划；与本总账冲突时以本总账为准。

## 2. 2026-07-30 基线

| 项目 | 数量 / 状态 |
| --- | --- |
| 已跟踪但修改 | 439 |
| 已跟踪但删除 | 55 |
| 未跟踪文件 | 721 |
| 暂存文件 | 0 |
| 未跟踪 Python 文件 | 548 |
| 可收集测试 | 4278 |
| 工程门禁 | 通过：显式低争议 Ruff 规则、编译、收集与 29 项 smoke |
| 场景 release payload | 通过：全部检查 0 issues |
| 严格公开发布扫描 | 失败：23 项 |
| P0 AC | AC-01～AC-11 目标验收完成 |

未跟踪文件按主边界分布：

| 边界 | 数量 | 初步处置 |
| --- | ---: | --- |
| `src/` | 350 | 产品源码候选，按子系统验证后跟踪 |
| `tests/` | 191 | 对应新实现的测试候选，按子系统验证后跟踪 |
| `docs/` | 73 | 区分权威文档、历史记录和可删除生成物 |
| `config_library/` | 50 | 核对旧资源迁移和 builtin/user 隔离 |
| `licenses/` | 48 | 通过许可证生成与发布检查后跟踪 |
| `scripts/` | 8 | 按工程、发布、Office 工具职责验证 |
| `defaults/` | 1 | 核对模板创作配置 owner |

## 3. 版本控制迁移批次

| 批次 | 边界 | 必须证明 | 状态 |
| --- | --- | --- | --- |
| G1 | 配置库与内置资源 | 旧 `scenes/templates/exam_masters` 有明确新 owner；builtin/user 隔离通过 | 已提交 `521943e` |
| G2 | 许可证与发布基础设施 | manifest 可重建；严格许可测试通过 | 已提交 `dc8bd97` |
| G3 | Assistant | 应用、runtime、storage、UI 契约闭合 | 已提交 `ab1bcd7` |
| G4 | 资料与产物装配 | intake、snapshot、assembly、delivery、Office 链闭合 | 已提交 `0de2a8f` |
| G5 | 模板、方案与 Workbench | UI owner、事务、导航和执行会话闭合 | 已提交 `c640dd5` |
| G6 | 文档范围识别 | 方案意图、导入后扫描、会话冻结、运行时过滤闭合 | 分布于 G1/G4/G5，已验证 |
| G7 | 测试与文档 | 测试归属明确；历史文档标记完成或 superseded | 测试已提交 `7dcf617`；文档收口中 |

所有批次遵守：

```text
归属审计
→ 编译与收集
→ 所属测试
→ 暂存清单复核
→ 独立提交
```

删除项按替代 owner 分组闭环：

| 删除边界 | 替代 owner / 裁决 |
| --- | --- |
| `scenes/`、`templates/`、`defaults/thesis.yaml` | `config_library/plans/`、`config_library/templates/` 与模板创作 profile |
| `exam_masters/builtin/` | `config_library/masters/exam/builtin/` |
| 旧样式差异控件与审计脚本 | 当前模板预览投影、执行状态链；旧可视化审计正式退役 |
| 旧资料问图/设置 presenter | `src/services/material_assets/` 与 `src/ui/panels/assets/` 当前 presenter |
| 旧方案范围/样式 override 服务 | 当前 document scope、scene detail 与 control registry owner |
| 旧 Workbench facade/runtime 文件 | `src/ui/panels/workbench/` 控制器与 `src/services/production_runtime/` |
| 7 个旧测试模块 | 新架构、事务、预览和资料链回归测试取代 |

## 4. 当前根阻断

### B1 工程门禁

- 已关闭；
- Ruff 规则显式固定为 `E9,F63,F7,F82`，不再受工具默认规则升级影响；
- 设计系统测试已对齐迁移后的反馈 mixin 与 `Card.set_header`；
- execution runtime 中的批量报告和公文 payload 转发壳已删除，调用真实 owner。

### B2 场景发布门禁

- 已关闭；
- 固定版式路由证据已指向真实 owner
  `src/ui/adapters/workbench_product_issue_navigation.py`；
- 交付报告证据已指向真实 owner `src/product_report_writer.py`；
- 全量场景门禁 0 issues，requirement dimensions 10/10、固定版式 12/12、
  drilldown 37/37。

### B3 P0 端到端验收

- 已关闭；
- AC-03～AC-11 组合复验 43 项全部通过；
- 内置模板保存语义已纠正为创建用户副本，不保留原内置脏草稿；
- 明细与测试入口统一记录在 P0 执行追踪表。

### B4 公开发布

严格扫描当前发现本地环境、build/dist、artifacts/output、用户资源目录、spec 和测试生成 DOCX 共 23 项。清理必须在产品文件完成归属后进行。

## 5. 执行阶段

| 阶段 | 完成条件 | 状态 |
| --- | --- | --- |
| P0 盘点 | 全部 Git 变化完成边界分类 | 已完成 |
| P1 Git 收口 | 无未跟踪产品源码、测试和正式文档；形成独立提交 | 执行中 |
| P2 工程门禁 | `scripts/engineering_gate.py` 通过 | 已完成 |
| P3 发布根问题 | 全局 scene release payload 为 `passed` | 已完成 |
| P4 P0 验收 | AC-01～AC-11 均有端到端证据 | 已完成 |
| P5 全量回归 | 4278 项完整执行结束，无未知失败 | 待执行 |
| P6 公开发布 | 严格扫描、许可证、staging 和打包 smoke 通过 | 待执行 |
| P7 最终归档 | 工作区干净，文档状态一致，最终报告完成 | 待执行 |

## 6. 完成定义

只有同时满足以下条件，项目才允许标记完成：

1. Git 工作区干净，或只剩明确忽略的本地状态；
2. 产品源码、测试、正式配置、许可证和权威文档均被跟踪；
3. 所有删除都有替代 owner 或正式删除裁决；
4. 工程门禁通过；
5. 场景 release payload 通过；
6. AC-01～AC-11 全部完成；
7. 4278 项全量测试完成且没有未知失败；
8. Windows、Word/WPS 和打包后核心路径完成验证；
9. 严格公开发布扫描通过；
10. 历史文档已标记完成、superseded 或 archived。

## 7. 执行记录

### 2026-07-30

- 建立当前工作区基线；
- 确认 494 个已跟踪变化、721 个未跟踪文件、暂存区为 0；
- 确认工程门禁因缺少 `ruff` 无法启动；
- 确认严格公开发布扫描存在 23 项；
- 确认场景 release payload 的三个根问题组；
- G1 配置资源相关 326 项测试通过，1 项因 Windows 符号链接权限跳过；
- 工程门禁安装 Ruff 后修复 Windows 输出解码，并将静态规则锁定为项目原定的低争议集合；
- 工程门禁通过：4273 项收集、29 项 smoke、编译与静态检查均通过；
- 关闭 3 项已知架构失败：2 项测试契约漂移、1 项运行时重复所有权；
- 修正固定版式路由与交付报告的审计 evidence owner，不回填旧文件标记；
- 场景 release payload 全量通过，全部检查 0 issues；
- AC-03～AC-11 组合验收 43 项全部通过，P0 AC-01～AC-11 目标验收完成；
- 内置模板保存改为用户命名副本，源字节保持不变且保存后无残留脏草稿；
- 新增 CLI 显式方案/模板、无效输入和问题报告无网络传输回归，当前收集 4278 项；
- 完成全部 Git 变化归属审计，无本地生成物或用户资源进入暂存区；
- G1～G5 与 G7 测试边界形成 6 个独立提交，删除项替代 owner 已分组闭环；
- 历史审计、重构记录和旧实施计划由本总账统一声明生命周期。
