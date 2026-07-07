# 启动加载优化执行记录

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
