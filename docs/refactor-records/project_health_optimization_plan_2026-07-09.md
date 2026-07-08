# Project Health Optimization Plan

记录日期: 2026-07-09

项目路径: `C:\Users\70768\Desktop\Lark-Formatter 1.0\Lark-Formatter V1.0`

## 1. 结论摘要

当前项目不是失控状态，核心能力、测试意识和场景治理基础都较强；但当前工作区不适合直接作为发布基线。

综合判断:

- 运行健康: 8/10
- 测试健康: 7.5/10
- 架构健康: 6/10
- 发布健康: 5/10

总体状态: 可持续开发中，但需要先修交付红线，再收束变更面，最后按热点做渐进式结构治理。

## 2. 当前证据

### 2.1 正向信号

- `scripts/engineering_gate.py` 通过。
- `compileall` 可通过，`src` 与 `main.py` 无基础语法崩坏。
- 测试可完整收集到 `1870` 个用例。
- 全量测试结果为 `1868 passed, 2 failed`，失败集中在环境依赖和发布卫生。
- `scripts/verify_scene_matrix_release_gate.py` 通过，场景矩阵发布门禁全绿。
- 未发现大面积 `pytest.mark.skip` / `pytest.mark.xfail`。
- `.gitignore` 与 `.gitattributes` 已覆盖日志、构建产物、临时目录和主要换行策略。

### 2.2 风险信号

- 当前工作区存在大量未提交改动: `118` 个修改文件，`21` 个未跟踪文件。
- 当前 tracked diff 约为 `5041 insertions(+), 13008 deletions(-)`。
- `src` 约 `451` 个 Python 文件，约 `162k` 行。
- `src` 中超过 1000 行的 Python 文件约 `39` 个。
- `config`、`ui`、`shared` 是主要体量集中区。
- 严格公开发布扫描失败，主要因为 `.venv`、`build`、`dist`、`.spec`、运行日志等本地产物仍在工作区。
- 全量测试失败项之一说明 `openpyxl` 被代码使用但没有声明为项目依赖。

## 3. 优化原则

本轮优化不建议直接做大规模重构。合理顺序应为:

1. 先让交付基线全绿。
2. 再拆分和归档当前大变更。
3. 然后补轻量质量门禁，防止回退。
4. 最后按热点文件做小切片重构。

判断依据:

- 当前项目仍能编译、收集测试并通过绝大多数测试，说明不需要推倒重来。
- 当前最大风险来自发布卫生、依赖声明和工作区变更规模。
- 大文件问题真实存在，但如果在工作区未收束前启动大重构，会放大合并和回归成本。

## 4. 阶段计划

### Phase 1: 修复交付红线

目标周期: 半天内。

任务:

- 在 `pyproject.toml` 与 `requirements.txt` 中补充 `openpyxl` 依赖。
- 清理根目录运行日志，例如 `alavette_form.log`。
- 清理本地构建产物，例如 `build/`、`dist/`、`*.spec`。
- 重新运行公开发布扫描。

验收命令:

```powershell
.\.venv\Scripts\python.exe scripts\engineering_gate.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_public_release.py --strict
.\.venv\Scripts\python.exe scripts\verify_scene_matrix_release_gate.py
```

完成标准:

- 基础工程门禁通过。
- 全量测试通过。
- 严格公开发布扫描通过。
- 场景矩阵发布门禁通过。

### Phase 2: 收束当前工作区

目标周期: 1 天内。

任务:

- 将当前大变更拆分为小主题提交或小主题变更集。
- 推荐分组:
  - 发布与打包依赖调整
  - 场景矩阵治理与 release gate 调整
  - UI 小组件一致性调整
  - 测试拆分与辅助断言抽取
  - 文档与审计记录
- 每组变更单独运行关联测试。
- 避免把文档、测试、发布脚本和核心代码混在一个不可回滚的大变更里。

完成标准:

- `git status` 可读、可审查。
- 每个主题变更能独立解释目标和验证结果。
- 主线可随时回到全绿状态。

### Phase 3: 增加轻量质量门禁

目标周期: 1 到 2 天。

任务:

- 引入 `ruff` 作为最小静态检查工具。
- 初期只启用低争议规则，例如语法错误、未使用导入、重复定义、明显不可达代码。
- 暂不强制全量 `mypy` 或 `pyright`。
- 可先在 CI 增加一个快速 lint job，或接入现有 `engineering-gate.yml`。

完成标准:

- 本地和 CI 都能运行同一套最小静态检查。
- 新增代码不能引入明显静态错误。
- 不因历史存量问题阻断正常开发。

### Phase 4: 大文件小切片治理

目标周期: 持续执行，每轮只处理一个边界。

优先候选:

- `src/ui/panels/scene_panel.py`
- `src/report_writer.py`
- `src/config/scene_matrix_dashboard.py`
- `src/ui/adapters/workbench_execution_adapter.py`
- `src/shared/engine/exam_paper_style.py`

治理方式:

- 优先抽取纯数据模型、投影函数、presenter、builder、导出器等低副作用边界。
- 每次重构保持外部行为不变。
- 不把风格清理、命名调整和行为重构混在同一轮。
- 每轮保留对应测试或新增回归测试。

完成标准:

- 单个大文件行数下降，且职责边界更清楚。
- 调用方行为不变。
- 对应测试通过。
- 文档记录本轮拆分前后的边界变化。

### Phase 5: 依赖方向和分层收口

目标周期: 持续执行。

目标方向:

- `config` 层只保留数据、规则、审计和投影，不依赖 UI。
- UI 层消费投影结果，不反向承载核心规则。
- `shared` 只承载真实跨域复用能力，避免成为无边界公共仓库。
- PySide6 使用尽量经由 `src/qt_api.py` 统一入口；确需直连 Qt 的地方保留明确白名单和测试说明。

完成标准:

- 新增 `config` 模块不引入 UI 依赖。
- 新增 UI 模块不复制核心业务规则。
- 关键跨层依赖有测试或架构检查覆盖。

## 5. 推荐优先级

P0:

- 补 `openpyxl` 依赖声明。
- 清理发布扫描阻断项。
- 跑通全量测试与严格发布扫描。

P1:

- 拆分当前工作区大变更。
- 将测试辅助断言和场景矩阵门禁相关改动整理为可审查单元。
- 引入最小 `ruff` 门禁。

P2:

- 从 `scene_panel.py` 或 `report_writer.py` 选择一个文件做第一轮小切片重构。
- 收口少量直接 `PySide6` import 的例外边界。
- 扩展编码护栏，逐步覆盖文档与非 Python 源文件中的乱码风险。

P3:

- 分模块推进类型标注和类型检查。
- 建立覆盖率基线，但不要一开始强推高覆盖率阈值。
- 为发布包增加更细的二进制产物检查。

## 6. 风险与控制

### 风险 1: 在工作区未收束前启动大重构

影响:

- 变更难审查。
- 回归定位困难。
- 容易把发布修复、架构调整和测试迁移混在一起。

控制:

- 先完成 P0。
- 每轮重构只处理一个明确边界。
- 每个主题变更都有独立验证命令。

### 风险 2: 静态门禁一次性过严

影响:

- 历史问题会阻塞正常开发。
- 团队可能绕过门禁。

控制:

- 先启用低争议规则。
- 对历史问题使用分阶段清单。
- 新代码先受约束，旧代码逐步纳入。

### 风险 3: `shared` 继续膨胀

影响:

- 公共模块边界模糊。
- 复用变成耦合入口。

控制:

- 新增 shared 能力前确认至少两个真实调用方。
- 对跨域 helper 保持小 API。
- 业务规则优先留在领域模块或服务层。

## 7. 验收清单

短期验收:

- [ ] `openpyxl` 已声明。
- [ ] `alavette_form.log` 等本地日志已清理。
- [ ] `build/`、`dist/`、`*.spec` 等发布阻断项已处理。
- [ ] `engineering_gate` 通过。
- [ ] 全量测试通过。
- [ ] `check_public_release.py --strict` 通过。
- [ ] `verify_scene_matrix_release_gate.py` 通过。

中期验收:

- [x] 当前大变更已按主题拆分。
- [x] CI 增加最小静态检查。
- [x] 至少完成一个大文件的小切片拆分。
- [x] 新增结构健康记录，记录拆分前后边界。

长期验收:

- [ ] `config`、`ui`、`shared` 的依赖方向有稳定约束。
- [ ] 大文件数量持续下降。
- [ ] 发布检查、工程门禁、场景门禁形成固定发布路径。
- [ ] 文档、审计记录和代码实现保持同步。

## 8. 下一步建议

建议下一步直接执行 P0:

1. 补充 `openpyxl` 依赖声明。
2. 清理本地发布阻断产物。
3. 重新运行四组验收命令。

P0 完成后，再进入 Phase 2 拆分当前工作区改动。这样能最快把项目从“可运行但不适合发布”推进到“可审查、可发布、可继续治理”的状态。

## 9. 跟进提交与隔离清理盘点

补充盘点日期: 2026-07-09

### 9.1 已有跟进提交

当前分支: `codex/code-structure-health-staging`

近期提交已经围绕场景矩阵发布治理做过连续跟进，例如:

- `61bd761 Extract release governance report context`
- `918e620 Extract early scene release gate reports`
- `70e0568 Extract dashboard residual release gate reports`
- `83efa64 Extract material delivery release gate reports`
- `2148f86 Extract release governance evidence gate`
- `02a1f69 Extract scene release gate foundation checks`
- `38ffdb2 Split scene matrix release gate payload builder`

判断:

- 已有提交方向是合理的，属于把超大 release gate payload 拆成可维护报告上下文、证据门禁和基础检查。
- 当前剩余问题不是没有跟进提交，而是工作区仍有大量未提交变更，需要继续按主题收口。

### 9.2 当前未提交变更建议拆分

建议后续至少拆成以下提交或变更集:

1. 发布与依赖修复
   - `pyproject.toml`
   - `requirements.txt`
   - `README.md`
   - `docs/OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md`
   - `scripts/windows/package_release.bat`
   - `tests/test_release_shell.py`

2. 场景发布治理注册表与证据源
   - `src/config/scene_release_governance_registry.py`
   - `src/config/scene_source_evidence.py`
   - `tests/test_scene_matrix_dashboard_release_governance_registry.py`
   - `tests/test_scene_matrix_drilldown_release_governance_registry.py`
   - `tests/test_scene_source_evidence.py`

3. 场景矩阵 dashboard / drilldown 测试拆分
   - `tests/_scene_matrix_dashboard_assertions.py`
   - `tests/_scene_matrix_drilldown_projection_references.py`
   - `tests/test_scene_matrix_dashboard_aggregate.py`
   - `tests/test_scene_matrix_dashboard_export.py`
   - `tests/test_scene_matrix_dashboard_release_gate_payload.py`
   - `tests/test_scene_matrix_dashboard_summary.py`
   - `tests/test_scene_matrix_drilldown_audit.py`
   - `tests/test_scene_matrix_drilldown_behavior.py`
   - `tests/test_scene_matrix_drilldown_frontend_sources.py`
   - `tests/test_scene_matrix_drilldown_source_markers.py`
   - `tests/test_scene_matrix_release_workflow.py`

4. 审计导出脚本收口
   - `scripts/export_scene_audit.py`
   - `scripts/export_scene_*_audit.py`
   - `scripts/scene_matrix_release_gate_payload.py`
   - `scripts/verify_scene_matrix_release_gate.py`

5. UI 与主题小修
   - `src/shared/ui/*`
   - `src/ui/panels/assets/*`
   - `src/ui/panels/scene_panel.py`
   - `src/ui/startup_splash.py`

6. 文档记录
   - `docs/refactor-records/project_health_optimization_plan_2026-07-09.md`
   - `docs/refactor-records/scene_matrix_release_governance_necessity_analysis_2026-07-08.md`

### 9.3 可直接清理候选

以下内容属于本地产物、构建产物或运行日志，已经被 `.gitignore` 或发布扫描口径覆盖。若不需要本地留档，可以删除；若需要留档，应移到明确的本地备份目录，不应进入发布基线。

- `.venv/`
- `.pytest_cache/`
- `build/`
- `dist/`
- `Alavette-Form_V1.0.spec`
- `alavette_form.log`
- `.tmp_gallery_stdout.txt`
- `.tmp_gallery_stderr.txt`
- `out.txt`
- `out2.txt`
- `out3.txt`
- `out4.txt`

删除前注意:

- `.venv/` 删除后需要重新安装依赖。
- `dist/` 与 `build/` 删除后需要重新打包生成。
- 日志和临时输出没有发现被测试或代码引用。

### 9.4 可隔离后再决定是否删除的候选

以下内容不建议直接删除，应先判断是否是正式证据、样本或回归基线。

1. 根目录生成的 `.docx`
   - 这些文件被 `.gitignore` 的 `/*.docx` 规则覆盖。
   - 与 `samples/docx/` 中同名样本不是字节级重复。
   - 建议:
     - 如果它们代表新版样本，应有意识地晋升到 `samples/docx/` 并更新相关 manifest。
     - 如果只是一次生成输出，应移动到本地隔离目录或删除。

2. 根目录报告
   - `manifest.json`
   - `request_cell_report.md`
   - 两者被 `.gitignore` 明确覆盖。
   - 建议:
     - 如果是发布证据，应移动到 `docs/audits/` 或 `docs/refactor-records/` 并保留生成命令。
     - 如果只是脚本运行输出，应删除。

3. 超大未跟踪分析文档
   - `docs/refactor-records/scene_matrix_release_governance_necessity_analysis_2026-07-08.md`
   - 当前约 `8303` 行、`506967` 字节。
   - 建议:
     - 如果要提交，先压缩为摘要版，把细节拆到附录或归档目录。
     - 如果只是推理过程记录，建议隔离，不进入主线文档。

4. 已跟踪的历史测试输出
   - `tests/TEST-1/output*/`
   - 当前 `tests/TEST-1` 下存在大量已跟踪输出文件。
   - `docs/DOCUMENTATION_BOUNDARIES.md` 与 `.gitignore` 都倾向于把测试输出视为生成物。
   - 已执行:
     - 已通过全文检索确认没有源码或测试依赖这些输出目录。
     - 已保留输入样本 `tests/TEST-1/中图分类号.docx`。
     - 已将历史输出文件作为独立清理提交删除。

5. 已跟踪视觉截图
   - `artifacts/*.png`
   - `docs/visual_audit/**`
   - `docs/visual_checks/**`
   - 建议:
     - 保留少量代表性验收图。
     - 旧迭代中间图可归档或删除。
     - 不建议继续让 `artifacts/` 承担长期文档职责。

### 9.5 内容级隔离候选

以下属于内容治理问题，不应和功能提交混在一起处理:

- 历史审计文档中可能存在编码异常或 mojibake 标记。
- 部分超长审计记录更像过程日志，不像可长期维护的产品文档。
- 建议建立 `docs/archive/` 或 `docs/refactor-records/archive/`，把仅供追溯的历史过程记录隔离。
- 对仍有决策价值的文档保留摘要版，详细流水进入归档。

### 9.6 推荐清理顺序

1. 先删除或隔离本地生成物，确保 `check_public_release.py --strict` 不再被本地文件阻断。
2. 再处理 `openpyxl` 依赖，跑通全量测试。
3. 然后按 9.2 拆分未提交变更。
4. 最后单独开一轮“历史生成物清理”提交，处理 `tests/TEST-1/output*/`、旧截图和超大过程文档。

本轮已按独立提交口径处理 `tests/TEST-1/output*/` 这类 tracked 历史生成物；后续旧截图和超大过程文档仍应继续按独立提交治理。

## 10. 执行进展记录

更新日期: 2026-07-09

### 10.1 P0 已完成

已完成事项:

- `pyproject.toml` 已补充 `openpyxl>=3.1.0`。
- `requirements.txt` 已补充 `openpyxl>=3.1.0`。
- 根目录运行日志、临时输出和构建产物已清理。
- 仓库内 `.venv/` 已清理，避免严格公开发布扫描被本地虚拟环境阻断。
- 根目录生成的 `.docx`、`manifest.json`、`request_cell_report.md` 已隔离到 `artifacts/isolation/2026-07-09-root-generated/`。

验证结果:

```powershell
# 仓库内 .venv 清理前执行
.\.venv\Scripts\python.exe scripts\engineering_gate.py
# passed

.\.venv\Scripts\python.exe -m pytest -q
# 1870 passed

.\.venv\Scripts\python.exe scripts\verify_scene_matrix_release_gate.py
# passed

# 仓库内 .venv 清理后执行
python scripts\check_public_release.py --strict
# [OK] No obvious public-release blockers were found.
```

### 10.2 最小静态门禁已接入

已完成事项:

- `ruff>=0.8.0` 已加入 `dev` 依赖。
- `scripts/engineering_gate.py` 已加入最小 `ruff` 检查。
- 规则范围限定为 `E9,F63,F7,F82`，用于捕获语法错误、明显未定义引用等低争议问题。
- 修复了最小门禁发现的 7 个问题:
  - `src/config/loader.py` 增加 `TYPE_CHECKING` 类型导入。
  - `src/shared/engine/chem_marks.py` 增加 `Document` 类型导入。
  - `src/ui/panels/workbench/quick_execution_detail.py` 增加 `build_execution_prereview_style_projection` 顶层导入。

验证结果:

```powershell
# 使用仓库外临时验证环境执行
python scripts\engineering_gate.py
# ruff passed
# compileall passed
# 1870 tests collected
# 10 smoke tests passed

python -m pytest -q
# 1870 passed

python scripts\verify_scene_matrix_release_gate.py
# passed

python scripts\check_public_release.py --strict
# [OK] No obvious public-release blockers were found.
```

### 10.3 当前剩余治理项

已完成的拆分/隔离:

- 当前大变更已拆成多个独立 Git 提交，功能、文档、UI、资产文案、历史生成物清理边界已分开。
- `docs/refactor-records/scene_matrix_release_governance_necessity_analysis_2026-07-08.md` 已隔离到 `artifacts/isolation/2026-07-09-docs/`，不进入主线文档。
- 根目录生成 `.docx` 与报告已隔离到 `artifacts/isolation/2026-07-09-root-generated/`。
- `tests/TEST-1/output*/` 等已跟踪历史生成物已确认无测试依赖，并作为独立清理提交删除。

仍需作为长期治理处理:

- 旧视觉截图与历史过程文档仍可继续瘦身。
- 大文件治理需要持续推进后续切片。

下一步建议:

1. 若要继续压缩仓库体积，单独处理旧视觉截图和历史过程文档。
2. 若要继续降低架构风险，选择 `scene_panel.py`、`report_writer.py` 或 `workbench_execution_adapter.py` 做下一轮小切片。
3. 每轮继续保持“独立提交 + 门禁验证”的节奏。
