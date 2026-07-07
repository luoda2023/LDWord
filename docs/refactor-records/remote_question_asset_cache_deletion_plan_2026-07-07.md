# 远程题图缓存最终删除规划（2026-07-07）

## 结论

远程题图缓存应从当前产品的活跃路径中最终删除。它现在已经不是一个简单的“缓存小功能”，而是一整套企业远程素材能力：远程 URL 解析、鉴权头、HTTP 下载、共享缓存目录、索引、命中率指标、清理确认、失效治理、manifest 打包和报告输出。对当前项目目标而言，这条链路扩大了维护面，也让题图链路承载了过多非核心产品逻辑。

最终目标不是把功能隐藏起来，而是删除运行时行为和 UI/报告投影：

- 不再从远程 URL 下载题图。
- 不再创建 `_remote_asset_cache` 目录、`index.json`、metrics/history/cleanup 记录。
- 不再解析远程题图下载鉴权字段。
- 不再在 manifest、归档报告、批量诊断中输出 `remote_asset_cache` / `remote_asset_items`。
- 不再在资产面板展示“共享缓存目录/缓存条目”这类远程缓存台账。

保留本地题图能力：

- 保留本地 `AssetItem`、题图清单、题图修复、题图审计、Word 图片插入等本地链路。
- 可以保留 `asset_id`、`asset_version`、`asset_etag` 等素材身份字段，前提是它们只作为本地匹配/追踪元数据，不触发远程行为。
- 本地图片路径仍然有效；远程 URL 或 `asset://` / `lark://` 类路径不再被自动下载，应被视为不支持的远程素材引用或缺失本地图片。

## 当前触点盘点

### Workbench 执行运行时

核心文件：`src/ui/panels/workbench/execution_runtime.py`

当前远程缓存链路的主入口和主体都集中在这里：

- `WorkbenchProductionRunner.run` 中先调用 `_material_context_with_remote_question_asset_cache`，再进入正式渲染。
- `_material_context_with_remote_question_asset_cache` 会创建 `_remote_asset_cache` 并改写素材上下文。
- `_download_remote_question_asset` / `_download_remote_question_asset_once` 使用 `urllib.request.Request` 和 `urlopen` 发起网络请求。
- `_asset_download_auth_headers` 及相关 `_asset_auth_*` 函数解析远程鉴权。
- `_remote_asset_cache_index_summary` 汇总缓存索引、命中率、重试、失效、清理等状态。
- `_copy_remote_asset_cache_package_references` 会把缓存索引和历史记录写入交付包。
- `_append_remote_asset_cache_archive_report` 会把缓存状态写入归档报告。
- `_runtime_payload` 会把 `remote_asset_cache` 写进运行产物。

这个文件里远程缓存相关代码量很大，删除时要按调用链而不是按关键词粗暴删除。

### Workbench 适配器与诊断

核心文件：`src/ui/adapters/workbench_execution_adapter.py`

需要删除或改写的职责：

- 从 payload 中读取并展示 `remote_asset_items`。
- `_asset_render_path` 当前会在远程路径存在时优先使用 `cache_path`，删除后不能再发生路径替换。
- `_looks_like_remote_asset_path` 可保留为“远程引用不支持”的判断，也可以下沉为本地缺失诊断。
- 批量 issue 明细里不再展示 `download_url`、远程缓存状态或远程素材项。

删除后，适配器应该只报告“本地图片缺失/远程引用未本地化”，而不是提示缓存下载或缓存刷新。

### 资产面板共享缓存 UI

核心文件：

- `src/ui/panels/assets/cache_presenter.py`
- `src/ui/panels/assets/question_cache.py`
- `src/services/material_assets/cache_projection.py`
- `src/ui/panels/assets/image_inventory_presenter.py`
- `src/ui/panels/assets/section_summary_presenter.py`
- `src/ui/panels/assets/enterprise_boundary.py`

当前资产面板仍有“共享缓存目录/缓存条目”的表格和投影：

- `QuestionFigureSharedCachePresenterMixin`
- `_setup_question_figure_shared_cache_tables`
- `_refresh_question_figure_shared_cache_dirs_table`
- `_refresh_question_figure_shared_cache_entries_table`
- `question_figure_shared_cache_dir_rows`
- `question_figure_shared_cache_entry_rows`
- `asset_item_shared_cache_dir`

这些功能本质上是远程题图缓存台账，不是本地题图库核心能力。最终删除时应去掉相关 UI 表格、服务导出、兼容 re-export 和测试。

### 素材服务字段

核心文件：

- `src/services/material_assets/question_library.py`
- `src/ui/panels/assets/field_editor_state_presenter.py`

需要谨慎处理：

- `download_url` 字段现在仍在题图库字段别名中出现。若删除远程能力，应从可编辑/可解析的活跃字段中移除，或降级为历史兼容只读字段。
- `remote_question_asset_download_auth`、`remote_asset_download_auth`、`asset_auth` 等字段应从活跃编辑、运行时解析、导出报告中删除。

建议保留历史数据读取的容错，但不要再让这些字段驱动任何下载、认证或缓存行为。

### 测试

核心文件：

- `tests/test_material_execution_context.py`
- `tests/test_assets_cache_presenter.py`
- `tests/test_assets_panel_question_cache.py`
- `tests/test_assets_panel_architecture.py`
- `tests/test_assets_panel_helper_modules.py`
- `tests/test_output_runtime_semantics.py`
- `tests/test_workbench_execution_center.py`

现有测试中有大量正向远程缓存用例，覆盖下载、重试、共享缓存、失效、清理、鉴权、打包和报告。这些测试在删除后应整体改为两类：

- 删除：验证远程缓存可工作的正向用例。
- 新增或改写：验证远程缓存不会被触发、不会创建目录、不会联网、不会出现在 manifest/report/UI 中。

## 执行规划

### 阶段 0：变更保护与基线

目标：避免在当前脏工作区里误伤已有改动。

操作：

- 记录 `git status --short` 当前状态。
- 在执行删除前，只处理与远程题图缓存相关的文件。
- 先不做场景面板、控件统一、视觉层重构。
- 先跑一组轻量扫描，确认删除前触点：
  - `rg -n "remote_question_asset|remote_asset_cache|remote_asset_download_auth|asset_auth|download_url|urlopen|Request\\(" src tests -g "*.py"`
  - `rg -n "QuestionFigureSharedCache|shared_cache|question_cache|cache_projection" src tests -g "*.py"`

交付物：

- 明确删除文件/函数列表。
- 明确保留本地题图能力的边界。

### 阶段 1：切断运行时入口

目标：先让执行链路不再触发远程缓存。

操作：

- 在 `src/ui/panels/workbench/execution_runtime.py` 中移除 `WorkbenchProductionRunner.run` 对 `_material_context_with_remote_question_asset_cache` 的调用。
- 删除 `urllib.request.Request` / `urlopen` import。
- 对远程 URL 型题图路径只产生本地缺失或不支持诊断，不尝试下载。
- 确认执行一次后不会生成 `_remote_asset_cache`。

验收：

- Workbench 执行路径不再依赖网络。
- 运行时不会创建 `_remote_asset_cache`。
- 远程路径不会被替换成 `cache_path`。

### 阶段 2：删除运行时缓存子系统

目标：移除远程缓存的主体代码。

删除范围：

- `_material_context_with_remote_question_asset_cache`
- `_download_remote_question_asset`
- `_download_remote_question_asset_once`
- `_remote_question_asset_*` 下载、后缀、缓存文件名、失败、重试函数
- `_asset_download_url`
- `_asset_library_download_url`
- `_asset_download_auth_headers`
- `_asset_auth_*`
- `_remote_asset_cache_*` 索引、指标、历史、失效、清理、确认函数
- `_remote_asset_cache_index_summary`
- `_copy_remote_asset_cache_package_references`
- `_append_remote_asset_cache_archive_report`
- `_remote_asset_cache_package_*`

同步改写：

- manifest payload 不再写入 `remote_asset_cache`。
- 交付包 manifest 不再保留 `remote_asset_cache` 分区。
- 归档报告不再输出缓存索引、命中率、清理历史、共享缓存历史。

验收：

- `src/ui/panels/workbench/execution_runtime.py` 不再出现 `urlopen`、`Request(`、`_remote_asset_cache`、`remote_asset_cache` 的活跃代码。
- 删除后文件体积应明显下降，这是本阶段最直接的结构收益。

### 阶段 3：清理适配器和诊断投影

目标：让 UI/批量诊断不再暴露已删除的远程缓存模型。

操作：

- 从 `src/ui/adapters/workbench_execution_adapter.py` 删除 `remote_asset_items` 的 payload 解析与展示。
- 改写 `_asset_render_path`，不再使用 `cache_path` 替代远程路径。
- 删除 issue 明细里的 `download_url`、缓存状态、远程缓存路径展示。
- 保留一个轻量判断：如果输入仍是远程 URL，可提示“远程题图未本地化”，但不提供缓存下载语义。

验收：

- 适配器输出中没有 `remote_asset_items`。
- 批量诊断不再显示远程缓存字段。
- 本地缺失图仍能被正常诊断。

### 阶段 4：删除资产面板共享缓存 UI 与服务投影

目标：移除用户界面和服务层里的远程缓存台账。

操作：

- 从 `AssetsPanel` 继承链中移除 `QuestionFigureSharedCachePresenterMixin`。
- 删除 `src/ui/panels/assets/cache_presenter.py`，或在确认无其他职责后整体移除。
- 删除 `src/ui/panels/assets/question_cache.py` 兼容导出。
- 删除 `src/services/material_assets/cache_projection.py`，或只保留与本地题图必要字段相关的最小函数。
- 从 `src/services/material_assets/__init__.py` 移除共享缓存相关导出。
- 从 `image_inventory_presenter.py` 和 `section_summary_presenter.py` 移除共享缓存表创建与刷新调用。
- 从 `enterprise_boundary.py` 删除 `lightweight_shared_cache` 边界记录。

验收：

- 资产面板不再创建共享缓存目录表和缓存条目表。
- `tests/test_assets_cache_presenter.py`、`tests/test_assets_panel_question_cache.py` 中正向缓存 UI 测试被删除或改为反向守门。
- `rg -n "QuestionFigureSharedCache|question_figure_shared_cache|shared_cache_dir|remote_asset_cache_dir" src/ui/panels/assets src/services/material_assets tests/test_assets*` 仅允许出现明确的删除守门测试。

### 阶段 5：字段与兼容策略收束

目标：历史字段可读，但不再塑造产品能力。

操作：

- 从题图库活跃字段别名中移除 `download_url`，或改为历史兼容字段，不进入 UI 编辑和运行时。
- 删除 `remote_question_asset_download_auth`、`remote_asset_download_auth`、`asset_auth` 的编辑排除和运行时解析。
- 对旧数据中遗留的 `download_url`、`remote_asset_cache_dir`、`shared_cache_dir` 做无害化处理：读取时忽略，不报错，不联网。

验收：

- 旧数据不会导致崩溃。
- 旧远程字段不会导致下载、缓存、鉴权、manifest 输出。

### 阶段 6：测试改写

目标：从“证明远程缓存可用”改成“证明远程缓存已不存在”。

删除或重写：

- `tests/test_material_execution_context.py` 中远程缓存正向用例：下载、重试、共享缓存复用、失效、清理、鉴权、打包、报告。
- `tests/test_assets_cache_presenter.py`
- `tests/test_assets_panel_question_cache.py`
- `tests/test_assets_panel_architecture.py` 中共享缓存 mixin 结构断言。
- `tests/test_assets_panel_helper_modules.py` 中共享缓存 presenter 断言。

新增守门测试：

- 执行远程 URL 型题图时不会调用网络。
- 执行后不会创建 `_remote_asset_cache`。
- manifest 不包含 `remote_asset_cache`。
- package manifest 不包含 `remote_asset_cache` category。
- archive report 不包含远程缓存章节。
- adapter 输出不包含 `remote_asset_items`。
- assets panel 不再拥有共享缓存表对象。

建议扫描守门：

```powershell
rg -n "urlopen|urllib.request|Request\\(|_remote_asset_cache|remote_asset_cache|remote_question_asset_download_auth|remote_asset_download_auth|asset_auth" src
rg -n "QuestionFigureSharedCache|question_figure_shared_cache|remote_asset_cache_dir|shared_cache_dir" src/ui/panels/assets src/services/material_assets
```

第一条在 `src` 中应无活跃命中；第二条在目标删除完成后也应无活跃命中。

### 阶段 7：验证与收口

建议验证命令：

```powershell
python -m compileall -q src tests
python -m pytest -q tests/test_material_execution_context.py tests/test_output_runtime_semantics.py tests/test_workbench_execution_center.py
python -m pytest -q tests/test_assets_panel_architecture.py tests/test_assets_panel_helper_modules.py tests/test_material_asset_services.py
```

如果测试总量过大，可以先跑远程删除相关的聚焦测试，再跑完整相关回归。

最终验收标准：

- `src` 中没有远程题图缓存活跃代码。
- Workbench 不联网获取题图。
- 运行产物、manifest、package、archive report 不再出现远程缓存章节。
- 资产面板不再出现共享缓存目录/条目 UI。
- 本地题图清单、题图修复、Word 输出图片插入能力仍然可用。

## 风险与处理

### 风险 1：测试文件很大，删除面广

`tests/test_material_execution_context.py` 中远程缓存正向测试跨度很大，直接整段删除容易误伤本地题图上下文测试。

处理：

- 先按关键词切分远程缓存测试块。
- 每删一组跑一次相关测试或至少 compile。
- 保留本地 material context、题图清单、图片修复相关测试。

### 风险 2：远程字段和本地字段混在 metadata 中

`cache_path`、`download_url`、`asset_id`、`shared_cache_dir` 可能同时存在。

处理：

- `asset_id` 等身份字段可保留。
- `cache_path` 只有在代表本地真实图片路径时才保留。
- `download_url`、`shared_cache_dir`、`remote_asset_cache_dir` 不再触发行为。

### 风险 3：报告和打包函数依赖 payload 结构

如果只删运行时，不删 package/report 读取逻辑，会留下死分支和误导性输出。

处理：

- 运行时、manifest、package、archive report 必须一起收束。
- 删除后增加“不包含 remote_asset_cache”的断言。

## 推荐执行顺序

建议按小批次推进：

1. 先切断 Workbench 运行时入口，让产品行为先停止远程缓存。
2. 再删除 `execution_runtime.py` 中远程缓存主体函数，减少最大维护债。
3. 清理 adapter/manifest/package/report，避免死字段继续外泄。
4. 删除资产面板共享缓存 UI 与服务投影。
5. 收束字段兼容和测试守门。

这条路线的好处是每一步都有可验证结果，并且不会把“删除远程缓存”和“重构控件/统一面板”搅在一起。

## 执行记录

执行日期：2026-07-07

已完成：

- Workbench 执行入口不再调用远程题图缓存准备函数，运行时不再导入 `urllib.request.Request` / `urlopen`。
- 删除 Workbench 远程题图缓存主体：下载、重试、鉴权、缓存索引、共享缓存、失效、清理、metrics/history、manifest 汇总、package 复制和 archive report 章节。
- Workbench adapter 不再读取 `remote_asset_items`，也不再用远程路径的 `cache_path` 替换渲染路径。
- 资产面板删除共享缓存表入口，不再继承 `QuestionFigureSharedCachePresenterMixin`。
- 删除共享缓存专用模块：
  - `src/ui/panels/assets/cache_presenter.py`
  - `src/ui/panels/assets/question_cache.py`
  - `src/services/material_assets/cache_projection.py`
- 题图库状态列改成本地/预览状态，不再依赖共享缓存投影。
- 移除 `asset_item_remote_asset_id` 兼容别名，统一使用 `asset_item_library_asset_id` 表达素材身份。
- 删除远程缓存正向测试，新增/改写反向守门测试，覆盖不会创建 `_remote_asset_cache`、不会输出 `remote_asset_cache` / `remote_asset_items`、不会暴露共享缓存 API。

保留：

- 本地题图清单、题图排序、题图修复、修复审计、Word 图片插入。
- `asset_id` / `assetId` 作为本地素材身份元数据。
- `cache_path` / `local_path` / `resolved_path` 作为本地路径兜底，但不再用于远程 URL 下载或远程缓存替换。
- 旧下载鉴权字段在字段编辑器中仍被剔除，作为历史数据清洗黑名单，不再驱动任何运行时行为。

验证：

```powershell
python -m compileall -q src tests\test_material_execution_context.py tests\test_assets_panel_architecture.py tests\test_assets_panel_helper_modules.py tests\test_material_asset_services.py tests\test_assets_panel_question_figures.py
python -m pytest -q tests/test_material_execution_context.py tests/test_assets_panel_architecture.py tests/test_assets_panel_helper_modules.py tests/test_material_asset_services.py tests/test_assets_panel_question_figures.py
```

结果：

- `compileall` 通过。
- 聚焦 pytest：`132 passed in 535.17s (0:08:55)`。
- 删除批量 `remote_asset_items` 死分支后追加小回归：`5 passed in 115.67s (0:01:55)`。
