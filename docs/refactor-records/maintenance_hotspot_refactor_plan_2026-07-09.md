# 维护热点完善方案

日期: 2026-07-09

## 1. 背景

本方案针对最近复审中确认的三个维护热点:

1. `src/ui/panels/scene_panel.py` 仍是 UI 侧最大维护热点。
2. `src/report_writer.py` 与 `src/ui/adapters/workbench_execution_adapter.py` 仍在按 section / issue family 持续膨胀。
3. CI 依赖安装口径需要避免和 `pyproject.toml` 漂移。

当前工作区基线:

| 文件 | 当前行数 | 说明 |
| --- | ---: | --- |
| `src/ui/panels/scene_panel.py` | 5972 | 主面板仍承载导航、详情装配、场景选择、样本/请求 cell、预检摘要等多类职责 |
| `tests/test_scene_panel_architecture.py` | 4582 | 架构断言和行为测试混在同一个大测试文件中 |
| `src/report_writer.py` | 3433 | 公开入口稳定，但内部 `_extract_*` / `_format_*` section 继续成对增长 |
| `src/ui/adapters/workbench_execution_adapter.py` | 3004 | issue item、证据行、素材、批量执行、preflight 等逻辑仍混在同一 adapter |
| `src/ui/panels/scene_card_definitions.py` | 41 | 已完成第一刀: `ScenePanel` 导航卡片常量迁出 |
| `.github/workflows/scene-matrix-release-gate.yml` | 97 | 已完成第一刀: 改为 `pip install -e ".[dev]"` |

## 2. 总体原则

- 每轮只处理一个可回滚边界，保持独立提交。
- 优先搬纯数据、纯投影、纯 formatter/extractor，不先搬 Qt widget 生命周期。
- 保持公开入口稳定:
  - `from src.ui.panels.scene_panel import ScenePanel`
  - `from src.report_writer import write_json_report, write_markdown_report`
  - `from src.ui.adapters.workbench_execution_adapter import WorkbenchExecutionAdapter`
- 抽出新模块后，原模块先继续 re-export 或代理调用，等下游引用收敛后再考虑改 import。
- 测试先改断言归属，不降低行为覆盖。

## 3. P2: ScenePanel 继续拆分方案

### 3.1 已完成基线

已完成:

- 新增 `src/ui/panels/scene_card_definitions.py`。
- 从 `scene_panel.py` 移出 `CARD_DEFINITIONS`、`CARD_ORDER`、`FIXED_CARDS`、`FORMAT_TEMPLATE_CARDS`、`INPUT_MATERIAL_CARDS`、`NAV_SECTION_CARD_GROUPS`。
- `scene_panel.py` 继续 import 这些常量，因此外部 `CARD_DEFINITIONS` 读取路径暂时不变。
- `tests/test_scene_panel_architecture.py` 已同步检查新模块承接卡片定义。

### 3.2 下一轮优先切片

建议按以下顺序继续，不建议一次性拆包重命名。

| 切片 | 新模块建议 | 搬迁内容 | 风险 | 验收重点 |
| --- | --- | --- | --- | --- |
| S1 | `src/ui/panels/scene_navigation_projection.py` | `_normalise_scene_detail_card_id`、导航分组/别名、导航 subtitle/snapshot 的纯函数 | 低 | 导航目标、Workbench issue 跳转不变 |
| S2 | `src/ui/panels/scene_selector_model.py` | 场景选择器 group id、builtin scene id、场景 selector 文案/过滤纯函数 | 低 | 场景库选择、内置/我的场景分组不变 |
| S3 | `src/ui/panels/scene_request_cell_projection.py` | request cell tooltip、filter option、list item projection 的 UI 无关部分 | 中 | request cell 列表、筛选、tooltip 不变 |
| S4 | `src/ui/panels/scene_sample_fixture_projection.py` | sample fixture status、list item、library status 的 UI 无关部分 | 中 | 样本库状态、生成/打开动作不变 |
| S5 | `src/ui/panels/scene_panel_actions.py` | 打开路径、生成样本、导入母版等 action wrapper | 中高 | QFileDialog、QDesktopServices、toast 行为不变 |

第一轮只建议执行 S1。S1 的目标不是立刻大幅减行，而是让后续导航相关变更不用继续进入 `scene_panel.py`。

### 3.3 ScenePanel 测试拆分

`tests/test_scene_panel_architecture.py` 已经接近 4600 行，后续应同步拆测试，否则主代码拆薄后测试仍会变成维护瓶颈。

建议新增:

- `tests/test_scene_panel_navigation_architecture.py`
- `tests/test_scene_panel_request_cell_projection.py`
- `tests/test_scene_panel_sample_fixture_projection.py`

迁移规则:

- 只搬和新模块直接相关的测试。
- 保留集成级测试在 `test_scene_panel_architecture.py`。
- 对源码字符串断言，优先检查职责归属，例如新模块包含常量、原模块 import 新模块，而不是检查旧文件里是否存在字面量。

### 3.4 ScenePanel 验收命令

每个 ScenePanel 切片至少执行:

```powershell
python -m pytest -q tests/test_scene_panel_architecture.py tests/test_workbench_issue_navigation.py
python scripts\check_public_release.py --strict
```

若触及 Qt widget 或 action 行为，再追加:

```powershell
python -m pytest -q tests/test_workbench_execution_session_architecture.py tests/test_scene_overview_projection.py
python scripts\engineering_gate.py
```

## 4. P2: report_writer 继续拆分方案

### 4.1 当前结构判断

`src/report_writer.py` 公开入口稳定，继续保留:

- `write_json_report()`
- `write_markdown_report()`

内部风险主要来自 section 成对增长:

- `_extract_journal_submission_package()` / `_format_journal_submission_package_markdown()`
- `_extract_official_numbering_preservation()` / `_format_official_numbering_preservation_markdown()`
- `_extract_technical_chapter_inventory()` / `_format_technical_chapter_inventory_markdown()`
- `_extract_application_section_word_limits()` / `_format_application_section_word_limits_markdown()`
- `_extract_exam_question_schema()` / `_format_exam_question_schema_markdown()`
- `_extract_material_field_consistency()` / `_format_material_field_consistency_markdown()`
- `_extract_object_preflight()` / `_format_object_preflight_markdown()`
- `_extract_control_contracts()` / `_format_control_contracts_markdown()`
- `_extract_parameter_ownership()` / `_format_parameter_ownership_markdown()`

### 4.2 推荐目标结构

延续已有 `src/reporting/` 边界，新增 section 模块，不再新增顶层大文件。

建议结构:

```text
src/reporting/
  sections/
    __init__.py
    journal_submission.py
    official_numbering.py
    technical_chapter.py
    application_word_limits.py
    exam_runtime.py
    material_consistency.py
    object_preflight.py
    coverage_boundaries.py
    scene_release_evidence.py
    parameter_ownership.py
    control_contracts.py
```

`report_writer.py` 只保留:

- 公开入口。
- section 调用顺序。
- 文件写入与顶层 payload 拼装。
- 对旧函数名的短期代理，直到测试和引用迁移完成。

### 4.3 推荐切片顺序

| 切片 | 内容 | 原因 | 推荐测试 |
| --- | --- | --- | --- |
| R1 | official numbering、technical chapter、application word limits | 输入输出相对独立，风险低 | `tests/test_execution_diagnostics_reporting.py` 对应用例 |
| R2 | exam question schema、exam delivery runtime | 领域内聚，现有测试集中 | `tests/test_exam_question_schema_runtime.py` |
| R3 | material field consistency、object preflight | 与 Workbench issue 有边界，但 report 输出相对独立 | `tests/test_material_field_consistency.py`、`tests/test_object_preflight_semantics.py` |
| R4 | coverage boundaries、scene journey、scene product readiness | scene release gate 相关，应单独验收 | `scripts/verify_scene_matrix_release_gate.py` |
| R5 | parameter ownership、control contracts | 出错影响 release evidence，最后拆 | `tests/test_scene_parameter_ownership.py`、`tests/test_execution_diagnostics_reporting.py` |

### 4.4 report_writer 验收命令

每个 report section 切片至少执行:

```powershell
python -m pytest -q tests/test_execution_diagnostics_reporting.py
python -m pytest -q tests/test_count_engine_semantics.py tests/test_output_runtime_semantics.py
python scripts\engineering_gate.py
```

涉及 scene release evidence 时追加:

```powershell
python scripts\verify_scene_matrix_release_gate.py
```

完成 R1-R5 后目标:

- `src/report_writer.py` 降到 2500 行以下。
- 新增 section 模块不依赖 UI。
- `write_json_report()` 和 `write_markdown_report()` 签名不变。

## 5. P2: WorkbenchExecutionAdapter 继续拆分方案

### 5.1 当前结构判断

`src/ui/adapters/workbench_execution_adapter.py` 目前仍承接:

- `WorkbenchExecutionAdapter` 主状态构建。
- `WorkbenchIssueItem` / `WorkbenchIssueQueueSummary` 等 issue 数据结构。
- issue action visual / evidence line projection。
- material readiness issue items。
- material asset comparison issue items。
- object preflight issue items。
- output target preflight issue items。
- execution diagnostic issue items。
- batch execution issue items。
- question figure repair / transaction issue items。
- coverage / sample fixture / parameter ownership / control contract issue items。

这些都是 adapter 语义，但不必都放在一个文件。

### 5.2 推荐目标结构

建议保持 `src/ui/adapters/` 目录，不引入 UI widget 依赖。

```text
src/ui/adapters/
  workbench_execution_adapter.py
  workbench_issue_models.py
  workbench_issue_visuals.py
  workbench_issue_evidence.py
  workbench_material_issues.py
  workbench_preflight_issues.py
  workbench_batch_issues.py
  workbench_question_figure_issues.py
  workbench_scene_release_issues.py
```

拆分原则:

- model/dataclass 先搬，保持 import re-export。
- visual/evidence projection 次之。
- issue family 构建函数按领域搬。
- `WorkbenchExecutionAdapter` 最后只负责组合状态，不直接承载所有 issue family 细节。

### 5.3 推荐切片顺序

| 切片 | 新模块 | 搬迁内容 | 推荐测试 |
| --- | --- | --- | --- |
| W1 | `workbench_issue_models.py` | `MaterialReadinessIssueGroups`、`WorkbenchIssueItem`、`WorkbenchIssueQueueSummary`、visual/evidence dataclass | `tests/test_workbench_execution_center.py` |
| W2 | `workbench_issue_visuals.py` / `workbench_issue_evidence.py` | action group、action visual、evidence line/body text | `tests/test_quick_execution_detail_architecture.py` |
| W3 | `workbench_material_issues.py` | material readiness、asset comparison、source note helper | `tests/test_workbench_execution_center.py`、`tests/test_scene_repair_routing.py` |
| W4 | `workbench_preflight_issues.py` | object preflight、output target、diagnostic issue items | `tests/test_object_preflight_semantics.py`、`tests/test_execution_diagnostics_reporting.py` |
| W5 | `workbench_batch_issues.py` | batch execution issue items | `tests/test_material_execution_context.py` |
| W6 | `workbench_question_figure_issues.py` | question figure repair queue、transaction task issue items | `tests/test_quick_execution_detail_architecture.py` |
| W7 | `workbench_scene_release_issues.py` | coverage boundary、sample fixture、parameter ownership、control contract issue items | `scripts/verify_scene_matrix_release_gate.py` |

第一轮只建议执行 W1 或 W2。W1 最稳，因为主要搬 dataclass 和类型，不改变构建逻辑。

### 5.4 Workbench adapter 验收命令

每个 adapter 切片至少执行:

```powershell
python -m pytest -q tests/test_workbench_execution_center.py tests/test_quick_execution_detail_architecture.py
python scripts\engineering_gate.py
```

涉及 scene release issue family 时追加:

```powershell
python scripts\verify_scene_matrix_release_gate.py
```

完成 W1-W7 后目标:

- `workbench_execution_adapter.py` 降到 2200 行以下。
- issue family 新增测试文件或迁移现有测试断言。
- `WorkbenchExecutionAdapter` 外部导入路径不变。

## 6. P3: CI 依赖口径完善方案

### 6.1 已完成基线

已完成:

- `.github/workflows/engineering-gate.yml` 使用 `python -m pip install -e ".[dev]"`。
- `.github/workflows/scene-matrix-release-gate.yml` 已改为 `python -m pip install -e ".[dev]"`。
- `pyproject.toml` 已声明 runtime 依赖和 dev 依赖。

### 6.2 后续防回归项

建议新增一个轻量测试，防止 workflow 重新手写依赖:

- 在 `tests/test_release_shell.py` 或新增 `tests/test_ci_workflow_policy.py` 中检查:
  - `.github/workflows/engineering-gate.yml` 包含 `pip install -e ".[dev]"`。
  - `.github/workflows/scene-matrix-release-gate.yml` 包含 `pip install -e ".[dev]"`。
  - workflow 不再出现 `pip install python-docx lxml PyYAML pytest` 这类手写 runtime 依赖组合。

建议后续再增加一个本地命令:

```powershell
python scripts\engineering_gate.py
python scripts\verify_scene_matrix_release_gate.py
python scripts\check_public_release.py --strict
```

这三条作为 release 前最小确认，不强制把全量 `pytest -q` 放进每次本地小切片。

## 7. 推荐执行顺序

推荐从低风险到高收益执行:

1. CI workflow 防回归测试。
2. ScenePanel S1: 导航 projection 拆分。
3. Workbench W1: issue model/dataclass 拆分。
4. report_writer R1: official numbering / technical chapter / application word limits section 拆分。
5. ScenePanel S2-S4: selector、request cell、sample fixture projection 拆分。
6. Workbench W2-W4: visual/evidence/material/preflight issue family 拆分。
7. report_writer R2-R5: exam/material/object/scene release/ownership section 拆分。

## 8. 每轮提交模板

每轮建议提交信息:

```text
Extract <domain> <boundary>
```

例如:

- `Extract scene navigation projection`
- `Extract workbench issue models`
- `Extract report official numbering section`
- `Guard CI workflow dependency profile`

每轮提交前检查:

```powershell
git diff --check
python scripts\check_public_release.py --strict
python scripts\engineering_gate.py
```

如果触及 scene release 或 report evidence:

```powershell
python scripts\verify_scene_matrix_release_gate.py
```

## 9. 停止条件

遇到以下情况应停止当前切片，改为记录风险而不是继续扩大改动:

- 需要改公共函数签名。
- 需要同时迁移 UI widget 生命周期和业务投影。
- 需要改多个测试族才能解释一个简单搬迁。
- 新模块出现反向依赖 UI widget，导致 adapter/reporting 层边界变差。
- 聚焦测试无法在 1 次小修内恢复。

## 10. 完成度目标

短期目标:

- `scene_panel.py` 降到 5200 行以下。
- `workbench_execution_adapter.py` 降到 2600 行以下。
- `report_writer.py` 降到 3000 行以下。
- CI workflow dependency profile 有测试守门。

中期目标:

- `scene_panel.py` 降到 4500 行以下。
- `workbench_execution_adapter.py` 降到 2200 行以下。
- `report_writer.py` 降到 2500 行以下。
- 大测试文件按新模块边界拆出 2-3 个聚焦测试文件。

## 11. 执行进展

### 2026-07-09 本轮推进

已完成:

- CI workflow dependency profile 防回归测试:
  - `tests/test_release_shell.py` 已检查 `engineering-gate.yml` 和 `scene-matrix-release-gate.yml` 均使用 `python -m pip install -e ".[dev]"`。
  - 测试同时防止 scene matrix workflow 退回 `python-docx lxml PyYAML pytest` 这类手写依赖组合。
- ScenePanel S1 首片:
  - 新增 `src/ui/panels/scene_navigation_projection.py`。
  - 已迁出 `_normalise_scene_detail_card_id`、导航别名、scope mode label、输出字段集合、导航 subtitle 拼接和输入格式摘要纯函数。
  - `scene_panel.py` 继续 import 原函数名，调用点不变。
  - `tests/test_scene_panel_architecture.py` 已改为检查职责归属在新模块。
- Workbench W1 首片:
  - 新增 `src/ui/adapters/workbench_issue_models.py`。
  - 已迁出 `MaterialReadinessIssueGroups`、`WorkbenchIssueItem`、`WorkbenchIssueQueueSummary`、`WorkbenchIssueActionVisualProjection`、`WorkbenchIssueEvidenceLineProjection` 和 issue status/action group 常量。
  - `workbench_execution_adapter.py` 继续 import 并 re-export 这些名字，外部导入路径不变。
  - `tests/test_workbench_execution_center.py` 已增加模型归属守门。
- report_writer R1 首片:
  - 新增 `src/reporting/document_sections.py`。
  - 已迁出 official numbering、technical chapter、application section word limits 三组无副作用 extractor/formatter。
  - `report_writer.py` 继续 import 原函数名，`write_json_report` / `write_markdown_report` 输出入口不变。
  - `tests/test_execution_diagnostics_reporting.py` 已增加 section 归属守门。
  - `report_writer.py` 已降至 2917 行，短期目标 3000 行以下已达成。
- report_writer R2:
  - 新增 `src/reporting/exam_sections.py`。
  - 已迁出 `exam_question_schema` 和 `exam_delivery_runtime` 两组 extractor/formatter 及清洗 helper。
  - 新增 exam section 归属守门，并补齐 `exam_delivery_runtime` JSON/Markdown 输出回归测试。
  - `report_writer.py` 已降至 2629 行，距离中期目标 2500 行以下还差约 130 行。
- report_writer R3:
  - 新增 `src/reporting/material_sections.py`。
  - 已迁出 material field consistency、object preflight、coverage boundaries 三组 extractor/formatter 及清洗 helper。
  - `plugin.manual_gate` 控件契约 evidence path 已从 `src/report_writer.py` 同步到 `src/reporting/material_sections.py`。
  - `tests/test_execution_diagnostics_reporting.py` 已增加 material section 归属守门。
  - `report_writer.py` 已降至 2271 行，中期目标 2500 行以下已达成。
- Workbench W2:
  - 新增 `src/ui/adapters/workbench_issue_projection.py`。
  - 已迁出 issue action visual、evidence line、display text/source note 投影和 coverage/boundary 展示映射。
  - `workbench_execution_adapter.py` 继续 import 并 re-export 原函数名，外部导入路径不变。
  - `tests/test_workbench_execution_center.py` 已增加 projection 归属守门。
  - `workbench_execution_adapter.py` 已降至 2585 行，短期目标 2600 行以下已达成。
- ScenePanel S1.2:
  - `src/ui/panels/scene_navigation_projection.py` 扩展为导航卡片 snapshot builder。
  - `ScenePanel._navigation_card_snapshots()` 保持兼容入口，只负责传入 scene label、dirty、当前模板、delivery preset 和 exam paper config。
  - 已迁出 overview/rules/content/exam/cleanup/output 等导航 snapshot 纯投影。
  - 同步修复因 report section 拆分造成的 release source evidence 路径: fixed-layout、import handoff、control runtime、object preflight、plugin boundary 均指向新 reporting section 模块。
  - `scene_panel.py` 已降至 5742 行。

验证:

```powershell
python -m pytest -q tests/test_release_shell.py tests/test_scene_panel_architecture.py tests/test_workbench_issue_navigation.py
# 93 passed

python scripts\check_public_release.py --strict
# [OK] No obvious public-release blockers were found.

python scripts\engineering_gate.py
# Engineering gate passed; 1871 tests collected; smoke 10 passed.

python -m pytest -q tests/test_workbench_execution_center.py tests/test_quick_execution_detail_architecture.py tests/test_scene_repair_routing.py tests/test_workbench_issue_navigation.py
# 139 passed

python -m pytest -q tests/test_execution_diagnostics_reporting.py tests/test_count_engine_semantics.py tests/test_output_runtime_semantics.py
# 61 passed

python -m pytest -q tests/test_release_shell.py tests/test_execution_diagnostics_reporting.py tests/test_count_engine_semantics.py tests/test_output_runtime_semantics.py
# 72 passed

python scripts\check_public_release.py --strict
# [OK] No obvious public-release blockers were found.

python scripts\engineering_gate.py
# Engineering gate passed; 1873 tests collected; smoke 10 passed.

python -m pytest -q tests/test_execution_diagnostics_reporting.py tests/test_count_engine_semantics.py tests/test_output_runtime_semantics.py
# 63 passed

python -m pytest -q tests/test_release_shell.py tests/test_execution_diagnostics_reporting.py tests/test_count_engine_semantics.py tests/test_output_runtime_semantics.py
# 74 passed

python scripts\check_public_release.py --strict
# [OK] No obvious public-release blockers were found.

python scripts\engineering_gate.py
# Engineering gate passed; 1875 tests collected; smoke 10 passed.

python -m pytest -q tests/test_execution_diagnostics_reporting.py tests/test_count_engine_semantics.py tests/test_output_runtime_semantics.py
# 64 passed

python -m pytest -q tests/test_release_shell.py tests/test_execution_diagnostics_reporting.py tests/test_count_engine_semantics.py tests/test_output_runtime_semantics.py
# 75 passed

python scripts\check_public_release.py --strict
# [OK] No obvious public-release blockers were found.

python scripts\engineering_gate.py
# Engineering gate passed; 1876 tests collected; smoke 10 passed.

python -m pytest -q tests/test_workbench_execution_center.py tests/test_quick_execution_detail_architecture.py tests/test_scene_repair_routing.py tests/test_workbench_issue_navigation.py
# 141 passed

python scripts\check_public_release.py --strict
# [OK] No obvious public-release blockers were found.

python scripts\engineering_gate.py
# Engineering gate passed; 1877 tests collected; smoke 10 passed.

python -m pytest -q tests/test_scene_panel_architecture.py tests/test_scene_repair_routing.py tests/test_quick_execution_detail_architecture.py
# 119 passed

python -m pytest -q tests/test_scene_fixed_layout_profile_audit.py tests/test_execution_diagnostics_reporting.py tests/test_control_contract_registry.py
# 40 passed

python scripts\verify_scene_matrix_release_gate.py
# Scene matrix release gate: passed

python scripts\check_public_release.py --strict
# [OK] No obvious public-release blockers were found.

python scripts\engineering_gate.py
# Engineering gate passed; 1877 tests collected; smoke 10 passed.
```

下一步:

1. 继续 ScenePanel S2: 评估 selector / request-cell / sample fixture projection 是否能按相同方式拆出。
2. 按推荐顺序进入 Workbench W3 或 report_writer R4: 继续拆无副作用 formatter / evidence projection，避免一次触碰执行副作用和 UI 生命周期。
