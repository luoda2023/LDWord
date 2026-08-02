# 启动加载优化执行记录

## 2026-07-30 补充：统一一级页面生命周期

状态：本轮执行完成；发布包 P50/P95 与关闭期方案事务去页面化仍待单独闭环。

本轮把“正确启动”收敛为一个规则：启动只构造当前必须可用的工作台；其余一级页面不预热、不抢主线程，统一由页面宿主在用户明确进入后加载。侧边栏点击和工作流深链不再走两套时序。

### 已落地

- 一级页面统一使用 `unloaded → scheduled → loading → ready / failed` 状态。
- 方案、模板、资料包、助手、主题和设置都先切换到稳定占位页，再于下一事件循环构造真实页面。
- 深链意图在页面就绪后回放；加载中再次导航保留最后目标。
- 用户在构造开始前离开目标页时取消排队任务；加载失败留在原位并提供“重试”。
- 删除方案、模板及其详情的启动后隐藏预热队列和定时器。
- 工作台不再提前导入执行运行时和文档结构识别；二者分别在真正执行、真正选择兼容文档后创建。
- “成套交付”保留入口，但其详情和 Excel/交付运行时在首次进入该功能时加载。
- splash 在导入主窗口前显示；主窗口 ready 后直接交接，不再使用固定 80 ms 延迟或透明窗口过渡。
- 工作台构造期间共享一次只读方案/模板选择器快照，并在同一构造会话内只确保一次方案库和模板库；会话结束立即失效。
- 一级页面工厂改为显式懒注册表；未知页面 ID 直接失败，不再静默显示成“未开放”。
- 工作台和资料包不再重复给 `MasterDetailShell` 应用同一套主题。
- 资料包初始化只投影一次真实档案，不再先投影空档案；重复行样式改为一条页面级规则。
- 资料包继承样式在空控件树阶段安装，避免构造完成后让 Qt 重新 polish 整棵页面树。

### 实测

环境：Windows、Python 3.12、`QT_QPA_PLATFORM=offscreen`，源码启动。

| 指标 | 调整前 | 本轮 |
| --- | ---: | ---: |
| 进程内 Qt 应用创建至 `startup_ready` | 约 5.2–5.4 s | 约 2.60 s |
| `MainWindow()` | 约 4.0–4.2 s | 约 1.73 s |
| `WorkbenchPanel()` | 未单列 | 约 1.40 s |
| 启动后自动创建的一级页面 | 工作台，随后隐藏预热方案/模板 | 仅工作台 |
| 资料包真实构造 | 约 4.0 s | 约 1.21 s |
| 资料包主题阶段 | 约 0.53 s | 约 0.034 s |

这些是单次源码离屏样本，不替代发布包 P50/P95。资料包点击仍先显示占位页，真实 Qt 控件树仍在主线程构造；当前已经移除可证明的重复工作，但不把占位反馈误记为异步加载。

### 被否决的实现

曾验证把现有 `AssetsPanel` 初始化机械拆成多个 0/16 ms 定时器。结果是首开总时长从约 3.3 秒上升到 6–9 秒，最大长任务仍约 2.6–3.7 秒。原因是数据装载、控件投影、主题和汇总刷新仍互相依赖，定时器只改变顺序，没有减少工作量。该实现已撤回。

资料包若继续向 500 ms 内首开推进，必须先把分区数据模型与控件投影解耦，再让 `fields/content/timeline/images/attachments` 各自按需创建；不能继续叠加伪异步定时器。

### 工作台懒加载边界

`QuickExecutionDetail`、多文件执行和按资料记录执行不是三个一级功能，而是“文档执行”在输入明确后的三种系统拓扑。它们共享同一输入清单、方案/模板绑定、资料上下文和执行反馈，因此本轮保留一个状态源，不为减少构造数字引入三套延迟状态。只有独立的“成套交付”继续按需创建。

### 当前未闭环

1. 方案为脏但 `ScenePanel` 尚未创建时，关闭程序或切换工作模式仍会反向创建方案页。事务核心 `SceneSessionCoordinator` 已经无 UI；剩余耦合是“未保存修改”提示和内置方案副本命名仍由 `ScenePanel` 提供。正确下一步是增加主窗口级事务参与者并复用这两个小型交互，不能直接清除 dirty 状态。
2. 发布包启动 P50/P95 尚未复测；当前数据仅为源码离屏基线。

### 回归边界

- `tests/test_main_window_panel_loading.py`：无隐藏预热、统一状态、离开取消、深链回放、失败重试。
- `tests/test_workbench_panel.py`：资料包一级入口和工作流跳转。
- `tests/test_material_suite_workbench.py`：成套交付按需创建后仍复用原执行生命周期。
- `tests/test_template_import_coordinator_lifecycle.py`：关闭时取消真实排队任务，不再验证已删除的预热定时器。
- `tests/test_config_library_read_session.py`：同一构造会话内只物化一次库，跨会话不缓存。
- `tests/test_panel_factory_registry.py`：全部一级入口都有唯一懒工厂，未知入口明确失败。

以下 2026-07-03 内容保留为历史基线；其中“后台预热方案/模板”的策略已由本补充废止。

日期：2026-07-03

## 结论先行

这次采用的方向是正确的，但正确点不是“加启动动画然后一次加载完所有页面”。更稳的路线是：

1. 启动动画只覆盖不可避免的首屏构造时间。
2. 首屏只保证工作台首页可用。
3. 常用且相对轻的页面在进入后空闲预热。
4. 重页面按需加载，并给用户一个明确的加载态。
5. 不再让所有页面在启动阶段快速闪过，也不在进入首页后偷偷加载很重的页面。

如果改成“启动动画期间一次性加载完所有页面”，体验大概率会变差：启动窗等待更久，主线程仍然会被大量 Qt 控件构造、样式应用、布局计算和模块 import 占满。动画只能遮住等待，不能消除等待。

## 本轮实际执行路线

### 1. 启动壳层

改动位置：

- `main.py`
- `src/ui/startup_splash.py`
- `src/ui/main_window.py`

策略：

- 启动时先显示一个轻量 splash。
- `MainWindow` 构造完成并发出 `startup_ready` 后再显示主窗口。
- 主窗口显示前用透明度过渡，减少进入首页前的闪烁和突兀拉伸感。

边界：

- splash 不承担“加载全部页面”的职责。
- splash 状态文案只反映当前阶段，不制造虚假进度。

### 2. 主窗口页面加载策略

改动位置：

- `src/ui/main_window.py`

策略：

- 启动只真实构造首页 `WorkbenchPanel`。
- 其它页面先放 `_PlaceholderPanel`。
- 空闲后台只预热 `template`、`theme`、`scene`。
- 不再后台预热 `assets`、`pipeline`、`preferences`。

原因：

- `AssetsPanel` 首次构造约 1 秒，是进入首页后隐藏卡顿的主要来源之一。
- 把它从后台预热移除后，进入首页后 9.5 秒内不会再偷偷触发这个重构造。

### 3. 资产页按需异步占位

改动位置：

- `src/ui/main_window.py`

策略：

- 用户点击资产页时，立即切到占位页并显示“正在加载”。
- 真正的 `AssetsPanel` 延后到事件循环里构造。
- 构造完成后，如果用户仍停在资产页，自动替换为真实页面。
- 如果用户中途切回首页，不会强行把用户拉回资产页。

这个做法不会消灭 `AssetsPanel` 本身约 1 秒的构造成本，但能避免点击瞬间主线程冻结，看起来会顺很多。

### 4. 场景页 detail 懒构造

改动位置：

- `src/ui/panels/scene_panel.py`

策略：

- `ScenePanel` 首次只构造总览。
- 规则、内容、试卷等 detail 在第一次打开时再构造。
- 已加载 detail 继续参与状态同步和信号绑定。

边界：

- 懒构造不能让状态丢失。
- `__getattr__`、`_ensure_detail_loaded`、`_sync_loaded_detail_state`、`_wire_loaded_detail_signals` 保证旧代码访问 detail 时仍能拿到真实控件。
- 导航 intent 进入场景页时使用同步加载，避免把导航请求投递给占位页后丢失。

### 5. 工作台重模块延后

改动位置：

- `src/ui/panels/workbench/quick_execution_detail.py`
- `src/ui/panels/workbench/execution_session_controller.py`
- `src/ui/panels/workbench/panel_v2.py`
- `src/ui/adapters/workbench_execution_adapter.py`
- `src/config/style_variant_semantics.py`

策略：

- 执行 runtime、worker、`docx.Document`、文档结构分析、最近结果面板、样式管理完整块等都改为局部 import 或按需构造。
- 工作台初始只显示轻量的场景与模板选择区。
- 只有用户真的触发样式差异复核或切换相关场景时，才构造完整 `StyleManagementBlock`。

边界：

- 保留 `recent_run_panel_module._open_artifact_file(...)` 兼容入口，避免测试和调用方直接失效。
- 风格差异存在时仍能自动补齐完整样式块，不牺牲功能完整性。

## 验证结果

验证环境：

- Windows
- `QT_QPA_PLATFORM=offscreen`
- Python 3.12.10
- PySide6 离屏构造计时

### 启动与后台预热

| 指标 | 优化前基线 | 本轮实测 |
| --- | ---: | ---: |
| `startup_ready` | 约 1419 ms | 约 781 ms |
| `MainWindow()` 构造 | 约 1399 ms | 约 766 ms |
| 启动后立即真实页面 | 多页面预加载倾向 | 仅 `WorkbenchPanel` |
| 进入后 9.5 秒内资产页 | 可能被后台构造 | 仍是占位页 |

本轮实测页面状态：

| 时刻 | 真实页面 |
| --- | --- |
| 启动后立即 | `WorkbenchPanel` |
| 4.5 秒后 | `WorkbenchPanel`、`ScenePanel`、`TemplatePanel`、`ThemePanel` |
| 9.5 秒后 | `WorkbenchPanel`、`ScenePanel`、`TemplatePanel`、`ThemePanel` |

结论：进入首页后不再隐藏加载 `AssetsPanel`，因此不会再在启动后几秒突然出现约 1 秒的后台卡顿。

### 资产页

| 场景 | 结果 |
| --- | ---: |
| 点击资产页返回耗时 | 约 0.3 ms |
| 点击后立即显示 | `_PlaceholderPanel` 加载态 |
| 真实资产页完成后 | `AssetsPanel` |
| 点击资产页后立刻切回首页 | 异步完成后仍停在 `WorkbenchPanel` |

结论：点击响应已经接近即时，但真实资产页内容仍需约 1 秒完成构造。下一轮如果要继续优化，应拆 `AssetsPanel` 内部，而不是继续改启动策略。

### 场景页

| 指标 | 结果 |
| --- | ---: |
| 真实路径首次打开场景页 | 约 616 ms |
| 首次打开后已加载 detail | `scn_overview` |
| 首次打开规则 detail | 约 740 ms |
| 首次打开内容 detail | 约 61 ms |
| 首次打开试卷 detail | 约 20 ms |

优化前场景页整体构造约 1229 ms。现在首开场景页只加载总览，重的规则 detail 延后到首次点击规则页时发生。

### 工作台样式模块

| 指标 | 结果 |
| --- | ---: |
| 工作台初始完整样式块 | `False` |
| 显式构造完整样式块 | 约 387 ms |
| 构造后状态 | `True` |

结论：工作台首页不再为完整样式管理块支付启动成本。代价是首次进入样式差异复核时会有约 0.4 秒构造成本。

### 自动化验证

已通过：

```powershell
python -m compileall main.py src/ui/main_window.py src/ui/startup_splash.py src/ui/panels/scene_panel.py src/ui/panels/workbench/panel_v2.py src/ui/panels/workbench/quick_execution_detail.py src/ui/panels/workbench/execution_session_controller.py src/ui/adapters/workbench_execution_adapter.py src/config/style_variant_semantics.py
```

已通过：

```powershell
pytest tests\test_quick_execution_detail_architecture.py tests\test_workbench_detail_architecture.py tests\test_workbench_issue_navigation.py tests\test_scene_repair_routing.py tests\test_workbench_panel.py
```

结果：`91 passed`

## 会不会引入新的问题

当前看，主要风险已经被控制住，但有几个取舍需要明确。

### 1. 首次进入某些重页面仍会等

这是有意取舍。之前是启动阶段或进入首页后隐藏等待，现在变成用户真正点击重页面时显示加载态。它更诚实，也更不容易让首页突然卡住。

### 2. 懒加载可能导致状态不同步

已针对场景页做了边界处理：

- 未加载 detail 不强行更新。
- detail 首次加载后立即同步当前 scene/template 状态。
- 已加载 detail 才接入对应信号。

### 3. 异步加载可能抢走当前页面

已验证不会。资产页异步完成前如果用户切回首页，完成后仍停在首页。

### 4. 局部 import 可能把错误推迟到首次使用

这是懒加载常见代价。本轮用相关工作台、导航、场景修复测试覆盖了主要路径。后续如果某个很少用的执行分支有 import 问题，会在首次触发时暴露，而不是启动时暴露。

## 市面上大应用为什么不明显卡

它们通常不是“全部加载完再显示”，而是组合使用这些策略：

1. 壳层和首页极轻，先让用户看到可操作界面。
2. 路由级拆分，页面首次进入才加载。
3. 重资源后台预热，但只预热高概率、低干扰模块。
4. 列表、图片、复杂控件虚拟化，不一次性创建全部子控件。
5. 文件解析、网络、索引、缩略图生成放到 worker。
6. 首次加载时有 skeleton、进度条或局部占位，不冻结整个窗口。

所以你的程序卡，不是因为功能比它们多，而是因为之前不少重控件、重 import、重页面构造都压在启动或后台主线程里。

## 体验可以优化到什么程度

### 本轮之后

在离屏计时里，首屏 ready 从约 1.4 秒降到约 0.8 秒，下降约 45%。实际桌面启动还会受磁盘、杀毒、字体、显卡、PyInstaller 打包方式影响，合理预期是：

- 启动闪烁和页面轮播感基本消失。
- 首页可见时间明显缩短。
- 进入首页后数秒内的隐藏卡顿明显降低。
- 资产页点击不再瞬间冻结，但内容完成仍约 1 秒。
- 场景页首开比以前轻，规则页首次打开仍会有一次约 0.7 秒等待。

### 下一轮可达到

如果继续拆重页面内部，可以进一步做到：

| 优化对象 | 目标体验 |
| --- | --- |
| `AssetsPanel` 内部拆分 | 点击后 300 到 500 ms 内出现真实主体，列表/预览继续渐进填充 |
| 场景规则 detail 拆分 | 规则 detail 首开压到 300 到 400 ms 左右 |
| QSS/主题应用收敛 | 页面切换减少 100 到 300 ms 级别抖动 |
| import 预算治理 | 冷启动再削 100 到 300 ms |
| worker 化文件扫描/结构分析 | 重文档相关操作不再堵主线程 |

### 最终判断

当前路线是对的：不要追求启动动画期间“一次加载完”，而要把首屏做轻、把后台预热收窄、把重页面变成明确的按需加载。

本轮已经把启动体验从“启动和进入后都可能闪/卡”推进到“首页先稳定出现，重页面首次进入有明确加载态”。继续优化的主要战场已经不在启动动画，而在 `AssetsPanel`、场景规则 detail、QSS/主题和少数重 import 的内部拆分。
