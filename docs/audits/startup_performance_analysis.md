# 启动与页面加载性能分析

日期：2026-07-03

## 背景

当前应用已经做过一轮启动体验调整：

- 启动窗先显示。
- 首屏只准备工作台首页。
- 主窗口首次显示前做首页布局整理，避免首页刚出现时明显拉伸。
- 其他顶层页面改为首页出现后的后台预加载。
- 模板页只后台预热较重的详情页：标题编号、页眉页脚、目录。

这轮调整改善了“启动时页面轮播闪烁”和“启动窗等待过久”的问题，但它没有消除程序内部的结构性开销。后续优化要区分两件事：

- 体验策略：什么时候让用户看见界面，什么时候后台预热。
- 真实性能：减少控件、样式、布局、导入、数据装配的总工作量。

## 分析方法

本次分析使用三类证据。

1. 离屏 Qt 启动计时

   使用 `QT_QPA_PLATFORM=offscreen` 构造 `QApplication` 和主窗口，测量 `MainWindow()` 构造耗时与 `startup_ready` 触发时间。

2. 单面板构造计时

   直接调用 `create_panel(panel_id, bridge)`，测量每个顶层页面真实创建耗时。

3. `cProfile` 热点采样

   对 `ScenePanel` 和 `AssetsPanel` 的创建过程做 cumulative profile，观察主要耗时来源。

4. 静态复杂度扫描

   统计核心文件行数、`setStyleSheet`、`bind_theme`、`refresh_layout_chain` 等调用数量，判断长期维护风险。

## 当前测量结果

### 首屏启动

当前版本离屏测量：

| 项目 | 耗时 |
| --- | ---: |
| `MainWindow()` 构造 | 约 1401 ms |
| `startup_ready` | 约 1419 ms |
| ready 时已加载页面 | WorkbenchPanel + 其他占位页 |

含义：

- 启动窗等待已经主要等工作台首页，而不是等所有页面。
- 当前首屏路径比“全量预加载”明显更短。
- 但工作台首页本身仍然不轻，约 1.2 到 1.4 秒。

### 顶层页面构造成本

离屏单面板构造计时：

| 页面 | 构造耗时 |
| --- | ---: |
| 工作台 | 约 1270 ms |
| 场景配置 | 约 1229 ms |
| 模板管理 | 约 299 ms |
| 资料包 | 约 965 ms |
| 主题 | 约 9 ms |

含义：

- 慢的不只是启动策略，页面本体构造也重。
- `ScenePanel` 和 `AssetsPanel` 即使放到后台，也会在用户或后台触发时造成主线程压力。
- `ThemePanel` 很轻，不是问题。

### 模板详情构造成本

| 模板详情 | 构造耗时 |
| --- | ---: |
| 页面设置 | 约 137 ms |
| 正文排版 | 约 163 ms |
| 标题编号 | 约 363 ms |
| 表格 | 约 149 ms |
| 页眉页脚 | 约 374 ms |
| 目录 | 约 286 ms |
| 题注 | 约 170 ms |

含义：

- 模板页顶层不算重，但内部详情有明显首开成本。
- 现在后台只预热标题编号、页眉页脚、目录，是合理折中。
- 如果用户刚进首页后立刻打开模板详情，仍可能抢在后台预热前触发点击加载。

## 结构性拖累

### 1. `AssetsPanel` 文件和职责过大

`src/ui/panels/assets_panel.py`：

| 指标 | 数值 |
| --- | ---: |
| 行数 | 70041 |
| 文件大小 | 约 3.18 MB |
| `setStyleSheet` | 149 次 |
| `refresh_layout_chain` | 11 次 |

问题：

- 一个类承载生成、导入导出、字段、图片、预览、批量、高级设置等多个子页面。
- `_setup_ui()` 中创建大量当前不可见区块。
- `_apply_theme()` 和 `setStyleSheet` 成本很高。

风险：

- 越继续加功能，启动和切页越容易变慢。
- 后续修改容易引入隐性刷新和布局抖动。

### 2. `ScenePanel` 一次性创建所有详情

`src/ui/panels/scene_panel.py` 在 `_setup_ui()` 中直接创建：

- `_SceneOverviewDetail`
- `_ExamPaperDetail`
- `_ScopeDetail`
- `_StyleRulesDetail`
- `_SceneReferenceDetail`
- `_CleanupDetail`
- `_ContentDetail`
- `_OutputDetail`
- `_SceneRulesDetail`

问题：

- 用户只看概览时，其他详情已经创建。
- `ScenePanel` profile 中 import、QSS、主题应用都很重。

Profile 热点：

| 热点 | 累计耗时 |
| --- | ---: |
| `scene_panel._setup_ui` | 约 1.5 s |
| import 链 | 约 0.8 s |
| `setStyleSheet` | 约 0.6 s |
| `_apply_theme` / shell theme | 约 0.4 到 0.5 s |

### 3. QSS 重复应用成本高

两个 profile 都显示 `setStyleSheet` 是大头：

| 页面 | `setStyleSheet` 累计耗时 |
| --- | ---: |
| ScenePanel | 约 0.6 s |
| AssetsPanel | 约 0.65 s |

问题：

- 很多控件在构造时立即 `_apply_theme()`。
- 隐藏控件也在构造阶段套样式。
- Qt QSS 解析和刷新不便宜，频繁调用会阻塞主线程。

### 4. 首页也不是轻首页

`WorkbenchPanel` 当前不是简单 dashboard，而是创建：

- 快速执行详情
- 配置管理详情
- 多个能力详情 pane
- 执行历史相关 pane
- 策略摘要和导航控制器

问题：

- 当前首屏 1.2 到 1.4 秒主要来自工作台本身。
- 后续如果要把首屏压到 1 秒以内，必须拆 Workbench 首页。

## 懒加载是否是正确做法

结论：是正确方向，但必须受控地做。

懒加载本身不是“偷懒”，而是桌面软件常规做法。真正的问题是懒加载会改变生命周期，因此需要明确规则。

### 懒加载适合的对象

- 当前不可见的详情页。
- 大型表单区块。
- 高级设置、批量处理、资料预览等低频区域。
- 场景页中非概览详情。
- 资料包中非当前 section。

### 不适合懒加载的对象

- 全局 bridge 状态容器。
- 当前首页必须显示的控件。
- 正在运行任务的控制器。
- 关闭时必须参与 shutdown 的执行 worker。
- 用户点击后必须立即响应的轻控件。

## 可能引入的新问题

### 1. 信号错过

如果面板未创建，可能错过 `scene_changed`、`template_changed`、`document_loaded` 等信号。

防护方式：

- 面板创建时必须从 `PanelBridge` 读取当前快照。
- 不依赖“曾经收到过某个信号”作为初始化条件。
- 对跨页面导航 intent，在面板创建后再调用 `handle_navigation_intent`。

### 2. 用户点击时遇到冷加载

如果后台还没预热到目标页面，用户点击会同步加载。

防护方式：

- 点击导航时优先加载目标页。
- 在目标页显示轻量 skeleton。
- 对高概率页面做后台优先级预热。

### 3. 后台预热造成首页卡顿

后台预热仍在主线程，若连续构造大页面，首页会短暂停顿。

防护方式：

- 每次只加载一个小任务。
- 每步间隔 150 到 300 ms。
- 首页显示后延迟 800 到 1000 ms 再启动后台预热。
- 重页面放低优先级，例如 `AssetsPanel`。

### 4. 文件监听器延迟安装

例如场景库、模板库 watcher 如果随面板延迟创建，面板打开前不会监听文件变化。

防护方式：

- 打开面板时主动 refresh 一次磁盘。
- 真正全局需要监听的内容放到轻量 service，不放在 UI 面板里。

### 5. 状态脏标记不同步

懒加载页面若持有自己的 dirty 状态，创建晚了可能和 bridge 不一致。

防护方式：

- dirty 状态以 `PanelBridge` 为单一事实来源。
- 面板构造时只读取 bridge 当前值。
- 保存/重置操作统一通过 bridge 发布。

### 6. 测试复杂度上升

懒加载会让测试从“对象一定存在”变成“对象可能尚未存在”。

防护方式：

- 提供 `ensure_*_loaded()` 测试辅助。
- 对导航、bridge replay、首次打开详情页分别补测试。

## 推荐优化路线

### Phase 0：建立基线

目标：

- 保留当前离屏启动计时脚本。
- 为 `create_panel`、重详情创建、后台预热增加可选日志。

验收：

- 每次优化后能看到首屏 ready、页面首次打开、后台预热的耗时变化。

### Phase 1：首屏优先

状态：已完成初步版本。

做法：

- 启动窗只等待首页。
- 其他页面后台按优先级加载。
- 模板只后台预热高成本详情。

收益：

- 首屏 ready 约 1.4 秒。
- 启动闪烁和首帧拉伸明显降低。

### Phase 2：ScenePanel 详情懒构建

推荐下一步先做。

做法：

- `ScenePanel` 启动时只创建 overview。
- exam、rules、content 等详情改为 factory。
- `_show_detail(card_id)` 时 `ensure_detail_loaded(card_id)`。
- `handle_navigation_intent` 进入具体详情前先 ensure。

原因：

- 改造范围比 `AssetsPanel` 小。
- 风险可控。
- 可以验证懒加载模式在当前架构下是否稳定。

预计收益：

- `ScenePanel` 首次创建从约 1.2 s 降到约 0.4 到 0.7 s。
- 后台加载对首页的影响下降。
- 打开具体详情时可能有 100 到 400 ms 首开成本。

### Phase 3：AssetsPanel section 懒构建

收益最大，但风险也最大。

做法：

- `AssetsPanel` 初始只创建 shell、section nav、generate section。
- `fields/images/preview/batch/advanced` 改为 section factory。
- `_on_section_selected(section_id)` 时创建对应 section。
- `_apply_theme()` 只作用于已创建 section。
- `_refresh_summary()` 不依赖未创建控件，或只更新数据模型。

预计收益：

- `AssetsPanel` 首次创建从约 0.9 到 1.0 s 降到约 0.3 到 0.5 s。
- 文件体量仍大，但实际控件创建减少。

主要风险：

- `_refresh_summary`、资料同步、repair navigation 现在可能假设控件已存在。
- 需要逐个梳理 section 间依赖。

### Phase 4：Workbench 首页瘦身

做法：

- 首页只创建 quick execution 当前视图。
- 配置管理、执行历史、能力详情改成 factory。
- Workbench 内部 master-detail 也使用懒详情。

预计收益：

- 首屏 ready 从约 1.4 s 进一步降到约 0.8 到 1.1 s。

风险：

- Workbench 是主流程入口，测试要求更高。

### Phase 5：QSS 与主题系统优化

做法：

- 尽量少对子控件逐个 `setStyleSheet`。
- 共享样式字符串缓存。
- 用 objectName/property + 父级 QSS 替代频繁局部 QSS。
- 隐藏控件首次显示前不主动 `_apply_theme()`。
- 大型页面创建时临时 `setUpdatesEnabled(False)`，完成后一次打开。

预计收益：

- 许多页面创建耗时下降 20% 到 40%。
- 页面切换时的卡顿和拉伸减少。

### Phase 6：导入链拆分

做法：

- 避免首页 import 大型 runtime/projection 模块。
- 大型执行 runtime 只在执行任务时 import。
- 场景矩阵、审计投影等低频模块后移。

预计收益：

- 冷启动和首次创建页面的 import 峰值下降。
- 对打包后首次运行尤其有帮助。

## 推荐顺序

建议顺序：

1. ScenePanel 详情懒构建。
2. AssetsPanel section 懒构建。
3. Workbench 首页瘦身。
4. QSS 缓存和主题刷新治理。
5. import 链拆分。

原因：

- ScenePanel 是较好试点：收益明显、风险适中。
- AssetsPanel 收益最大，但依赖复杂，适合在懒加载模式验证后再做。
- QSS 优化横跨很多组件，适合作为第二轮系统治理。

## 体验可以优化到什么程度

以下是合理预期，不是承诺值，最终需要以实机测量为准。

| 阶段 | 首屏等待 | 页面闪烁 | 模板页首开 | 场景页首开 | 资料页首开 |
| --- | ---: | --- | --- | --- | --- |
| 调整前 | 多秒级 | 明显 | 多个详情首次加载 | 秒级 | 秒级 |
| 当前版本 | 约 1.4 s 离屏 | 基本消除 | 重详情后台预热，仍可能抢先点击冷加载 | 后台或点击加载 | 后台或点击加载 |
| Scene 懒构建后 | 约 1.3 到 1.4 s | 基本消除 | 类似当前 | 概览更快，详情按需 | 类似当前 |
| Assets 懒构建后 | 约 1.2 到 1.4 s | 基本消除 | 类似当前 | 更稳 | 资料首页更快，子区按需 |
| Workbench 瘦身后 | 约 0.8 到 1.1 s | 基本消除 | 后台/按需 | 后台/按需 | 后台/按需 |
| QSS/import 治理后 | 约 0.7 到 1.0 s | 基本消除 | 首开更顺 | 首开更顺 | 首开更顺 |

实际用户感受目标：

- 启动窗不超过 1 秒左右，最多 1.5 秒。
- 首页出现后无明显拉伸和轮播闪烁。
- 点击模板、场景、资料区时，如果未后台加载完成，应显示稳定 skeleton，而不是卡死。
- 高频路径第二次进入应接近瞬时。

## 结论

1. 懒加载是正确方向，但不能粗暴地“到处懒加载”。
2. 当前程序确实存在结构性拖累，尤其是 `AssetsPanel`、`ScenePanel` 一次性构建和大量 QSS。
3. 继续用启动动画遮住所有工作不是正确路线，会让等待变长。
4. 最优路线是：首屏优先 + 受控后台预热 + 页面内部懒构建 + QSS/主题治理。
5. 下一步最建议先做 `ScenePanel` 详情懒构建，作为低风险验证；确认稳定后再拆 `AssetsPanel`。
