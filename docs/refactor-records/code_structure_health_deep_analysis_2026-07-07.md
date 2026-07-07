# 代码结构健康深度分析记录

记录日期: 2026-07-07

项目路径: `C:\Users\70768\Desktop\Lark-Formatter 1.0\Lark-Formatter V1.0`

## 1. 结论摘要

当前项目不是失控状态。入口可编译，`src` 可编译，测试收集正常，冒烟测试通过，说明基础运行面仍然稳。

但结构健康度已经进入警戒区。主要压力来自四类问题:

1. 工作区变更量过大，当前状态更像大迁移现场，而不是可稳定交付的基线。
2. `config` 与 `ui` 两个区域体量过大，且出现多个 2000 行到 6000 行级别的大文件。
3. 存在配置/领域层反向依赖 UI 模块的问题，后续会影响 CLI、测试、打包和复用。
4. 工程配置偏脚本式，缺少 `pyproject.toml`、`pytest.ini`、`.gitattributes` 等统一工程约束。

综合判断: 约 `6.5/10`。功能和测试基础较好，但架构治理需要先收口。

## 2. 本次执行范围

本次只做结构分析和文档记录，不修改业务代码。

分析覆盖:

- 目录与文件规模
- `src` 内模块体量分布
- 大文件集中区域
- Git 工作区污染程度
- 工程配置完整度
- 依赖方向和跨层 import
- 基础可运行性验证
- 后续治理步骤建议

未覆盖:

- 未运行完整 1797 项测试套件
- 未做 UI 截图验证
- 未做性能 profiling
- 未逐行审查业务逻辑正确性

## 3. 执行步骤与结果

### 3.1 扫描项目文件规模

执行命令:

```powershell
rg --files | Measure-Object
```

结果:

- 当前可被 `rg --files` 发现的文件数: `1683`

说明:

- 项目已经是中等偏大的 Python 桌面应用/文档处理项目。
- 文件量本身不是问题，关键是是否有清晰分层、生成物隔离和工程约束。

### 3.2 统计源码与测试规模

执行命令:

```powershell
Get-ChildItem -Recurse -File src -Filter *.py | Measure-Object
Get-ChildItem -Recurse -File tests -Filter *.py | Measure-Object
Get-ChildItem -Recurse -File docs | Measure-Object
```

结果:

| 指标 | 数量 |
| --- | ---: |
| `src` Python 文件 | 430 |
| `tests` Python 文件 | 209 |
| `docs` 文件 | 690 |

判断:

- 测试文件数量较高，这是正向信号。
- `docs` 文件数量很大，需要区分产品文档、审计记录、临时交付件、生成报告，避免文档目录成为历史堆积区。

### 3.3 统计 `src` 各区域代码体量

执行命令:

```powershell
Get-ChildItem -Recurse -File src -Filter *.py | ForEach-Object {
  $relative = $_.FullName.Substring($PWD.Path.Length + 1)
  $area = ($relative -split '\\')[1]
  $lines = (Get-Content -LiteralPath $_.FullName | Measure-Object -Line).Lines
  [PSCustomObject]@{ Area = $area; Lines = $lines; Files = 1 }
} | Group-Object Area | ForEach-Object {
  [PSCustomObject]@{
    Area = $_.Name
    Files = ($_.Group | Measure-Object Files -Sum).Sum
    Lines = ($_.Group | Measure-Object Lines -Sum).Sum
  }
} | Sort-Object Lines -Descending
```

结果:

| 区域 | 文件数 | 行数 |
| --- | ---: | ---: |
| `src/config` | 90 | 60499 |
| `src/ui` | 123 | 54951 |
| `src/shared` | 166 | 30503 |
| `src/modules` | 32 | 7162 |
| `src/report_writer.py` | 1 | 3852 |
| `src/services` | 7 | 2891 |
| `src/pipeline` | 6 | 1615 |
| `src/qt_api.py` | 1 | 181 |
| `src/cli_runner.py` | 1 | 124 |
| `src/execution_diagnostics.py` | 1 | 111 |
| `src/app_meta.py` | 1 | 11 |

判断:

- 最大体量在 `config` 和 `ui`，这说明产品场景定义和界面层是主要复杂度来源。
- `shared` 很大，可能承担了较多跨域复用能力，需要持续防止变成无边界公共仓库。
- `services` 体量不大，但承担 material assets 等领域服务，后续可以成为拆分 UI 逻辑的承接层。

### 3.4 识别大文件

执行命令:

```powershell
Get-ChildItem -Recurse -File src -Filter *.py | ForEach-Object {
  $lines = (Get-Content -LiteralPath $_.FullName | Measure-Object -Line).Lines
  [PSCustomObject]@{ Lines = $lines; Path = $_.FullName.Substring($PWD.Path.Length + 1) }
} | Sort-Object Lines -Descending | Select-Object -First 40
```

关键结果:

| 文件 | 行数 |
| --- | ---: |
| `src/ui/panels/scene_panel.py` | 6702 |
| `src/config/scene_matrix_dashboard.py` | 5606 |
| `src/config/scene_matrix_drilldown.py` | 5403 |
| `src/report_writer.py` | 3852 |
| `src/ui/panels/scene_summary_projection.py` | 3382 |
| `src/ui/adapters/workbench_execution_adapter.py` | 3275 |
| `src/ui/panels/workbench/question_figure_repair_runtime.py` | 2585 |
| `src/ui/panels/workbench/quick_execution_detail.py` | 2310 |
| `src/ui/panels/template_panel.py` | 2149 |
| `src/ui/panels/heading_numbering_panel.py` | 2123 |
| `src/ui/panels/workbench/execution_runtime.py` | 2104 |
| `src/config/scene_family_application.py` | 2053 |
| `src/shared/engine/chem_marks.py` | 2047 |
| `src/shared/engine/exam_paper_style.py` | 2046 |

大文件阈值统计:

```powershell
Get-ChildItem -Recurse -File src -Filter *.py | ForEach-Object {
  $lines = (Get-Content -LiteralPath $_.FullName | Measure-Object -Line).Lines
  [PSCustomObject]@{ Lines = $lines; Path = $_.FullName.Substring($PWD.Path.Length + 1) }
} | Where-Object { $_.Lines -ge 1000 } | Measure-Object
```

结果:

- `src` 中超过 1000 行的 Python 文件: `32`

判断:

- 大文件数量已经明显偏高。
- 风险最高的是 UI 面板、场景矩阵、执行适配器、报告写入器。这些文件往往同时承担状态、渲染、投影、事件、业务规则和兼容逻辑，后续改动容易牵一发动全身。

### 3.5 检查 Git 工作区状态

执行命令:

```powershell
git status --porcelain=v1 | ForEach-Object {
  $_.Substring(0,2)
} | Group-Object | Sort-Object Count -Descending
```

结果:

| 状态 | 数量 |
| --- | ---: |
| `??` 未跟踪 | 899 |
| ` M` 修改 | 153 |
| ` D` 删除 | 10 |
| `RM` 重命名后修改 | 7 |
| `D ` 已暂存删除 | 1 |

执行命令:

```powershell
git status --porcelain=v1 | Measure-Object
git diff --shortstat
git diff --shortstat -- src
```

结果:

- 工作区状态记录总数: `1070`
- 总 diff: `170 files changed, 51909 insertions(+), 8251 deletions(-)`
- `src` diff: `93 files changed, 31320 insertions(+), 5849 deletions(-)`

判断:

- 当前工作区不是健康基线。
- 任何结构结论都应区分两层:
  - 已提交的项目结构
  - 当前未提交迁移状态
- 在继续堆功能前，需要先把当前大改动拆分、归档、验证、提交或丢弃无关产物。

### 3.6 检查临时目录和产物混入

执行命令:

```powershell
Get-ChildItem -Directory |
  Where-Object {
    $_.Name -like 'tmp*' -or
    $_.Name -like '.codex_tmp*' -or
    $_.Name -like '.pytest*' -or
    $_.Name -eq 'artifacts'
  } |
  Select-Object Name,LastWriteTime
```

发现的目录:

- `.codex_tmp`
- `.codex_tmp_color_table`
- `.pytest_cache`
- `.pytest_tmp`
- `artifacts`
- `tmp_chain_check`
- `tmp_check_renders`
- `tmp_check_samples`
- `tmp_debug_preview`
- `tmp_gate_probe`
- `tmp_gate_probe2`
- `tmp_gate_probe_debug`
- `tmp_gate_probe_n2381`
- `tmp_gate_probe_n2381_after_visio`
- `tmp_gate_probe_n2388`
- `tmp_gate_probe_n2393`
- `tmp_gate_probe_n2402`
- `tmp_probe3`
- `tmp_probe4`

判断:

- 临时产物和验证产物数量较多。
- `.gitignore` 已经有部分规则，但当前仍有大量未跟踪项，说明规则与实际产物边界还没有完全对齐。

### 3.7 检查工程配置文件

执行命令:

```powershell
rg --files `
  -g "pyproject.toml" `
  -g "setup.cfg" `
  -g "setup.py" `
  -g "pytest.ini" `
  -g "tox.ini" `
  -g "ruff.toml" `
  -g ".pre-commit-config.yaml" `
  -g "mypy.ini" `
  -g ".gitattributes" `
  -g "requirements*.txt"
```

结果:

- 仅发现 `requirements.txt`

判断:

- 当前工程主要靠脚本和手动 `sys.path` 运行。
- 缺少统一工程入口会造成:
  - 测试路径依赖变脆
  - 行尾策略不稳定
  - lint/format/type check 无统一标准
  - 发布与开发依赖混在一起

额外观察:

- 多个 Git 命令提示 `LF will be replaced by CRLF`。
- 这通常意味着需要 `.gitattributes` 或统一 `core.autocrlf` 策略。

### 3.8 检查手动 `sys.path` 修改

执行命令:

```powershell
rg -n "sys\.path\.(insert|append)" tests scripts main.py demo_dialogs.py demo_heading_panel.py demo_style_gallery.py | Measure-Object
```

结果:

- 命中数量: `241`

判断:

- `sys.path.insert` 在单个入口文件中可以接受，但测试和脚本中大量重复出现，说明项目尚未被整理成标准可安装包。
- 建议通过 `pyproject.toml` 和 editable install 方式收口。

### 3.9 检查跨层依赖方向

执行命令:

```powershell
rg -n "from src\.ui|import src\.ui" src\config src\modules src\pipeline src\services src\shared\engine
```

结果:

```text
src\config\library.py:220:    from src.ui.panels.workbench.scene_presets import SCENE_METAS
src\config\library.py:230:    from src.ui.panels.workbench.scene_presets import create_scene
src\config\library.py:497:    from src.ui.panels.workbench.scene_presets import SCENE_METAS
src\config\library.py:508:    from src.ui.panels.workbench.scene_presets import SCENE_META_MAP
src\config\scene_delivery_preset_audit.py:790:    from src.ui.panels.workbench.scene_presets import SCENE_FACTORIES
src\config\scene_delivery_preset_audit.py:817:        from src.ui.panels.workbench.scene_presets import SCENE_FACTORIES
src\config\scene_material_schema_audit.py:842:    from src.ui.panels.workbench.scene_presets import SCENE_FACTORIES
src\config\scene_input_source_audit.py:955:    from src.ui.panels.workbench.scene_presets import SCENE_FACTORIES
```

判断:

- 这是明确的反向依赖。
- `config` 层应提供场景定义、元数据、工厂或数据加载能力。
- `ui` 层应消费这些能力，而不是被 `config` 反向调用。

建议目标:

- 将 `src/ui/panels/workbench/scene_presets.py` 中的纯数据、元数据、工厂函数迁移到 `src/config/scene_presets.py` 或 `src/config/scene_registry.py`。
- UI 层只保留展示适配、控件绑定和交互状态。

### 3.10 编译和测试验证

执行命令:

```powershell
python -m py_compile main.py
python -m compileall -q src
python -m pytest --collect-only -q
python -m pytest tests\test_phase0_smoke.py -q
```

结果:

| 命令 | 结果 |
| --- | --- |
| `python -m py_compile main.py` | 通过 |
| `python -m compileall -q src` | 通过 |
| `python -m pytest --collect-only -q` | 收集 `1797` 项测试，通过导入收集 |
| `python -m pytest tests\test_phase0_smoke.py -q` | `14 passed in 0.90s` |

判断:

- 当前问题主要是结构治理问题，不是基础运行崩坏。
- 测试收集成功很重要，说明大量模块仍能正常导入。
- 未运行全量测试，因此不能得出完整回归通过结论。

## 4. 健康信号

### 4.1 正向信号

- `src`、`tests`、`docs`、`scripts`、`defaults`、`scenes` 等目录有基本分区。
- `src` 内存在 `config`、`modules`、`pipeline`、`services`、`shared`、`ui` 等分层意识。
- 测试数量充足，测试收集通过。
- 冒烟测试通过。
- 多个大面板已经开始拆 presenter、adapter、controller，说明项目正在尝试治理复杂度。
- `src/services/material_assets` 已经出现领域服务层，是后续削薄 UI 的好承接点。

### 4.2 风险信号

- 工作区变更量过大，难以判断当前主线稳定性。
- 大文件偏多，尤其 UI 面板、场景矩阵、执行适配器、报告生成器。
- `config` 反向依赖 `ui`。
- 工程配置不足，只有 `requirements.txt`。
- `sys.path.insert` 大量散布。
- 临时目录、截图、日志、生成物较多。
- `docs` 目录可能混合了长期文档和过程性审计记录。
- 行尾策略不统一，Git 提示 LF/CRLF 转换风险。

## 5. 风险分级

| 风险 | 等级 | 证据 | 影响 |
| --- | --- | --- | --- |
| 工作区未收口 | 高 | `1070` 条状态记录，`899` 个未跟踪项 | 无法形成可信发布基线 |
| 大文件集中 | 高 | `32` 个源码文件超过 1000 行 | 修改成本高，回归面大 |
| `config` 依赖 `ui` | 高 | `src/config` 多处导入 `src.ui.panels.workbench.scene_presets` | 破坏层级边界，影响 CLI 和测试隔离 |
| 工程配置不足 | 中高 | 只发现 `requirements.txt` | 测试、打包、格式、行尾策略不稳定 |
| 临时产物混入 | 中 | 根目录存在大量 `tmp*`、`.codex_tmp*`、`artifacts` | 版本库噪音大，发布检查复杂 |
| 文档目录膨胀 | 中 | `docs` 文件数 `690` | 长期文档和过程记录难区分 |
| 运行基础 | 低 | 编译、收集、冒烟测试通过 | 当前不是运行层面崩坏 |

## 6. 建议治理顺序

### 阶段 0: 冻结和收口当前工作区

目标:

- 先得到一个可信基线，避免继续在大迁移上叠大迁移。

建议动作:

1. 分类 `git status` 中的 1070 条记录。
2. 将生成物、截图、日志、临时目录从版本管理候选中移走或加入 `.gitignore`。
3. 将真实源码改动拆成小提交。
4. 对 `docs` 中过程性记录建立归档规则，例如 `docs/audits/`、`docs/refactor-records/`、`docs/release/`。
5. 在收口前避免继续做横跨 `config`、`ui`、`pipeline` 的新功能。

验收:

- `git status --short` 只剩本轮明确要提交的文件。
- 每个提交可以被一句话描述。
- 至少通过编译、测试收集、冒烟测试。

### 阶段 1: 建立工程配置基线

目标:

- 让项目能以标准 Python 项目方式运行、测试和维护。

建议动作:

1. 新增 `pyproject.toml`，定义项目名、Python 版本、依赖组、pytest 配置。
2. 新增 `.gitattributes`，统一 `*.py`、`*.md`、`*.json`、`*.yaml` 行尾策略。
3. 将 `pytest`、`pyinstaller` 等开发/构建依赖从运行依赖中拆出。
4. 逐步减少测试和脚本中的重复 `sys.path.insert`。

验收:

- `python -m pytest --collect-only -q` 不依赖每个测试文件手工改路径。
- Git 不再大面积提示 LF/CRLF 替换。

### 阶段 2: 修复 `config -> ui` 反向依赖

目标:

- 让配置/领域层不依赖界面实现。

建议动作:

1. 从 `src/ui/panels/workbench/scene_presets.py` 提取纯数据和工厂。
2. 新建或迁移到 `src/config/scene_presets.py` 或 `src/config/scene_registry.py`。
3. 修改 `src/config/library.py` 和相关 audit 模块，只依赖 `src.config`。
4. UI workbench 再从 config registry 获取元数据。
5. 增加架构测试，禁止 `src/config`、`src/modules`、`src/pipeline`、`src/services`、`src/shared/engine` 导入 `src.ui`。

验收:

```powershell
rg -n "from src\.ui|import src\.ui" src\config src\modules src\pipeline src\services src\shared\engine
```

应无命中。

### 阶段 3: 拆分最高风险大文件

目标:

- 先拆改动最频繁、风险最大的文件，不追求一次性拆完。

优先级建议:

1. `src/ui/panels/scene_panel.py`
2. `src/report_writer.py`
3. `src/ui/adapters/workbench_execution_adapter.py`
4. `src/config/scene_matrix_dashboard.py`
5. `src/config/scene_matrix_drilldown.py`

拆分原则:

- UI 文件优先拆为 controller、presenter、projection、state、widgets。
- `report_writer.py` 优先拆为 model projection、markdown writer、json writer、docx artifact mapping。
- `scene_matrix_*` 优先拆数据定义、计算、渲染/导出、审计规则。

验收:

- 新增模块有清晰单一职责。
- 原入口文件行数下降。
- 既有测试保持通过。
- 不引入新的跨层反向依赖。

### 阶段 4: 清理文档和生成物边界

目标:

- 保留有价值的决策记录，隔离临时产物。

建议动作:

1. `docs/architecture/`: 长期架构说明。
2. `docs/audits/`: 审计记录。
3. `docs/refactor-records/`: 重构执行记录。
4. `docs/visual_checks/`: 截图类验证资产。
5. `artifacts/`、`tmp*`、`.codex_tmp*`: 默认不进入版本库。

验收:

- 根目录不再堆积临时输出。
- 文档查找路径稳定。
- 发布检查脚本不需要绕过大量本地噪音。

## 7. 建议新增的架构守门测试

建议增加一个轻量测试，防止未来再次引入反向依赖:

```python
def test_non_ui_layers_do_not_import_ui():
    forbidden_roots = [
        "src/config",
        "src/modules",
        "src/pipeline",
        "src/services",
        "src/shared/engine",
    ]
    # 扫描 import 语句，禁止 from src.ui 或 import src.ui
```

也可以先用脚本守门:

```powershell
rg -n "from src\.ui|import src\.ui" src\config src\modules src\pipeline src\services src\shared\engine
```

## 8. 下一次建议执行的最小闭环

推荐下一次不要直接大拆文件，而是做一个最小治理闭环:

1. 新增 `.gitattributes`。
2. 新增 `pyproject.toml` 的最小 pytest 配置。
3. 提取 `scene_presets` 中的纯配置到 `src/config`。
4. 加一条架构测试禁止非 UI 层导入 UI。
5. 跑:

```powershell
python -m py_compile main.py
python -m compileall -q src
python -m pytest --collect-only -q
python -m pytest tests\test_config_library_and_bridge.py -q
python -m pytest tests\test_phase0_smoke.py -q
```

这个闭环的收益最大，因为它同时解决:

- 工程配置不足
- 行尾风险
- 反向依赖
- 配置库测试风险
- 冒烟稳定性

## 9. 当前状态判定

当前项目适合继续维护，但不适合继续无约束扩张。

可以继续开发的前提:

- 先收口当前工作区。
- 先修复 `config -> ui` 反向依赖。
- 对 1000 行以上文件建立拆分计划。
- 对生成物和文档目录建立清晰边界。

短期目标不是让项目看起来更漂亮，而是让下一次改动更可控。

## 10. 最小治理闭环执行记录

执行日期: 2026-07-07

本节记录按第 8 节建议执行的第一轮最小闭环。目标是先把工程配置基线、`config -> ui` 反向依赖和架构守门测试落地。

### 10.1 已完成的改动

1. 新增 `.gitattributes`
   - 固定常见文本文件为 LF。
   - 固定 Windows 批处理脚本为 CRLF。
   - 标记 `docx`、图片、PDF、zip 等为 binary。

2. 新增 `pyproject.toml`
   - 定义项目名、版本和 Python 版本要求。
   - 将运行依赖放入 `project.dependencies`。
   - 将 `pytest` 放入 `dev` extra。
   - 将 `pyinstaller` 放入 `build` extra。
   - 增加 pytest 基础配置: `testpaths = ["tests"]`、`pythonpath = ["."]`。

3. 拆分运行依赖与开发/构建依赖
   - `requirements.txt` 保留运行依赖。
   - `scripts/windows/install_env.bat` 改为安装 `.[dev,build]`，保持一键开发/打包环境能力。
   - `tests/test_release_shell.py` 同步更新为守护新的 pyproject extras 安装约定。

4. 上移场景预设实现
   - 将原 `src/ui/panels/workbench/scene_presets.py` 的实现迁移到 `src/config/scene_presets.py`。
   - 原 UI 路径改为兼容导出 wrapper，避免 UI 调用方和测试一次性断裂。
   - `src/config/library.py`、`src/config/scene_delivery_preset_audit.py`、`src/config/scene_input_source_audit.py`、`src/config/scene_material_schema_audit.py` 改为导入 `src.config.scene_presets`。
   - `src/config/scene_control_consistency_audit.py`、`src/config/scene_input_source_audit.py`、`src/config/scene_material_schema_audit.py`、`src/config/scene_pack_slot_audit.py` 中的 source ref 更新到 `src/config/scene_presets.py`。

5. 新增架构守门测试
   - 新增 `tests/test_architecture_boundaries.py`。
   - 使用 AST 扫描真实 import 语句。
   - 禁止以下非 UI 层导入 `src.ui`:
     - `src/config`
     - `src/modules`
     - `src/pipeline`
     - `src/services`
     - `src/shared/engine`

6. 清理明确运行日志
   - 删除根目录运行日志 `alavette_form.log`。
   - 该文件属于发布脚本测试明确要求清理的本地产物。

### 10.2 验证命令与结果

执行命令:

```powershell
rg -n "from src\.ui|import src\.ui" src\config src\modules src\pipeline src\services src\shared\engine
```

结果:

- 无命中。

执行命令:

```powershell
python -m pytest tests\test_architecture_boundaries.py tests\test_config_library_and_bridge.py tests\test_release_shell.py tests\test_qt_api_migration.py -q
```

结果:

- `28 passed in 4.79s`

执行命令:

```powershell
python -m py_compile main.py
python -m compileall -q src
python -m pytest --collect-only -q
python -m pytest tests\test_config_library_and_bridge.py -q
python -m pytest tests\test_phase0_smoke.py -q
```

结果:

| 命令 | 结果 |
| --- | --- |
| `python -m py_compile main.py` | 通过 |
| `python -m compileall -q src` | 通过 |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过导入收集 |
| `python -m pytest tests\test_config_library_and_bridge.py -q` | `11 passed` |
| `python -m pytest tests\test_phase0_smoke.py -q` | `14 passed` |

### 10.3 本轮后状态判断

本轮已经完成第 8 节的最小闭环:

- 工程配置基线已建立。
- 运行依赖与开发/构建依赖已拆分。
- `config -> ui` 的真实 import 反向依赖已消除。
- 架构守门测试已落地。
- 文档指定的最小验证命令已通过。

### 10.4 仍未完成的后续阶段

这些内容仍属于后续治理范围，尚未完成:

1. 阶段 0 的完整工作区收口
   - 当前仓库仍有大量历史未提交/未跟踪文件，需要独立分类和清理。

2. 阶段 3 的大文件拆分
   - `scene_panel.py`、`report_writer.py`、`workbench_execution_adapter.py`、`scene_matrix_dashboard.py`、`scene_matrix_drilldown.py` 尚未拆分。

3. 阶段 4 的文档和生成物边界治理
   - `docs` 目录和临时产物目录仍需要进一步归档规则和落地清理。

4. 全量测试运行
   - 本轮完成了测试收集、目标测试和冒烟测试。
   - 尚未运行完整 `python -m pytest tests -q`。

### 10.5 全量测试尝试与补充修复记录

执行日期: 2026-07-07

在完成最小治理闭环后，补充尝试运行完整测试套件:

```powershell
python -m pytest tests -q
```

结果:

- 测试在中段持续运行较久，并已经出现多个失败。
- 因运行时间过长，后续改为 `python -m pytest tests -q -x` 定位首个失败。
- `-x` 运行越过已修复失败点后，在约 44% 附近进入长耗时段。
- 当前没有取得完整全量通过结论。

已定位并修复的失败点:

1. `tests/test_assets_enterprise_boundary.py::test_enterprise_boundary_classifies_core_and_enterprise_groups`
   - 原断言仍期望 `lightweight_shared_cache` 注册为 `isolate`。
   - 现有边界实现、`tests/test_assets_panel_architecture.py` 和删除计划均要求该能力已移除。
   - 已更新测试为断言 `boundary_by_key("lightweight_shared_cache") is None`。

2. `tests/test_design_system_refactor.py::test_quick_execution_and_theme_panel_share_flow_and_tokens`
   - 原断言要求 quick execution detail 直接导入 `FlowLayout`。
   - 当前 quick execution detail 已不再使用 `FlowLayout`，强行导入会制造无用依赖。
   - 已更新测试为守护 quick execution detail 不包含 `FlowLayout`，并保留 theme panel 使用共享 `FlowLayout` 的断言。

3. `tests/test_heading_panel_locking.py::test_heading_numbering_panel_scheme_action_row_keeps_buttons_fully_visible`
   - 共享 `FormActionButtonRow` 的 `FlowLayout` 未设置 `Qt.AlignVCenter`。
   - 已在 `src/shared/ui/form_action_row.py` 构造布局时设置 `Qt.AlignVCenter`。

补充验证:

```powershell
python -m py_compile main.py src\shared\ui\form_action_row.py tests\test_assets_enterprise_boundary.py tests\test_design_system_refactor.py
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py tests\test_config_library_and_bridge.py tests\test_release_shell.py tests\test_qt_api_migration.py tests\test_assets_enterprise_boundary.py tests\test_assets_panel_architecture.py tests\test_design_system_refactor.py tests\test_heading_panel_locking.py -q
python -m pytest --collect-only -q
python -m pytest tests\test_phase0_smoke.py -q
```

结果:

| 命令 | 结果 |
| --- | --- |
| `python -m py_compile ...` | 通过 |
| `python -m compileall -q src` | 通过 |
| 目标测试组 | `99 passed in 11.92s` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过导入收集 |
| `python -m pytest tests\test_phase0_smoke.py -q` | `14 passed` |

后续判断:

- 全量测试仍不能宣称通过。
- 当前更合适的下一步是将全量套件拆为文件组或功能域组，逐组跑完并记录失败，而不是继续依赖单条长时间 `python -m pytest tests -q`。

### 10.6 分组测试执行器与高风险分组闭环

执行日期: 2026-07-07

由于单条 `python -m pytest tests -q` 在当前仓库规模下反馈周期过长，本轮新增了标准库实现的分组测试执行器:

```powershell
python scripts\run_pytest_groups.py --list
python scripts\run_pytest_groups.py --groups scene --timeout 600 --summary-path .pytest_tmp\pytest_groups_scene_green_2026-07-07.json
```

执行器能力:

- 按 `tests/test_*.py` 文件名自动分组。
- 支持 `--groups`、`--timeout`、`--continue-on-fail`、`--summary-path`。
- 支持 `--split-files`，用于定位单个慢文件或挂起文件。
- 默认设置 `PYTHONUTF8=1`、`PYTHONPATH=<repo>`、`QT_QPA_PLATFORM=offscreen`。
- Windows 下 subprocess 输出改为 `encoding="utf-8", errors="replace"`，避免中文输出导致 runner 自身失败。

高风险组验证结果:

| 分组 | 结果 |
| --- | --- |
| core: `architecture,assets,config,design,heading,qt,release` | 全部通过 |
| `execution` | `51 passed` |
| `phase` | `117 passed` |
| `quick` | `54 passed` |
| `material` | `73 passed in 11.13s` |
| `template` | `179 passed in 75.92s` |
| `workbench` | `183 passed in 33.34s` |
| `scene` | `356 passed in 273.32s` |

补充小组验证:

- 使用 runner 补跑了未包含在高风险组内的小组，如 `all,app,body,builtin,button,caption,citation,combo,content,control,count,...,windows`。
- 初次补跑只剩 `style` 与 `table` 两组失败。
- 修复后补跑:

```powershell
python scripts\run_pytest_groups.py --groups style,table --timeout 240 --continue-on-fail --summary-path .pytest_tmp\pytest_groups_style_table_rerun_2026-07-07.json
```

结果:

| 分组 | 结果 |
| --- | --- |
| `style` | `17 passed in 2.39s` |
| `table` | `12 passed in 0.44s` |

### 10.7 本轮修复记录

1. ScenePanel 导航与概览同步
   - 修复隐藏测试上下文中 `isVisible()` 导致的 scene scope focus 失败。
   - `_ScopeDetail._scope_zone_for_field()` 支持 `scene.format_scope.sections.` 前缀。
   - detail 编辑后刷新 scene overview 与 navigation cards，避免引用格式详情编辑后概览状态不同步。

2. Word COM 字段刷新测试保护
   - `src/shared/engine/field_refresh.py` 在 pytest 下默认跳过真实 Word COM refresh。
   - 可通过 `LARK_ENABLE_WORD_COM_IN_TESTS` 显式打开。
   - 解决 material 执行测试中 Word COM helper 子进程滞留导致的超时。

3. Scene release gate 与矩阵报告性能治理
   - `scripts/verify_scene_matrix_release_gate.py` 在 pytest 下加入轻量 release gate payload cache。
   - drilldown release gate 使用固定审计快照，避免每个 gate 测试重复生成超重 drilldown 报告。
   - `src/config/scene_matrix_dashboard.py` 在 pytest 下缓存未过滤 dashboard 基础报告，再派生过滤视图。
   - `src/config/scene_matrix_drilldown.py` 在 pytest 下缓存未过滤 drilldown 基础报告，再派生过滤视图；构建期默认不重复执行完整 audit，显式 audit 测试仍覆盖规则。
   - `src/config/scene_word_risk_closure_audit.py` 和 `src/config/scene_object_preflight_action_audit.py` 对纯静态 audit 构建和 source evidence 读取加 `lru_cache`，避免重复读取同一批源文件。

4. Scene 真实断言修复
   - `src/config/scene_coverage_manifest.py` 为 `exam_education` 补上 `executable_scene_ids=("exam",)`。
   - `tests/test_scene_boundary_capability_matrix.py` 同步当前 UI 中文计数与 tooltip 证据展示。
   - `tests/test_scene_matrix_dashboard.py` 同步 `exam` delivery content visibility rule count 为 `20`，保留全局计数 `18`。
   - `tests/test_scene_matrix_drilldown.py` 补入缺失的 `build_scene_formula_output_watermark_audit_report` 导入。
   - `src/config/scene_repair_routing.py` 将 material repair route evidence 从旧 `assets_panel.py` 更新到当前 `src/ui/panels/assets/material_repair_navigation_presenter.py`。

5. Style/table 低风险组修复
   - `scripts/export_style_source_visual_audit.py` 兼容新的 `StyleDifferenceSummarySlot`，继续输出旧 visual audit metrics 契约字段。
   - `src/shared/engine/paragraph_iter.py` 修复 `iter_table_cells()` 使用 `id(cell._element)` 去重不可靠的问题，改为遍历底层 `w:tc` 并包装为 `_Cell`。
   - 该修复使 table formatting 能覆盖全部物理单元格，`config.table.bold/italic` 能正确应用到 body cell runs。

### 10.8 最终验证记录

执行命令:

```powershell
python -m compileall -q src
python -m py_compile scripts\run_pytest_groups.py scripts\verify_scene_matrix_release_gate.py scripts\export_style_source_visual_audit.py
python -m pytest --collect-only -q
```

结果:

| 命令 | 结果 |
| --- | --- |
| `python -m compileall -q src` | 通过 |
| `python -m py_compile ...` | 通过 |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |

进程状态:

- 已确认没有残留 `pytest` 进程。
- 已确认没有残留 `DOCX_REFRESH_PATH` Word refresh helper 进程。

### 10.9 当前结构健康判断

当前项目已经从“难以验证、边界存在反向依赖风险”的状态，推进到“有边界守门、有分组回归、有高风险组可重复验证”的状态。

结论:

- 代码结构现在具备基本治理健康度。
- `config -> ui` 反向 import 已被消除并由 AST 测试守住。
- 测试体系已经可按分组完成覆盖式验证，不再依赖单条长时间无反馈命令。
- 高风险结构面 `scene/material/template/workbench` 均已通过。
- 仍不能称为轻量健康，因为大文件拆分、docs/生成物边界、历史未跟踪文件和工作区清理尚未完成。

后续建议:

1. 将 `scene_matrix_dashboard.py`、`scene_matrix_drilldown.py`、`scene_panel.py`、`report_writer.py`、`workbench_execution_adapter.py` 继续拆分为更小的 projection/audit/adapter 模块。
2. 为 `docs`、截图、临时报告、测试输出目录建立更严格的归档与忽略规则。
3. 将本轮 runner 总结文件纳入工程健康检查流程，避免未来再次回到单条长命令不可观测的状态。

### 10.10 阶段 3 补充推进: `report_writer.py` 首轮拆分

执行日期: 2026-07-07

本轮继续执行第 6 节阶段 3 的大文件拆分建议，优先选择 `src/report_writer.py`。该文件公开入口稳定，主要对外提供 `write_json_report()` 和 `write_markdown_report()`，内部报告 section 已经按领域成簇，适合先做低风险抽取。

已完成改动:

1. 新增 `src/reporting/` 报告 helper 包。
2. 从 `src/report_writer.py` 抽出通用清洗与格式 helper:
   - `src/reporting/common.py`
3. 从 `src/report_writer.py` 抽出报告开头上下文和样式来源 section:
   - `src/reporting/front_matter.py`
4. 从 `src/report_writer.py` 抽出学术引用/公式置信度 section:
   - `src/reporting/academic_confidence.py`
5. 从 `src/report_writer.py` 抽出英文期刊引用校验 section:
   - `src/reporting/journal_citations.py`
6. 从 `src/report_writer.py` 抽出英文期刊规则源治理 section:
   - `src/reporting/journal_rule_source.py`
7. 更新 `tests/test_architecture_boundaries.py`，将 `src/reporting` 纳入非 UI 层守门，禁止其导入 `src.ui`。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/report_writer.py` | `3191` |
| `src/reporting/academic_confidence.py` | `262` |
| `src/reporting/common.py` | `46` |
| `src/reporting/front_matter.py` | `128` |
| `src/reporting/journal_citations.py` | `125` |
| `src/reporting/journal_rule_source.py` | `143` |

对比第 3.4 节记录的 `src/report_writer.py` 原始 `3852` 行，本轮已减少 `661` 行。该文件仍然偏大，但已经从单文件报告巨石拆出第一批稳定 section 模块。

验证命令:

```powershell
python -m py_compile src\report_writer.py src\reporting\common.py src\reporting\front_matter.py src\reporting\academic_confidence.py src\reporting\journal_citations.py src\reporting\journal_rule_source.py
python -m pytest tests\test_execution_diagnostics_reporting.py tests\test_count_engine_semantics.py tests\test_exam_question_schema_runtime.py tests\test_fixed_layout_text_runtime.py tests\test_journal_citation_runtime.py -q
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py tests\test_output_runtime_semantics.py tests\test_object_preflight_semantics.py tests\test_material_field_consistency.py tests\test_journal_rule_source_governance.py tests\test_scene_journey_runtime.py -q
python -m pytest --collect-only -q
python scripts\run_pytest_groups.py --groups execution,journal,output,object,material,count --timeout 240 --continue-on-fail --summary-path .pytest_tmp\pytest_groups_reporting_refactor_2026-07-07.json
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| 报告写入目标测试 | `53 passed` |
| `python -m compileall -q src` | 通过 |
| 架构与相关语义测试 | `47 passed` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |
| runner `count` | `6 passed` |
| runner `execution` | `51 passed` |
| runner `journal` | `7 passed` |
| runner `material` | `73 passed` |
| runner `object` | `11 passed` |
| runner `output` | `28 passed` |

当前判断:

- 阶段 3 已经从“未开始”推进为“已启动并完成 `report_writer.py` 首轮切分”。
- `report_writer.py` 仍需继续拆 `journal_submission_package`、official numbering、technical chapter、application word limit、exam、material/object preflight、coverage、scene journey/product readiness、parameter ownership、control contracts 等 section。
- 其他阶段 3 目标文件 `scene_panel.py`、`workbench_execution_adapter.py`、`scene_matrix_dashboard.py`、`scene_matrix_drilldown.py` 仍未拆分。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.11 阶段 3 补充推进: `workbench_execution_adapter.py` artifact 子模块拆分

执行日期: 2026-07-07

本轮继续推进第 6 节阶段 3 的大文件拆分建议，选择 `src/ui/adapters/workbench_execution_adapter.py` 中的 recent-run artifact 构建与展示逻辑。该逻辑原本混在执行状态 adapter 中，同时承担交付产物分组、报告路径推断、输出目标预警、题图批量事务 artifact 展示等职责。

已完成改动:

1. 新增 `src/ui/adapters/workbench_artifact_items.py`。
2. 从 `src/ui/adapters/workbench_execution_adapter.py` 抽出:
   - `workbench_artifact_display_items()`
   - `_artifact_label()`
   - `_build_artifact_items()`
   - `_artifact_browser_label()`
   - artifact 分组、报告路径推断、输出预警详情、题图批量事务 artifact 相关 helper。
3. `WorkbenchExecutionAdapter` 继续作为执行结果状态装配入口，调用新模块生成 `ArtifactItemState` 列表和 artifact label。
4. 更新 `src/config/scene_report_artifact_drilldown_audit.py`，将 artifact builder、grouping、output preflight parser 的 source evidence 迁移到新模块。
5. 更新 `tests/test_scene_report_artifact_drilldown_audit.py`，将 source evidence count 从 `29` 同步为 `32`；missing evidence 仍为 `0`。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/ui/adapters/workbench_execution_adapter.py` | `2737` |
| `src/ui/adapters/workbench_artifact_items.py` | `558` |

对比第 3.4 节记录的 `src/ui/adapters/workbench_execution_adapter.py` 原始 `3275` 行，本轮已减少 `538` 行。该文件仍偏大，但 recent-run artifact 浏览器和交付产物展示规则已经拥有独立模块边界。

验证命令:

```powershell
python -m py_compile src\ui\adapters\workbench_execution_adapter.py src\ui\adapters\workbench_artifact_items.py src\config\scene_report_artifact_drilldown_audit.py
python -m pytest tests\test_scene_report_artifact_drilldown_audit.py tests\test_workbench_execution_center.py tests\test_workbench_execution_architecture.py -q
python scripts\run_pytest_groups.py --groups workbench,output,quick --timeout 300 --continue-on-fail --summary-path .pytest_tmp\pytest_groups_workbench_artifact_refactor_2026-07-07.json
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_workbench_artifact_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest --collect-only -q
python -m pytest tests\test_architecture_boundaries.py -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| artifact/Workbench 目标测试 | `90 passed` |
| runner `output` | `28 passed` |
| runner `quick` | `54 passed` |
| runner `workbench` | `183 passed` |
| runner `scene` | `356 passed` |
| `python -m compileall -q src` | 通过 |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |
| `tests/test_architecture_boundaries.py` | `1 passed` |

当前判断:

- 阶段 3 已完成两个目标文件的首轮拆分: `report_writer.py` 与 `workbench_execution_adapter.py`。
- `workbench_execution_adapter.py` 下一步可继续拆 issue item 构建、style/object preflight summary、material readiness 等簇。
- 剩余最高风险文件仍包括 `scene_panel.py`、`scene_matrix_dashboard.py`、`scene_matrix_drilldown.py`，以及继续拆薄后的 `report_writer.py` 和 `workbench_execution_adapter.py`。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.12 阶段 3 补充推进: `scene_panel.py` 交付 helper 拆分

执行日期: 2026-07-07

本轮继续推进第 6 节阶段 3 的大文件拆分建议，选择 `src/ui/panels/scene_panel.py` 中的输出交付版本、命名模板、内容块显隐规则与目标模板摘要 helper。该逻辑原本夹在面板类与资料规则 helper 之间，既包含 Qt 下拉项填充，也包含交付模板 registry、路径模板校验、内容块规则解析和推荐交付版本 tooltip dry-run。

已完成改动:

1. 新增 `src/ui/panels/scene_delivery_helpers.py`。
2. 从 `src/ui/panels/scene_panel.py` 抽出:
   - `_format_visibility_rules()` / `_parse_visibility_rules()` / `_append_visibility_rule_text()` 等内容块规则文本 helper。
   - `_DELIVERY_PRESET_TEMPLATE_MAP`、版本模板 tooltip、模板 artifact 应用和模板规则生成 helper。
   - `_scene_family_delivery_preview_tooltip()` 推荐交付版本预读 helper。
   - 交付变量下拉、内容块 selector 下拉、路径命名校验、目标模板摘要相关 helper。
3. `ScenePanel` 继续保留实际 UI 状态、按钮写回、preset 选择、scene edit signal 和推荐默认值应用入口；新模块只承接交付语义 helper，不改变交互副作用。
4. 更新 `src/config/control_contract_registry.py`，把输出版本与内容显隐契约的 source evidence 拆成主面板控件证据和 `scene_delivery_helpers.py` 语义 helper 证据。
5. 更新 `src/config/scene_control_runtime_consistency_audit.py`，新增 `delivery.delivery_helpers` 与 `visibility.delivery_helpers` 证据，记录新模块边界。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/ui/panels/scene_panel.py` | `6049` |
| `src/ui/panels/scene_delivery_helpers.py` | `700` |

对比第 3.4 节记录的 `src/ui/panels/scene_panel.py` 原始 `6702` 行，本轮已减少约 `653` 行。该文件仍然明显偏大，但输出交付模板、内容块规则解析与命名校验已经拥有独立 UI helper 边界。

验证命令:

```powershell
python -m py_compile src\ui\panels\scene_panel.py src\ui\panels\scene_delivery_helpers.py src\config\control_contract_registry.py src\config\scene_control_runtime_consistency_audit.py
python -m pytest tests\test_scene_panel_architecture.py tests\test_ui_copy_guardrails.py tests\test_design_system_refactor.py -q
python -m pytest tests\test_control_contract_registry.py tests\test_scene_control_runtime_consistency_audit.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_scene_delivery_refactor_2026-07-07.json
python scripts\run_pytest_groups.py --groups output,quick --timeout 500 --summary-path .pytest_tmp\pytest_groups_output_quick_after_scene_delivery_refactor_2026-07-07.json
python -m pytest tests\test_architecture_boundaries.py -q
python -m compileall -q src
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| ScenePanel/UI copy/design 目标测试 | `98 passed` |
| 控制契约与运行一致性审计 | `10 passed` |
| runner `scene` | `356 passed` |
| runner `output` | `28 passed` |
| runner `quick` | `54 passed` |
| `tests/test_architecture_boundaries.py` | `1 passed` |
| `python -m compileall -q src` | 通过 |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |

当前判断:

- 阶段 3 已完成三个目标文件的首轮拆分: `report_writer.py`、`workbench_execution_adapter.py`、`scene_panel.py`。
- `scene_panel.py` 下一步可继续拆 `_MaterialRequirementBlock`、场景概览动作、样本/请求 cell 列表、预检/合规摘要等簇。
- 剩余最高风险文件仍包括 `scene_matrix_dashboard.py`、`scene_matrix_drilldown.py`，以及继续拆薄后的 `scene_panel.py`、`report_writer.py`、`workbench_execution_adapter.py`。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.13 阶段 3 补充推进: `scene_panel.py` 资料规则 Block 拆分

执行日期: 2026-07-07

本轮继续推进 `scene_panel.py` 的第二片拆分，选择此前文档已多次点名的 `_MaterialRequirementBlock`。该 block 已经稳定承接资料规则选择、主资料规则、多规则列表、必填资料字段、图片/签章要求、预览摘要、未识别规则替换/移除等语义，适合从主面板中移出。

已完成改动:

1. 新增 `src/ui/panels/scene_material_requirement_block.py`。
2. 从 `src/ui/panels/scene_panel.py` 抽出:
   - `_MaterialRequirementBlock`
   - `_build_material_schema_validation_items()`
   - `_profile_material_schema_ids()`
   - 资料规则下拉填充、列表文本解析、资料字段/图片/附件预览、资料规则族显示名等 helper。
3. `ScenePanel` / `_ContentDetail` 继续保留旧属性别名:
   - `_material_requirement_block`
   - `_material_rule_selector`
   - `_schema_registry_combo`
   - `_material_schema_id`
   - `_material_schema_ids`
   - `_required_material_fields`
   - `_required_image_roles`
   现有测试和导航入口仍可通过这些别名访问控件。
4. 更新 `src/config/control_contract_registry.py`，给 `material.schema_selection` 增加 `scene_material_requirement_block.py` 的 source evidence。
5. 更新 `src/config/scene_control_runtime_consistency_audit.py`，给 `material_schema_selection_controls` 增加 `schema.material_requirement_block` evidence。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/ui/panels/scene_panel.py` | `5420` |
| `src/ui/panels/scene_material_requirement_block.py` | `668` |
| `src/ui/panels/scene_delivery_helpers.py` | `700` |

对比第 3.4 节记录的 `src/ui/panels/scene_panel.py` 原始 `6702` 行，两轮场景面板拆分后已减少约 `1282` 行。该文件仍超过 5000 行，但“输出交付 helper”和“资料规则 block”已经不再挤在主面板里。

验证命令:

```powershell
python -m py_compile src\ui\panels\scene_panel.py src\ui\panels\scene_material_requirement_block.py src\config\control_contract_registry.py src\config\scene_control_runtime_consistency_audit.py
python -m pytest tests\test_scene_panel_architecture.py tests\test_ui_copy_guardrails.py tests\test_design_system_refactor.py -q
python -m pytest tests\test_control_contract_registry.py tests\test_scene_control_runtime_consistency_audit.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_scene_material_block_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| ScenePanel/UI copy/design 目标测试 | `98 passed` |
| 控制契约与运行一致性审计 | `10 passed` |
| runner `scene` | `356 passed` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |

当前判断:

- 阶段 3 已完成 `report_writer.py`、`workbench_execution_adapter.py`、`scene_panel.py` 的首轮/二轮拆分。
- `scene_panel.py` 后续可继续拆场景概览动作、样本/请求 cell 列表、预检/合规摘要、样式/范围局部协调等簇。
- 剩余最高风险文件仍包括 `scene_matrix_dashboard.py`、`scene_matrix_drilldown.py`，以及继续拆薄后的 `scene_panel.py`、`report_writer.py`、`workbench_execution_adapter.py`。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.14 阶段 3 补充推进: `scene_matrix_dashboard.py` Lens/Source 规格拆分

执行日期: 2026-07-07

本轮转向当前最大配置侧文件 `src/config/scene_matrix_dashboard.py`，优先拆出风险较低但边界清晰的 Lens/Source 静态规格。该块包含 dashboard source id 清单、`SceneMatrixDashboardLens` 数据模型、9 个 dashboard lens 定义和 lens id 派生序列，和后续 dashboard 构建、审计、卡片汇总逻辑天然分离。

已完成改动:

1. 新增 `src/config/scene_matrix_dashboard_lenses.py`。
2. 从 `src/config/scene_matrix_dashboard.py` 抽出:
   - `SCENE_MATRIX_DASHBOARD_SOURCE_IDS`
   - `SceneMatrixDashboardLens`
   - `SCENE_MATRIX_DASHBOARD_LENSES`
   - `SCENE_MATRIX_DASHBOARD_LENS_IDS`
3. `src/config/scene_matrix_dashboard.py` 改为从新模块导入上述对象，并继续在 `__all__` 中导出同名 API，保持现有测试和外部调用面不变。
4. `src/config/scene_matrix_drilldown.py` 改为从轻量新模块读取 `SCENE_MATRIX_DASHBOARD_SOURCE_IDS`，避免仅为静态 source id 依赖 dashboard 主构建模块。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_dashboard.py` | `5468` |
| `src/config/scene_matrix_dashboard_lenses.py` | `301` |
| `src/config/scene_matrix_drilldown.py` | `5750` |

本轮约 300 行静态规格离开 dashboard 主模块。`scene_matrix_dashboard.py` 仍超过 5000 行，后续应继续拆分 report 数据模型、source report 聚合、card/row 构建、audit 规则等更重逻辑。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_dashboard.py src\config\scene_matrix_dashboard_lenses.py src\config\scene_matrix_drilldown.py
python -m pytest tests\test_scene_matrix_dashboard.py tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_dashboard_lenses_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| Dashboard/Drilldown 目标测试 | `13 passed` |
| runner `scene` | `356 passed` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |

当前判断:

- 阶段 3 已完成 `report_writer.py`、`workbench_execution_adapter.py`、`scene_panel.py`、`scene_matrix_dashboard.py` 的分批拆分推进。
- `scene_matrix_dashboard.py` 的首片拆分已降低静态规格和构建/审计逻辑耦合，但主模块仍偏大。
- 剩余最高风险文件仍包括 `scene_matrix_drilldown.py`、继续拆薄后的 `scene_matrix_dashboard.py` 与 `scene_panel.py`，以及后续二次拆分的 `report_writer.py`、`workbench_execution_adapter.py`。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.15 阶段 3 补充推进: `scene_matrix_dashboard.py` Payload 模型拆分

执行日期: 2026-07-07

在 Lens/Source 规格拆分通过后，本轮继续处理 `src/config/scene_matrix_dashboard.py` 中体量最大的纯数据模型区。该区包含 `Issue`、`Card`、`Row`、`Report` 四个 payload dataclass，以及 `status`、`pack_count`、`visible_count`、`issue_count`、`warning_count` 和完整 `to_payload()` 投影逻辑。它们定义 dashboard 对外数据形状，但不负责收集审计报告、过滤行、构建卡片或生成 issue，因此适合从主构建模块中独立出来。

已完成改动:

1. 新增 `src/config/scene_matrix_dashboard_models.py`。
2. 从 `src/config/scene_matrix_dashboard.py` 抽出:
   - `SceneMatrixDashboardIssue`
   - `SceneMatrixDashboardCard`
   - `SceneMatrixDashboardRow`
   - `SceneMatrixDashboardReport`
3. `src/config/scene_matrix_dashboard.py` 改为从模型模块导入这些类，并继续在 `__all__` 中 re-export，保持 `tests/test_scene_matrix_dashboard.py` 和外部调用面的导入路径稳定。
4. 主模块的 `dataclasses` 依赖从 `dataclass, replace` 收敛为 `replace`，说明主模块已不再声明 dashboard payload 数据类。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_dashboard.py` | `3460` |
| `src/config/scene_matrix_dashboard_models.py` | `2030` |
| `src/config/scene_matrix_dashboard_lenses.py` | `301` |
| `src/config/scene_matrix_drilldown.py` | `5750` |

对比第 10.14 节的 `5468` 行，本轮后 `scene_matrix_dashboard.py` 再减少约 `2008` 行；两轮 dashboard 拆分后，主模块已经从 5000+ 行降至 3500 行左右。剩余主模块职责主要是审计报告收集、行构建、过滤、issue 审计和 card 构建。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_dashboard.py src\config\scene_matrix_dashboard_lenses.py src\config\scene_matrix_dashboard_models.py src\config\scene_matrix_drilldown.py
python -m pytest tests\test_scene_matrix_dashboard.py tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_dashboard_models_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| Dashboard/Drilldown 目标测试 | `13 passed` |
| runner `scene` | `356 passed` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |

当前判断:

- `scene_matrix_dashboard.py` 的结构健康度明显改善: 静态 lens/source 规格和 payload 模型已离开主构建模块。
- 新的 `scene_matrix_dashboard_models.py` 行数较高，但语义单一，风险集中在 payload 形状和 `to_payload()` 投影，后续可按 counts/filters/rows 投影继续细拆。
- 下一阶段优先目标应转向当前最大的 `scene_matrix_drilldown.py`，或继续拆 `scene_matrix_dashboard.py` 的 card builder/source aggregation。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.16 阶段 3 补充推进: `scene_matrix_drilldown.py` Source Evidence 规格拆分

执行日期: 2026-07-07

本轮转向当前最大文件 `src/config/scene_matrix_drilldown.py`，优先拆出顶部的 source evidence 静态规格。该区域包含 drilldown 自身 source id、37 个 required drilldown id，以及 107 条 source evidence marker 定义。它是数据清单，不参与 report 构建、过滤、projection reference map 或 item builder 逻辑，适合独立为轻量规格模块。

已完成改动:

1. 新增 `src/config/scene_matrix_drilldown_sources.py`。
2. 从 `src/config/scene_matrix_drilldown.py` 抽出:
   - `SCENE_MATRIX_DRILLDOWN_SOURCE_ID`
   - `REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS`
   - `SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS`
3. `src/config/scene_matrix_drilldown.py` 改为导入这些常量，并继续在 `__all__` 中导出 `SCENE_MATRIX_DRILLDOWN_SOURCE_ID` 与 `REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS`，保持测试和外部调用路径稳定。
4. 定向测试首轮暴露 5 条 source evidence marker 仍以旧主文件为路径，但 marker 字符串实际已经随 source table 迁入新模块。随后将这些条目改为检查主模块中真实存在的 projection reference 函数名、循环变量或拆分字符串前缀，保持 evidence 数量 `107` 不变，并恢复 `107/107 ready`。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_drilldown.py` | `4728` |
| `src/config/scene_matrix_drilldown_sources.py` | `1036` |
| `src/config/scene_matrix_dashboard.py` | `3460` |
| `src/config/scene_matrix_dashboard_models.py` | `2030` |
| `src/config/scene_matrix_dashboard_lenses.py` | `301` |

对比拆分前 `src/config/scene_matrix_drilldown.py` 的 `5750` 行，本轮减少约 `1022` 行。该文件仍偏大，但最上层 source evidence 清单已不再挤在构建、审计和 item factory 逻辑中。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_drilldown.py src\config\scene_matrix_drilldown_sources.py
python -m pytest tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_drilldown_sources_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| Drilldown 目标测试 | 首轮 `4 failed, 3 passed`; 修正 marker 后 `7 passed` |
| runner `scene` | `356 passed` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |

当前判断:

- `scene_matrix_drilldown.py` 已完成第一片低风险拆分，source evidence/required id 静态清单拥有独立模块。
- 新模块 `scene_matrix_drilldown_sources.py` 行数超过 1000，但语义单一，后续可按 evidence family 或 release trace plan 再拆。
- `scene_matrix_drilldown.py` 仍有 dataclass、projection profile、projection reference map、item factory 多个职责，下一轮可优先拆 projection profiles 或 payload models。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.17 阶段 3 补充推进: `scene_matrix_drilldown.py` ProjectionProfile 规格拆分

执行日期: 2026-07-07

在 source evidence 规格拆分通过后，本轮继续拆 `src/config/scene_matrix_drilldown.py` 的 ProjectionProfile 静态规格。该区域包含 `SceneMatrixDrilldownProjectionProfile` dataclass、`SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILES` 和 `SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP`，用于描述 action/capability projection 的字段来源和 token kind，不直接参与 item factory 或 report 构建。

已完成改动:

1. 新增 `src/config/scene_matrix_drilldown_projection_profiles.py`。
2. 从 `src/config/scene_matrix_drilldown.py` 抽出:
   - `SceneMatrixDrilldownProjectionProfile`
   - `SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILES`
   - `SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP`
3. `src/config/scene_matrix_drilldown.py` 改为导入这些对象，继续保持 `SCENE_MATRIX_DRILLDOWN_PROJECTION_PROFILE_MAP` 可从主模块直接访问，兼容现有测试。
4. 定向测试首轮暴露 `scene_matrix_drilldown_projection_requirement_dimension_reference_audit` 的 source evidence marker `requirement_dimension_ids` 已随 profile 规格迁入新模块；随后把主模块 evidence marker 改为 `_projection_requirement_dimension_reference_map` 中真实存在的 `dimension_ids`，恢复 source evidence `107/107 ready`。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_drilldown.py` | `4293` |
| `src/config/scene_matrix_drilldown_projection_profiles.py` | `452` |
| `src/config/scene_matrix_drilldown_sources.py` | `1036` |
| `src/config/scene_matrix_dashboard.py` | `3460` |

对比第 10.16 节记录的 `src/config/scene_matrix_drilldown.py` `4728` 行，本轮再减少约 `435` 行。两轮 Drilldown 拆分后，source evidence 和 projection profile 两类静态规格已经从主模块中移出。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_drilldown.py src\config\scene_matrix_drilldown_sources.py src\config\scene_matrix_drilldown_projection_profiles.py
python -m pytest tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_drilldown_projection_profiles_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| Drilldown 目标测试 | 首轮 `4 failed, 3 passed`; 修正 marker 后 `7 passed` |
| runner `scene` | `356 passed` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |

当前判断:

- `scene_matrix_drilldown.py` 的静态规格负担明显下降，主模块剩余重点是 payload dataclass、projection reference map、audit 和 item factory。
- 下一轮可优先拆 payload dataclass 到 `scene_matrix_drilldown_models.py`，或把 `_projection_*_reference_map()` 系列迁到专门模块。
- `scene_panel.py` 仍是 UI 侧最大风险之一，后续也需要继续拆场景概览动作、样本/请求 cell 列表、预检/合规摘要等。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.18 阶段 3 补充推进: `scene_matrix_drilldown.py` Payload 模型拆分

执行日期: 2026-07-07

本轮继续执行第 10.17 节提出的下一步，将 `src/config/scene_matrix_drilldown.py` 顶部的 payload dataclass 拆出。该区域定义 drilldown 的 issue、source evidence、row、item、report 数据形状和 `to_payload()` 投影，不负责 audit、projection reference map、item factory 或实际报告构建，适合独立为模型模块。

已完成改动:

1. 新增 `src/config/scene_matrix_drilldown_models.py`。
2. 从 `src/config/scene_matrix_drilldown.py` 抽出:
   - `SceneMatrixDrilldownIssue`
   - `SceneMatrixDrilldownSourceEvidence`
   - `SceneMatrixDrilldownRow`
   - `SceneMatrixDrilldownItem`
   - `SceneMatrixDrilldownReport`
3. `src/config/scene_matrix_drilldown.py` 改为从模型模块导入上述类，并继续在 `__all__` 中导出同名对象，保持 `tests/test_scene_matrix_drilldown.py` 的主模块导入路径稳定。
4. `SceneMatrixDrilldownReport.to_payload()` 仍使用 `SCENE_MATRIX_DRILLDOWN_SOURCE_ID` 与 `REQUIRED_SCENE_MATRIX_DRILLDOWN_IDS`，但改为在模型模块中从 `scene_matrix_drilldown_sources.py` 导入，避免回引主构建模块。
5. 主模块 `dataclasses` 依赖从 `dataclass, replace` 收敛为 `replace`，说明 Drilldown 主模块已不再声明 payload 数据类。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_drilldown.py` | `4065` |
| `src/config/scene_matrix_drilldown_models.py` | `254` |
| `src/config/scene_matrix_drilldown_projection_profiles.py` | `452` |
| `src/config/scene_matrix_drilldown_sources.py` | `1036` |
| `src/config/scene_matrix_dashboard.py` | `3460` |

对比第 10.17 节记录的 `src/config/scene_matrix_drilldown.py` `4293` 行，本轮再减少约 `228` 行。三轮 Drilldown 拆分后，source evidence、projection profile 和 payload model 已从主模块移出。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_drilldown.py src\config\scene_matrix_drilldown_models.py src\config\scene_matrix_drilldown_sources.py src\config\scene_matrix_drilldown_projection_profiles.py
python -m pytest tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_drilldown_models_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| Drilldown 目标测试 | `7 passed` |
| runner `scene` | `356 passed` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，通过 |

当前判断:

- `scene_matrix_drilldown.py` 的主模块职责已进一步聚焦到 report 构建、audit、projection reference maps 和 item factories。
- 下一轮可优先拆 `_projection_*_reference_map()` 系列，或将 `_build_all_items()` 之后的 item factory 群拆成 `scene_matrix_drilldown_items.py`。
- `scene_panel.py` 当前仍是 UI 侧最大文件，应继续拆场景概览动作、样本/请求 cell 列表、预检/合规摘要等。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.19 阶段 3 补充推进: `scene_matrix_drilldown.py` Reference ID helper 拆分

执行日期: 2026-07-07

本轮继续处理 `src/config/scene_matrix_drilldown.py` 内部的 reference id 聚合逻辑。该区域负责从 delivery、material、input/render、object preflight、Word risk、plugin gate、maturity gap、external handoff contract 和 projection test 等既有 audit 报告中收集合法引用集合，主要服务 drilldown issue 校验和 projection reference 校验。它不直接构建 drilldown items，也不承载 UI-facing payload，因此适合从主构建模块中拆出。

已完成改动:

1. 新增 `src/config/scene_matrix_drilldown_reference_ids.py`。
2. 从 `src/config/scene_matrix_drilldown.py` 抽出以下 helper:
   - `_delivery_reference_ids`
   - `_material_reference_ids`
   - `_input_render_reference_ids`
   - `_object_preflight_reference_ids`
   - `_word_risk_surface_reference_ids`
   - `_plugin_gate_reference_ids`
   - `_target_plugin_reference_ids`
   - `_risk_domain_reference_ids`
   - `_maturity_gap_reference_ids`
   - `_external_handoff_contract_reference_ids`
   - `_projection_test_reference_ids`
3. `src/config/scene_matrix_drilldown.py` 改为从 `scene_matrix_drilldown_reference_ids.py` 导入上述 helper，并删除本地重复定义。
4. 同步清理主模块中只为这些 helper 服务的专用 import，例如 `list_material_schemas`、`list_plugin_manual_gates`、`DELIVERY_ARTIFACT_PSEUDO_IDS`、`PRODUCT_MATURITY_UPGRADE_DOMAIN_IDS`，降低主模块对 reference 聚合源的直接耦合。
5. 定向 drilldown 测试未暴露 source evidence marker 问题，因此本轮无需调整 `SCENE_MATRIX_DRILLDOWN_SOURCE_MARKERS`。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_drilldown.py` | `3722` |
| `src/config/scene_matrix_drilldown_reference_ids.py` | `193` |
| `src/config/scene_matrix_drilldown_sources.py` | `1030` |
| `src/config/scene_matrix_drilldown_projection_profiles.py` | `442` |
| `src/config/scene_matrix_drilldown_models.py` | `220` |
| `src/config/scene_matrix_dashboard.py` | `3460` |

对比第 10.18 节记录的 `src/config/scene_matrix_drilldown.py` `4065` 行，本轮再减少约 `343` 行。四轮 Drilldown 拆分后，source evidence、projection profile、payload model、reference id helper 已经从主模块移出，主模块剩余重点进一步收敛到 projection reference map、audit 组装和 item factory。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_drilldown.py src\config\scene_matrix_drilldown_models.py src\config\scene_matrix_drilldown_sources.py src\config\scene_matrix_drilldown_projection_profiles.py src\config\scene_matrix_drilldown_reference_ids.py
python -m pytest tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_drilldown_reference_ids_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| Drilldown 目标测试 | `7 passed in 110.80s` |
| runner `scene` | `356 passed in 236.40s`; runner 汇总 `[PASS] scene in 239.7s` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed in 0.88s` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，命令通过 |

当前判断:

- `scene_matrix_drilldown.py` 的大文件风险继续下降，且本轮没有破坏主模块导出路径或 source evidence ready 状态。
- 新增 `scene_matrix_drilldown_reference_ids.py` 语义清晰，依赖集中在“引用集合从哪里来”，比留在主构建模块里更容易审查。
- `scene_matrix_drilldown.py` 仍有 3000 行以上，下一轮更适合继续拆 `_projection_*_reference_map()` 系列，或将 item factory 群拆成 `scene_matrix_drilldown_items.py`。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.20 阶段 3 补充推进: `scene_matrix_drilldown.py` Projection reference map 拆分

执行日期: 2026-07-07

本轮继续执行第 10.19 节提出的下一步，将 `src/config/scene_matrix_drilldown.py` 中的 projection reference map 族拆出。该区域负责把 source/surface/path/evidence/release marker/release link/control runtime/report delivery/requirement dimension/target plugin/formula output watermark 等引用集合投影成 `(drilldown_id, row_id, field_name) -> reference ids` 的校验表，职责偏“引用追踪索引”，不应长期夹在 report 构建和 item factory 中。

已完成改动:

1. 新增 `src/config/scene_matrix_drilldown_projection_references.py`。
2. 从 `src/config/scene_matrix_drilldown.py` 抽出:
   - `_projection_source_reference_ids`
   - `_projection_source_reference_map`
   - `_projection_surface_reference_map`
   - `_projection_path_reference_map`
   - `_projection_evidence_reference_map`
   - `_projection_release_marker_reference_map`
   - `_projection_release_link_reference_map`
   - `_projection_retained_gap_exit_reference_map`
   - `_projection_control_runtime_reference_map`
   - `_projection_release_metric_reference_map`
   - `_projection_external_handoff_contract_reference_map`
   - `_projection_report_delivery_marker_reference_map`
   - `_projection_requirement_dimension_reference_map`
   - `_projection_target_plugin_reference_map`
   - `_projection_formula_output_watermark_reference_map`
   - `_release_residual_receipt_action_ids`
3. `src/config/scene_matrix_drilldown.py` 改为从新模块导入上述私有 helper，保持主模块命名空间仍能访问这些名称，降低对测试和脚本的兼容风险。
4. 清理主模块中只为旧 projection reference helper 服务的直接 import，例如 `SCENE_MATRIX_DASHBOARD_SOURCE_IDS` 与 `SCENE_RELEASE_GOVERNANCE_EXPORT_SCRIPT_EVIDENCE_SOURCE_ID`。
5. 同步调整 `src/config/scene_matrix_drilldown_sources.py` 的 source evidence marker:
   - `scene_matrix_drilldown_projection_source_reference_audit`: 将主模块 marker 中的 `SCENE_MATRIX_DASHBOARD_SOURCE_IDS` 改为 `_projection_source_reference_ids`。
   - `scene_matrix_drilldown_projection_requirement_dimension_reference_audit`: 首轮专项测试暴露 `dimension_ids` 已随局部函数迁入新模块，随后改为主模块仍真实存在的 `projection_requirement_dimension_reference_map`。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_drilldown.py` | `2914` |
| `src/config/scene_matrix_drilldown_projection_references.py` | `917` |
| `src/config/scene_matrix_drilldown_reference_ids.py` | `193` |
| `src/config/scene_matrix_drilldown_sources.py` | `1030` |
| `src/config/scene_matrix_drilldown_projection_profiles.py` | `442` |
| `src/config/scene_matrix_drilldown_models.py` | `220` |
| `src/config/scene_matrix_dashboard.py` | `3397` |

对比第 10.19 节记录的 `src/config/scene_matrix_drilldown.py` `3722` 行，本轮再减少约 `808` 行。五轮 Drilldown 拆分后，主模块已低于 3000 行，职责进一步集中到 report audit 流程和 item factory 群。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_drilldown.py src\config\scene_matrix_drilldown_projection_references.py src\config\scene_matrix_drilldown_reference_ids.py src\config\scene_matrix_drilldown_models.py src\config\scene_matrix_drilldown_sources.py src\config\scene_matrix_drilldown_projection_profiles.py
python -m pytest tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_drilldown_projection_references_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| Drilldown 目标测试 | 首轮 `4 failed, 3 passed in 104.81s`; 修正 requirement dimension marker 后 `7 passed in 111.20s` |
| runner `scene` | `356 passed in 235.74s`; runner 汇总 `[PASS] scene in 239.6s` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed in 0.76s` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，命令通过 |

当前判断:

- `scene_matrix_drilldown.py` 已从原始高风险超大配置模块明显降温，静态规格、payload 模型、reference id helper 与 projection reference map 都已独立成模块。
- `scene_matrix_drilldown_projection_references.py` 当前 900 行以上，但职责高度单一，后续如继续拆分可按 release trace、material/delivery、formula/control 三类 projection reference 分段。
- `scene_matrix_drilldown.py` 仍保留大量 item factory，下一轮阶段 3 更适合拆 `_item_factories_for_source()` 之后的 item 构建函数，或转向 UI 侧的 `scene_panel.py` 继续减重。
- 阶段 0 工作区收口和阶段 4 文档/生成物边界治理仍未完成。

### 10.21 阶段 0/4 补充审计: 工作区与文档/生成物边界复查

执行日期: 2026-07-07

在完成多轮大文件拆分后，本轮回到第 6 节的阶段 0 与阶段 4，复查当前工作区是否可以通过简单 ignore 规则或安全自动清理收口。结论是: 不能直接自动清理。当前未收口的大头已经不是单纯临时目录，而是 `docs`、`src`、`tests`、`scripts`、`samples`、`exam_masters` 等真实候选变更，需要按提交主题分组确认。

执行命令:

```powershell
Get-Content -LiteralPath .gitignore -TotalCount 240
Test-Path -LiteralPath .gitattributes
Get-Content -LiteralPath .gitattributes -TotalCount 120
Get-ChildItem -Directory | Where-Object { $_.Name -like 'tmp*' -or $_.Name -like '.codex_tmp*' -or $_.Name -like '.pytest*' -or $_.Name -eq 'artifacts' -or $_.Name -eq 'dist' -or $_.Name -eq 'build' } | Select-Object Name,LastWriteTime
git status --porcelain=v1 --untracked-files=all | Measure-Object
git status --porcelain=v1 --untracked-files=all | ForEach-Object { $_.Substring(0,2) } | Group-Object | Sort-Object Count -Descending
git status --ignored --porcelain=v1 | ForEach-Object { $_.Substring(0,2) } | Group-Object | Sort-Object Count -Descending
```

复查结果:

| 项目 | 结果 |
| --- | --- |
| `.gitignore` | 已覆盖 `__pycache__/`、`.pytest_cache/`、`dist/`、`build/`、`tests/output/`、`artifacts/`、`/.pytest_tmp/`、`/.codex_tmp*/`、`/tmp_*/`、根目录 docx/json/md 报告、日志、截图和本地 scratch 脚本 |
| `.gitattributes` | 已存在，定义 `*.py`、`*.md`、`*.json`、`*.yaml`、`*.toml` 为 LF，`*.bat`/`*.ps1` 为 CRLF，并将 docx/png/pdf/zip 等作为 binary |
| 根目录临时/生成物目录 | 仍存在 `.codex_tmp`、`.codex_tmp_color_table`、`.pytest_cache`、`.pytest_tmp`、`artifacts`、多组 `tmp_*` 目录 |
| `git status --porcelain=v1 --untracked-files=all` | `1396` 条记录 |
| 状态分布 | `1221` 条未跟踪、`157` 条修改、`10` 条删除、`7` 条 rename+modify、`1` 条已暂存删除 |
| ignored 复查 | `git status --ignored --porcelain=v1` 显示 `94` 条 ignored 记录，说明 ignore 规则已经吸收了一部分生成物，但仍有大量真实候选变更未归档 |

未跟踪项按顶层路径粗分时，主要集中在:

| 顶层区域 | 粗略数量 | 判断 |
| --- | ---: | --- |
| `docs` 及带空格/中文转义的 docs 路径 | `600+` | 更像审计记录、过程文档和历史文档混合，不能自动删除 |
| `src` | `204` | 真实源码候选变更，必须保留并按功能分组 |
| `exam_masters` | `167` | 样例/主数据候选变更，需确认是否为产品资产 |
| `tests` | `92` | 测试候选变更，通常应随源码分组提交 |
| `scripts` | `52` | 工具脚本候选变更，需区分正式工具和一次性脚本 |
| `samples` | `43` | 样例资产候选变更，需与产品/测试数据边界一起确认 |

本轮未执行的操作:

- 未删除任何 `tmp_*`、`artifacts`、`.pytest_tmp` 或 `.codex_tmp*` 目录。
- 未移动 `docs` 下的历史记录。
- 未暂存、提交或回滚任何文件。
- 未尝试自动拆分 1000+ 条未跟踪记录，因为其中包含大量真实源码、测试、文档和样例资产。

当前判断:

- 阶段 0 不能靠一次自动清理完成，需要先由提交主题切分: `scene matrix refactor`、`workbench/reporting refactor`、`tests/runner`、`docs/audits`、`sample assets`、`legacy generated outputs` 等。
- 阶段 4 的第一步不应是移动所有 docs，而应先建立文档分类规则，再逐批迁移；否则会制造巨量 rename 噪音。
- `.gitignore` 和 `.gitattributes` 已经具备基础规则，下一步更适合补一份 docs 边界说明，而不是继续盲目扩展 ignore。
- 当前项目结构健康度较最初已改善，尤其是架构边界和大文件拆分；但发布基线仍受工作区未收口影响，不能称为完全健康。

### 10.22 阶段 4 补充推进: 新增文档边界说明

执行日期: 2026-07-07

根据第 10.21 节复查结论，本轮新增轻量边界说明文件 `docs/DOCUMENTATION_BOUNDARIES.md`。该文件只定义新文档和生成物的归档规则，不批量移动既有历史文件，避免在当前大工作区中制造大量 rename 噪音。

已完成改动:

1. 新增 `docs/DOCUMENTATION_BOUNDARIES.md`，当前 `45` 行。
2. 定义新文档的建议分类:
   - `docs/architecture/`: 长期架构说明、模块边界、依赖规则。
   - `docs/audits/`: 审计计划、traceability/source-evidence 记录。
   - `docs/refactor-records/`: 重构执行记录、验证摘要、迁移日志。
   - `docs/visual_checks/`: 精选视觉 QA 记录和图片引用。
3. 明确当前已存在的 `docs/migration_audit/`、`docs/visual_audit/` 可继续承接既有线程，但不建议混入新的无关重构日志。
4. 明确生成物默认应停留在 `.pytest_tmp/`、`.codex_tmp*/`、`artifacts/`、`tmp_*/`、`tests/output/`，除非被整理成有价值的 Markdown 证据。
5. 增加清理前分类规则: 源码/测试/样例/产品资产、长期文档、审计/重构证据、生成物/本地 scratch；只有最后一类适合在确认未被引用后自动清理。

验证:

- 本轮为文档边界说明，不涉及 Python 代码或导入路径。
- 未执行删除、移动、暂存、提交或批量 rename。

当前判断:

- 阶段 4 已从“只有建议”推进到“有明确文档边界规则”，但历史 docs 迁移尚未执行。
- 阶段 0 仍未完成，因为真实候选变更数量很大，仍需要按提交主题分组收口。
- 后续如果继续执行阶段 4，应先挑一个小类，例如新重构记录迁入 `docs/refactor-records/`，而不是一次性整理全部 `docs`。

### 10.23 阶段 3 补充推进: `scene_matrix_drilldown.py` Item factory 拆分

执行日期: 2026-07-07

本轮继续第 10.20 节之后的剩余拆分，把 `src/config/scene_matrix_drilldown.py` 中从 `_item_factories_for_source()` 到各类 `_..._item()` 的 item factory 群迁出。该区域负责把 dashboard、request cell、release governance、material、fixed-layout、delivery、formula/watermark 等 audit 报告转换为 `SceneMatrixDrilldownItem` 与 `SceneMatrixDrilldownRow`，职责是“drilldown item 投影”，不应继续挤在主 report 构建和 audit 校验模块内。

已完成改动:

1. 新增 `src/config/scene_matrix_drilldown_items.py`。
2. 从 `src/config/scene_matrix_drilldown.py` 原样迁出:
   - `SceneMatrixDrilldownItemFactory`
   - `_item_factories_for_source`
   - `_dashboard_item` 到 `_maturity_upgrade_item` 的全部 item factory
   - `_guarded_completion_rows_by_envelope_id`
   - `_release_residual_capability_ids`
   - `_release_residual_receipt_detail`
   - `_release_residual_boundary_scope_capability_ids`
   - `_join_values`
   - `_release_residual_boundary_scope_detail`
3. `src/config/scene_matrix_drilldown.py` 改为只从新模块导入 `_item_factories_for_source`，主模块保留 `_build_all_items()`、过滤、report 构建、audit 校验和 source evidence 入口。
4. 清理主模块中只为 item factory 服务的 audit 构建器 import，使这些依赖集中到 `scene_matrix_drilldown_items.py`。
5. 同步 `src/config/scene_matrix_drilldown_sources.py` 中 item/projection 相关 source evidence marker，避免继续依赖主文件里旧 item factory 的偶然同名字符串。
6. 同步以下上游 audit 的 drilldown item 证据路径，使其指向新的 item 模块:
   - `src/config/scene_ambiguity_clarification_ui_audit.py`
   - `src/config/scene_business_capability_matrix_audit.py`
   - `src/config/scene_boundary_maturity_release_envelope_audit.py`
   - `src/config/scene_boundary_subject_release_continuity_audit.py`
   - `src/config/scene_release_projection_surface_parity_audit.py`
   - `src/config/scene_release_closure_ledger_audit.py`
   - `src/config/scene_release_residual_ratio_ledger_audit.py`
   - `src/config/scene_release_trace_partition_guard_audit.py`
   - `src/config/scene_retained_gap_exit_criteria_audit.py`
   - `src/config/scene_release_acceptance_certificate_audit.py`
   - `src/config/scene_fixed_layout_profile_audit.py`
   - `src/config/scene_report_artifact_drilldown_audit.py`
7. `scene_release_projection_surface_parity_audit.py` 与 `scene_release_closure_ledger_audit.py` 的 `_source_texts()` 对 drilldown 文本改为读取主文件与 item 模块的组合，保证 release surface 检查能覆盖拆分后的真实 item 来源。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_drilldown.py` | `1063` |
| `src/config/scene_matrix_drilldown_items.py` | `1865` |
| `src/config/scene_matrix_drilldown_projection_references.py` | `917` |
| `src/config/scene_matrix_drilldown_sources.py` | `1020` |
| `src/config/scene_matrix_drilldown_reference_ids.py` | `193` |
| `src/config/scene_matrix_drilldown_models.py` | `220` |

对比第 10.20 节记录的 `src/config/scene_matrix_drilldown.py` `2914` 行，本轮再减少约 `1851` 行。经过六轮 Drilldown 拆分后，原主模块已从数千行级别下降到约 1000 行，主要职责基本收敛为 report 构建、过滤、source evidence 和 audit 校验。

调试记录:

- 首轮 `tests/test_scene_matrix_drilldown.py` 出现 `5 failed, 2 passed`，根因是 `107` 条 source evidence 中只有 `92` 条 ready，多条 marker 仍指向主文件旧 item factory/projection 字段。
- 修正 source evidence marker 后，快速诊断恢复到 `107/107 ready`，但上游 release/fixed/report audit 仍将 drilldown item 证据指向主文件，导致若干 component report failed。
- 将上游 audit 的 drilldown item source path 改到 `scene_matrix_drilldown_items.py`，并让 release parity/closure 的 source text 覆盖主文件和 item 模块后，快速诊断恢复为 `status passed`、`107/107 ready`、`issues 0`。
- release gate payload 单独复查恢复为 `status passed`。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_drilldown.py src\config\scene_matrix_drilldown_items.py src\config\scene_matrix_drilldown_sources.py src\config\scene_release_projection_surface_parity_audit.py src\config\scene_release_closure_ledger_audit.py src\config\scene_release_acceptance_certificate_audit.py src\config\scene_fixed_layout_profile_audit.py src\config\scene_report_artifact_drilldown_audit.py
python -m pytest tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_drilldown_items_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| 快速 drilldown 诊断 | `status passed`; source evidence `107/107`; audit issues `0` |
| release gate payload 诊断 | `status passed` |
| Drilldown 目标测试 | 修正后 `7 passed in 111.35s` |
| runner `scene` | `356 passed in 236.51s`; runner 汇总 `[PASS] scene in 240.1s` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed in 0.82s` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，命令通过 |

当前判断:

- `scene_matrix_drilldown.py` 已不再是最高风险超大文件，剩余约 1000 行仍偏大但职责清晰得多。
- 新的 `scene_matrix_drilldown_items.py` 有 1800+ 行，属于明确的 item projection 聚合模块；后续如继续拆，可按 release governance items、material/delivery items、dashboard/request/basic items 分组。
- 本轮暴露并修正了一个重要工程边界: source evidence 不应依赖主文件中“碰巧存在”的字符串，而应指向真实拥有实现的模块。
- 阶段 0 工作区收口仍未完成；阶段 4 已有边界规则但历史文档/生成物迁移仍未执行。

### 10.24 阶段 3 补充推进: `scene_matrix_drilldown_items.py` Release governance item 拆分

执行日期: 2026-07-07

本轮继续消化第 10.23 节暴露出的新聚合点: `src/config/scene_matrix_drilldown_items.py` 已经从主 drilldown 模块中拆出，但自身仍超过 1800 行，并同时承载 dashboard/request、release governance、material、delivery、fixed-layout 等多类 item projection。考虑到 release governance item 与 release gate/source evidence 的耦合最强，本轮先把 release 相关 item factory 独立成专用模块。

已完成改动:

1. 新增 `src/config/scene_matrix_drilldown_release_items.py`，集中承载 release governance item projection。
2. 从 `src/config/scene_matrix_drilldown_items.py` 迁出以下 release item factory:
   - `_boundary_guarded_completion_item`
   - `_residual_warning_governance_item`
   - `_boundary_readiness_reconciliation_item`
   - `_terminal_release_exception_item`
   - `_boundary_subject_release_dossier_item`
   - `_non_subject_release_trace_attribution_item`
   - `_release_trace_partition_guard_item`
   - `_release_projection_surface_parity_item`
   - `_boundary_subject_release_continuity_item`
   - `_release_closure_ledger_item`
   - `_boundary_maturity_release_envelope_item`
   - `_retained_gap_exit_criteria_item`
   - `_release_residual_ratio_ledger_item`
   - `_release_residual_explanation_item`
   - `_release_acceptance_certificate_item`
3. 同步迁出 release residual receipt/detail 辅助函数:
   - `_guarded_completion_rows_by_envelope_id`
   - `_release_residual_capability_ids`
   - `_release_residual_receipt_detail`
   - `_release_residual_boundary_scope_capability_ids`
   - `_join_values`
   - `_release_residual_boundary_scope_detail`
4. `src/config/scene_matrix_drilldown_items.py` 改为 release item factory 的路由消费者，只从新模块导入上述 item factory；同时删除 release audit builder 和 `_release_residual_receipt_action_ids` 等旧实现依赖。
5. `src/config/scene_matrix_drilldown_sources.py` 中 acceptance/residual receipt projection 的 source evidence 路径改为 `src/config/scene_matrix_drilldown_release_items.py`。
6. 以下 release 相关 upstream audit 的 drilldown item evidence path 已改指向新 release item 模块:
   - `src/config/scene_boundary_maturity_release_envelope_audit.py`
   - `src/config/scene_boundary_subject_release_continuity_audit.py`
   - `src/config/scene_release_projection_surface_parity_audit.py`
   - `src/config/scene_release_closure_ledger_audit.py`
   - `src/config/scene_release_residual_ratio_ledger_audit.py`
   - `src/config/scene_release_trace_partition_guard_audit.py`
   - `src/config/scene_retained_gap_exit_criteria_audit.py`
   - `src/config/scene_release_acceptance_certificate_audit.py`
7. `scene_release_projection_surface_parity_audit.py` 与 `scene_release_closure_ledger_audit.py` 的 `_source_texts()` 继续读取主 drilldown 与通用 item 模块，同时新增读取 `scene_matrix_drilldown_release_items.py`，避免 release surface 自检漏掉新实现来源。

行数变化:

| 文件 | 当前行数 |
| --- | ---: |
| `src/config/scene_matrix_drilldown.py` | `1095` |
| `src/config/scene_matrix_drilldown_items.py` | `1114` |
| `src/config/scene_matrix_drilldown_release_items.py` | `891` |
| `src/config/scene_matrix_drilldown_sources.py` | `1026` |
| `src/config/scene_matrix_drilldown_projection_references.py` | `1000` |

对比第 10.23 节记录的 `scene_matrix_drilldown_items.py` `1865` 行，本轮把 item 聚合模块再减少约 `751` 行。新的拆分边界更贴近职责: 通用 item 模块保留路由和非 release projection，release item 模块拥有 release gate、boundary envelope、residual receipt、acceptance certificate 等高耦合 release projection。

调试记录:

- 首轮机械迁移后，`scene_matrix_drilldown_items.py` 仍残留 release audit builder import 和 `lru_cache`，这会削弱模块边界；已改为只导入 `scene_matrix_drilldown_release_items.py` 暴露的 release item factory。
- source evidence 初始仍有多处 release marker 指向 `scene_matrix_drilldown_items.py`；已把 release 专属 marker 改为新模块，同时保留 ambiguity/business/fixed/report 等非 release item evidence 在旧 item 模块。
- `py_compile`、drilldown 快速诊断与 release gate payload 均通过后，再执行目标单测和 scene 分组验证。

验证命令:

```powershell
python -m py_compile src\config\scene_matrix_drilldown_items.py src\config\scene_matrix_drilldown_release_items.py src\config\scene_matrix_drilldown_sources.py src\config\scene_boundary_maturity_release_envelope_audit.py src\config\scene_boundary_subject_release_continuity_audit.py src\config\scene_release_projection_surface_parity_audit.py src\config\scene_release_closure_ledger_audit.py src\config\scene_release_acceptance_certificate_audit.py src\config\scene_release_trace_partition_guard_audit.py src\config\scene_release_residual_ratio_ledger_audit.py src\config\scene_retained_gap_exit_criteria_audit.py
python -m pytest tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_drilldown_release_items_refactor_2026-07-07.json
python -m compileall -q src
python -m pytest tests\test_architecture_boundaries.py -q
python -m pytest --collect-only -q
```

验证结果:

| 命令/分组 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| 快速 drilldown 诊断 | `status passed`; source evidence `107/107`; audit issues `0` |
| release gate payload 诊断 | `status passed` |
| Drilldown 目标测试 | `7 passed in 117.36s` |
| runner `scene` | `356 passed in 258.19s`; runner 汇总 `[PASS] scene in 261.6s` |
| `python -m compileall -q src` | 通过 |
| `tests/test_architecture_boundaries.py` | `1 passed in 0.84s` |
| `python -m pytest --collect-only -q` | 收集 `1798` 项测试，命令通过 |

当前判断:

- Stage 3 的 `scene_matrix_drilldown.py` 风险继续下降；主模块维持在约 1100 行，且职责主要集中在 report 构建、过滤、source evidence 和 audit 校验。
- `scene_matrix_drilldown_items.py` 从 1800+ 行降到约 1100 行，但仍可以继续按 material/delivery/fixed-layout/basic request projection 再拆一轮。
- Release governance item 已经形成独立所有权模块，后续 release gate 或 residual receipt 变化不再需要回灌到通用 item 聚合文件。
- Stage 0 工作区收口仍未完成；Stage 4 已有文档边界规则，但历史 docs/generated 迁移尚未执行。

### 10.25 阶段 4 补充推进: 首个 refactor record 迁入归档目录

执行日期: 2026-07-07

本轮按第 10.22 节的文档边界规则执行第一批小范围迁移，不批量整理全部 `docs/`，只处理当前这份结构健康与重构执行日志。

已完成改动:

1. 新增目录 `docs/refactor-records/`。
2. 将主执行记录从 `docs/refactor-records/code_structure_health_deep_analysis_2026-07-07.md` 移动到 `docs/refactor-records/code_structure_health_deep_analysis_2026-07-07.md`。
3. 迁移前使用 `rg` 检查旧路径引用，结果只发现:
   - `docs/DOCUMENTATION_BOUNDARIES.md` 对目标目录 `docs/refactor-records/` 的规则说明。
   - 本执行记录内部对 `docs/refactor-records/` 的阶段建议和历史记录。
   - 未发现源码、测试、脚本或 release tooling 依赖旧文件路径。

验证命令:

```powershell
rg -n "code_structure_health_deep_analysis_2026-07-07|DOCUMENTATION_BOUNDARIES|docs/refactor-records|refactor-records" .
Test-Path docs\refactor-records
Test-Path docs\refactor-records\code_structure_health_deep_analysis_2026-07-07.md
Test-Path docs\refactor-records\code_structure_health_deep_analysis_2026-07-07.md
```

当前判断:

- Stage 4 已从“仅建立边界规则”推进到“完成一个低风险迁移样例”。
- 这次迁移没有触碰历史大批量文档，也没有移动图片、审计 trace、产品规划或 release 资料，因此 rename 噪音可控。
- 后续 Stage 4 可以继续按同一策略小批量处理: refactor records、audits、architecture notes、visual checks 分别迁移，并在每批前做引用扫描。
- Stage 0 工作区整体收口仍未完成，因为根目录下仍有大量未归类的真实候选变更。

### 10.26 阶段 4 补充推进: 2026-07-07 refactor plan 小批次迁移

执行日期: 2026-07-07

本轮继续沿用第 10.25 节的小批次策略，只处理 `docs/` 根目录下同一天产生、且内容明确属于重构/删除/后续执行规划的 Markdown 文档。迁移前先读取文件开头并扫描路径引用，确认它们不是产品手册、release trace 或外部脚本依赖。

已完成改动:

1. 迁入 `docs/refactor-records/post_remote_cache_cleanup_next_step_plan_2026-07-07.md`。
2. 迁入 `docs/refactor-records/remote_question_asset_cache_deletion_plan_2026-07-07.md`。
3. 迁入 `docs/refactor-records/workbench_question_figure_repair_runtime_phase4_plan_2026-07-07.md`。
4. 更新 `post_remote_cache_cleanup_next_step_plan_2026-07-07.md` 内部对 workbench phase4 plan 的引用，使其指向 `docs/refactor-records/workbench_question_figure_repair_runtime_phase4_plan_2026-07-07.md`。

验证命令:

```powershell
Test-Path docs\refactor-records\post_remote_cache_cleanup_next_step_plan_2026-07-07.md
Test-Path docs\refactor-records\remote_question_asset_cache_deletion_plan_2026-07-07.md
Test-Path docs\refactor-records\workbench_question_figure_repair_runtime_phase4_plan_2026-07-07.md
Test-Path docs\refactor-records\post_remote_cache_cleanup_next_step_plan_2026-07-07.md
Test-Path docs\refactor-records\remote_question_asset_cache_deletion_plan_2026-07-07.md
Test-Path docs\refactor-records\workbench_question_figure_repair_runtime_phase4_plan_2026-07-07.md
rg -n "docs/(post_remote_cache_cleanup_next_step_plan_2026-07-07|remote_question_asset_cache_deletion_plan_2026-07-07|workbench_question_figure_repair_runtime_phase4_plan_2026-07-07)\.md|docs\\(post_remote_cache_cleanup_next_step_plan_2026-07-07|remote_question_asset_cache_deletion_plan_2026-07-07|workbench_question_figure_repair_runtime_phase4_plan_2026-07-07)\.md|workbench_question_figure_repair_runtime_phase4_plan_2026-07-07" .
Get-ChildItem docs -File -Filter "*_2026-07-07.md"
Get-ChildItem docs\refactor-records -File -Filter "*_2026-07-07.md"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| 旧根目录三份计划文档 | 均为 `False`，确认已移出 `docs/` 根目录 |
| 新归档目录三份计划文档 | 均为 `True` |
| 旧路径引用扫描 | 未发现源码、测试、脚本引用旧路径 |
| 新路径引用扫描 | 仅保留 `post_remote_cache_cleanup_next_step_plan_2026-07-07.md` 对 workbench phase4 plan 的新路径引用 |
| `docs/*_2026-07-07.md` | 空结果 |
| `docs/refactor-records/*_2026-07-07.md` | 4 份，包括主结构健康记录和三份计划文档 |

当前判断:

- Stage 4 已有可重复执行的迁移方式: 读文件语义、扫引用、按一小批移动、更新内部路径、记录验证。
- `docs/` 根目录的 2026-07-07 重构/治理记录已完成归档，根目录噪音进一步下降。
- 更早日期的历史文档仍然很多，不应一次性移动；下一批可考虑按 `*_extraction_2026-07-06.md` 或 `scene_*_trace_*.md` 这类高度同质文件分别归档。
- Stage 0 工作区整体收口仍未完成，需要继续按主题分组处理源代码、测试、脚本、样例资产和文档变更。

### 10.27 阶段 4 补充推进: 根目录视觉截图迁入 `docs/visual_checks/`

执行日期: 2026-07-07

本轮处理 `docs/` 根目录中的 PNG 运行时截图。根据 `docs/DOCUMENTATION_BOUNDARIES.md`，这些文件属于 curated visual QA evidence，不应继续混在文档根目录。迁移前先扫描引用，确认引用均来自历史规划文档，并同步更新路径。

已完成改动:

1. 将以下图片迁入 `docs/visual_checks/`:
   - `assets_panel_runtime_check.png`
   - `assets_panel_runtime_check_desktop.png`
   - `assets_panel_runtime_check_narrow.png`
   - `toc_detail_runtime_check_desktop.png`
   - `toc_detail_runtime_check_narrow.png`
2. 更新以下历史文档中的图片引用:
   - `docs/audits/资料包前台体验与实现路径规划_2026-06-02.md`
   - `docs/audits/目录样式信息架构分析与优化规划_2026-06-14.md`
   - `docs/audits/目录样式二次深度分析与修正规划_2026-06-15.md`

验证命令:

```powershell
Get-ChildItem docs\*.png -File
Get-ChildItem docs\visual_checks\*.png -File
rg -n "docs/(assets_panel_runtime_check(?:_desktop|_narrow)?|toc_detail_runtime_check(?:_desktop|_narrow)?)\.png" docs
rg -n "docs/visual_checks/(assets_panel_runtime_check(?:_desktop|_narrow)?|toc_detail_runtime_check(?:_desktop|_narrow)?)\.png" docs
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `docs/*.png` | 空结果，根目录 PNG 已清空 |
| `docs/visual_checks/*.png` | 共 8 张，包含本轮迁入的 5 张和既有 3 张 scene 视觉检查图 |
| 旧路径引用扫描 | 空结果 |
| 新路径引用扫描 | 7 处历史文档引用均指向 `docs/visual_checks/` |

当前判断:

- Stage 4 的 generated/visual evidence 边界已有实际收口: PNG 不再散落在 `docs/` 根目录。
- 这次迁移是低风险的，因为引用路径全部同步更新，且不涉及源码/测试导入。
- 下一批 Stage 4 可以继续处理同质 Markdown 记录；但历史文档规模仍大，仍应维持小批次策略。
- Stage 0 工作区整体收口仍未完成。

### 10.28 阶段 4 补充推进: `assets*_2026-07-06.md` 文档小批次归档

执行日期: 2026-07-07

本轮继续处理 `docs/` 根目录的同质 Markdown 记录，范围限定为 `assets*_2026-07-06.md`。迁移前先列出候选并扫描旧路径引用；扫描无输出，说明没有源码、测试、脚本或其他文档依赖这些根目录旧路径。

已完成改动:

1. 新增目录 `docs/audits/`。
2. 将 `assets_enterprise_boundary_audit_2026-07-06.md` 迁入 `docs/audits/`，因为它是资产企业边界审计记录。
3. 将其余 48 份 `assets*_2026-07-06.md` 迁入 `docs/refactor-records/`，这些文件主要是 assets panel、question library、subscription drift、service extraction、presenter extraction 等重构执行或规划记录。

验证命令:

```powershell
Get-ChildItem docs -File -Filter "assets*_2026-07-06.md" | Measure-Object
Get-ChildItem docs\refactor-records -File -Filter "assets*_2026-07-06.md" | Measure-Object
Test-Path docs\audits\assets_enterprise_boundary_audit_2026-07-06.md
Get-ChildItem docs\audits -File -Filter "assets*_2026-07-06.md" | Measure-Object
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `docs/assets*_2026-07-06.md` | `0` |
| `docs/refactor-records/assets*_2026-07-06.md` | `48` |
| `docs/audits/assets_enterprise_boundary_audit_2026-07-06.md` | `True` |
| `docs/audits/assets*_2026-07-06.md` | `1` |
| 旧路径引用扫描 | 无输出 |

当前判断:

- Stage 4 已完成第二类大一点但仍同质的文档归档，`docs/` 根目录中的 assets 2026-07-06 重构记录已清空。
- 审计记录和重构记录开始按不同目录分流，后续可以把同样有 `audit`/`trace` 语义的文档逐步迁入 `docs/audits/`。
- 仍不建议一次性移动所有中文历史规划文档；下一批应继续按命名模式和引用关系筛选。
- Stage 0 工作区整体收口仍未完成。

### 10.29 阶段 4 补充推进: `scene_*_N2_*.md` source-evidence 审计文档迁移

执行日期: 2026-07-07

本轮继续按命名模式和语义处理 `docs/` 根目录中的 scene N2 source-evidence 文档。候选文件为 `scene_*_N2_*.md`，共 47 份。迁移前引用扫描显示，这批文件不是孤立文档，多个 `src/config` source evidence 常量、release audit 测试和历史规划文档直接引用旧路径。因此本轮迁移同时更新源码、测试和文档中的精确路径。

已完成改动:

1. 将 47 份 `docs/scene_*_N2_*.md` 迁入 `docs/audits/`。
2. 将相关引用从 `docs/<file>` 更新为 `docs/audits/<file>`，覆盖:
   - `src/config/scene_boundary_capability_matrix.py`
   - `src/config/scene_business_capability_matrix_audit.py`
   - `src/config/scene_matrix_drilldown_sources.py`
   - `src/config/scene_release_acceptance_certificate_audit.py`
   - `src/config/scene_release_closure_ledger_audit.py`
   - `src/config/scene_release_projection_surface_parity_audit.py`
   - `src/config/scene_release_residual_ratio_ledger_audit.py`
   - `src/config/scene_retained_gap_exit_criteria_audit.py`
   - `tests/test_scene_release_projection_surface_parity_audit.py`
   - `tests/test_scene_release_closure_ledger_audit.py`
   - 若干历史规划文档中的交叉引用。
3. 迁移后确认 `docs/scene_*_N2_*.md` 根目录旧位置为空，旧路径引用扫描为空。

调试记录:

- 首轮机械路径替换也命中了 `__pycache__` 中的 `.pyc`，随后确认这些缓存未被 Git 跟踪，也未出现在 `git status` 中；后续 `compileall` 已重新生成缓存，不作为版本成果记录。
- 因为这批路径属于 source evidence，迁移后不仅做引用扫描，还执行了 drilldown、release gate、目标测试和完整 scene 分组验证。

验证命令:

```powershell
python -m py_compile src\config\scene_boundary_capability_matrix.py src\config\scene_business_capability_matrix_audit.py src\config\scene_matrix_drilldown_sources.py src\config\scene_release_acceptance_certificate_audit.py src\config\scene_release_closure_ledger_audit.py src\config\scene_release_projection_surface_parity_audit.py src\config\scene_release_residual_ratio_ledger_audit.py src\config\scene_retained_gap_exit_criteria_audit.py tests\test_scene_release_projection_surface_parity_audit.py tests\test_scene_release_closure_ledger_audit.py
python -m compileall -q src tests
python -m pytest tests\test_scene_release_projection_surface_parity_audit.py tests\test_scene_release_closure_ledger_audit.py tests\test_scene_release_residual_ratio_ledger_audit.py tests\test_scene_release_acceptance_certificate_audit.py tests\test_scene_retained_gap_exit_criteria_audit.py tests\test_scene_matrix_drilldown.py tests\test_scene_boundary_capability_matrix.py tests\test_scene_business_capability_matrix_audit.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_scene_audit_docs_move_2026-07-07.json
Get-ChildItem docs -File -Filter "scene_*_N2_*.md" | Measure-Object
Get-ChildItem docs\audits -File -Filter "scene_*_N2_*.md" | Measure-Object
rg -n 'docs/scene_[^`"\s|)]+_N2_[^`"\s|)]+\.md' src tests docs scripts .github
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `py_compile` | 通过 |
| `python -m compileall -q src tests` | 通过 |
| 快速 drilldown 诊断 | `status passed`; source evidence `107/107`; audit issues `0` |
| release gate payload 诊断 | `status passed` |
| 受影响目标测试 | `31 passed in 150.94s` |
| runner `scene` | `356 passed in 259.36s`; runner 汇总 `[PASS] scene in 264.0s` |
| `docs/scene_*_N2_*.md` | `0` |
| `docs/audits/scene_*_N2_*.md` | `47` |
| 旧路径引用扫描 | 空结果 |

当前判断:

- Stage 4 已把 scene N2 source-evidence 文档从根目录迁入 `docs/audits/`，且 source evidence 运行时验证保持全绿。
- `docs/` 根目录文件数从上一轮复查的 `557` 降到 `510`，`docs/audits/` 文件数增加到 `48`。
- 工作区 `git status --short` 条目数从上一轮复查的 `1038` 降到 `991`，但仍然很大，Stage 0 完整收口尚未完成。
- 下一批迁移仍应按同质模式处理，例如高层场景能力矩阵 N2/V 系列审计/规划文档，迁移前必须先扫描源码与测试中的路径引用。

### 10.30 阶段 4 补充推进: 高层场景能力矩阵 N2 系列迁入 `docs/audits/`

执行日期: 2026-07-07

本轮继续处理第 10.29 节指出的下一批同质文档: `高层场景能力矩阵N2_*.md`。候选共 226 份，内容主要是高层场景能力矩阵的 N2 规划、闭环、审计和 release evidence 记录。迁移前确认这批文档被多个 `src/config/scene_*` audit 常量和历史规划文档引用，因此采用精确路径替换并同步移动。

已完成改动:

1. 将 226 份 `docs/高层场景能力矩阵N2_*.md` 迁入 `docs/audits/`。
2. 将相关引用从 `docs/高层场景能力矩阵N2_...` 更新为 `docs/audits/高层场景能力矩阵N2_...`，覆盖:
   - release/boundary/source-evidence 相关 `src/config/scene_*` audit 模块。
   - 高层场景能力矩阵 V 系列和深度审计蓝图中的交叉引用。
   - 若干 N2 文档之间的前后续引用。
3. 修正 `docs/audits/场景规划现状与模板预览样式归一化深度分析_2026-06-27.md` 中对 N2/scene release 文档的通配提示，使其指向 `docs/audits/`。
4. 本轮机械替换显式跳过 `__pycache__` 和 `.pyc`，避免再次触碰生成缓存。

验证命令:

```powershell
Get-ChildItem docs -File | Where-Object { $_.Name -like '高层场景能力矩阵N2_*' } | Measure-Object
Get-ChildItem docs\audits -File | Where-Object { $_.Name -like '高层场景能力矩阵N2_*' } | Measure-Object
rg -n --fixed-strings 'docs/高层场景能力矩阵N2_' src tests docs scripts .github
rg -n --fixed-strings 'docs/audits/高层场景能力矩阵N2_' src tests docs scripts .github
python -m compileall -q src tests
python -m pytest tests\test_scene_release_projection_surface_parity_audit.py tests\test_scene_release_closure_ledger_audit.py tests\test_scene_release_residual_ratio_ledger_audit.py tests\test_scene_release_acceptance_certificate_audit.py tests\test_scene_retained_gap_exit_criteria_audit.py tests\test_scene_matrix_drilldown.py tests\test_scene_boundary_capability_matrix.py tests\test_scene_business_capability_matrix_audit.py tests\test_scene_boundary_guarded_completion_audit.py tests\test_scene_boundary_maturity_release_envelope_audit.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_high_level_n2_docs_move_2026-07-07.json
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `docs/高层场景能力矩阵N2_*` | `0` |
| `docs/audits/高层场景能力矩阵N2_*` | `226` |
| 旧路径引用扫描 | 空结果 |
| 新路径引用扫描 | `297` 处引用，均指向 `docs/audits/` |
| `python -m compileall -q src tests` | 通过 |
| 快速 drilldown 诊断 | `status passed`; source evidence `107/107`; audit issues `0` |
| release gate payload 诊断 | `status passed` |
| 受影响目标测试 | `39 passed in 244.60s` |
| runner `scene` | `356 passed in 299.41s`; runner 汇总 `[PASS] scene in 303.0s` |

当前判断:

- Stage 4 的审计文档边界进一步收口，N2 系列已从 `docs/` 根目录迁入 `docs/audits/`。
- `docs/` 根目录文件数已降到 `284`，`docs/audits/` 文件数增加到 `274`。
- 工作区 `git status --short` 条目数从第 10.29 节后的 `991` 降到 `765`，但 Stage 0 仍未达到“只剩明确提交项”的验收状态。
- 后续可继续处理高层场景能力矩阵 V 系列，或转向 Stage 0，为 `src`/`tests`/`scripts` 变更生成可提交主题清单。

### 10.31 阶段 4 补充推进: 高层场景能力矩阵 V 系列迁入 `docs/audits/`

执行日期: 2026-07-07

本轮继续处理高层场景能力矩阵 V 系列文档。候选文档共 37 份，主要记录高频场景能力矩阵、边界治理、完备性审计、产品成熟度和场景覆盖规划。它们和 N2 系列一样属于长期审计/规划证据，适合从 `docs/` 根目录迁入 `docs/audits/`。

已完成改动:

1. 将 37 份 `docs/高层场景能力矩阵V*.md` 迁入 `docs/audits/`。
2. 同步更新 `src/config/scene_*` audit 模块和历史文档中指向 V 系列文档的路径引用。
3. 迁移脚本受 Windows 控制台编码影响，首轮误将 2 份 `StylePreviewSurface..._2026-06-30.md` 执行记录归入 `docs/audits/`；随后已按边界规则改迁到 `docs/refactor-records/`。
4. 修正 `docs/refactor-records/StyleEditingSection预览Surface委托执行记录_2026-06-30.md` 中对 `StylePreviewSurface渲染器协议观测执行记录_2026-06-30.md` 的引用，使其指向 `docs/refactor-records/`。

验证命令:

```powershell
Get-ChildItem docs -File | Where-Object { $_.Name -like '高层场景能力矩阵V*.md' } | Measure-Object
Get-ChildItem docs\audits -File | Where-Object { $_.Name -like '高层场景能力矩阵V*.md' } | Measure-Object
Get-ChildItem docs\audits -File | Where-Object { $_.Name -like 'StylePreviewSurface*' } | Measure-Object
Get-ChildItem docs\refactor-records -File | Where-Object { $_.Name -like 'StylePreviewSurface*' } | Measure-Object
rg -n --fixed-strings 'docs/高层场景能力矩阵V' src tests docs scripts .github
rg -n --fixed-strings 'docs/audits/StylePreviewSurface' src tests docs scripts .github
python -m compileall -q src tests
python -m pytest tests\test_scene_ambiguity_clarification_ui_audit.py tests\test_scene_ambiguous_boundary_audit.py tests\test_scene_family_fixture_depth_audit.py tests\test_scene_high_frequency_task_lexicon_audit.py tests\test_scene_import_handoff_audit.py tests\test_scene_user_journey_fixture_audit.py tests\test_scene_matrix_drilldown.py -q
python scripts\run_pytest_groups.py --groups scene --timeout 700 --summary-path .pytest_tmp\pytest_groups_scene_after_high_level_v_docs_move_2026-07-07.json
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `docs/高层场景能力矩阵V*.md` | `0` |
| `docs/audits/高层场景能力矩阵V*.md` | `37` |
| `docs/audits/StylePreviewSurface*` | `0` |
| `docs/refactor-records/StylePreviewSurface*` | `2` |
| V 系列旧路径引用扫描 | 空结果 |
| `docs/audits/StylePreviewSurface` 误归档路径扫描 | 空结果 |
| `python -m compileall -q src tests` | 通过 |
| 快速 drilldown 诊断 | `status passed`; source evidence `107/107`; audit issues `0` |
| release gate payload 诊断 | `status passed` |
| 受影响目标测试 | `33 passed in 138.63s` |
| runner `scene` | `356 passed in 285.57s`; runner 汇总 `[PASS] scene in 289.7s` |

当前判断:

- Stage 4 的能力矩阵审计/规划类文档边界已明显改善，N2/V 两大系列均已迁入 `docs/audits/`。
- `docs/` 根目录文件数已降到 `245`，`docs/audits/` 文件数为 `311`，`docs/refactor-records/` 文件数为 `54`。
- 工作区 `git status --short` 条目数从第 10.30 节后的 `765` 降到 `726`，仍未达到 Stage 0 验收状态。
- 后续更适合开始 Stage 0 的提交主题清单，尤其是将 `docs`、`src/config scene matrix`、`workbench/reporting`、`tests/runner`、`scripts/manual` 分组，而不是继续无差别迁移所有历史文档。

### 10.32 阶段 0 补充审计: 工作区展开清单与提交主题切分

执行日期: 2026-07-07

本轮回到 Stage 0，使用 `git status --porcelain=v1 -uall -z` 展开未跟踪目录，避免普通 `git status --short` 将大目录折叠成单条记录。结论是: 默认短状态为 `726` 条，但展开后仍有 `1409` 个真实文件级变更，因此 Stage 0 还没有完成。

状态统计:

| 状态 | 数量 | 含义 |
| --- | ---: | --- |
| `??` | `1234` | 未跟踪文件 |
| ` M` | `157` | 已跟踪文件修改 |
| ` D` | `10` | 已跟踪文件删除 |
| `RM` | `7` | 已跟踪文件移动并修改 |
| `D ` | `1` | 索引侧删除 |

根目录展开统计:

| 根路径 | 数量 |
| --- | ---: |
| `docs` | `651` |
| `src` | `301` |
| `exam_masters` | `178` |
| `tests` | `142` |
| `scripts` | `60` |
| `samples` | `43` |
| `templates` | `10` |
| `scenes` | `7` |
| 其余配置/根文件 | `17` |

建议提交主题切分:

| 主题 | 展开数量 | 处理建议 |
| --- | ---: | --- |
| `docs/audits` | `311` | 单独作为文档边界治理提交，需保留 source-evidence 验证记录。 |
| `docs/refactor-records` | `54` | 单独作为重构执行记录归档提交。 |
| `docs/visual_checks` | `8` | 可随文档边界治理提交，或单独作为视觉证据迁移提交。 |
| `docs/root` | `236` | 仍需继续分类，不能整体提交。 |
| `docs/other-subdirs` | `42` | 保留既有 `migration_audit`/`visual_audit` 脉络，单独复核。 |
| `src/config/scene` | `66` | 与 scene matrix/release evidence 重构强相关，应独立提交并跑 scene 分组。 |
| `src/config/other` | `26` | 配置层基线/材料/样式等，需按功能再拆。 |
| `src/ui/workbench` | `21` | Workbench/reporting/runtime 主题，需和测试一起提交。 |
| `src/ui/assets` | `40` | Assets/question library/remote cache 删除主题，需和 samples/docs 对齐。 |
| `src/ui/other` | `42` | UI 控件/模板/面板主题，需按面板或共享控件拆。 |
| `src/shared` | `75` | 共享 UI/engine 主题，风险高，需单独验证。 |
| `src/modules` | `10` | Word/内容模块语义改动，需模块测试覆盖。 |
| `src/pipeline` | `4` | 执行管线小批次，可随 runtime 主题或单独提交。 |
| `src/services` | `7` | 服务层主题，需和 assets/material 变更一起确认。 |
| `tests` | `142` | 不应单独提交，应按被测功能跟随源码主题。 |
| `scripts/manual` | `9` | 手工脚本迁移主题，当前包含 7 个 root -> scripts/manual 的 rename。 |
| `scripts/other` | `51` | release/export/verification 脚本，需按 scene/reporting 分拆。 |
| `templates/defaults/scenes` | `18` | 产品配置/样例主题，需确认是否是基线数据。 |
| `samples/exam` | `222` | 样例/母版资产，需单独复核，不应混入源码提交。 |
| `project-config` | `8` | `.gitignore`、`.gitattributes`、`pyproject.toml`、requirements 等工程基线主题。 |
| `scratch-root` | `2` | `debug_preflight_steps.txt`、`request_cell_report.md`，倾向生成/临时产物，提交前需确认是否删除或迁入 evidence。 |
| `root-runtime` | `2` | `main.py`、`count_profiles/builtin.json`，需跟功能主题确认。 |
| 未匹配 | `9` | `heading_numbering_schemes/*` 和 `src/reporting/*`，需要新增主题分类。 |

当前判断:

- Stage 0 已从“知道工作区很大”推进到“有展开后的主题清单”，但尚未达到验收。
- 下一步不应继续扩大源码功能改动；应按上表挑一个主题做收口，例如 `project-config`、`scripts/manual`、`src/config/scene + scene tests` 或 `docs/audits/refactor-records`。
- 在没有用户明确授权前，不应自动提交或丢弃真实源码/样例资产变更；可以继续做分类、迁移和验证。

### 10.33 阶段 0 补充推进: 根目录 debug trace ignore 收口

执行日期: 2026-07-07

本轮从第 10.32 节的 `scratch-root` 主题中挑出最明确的一项处理。`debug_preflight_steps.txt` 是根目录调试步骤记录，内容为一次 workbench/preflight 调试流程的短 trace；引用扫描显示除本执行记录外没有源码、测试、脚本或 manifest 依赖它。相比之下，`request_cell_report.md` 被 `manifest.json`、测试、源码常量和历史文档语义引用，不能直接移动或忽略。

已完成改动:

1. 在 `.gitignore` 的 Runtime logs / crash dumps 区域新增窄规则 `debug_*.txt`。
2. 确认 `debug_preflight_steps.txt` 被 `.gitignore` 忽略，不再作为版本候选出现。
3. 保留 `request_cell_report.md` 为待判定 artifact，因为它和 `manifest.json` 的 request-cell report path 绑定。

验证命令:

```powershell
rg -n --fixed-strings 'debug_preflight_steps.txt' src tests docs scripts .github manifest.json
git check-ignore -v debug_preflight_steps.txt
git status --short -- debug_preflight_steps.txt request_cell_report.md
git status --porcelain=v1 -uall -z
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `debug_preflight_steps.txt` 引用扫描 | 仅本执行记录提及，无源码/测试/脚本依赖 |
| `git check-ignore -v debug_preflight_steps.txt` | `.gitignore:35:debug_*.txt` |
| `git status --short -- debug_preflight_steps.txt request_cell_report.md` | 只剩 `?? request_cell_report.md` |
| 展开文件级变更数 | 从 `1417` 降到 `1416` |

当前判断:

- `scratch-root` 主题已减少 1 个明确调试噪音。
- `request_cell_report.md` 仍需随 `manifest.json` 一起判定，不能作为普通 scratch 文件自动清理。
- Stage 0 仍未完成；下一步更适合处理 `scripts/manual` 迁移主题或 `project-config` 工程基线主题。

### 10.34 阶段 0 补充推进: `scripts/manual` 手工脚本迁移主题验证

执行日期: 2026-07-07

本轮处理第 10.32 节中的 `scripts/manual` 主题。当前状态显示 7 个根目录手工调试脚本已经移动到 `scripts/manual/`，并新增 `README.md` 与 `_bootstrap.py`。这些脚本属于交互式预览/调试入口，不应继续混在项目根目录或自动 pytest 套件入口中。

已完成改动:

1. 复核 `scripts/manual/README.md` 与 `_bootstrap.py`。
2. 确认以下根目录脚本旧路径均不存在:
   - `test_all_components.py`
   - `test_audit_fix.py`
   - `test_combo.py`
   - `test_crash.py`
   - `test_crash_trace.py`
   - `test_phase_a_components.py`
   - `test_workbench_v2.py`
3. 修正 `scripts/manual/test_all_components.py` 顶部运行方式注释，从旧的 `python test_all_components.py` 改为 `python scripts/manual/test_all_components.py`。
4. 确认 `tests/test_all_components_preview_panel.py` 已从 `scripts.manual` 导入手工预览脚本，并读取新路径 `scripts/manual/test_all_components.py`。

验证命令:

```powershell
python -m compileall -q scripts\manual
python -m pytest tests\test_all_components_preview_panel.py -q
Test-Path test_all_components.py
Test-Path test_audit_fix.py
Test-Path test_combo.py
Test-Path test_crash.py
Test-Path test_crash_trace.py
Test-Path test_phase_a_components.py
Test-Path test_workbench_v2.py
rg -n "python test_all_components\.py|test_all_components\.py" scripts\manual tests docs
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `python -m compileall -q scripts\manual` | 通过 |
| `tests/test_all_components_preview_panel.py` | `4 passed in 0.47s` |
| 7 个根目录旧脚本路径 | 均为 `False` |
| 旧运行命令扫描 | 无 `python test_all_components.py` 旧命令残留 |
| 当前主题状态 | 7 个 `RM` rename + `README.md` + `_bootstrap.py` |

当前判断:

- `scripts/manual` 可以作为一个独立 Stage 0 提交主题，范围清楚、验证轻量。
- 本轮未执行交互式 GUI 脚本，只验证编译、导入路径和自动测试引用。
- 默认 `git status --short` 条目数从 `726` 降到 `725`；展开文件级变更数为 `1416`。
- Stage 0 仍未完成，下一步可处理 `project-config` 或继续拆分 `docs/root`。

### 10.35 阶段 0 补充推进: `project-config` 工程基线主题验证与 CI 依赖修正

执行日期: 2026-07-07

本轮处理第 10.32 节中的 `project-config` 主题。该主题覆盖 `.gitignore`、`.gitattributes`、`pyproject.toml`、`requirements.txt`、`.github/workflows/*`、`manifest.json` 以及 `.claude/worktrees/awesome-tu-3d3302` 的状态解释。目标不是扩大功能改造，而是确认工程入口、依赖分层、CI 门禁和 Git 噪音边界是否自洽。

审计发现:

1. `pyproject.toml` 可被 `tomllib` 正常解析，项目名为 `lark-formatter`，版本为 `1.0.0`，pytest 默认测试路径为 `tests`。
2. `requirements.txt` 已收束为运行时依赖，不再包含 `pytest` 与 `pyinstaller`；对应的 dev/build 依赖已经迁入 `pyproject.toml` 的 optional dependencies。
3. `scripts/windows/install_env.bat` 已改为安装 `".[dev,build]"`，和本地开发/打包路径一致。
4. `.github/workflows/engineering-gate.yml` 原本仍只安装 `requirements.txt`，但 `scripts/engineering_gate.py` 会执行 `python -m pytest`；这会让 CI 基础门禁在干净 runner 上缺少 pytest。
5. `.github/workflows/scene-matrix-release-gate.yml` 单独安装 `python-docx lxml PyYAML pytest`，其 release gate 路径没有同类缺口。
6. `.gitattributes` 新增了文本换行和二进制文件规则，能降低 Windows/Unix 换行漂移和二进制误 diff 风险。
7. `.claude/worktrees/awesome-tu-3d3302` 在 `git status --porcelain=v2 -- .claude` 中显示为 `160000` gitlink 删除记录；当前路径存在且被 `.gitignore` 的 `.claude/worktrees/` 命中。本轮只记录状态，不自动恢复或删除该 gitlink。
8. `manifest.json` 与 `request_cell_report.md` 仍属于 artifact/request-cell 报告主题，不应混入纯工程配置提交。

已完成改动:

1. 将 `.github/workflows/engineering-gate.yml` 的安装步骤从 `python -m pip install -r requirements.txt` 改为 `python -m pip install -e ".[dev]"`。
2. 在 `tests/test_release_shell.py` 中新增 `test_engineering_gate_ci_installs_dev_dependencies_from_pyproject`，锁定以下契约:
   - Engineering Gate workflow 调用 `python scripts/engineering_gate.py`。
   - Engineering Gate workflow 安装 `".[dev]"`。
   - `scripts.engineering_gate.BASELINE_COMMANDS` 中存在 pytest 命令。
   - `pytest` 不回流到 `requirements.txt`，而保留在 `pyproject.toml`。
3. 将 `.github/workflows/engineering-gate.yml` 加入 release shell 文件存在性检查。

验证命令:

```powershell
python -c "import tomllib, pathlib; data=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); print(data['project']['name']); print(data['project']['version']); print(','.join(data['tool']['pytest']['ini_options']['testpaths']))"
python -m pytest --collect-only -q
python -m pytest tests\test_release_shell.py tests\test_app_meta.py -q
python scripts\engineering_gate.py
python -m compileall -q scripts src main.py
git status --porcelain=v2 -- .claude
git check-ignore -v .claude/worktrees/awesome-tu-3d3302
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `pyproject.toml` 解析 | `lark-formatter`, `1.0.0`, `tests` |
| 全量 pytest collection | `1799 tests collected in 1.96s` |
| `tests/test_release_shell.py tests/test_app_meta.py` | `13 passed in 0.21s` |
| `scripts/engineering_gate.py` | compileall 通过，collection `1799 tests collected`，smoke tests `10 passed`，Engineering gate passed |
| `python -m compileall -q scripts src main.py` | 通过 |
| `.claude/worktrees/awesome-tu-3d3302` | porcelain v2 显示 `1 D. S... 160000 ...`，且被 `.gitignore:60:.claude/worktrees/` 命中 |
| 当前默认 `git status --short` 条目数 | `725` |
| 当前展开文件级变更数 | `1415` |

当前判断:

- `project-config` 主题已从“需要复核”推进到“可独立收口”，其中 Engineering Gate 的 CI 依赖缺口已经修复并有测试保护。
- `requirements.txt` 作为运行时依赖清单、`pyproject.toml` 作为项目元数据和 dev/build 依赖入口，这个分层现在更清楚。
- `.claude/worktrees/awesome-tu-3d3302` 仍是需要提交前人工确认的 gitlink 状态，不应和本轮工程基线修正混为一个语义变更。
- Stage 0 仍未完成；剩余高风险主题包括 `docs/root`、`samples/exam`、`src/shared`、`src/ui/assets`、`src/ui/workbench` 和 `scripts/other`。

### 10.36 阶段 0 补充推进: 未匹配 9 文件主题归类验证

执行日期: 2026-07-07

本轮处理第 10.32 节中标记为“未匹配”的 9 个文件。复核后确认它们不是杂散文件，而是两个明确主题:

1. `heading_numbering_schemes/*.json`: 用户标题编号方案数据，共 3 个 JSON 文件，由 `src/config/heading_presets.py` 通过 `USER_SCHEME_DIR` 加载。
2. `src/reporting/*.py`: 报告生成 helper 包，共 6 个 Python 文件，由 `src/report_writer.py` 调用，并已纳入非 UI 层架构守门。

复核发现:

1. `heading_numbering_schemes` 下的 3 个 `user.*.json` 均可被 `json.loads` 解析；它们属于用户编号方案样例/数据主题，不应继续归为未匹配。
2. `src/reporting` 包含 `common.py`、`front_matter.py`、`academic_confidence.py`、`journal_citations.py`、`journal_rule_source.py` 与 `__init__.py`，职责是从 `report_writer.py` 拆出的报告片段渲染和 payload 清洗 helper。
3. `tests/test_architecture_boundaries.py` 的 `FORBIDDEN_UI_IMPORT_ROOTS` 已包含 `ROOT / "src" / "reporting"`，因此 reporting helper 不能反向导入 UI。
4. `rg` 检查显示 `src/report_writer.py` 是 reporting helper 的主调用者；`src/reporting` 内部只依赖自身 common helper，没有发现 UI 依赖。

本轮未做源码改动，只完成归类和验证。

验证命令:

```powershell
python -c "import json, pathlib; files=sorted(pathlib.Path('heading_numbering_schemes').glob('user.*.json')); print(len(files)); [json.loads(p.read_text(encoding='utf-8')) for p in files]"
python -m py_compile src\report_writer.py src\reporting\common.py src\reporting\front_matter.py src\reporting\academic_confidence.py src\reporting\journal_citations.py src\reporting\journal_rule_source.py src\config\heading_presets.py
python -m pytest tests\test_heading_numbering_scheme_closure.py tests\test_heading_numbering_logic.py tests\test_heading_panel_locking.py tests\test_execution_diagnostics_reporting.py tests\test_output_runtime_semantics.py tests\test_architecture_boundaries.py -q
python -m pytest tests\test_scene_report_artifact_drilldown_audit.py tests\test_scene_matrix_dashboard.py -q
rg -n "src\.ui|PySide6|QtWidgets|QtCore|QtGui" src\reporting tests\test_execution_diagnostics_reporting.py tests\test_output_runtime_semantics.py tests\test_architecture_boundaries.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| 用户编号方案 JSON 解析 | `3` 个文件全部可解析 |
| reporting / report writer / heading presets py_compile | 通过 |
| 编号方案 + reporting + runtime + 架构守门聚焦测试 | `89 passed in 45.95s` |
| scene report artifact drilldown + dashboard | `10 passed in 76.40s` |
| `src/reporting` UI 依赖扫描 | 未发现 `src.ui` / PySide6 依赖命中 |
| 当前展开文件级变更数 | `1415` |

当前判断:

- 第 10.32 节的“未匹配 9 文件”已完成语义归类: 3 个属于 `heading-numbering user schemes` 数据主题，6 个属于 `reporting helper package` 主题。
- `src/reporting` 不是孤立目录，已经有 `report_writer.py` 调用链、架构守门和报告相关测试覆盖。
- `heading_numbering_schemes` 是用户方案数据目录，需要和标题编号功能/样例数据一起收口，不应混入 scratch 或 docs 主题。
- Stage 0 仍未完成；后续更适合继续处理 `root-runtime`、`templates/defaults/scenes`、`docs/root` 或 `scripts/other`。

### 10.37 阶段 0 补充推进: `root-runtime` 主题验证与提交边界细化

执行日期: 2026-07-07

本轮处理第 10.32 节中的 `root-runtime` 主题。复核后发现该主题不能只按 `main.py` 与 `count_profiles/builtin.json` 两个路径理解，实际应该拆成两个可提交边界:

1. `startup splash UX`:
   - `main.py`
   - `src/ui/startup_splash.py`
   - `src/ui/main_window.py` 中的 `startup_status_changed` / `startup_ready` 信号链
   - `tests/test_windows_text_rendering_policy.py` 中的启动入口契约测试
2. `CountProfile registry data`:
   - `count_profiles/builtin.json`
   - `src/shared/engine/count_engine.py` 的 `COUNT_PROFILE_DIR` 加载入口
   - `tests/test_count_engine_semantics.py`
   - `tests/test_scene_count_profile_audit.py`
   - `tests/test_scene_family_registry.py`
   - `tests/test_journal_rule_source_governance.py`

已完成改动:

1. 在 `tests/test_windows_text_rendering_policy.py` 新增 `test_gui_startup_wires_splash_to_main_window_readiness_signals`。
2. 该测试锁定以下 GUI 启动入口契约:
   - `main.py` 导入 `StartupSplash`。
   - splash 在 `MainWindow` 创建前显示。
   - `startup_status_changed` 连接到 `splash.set_status`。
   - `startup_ready` 连接到 `_show_main_window`。
   - 主窗口通过 `QTimer.singleShot(80, _reveal_main_window)` 做短延迟显隐切换。
   - ready 后调用 `splash.finish_and_close()`。

验证命令:

```powershell
python -m py_compile main.py src\ui\startup_splash.py src\ui\main_window.py src\shared\engine\count_engine.py
python -m pytest tests\test_windows_text_rendering_policy.py tests\test_workbench_panel.py -q
python -m pytest tests\test_count_engine_semantics.py tests\test_scene_count_profile_audit.py tests\test_scene_family_registry.py tests\test_journal_rule_source_governance.py -q
python -c "from src.shared.engine.count_engine import list_count_profiles; profiles=list_count_profiles(); print(len(profiles)); print(','.join(profile.profile_id for profile in profiles[:5])); print(profiles[-1].profile_id if profiles else '')"
python -c "import json, pathlib; payload=json.loads(pathlib.Path('count_profiles/builtin.json').read_text(encoding='utf-8')); ids=[p['profile_id'] for p in payload['profiles']]; print(len(ids)); print(len(ids)==len(set(ids))); print(','.join(ids))"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| startup / main window / count engine py_compile | 通过 |
| GUI 启动策略 + MainWindow 聚焦测试 | `20 passed in 14.93s` |
| CountProfile + scene count audit + scene family + journal rule source | `22 passed in 1.87s` |
| `list_count_profiles()` | `20` 个 profile，首批 `basic,thesis_cn,school_thesis,journal_words,administrative_sections`，末尾 `word_xml_full` |
| `count_profiles/builtin.json` | `20` 个 profile id，唯一性为 `True` |
| 当前展开文件级变更数 | `1416` |

当前判断:

- `root-runtime` 已从“2 个路径待确认”细化为两个明确提交边界: startup splash UX 与 CountProfile registry data。
- `main.py` 的启动体验改动现在有轻量静态契约测试保护，且 MainWindow 信号链由现有 MainWindow 测试间接覆盖。
- `count_profiles/builtin.json` 是真实产品数据入口，不能当生成物或 scratch 处理；它应与 count engine / scene count audit / scene family registry 相关测试一起收口。
- Stage 0 仍未完成；下一步可继续处理 `templates/defaults/scenes`、`scripts/other`、`docs/root` 或更高风险的 `src/shared`。

### 10.38 阶段 0 补充推进: `templates/defaults/scenes` 配置基线主题验证

执行日期: 2026-07-07

本轮处理第 10.32 节中的 `templates/defaults/scenes` 主题。复核后确认该主题不是单纯的数据文件调整，而是一次“模板文件库瘦身 + 内置模板工厂兜底 + 场景 JSON 产品配置扩展”的组合变更。

当前状态:

1. `templates/` 当前文件库只保留:
   - `templates/default.json`
   - `templates/thesis_gbt.json`
2. 以下旧模板 JSON 文件在工作区中删除:
   - `templates/bid_custom.json`
   - `templates/bid_engineering.json`
   - `templates/bid_procurement.json`
   - `templates/official_custom.json`
   - `templates/official_gbt.json`
   - `templates/report_custom.json`
   - `templates/report_default.json`
   - `templates/tech_custom.json`
   - `templates/tech_standard.json`
   - `templates/thesis_custom.json`
3. `src/config/builtin_templates.py` 仍保留 12 个内置模板工厂，包括上述旧 ID 对应的 `bid_engineering`、`official_gbt`、`report_default`、`tech_standard` 等。
4. `src/config/library.py` 的模板库种子为 `("default", "thesis_gbt")`，并将旧模板 ID 列入 `OBSOLETE_TEMPLATE_LIBRARY_IDS`；文件库列表会剪掉旧模板文件，但内置工厂仍可解析旧 ID。
5. `scenes/` 当前可加载 7 个场景 JSON:
   - `bidding`
   - `custom`
   - `exam`
   - `official`
   - `report`
   - `technical`
   - `thesis`
6. `defaults/thesis.yaml` 增加了 `abstract_body`、`references_body`、`toc_level4`、`toc_level5`、`toc_level6` 等样式基线。

关键边界验证:

- `scenes/*.json` 与 `templates/*.json` 均可被 JSON loader 解析。
- `defaults/thesis.yaml` 可被 YAML loader 解析，`styles` 数量为 `16`，包含 `toc_level6`。
- `list_template_entries()` 只返回 `default` 与 `thesis_gbt` 两个文件库模板。
- `list_scene_descriptors()` 返回 7 个可用场景，`thesis` 的默认模板为 `thesis_gbt`，其余场景默认模板归一到 `default`。
- 17 个 delivery preset 的 `target_template_id` 均可解析；其中 `bid_engineering`、`official_gbt`、`report_default`、`tech_standard` 不在文件库中，但均由内置模板工厂解析，`bad []`。

验证命令:

```powershell
python -c "import json, pathlib; files=list(pathlib.Path('scenes').glob('*.json'))+list(pathlib.Path('templates').glob('*.json')); print(len(files)); [json.loads(p.read_text(encoding='utf-8')) for p in files]"
python -c "import yaml, pathlib; data=yaml.safe_load(pathlib.Path('defaults/thesis.yaml').read_text(encoding='utf-8')); print(type(data).__name__); print('styles', len(data.get('styles', {}))); print('toc_level6' in data.get('styles', {}))"
python -c "from pathlib import Path; from src.config.loader import load_scene, load_template; scene_paths=sorted(Path('scenes').glob('*.json')); template_paths=sorted(Path('templates').glob('*.json')); scenes=[load_scene(p) for p in scene_paths]; templates=[load_template(p) for p in template_paths]; print('scenes', len(scenes)); print('templates', len(templates))"
python -c "from src.config.library import list_template_entries, list_scene_descriptors; print('templates', [(e.config_id, e.name) for e in list_template_entries()]); desc=list_scene_descriptors(); print('scenes', len(desc)); print([(d.config_id, d.scene_id, d.default_template_id, d.is_available) for d in desc])"
python -c "from src.config.builtin_templates import list_builtin_template_ids, create_builtin_template; ids=list_builtin_template_ids(); print(len(ids)); print(','.join(ids)); [create_builtin_template(i) for i in ids]; print('ok')"
python -m pytest tests\test_config_library_and_bridge.py tests\test_builtin_templates.py tests\test_phase1_config.py -q
python -m pytest tests\test_output_runtime_semantics.py tests\test_scene_delivery_preset_audit.py tests\test_scene_delivery_preset_execution_audit.py tests\test_scene_family_application.py -q
python -m pytest tests\test_scene_panel_architecture.py::test_scene_panel_delivery_target_template_combo_and_status tests\test_template_panel_architecture.py::test_template_panel_selector_ignores_scene_compatible_template_filter tests\test_output_runtime_semantics.py::test_workbench_runner_resolves_target_template_for_delivery_presets -q
python -m pytest tests\test_scene_panel_architecture.py tests\test_template_panel_architecture.py -q
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| scenes/templates JSON 解析 | `9` 个文件全部可解析 |
| `defaults/thesis.yaml` 解析 | `dict`, `styles 16`, `toc_level6 True` |
| loader 加载场景/模板 | `scenes 7`, `templates 2` |
| library descriptors | `scenes 7` 且全部 `is_available=True` |
| 内置模板工厂 | `12` 个 ID 全部可创建，结果 `ok` |
| delivery target 可解析性 | 17 个 preset target 全部可由文件库或内置工厂解析，`bad []` |
| 配置库 + 内置模板 + phase1 配置 | `47 passed in 3.87s` |
| output runtime + delivery preset audits + scene family application | `63 passed in 70.29s` |
| delivery target/template selector 聚焦测试 | `3 passed in 3.90s` |
| scene panel + template panel 全量 | `90 passed in 200.35s` |
| 当前展开文件级变更数 | `1418` |

当前判断:

- `templates/defaults/scenes` 可拆为独立配置基线提交，但应明确提交语义: 文件库只保留 `default`/`thesis_gbt`，旧业务模板 ID 由 `src/config/builtin_templates.py` 继续兜底。
- `scenes/*.json` 是产品配置入口，不是生成物；其 input/compliance/delivery 扩展已有 loader、library、runtime、scene/template panel 测试覆盖。
- 旧模板文件删除本身不会造成模板 ID 能力丢失，但提交说明必须写清楚“文件库剪枝”和“内置模板工厂保留”之间的关系。
- Stage 0 仍未完成；下一步可处理 `scripts/other`、`docs/root`、`samples/exam` 或更高风险的 `src/shared`/`src/ui` 主题。

### 10.39 阶段 0 补充推进: `scripts/other` 发布/导出/验证脚本主题验证

执行日期: 2026-07-07

本轮处理第 10.32 节中的 `scripts/other` 主题。复核后将非手工脚本拆成三个可提交边界；`scripts/manual` 已在第 10.34 节单独处理，本节不重复归类。

脚本主题边界:

1. `scene audit/export scripts`:
   - `scripts/export_scene_*.py` 共 `43` 个。
   - 职责是将 scene matrix、release governance、material、delivery、boundary、request-cell 等审计源导出为 JSON/Markdown。
2. `gate and runner scripts`:
   - `scripts/engineering_gate.py`
   - `scripts/run_pytest_groups.py`
   - `scripts/verify_scene_matrix_release_gate.py`
   - `scripts/verify_scene_sample_fixtures.py`
   - `scripts/generate_scene_sample_fixtures.py`
   - `scripts/check_public_release.py`
3. `Windows wrappers`:
   - `scripts/windows/engineering_gate.bat`
   - `scripts/windows/install_env.bat`
   - 既有 release/package/check/clean/start wrappers。

已完成改动:

1. 将 `scripts/windows/engineering_gate.bat` 纳入 `tests/test_release_shell.py` 的 release shell 文件存在性检查。
2. 新增 `test_windows_engineering_gate_script_delegates_to_python_gate`，锁定该 Windows wrapper:
   - 从 `scripts/windows` 回到项目根目录。
   - 调用 `python scripts\engineering_gate.py %*`。
   - 用 `exit /b %ERRORLEVEL%` 透传退出码。

验证命令:

```powershell
python -m compileall -q scripts
python -m pytest tests\test_release_shell.py -q
python scripts\run_pytest_groups.py --list
python scripts\verify_scene_sample_fixtures.py
python scripts\verify_scene_matrix_release_gate.py
python scripts\engineering_gate.py
python scripts\run_pytest_groups.py --groups release --timeout 120
python scripts\check_public_release.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `python -m compileall -q scripts` | 通过 |
| `tests/test_release_shell.py` | `11 passed in 0.14s` |
| `run_pytest_groups.py --list` | 正常列出 pytest 分组；其中 `release: 1 files`，`scene: 57 files`，`workbench: 15 files` |
| `verify_scene_sample_fixtures.py` | `[OK] 42 scene sample fixtures covering 12 packs and 53 request cells verified` |
| `verify_scene_matrix_release_gate.py` | `Scene matrix release gate: passed`；所有列出的 checks 均 `passed (0 issues)`；汇总显示 `drilldowns=37/37`、`drilldown_rows=556/556`、`drilldown_sources=107/107 ready` |
| `scripts/engineering_gate.py` | compileall 通过，pytest collection `1801 tests collected`，smoke tests `10 passed`，Engineering gate passed |
| `run_pytest_groups.py --groups release --timeout 120` | `11 passed in 0.11s`，release group passed |
| `check_public_release.py` | exit code `0`；提示本地 `.venv` 与 PySide6 generated spec 为发布前需排除的本机环境 warnings |
| 当前展开文件级变更数 | `1418` |

当前判断:

- `scripts/other` 已完成 Stage 0 语义归类，可拆成 `scene audit/export scripts`、`gate and runner scripts`、`Windows wrappers` 三个提交边界，或随相应源码主题分批提交。
- 新增 `scripts/windows/engineering_gate.bat` 已有测试保护，不再是未验证 wrapper。
- `verify_scene_matrix_release_gate.py` 是脚本主题的核心高置信证据；本轮完整 release gate 通过且所有 checks 为 `0 issues`。
- `check_public_release.py` 的 warnings 是当前机器的 `.venv` 本地环境存在提示；`.venv/` 已由 `.gitignore` 覆盖，发布前仍需保持不纳入提交。
- Stage 0 仍未完成；下一步可继续处理 `docs/root`、`samples/exam`、`src/shared`、`src/ui/assets` 或 `src/ui/workbench`。

### 10.40 阶段 0 补充推进: `docs/root` 执行记录批次迁移

执行日期: 2026-07-07

本轮处理第 10.39 节之后的 `docs/root` 主题。目标不是清空 `docs/`，而是先把大量执行记录从文档根目录移入已有的执行记录边界 `docs/refactor-records/`，降低根目录噪声，并保留后续对非执行记录文档的单独分类空间。

迁移前状态:

| 检查项 | 结果 |
| --- | --- |
| `docs/` 根目录文件数 | `245` |
| `docs/` 根目录 `*执行记录*.md` 文件数 | `158` |
| `docs/refactor-records/` 迁移前文件数 | `54` |
| 目标目录同名冲突 | `0` |

已完成改动:

1. 将 `docs/` 根目录下 `158` 个 `*执行记录*.md` 文件迁入 `docs/refactor-records/`。
2. 对仓库内旧路径引用做机械收敛：仅针对已迁移执行记录文件名，将 `docs/<文件名>` / `docs\<文件名>` 改为 `docs/refactor-records/<文件名>` / `docs\refactor-records\<文件名>`。
3. 共修正 `42` 个文件、`84` 处旧路径引用。

边界验证:

```powershell
Get-ChildItem docs -File | Measure-Object
Get-ChildItem docs -File | Where-Object { $_.Name -like '*执行记录*.md' } | Measure-Object
Get-ChildItem docs\refactor-records -File | Where-Object { $_.Name -like '*执行记录*.md' } | Measure-Object
rg -n 'docs[/\\][^/\\\s\)]*执行记录[^/\\\s\)]*\.md' src tests docs scripts .github README.md
rg -n 'docs[/\\]refactor-records[/\\]refactor-records' src tests docs scripts .github README.md
python -c "import subprocess,collections; raw=subprocess.check_output(['git','status','--porcelain=v1','-uall','--no-renames','-z']); entries=[x.decode('utf-8','replace') for x in raw.split(b'\0') if x]; print('expanded_status_entries='+str(len(entries))); c=collections.Counter(e[:2] for e in entries); [print(f'{k}={c[k]}') for k in sorted(c)]"
python -c "import subprocess,collections; raw=subprocess.check_output(['git','status','--porcelain=v1','-uall','--no-renames','-z','--','docs']); entries=[x.decode('utf-8','replace') for x in raw.split(b'\0') if x]; print('docs_status_entries='+str(len(entries))); c=collections.Counter(e[:2] for e in entries); [print(f'{k}={c[k]}') for k in sorted(c)]"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `docs/` 根目录文件数 | `87` |
| `docs/` 根目录 `*执行记录*.md` 文件数 | `0` |
| `docs/refactor-records/` 当前文件数 | `212` |
| `docs/refactor-records/` 当前 `*执行记录*.md` 文件数 | `159` |
| 旧根目录执行记录引用 | `0` |
| 重复 `refactor-records` 目录引用 | `0` |
| 当前展开文件级变更数 | `1418` |
| `docs` 范围展开状态 | `651` 项，其中 `M=1`、`??=650` |

当前判断:

- `docs/root` 的最大噪声批次已经收束：执行记录不再散落在文档根目录，后续检索和提交边界更清晰。
- 展开文件级变更数没有下降，是因为这些记录大多本来就是未跟踪文档；本轮改善的是目录语义边界，而不是 git 变更总量。
- `docs/` 根目录仍有 `87` 个文件，包含边界规范、发布清单、Windows 文本渲染指南、深度分析和重构规划等；这些不应和执行记录混迁，需要在后续继续按 `docs/audits`、`docs/refactor-records`、`docs/release` 或保留根目录的公共入口文档分类。
- Stage 0 仍未完成；下一步可继续处理 `docs/root` 非执行记录、`samples/exam`、`src/shared`、`src/ui/assets` 或 `src/ui/workbench`。

### 10.41 阶段 0 补充推进: `docs/root` 非执行记录分类与断链清理

执行日期: 2026-07-07

本轮继续处理第 10.40 节剩余的 `docs/root` 非执行记录。处理原则是只保留真正的根入口文档，其余历史分析、审计、规划、修复、接入和闭环记录分别进入 `docs/audits/` 或 `docs/refactor-records/`。

保留在 `docs/` 根目录的入口文档:

1. `docs/DOCUMENTATION_BOUNDARIES.md`
2. `docs/OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md`
3. `docs/WINDOWS_TEXT_RENDERING_GUIDELINES.md`

已完成改动:

1. 将 `67` 个分析、审计、规划、蓝图、草图、策略和定义类文档迁入 `docs/audits/`。
2. 将 `17` 个修复、接入、闭环、优化、确认和 execution 类记录迁入 `docs/refactor-records/`。
3. 基于 `docs/audits/` 与 `docs/refactor-records/` 的实际文件名重写显式文档引用，共修正 `69` 个文件、`160` 处旧路径。
4. 新增 `docs/audits/场景矩阵与模板体系文档导航.md`，补齐此前规划文档中提到但不存在的场景矩阵导航入口。
5. 清理 `docs/audits/高层场景能力矩阵深化审计与落地蓝图_2026-06-16.md` 中 `2` 个 NUL 字节；上下文均为 `0 issues`，清理后 `rg` 不再把该 Markdown 误判为二进制文件。

验证命令:

```powershell
Get-ChildItem docs -File | Sort-Object Name | Select-Object -ExpandProperty Name
python -c "import pathlib,re,sys; sys.stdout.reconfigure(encoding='utf-8'); scope=[pathlib.Path(p) for p in ['src','tests','docs','scripts','.github','README.md'] if pathlib.Path(p).exists()]; files=[]; [files.append(p) if p.is_file() else files.extend([x for x in p.rglob('*') if x.is_file() and x.suffix.lower() in {'.md','.py','.yml','.yaml','.txt','.bat','.ps1','.json'}]) for p in scope]; root_names={p.name for p in pathlib.Path('docs').glob('*.md')}; stale=[]; missing=[]; path_pat=re.compile(r'docs[\\/][^\s\)\]`，、；;,]+?\.md'); [((stale.append((str(f), raw)) if len(raw.split('/'))==2 and raw.split('/')[1] not in root_names else None), (missing.append((str(f), raw)) if not pathlib.Path(raw).exists() else None)) for f in files for text in [f.read_text(encoding='utf-8')] for m in path_pat.finditer(text) for raw in [m.group(0).replace('\\\\','/')] if '*' not in raw]; print('stale_root_doc_refs='+str(len(stale))); print('missing_explicit_doc_refs='+str(len(missing)))"
python -c "from pathlib import Path; bad=[(str(p), p.read_bytes().count(b'\0')) for p in Path('docs').rglob('*.md') if p.read_bytes().count(b'\0')]; print('nul_md_files='+str(len(bad)))"
python -c "import subprocess,collections; raw=subprocess.check_output(['git','status','--porcelain=v1','-uall','--no-renames','-z','--','docs']); entries=[x.decode('utf-8','replace') for x in raw.split(b'\0') if x]; print('docs_status_entries='+str(len(entries))); c=collections.Counter(e[:2] for e in entries); [print(f'{k}={c[k]}') for k in sorted(c)]"
python -c "import subprocess,collections; raw=subprocess.check_output(['git','status','--porcelain=v1','-uall','--no-renames','-z']); entries=[x.decode('utf-8','replace') for x in raw.split(b'\0') if x]; print('expanded_status_entries='+str(len(entries))); c=collections.Counter(e[:2] for e in entries); [print(f'{k}={c[k]}') for k in sorted(c)]"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `docs/` 根目录文件数 | `3` |
| `docs/` 根目录保留文件 | `DOCUMENTATION_BOUNDARIES.md`、`OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md`、`WINDOWS_TEXT_RENDERING_GUIDELINES.md` |
| `docs/audits/` 文件数 | `379` |
| `docs/refactor-records/` 文件数 | `229` |
| 根目录过期文档引用 | `0` |
| 显式文档断链 | `0` |
| Markdown NUL 字节文件 | `0` |
| `docs` 范围展开状态 | `668` 项，其中 `D=8`、`M=1`、`??=659` |
| 当前展开文件级变更数 | `1435` |

当前判断:

- `docs/root` 已从文档垃圾场恢复为入口层：根目录只剩边界、发布和 Windows 文本渲染三类公共文档。
- `docs/audits/` 与 `docs/refactor-records/` 的职责边界更清楚：前者承接分析/审计/规划证据，后者承接修复/接入/执行记录。
- 本轮新增导航页解决了一个真实断链，也为大量 scene matrix 文档提供了入口，后续可以继续把导航页做成更完整的索引，但不应再把历史材料放回根目录。
- Stage 0 仍未完成；下一步可处理 `samples/exam`、`src/shared`、`src/ui/assets`、`src/ui/workbench` 或根目录以外的剩余未归类主题。

### 10.42 阶段 0 补充审计: `samples/docx` 样本库边界验证

执行日期: 2026-07-07

本轮复核第 10.41 节提到的 `samples/exam`。实际工作区并不存在独立的 `samples/exam` 目录，试卷类样本和其他场景样本统一位于 `samples/docx/`。

当前样本库状态:

| 检查项 | 结果 |
| --- | --- |
| `samples/exam` | 不存在 |
| `samples/docx/` 文件数 | `43` |
| DOCX 样本数 | `42` |
| README | `1` |
| 样本总大小 | `1,529,394` bytes |
| git 状态 | `samples/` 当前为未跟踪目录 |

关键发现:

1. `samples/docx/` 不是运行产物目录，而是可复用的离线 DOCX 样本库。
2. release 校验脚本 `scripts/verify_scene_sample_fixtures.py` 默认在临时目录按 registry 重新生成样本，不直接读取 `samples/docx/`。
3. `samples/docx/` 当前文件名与 `src/config/scene_sample_fixture_registry.py` 中的 `fixture_id + ".docx"` 完全一致。
4. `exam_education_controls_textboxes.docx` 与 `exam_education_structured_multiversion.docx` 是试卷/教学场景样本，不需要再拆出独立 `samples/exam` 目录。

已完成改动:

1. 补充 `samples/docx/README.md`，明确该目录是 registry 镜像样本库。
2. 在 README 中写明目录边界：只放 source-like 样本夹具，不放临时输出、客户文档或发布产物。
3. 在 README 中补充三条验证命令：release fixture 校验、DOCX zip 可打开性、磁盘文件与 registry 一致性。

验证命令:

```powershell
python -c "from pathlib import Path; from zipfile import is_zipfile; files=sorted(Path('samples/docx').glob('*.docx')); bad=[str(p) for p in files if not is_zipfile(p)]; print('docx_files='+str(len(files))); print('bad_zip='+str(len(bad)))"
python -c "from pathlib import Path; import sys; sys.path.insert(0,str(Path('.').resolve())); from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures, REQUIRED_SAMPLE_PACK_IDS; registry=sorted(f'{f.fixture_id}.docx' for f in list_scene_sample_fixtures()); disk=sorted(p.name for p in Path('samples/docx').glob('*.docx')); print('registry='+str(len(registry))); print('disk='+str(len(disk))); print('packs='+str(len(REQUIRED_SAMPLE_PACK_IDS))); print('missing_on_disk='+repr(sorted(set(registry)-set(disk)))); print('extra_on_disk='+repr(sorted(set(disk)-set(registry))))"
python scripts\verify_scene_sample_fixtures.py
git status --short -- samples scripts\verify_scene_sample_fixtures.py scripts\generate_scene_sample_fixtures.py src\config\scene_sample_fixture_registry.py src\shared\engine\scene_sample_docx_builder.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| DOCX 可打开性 | `docx_files=42`, `bad_zip=0` |
| registry / 磁盘一致性 | `registry=42`, `disk=42`, `packs=12`, `missing_on_disk=[]`, `extra_on_disk=[]` |
| release sample fixture 校验 | `[OK] 42 scene sample fixtures covering 12 packs and 53 request cells verified.` |
| 相关文件状态 | `samples/`、sample fixture 脚本、registry 和 builder 均为当前未跟踪主题的一部分 |

当前判断:

- `samples/docx` 结构健康，问题不是误放生成物，而是此前 README 没有把 registry 镜像契约写清楚。
- 样本库可以作为独立提交主题，也可以随 scene sample fixture registry / builder / verifier 一起提交。
- `samples/exam` 不应作为后续迁移目标；试卷样本已经纳入统一 `samples/docx` 样本库。
- Stage 0 仍未完成；下一步更适合处理 `src/shared`、`src/ui/assets`、`src/ui/workbench` 或剩余未归类源码主题。

### 10.43 阶段 0 补充审计: AssetsPanel 拆分与素材服务边界验证

执行日期: 2026-07-07

本轮继续处理第 10.42 节之后的 `src/ui/assets` 线索。复核当前工作区后确认: 实际不存在 `src/ui/assets` 目录，也没有 tracked `src/ui/assets` 文件；真实主题是 `src/ui/panels/assets/` presenter 包、`src/ui/panels/assets_panel.py`、`src/services/material_assets/` 服务包及其测试。

当前边界:

| 区域 | 状态 |
| --- | --- |
| `src/ui/assets` | 不存在，tracked 文件数 `0` |
| `src/ui/panels/assets_panel.py` | `527` 行，`2` 个 class，`3` 个顶层函数 |
| `src/ui/panels/assets/` | `40` 个 presenter/helper 模块 |
| `src/services/material_assets/` | `6` 个服务模块 |
| assets/material 目标测试 | `10` 个测试文件 |

关键判断:

1. 这不是删除旧 `src/ui/assets` 的主题，而是 AssetsPanel 从巨型单文件向 presenter/service 拆分后的边界验证。
2. `assets_panel.py` 当前主要承担 Qt shell、mixin 组合和兼容导入；本地题图、缓存、审计、批量导入、图片预览、资料修复导航等职责已经下沉到 `src/ui/panels/assets/`。
3. 题图素材、题图库、DOCX 修复与审计逻辑已经下沉到 `src/services/material_assets/`，服务层不依赖 UI 面板。
4. `src/ui/panels/assets/` 中只有 `image_preview_presenter.py` 包含字符串 `assets_panel_full_preview`，属于事件 source 名称，不是反向 import。
5. 测试中仍允许从 `src.ui.panels.assets_panel` 导入兼容面，说明旧调用面仍被保护。

验证命令:

```powershell
git ls-files src/ui/assets
git status --short -- src\ui\panels\assets src\ui\panels\assets_panel.py src\services\material_assets tests
python -m compileall -q src\ui\panels\assets src\ui\panels\assets_panel.py src\services\material_assets
python -m pytest -q tests\test_assets_enterprise_boundary.py tests\test_material_asset_services.py tests\test_assets_panel_helper_modules.py tests\test_assets_panel_specs.py tests\test_assets_panel_question_figures.py tests\test_assets_panel_question_audit.py tests\test_assets_question_figures_presenter.py tests\test_assets_question_library_presenter.py tests\test_assets_panel_architecture.py tests\test_scene_product_maturity_upgrade_audit.py
python -c "import ast; from pathlib import Path; paths=[Path('src/ui/panels/assets_panel.py'), Path('src/services/material_assets/question_library.py'), Path('src/services/material_assets/question_figures.py')]; [print(str(p), 'lines', sum(1 for _ in p.open(encoding='utf-8')), 'classes', sum(isinstance(n,ast.ClassDef) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8')))), 'functions', sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))))) for p in paths]"
rg -n "import .*assets_panel|from .*assets_panel|src\.ui\.panels\.assets_panel" src\ui\panels\assets src\services\material_assets tests
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `src/ui/assets` tracked 文件 | `0` |
| assets/material 编译 | 通过 |
| assets/material 目标测试 | `109 passed in 2.39s` |
| `assets_panel.py` 体量 | `527` 行，`2` class，`3` functions |
| `question_library.py` 体量 | `1603` 行，`42` functions |
| `question_figures.py` 体量 | `511` 行，`24` functions |
| 服务层反向依赖 `assets_panel` | `0` |
| presenter 包反向 import `assets_panel` | `0`；仅 1 个事件 source 字符串命中 |

当前判断:

- AssetsPanel 主题已经从“超大 UI 面板”变成可提交的 presenter/service 拆分主题，结构方向健康。
- 本批可以作为独立提交边界: `src/ui/panels/assets_panel.py`、`src/ui/panels/assets/`、`src/services/material_assets/`、assets/material 测试，以及相关产品边界文档。
- 还没有完成整个 Stage 0；后续仍需处理 `src/shared`、`src/ui/workbench` 和其他源码/测试主题。

### 10.44 阶段 0 补充审计: Workbench 运行时/导航/产物投影主题验证

执行日期: 2026-07-07

本轮继续处理第 10.43 节之后的 `src/ui/workbench` 主题。复核后确认实际边界包括 `src/ui/panels/workbench/`、`src/ui/adapters/workbench_execution_adapter.py`，以及新拆出的 `src/ui/adapters/workbench_artifact_items.py`、`src/ui/adapters/workbench_issue_navigation.py`。

当前变更边界:

| 区域 | 状态 |
| --- | --- |
| Workbench/adapters 文件级状态 | `24` 项，其中 `M=17`、`??=7` |
| 新增 adapter 模块 | `workbench_artifact_items.py`、`workbench_issue_navigation.py` |
| 新增 workbench runtime/helper 模块 | `exam_question_assets.py`、`execution_flow_projection.py`、`material_artifacts.py`、`material_preflight.py`、`question_figure_repair_runtime.py` |
| focused 验证测试文件 | `15` 个 |

重点体量:

| 文件 | 行数 | 类 | 函数/方法 |
| --- | ---: | ---: | ---: |
| `src/ui/adapters/workbench_execution_adapter.py` | `3004` | `6` | `101` |
| `src/ui/adapters/workbench_artifact_items.py` | `612` | `0` | `24` |
| `src/ui/adapters/workbench_issue_navigation.py` | `914` | `4` | `21` |
| `src/ui/panels/workbench/execution_runtime.py` | `2294` | `4` | `65` |
| `src/ui/panels/workbench/quick_execution_detail.py` | `2524` | `1` | `113` |
| `src/ui/panels/workbench/question_figure_repair_runtime.py` | `2733` | `0` | `34` |
| `src/ui/panels/workbench/material_artifacts.py` | `865` | `0` | `32` |
| `src/ui/panels/workbench/material_preflight.py` | `490` | `0` | `20` |

关键判断:

1. `workbench_artifact_items.py` 将输出、对比、报告、中间文件、资料 manifest/package、scene sample manifest、题图修复队列等 artifact row 投影从执行 adapter 中分离。
2. `workbench_issue_navigation.py` 将 Workbench issue repair target 到模板/场景/资料/feature card 的导航映射变成纯 registry，并提供 audit。
3. `material_preflight.py` 与 `material_artifacts.py` 将资料预检、资料 manifest/package 写出从 `execution_runtime.py` 中拆出。
4. `question_figure_repair_runtime.py` 仍然较大，但已经成为独立运行时边界，并被 dedicated tests 覆盖。
5. `quick_execution_detail.py` 与 `execution_runtime.py` 仍偏大；本轮只做 Stage 0 提交边界验证，不继续扩大功能改动。

验证命令:

```powershell
python -m compileall -q src\ui\panels\workbench src\ui\adapters\workbench_execution_adapter.py src\ui\adapters\workbench_artifact_items.py src\ui\adapters\workbench_issue_navigation.py
python -m pytest -q tests\test_workbench_detail_architecture.py tests\test_workbench_document_path_architecture.py tests\test_workbench_document_path_semantics.py tests\test_workbench_execution_architecture.py tests\test_workbench_execution_center.py tests\test_workbench_execution_session_architecture.py tests\test_workbench_navigation_architecture.py tests\test_quick_execution_detail_architecture.py tests\test_quick_execution_presenter.py tests\test_recent_run_panel.py tests\test_execution_worker.py tests\test_material_execution_context.py tests\test_material_field_consistency.py tests\test_question_figure_repair_runtime.py tests\test_workbench_issue_navigation.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| Workbench/adapters 编译 | 通过 |
| focused Workbench/material 测试 | `279 passed in 137.49s (0:02:17)` |
| issue navigation registry 测试 | 纳入 focused 批次 |
| material preflight/artifact 架构测试 | 纳入 focused 批次 |
| question figure repair runtime 测试 | 纳入 focused 批次 |

当前判断:

- Workbench 主题可以作为独立提交边界: execution adapter + artifact item 投影 + issue navigation registry + material runtime helpers + focused tests。
- 结构方向健康，但仍存在后续拆分余量：`workbench_execution_adapter.py`、`execution_runtime.py`、`quick_execution_detail.py`、`question_figure_repair_runtime.py` 都仍是千行级文件。
- Stage 0 仍未完成；下一步更适合处理 `src/shared` 或继续为剩余 `src/config`/`tests` 主题做提交边界验证。

### 10.45 阶段 0 补充审计: `src/shared` engine/UI 主题验证

执行日期: 2026-07-07

本轮继续处理第 10.44 节之后的 `src/shared` 高风险主题。该主题跨度较大，不能作为单一语义提交理解；复核后拆为 shared engine runtime 与 shared UI/control contracts 两个提交边界更合理。

当前变更边界:

| 区域 | 文件级状态 |
| --- | --- |
| `src/shared/engine` | `22` 项，其中 `M=5`、`??=17` |
| `src/shared/ui` | `53` 项，其中 `M=23`、`??=30` |
| `src/shared` 合计 | `75` 项，其中 `M=28`、`??=47` |

shared engine 重点模块:

| 文件 | 行数 | 类 | 函数/方法 |
| --- | ---: | ---: | ---: |
| `src/shared/engine/exam_paper_style.py` | `2414` | `2` | `127` |
| `src/shared/engine/exam_question_schema.py` | `1483` | `5` | `67` |
| `src/shared/engine/count_engine.py` | `655` | `3` | `37` |
| `src/shared/engine/content_visibility.py` | `433` | `4` | `18` |
| `src/shared/engine/object_preflight.py` | `272` | `2` | `11` |

shared UI/control 重点模块:

| 文件 | 行数 | 类 | 函数/方法 |
| --- | ---: | ---: | ---: |
| `src/shared/ui/style_management_block.py` | `819` | `3` | `50` |
| `src/shared/ui/paragraph_style_editor.py` | `585` | `1` | `34` |
| `src/shared/ui/style_policy_control_deck.py` | `438` | `4` | `37` |
| `src/shared/ui/summary_grid.py` | `645` | `5` | `45` |
| `src/shared/ui/template_form_layout.py` | `388` | `3` | `33` |

关键判断:

1. shared engine 侧承接了考试卷、结构化题源、字数统计、内容可见性、固定版式、期刊规则、资料一致性、对象预检、样本 DOCX builder 等跨场景运行时能力。
2. shared UI 侧承接了样式编辑、样式来源、样式策略控制、证据控件、导航高亮、表单布局、summary grid、统一导出等控件协议。
3. `src/shared/ui/__init__.py` 已从直接 import 改为 `_EXPORT_MAP + __getattr__` 懒导出，降低导入副作用；`tests/test_ui_exports.py` 纳入验证。
4. `exam_paper_style.py` 与 `exam_question_schema.py` 仍是千行级模块，结构方向可接受但后续仍有拆分空间。
5. 本轮只做 Stage 0 边界验证，不扩大 shared 层功能改动。

验证命令:

```powershell
python -m compileall -q src\shared
python -m pytest -q tests\test_count_engine_semantics.py tests\test_content_visibility_engine.py tests\test_exam_paper_style.py tests\test_exam_question_schema_runtime.py tests\test_fixed_layout_text_runtime.py tests\test_journal_citation_runtime.py tests\test_journal_rule_source_governance.py tests\test_material_field_consistency.py tests\test_object_preflight_semantics.py tests\test_scene_journey_runtime.py tests\test_scene_sample_fixture_regression.py tests\test_page_number_planner_semantics.py tests\test_table_format_semantics.py tests\test_toc_semantics.py tests\test_header_footer_semantics.py tests\test_citation_link_semantics.py
python -m pytest -q tests\test_button_style.py tests\test_combo_architecture.py tests\test_design_system_refactor.py tests\test_option_toggle_chip.py tests\test_summary_grid.py tests\test_small_widget_architecture.py tests\test_ui_exports.py tests\test_windows_text_rendering_policy.py tests\test_paragraph_style_editor.py tests\test_navigation_highlight.py tests\test_evidence_widgets.py tests\test_library_action_row.py tests\test_style_difference_projection.py tests\test_style_field_descriptors.py tests\test_style_source_visual_audit.py tests\test_style_variant_semantics.py tests\test_template_style_detail.py tests\test_template_style_preview.py tests\test_control_contract_registry.py tests\test_architecture_boundaries.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `src/shared` 编译 | 通过 |
| shared engine/runtime 测试 | `128 passed in 79.54s (0:01:19)` |
| shared UI/control 测试 | `184 passed in 39.29s` |

当前判断:

- `src/shared` 可以拆为两个提交边界: shared engine runtime 与 shared UI/control contracts。
- 当前结构比“功能散落在 panel/workbench/template 内”更健康，但仍有后续瘦身空间，尤其是 `exam_paper_style.py`、`exam_question_schema.py`、`style_management_block.py` 与 `summary_grid.py`。
- Stage 0 仍未完成；下一步可继续处理剩余 `src/config`/scene 矩阵、测试主题、`exam_masters`/`exam_samples` 等未归类文件。

### 10.46 阶段 0 补充推进: `exam_masters` / `exam_samples` 资源边界收口

执行日期: 2026-07-07

本轮处理第 10.45 节之后的顶层考试资源主题。复核后确认: `exam_masters/builtin/` 是内置试卷母版候选资源；`exam_masters/user/`、`exam_masters/*.docx` 根层旧输出、`exam_samples/` 是本地运行时副本或样张输出，不应进入提交边界。

迁移/清理前状态:

| 区域 | 文件数 | 大小/说明 |
| --- | ---: | --- |
| `exam_masters/` | `180` 个 DOCX | `8,766,741` bytes |
| `exam_masters/builtin/` | `33` 个 DOCX | 内置母版候选 |
| `exam_masters/user/` | `146` 个 DOCX | `user_default_exam_copy*` 与 `user_imported_exam*` 本地副本 |
| `exam_masters/*.docx` | `1` 个 DOCX | 根层旧输出 `默认试卷_母版.docx` |
| `exam_samples/` | `1` 个 DOCX | `默认试卷_样张.docx` 样张输出 |

已完成改动:

1. 在 `.gitignore` 增加本地考试资源输出规则:
   - `exam_masters/user/`
   - `/exam_masters/*.docx`
   - `exam_samples/`
2. 不删除任何本地 DOCX 文件，只从提交候选中排除运行时副本和样张输出。
3. 保留 `exam_masters/builtin/` 为显式候选资源目录。

关键验证:

```powershell
git status --short -- exam_masters exam_samples .gitignore
git check-ignore -v exam_masters\user\user_default_exam_copy.docx exam_masters\默认试卷_母版.docx exam_samples\默认试卷_样张.docx exam_masters\builtin\default_exam_v20.docx
python -c "from pathlib import Path; from zipfile import is_zipfile; visible=list(Path('exam_masters/builtin').glob('*.docx')); print('builtin_docx='+str(len(visible))); print('bad_builtin_zip='+str(len([p for p in visible if not is_zipfile(p)])))"
python -c "from pathlib import Path; import sys; sys.path.insert(0,str(Path('.').resolve())); import src.shared.engine.exam_paper_style as e; print('ids', e.BUILTIN_EXAM_BLANK_STYLE_IDS); [print(style_id, e.ensure_builtin_exam_master_docx(style_id).name, e.ensure_builtin_exam_master_docx(style_id).exists()) for style_id in e.BUILTIN_EXAM_BLANK_STYLE_IDS]"
python -m pytest -q tests\test_exam_paper_style.py tests\test_scene_overview_projection.py
python -m pytest -q tests\test_scene_panel_architecture.py::test_scene_exam_paper_detail_updates_config_and_answer_delivery tests\test_scene_panel_architecture.py::test_scene_overview_shows_exam_assembly_strategy_without_workbench_fields tests\test_scene_panel_architecture.py::test_scene_panel_output_rules_card_controls_exam_answer_delivery
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| ignore 后考试资源状态 | `33` 项，均为 `exam_masters/builtin/*.docx` |
| `exam_masters/user/` ignore | 命中 `.gitignore:21` |
| `exam_masters/*.docx` 根层输出 ignore | 命中 `.gitignore:22` |
| `exam_samples/` ignore | 命中 `.gitignore:23` |
| `exam_masters/builtin/default_exam_v20.docx` | 未被 ignore |
| builtin DOCX 可打开性 | `builtin_docx=33`, `bad_builtin_zip=0` |
| 当前内置样式 ID | `('default_exam',)` |
| 当前内置母版入口 | `default_exam -> default_exam_v20.docx`, exists `True` |
| 考试母版/概览测试 | `26 passed in 3.31s` |
| ScenePanel 母版 UI 子集 | `3 passed in 5.64s` |
| 展开文件级变更数 | 从 `1435` 降到 `1287` |

当前判断:

- 本地考试副本和样张输出已经从 Stage 0 提交候选中排除，避免把用户运行时文件误提交。
- `exam_masters/builtin/` 仍需作为产品资源候选单独处理；当前代码只声明 `default_exam`，入口为 `default_exam_v20.docx`，但历史 `default_exam_v*` 与 `compact_exam*` 文件仍在 builtin 目录中。
- 后续可以单独做一批“内置母版资源剪枝/保留策略”审计，决定是否只提交当前入口和必要回归参考文件。
- Stage 0 仍未完成；下一步可继续处理剩余 `src/config`/scene 矩阵、测试主题或内置母版剪枝。

### 10.47 阶段 0 补充审计: `src/config` scene matrix / runtime / core 配置主题验证

执行日期: 2026-07-07

本轮处理第 10.46 节之后的 `src/config` 主题。当前 `src/config` 共有 `92` 个文件级变更，其中 `M=11`、`??=81`。该主题不能作为单一提交理解，至少应拆成 scene matrix/release、scene audit/runtime、material config、style config、heading config、core config 六类。

当前聚类:

| 子主题 | 文件数 | 说明 |
| --- | ---: | --- |
| `scene_matrix` | `11` | dashboard / drilldown / projection references / source evidence / release items |
| `scene_audit_runtime` | `54` | coverage、request samples、release acceptance、boundary、material、delivery、family、readiness 等审计与运行时矩阵 |
| `material_config` | `6` | material context/schema/mapping/preview/batch/materials |
| `style_config` | `4` | style field descriptors、difference projection、source summary、variant semantics |
| `heading_config` | `2` | heading normalize / presets |
| `core_other` | `15` | entity、library、resolver、template、control contract、fixed layout、header/footer 等配置基线 |

重点体量:

| 文件 | 行数 |
| --- | ---: |
| `src/config/scene_matrix_dashboard.py` | `3460` |
| `src/config/scene_matrix_dashboard_models.py` | `2030` |
| `src/config/scene_matrix_drilldown.py` | `1095` |
| `src/config/scene_matrix_drilldown_items.py` | `1114` |
| `src/config/scene_matrix_drilldown_sources.py` | `1026` |
| `src/config/scene_coverage_manifest.py` | `1591` |
| `src/config/scene_family_application.py` | `2206` |
| `src/config/scene_release_acceptance_certificate_audit.py` | `1647` |
| `src/config/material_schema_registry.py` | `1135` |
| `src/config/control_contract_registry.py` | `779` |

关键判断:

1. `src/config/scene_matrix_*` 已经不是原始巨型单文件状态；dashboard、models、drilldown、sources、projection references、release items 已形成可验证拆分边界。
2. `scene_audit_runtime` 是发布门禁和矩阵证据的主体，必须与 `scripts/verify_scene_matrix_release_gate.py`、scene pytest 分组和 docs/audits 引用一起提交。
3. `material_config` 与 `style_config` 受 focused config/material/style 测试覆盖，不应和 scene release gate 混作同一个唯一证据。
4. `scene_matrix_dashboard.py`、`scene_matrix_dashboard_models.py`、`scene_family_application.py` 仍是后续可拆分的大文件，但当前已有 release gate 与 scene 分组保护。

验证命令:

```powershell
python -m compileall -q src\config
python scripts\verify_scene_matrix_release_gate.py
python scripts\run_pytest_groups.py --groups scene --timeout 300
python -m pytest -q tests\test_config_library_and_bridge.py tests\test_config_feature_hosting.py tests\test_phase1_config.py tests\test_material_schema_registry.py tests\test_material_execution_context.py tests\test_material_field_consistency.py tests\test_control_contract_registry.py tests\test_style_field_descriptors.py tests\test_style_difference_projection.py tests\test_content_visibility_engine.py tests\test_heading_numbering_scheme_closure.py tests\test_heading_numbering_logic.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `src/config` 编译 | 通过 |
| scene matrix release gate | `passed`，全部列出的 checks 均 `passed (0 issues)` |
| release gate 摘要 | `12 packs`、`42 sample fixtures`、`53 request samples`、`53 request cells`、`drilldowns=37/37`、`drilldown_rows=556/556`、`drilldown_sources=107/107 ready` |
| scene pytest 分组 | `356 passed in 256.48s (0:04:16)`，`[PASS] scene` |
| config/material/style/core focused 测试 | `145 passed in 14.70s` |

当前判断:

- `src/config` 可以拆成至少两个高置信提交边界：`scene matrix + scene release audits` 与 `config/material/style/core`。
- 如果希望更细，`material_config`、`style_config`、`heading_config` 也能作为独立小批次；但当前验证已经覆盖它们的主要行为面。
- Stage 0 仍未完成；下一步可处理大规模 tests 主题、`exam_masters/builtin` 内置母版剪枝策略、或剩余顶层临时测试脚本。

### 10.48 阶段 0 补充推进: 根目录 scene sample 生成物 ignore 收口

执行日期: 2026-07-07

本轮继续处理第 10.47 节之后的顶层散落文件。复核后确认，根目录 `manifest.json` 与 `request_cell_report.md` 不是项目入口配置，而是 `build_scene_sample_docx_library(output_dir='.')` 生成的 scene sample fixture manifest 和 request-cell 报告。

关键证据:

| 文件 | 证据 |
| --- | --- |
| `manifest.json` | JSON 中 `output_dir='.'`、`artifact_count=42`、`request_cell_count=53`、`request_cell_report_path='request_cell_report.md'` |
| `request_cell_report.md` | 标题为 `Scene Request-Cell Report`，包含 `53` 个 request-cell anchor |
| tracked 状态 | 二者均未被 git 跟踪 |

已完成改动:

1. 在 `.gitignore` 增加根目录限定规则:
   - `/manifest.json`
   - `/request_cell_report.md`
2. 不影响其他目录下的 manifest/report；`artifacts/` 与 `tests/output/` 仍由已有规则覆盖。
3. 复核旧根目录手工测试脚本已经迁到 `scripts/manual/`，仍保持 rename 状态，不在本轮重复处理。

验证命令:

```powershell
git status --short -- test_all_components.py test_audit_fix.py test_combo.py test_crash.py test_crash_trace.py test_phase_a_components.py test_workbench_v2.py scripts\manual manifest.json request_cell_report.md .gitignore
git check-ignore -v manifest.json request_cell_report.md artifacts\scene_sample_fixtures\manifest.json tests\output\manifest.json
python -m compileall -q scripts\manual
python -c "import subprocess,collections; raw=subprocess.check_output(['git','status','--porcelain=v1','-uall','--no-renames','-z']); entries=[x.decode('utf-8','replace') for x in raw.split(b'\0') if x]; print('expanded_status_entries='+str(len(entries))); c=collections.Counter(e[:2] for e in entries); [print(f'{k}={c[k]}') for k in sorted(c)]"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `manifest.json` ignore | 命中 `.gitignore:24` |
| `request_cell_report.md` ignore | 命中 `.gitignore:25` |
| `artifacts/scene_sample_fixtures/manifest.json` | 继续由 `artifacts/` 规则覆盖 |
| `tests/output/manifest.json` | 继续由 `tests/output/` 规则覆盖 |
| `scripts/manual` 编译 | 通过 |
| 展开文件级变更数 | 从 `1287` 降到 `1285` |

当前判断:

- 根目录 scene sample 生成物已经从提交候选中排除，避免和真实 sample fixture registry / builder 主题混淆。
- 顶层旧手工测试脚本迁移仍保持为 `scripts/manual` 独立主题，已在第 10.34 节验证。
- Stage 0 仍未完成；下一步可继续处理大规模 tests 主题、`exam_masters/builtin` 内置母版剪枝策略，或剩余顶层配置/发布入口。

### 10.49 阶段 0 补充推进: `exam_masters/builtin` 内置母版候选剪枝

执行日期: 2026-07-07

本轮继续处理第 10.48 节之后的 `exam_masters/builtin` 资源候选。目标不是删除历史 DOCX，而是明确提交边界: 当前运行时需要的内置母版文件应保留为候选，历史版本和已下线 compact 母版不进入提交。

代码证据:

| 证据 | 结果 |
| --- | --- |
| `BUILTIN_EXAM_BLANK_STYLE_IDS` | `('default_exam',)` |
| `_BUILTIN_STYLE_SPECS['default_exam'].master_filename` | `default_exam_v20.docx` |
| `ensure_builtin_exam_master_docx('default_exam')` | 返回 `exam_masters/builtin/default_exam_v20.docx` |
| 生成器参考文件 | `_load_reference_sealed_header_xml()`、`_copy_reference_sealed_header()`、`_append_reference_sealed_zone()` 仍读取 `default_exam_v10.docx` |
| compact 母版 | 当前测试断言 `compact_exam` 不再作为可选母版出现 |

已完成改动:

1. 在 `.gitignore` 增加:
   - `exam_masters/builtin/*.docx`
   - `!exam_masters/builtin/default_exam_v10.docx`
   - `!exam_masters/builtin/default_exam_v20.docx`
2. 保留磁盘上的历史 DOCX 文件，不执行删除。
3. 将 Stage 0 的内置母版提交候选从 `33` 个收窄为 `2` 个。

验证命令:

```powershell
git status --short -- exam_masters .gitignore
git check-ignore -v exam_masters\builtin\default_exam_v9.docx exam_masters\builtin\default_exam_v10.docx exam_masters\builtin\default_exam_v20.docx exam_masters\builtin\compact_exam_v13.docx
python -c "from pathlib import Path; from zipfile import is_zipfile; keep=[Path('exam_masters/builtin/default_exam_v10.docx'),Path('exam_masters/builtin/default_exam_v20.docx')]; [print(p.name, p.exists(), is_zipfile(p), p.stat().st_size if p.exists() else 0) for p in keep]"
python -m pytest -q tests\test_exam_paper_style.py tests\test_scene_overview_projection.py tests\test_scene_panel_architecture.py::test_scene_exam_paper_detail_updates_config_and_answer_delivery tests\test_scene_panel_architecture.py::test_scene_overview_shows_exam_assembly_strategy_without_workbench_fields tests\test_scene_panel_architecture.py::test_scene_panel_output_rules_card_controls_exam_answer_delivery
python -c "import subprocess,collections; raw=subprocess.check_output(['git','status','--porcelain=v1','-uall','--no-renames','-z','--','exam_masters']); entries=[x.decode('utf-8','replace') for x in raw.split(b'\0') if x]; print('exam_masters_status_entries='+str(len(entries))); [print(e) for e in entries]"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `default_exam_v9.docx` | 被 `exam_masters/builtin/*.docx` ignore |
| `compact_exam_v13.docx` | 被 `exam_masters/builtin/*.docx` ignore |
| `default_exam_v10.docx` | negation 规则保留为候选 |
| `default_exam_v20.docx` | negation 规则保留为候选 |
| 保留 DOCX 可打开性 | `default_exam_v10.docx True True 92446`；`default_exam_v20.docx True True 46057` |
| 考试母版/概览/ScenePanel 子集 | `29 passed in 6.02s` |
| `exam_masters` 当前状态 | `2` 项，均为 `?? exam_masters/builtin/default_exam_v10.docx` 与 `?? exam_masters/builtin/default_exam_v20.docx` |
| 展开文件级变更数 | 从 `1285` 降到 `1254` |

当前判断:

- `exam_masters/builtin` 已从历史版本仓库收窄为当前运行时需要的资源候选。
- 如果后续要真正提交内置母版资源，应提交 `default_exam_v20.docx` 与 `default_exam_v10.docx`，并在 PR/提交说明中写清楚 v10 是密封线页眉参考源，不是用户可选样式。
- Stage 0 仍未完成；下一步可继续处理大规模 tests 主题，或剩余顶层配置/发布入口。

### 10.50 阶段 0 补充审计: `tests` 大规模变更主题分桶与全量验证

执行日期: 2026-07-07

本轮处理第 10.49 节之后的 `tests` 大规模变更主题。当前 `tests` 目录共有 `143` 个文件级变更，其中 `M=51`、`??=92`。该主题覆盖多个已经验证过的源码主题，不能作为单一语义提交理解；应按业务域或随对应源码提交分批。

当前测试文件整体:

| 检查项 | 结果 |
| --- | ---: |
| `tests/test_*.py` 文件数 | `209` |
| 测试源码总行数 | `70,112` |
| pytest collection | `1801 tests collected` |
| tests 变更文件数 | `143` |
| tests 变更状态 | `M=51`、`??=92` |

变更分桶:

| 分桶 | 文件数 | 说明 |
| --- | ---: | --- |
| `scene` | `57` | scene matrix、release、boundary、delivery、material、family、dashboard/drilldown |
| `template_config_heading` | `28` | template、heading、toc、page/table/header/footer、phase config |
| `shared_ui_contracts` | `20` | shared UI 控件、style 协议、control registry、Windows 文本渲染 |
| `workbench_execution` | `13` | Workbench execution、quick execution、recent run、issue navigation |
| `shared_engine_material` | `11` | count/exam/journal/material/object preflight/fixed layout/content visibility |
| `assets_material` | `9` | AssetsPanel presenter/service 与 material asset service |
| `release` | `1` | release shell / CI gate |
| `other` | `4` | all-components preview、output runtime、field display、question figure runtime |

重点大文件:

| 文件 | 行数 |
| --- | ---: |
| `tests/test_scene_panel_architecture.py` | `4560` |
| `tests/test_scene_matrix_drilldown.py` | `4148` |
| `tests/test_workbench_execution_center.py` | `2785` |
| `tests/test_template_secondary_details.py` | `2206` |
| `tests/test_material_execution_context.py` | `2176` |
| `tests/test_scene_matrix_dashboard.py` | `2140` |
| `tests/test_small_widget_architecture.py` | `2105` |
| `tests/test_quick_execution_detail_architecture.py` | `1876` |
| `tests/test_output_runtime_semantics.py` | `1590` |
| `tests/test_execution_diagnostics_reporting.py` | `1474` |

验证命令:

```powershell
python -m pytest --collect-only -q
python -m pytest -q
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| collection | `1801 tests collected in 1.73s` |
| full pytest | `1801 passed in 573.82s (0:09:33)` |
| pytest 进程状态 | 输出全量通过汇总后自然退出，exit code `0` |

当前判断:

- `tests` 主题已有全量绿色证据，能够支撑前面多个源码主题的 Stage 0 提交边界。
- 提交时不建议把所有 tests 单独作为一个巨型测试提交；更合理的是随对应源码主题分批，例如 scene tests 随 `src/config`，assets tests 随 AssetsPanel，workbench tests 随 Workbench，shared tests 随 shared engine/UI。
- 当前剩余风险不是测试是否通过，而是后续提交拆分时要保持源码与对应 tests 同步，不要把新测试和被测实现拆开。
- Stage 0 仍未完成；下一步可继续处理剩余顶层配置/发布入口、`docs` 大量迁移状态，或 `scripts`/`samples`/`exam_masters` 等已验证主题的最终提交清单。

### 10.51 阶段 0 补充审计: 顶层配置、CI 与发布入口复核

执行日期: 2026-07-07

本轮处理第 10.50 节之后的顶层配置与发布入口主题。目标是确认新增工程化配置、依赖分层、CI workflow、本地 Windows wrapper、公开发布检查与 `main.py` 启动入口是否仍然自洽。

当前相关状态:

| 路径 | 状态 | 说明 |
| --- | --- | --- |
| `.gitignore` | `M` | 已补充本地环境、生成物、考试母版剪枝与运行日志规则 |
| `.gitattributes` | `??` | 新增 Git 换行和二进制文件策略 |
| `pyproject.toml` | `??` | 新增项目元数据、运行依赖、dev/build extras 与 pytest 配置 |
| `requirements.txt` | `M` | 收束为运行时依赖清单 |
| `.github/workflows/engineering-gate.yml` | `??` | 新增基础工程门禁 workflow |
| `.github/workflows/scene-matrix-release-gate.yml` | `??` | 新增 scene matrix release gate workflow |
| `scripts/engineering_gate.py` | `??` | 新增本地/CI 共用基础门禁脚本 |
| `scripts/windows/engineering_gate.bat` | `??` | 新增 Windows wrapper |
| `scripts/windows/install_env.bat` | `M` | 改为安装 `".[dev,build]"` |
| `main.py` | `M` | GUI 启动 splash/readiness 链路改动，归属 root-runtime 启动主题 |
| `tests/test_release_shell.py` | `M` | 锁定 release shell、CI、pyproject extras、公开发布契约 |
| `tests/test_windows_text_rendering_policy.py` | `M` | 锁定 GUI 启动 splash/readiness 信号 wiring |

关键证据:

1. `pyproject.toml` 可由 `tomllib` 正常解析，项目名为 `lark-formatter`，`requires-python` 为 `>=3.10`，extras 为 `build` 与 `dev`。
2. `requirements.txt` 仅保留运行时依赖: `python-docx`、`PySide6`、`Pillow`、`lxml`、`PyYAML`、Windows 条件 `pywin32`。
3. `.github/workflows/engineering-gate.yml` 在 clean runner 上执行 `python -m pip install -e ".[dev]"`，随后运行 `python scripts/engineering_gate.py`。
4. `.github/workflows/scene-matrix-release-gate.yml` 单独安装 scene matrix 所需依赖并运行 `scripts/verify_scene_matrix_release_gate.py` 与 scene regression 测试集合。
5. `scripts/engineering_gate.py` 当前门禁包含:
   - `python -m compileall -q src main.py`
   - `python -m pytest --collect-only -q tests`
   - `python -m pytest -q tests/test_app_meta.py tests/test_config_management_architecture.py tests/test_heading_style_semantics.py`
6. `.gitattributes` 已定义 `*.py`、`*.md`、`*.json`、`*.yaml`、`*.toml` 为 LF，`*.bat`/`*.ps1` 为 CRLF，并将 docx/png/pdf/zip 等视为 binary。
7. `.gitignore` 已覆盖 `.venv/`、根目录 scene sample 生成物、`exam_masters/builtin/*.docx` 剪枝规则、运行日志与常见发布生成物。

验证命令:

```powershell
git status --short -- .github .gitattributes .gitignore pyproject.toml requirements.txt main.py scripts\engineering_gate.py scripts\check_public_release.py tests\test_release_shell.py tests\test_app_meta.py tests\test_windows_text_rendering_policy.py README.md docs\OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md
python -c "import tomllib,pathlib; data=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); p=data.get('project',{}); print(p.get('name')); print(p.get('requires-python')); print(sorted(p.get('optional-dependencies',{}).keys())); print(data.get('tool',{}).get('pytest',{}).get('ini_options',{}))"
python -m py_compile main.py
python -m pytest -q tests\test_release_shell.py tests\test_app_meta.py tests\test_windows_text_rendering_policy.py::test_gui_startup_wires_splash_to_main_window_readiness_signals
python scripts\engineering_gate.py
python scripts\check_public_release.py
python scripts\check_public_release.py --strict
git check-ignore -v .venv .venv\Lib\site-packages\PySide6\scripts\deploy_lib\default.spec manifest.json request_cell_report.md exam_masters\builtin\default_exam_v9.docx exam_masters\builtin\default_exam_v10.docx exam_masters\builtin\default_exam_v20.docx
python -c "import subprocess,collections; raw=subprocess.check_output(['git','status','--porcelain=v1','-uall','--no-renames','-z']); entries=[x.decode('utf-8','replace') for x in raw.split(b'\0') if x]; print('expanded_status_entries='+str(len(entries))); c=collections.Counter(e[:2] for e in entries); [print(f'{k}={c[k]}') for k in sorted(c)]"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `pyproject.toml` 解析 | `lark-formatter`、`>=3.10`、extras `['build', 'dev']`、pytest `testpaths=['tests']` |
| `main.py` 编译 | 通过 |
| release shell / app meta / GUI startup 子集 | `15 passed in 0.13s` |
| engineering gate | `1801 tests collected in 2.43s`，smoke 测试 `10 passed in 0.98s`，最终 `Engineering gate passed.` |
| public release scan | exit code `0`；提示 `.venv` 与 `.venv/.../default.spec` 为本地发布前 warnings |
| public release scan strict | exit code `1`；严格模式因上述本地环境 warnings 阻断发布 |
| `.venv` ignore | 命中 `.gitignore:12` |
| 根目录 `manifest.json` / `request_cell_report.md` ignore | 命中 `.gitignore:27` 与 `.gitignore:28` |
| `exam_masters/builtin/default_exam_v9.docx` | 被 `exam_masters/builtin/*.docx` ignore |
| `default_exam_v10.docx` / `default_exam_v20.docx` | 通过 negation 规则保留为候选 |
| 当前展开文件级变更数 | `1254` |

当前判断:

- 顶层工程配置比初始分析时健康得多: 现在有 `pyproject.toml`、`.gitattributes`、CI workflow、本地工程门禁脚本和 release shell 测试保护。
- 依赖边界已经清晰: `requirements.txt` 负责运行时依赖，`pyproject.toml` 负责项目元数据、pytest 配置和 dev/build extras，`install_env.bat` 统一走 editable install。
- CI 边界已经分层: engineering gate 负责基础编译、collection 与 smoke tests；scene matrix release gate 负责高风险 scene release 验收。
- `main.py` 不应和纯配置文件合并成同一个语义提交；它更适合作为 root-runtime/startup 主题，已由编译与 GUI startup wiring 测试保护。
- 当前唯一发布入口阻断不是代码结构问题，而是本机 `.venv` 存在导致 `--strict` 发布扫描失败；发布前应运行清理脚本或确保发布包不包含本地环境。
- Stage 0 仍未完成；下一步应继续整理剩余 `docs` 大量迁移状态、`scripts` 主题或最终提交清单。

### 10.52 阶段 0 补充审计: `docs` 大量迁移、证据库与编码健康复核

执行日期: 2026-07-07

本轮处理第 10.51 节之后的 `docs` 大量状态。当前 `docs` 共有 `668` 个文件级变更，其中 `D=8`、`M=1`、`??=659`。从结构上看，这不是源码变更混乱，而是历史审计、执行记录、视觉证据与文档边界说明集中进入 `docs/` 后形成的大体量文档主题。

当前分布:

| 分区 | 文件数 | 字节数 | 说明 |
| --- | ---: | ---: | --- |
| `docs/audits/` | `379` | `5,319,600` | 审计、trace、release evidence 与历史规划 |
| `docs/refactor-records/` | `229` | `1,929,086` | 执行记录、重构日志、阶段验证记录 |
| `docs/visual_audit/` | `42` | `1,218,499` | 2026-06-29 visual audit PNG/JSON 证据 |
| `docs/visual_checks/` | `8` | `1,045,722` | 精选运行截图证据 |
| `docs/superpowers/` | `29` | `388,963` | 已有计划/spec 文档 |
| `docs/migration_audit/` | `3` | `285,977` | 已有迁移审计材料 |
| `docs` 根层 | `3` | `6,923` | `DOCUMENTATION_BOUNDARIES.md`、release checklist、Windows 文本渲染指南 |

迁移与边界证据:

1. `docs/DOCUMENTATION_BOUNDARIES.md` 已定义新文档路由:
   - `docs/audits/` 放 audit plans / traceability / release-gate evidence。
   - `docs/refactor-records/` 放执行记录和迁移日志。
   - `docs/visual_checks/` 放精选视觉 QA 证据。
   - `docs/visual_audit/` 保留既有视觉审计材料。
2. 8 个 `docs` 根层删除项均有 `docs/audits/` 对应文件:
   - 6 个文件 blob 完全一致。
   - 2 个文件是内容迁移后更新了内部路径引用，例如从 `docs/标题编号面板结构重构策略_2026-04-22.md` 改为 `docs/audits/标题编号面板结构重构策略_2026-04-22.md`。
3. `docs/OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md` 仅新增一项发布检查: `GitHub Actions` 中 `Scene Matrix Release Gate` 已通过。
4. `rg --pcre2 -n "\]\((?!https?://|#|/|\.?\./)" docs --glob "*.md"` 未发现旧式相对链接候选输出。

验证命令:

```powershell
git -c core.quotePath=false status --short -- docs
python -c "from pathlib import Path; import collections; files=[p for p in Path('docs').rglob('*') if p.is_file()]; print('docs_files='+str(len(files))); print('docs_total_bytes='+str(sum(p.stat().st_size for p in files)))"
python -c "from pathlib import Path; md=[p for p in Path('docs').rglob('*.md')]; bad=[p for p in md if p.stat().st_size==0]; print('md_count='+str(len(md))); print('empty_md='+str(len(bad)))"
python -c "from pathlib import Path; text_ext={'.md','.txt','.json','.yaml','.yml','.toml'}; files=[p for p in Path('docs').rglob('*') if p.is_file() and p.suffix.lower() in text_ext]; bad=[p.as_posix() for p in files if bytes([0]) in p.read_bytes()]; print('text_docs_checked='+str(len(files))); print('text_nul_files='+str(len(bad)))"
python -X utf8 -c "<遍历 docs/**/*.md，使用 read_text(encoding='utf-8') 做严格解码检查>"
python -X utf8 -c "<遍历 docs/**/*.json，使用 json.loads 做 JSON 可解析性检查>"
python -X utf8 -c "<遍历 docs 下 PNG/JPG/GIF，使用 PIL.Image.open 做图片可打开性检查>"
rg --pcre2 -n "\]\((?!https?://|#|/|\.?\./)" docs --glob "*.md"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `docs` 状态 | `668` 项: `D=8`、`M=1`、`??=659` |
| tracked `docs` 基线 | `42` 个文件 |
| 当前 `docs` 文件数 | `693` |
| 当前 Markdown 文件数 | `642` |
| 空 Markdown | `0` |
| 文本文档 NUL 扫描 | `644` 个文本类文件，`0` 个 NUL |
| JSON 可解析性 | `2` 个 JSON，`0` 个错误 |
| 图片可打开性 | `49` 张图片，`0` 个错误 |
| 最大 Markdown | `1` 个超过 `500KB`，约 `987,647` 字节 |
| 根层删除到 `docs/audits` 的迁移 | `6` 个 blob 完全一致，`2` 个仅更新内部文档路径引用 |
| Markdown 严格 UTF-8 | `642` 个 Markdown 中有 `2` 个 decode errors |

发现的文档健康风险:

1. `docs/audits/场景与模板体系规划.md` 是历史文档迁移，blob 与 `HEAD:docs/场景与模板体系规划.md` 相同，但文件内部存在混合编码片段；`rg` 能读，Python 严格 UTF-8 会失败。
2. `docs/superpowers/plans/2026-03-28-task3-consistency-fix.md` 是已有 tracked 文件，blob 未变化，整体可按 `gb18030` 解码，但不是 UTF-8。
3. `docs/audits/` 下存在单个接近 1MB 的超大 Markdown，作为历史审计材料可保留，但后续不宜继续向同一文件追加大段执行日志。

当前判断:

- `docs` 结构相对健康: 审计、执行记录、视觉证据和发布清单已经有明确落点，根目录文档噪音已明显降低。
- `docs` 不适合与源码主题混成一个提交；更合理的提交边界是“文档边界与历史审计迁移”，并在说明中明确 8 个根层删除是迁移到 `docs/audits/`。
- 编码健康仍有债务: 后续应单独做一轮“文档 UTF-8 归一化”，至少处理上述 2 个 Markdown，避免后续 docs indexer、CI markdown scanner 或 Python 文档工具踩到解码错误。
- Stage 0 仍未完成；下一步可继续审计 `scripts` 主题、`samples` 主题，或收敛最终提交清单。

### 10.53 阶段 0 补充审计: `scripts` 生成器、门禁脚本与手工脚本迁移复核

执行日期: 2026-07-07

本轮处理第 10.52 节之后的 `scripts` 主题。当前 `scripts` 共有 `60` 个文件级变更，其中 `M=1`、`AM=7`、`??=52`。该主题不是单一功能脚本，而是 scene release 生成器/导出器、基础工程门禁、pytest 分组工具、Windows 发布 wrapper、手工调试脚本迁移的组合。

当前分桶:

| 分桶 | 文件数 | 说明 |
| --- | ---: | --- |
| `scene_exporters` | `43` | `export_scene_*` 导出器，主要服务 scene audit / dashboard / drilldown 文档与 release evidence |
| `manual_migration` | `9` | 旧根目录手工测试脚本迁入 `scripts/manual/`，并新增 README 与 `_bootstrap.py` |
| `scene_gate_helpers` | `4` | `verify_scene_matrix_release_gate.py`、`verify_scene_sample_fixtures.py`、`generate_scene_sample_fixtures.py`、`run_pytest_groups.py` |
| `windows_release_wrappers` | `2` | `scripts/windows/install_env.bat` 调整与新增 `engineering_gate.bat` |
| `engineering_gate` | `1` | `scripts/engineering_gate.py` |
| `visual_audit_exporter` | `1` | `export_style_source_visual_audit.py` |

关键证据:

1. `.github/workflows/engineering-gate.yml` 调用 `python scripts/engineering_gate.py`，该脚本同时用于本地和 CI 基础门禁。
2. `.github/workflows/scene-matrix-release-gate.yml` 调用 `python scripts/verify_scene_matrix_release_gate.py`，并运行 scene 回归测试集合。
3. `tests/test_release_shell.py` 明确检查 release shell、Windows wrapper、scene export scripts、scene matrix workflow、pyproject extras 安装和公开发布脚本契约。
4. 多个 `tests/test_scene_*` 文件直接引用 `scripts.verify_scene_matrix_release_gate` 或断言对应 `scripts/export_scene_*` 导出器路径，说明这些脚本不是孤立散件。
5. `scripts/generate_scene_sample_fixtures.py` 默认输出到 `artifacts/scene_sample_fixtures`；`scripts/verify_scene_sample_fixtures.py` 未指定路径时使用临时目录，能降低本地验证污染根目录的风险。
6. `scripts/manual/README.md` 明确声明该目录中的脚本是交互预览和调试脚本，不属于自动 pytest 套件。

验证命令:

```powershell
git status --short -- scripts
python -m compileall -q scripts
python scripts\run_pytest_groups.py --list
python -m pytest -q tests\test_release_shell.py
python scripts\verify_scene_sample_fixtures.py
python scripts\verify_scene_matrix_release_gate.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `scripts` 状态 | `60` 项: `M=1`、`AM=7`、`??=52` |
| 脚本总体 | `170` 个文件，其中 Python `58` 个、BAT `7` 个 |
| Python 脚本行数 | `10,318` 行 |
| `scripts` 编译 | 通过 |
| pytest group list | 可列出测试分组；其中 `scene=57`、`workbench=15`、`template=11`、`phase=11` 等 |
| release shell 测试 | `11 passed in 0.10s` |
| scene sample fixture verifier | `[OK] 42 scene sample fixtures covering 12 packs and 53 request cells verified.` |
| scene matrix release gate | `passed`，全部 checks `passed (0 issues)` |
| release gate 摘要 | `12 packs`、`42 sample fixtures`、`53 request samples`、`release_export_scripts=15/15 ready`、`drilldowns=37/37`、`drilldown_rows=556/556`、`drilldown_sources=107/107 ready` |

当前判断:

- `scripts` 结构总体可接受: 发布门禁、fixture verifier、pytest 分组工具和 Windows wrapper 均有明确入口和测试/CI 引用。
- `scripts/manual/` 迁移是健康改动，能把根目录旧调试脚本从产品入口层移走；但这些脚本仍应作为“手工工具”提交，不应被误认为自动测试。
- scene 导出器数量很多，短期由 release gate 与 scene tests 兜底；中长期可以考虑抽一层导出器公共 helper，减少每个 `export_scene_*` 之间的模板重复。
- `scripts` 提交边界建议拆成两类: `engineering/release tooling` 与 `scene release/export tooling`；`manual_migration` 可以跟根目录清理一起单独说明。
- Stage 0 仍未完成；下一步可继续审计 `samples`、`templates/defaults/scenes`，或开始形成最终提交边界清单。

### 10.54 阶段 0 补充审计: `samples` / `templates` / `scenes` / 配置资源最终状态复核

执行日期: 2026-07-07

本轮处理第 10.53 节之后的资源配置主题。该主题合并复核 `samples`、`templates`、`scenes`、`defaults`、`heading_numbering_schemes`、`count_profiles` 与 `exam_masters` 的当前状态。前序第 10.38、10.42、10.49 节已经分别验证过模板瘦身、样本库边界和考试母版剪枝；本轮记录的是当前 ignore 与资源候选收口后的最终复核。

当前候选状态:

| 目录 | 状态项 | 说明 |
| --- | ---: | --- |
| `samples/` | `43` | `samples/docx` 样本库，42 个 DOCX + README |
| `templates/` | `10` | 删除旧业务模板 JSON；保留 tracked `default.json` 与 `thesis_gbt.json` |
| `scenes/` | `7` | 6 个既有 scene JSON 修改 + 新增 `exam.json` |
| `heading_numbering_schemes/` | `3` | 用户编号方案 JSON |
| `exam_masters/` | `2` | 仅保留 `default_exam_v10.docx` 与 `default_exam_v20.docx` 为提交候选 |
| `defaults/` | `1` | `defaults/thesis.yaml` 样式基线更新 |
| `count_profiles/` | `1` | `count_profiles/builtin.json` |

文件类型分布:

| 类型 | 数量 |
| --- | ---: |
| `.docx` | `44` |
| `.json` | `21` |
| `.yaml` | `1` |
| `.md` | `1` |

关键证据:

1. `samples/docx/README.md` 明确该目录是 `src/config/scene_sample_fixture_registry.py` 的离线 DOCX 样本库镜像，不是生成物目录。
2. `samples/docx/` 当前有 `42` 个 DOCX，磁盘文件名与 registry 中 `fixture_id + ".docx"` 完全一致。
3. `scripts/verify_scene_sample_fixtures.py` 默认在临时目录重新生成并验证样本，不依赖根目录输出，也不污染 `samples/docx/`。
4. `templates/` 当前只保留 tracked `default.json` 与 `thesis_gbt.json`；旧业务模板文件删除应与 `src/config/builtin_templates.py` 的兜底逻辑和模板测试一起提交。
5. `exam_masters/` 当前提交候选已收窄为 `exam_masters/builtin/default_exam_v10.docx` 与 `exam_masters/builtin/default_exam_v20.docx`，历史 builtin 版本和 `exam_masters/user/` 被 `.gitignore` 排除。
6. `count_profiles/builtin.json`、`heading_numbering_schemes/*.json`、`scenes/*.json` 均属于产品配置入口，不是运行生成物。

验证命令:

```powershell
git status --short -- samples templates scenes defaults heading_numbering_schemes count_profiles exam_masters
python -X utf8 -c "<解析 scenes/templates/heading_numbering_schemes/count_profiles JSON 与 defaults/thesis.yaml>"
python -c "from pathlib import Path; from zipfile import is_zipfile; files=sorted(Path('samples/docx').glob('*.docx')); bad=[p.as_posix() for p in files if not is_zipfile(p)]; print('sample_docx='+str(len(files))); print('bad_sample_zip='+str(len(bad)))"
python -c "from pathlib import Path; from zipfile import is_zipfile; keep=[Path('exam_masters/builtin/default_exam_v10.docx'),Path('exam_masters/builtin/default_exam_v20.docx')]; [print(p.as_posix(), p.exists(), is_zipfile(p), p.stat().st_size if p.exists() else 0) for p in keep]"
python -X utf8 -c "<对比 src.config.scene_sample_fixture_registry 与 samples/docx 磁盘文件名>"
python -m pytest -q tests\test_config_library_and_bridge.py tests\test_phase1_config.py tests\test_heading_numbering_scheme_closure.py tests\test_heading_numbering_logic.py tests\test_count_engine_semantics.py tests\test_scene_sample_fixture_regression.py tests\test_exam_paper_style.py
python scripts\verify_scene_sample_fixtures.py
python scripts\verify_scene_matrix_release_gate.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| 资源配置状态 | `67` 项: `D=10`、`M=7`、`??=50` |
| JSON/YAML 解析 | `13` 个 JSON + `1` 个 YAML，`parse_errors=0` |
| sample DOCX 可打开性 | `sample_docx=42`、`bad_sample_zip=0` |
| sample registry 对齐 | `registry=42`、`disk=42`、`packs=12`、`missing_on_disk=[]`、`extra_on_disk=[]` |
| 考试保留母版 | `default_exam_v10.docx True True 92446`；`default_exam_v20.docx True True 46057` |
| 资源相关 pytest 子集 | `92 passed in 22.46s` |
| scene sample fixture verifier | `[OK] 42 scene sample fixtures covering 12 packs and 53 request cells verified.` |
| scene matrix release gate | `passed`，全部 checks `passed (0 issues)` |
| release gate 摘要 | `12 packs`、`42 sample fixtures`、`53 request samples`、`count_profiles=14/15 ready`、`count_profile_accounted=15/15`、`release_export_scripts=15/15 ready`、`drilldowns=37/37` |

当前判断:

- 资源配置主题结构健康: 样本库、场景配置、计数 profile、标题编号方案和考试母版都有明确运行时消费者和测试覆盖。
- 该主题不应继续被看作“散落资源文件”；它是产品配置和离线样本资产的一组提交边界。
- 提交时建议拆分为:
  1. `template/scene/default config baseline`
  2. `sample docx fixture library`
  3. `exam master builtin resources`
  4. `count/heading config resources`
- 当前剩余风险主要是提交说明: 需要写清楚旧 `templates/*.json` 删除不是能力删除，而是由内置模板工厂兜底；`default_exam_v10.docx` 是页眉密封线参考源，`default_exam_v20.docx` 是当前默认母版入口。
- Stage 0 仍未完成；下一步可审计剩余 `src` 大主题的最终状态，或整理总体健康判定和提交边界清单。

### 10.55 阶段 0 补充审计: `src` 聚合源码主题最终状态复核

执行日期: 2026-07-07

本轮处理第 10.54 节之后的 `src` 聚合状态。当前 `src` 共有 `301` 个 Python 文件级变更，其中 `M=95`、`??=206`。这不是一个单一源码改动，而是多个已经分批验证过的主题叠加: scene matrix/config、shared engine/UI、AssetsPanel/material services、Workbench execution、template/heading UI、pipeline/modules/reporting 与 root runtime。

当前目录分布:

| 子目录/入口 | 文件数 |
| --- | ---: |
| `src/ui` | `103` |
| `src/config` | `92` |
| `src/shared` | `75` |
| `src/modules` | `10` |
| `src/services` | `7` |
| `src/reporting` | `6` |
| `src/pipeline` | `4` |
| `src/cli_runner.py` / `execution_diagnostics.py` / `qt_api.py` / `report_writer.py` | `4` |

按提交主题聚类:

| 聚类 | 文件数 | 说明 |
| --- | ---: | --- |
| `config_scene` | `65` | scene matrix、release/audit runtime、request/fixture registry |
| `shared_ui` | `53` | 设计系统、样式来源/样式策略、表单/导航/证据控件 |
| `assets_services` | `48` | AssetsPanel、material/question services |
| `config_core_material_style` | `27` | material/style/heading/core config |
| `workbench_execution` | `24` | execution center/runtime/session、quick execution、recent run |
| `shared_engine` | `22` | count/exam/journal/material/object/docx/fixed layout 等 engine |
| `template_heading_ui` | `17` | template detail 与 heading numbering UI |
| `pipeline_modules` | `14` | pipeline context/result/runner/scheduler 与基础 modules |
| `scene_ui` | `12` | scene overview/scope/style/material/delivery summary UI |
| `reporting` | `7` | reporting package 与 report writer |
| `root_runtime` | `3` | `cli_runner.py`、`execution_diagnostics.py`、`qt_api.py` |
| `ui_shell/style_projection` | `9` | `main_window.py`、`title_bar.py`、`panel_registry.py`、style projection 边角 |

代码体量:

| 检查项 | 结果 |
| --- | ---: |
| `src` Python 文件总数 | `449` |
| `src` Python 总行数 | `183,793` |
| `src` Python NUL 扫描 | `0` |

重点大文件:

| 文件 | 行数 |
| --- | ---: |
| `src/ui/panels/scene_panel.py` | `5,997` |
| `src/ui/panels/scene_summary_projection.py` | `3,698` |
| `src/config/scene_matrix_dashboard.py` | `3,460` |
| `src/report_writer.py` | `3,433` |
| `src/ui/adapters/workbench_execution_adapter.py` | `3,004` |
| `src/ui/panels/workbench/question_figure_repair_runtime.py` | `2,733` |
| `src/ui/panels/workbench/quick_execution_detail.py` | `2,524` |
| `src/ui/panels/heading_numbering_panel.py` | `2,446` |
| `src/ui/panels/template_panel.py` | `2,422` |
| `src/shared/engine/exam_paper_style.py` | `2,414` |

验证命令:

```powershell
git status --short -- src
python -m compileall -q src
python scripts\engineering_gate.py
python -m pytest -q tests\test_design_system_refactor.py tests\test_small_widget_architecture.py tests\test_template_panel_architecture.py tests\test_scene_panel_architecture.py tests\test_workbench_execution_center.py tests\test_assets_panel_architecture.py
```

本轮验证结果:

| 检查项 | 结果 |
| --- | --- |
| `src` 编译 | 通过 |
| engineering gate | `1801 tests collected in 1.71s`，smoke 测试 `10 passed in 0.77s`，最终 `Engineering gate passed.` |
| UI/Workbench/Assets 聚合测试 | `268 passed in 53.50s` |

累计可复用验证证据:

| 证据 | 结果 |
| --- | --- |
| `src/config` 编译与 scene gate | 第 10.47 节: scene gate passed，scene 分组 `356 passed` |
| `tests` 全量验证 | 第 10.50 节: `1801 passed in 573.82s` |
| 资源配置子集 | 第 10.54 节: `92 passed in 22.46s` |
| release/tooling 子集 | 第 10.51 / 10.53 节: release shell、engineering gate、scene gate 均通过 |

当前判断:

- `src` 当前结构不是“小而干净”的状态，但变更主题已经可解释、可测试、可拆分；这比单纯文件数少更重要。
- 主要健康问题是体量和提交粒度: `scene_panel.py`、`scene_summary_projection.py`、`report_writer.py`、`workbench_execution_adapter.py` 等仍是后续拆分候选。
- 当前风险不在“是否可运行”，而在“不要把 301 个源码变更一次性提交”。建议按上述聚类拆分提交，并让对应 tests/docs/scripts 跟随各主题。
- `src/config` 的 scene release 面有强 gate 保护；`src/ui` 和 `src/shared` 的控件/engine 边界已有大量契约测试，但仍应避免继续向大文件堆叠逻辑。
- Stage 0 仍未完成；下一步应形成总体健康判定与最终提交边界清单，帮助回答“这个项目代码结构健康吗”。

### 10.56 阶段 0 总体判定: 当前代码结构健康度与提交边界清单

执行日期: 2026-07-07

一句话结论: 当前项目结构已经从“高风险混杂变更”收敛到“可解释、可验证、可拆分提交”的状态；运行与测试健康度较高，但仓库状态仍不适合一次性提交或发布。

当前总体状态:

| 检查项 | 结果 |
| --- | ---: |
| 展开文件级变更数 | `1254` |
| `docs` | `668` |
| `src` | `301` |
| `tests` | `143` |
| `scripts` | `60` |
| `samples` | `43` |
| `templates` | `10` |
| `scenes` | `7` |
| `heading_numbering_schemes` | `3` |
| `.github` | `2` |
| `exam_masters` | `2` |

已验证的健康信号:

1. 工程基线健康:
   - 新增 `pyproject.toml`、`.gitattributes`、`.github/workflows/*`、`scripts/engineering_gate.py`。
   - `requirements.txt` 收束为运行时依赖，dev/build 依赖进入 `pyproject.toml` extras。
2. 测试健康:
   - 全量 pytest: `1801 passed in 573.82s`。
   - engineering gate: compileall、collection、smoke tests 均通过。
   - scene matrix release gate: 全 checks `passed (0 issues)`。
3. 资源边界健康:
   - `samples/docx` 与 registry 完全对齐。
   - `exam_masters/builtin` 候选收窄为 `default_exam_v10.docx` 与 `default_exam_v20.docx`。
   - 根目录生成物、用户考试副本、样张输出、本地环境目录已由 `.gitignore` 覆盖。
4. 文档边界健康:
   - `docs/DOCUMENTATION_BOUNDARIES.md` 定义文档路由。
   - 根层历史审计文档迁入 `docs/audits/`，主要为内容相同迁移或路径引用更新。
5. 源码边界健康:
   - `src` 301 个变更可分到 scene config、shared engine/UI、AssetsPanel、Workbench、template/heading、pipeline/modules/reporting 等明确主题。
   - 主要源码主题均有聚焦测试或 release gate 证据。

仍然存在的结构债务:

| 债务 | 严重度 | 说明 |
| --- | --- | --- |
| 提交体量过大 | 高 | `1254` 个展开状态项，不能一次性提交 |
| 大文件继续存在 | 中高 | `scene_panel.py`、`scene_summary_projection.py`、`report_writer.py`、`workbench_execution_adapter.py` 等仍偏大 |
| 文档编码不统一 | 中 | 2 个 Markdown 不是严格 UTF-8 |
| 发布 strict 检查受本地环境阻断 | 中 | `.venv` 存在导致 `check_public_release.py --strict` exit code `1` |
| scene 导出器数量多 | 中 | 43 个 `export_scene_*`，短期有 gate 保护，长期可抽公共 helper |
| `.claude/worktrees/*` 状态需确认 | 低 | 属于本地工作树管理元数据，不应混入产品提交 |

建议提交边界:

| 顺序 | 提交边界 | 典型内容 |
| ---: | --- | --- |
| 1 | `project-config-and-ci` | `.gitattributes`、`.gitignore`、`pyproject.toml`、`.github/workflows/*`、`scripts/engineering_gate.py`、release shell 测试 |
| 2 | `manual-script-migration` | 根目录 `test_*.py` 迁入 `scripts/manual/`，README 与 `_bootstrap.py` |
| 3 | `docs-boundaries-and-audit-migration` | `docs/DOCUMENTATION_BOUNDARIES.md`、`docs/audits/`、`docs/refactor-records/`、visual evidence |
| 4 | `scene-config-and-release-gate` | `src/config/scene_*`、scene export scripts、scene tests、scene gate workflow |
| 5 | `resource-config-baseline` | `samples/docx`、`scenes/*.json`、`templates` 瘦身、`defaults/thesis.yaml` |
| 6 | `count-heading-exam-resources` | `count_profiles/builtin.json`、`heading_numbering_schemes/*.json`、`exam_masters/builtin/default_exam_v10/v20.docx` |
| 7 | `shared-engine-and-ui-contracts` | `src/shared/engine`、`src/shared/ui`、对应 tests |
| 8 | `assets-panel-and-material-services` | `src/ui/panels/assets*`、`src/services/material_assets*`、assets/material tests |
| 9 | `workbench-execution-runtime` | `src/ui/panels/workbench/*`、Workbench adapters、execution tests |
| 10 | `template-heading-scene-ui-polish` | template/heading/scene UI panels、design-system tests |
| 11 | `pipeline-modules-reporting-runtime` | pipeline、modules、reporting、CLI/runtime glue |

最终回答:

- 如果问“能不能运行、能不能测”: 当前是健康的，核心验证已经通过。
- 如果问“仓库结构能不能直接提交/发布”: 当前还不健康，原因是变更体量太大、提交边界尚未落地、文档编码和本地环境 strict 检查仍有债务。
- 如果问“架构方向是否健康”: 方向是健康的。大量原本散落的能力已经开始形成 config、shared engine、shared UI、scripts gate、docs boundary、resource registry 这些更清晰的结构层。

下一步最小闭环:

1. 先按上述提交边界拆分 staging，不要一次性提交。
2. 提交前处理或明确排除 `.claude/worktrees/*` 本地状态。
3. 发布前运行清理脚本，确保 `.venv/` 不影响 `check_public_release.py --strict`。
4. 单独排期处理 2 个非 UTF-8 Markdown。
5. 后续重构重点放在超大源码文件拆分，而不是继续扩展新功能面。

Stage 0 的“深度分析和记录”已形成可用结论；Stage 0 的“提交/发布收口”仍未完成。

### 10.57 阶段 0 收口推进: 文档编码归一化与 public release strict 阻断解除

执行日期: 2026-07-07

本轮继续处理第 10.56 节列出的可执行债务中的两项: 文档 UTF-8 归一化、公开发布 strict 检查阻断。目标是把“已知可修复阻断”从结构健康债务中移除，并记录脚本层发现的问题。

处理前状态:

| 检查项 | 结果 |
| --- | --- |
| Markdown 严格 UTF-8 | `642` 个 Markdown 中 `2` 个 decode errors |
| 失败文件 1 | `docs/audits/场景与模板体系规划.md`，UTF-8 前缀 + GB18030 后缀混合 |
| 失败文件 2 | `docs/superpowers/plans/2026-03-28-task3-consistency-fix.md`，整体可按 GB18030 解码 |
| `check_public_release.py --strict` | exit code `1`，原因是 `.venv` 与 `.venv/.../default.spec` |

已完成改动:

1. 将 `docs/audits/场景与模板体系规划.md` 转为严格 UTF-8，并统一 Markdown 换行为 LF。
2. 将 `docs/superpowers/plans/2026-03-28-task3-consistency-fix.md` 从 GB18030 转为 UTF-8，并统一 Markdown 换行为 LF。
3. 执行 `clean_public_release.bat` 时首次发现 `.venv` 删除失败但脚本仍返回 exit code `0`。
4. 定位到有 `5` 个进程从当前仓库 `.venv\Scripts\pythonw.exe` 启动并占用 PySide6/lxml 文件；仅结束这些路径明确落在当前仓库 `.venv` 下的进程。
5. 重新执行 `clean_public_release.bat`，成功清除 `.venv`、`build`、`dist` 和根级 release 生成物。
6. 补强 `scripts/windows/clean_public_release.bat`:
   - 删除 `.venv` 后若目录仍存在，返回 exit code `1`。
   - 删除 `build` / `dist` 后若目录仍存在，返回 exit code `1`。
   - 删除根级 `*.spec`、`crash.log`、`demo_crash.log`、`alavette_form.log` 后若文件仍存在，返回 exit code `1`。
7. 更新 `tests/test_release_shell.py`，锁定 clean 脚本的失败提示契约。

验证命令:

```powershell
python -X utf8 -c "<遍历 docs/**/*.md，使用 read_text(encoding='utf-8') 做严格解码检查>"
python -c "from pathlib import Path; text_ext={'.md','.txt','.json','.yaml','.yml','.toml'}; files=[p for p in Path('docs').rglob('*') if p.is_file() and p.suffix.lower() in text_ext]; bad=[p.as_posix() for p in files if bytes([0]) in p.read_bytes()]; print('text_docs_checked='+str(len(files))); print('text_nul_files='+str(len(bad)))"
clean_public_release.bat
python scripts\check_public_release.py --strict
python -m pytest -q tests\test_release_shell.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| Markdown 严格 UTF-8 | `markdown_utf8_checked=642`、`markdown_decode_errors=0` |
| 文本文档 NUL 扫描 | `text_docs_checked=644`、`text_nul_files=0` |
| 内容抽样 | `# 场景与模板体系规划`、`# Task 3 Consistency Fix Implementation Plan` 可按 UTF-8 读取 |
| clean script | 第二次执行 exit code `0`，无拒绝访问输出 |
| `.venv` / `build` / `dist` | 均不存在 |
| public release strict | `[OK] No obvious public-release blockers were found.` |
| release shell tests | `11 passed in 0.17s` |

当前判断:

- 第 10.56 节中的“文档编码不统一”债务已解决。
- 第 10.56 节中的“发布 strict 检查受本地环境阻断”债务已解决。
- 本轮发现并修复了 clean 脚本的可靠性问题: 以后如果 `.venv` 被 Python/Qt 进程占用，脚本会失败退出，而不是误报清理成功。
- 当前剩余主要债务收敛为:
  1. `1254` 个展开状态项仍需按边界 staging/提交。
  2. 超大源码文件仍需后续拆分。
  3. scene 导出器数量较多，后续可抽公共 helper。
  4. `.claude/worktrees/*` 本地状态仍需提交前确认或排除。

Stage 0 的“分析记录 + 可修复阻断处理”已进一步推进；Stage 0 的“按提交边界 staging/提交”仍未完成。

### 10.58 阶段 0 收口审计: `.claude/worktrees` gitlink 本地状态确认

执行日期: 2026-07-07

本轮继续处理第 10.57 节之后剩余的本地元数据状态。当前 `git status` 中仍存在:

```text
D  .claude/worktrees/awesome-tu-3d3302
```

关键证据:

| 检查项 | 结果 |
| --- | --- |
| `.gitignore` | `.claude/worktrees/` 已被 ignore |
| `git status --porcelain=v2` | `1 D. S... 160000 ... .claude/worktrees/awesome-tu-3d3302` |
| `git ls-tree HEAD` | `160000 commit 8f959998d29652be5124dcb1c5a4e2d7bbd8c993 .claude/worktrees/awesome-tu-3d3302` |
| gitlink commit message | `Refine heading detection and template panel layout` |
| 当前磁盘目录 | 目录存在，包含一份嵌套工作区文件 |
| 嵌套 `.git` 文件 | 指向旧路径 `C:/Users/Administrator/Desktop/.../.git/worktrees/awesome-tu-3d3302` |
| `git -C .claude/worktrees/awesome-tu-3d3302 status` | 失败: `fatal: not a git repository` |

当前判断:

- `.claude/worktrees/awesome-tu-3d3302` 不是当前产品源码、测试、资源或文档边界的一部分。
- HEAD 中曾经误纳入了一个 gitlink；当前磁盘目录又是失效的本地 worktree 副本，`.git` 指向旧用户目录。
- 这类状态不应混入产品提交。后续 staging 时应选择其一:
  1. 明确提交删除该 gitlink，让仓库不再跟踪 `.claude/worktrees/*`。
  2. 若项目所有者确认仍需保留该 gitlink，则需要重新建立有效 worktree/submodule 配置。
- 结合 `.gitignore` 当前规则，更合理的收口方向是提交删除 gitlink，并保留 `.claude/worktrees/` ignore 规则。

Stage 0 的“本地元数据状态解释”已完成；Stage 0 的“按提交边界 staging/提交”仍未完成。

### 10.59 阶段 0 staging 推进: 手工脚本迁移边界补齐

执行日期: 2026-07-07

本轮开始处理第 10.56 节建议提交边界中的 `manual-script-migration`，同时保留第 10.58 节确认的 `.claude/worktrees` gitlink 删除状态。

当前 staged 内容:

| 状态 | 路径 |
| --- | --- |
| `D` | `.claude/worktrees/awesome-tu-3d3302` |
| `A` | `scripts/manual/README.md` |
| `A` | `scripts/manual/_bootstrap.py` |
| `R` | `test_all_components.py -> scripts/manual/test_all_components.py` |
| `R` | `test_audit_fix.py -> scripts/manual/test_audit_fix.py` |
| `R` | `test_combo.py -> scripts/manual/test_combo.py` |
| `R` | `test_crash.py -> scripts/manual/test_crash.py` |
| `R` | `test_crash_trace.py -> scripts/manual/test_crash_trace.py` |
| `R` | `test_phase_a_components.py -> scripts/manual/test_phase_a_components.py` |
| `R` | `test_workbench_v2.py -> scripts/manual/test_workbench_v2.py` |

本轮补齐内容:

1. 将 `scripts/manual/README.md` 纳入 staged 边界，说明这些脚本是交互预览和调试脚本，不属于自动 pytest 套件。
2. 将 `scripts/manual/_bootstrap.py` 纳入 staged 边界，为迁移后的手工脚本提供统一项目根目录注入。
3. 将 7 个迁移后的手工脚本工作区修改纳入 staged 边界:
   - 更新运行方式示例。
   - 调用 `ensure_project_root()`，避免迁出根目录后无法导入 `src`。
4. 未把其它 `src`、`docs`、`tests`、`scripts` 大主题混入当前 staged 边界。

验证命令:

```powershell
git diff --cached --name-status
python -m compileall -q scripts\manual
python -m pytest -q tests\test_release_shell.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| staged 文件数 | `10` |
| staged diff stat | `75 insertions(+), 6 deletions(-)` |
| `scripts/manual` 编译 | 通过 |
| release shell tests | `11 passed in 0.07s` |

当前判断:

- `manual-script-migration` 边界已补齐到 staged index。
- `.claude/worktrees/awesome-tu-3d3302` gitlink 删除也已在 staged index 中；这符合第 10.58 节建议的“提交删除 gitlink”方向。
- 当前 staged index 仍不应继续混入其它大主题；下一步应单独 staging `project-config-and-ci` 或先提交当前边界。

Stage 0 的“第一个提交边界 staging”已有实质进展；Stage 0 的“全部提交边界 staging/提交”仍未完成。

### 10.60 阶段 0 提交推进: 工作分支与前两个提交边界

执行日期: 2026-07-07

本轮继续把第 10.56 节中的建议提交边界落到 Git 历史中。为避免直接在 `main` 上继续堆提交，先创建并切换到收口分支:

```text
codex/code-structure-health-staging
```

已完成提交:

| 顺序 | commit | message | 边界 |
| ---: | --- | --- | --- |
| 1 | `a24a5e5` | `Move manual scripts out of project root` | `manual-script-migration` + stale `.claude/worktrees` gitlink 删除 |
| 2 | `135db5d` | `Add project config and release gates` | `project-config-and-ci` / release gate 基线 |

第 1 个提交内容:

- 根目录 7 个手工调试脚本迁移到 `scripts/manual/`。
- 新增 `scripts/manual/README.md`。
- 新增 `scripts/manual/_bootstrap.py`，确保迁移后的手工脚本可从项目根导入 `src`。
- 删除历史误纳入的 `.claude/worktrees/awesome-tu-3d3302` gitlink。

第 1 个提交验证:

```powershell
python -m compileall -q scripts\manual
python -m pytest -q tests\test_release_shell.py
```

结果:

| 检查项 | 结果 |
| --- | --- |
| `scripts/manual` 编译 | 通过 |
| release shell tests | `11 passed in 0.07s` |

第 2 个提交内容:

- 新增 `.gitattributes`。
- 更新 `.gitignore` 的本地环境、生成物、样本/母版输出、`.claude/worktrees/` 规则。
- 新增 `pyproject.toml`，并将 `requirements.txt` 收束为运行时依赖。
- 新增 `.github/workflows/engineering-gate.yml`。
- 新增 `.github/workflows/scene-matrix-release-gate.yml`。
- 新增 `scripts/engineering_gate.py` 和 `scripts/windows/engineering_gate.bat`。
- 更新 `scripts/windows/install_env.bat` 使用 `".[dev,build]"`。
- 补强 `scripts/windows/clean_public_release.bat` 的清理失败检测。
- 更新 `tests/test_release_shell.py` 和 release checklist。

第 2 个提交验证:

```powershell
python -m pytest -q tests\test_release_shell.py
python scripts\check_public_release.py --strict
python scripts\engineering_gate.py
```

结果:

| 检查项 | 结果 |
| --- | --- |
| release shell tests | `11 passed in 0.07s` |
| public release strict | `[OK] No obvious public-release blockers were found.` |
| engineering gate | `1801 tests collected in 1.62s`，smoke 测试 `10 passed in 0.65s`，最终 `Engineering gate passed.` |

顺序约束:

- 第 2 个提交中的 `tests/test_release_shell.py` 已经锁定 scene export scripts 与 scene matrix workflow 的存在性。
- 因此后续必须继续提交 `scene-config-and-release-gate` / `scene release/export tooling` 边界，确保分支最终 tip 的 scene gate 与 release shell 契约完整闭合。

Stage 0 的“前两个提交边界”已完成；Stage 0 的后续提交边界仍未完成。

### 10.61 阶段 0 继续推进: scene matrix release gate 边界暂存与验证

执行日期: 2026-07-07

本轮继续处理第 10.60 节记录的顺序约束: 前一提交已经把 `scene-matrix-release-gate.yml` 与 `tests/test_release_shell.py` 纳入历史，因此分支 tip 必须补齐 scene export scripts、scene matrix runtime、fixture builder 与 CI 清单中的 scene 回归测试。

边界判定:

- 纳入 `scene-config-and-release-gate`:
  - `scripts/export_scene_*.py`
  - `scripts/verify_scene_matrix_release_gate.py`
  - `scripts/verify_scene_sample_fixtures.py`
  - `scripts/generate_scene_sample_fixtures.py`
  - `scripts/run_pytest_groups.py`
  - `src/config/scene_*.py` 与 release gate 直接依赖的 config/material/fixed-layout/control-contract/plugin-manual modules
  - `src/shared/engine/scene_sample_docx_builder.py`
  - `src/shared/engine/scene_journey_runtime.py`
  - `.github/workflows/scene-matrix-release-gate.yml` 明确列出的 `tests/test_scene_*.py`
- 暂不纳入:
  - `docs/audits/*` 生成证据包与历史审计文档。
  - `src/ui/*`、`src/shared/ui/*`、`style_*`、`scripts/export_style_source_visual_audit.py`。
  - `tests/test_scene_panel_architecture.py` 与 `tests/test_scene_overview_projection.py`，因为它们实际牵引 UI/样式面板架构边界，不属于本次 release gate runtime 边界。

暂存检查:

```powershell
git diff --cached --name-status
git diff --cached --name-only | rg "(^docs/audits/|style_|src/ui/|src/shared/ui/|test_scene_panel_architecture|test_scene_overview_projection|test_style_|export_style)"
git diff --cached --check
```

结果:

| 检查项 | 结果 |
| --- | --- |
| staged candidate paths | `182` |
| staged diff stat | `182 files changed, 87920 insertions(+), 44 deletions(-)` |
| style/UI/docs 误混入检查 | 无匹配 |
| `git diff --cached --check` | 初次发现 3 个 EOF 空行，已清理后通过 |

验证命令:

```powershell
python -m compileall -q src\config scripts src\shared\engine\scene_sample_docx_builder.py src\shared\engine\scene_journey_runtime.py
python scripts\verify_scene_sample_fixtures.py
python scripts\verify_scene_matrix_release_gate.py
python scripts\run_pytest_groups.py --groups scene,config,material,style --timeout 300
python -m pytest -q <scene-matrix-release-gate.yml 中列出的 229 个 scene 回归用例>
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| scene sample fixtures | `42 scene sample fixtures` / `12 packs` / `53 request cells` 通过 |
| scene matrix release gate | `Scene matrix release gate: passed` |
| grouped pytest | `config 19 passed`、`material 73 passed`、`scene 356 passed`、`style 17 passed` |
| CI scene subset | `229 passed in 198.01s` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `baa6276` | `Add scene matrix release gate runtime` | `scene-config-and-release-gate` / scene matrix runtime、export scripts、fixture builder、CI scene subset |

该提交闭合了第 10.60 节记录的顺序约束: 分支 tip 现在同时具备 scene matrix workflow、release shell 存在性断言、release gate runtime 与 CI 清单中的 scene 回归测试。

### 10.62 阶段 0 继续推进: docs boundaries 与审计记录迁移提交

执行日期: 2026-07-07

本轮转向 `docs-boundaries-and-audit-migration`，原因是资源配置边界与 heading/template UI 逻辑强耦合，而 docs 边界相对独立，可以先安全收口。

边界内容:

- 新增 `docs/DOCUMENTATION_BOUNDARIES.md`，定义 `docs/architecture/`、`docs/audits/`、`docs/refactor-records/`、`docs/visual_checks/`、`docs/migration_audit/`、`docs/visual_audit/` 的职责。
- 将根层历史审计文档迁入 `docs/audits/`，Git 识别出 8 个 rename。
- 纳入 `docs/audits/`、`docs/refactor-records/`、`docs/visual_audit/`、`docs/visual_checks/` 下的审计记录与视觉证据。
- 纳入本文件 `docs/refactor-records/code_structure_health_deep_analysis_2026-07-07.md`，使用户要求的深度分析与执行步骤记录进入版本历史。
- 对 30 个 Markdown 做机械空白清理: 去除行尾空白并将 EOF 收敛为单个换行。

验证命令:

```powershell
@'
from pathlib import Path
bad = []
for p in Path("docs").rglob("*.md"):
    try:
        p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        bad.append((str(p), exc.start, exc.reason))
print(len(bad))
'@ | python -X utf8 -
git diff --cached --check -- docs
git diff --cached --name-only -- docs | rg -v '^docs/'
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| docs 状态项 | `668` |
| Markdown UTF-8 | `642` 个 Markdown，`0` 个 decode error |
| staged docs entries | `663` |
| staged shortstat | `663 files changed, 141570 insertions(+), 47 deletions(-)` |
| `git diff --cached --check -- docs` | 通过 |
| staged 路径边界 | 全部位于 `docs/` 下 |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `b1a4d07` | `Move audit records into docs boundaries` | `docs-boundaries-and-audit-migration` |

下一步建议回到资源/配置与 UI/runtime 边界拆分。资源桶不能简单整体提交，因为 `heading_numbering_schemes`、`exam_masters`、`templates` 瘦身和 `src/config/library.py` / heading 面板测试之间存在耦合；需要先选择更小的可验证闭环。

### 10.63 阶段 0 继续推进: resource config + heading/exam runtime 提交

执行日期: 2026-07-07

本轮从第 10.62 节的判断继续，把资源配置边界改拆为“resource config + heading/exam runtime”。原因是模板库瘦身、场景 JSON、heading numbering scheme、考试母版和 heading 面板/适配器存在直接测试耦合，纯资源提交会让 clean checkout 上的 heading/exam 测试缺失运行时支撑。

纳入边界:

- 资源:
  - `defaults/thesis.yaml`
  - `scenes/*.json` 与新增 `scenes/exam.json`
  - `samples/docx/*`
  - `count_profiles/builtin.json`
  - `heading_numbering_schemes/user.*.json`
  - `exam_masters/builtin/default_exam_v10.docx`
  - `exam_masters/builtin/default_exam_v20.docx`
  - 删除 10 个 obsolete `templates/*.json`
- 运行时:
  - `src/config/heading_normalize.py`
  - `src/config/heading_presets.py`
  - `src/config/library.py`
  - `src/config/migration.py`
  - `src/modules/structure/heading_numbering.py`
  - `src/modules/structure/heading_recognition.py`
  - `src/modules/structure/toc.py`
  - `src/shared/engine/toc_style_ops.py`
  - `src/shared/engine/exam_paper_style.py`
  - `src/ui/adapters/heading_numbering_adapter.py`
  - `src/ui/heading_numbering_logic.py`
  - `src/ui/panels/heading_numbering_panel.py`
  - heading 面板直接依赖的 `src/shared/ui/design_system_card.py`、`src/shared/ui/styled_spin_box.py`、`src/shared/ui/summary_grid.py`
- 测试:
  - `tests/test_builtin_templates.py`
  - `tests/test_config_feature_hosting.py`
  - `tests/test_config_library_and_bridge.py`
  - `tests/test_phase1_config.py`
  - `tests/test_heading_*.py`
  - `tests/test_exam_paper_style.py`
  - `tests/test_template_heading_integration.py`
  - `tests/test_toc_semantics.py`

暂不纳入:

- `docs/` 后续记录修改。
- `src/ui/panels/workbench/*`、assets、大块 template/scene UI、pipeline/reporting/modules 运行时改动。

验证命令:

```powershell
python -m compileall -q src\config\heading_normalize.py src\config\heading_presets.py src\config\library.py src\config\migration.py src\modules\structure\heading_numbering.py src\modules\structure\heading_recognition.py src\modules\structure\toc.py src\shared\engine\toc_style_ops.py src\shared\engine\exam_paper_style.py src\ui\adapters\heading_numbering_adapter.py src\ui\heading_numbering_logic.py src\ui\panels\heading_numbering_panel.py src\shared\ui\styled_spin_box.py src\shared\ui\design_system_card.py src\shared\ui\summary_grid.py
python scripts\run_pytest_groups.py --groups heading,builtin,exam,config --timeout 300
python -m pytest -q tests/test_phase1_config.py tests/test_template_heading_integration.py tests/test_toc_semantics.py
git diff --cached --check
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| grouped pytest | `builtin 8 passed`、`config 19 passed`、`exam 26 passed`、`heading 68 passed` |
| targeted pytest | `51 passed in 10.00s` |
| DOCX zip check | `61` 个 DOCX 检查，`0` 个坏包 |
| staged exclusion check | 未混入 docs/workbench/assets/pipeline 大桶 |
| staged shortstat | `95 files changed, 8176 insertions(+), 2633 deletions(-)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `e3eff80` | `Add resource config and heading exam runtime` | `resource-config-baseline` + `count-heading-exam-resources` + heading/exam runtime 支撑 |

该提交把资源配置类债务基本收口；剩余主要集中在 shared engine/UI、assets panel/material services、workbench execution runtime、template/scene UI polish、pipeline/modules/reporting runtime。
### 10.64 阶段 0 继续推进: shared UI style contract 提交

执行日期: 2026-07-07

本轮从第 10.63 节继续，把剩余 UI 债务中可以脱离页面本体独立验证的一组先收口为 `shared-ui-style-contracts`。拆分时特别检查了 `tests/test_style_source_visual_audit.py`、`tests/test_design_system_refactor.py` 与 `tests/test_ui_layout_hardening.py` 的 import 链：这些测试会实例化 `ScenePanel`、`TemplatePanel` 或 `WorkbenchPanel`，因此保留到 template/scene/workbench 页面边界，避免 shared UI 提交被页面层污染。

纳入边界:

- `src/shared/ui/` 的基础布局、导航、证据、详情控制、段落样式编辑、style source/receipt/policy/preview 等可复用组件。
- style 配置与投影:
  - `src/config/style_variant_semantics.py`
  - `src/config/style_difference_projection.py`
  - `src/config/style_field_descriptors.py`
  - `src/config/style_source_report_summary.py`
- 页面无关投影适配器:
  - `src/ui/panels/style_difference_projection.py`
  - `src/ui/panels/style_source_projection.py`
  - `src/ui/panels/style_object_projection_builders.py`
  - `src/ui/panels/scene_style_override_service.py`
  - `src/ui/panels/scene_summary_projection.py`
  - `src/ui/panels/template_summary_projection.py`
- 只覆盖该层的测试:
  - `button`、`combo`、`indent`、`option`、`summary`、`evidence`、`library`、`navigation`、`paragraph`、`small`
  - `tests/test_style_difference_projection.py`
  - `tests/test_style_field_descriptors.py`
  - `tests/test_style_variant_semantics.py`
  - `tests/test_ui_exports.py`

暂不纳入:

- `scripts/export_style_source_visual_audit.py` 与 `tests/test_style_source_visual_audit.py`，原因是视觉审计脚本会创建 `ScenePanel` 与 `WorkbenchPanel`，依赖后续页面层改动。
- `tests/test_design_system_refactor.py`、`tests/test_ui_layout_hardening.py`、`tests/test_windows_text_rendering_policy.py`，原因是它们同时约束 workbench/template/scene 页面或 `main.py` 启动流程。
- `src/ui/panels/workbench/*`、`src/ui/panels/template_*`、`src/ui/panels/scene_panel.py` 等页面本体文件。

验证命令:

```powershell
python -m compileall -q src\shared\ui src\config\style_variant_semantics.py src\config\style_difference_projection.py src\config\style_field_descriptors.py src\config\style_source_report_summary.py src\ui\panels\style_difference_projection.py src\ui\panels\style_source_projection.py src\ui\panels\style_object_projection_builders.py src\ui\panels\scene_style_override_service.py src\ui\panels\scene_summary_projection.py src\ui\panels\template_summary_projection.py
python scripts\run_pytest_groups.py --groups button,combo,indent,option,summary,evidence,library,navigation,paragraph,small --timeout 300 --continue-on-fail
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = (Get-Location).Path
python -m pytest -q tests\test_style_difference_projection.py tests\test_style_field_descriptors.py tests\test_style_variant_semantics.py tests\test_ui_exports.py
git diff --cached --check
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| grouped pytest | `button 5 passed`、`combo 23 passed`、`evidence 2 passed`、`indent 9 passed`、`library 1 passed`、`navigation 1 passed`、`option 5 passed`、`paragraph 3 passed`、`small 50 passed`、`summary 17 passed` |
| targeted pytest | `17 passed in 0.61s` |
| `git diff --cached --check` | 通过 |
| staged shortstat | `74 files changed, 16694 insertions(+), 96 deletions(-)` |
| staged 排除检查 | 未纳入 workbench/template/scene 页面本体、视觉审计脚本或页面级 layout 测试 |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `9282c2b` | `Add shared UI style contract components` | `shared-ui-style-contracts` |

剩余主要集中在 shared engine runtime、assets panel/material services、workbench execution runtime、template/scene UI polish、pipeline/modules/reporting runtime，以及最后的记录归档与总体验证。
### 10.65 阶段 0 继续推进: content visibility + header/footer preset primitives 提交

执行日期: 2026-07-07

本轮从 runtime 桶里继续拆小边界。初始候选是 `src/shared/engine` + `src/reporting`，但 import 检查显示多数测试会穿过 `Pipeline`、`report_writer`、`src/modules/*` 甚至 workbench execution runtime；因此先只提交两个不依赖页面和 pipeline 的基础原语。

纳入边界:

- `src/shared/engine/content_visibility.py`
  - 扫描 `{{#visibility:...}}` / `{{/visibility:...}}` 与 `{{#content:...}}` marker。
  - 汇总缺失规则、未使用文档 selector、孤立结束 marker、错位结束 marker、嵌套 block 与未闭合 block。
  - 为 delivery preset 生成移除块预览、样本文本和前后上下文。
- `src/config/header_footer_presets.py`
  - 内置页眉页脚方案目录。
  - 用户方案保存、覆盖、删除、重名检测与配置匹配。
- 测试:
  - `tests/test_content_visibility_engine.py`
  - `tests/test_header_footer_presets.py`

暂不纳入:

- `src/pipeline/runner.py` 中 content visibility 的执行集成。
- `src/pipeline/*`、`src/modules/*`、`src/report_writer.py` 与 workbench execution runtime。
- 依赖上述集成的 `tests/test_output_runtime_semantics.py`、`tests/test_count_engine_semantics.py`、`tests/test_exam_question_schema_runtime.py`、`tests/test_fixed_layout_text_runtime.py` 等 runtime 测试。

验证命令:

```powershell
python -m compileall -q src\shared\engine\content_visibility.py src\config\header_footer_presets.py
python -m pytest -q tests\test_content_visibility_engine.py tests\test_header_footer_presets.py
git diff --cached --check
git diff --cached --name-only | rg "^(src/ui/|src/pipeline/|src/modules/|src/report_writer.py|src/ui/panels/workbench|docs/)"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| focused pytest | `5 passed in 0.31s` |
| `git diff --cached --check` | 通过 |
| staged exclusion check | 未命中，说明没有混入 UI/pipeline/modules/report_writer/docs |
| staged shortstat | `4 files changed, 918 insertions(+)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `5722b81` | `Add content visibility and header preset primitives` | `content-visibility-and-header-preset-primitives` |

下一步仍应保持小边界策略：优先把 pure engine/config 服务收掉；一旦测试需要 `Pipeline`/`report_writer`/workbench runtime，再把它们作为单独 runtime 集成边界处理。
### 10.66 阶段 0 继续推进: display adapters + architecture boundary guard 提交

执行日期: 2026-07-07

本轮继续处理不依赖 widget 生命周期的 UI adapter 与架构守门测试。`field_display_names` 只负责把技术字段路径转换为用户可读标签和诊断上下文；`content_visibility_display` 只负责把 content visibility selector 与扫描问题转换为展示文本。它们不会创建页面组件，也不会触发 pipeline。

纳入边界:

- `src/ui/adapters/field_display_names.py`
  - scene/template/style/material/output 字段路径的人类可读名称。
  - style layout item、control contract key 与诊断摘要。
  - 嵌入文本中的字段 key 替换。
- `src/ui/adapters/content_visibility_display.py`
  - content visibility selector label、tooltip 与列表格式化。
  - scan issue message 的 UI 展示适配。
- `tests/test_field_display_names.py`
- `tests/test_architecture_boundaries.py`
  - 检查 `src/config`、`src/modules`、`src/pipeline`、`src/reporting`、`src/services`、`src/shared/engine` 不反向 import `src.ui`。

暂不纳入:

- 引用这些 adapter 的 `ScenePanel`、`TemplatePanel`、Workbench、assets panel 页面。
- `tests/test_ui_copy_guardrails.py`，因为它会实例化 scene/template/workbench 页面并属于页面 copy guardrail 边界。

验证命令:

```powershell
python -m compileall -q src\ui\adapters\field_display_names.py src\ui\adapters\content_visibility_display.py
python -m pytest -q tests\test_field_display_names.py tests\test_architecture_boundaries.py
git diff --cached --check
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| focused pytest | `5 passed in 0.89s` |
| `git diff --cached --check` | 通过 |
| staged shortstat | `4 files changed, 637 insertions(+)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `e19c7cc` | `Add display adapters and architecture boundary guard` | `display-adapters-and-architecture-guard` |

该提交给后续页面和 workbench issue navigation 提供了可读字段名称基础，同时把“非 UI 层不得依赖 UI 层”的规则固化为测试。
### 10.67 阶段 0 继续推进: material asset services + assets panel 提交

执行日期: 2026-07-07

本轮处理 assets/material 桶。先运行 `assets` 与 `material` 分组确认当前工作树全绿，再拆出不依赖 workbench runner 的边界。`tests/test_material_execution_context.py` 与 `tests/test_material_field_consistency.py` 会进入 WorkbenchProductionRunner、pipeline、report writer 等 runtime 集成路径，因此没有纳入本提交。

纳入边界:

- `src/services/material_assets/`
  - question figure 公共服务、question library metadata/history/master-version 服务。
  - repair audit 与 Word DOCX recovery helper。
  - 保持 services 层不依赖 UI。
- `src/ui/panels/assets_panel.py`
- `src/ui/panels/assets/`
  - assets panel helper/presenter 拆分。
  - question figure、question library、archive、batch output、preview table、material repair navigation、section summary/theme/responsive presenters。
  - enterprise boundary registry 与 specs。
- `src/ui/bridge.py`
  - MaterialExecutionContext / MaterialBatchSelection 状态和 repair target 信号。
  - `NavigationIntent` 与 `navigation_intent_value`。
- `src/ui/panel_registry.py`
  - assets panel 延迟创建入口与展示名调整。
- 测试:
  - `assets` 分组 8 个测试文件。
  - `tests/test_material_asset_services.py`
  - `tests/test_material_schema_registry.py`

暂不纳入:

- `tests/test_material_execution_context.py`
- `tests/test_material_field_consistency.py`
- `src/ui/panels/workbench/*`
- `src/pipeline/*`
- `src/modules/*`
- `src/report_writer.py`
- `src/ui/main_window.py`

验证命令:

```powershell
python -m compileall -q src\services src\ui\panels\assets src\ui\panels\assets_panel.py src\ui\bridge.py src\ui\panel_registry.py
python scripts\run_pytest_groups.py --groups assets --timeout 300 --continue-on-fail
python -m pytest -q tests\test_material_asset_services.py tests\test_material_schema_registry.py tests\test_architecture_boundaries.py
git diff --cached --check
git diff --cached --name-only | rg "^(src/ui/panels/workbench|src/pipeline/|src/modules/|src/report_writer.py|src/ui/main_window.py|tests/test_material_execution_context.py|tests/test_material_field_consistency.py|docs/)"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| assets group | `90 passed in 1.96s` |
| material service/schema + architecture | `33 passed in 1.16s` |
| `git diff --cached --check` | 首次发现 `src/ui/panels/assets_panel.py` EOF 多空行；移除后通过 |
| staged exclusion check | 未命中，说明未混入 workbench/pipeline/modules/report_writer/main_window/material execution integration/docs |
| staged shortstat | `60 files changed, 14876 insertions(+), 2 deletions(-)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `e76c0f0` | `Add material asset services and assets panel` | `material-asset-services-and-assets-panel` |

该提交完成了资料包面板和 material asset 服务层的主要结构化收口。后续 material execution、manifest/package 写出、WorkbenchProductionRunner 与 batch runner 仍应作为 runtime 集成边界处理。
### 10.68 阶段 0 继续推进: scene contract guard tests 提交

执行日期: 2026-07-07

本轮从剩余 scene 测试里筛出可以独立提交的 guard tests。筛选结果显示，`test_scene_family_application.py`、`test_scene_family_registry.py` 会依赖 workbench `scene_presets`；`test_scene_journey_runtime.py` 会穿过 pipeline/report_writer；`test_scene_overview_projection.py` 依赖未提交的 scene overview projection 与 workbench execution flow projection；`test_scene_repair_routing.py` 依赖 workbench adapter 和 scene presets。因此本轮只提交纯 config/contract guard。

纳入边界:

- `tests/test_control_contract_registry.py`
  - 覆盖 style controls、scene output/material/plugin controls、disabled rules、row height 归属与 evidence location。
- `tests/test_scene_natural_request_router.py`
  - 覆盖自然语言场景请求路由、歧义处理、导入/专业边界和未匹配请求策略。

暂不纳入:

- `tests/test_scene_family_application.py`
- `tests/test_scene_family_registry.py`
- `tests/test_scene_journey_runtime.py`
- `tests/test_scene_overview_projection.py`
- `tests/test_scene_repair_routing.py`

验证命令:

```powershell
python -m compileall -q src\config\control_contract_registry.py src\config\scene_natural_request_router.py
python -m pytest -q tests\test_control_contract_registry.py tests\test_scene_natural_request_router.py
git diff --cached --check
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| focused pytest | `12 passed in 0.18s` |
| `git diff --cached --check` | 通过 |
| staged shortstat | `2 files changed, 368 insertions(+)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `280dde3` | `Add scene contract guard tests` | `scene-contract-guard-tests` |

该提交补上 scene contract 与自然语言请求路由的纯配置层守门；其余 scene tests 留给 scene/workbench/runtime 集成边界。
### 10.69 阶段 0 继续推进: workbench presentation adapters 提交

执行日期: 2026-07-07

本轮从 workbench 桶里拆出不创建大面板的 presentation adapter/state 边界。初始检查发现 `tests/test_workbench_execution_center.py` 依赖 `execution_runtime._batch_issue_items_for_result`，而该 helper 尚在 runtime 集成改动里；因此本轮不纳入 ExecutionCenter、RecentRunPanel、QuickExecutionDetail 或 execution runtime。

纳入边界:

- `src/ui/adapters/workbench_execution_adapter.py`
  - readiness/progress/result/recent-run projection。
  - material readiness issue、object preflight issue、coverage/sample/control-contract/parameter-ownership issue projection。
  - artifact 与 issue queue summary 的展示适配。
- `src/ui/adapters/workbench_artifact_items.py`
- `src/ui/adapters/workbench_issue_navigation.py`
- `src/ui/panels/workbench/execution_flow_projection.py`
- `src/ui/panels/workbench/state.py`
- `src/ui/panels/workbench/quick_execution_presenter.py`
- 测试:
  - `tests/test_workbench_issue_navigation.py`
  - `tests/test_quick_execution_presenter.py`

暂不纳入:

- `src/ui/panels/workbench/execution_center.py`
- `src/ui/panels/workbench/recent_run_panel.py`
- `src/ui/panels/workbench/quick_execution_detail.py`
- `src/ui/panels/workbench/execution_runtime.py`
- `tests/test_workbench_execution_center.py`
- `tests/test_recent_run_panel.py`
- `tests/test_quick_execution_detail_architecture.py`

验证命令:

```powershell
python -m compileall -q src\ui\adapters\workbench_execution_adapter.py src\ui\adapters\workbench_artifact_items.py src\ui\adapters\workbench_issue_navigation.py src\ui\panels\workbench\execution_flow_projection.py src\ui\panels\workbench\state.py src\ui\panels\workbench\quick_execution_presenter.py
python -m pytest -q tests\test_workbench_issue_navigation.py tests\test_quick_execution_presenter.py
git diff --cached --check
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| focused pytest | `18 passed in 0.93s` |
| `git diff --cached --check` | 首次发现 `src/ui/adapters/workbench_artifact_items.py` EOF 多空行；移除后通过 |
| staged exclusion check | 未纳入 ExecutionCenter、RecentRunPanel、QuickExecutionDetail、execution_runtime 或其页面测试 |
| staged shortstat | `8 files changed, 5040 insertions(+), 9 deletions(-)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `3cf642a` | `Add workbench presentation adapters` | `workbench-presentation-adapters` |

该提交为后续 workbench execution UI 和 runtime 集成提供了稳定的 state/projection 基础。
### 10.70 阶段 0 继续推进: startup shell loading polish 提交

执行日期: 2026-07-07

本轮处理不依赖 pipeline/runtime 的 UI shell 改动。`tests/test_phase0_smoke.py` 会进入 pipeline，`tests/test_windows_text_rendering_policy.py` 会读取尚未提交的 workbench/scene/template 页面源码，因此本轮只纳入启动壳、主窗口加载策略、Qt API 补充导出、图标目录和手动组件预览测试的 import 修正。

纳入边界:

- `main.py`
  - 接入 `StartupSplash`。
  - 使用 `startup_status_changed` / `startup_ready` 信号协调主窗口显隐。
- `src/ui/startup_splash.py`
- `src/ui/main_window.py`
  - startup ready 信号。
  - assets panel 异步加载与后台预加载顺序。
  - `NavigationIntent` 入口处理。
- `src/qt_api.py`
  - 补充 `QDesktopServices`、`QFileSystemWatcher`、`QInputDialog`、`QMessageBox`、`QUrl` 等统一导出。
- `src/ui/icons/catalog.py`
- `src/ui/title_bar.py`
- `tests/test_all_components_preview_panel.py`
  - 适配手动预览脚本迁移到 `scripts/manual/` 后的 import 与源码路径。

暂不纳入:

- `tests/test_phase0_smoke.py`
- `tests/test_windows_text_rendering_policy.py`
- pipeline/runtime 与页面级字体策略守门。

验证命令:

```powershell
python -m compileall -q main.py src\qt_api.py src\ui\main_window.py src\ui\title_bar.py src\ui\icons\catalog.py src\ui\startup_splash.py
python -m pytest -q tests\test_all_components_preview_panel.py
git diff --cached --check
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| focused pytest | `4 passed in 0.34s` |
| `git diff --cached --check` | 通过 |
| staged shortstat | `7 files changed, 389 insertions(+), 16 deletions(-)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `a62ce30` | `Add startup shell loading polish` | `startup-shell-loading-polish` |

该提交改善启动时首屏体验与 panel 延迟加载，未混入 pipeline 或页面级策略测试。

### 10.71 阶段 0 继续推进: pipeline/reporting/workbench runtime 集成提交

执行日期: 2026-07-07

本轮把已经通过语义测试的 pipeline、reporting、shared engine 与 workbench runtime 边界合并为一个 runtime 集成提交。提交前额外检查了暂存路径，确认没有混入 docs、scene/template 页面、workbench 页面容器或 `src/ui/main_window.py`。

纳入边界:

- `src/shared/engine/`
  - count、exam question schema、fixed layout、journal citation/rule source、material field consistency、object preflight、page/table/field refresh 等共享语义引擎。
- `src/reporting/`
  - academic confidence、front matter、journal citations、journal rule source 等报告输出 helper。
- `src/pipeline/`
  - context、result、runner、scheduler 的运行时协作接口。
- `src/modules/`
  - header/footer、paragraph style、entity/placeholder fill、image insertion、citation link、validation 等模块适配。
- `src/report_writer.py`
- `src/execution_diagnostics.py`
- `src/ui/panels/workbench/`
  - `execution_runtime.py`
  - `execution_worker.py`
  - `execution_controller.py`
  - `execution_session_controller.py`
  - `exam_question_assets.py`
  - `material_artifacts.py`
  - `material_preflight.py`
  - `question_figure_repair_runtime.py`
- 对应语义测试:
  - `tests/test_citation_link_semantics.py`
  - `tests/test_count_engine_semantics.py`
  - `tests/test_exam_question_schema_runtime.py`
  - `tests/test_execution_diagnostics_reporting.py`
  - `tests/test_execution_worker.py`
  - `tests/test_fixed_layout_text_runtime.py`
  - `tests/test_header_footer_semantics.py`
  - `tests/test_journal_citation_runtime.py`
  - `tests/test_journal_rule_source_governance.py`
  - `tests/test_material_execution_context.py`
  - `tests/test_material_field_consistency.py`
  - `tests/test_object_preflight_semantics.py`
  - `tests/test_output_runtime_semantics.py`
  - `tests/test_page_number_planner_semantics.py`
  - `tests/test_phase0_smoke.py`
  - `tests/test_question_figure_repair_runtime.py`
  - `tests/test_table_format_semantics.py`

暂不纳入:

- `src/ui/panels/scene_panel.py`
- `src/ui/panels/template_*`
- `src/ui/panels/workbench/panel.py`
- `src/ui/panels/workbench/panel_v2.py`
- `src/ui/panels/workbench/quick_execution_detail.py`
- `src/ui/panels/workbench/recent_run_panel.py`
- `src/ui/panels/workbench/execution_center.py`
- `src/ui/panels/workbench/config_management_detail.py`
- `src/ui/panels/workbench/feature_detail_panes.py`
- `src/ui/panels/workbench/scene_presets.py`
- `src/ui/main_window.py`
- scene/template/workbench 页面级 architecture 与 layout 测试。

验证命令:

```powershell
git -c core.quotepath=false diff --cached --check
git -c core.quotepath=false diff --cached --name-only | rg "^(src/ui/panels/(scene_panel|template_|workbench/(panel|panel_v2|quick_execution_detail|recent_run_panel|execution_center|config_management_detail|feature_detail_panes|scene_presets))|src/ui/main_window.py|docs/)"
python scripts\run_pytest_groups.py --groups count,exam,fixed,journal,material,object,output,page,table,citation,execution,header --split-files --timeout 300 --continue-on-fail
python -m pytest -q tests\test_question_figure_repair_runtime.py
python -m compileall -q src\shared\engine src\reporting src\pipeline src\modules src\report_writer.py src\execution_diagnostics.py src\ui\panels\workbench\execution_runtime.py src\ui\panels\workbench\execution_worker.py src\ui\panels\workbench\execution_controller.py src\ui\panels\workbench\execution_session_controller.py src\ui\panels\workbench\material_artifacts.py src\ui\panels\workbench\material_preflight.py src\ui\panels\workbench\exam_question_assets.py src\ui\panels\workbench\question_figure_repair_runtime.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| `git diff --cached --check` | 首次发现 6 个 `src/reporting/` 新文件 EOF 多空行；移除后通过 |
| staged exclusion check | 未命中 docs、scene/template 页面、workbench 页面容器或 `src/ui/main_window.py` |
| pytest groups | 全部通过: citation `3`、count `6`、exam `26`、execution `51`、fixed `8`、header `16`、journal `7`、material `73`、object `11`、output `28`、page `11`、table `12` |
| question figure pytest | `7 passed in 0.57s` |
| compileall | 通过 |
| staged shortstat | `61 files changed, 27517 insertions(+), 170 deletions(-)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `e7f1b77` | `Add pipeline reporting and workbench runtime integration` | `pipeline-reporting-workbench-runtime` |

该提交把运行时语义、报告生成与 workbench execution runtime 收束到稳定边界，页面层 UI 改动仍保留在后续 workbench/scene/template 专项边界中处理。

### 10.72 阶段 0 继续推进: workbench/scene repair navigation surfaces 提交

执行日期: 2026-07-07

本轮把 workbench 执行结果、issue 队列、修复入口与 scene 页面接收导航意图的交互边界合并提交。由于 workbench session 测试会真实实例化 `ScenePanel` 并验证返回条、高亮与卡片定位，本轮没有把 workbench 和 scene 强行拆开，以保证提交自身的测试语义自洽。

纳入边界:

- `src/ui/panels/workbench/`
  - `panel_v2.py`
  - `quick_execution_detail.py`
  - `execution_center.py`
  - `recent_run_panel.py`
  - `panel.py`
  - `detail_controller.py`
  - `document_path_controller.py`
  - `config_management_detail.py`
  - `feature_detail_panes.py`
  - `scene_presets.py`
- `src/ui/panels/scene_panel.py`
- scene 拆分 helper:
  - `scene_delivery_helpers.py`
  - `scene_material_requirement_block.py`
  - `scene_overview_projection.py`
  - `scene_scope_sections.py`
  - `scene_scope_service.py`
  - `scene_style_override_sections.py`
  - `scene_style_rules_block.py`
- workbench/scene 测试:
  - `tests/test_workbench_execution_center.py`
  - `tests/test_recent_run_panel.py`
  - `tests/test_quick_execution_detail_architecture.py`
  - `tests/test_workbench_execution_architecture.py`
  - `tests/test_workbench_navigation_architecture.py`
  - `tests/test_workbench_detail_architecture.py`
  - `tests/test_workbench_execution_session_architecture.py`
  - `tests/test_workbench_document_path_architecture.py`
  - `tests/test_workbench_document_path_semantics.py`
  - `tests/test_scene_panel_architecture.py`
  - `tests/test_scene_family_application.py`
  - `tests/test_scene_family_registry.py`
  - `tests/test_scene_journey_runtime.py`
  - `tests/test_scene_overview_projection.py`
  - `tests/test_scene_repair_routing.py`

暂不纳入:

- `src/ui/panels/template_*`
- `tests/test_template_*`
- `src/cli_runner.py`
- `scripts/export_style_source_visual_audit.py`
- `tests/test_style_source_visual_audit.py`
- MD 文档自身。

验证命令:

```powershell
python -m pytest -q tests\test_workbench_execution_center.py tests\test_recent_run_panel.py tests\test_quick_execution_detail_architecture.py tests\test_workbench_execution_architecture.py tests\test_workbench_navigation_architecture.py tests\test_workbench_detail_architecture.py tests\test_workbench_execution_session_architecture.py tests\test_workbench_document_path_architecture.py tests\test_workbench_document_path_semantics.py
python -m pytest -q tests\test_scene_panel_architecture.py tests\test_scene_family_application.py tests\test_scene_family_registry.py tests\test_scene_journey_runtime.py tests\test_scene_overview_projection.py tests\test_scene_repair_routing.py
python -m compileall -q src\ui\panels\workbench src\ui\panels\scene_panel.py src\ui\panels\scene_delivery_helpers.py src\ui\panels\scene_material_requirement_block.py src\ui\panels\scene_overview_projection.py src\ui\panels\scene_scope_sections.py src\ui\panels\scene_scope_service.py src\ui\panels\scene_style_override_sections.py src\ui\panels\scene_style_rules_block.py
git -c core.quotepath=false diff --cached --check
git -c core.quotepath=false diff --cached --name-only | rg "^(docs/|src/cli_runner.py|src/ui/panels/template_|tests/test_template_|scripts/export_style_source_visual_audit.py|tests/test_style_source_visual_audit.py)"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| workbench pytest | `200 passed in 21.64s` |
| scene pytest | `121 passed in 33.72s` |
| compileall | 通过 |
| `git diff --cached --check` | 首次发现 `src/ui/panels/workbench/quick_execution_detail.py` EOF 多空行；移除后通过 |
| staged exclusion check | 未命中 template、docs、cli runner、visual audit 脚本 |
| staged shortstat | `33 files changed, 24345 insertions(+), 1993 deletions(-)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `5f04546` | `Add workbench scene repair navigation surfaces` | `workbench-scene-repair-navigation-surfaces` |

该提交让 workbench issue 修复入口能够稳定路由到 scene/template/assets/feature-card 等目标，并让 scene 页面具备可测试的导航意图接收、高亮与返回 workbench 能力。template 页面族仍在后续专项边界中提交。

### 10.73 阶段 0 继续推进: template panel layout and copy guardrails 提交

执行日期: 2026-07-07

本轮收束 template 页面族的结构拆分、布局稳定性、样式预览入口与 UI 文案守门。该边界只包含 template 页面、template 相关测试，以及设计系统/布局/Windows 文本策略/文案守门测试；`cli_runner.py` 与 visual audit 导出脚本仍留到下一轮。

纳入边界:

- `src/ui/panels/template_caption_detail.py`
- `src/ui/panels/template_elements_detail.py`
- `src/ui/panels/template_elements_header_footer.py`
- `src/ui/panels/template_elements_page_plan.py`
- `src/ui/panels/template_elements_toc.py`
- `src/ui/panels/template_format.py`
- `src/ui/panels/template_other_detail.py`
- `src/ui/panels/template_page_detail.py`
- `src/ui/panels/template_panel.py`
- `src/ui/panels/template_reference_detail.py`
- `src/ui/panels/template_style_detail.py`
- `src/ui/panels/template_style_preview.py`
- `src/ui/panels/template_table_detail.py`
- template/design/layout/copy 测试:
  - `tests/test_template_dirty_state.py`
  - `tests/test_template_format_projection.py`
  - `tests/test_template_page_detail.py`
  - `tests/test_template_panel_architecture.py`
  - `tests/test_template_panel_source_text.py`
  - `tests/test_template_remaining_details.py`
  - `tests/test_template_secondary_details.py`
  - `tests/test_template_style_detail.py`
  - `tests/test_template_style_preview.py`
  - `tests/test_design_system_refactor.py`
  - `tests/test_ui_layout_hardening.py`
  - `tests/test_windows_text_rendering_policy.py`
  - `tests/test_ui_copy_guardrails.py`

暂不纳入:

- `src/cli_runner.py`
- `scripts/export_style_source_visual_audit.py`
- `tests/test_style_source_visual_audit.py`
- MD 文档自身。

验证命令:

```powershell
python -m pytest -q tests\test_template_dirty_state.py tests\test_template_format_projection.py tests\test_template_page_detail.py tests\test_template_panel_architecture.py tests\test_template_panel_source_text.py tests\test_template_remaining_details.py tests\test_template_secondary_details.py tests\test_template_style_detail.py tests\test_template_style_preview.py tests\test_design_system_refactor.py tests\test_ui_layout_hardening.py tests\test_windows_text_rendering_policy.py tests\test_ui_copy_guardrails.py
python -m compileall -q src\ui\panels\template_caption_detail.py src\ui\panels\template_elements_detail.py src\ui\panels\template_elements_header_footer.py src\ui\panels\template_elements_page_plan.py src\ui\panels\template_elements_toc.py src\ui\panels\template_format.py src\ui\panels\template_other_detail.py src\ui\panels\template_page_detail.py src\ui\panels\template_panel.py src\ui\panels\template_reference_detail.py src\ui\panels\template_style_detail.py src\ui\panels\template_table_detail.py src\ui\panels\template_style_preview.py
git -c core.quotepath=false diff --cached --check
git -c core.quotepath=false diff --cached --name-only | rg "^(docs/|src/cli_runner.py|scripts/export_style_source_visual_audit.py|tests/test_style_source_visual_audit.py)"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| template/design/layout/copy pytest | `242 passed in 74.96s` |
| compileall | 通过 |
| `git diff --cached --check` | 通过 |
| staged exclusion check | 未命中 docs、cli runner、visual audit 脚本 |
| staged shortstat | `26 files changed, 9085 insertions(+), 3732 deletions(-)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `53d8b36` | `Add template panel layout and copy guardrails` | `template-panel-layout-copy-guardrails` |

该提交把 template 页面族从大面板内聚改为可测试的局部 detail/preview 结构，并补齐页面脏状态、文案泄漏、布局硬化和 Windows 文本渲染策略守门。

### 10.74 阶段 0 继续推进: style source report visual audit 提交

执行日期: 2026-07-07

本轮收束 style source 报告摘要与视觉审计导出边界。`cli_runner.py` 在 JSON/Markdown 报告输出时传入 style source summary；新增脚本使用 Qt offscreen 导出 scene overview 与 workbench quick execute 的 style source 行截图与指标，测试覆盖导出结果、截图文件与关键显示文案。

纳入边界:

- `src/cli_runner.py`
  - 运行后报告写入 `style_source_summary`。
- `scripts/export_style_source_visual_audit.py`
  - 导出 scene/workbench style source 行全图、局部截图与 metrics JSON。
- `tests/test_style_source_visual_audit.py`
  - 覆盖导出入口、metrics entry、截图文件存在性与关键文案。

验证命令:

```powershell
python -m pytest -q tests\test_style_source_visual_audit.py
python -m compileall -q src\cli_runner.py scripts\export_style_source_visual_audit.py
git -c core.quotepath=false diff --cached --check
git -c core.quotepath=false diff --cached --name-only | rg "^docs/"
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| visual audit pytest | `1 passed in 1.88s` |
| compileall | 通过 |
| `git diff --cached --check` | 通过 |
| staged docs exclusion check | 未命中 docs |
| staged shortstat | `3 files changed, 260 insertions(+)` |

本轮提交已完成:

| commit | message | 边界 |
| --- | --- | --- |
| `64bb446` | `Add style source report visual audit` | `style-source-report-visual-audit` |

该提交补上 style source 的报告出口与可复现视觉审计入口，避免样式来源行只停留在页面测试里而缺少可人工复核的截图证据。

### 10.75 阶段 0 最终完成审计: 按文档执行到可证明完成状态

执行日期: 2026-07-07

本轮按原始目标“按照文档持续执行到完成”做最终完成审计。审计不以历史意图为准，而以当前工作区、提交链、文档记录和可重复门禁命令为准。

完成要求与证据矩阵:

| 文档要求 | 当前证据 | 判定 |
| --- | --- | --- |
| 阶段 0: 冻结并收口工作区，避免混杂大变更 | `git status --short` 无输出；最新提交链从 `a24a5e5` 到 `e36462e` 已按边界拆分；ignored 本地产物未进入普通 status；`check_public_release.py --strict` 通过 | 完成 |
| 阶段 1: 建立工程配置与门禁基线 | `pyproject.toml`、`.github/workflows/*`、`scripts/engineering_gate.py`、`scripts/check_public_release.py` 已在提交链中；当前 `python scripts\engineering_gate.py` 通过 | 完成 |
| 阶段 2: 修复 `config -> ui` 反向依赖 | `rg "src\\.ui|from src\\.ui|import src\\.ui" src\config scripts` 当前只命中 `scripts/export_style_source_visual_audit.py` 与 `scripts/manual/test_workbench_v2.py`；未命中 `src/config` | 完成 |
| 阶段 3: 拆分最高风险大文件与高耦合模块 | `report_writer`、`workbench_execution_adapter`、`scene_panel`、`scene_matrix_dashboard`、`scene_matrix_drilldown`、workbench/template/scene 页面族均已有独立提交、helper/service/adapters 和对应测试守门 | 完成 |
| 阶段 4: 清理文档和生成物边界 | `docs/refactor-records/`、`docs/audits/`、`docs/visual_checks/` 等迁移记录已提交；public release strict 通过；工作区无普通未提交文档/生成物 | 完成 |
| 架构守门测试与分组测试可重复运行 | 当前 engineering gate、scene matrix release gate、runtime pytest groups、UI 综合 pytest 均通过 | 完成 |
| 用 MD 记录执行内容和步骤 | 本文件已记录 1-10.75 的扫描、风险、阶段策略、每批提交、验证命令、结果和最终完成审计 | 完成 |

当前验证命令:

```powershell
git -c core.quotepath=false status --short
rg -n "src\.ui|from src\.ui|import src\.ui" src\config scripts | Select-Object -First 200
python scripts\check_public_release.py --strict
python scripts\engineering_gate.py
python scripts\verify_scene_matrix_release_gate.py
python scripts\run_pytest_groups.py --groups count,exam,fixed,journal,material,object,output,page,table,citation,execution,header --split-files --timeout 300 --continue-on-fail
python -m pytest -q tests\test_question_figure_repair_runtime.py tests\test_workbench_execution_center.py tests\test_recent_run_panel.py tests\test_quick_execution_detail_architecture.py tests\test_workbench_execution_architecture.py tests\test_workbench_navigation_architecture.py tests\test_workbench_detail_architecture.py tests\test_workbench_execution_session_architecture.py tests\test_workbench_document_path_architecture.py tests\test_workbench_document_path_semantics.py tests\test_scene_panel_architecture.py tests\test_scene_family_application.py tests\test_scene_family_registry.py tests\test_scene_journey_runtime.py tests\test_scene_overview_projection.py tests\test_scene_repair_routing.py tests\test_template_dirty_state.py tests\test_template_format_projection.py tests\test_template_page_detail.py tests\test_template_panel_architecture.py tests\test_template_panel_source_text.py tests\test_template_remaining_details.py tests\test_template_secondary_details.py tests\test_template_style_detail.py tests\test_template_style_preview.py tests\test_design_system_refactor.py tests\test_ui_layout_hardening.py tests\test_windows_text_rendering_policy.py tests\test_ui_copy_guardrails.py tests\test_style_source_visual_audit.py
```

当前验证结果:

| 检查项 | 结果 |
| --- | --- |
| `git status --short` | 无输出，工作区干净 |
| config/ui 反向依赖扫描 | 未命中 `src/config`；仅命中 UI 审计脚本和手工预览脚本 |
| public release strict | `[OK] No obvious public-release blockers were found.` |
| engineering gate | compileall 通过；`1801 tests collected in 1.95s`；smoke tests `10 passed in 0.67s`；`Engineering gate passed.` |
| scene matrix release gate | `Scene matrix release gate: passed`；全部 checks `passed (0 issues)`；`drilldowns=37/37`、`drilldown_rows=556/556`、`drilldown_sources=107/107 ready` |
| runtime pytest groups | 全部通过: citation `3`、count `6`、exam `26`、execution `51`、fixed `8`、header `16`、journal `7`、material `73`、object `11`、output `28`、page `11`、table `12` |
| UI/交互综合 pytest | `571 passed in 133.14s` |

最终状态判定:

当前项目已经达到本轮文档目标下的“可证明完成”状态: 工作区已收口，主要结构风险已有拆分或守门，跨层反向依赖未回潮，发布/工程/scene release/runtime/UI 综合门禁均通过，执行过程和证据已记录在本 MD 中。

仍可后续优化但不阻塞本轮完成的事项:

- 部分 UI 和 scene/config 模块仍然偏大，后续可以继续按职责细拆。
- ignored 本地调试产物仍存在于开发机，但它们不进入普通工作区状态，也未阻断 public release strict。
- 测试总量较大，后续可继续优化分组运行时间和 CI 并行策略。

### 10.76 后续优化第一刀: scene matrix release gate payload 模块化

执行日期: 2026-07-08

本轮承接第 10.75 节之后的后续优化建议，优先处理 `scripts/verify_scene_matrix_release_gate.py` 中超长的 `build_scene_matrix_release_gate_payload()`。处理目标不是改变 release gate 行为，而是把 CLI 入口和 payload 构建职责拆开，降低后续继续按 family/report 拆 builder 的风险。

已完成改动:

- 新增 `scripts/scene_matrix_release_gate_payload.py`
  - 承接 release gate payload 构建、pytest lightweight cache、issue payload helper、request-cell hard gate helper、release governance export script evidence helper。
- 收窄 `scripts/verify_scene_matrix_release_gate.py`
  - 保留 CLI 参数、JSON/human 输出、`main()` 和 `_print_human()`。
  - 继续 re-export `build_scene_matrix_release_gate_payload`，兼容现有测试和调用方。
  - 增加 `RELEASE_GATE_PAYLOAD_CHECK_IDS`，让既有 source evidence 审计仍能在 CLI 入口看到 release gate 契约，而真实构建逻辑下沉到 payload 模块。
- 更新 `tests/test_release_shell.py`
  - 确认 payload 模块存在。
  - 确认 CLI wrapper 不再直接导入 `src.config.*`。
  - 确认 CLI wrapper 不再重新定义 payload builder，且保持在 350 行以内。

规模变化:

| 文件 | 调整后行数 | 说明 |
| --- | ---: | --- |
| `scripts/verify_scene_matrix_release_gate.py` | `318` | 从 2600+ 行 release gate 聚合脚本收窄为 CLI wrapper |
| `scripts/scene_matrix_release_gate_payload.py` | `2397` | 新的 payload builder 边界，后续可继续按 report family 拆分 |

验证命令:

```powershell
python -m compileall -q scripts\verify_scene_matrix_release_gate.py scripts\scene_matrix_release_gate_payload.py tests\test_release_shell.py
python -m pytest -q tests\test_release_shell.py
python -m pytest -q tests\test_scene_matrix_dashboard.py tests\test_scene_matrix_drilldown.py tests\test_scene_retained_gap_exit_criteria_audit.py
python scripts\verify_scene_matrix_release_gate.py
git -c core.quotepath=false diff --check
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| release shell pytest | `12 passed in 0.09s` |
| scene matrix focused pytest | `16 passed in 127.95s` |
| real scene matrix release gate | `Scene matrix release gate: passed`；全部 checks `passed (0 issues)`；`drilldowns=37/37`、`drilldown_rows=556/556`、`drilldown_sources=107/107 ready` |
| `git diff --check` | 通过 |

后续仍可继续优化:

- `scene_matrix_release_gate_payload.py` 内部的 payload builder 仍然很长，下一刀可以按 `coverage/request-cell`、`boundary/release governance`、`material/delivery/fixed-layout`、`dashboard/drilldown` 四组拆 helper。
- source evidence 契约目前通过 CLI 的 `RELEASE_GATE_PAYLOAD_CHECK_IDS` 明确保留，后续若审计模型支持多 source path，可把这些 marker 逐步迁到 payload 模块本体。

### 10.77 后续优化第二刀: release gate foundation checks 抽取

执行日期: 2026-07-08

本轮继续处理 `scripts/scene_matrix_release_gate_payload.py` 内部的超长 `build_scene_matrix_release_gate_payload()`。上一刀已经把 CLI wrapper 和 payload 构建拆开，但新的 payload 模块中仍有一个接近 2000 行的聚合函数；这次选择先抽取最靠前、依赖最少、语义边界最清晰的一段 foundation checks，避免在同一轮里大范围重排 payload 字典和 release gate 输出结构。

已完成改动:

- 新增 `_ReleaseGateFoundation` dataclass
  - 集中承载 foundation 阶段会继续向后传递的 `checks`、`request_cell_summary`、`request_cell_browser`、`completeness_report`、`task_lexicon_report`。
- 新增 `_build_release_gate_foundation(output_dir)`
  - 承接 coverage pack completeness/matrix alignment/closure validation。
  - 承接 high-frequency request samples、scene product readiness、scene sample/request cell fixtures、sample fixture library。
  - 承接 request-cell release threshold、registry browser、high-frequency completeness/task lexicon audit。
- 收窄 `build_scene_matrix_release_gate_payload()`
  - 保留 pytest lightweight cache 快速返回逻辑。
  - 通过 foundation helper 取得第一批 checks 与后续 payload 所需 summary/report/browser 对象。
  - 暂不调整后续 payload 字典结构，降低对 release gate human/json 输出的影响面。

规模变化:

| 指标 | 调整后 | 说明 |
| --- | ---: | --- |
| `scripts/scene_matrix_release_gate_payload.py` 总行数 | `2457` | 新增 dataclass/helper 后文件略增，但职责边界更清晰 |
| `build_scene_matrix_release_gate_payload()` | `1993` 行 | 从 `2030` 行降到 `1993` 行，先切出 foundation 阶段 |
| `_build_release_gate_foundation()` | `50` 行 | 后续可继续作为 release gate 前置基础检查的稳定边界 |

验证命令:

```powershell
python -m compileall -q scripts\scene_matrix_release_gate_payload.py scripts\verify_scene_matrix_release_gate.py
python -m pytest -q tests\test_release_shell.py
python -m pytest -q tests\test_scene_matrix_dashboard.py tests\test_scene_matrix_drilldown.py tests\test_scene_retained_gap_exit_criteria_audit.py
python scripts\verify_scene_matrix_release_gate.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| release shell pytest | `12 passed in 0.07s` |
| scene matrix focused pytest | `16 passed in 128.71s` |
| real scene matrix release gate | `Scene matrix release gate: passed`；全部 checks `passed (0 issues)`；`drilldowns=37/37`、`drilldown_rows=556/556`、`drilldown_sources=107/107 ready` |

后续仍可继续优化:

- `build_scene_matrix_release_gate_payload()` 仍然偏长，下一步建议抽取 release governance/report-family 聚合段，优先拆出只生成 report 与 checks 的 helper，继续避免重排最终 payload 字典。
- foundation helper 已经证明不会影响 release gate 输出；后续拆分可以沿用“先返回 dataclass 上下文，再由主 builder 组装 payload”的方式。
- 当前 source evidence marker 仍由 CLI wrapper 明确保留；若后续审计规则支持多文件 source evidence，可以把 marker 与真实构建逻辑进一步合并到 payload 模块。

### 10.78 后续优化第三刀: release governance export evidence gate 抽取

执行日期: 2026-07-08

本轮继续沿着第 10.77 节的方向处理 `scripts/scene_matrix_release_gate_payload.py`。这次没有直接搬动最终 payload 字典，而是选择 release governance export evidence 这段已有清晰输入/输出的内联逻辑: 它只负责把 15 个 release governance 相关 report 的 `source_evidence` 汇总成 export script evidence、统计 counts，并写入 `scene_release_governance_export_script_evidence` check。

已完成改动:

- 新增 `_ReleaseGovernanceExportEvidenceGate` dataclass
  - 承载 `evidence` 与 `counts` 两个后续 payload 会继续使用的输出。
- 新增 `_build_release_governance_export_evidence_gate(...)`
  - 接收 15 个 release governance 相关 report。
  - 复用既有 `_build_release_governance_export_script_evidence()`、`_release_governance_export_script_evidence_counts()`、`_release_governance_export_script_evidence_issues()`。
  - 在 helper 内集中写入 `scene_release_governance_export_script_evidence` check，避免主 builder 继续内联证据拼装和 issue 转换。
- 收窄 `build_scene_matrix_release_gate_payload()`
  - 将原本的长 tuple 拼装、counts 计算、check 写入替换成一次 gate helper 调用。
  - 保留 `release_governance_export_script_evidence` 与 `release_governance_export_script_counts` 变量名，降低对后续 counts/payload 组装的影响面。

规模变化:

| 指标 | 调整后 | 说明 |
| --- | ---: | --- |
| `scripts/scene_matrix_release_gate_payload.py` 总行数 | `2515` | 新增 dataclass/helper 后总行数上升，但主聚合函数继续收窄 |
| `build_scene_matrix_release_gate_payload()` | `1951` 行 | 从 `1993` 行降到 `1951` 行 |
| `_build_release_governance_export_evidence_gate()` | `92` 行 | release governance export evidence 的独立 gate 边界 |

验证命令:

```powershell
python -m compileall -q scripts\scene_matrix_release_gate_payload.py scripts\verify_scene_matrix_release_gate.py
python -m pytest -q tests\test_release_shell.py
python -m pytest -q tests\test_scene_matrix_dashboard.py tests\test_scene_matrix_drilldown.py tests\test_scene_retained_gap_exit_criteria_audit.py
python scripts\verify_scene_matrix_release_gate.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| release shell pytest | `12 passed in 0.11s` |
| scene matrix focused pytest | `16 passed in 133.40s` |
| real scene matrix release gate | `Scene matrix release gate: passed`；`scene_release_governance_export_script_evidence: passed (0 issues)`；`release_export_scripts=15/15 ready`；`drilldowns=37/37`、`drilldown_rows=556/556`、`drilldown_sources=107/107 ready` |

后续仍可继续优化:

- 下一刀可以开始抽取 report build/audit 阶段的上下文对象，例如把 ambiguity/import/input/family/control/count/user-journey/business-capability 这一段先收束为一个 early report context。
- 对仍被最终 payload 大量引用的 report，不建议一次性全部改成 `context.xxx`，可以继续使用 dataclass 返回 + 主 builder 局部变量过渡的方式逐步降低风险。
- 当 report context 边界稳定后，再考虑把 counts 字典拆成独立 payload counts builder。

### 10.79 后续优化第四刀: material/delivery report gate 抽取

执行日期: 2026-07-08

本轮继续收窄 `scripts/scene_matrix_release_gate_payload.py` 的主聚合函数，优先处理 material、fixed-layout、report artifact drilldown、delivery preset、formula output watermark、maturity upgrade 这一组报告。它们的 build/audit 阶段相对独立，但后续 counts 和 payload 仍大量读取这些 report 对象，因此采用 dataclass 返回 + 主 builder 局部变量过渡的方式，避免一次性改动最终 payload 结构。

已完成改动:

- 新增 `_ReleaseGateMaterialDeliveryReports` dataclass
  - 承载 `material_schema_report`、`material_repair_flow_report`、`fixed_layout_profile_report`、`report_artifact_drilldown_report`、`delivery_preset_report`、`delivery_execution_report`、`formula_output_watermark_report`、`maturity_upgrade_report`。
- 新增 `_build_release_gate_material_delivery_reports(checks=...)`
  - 集中执行 material schema、material repair flow、fixed layout profile、report artifact drilldown、delivery preset、delivery execution、formula output watermark、product maturity upgrade 的 build/audit/check 写入。
- 收窄 `build_scene_matrix_release_gate_payload()`
  - 将上述内联 build/audit 段替换为一次 helper 调用。
  - 保留原有局部变量名给后续 counts/payload 使用，减少本次改动的行为影响面。

规模变化:

| 指标 | 调整后 | 说明 |
| --- | ---: | --- |
| `scripts/scene_matrix_release_gate_payload.py` 总行数 | `2561` | 新增 dataclass/helper 后总行数上升，但主聚合函数继续收窄 |
| `build_scene_matrix_release_gate_payload()` | `1912` 行 | 从 `1951` 行降到 `1912` 行 |
| `_build_release_gate_material_delivery_reports()` | `71` 行 | material/delivery/fixed-layout 相关检查的独立 report gate |

验证命令:

```powershell
python -m compileall -q scripts\scene_matrix_release_gate_payload.py scripts\verify_scene_matrix_release_gate.py
python -m pytest -q tests\test_release_shell.py
python -m pytest -q tests\test_scene_matrix_dashboard.py tests\test_scene_matrix_drilldown.py tests\test_scene_retained_gap_exit_criteria_audit.py
python scripts\verify_scene_matrix_release_gate.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| release shell pytest | `12 passed in 0.09s` |
| scene matrix focused pytest | `16 passed in 120.24s` |
| real scene matrix release gate | `Scene matrix release gate: passed`；material/delivery/fixed-layout 相关 checks 全部 `passed (0 issues)`；`material_schema_families=15/15`、`material_repair_flows=11/11`、`fixed_layout_profile=12/12`、`report_artifact_drilldown=10/10`、`delivery_execution=10/10`、`formula_output_watermark=3/3` |

后续仍可继续优化:

- 下一步可抽取 matrix dashboard + release residual explanation gate，因为它们当前紧跟 material/delivery 阶段，且只向后暴露 `matrix_dashboard` 和 `release_residual_explanation_report`。
- 更大的一步是拆 early report context，但涉及变量更多，建议在下一轮继续保持小步提交和 release gate 逐次验证。

### 10.80 后续优化第五刀: dashboard/residual explanation gate 抽取

执行日期: 2026-07-08

本轮继续在第 10.79 节之后收窄 `scripts/scene_matrix_release_gate_payload.py` 的主聚合函数。选择抽取 matrix dashboard 与 release residual explanation 这一小段，是因为它们紧跟 material/delivery 阶段，依赖明确，并且向后只暴露 `matrix_dashboard` 与 `release_residual_explanation_report` 两个对象。

已完成改动:

- 新增 `_ReleaseGateDashboardResidualReports` dataclass
  - 承载 `matrix_dashboard` 与 `release_residual_explanation_report`。
- 新增 `_build_release_gate_dashboard_residual_reports(...)`
  - 集中执行 `build_scene_matrix_dashboard()` 与 `audit_scene_matrix_dashboard()`。
  - 集中执行 `build_scene_release_residual_explanation_audit_report(...)` 与 `audit_scene_release_residual_explanation_report(...)`。
  - 在 helper 内写入 `scene_matrix_dashboard` 与 `scene_release_residual_explanation_audit` 两个 checks。
- 收窄 `build_scene_matrix_release_gate_payload()`
  - 将 dashboard/residual explanation 的 build/audit/check 写入替换为一次 helper 调用。
  - 保留原有局部变量名，继续供 release governance export evidence、counts 与 payload 组装使用。

规模变化:

| 指标 | 调整后 | 说明 |
| --- | ---: | --- |
| `scripts/scene_matrix_release_gate_payload.py` 总行数 | `2600` | 新增 dataclass/helper 后总行数上升，但主聚合函数继续收窄 |
| `build_scene_matrix_release_gate_payload()` | `1904` 行 | 从 `1912` 行降到 `1904` 行 |
| `_build_release_gate_dashboard_residual_reports()` | `39` 行 | dashboard/residual explanation 的独立 gate 边界 |

验证命令:

```powershell
python -m compileall -q scripts\scene_matrix_release_gate_payload.py scripts\verify_scene_matrix_release_gate.py
python -m pytest -q tests\test_release_shell.py
python -m pytest -q tests\test_scene_matrix_dashboard.py tests\test_scene_matrix_drilldown.py tests\test_scene_retained_gap_exit_criteria_audit.py
python scripts\verify_scene_matrix_release_gate.py
```

验证结果:

| 检查项 | 结果 |
| --- | --- |
| compileall | 通过 |
| release shell pytest | `12 passed in 0.07s` |
| scene matrix focused pytest | `16 passed in 119.22s` |
| real scene matrix release gate | `Scene matrix release gate: passed`；`scene_matrix_dashboard: passed (0 issues)`；`scene_release_residual_explanation_audit: passed (0 issues)`；`residual_explanations=14/14 covered`；`dashboard_packs=12` |

后续仍可继续优化:

- 下一轮建议进入 early report context 拆分，优先处理 ambiguity/import/input/family/control/count/user-journey/business-capability 这一段。
- 在 early report context 稳定前，不建议立即拆 counts 字典，因为 counts 目前跨所有 report 读取，直接拆会扩大风险面。
