# Windows 字体、缩放与 UI 渲染链路深度审计

- 日期：2026-07-12
- 范围：`main.py`、`src/shared/ui`、`src/ui`、相关 UI 测试与 Windows/Qt 渲染边界
- 运行环境：Windows，PySide6 6.10.2，当前窗口 `devicePixelRatioF() = 1.75`
- 起因：确认 UI 中文字体设置是否可靠，并进一步分析缩放后仍可能出现的字重异常、1px 线宽不一致、转角不平滑和整体 UI 架构杂糅问题
- 状态：已完成第一阶段基础链路整改；字体单一来源、内容树阴影隔离、DPR 描边、圆角边框几何和多 DPR 图标已落地，页面级 QSS/Surface 全量迁移仍按本文后续阶段推进

## 1. 执行结论

当前 UI 不是“微软雅黑配置完全错误”，也不是“某一个抗锯齿开关失效”。真实问题是多个本来可以分别成立的机制被叠加在同一渲染树中，但没有唯一所有者：

1. `QApplication` 硬编码 `Microsoft YaHei 10pt`，主题对象又保存一条独立 QSS 字体栈；
2. 大部分控件继承应用字体，少数输入框、下拉框和弹窗由 QSS 再次指定字体；
3. 局部 `setFont()` 与 QSS 同时存在，Qt 按 QSS 优先，导致部分代码表面执行、实际不生效；
4. 主窗口根容器安装 `QGraphicsDropShadowEffect`，该效果会作用于根容器及所有子控件；
5. 通用 `DesignSystemCard` 默认也安装并启用 `QGraphicsDropShadowEffect`，卡片内部文字可能再经过一层图形效果；
6. 主窗口使用透明无框窗口、DWM 扩展客户区、自定义圆角、自定义阴影、原生厚边框能力和重复的子控件 QSS 圆角；
7. `PassThrough` 保留 125%、150%、175% 等真实分数缩放，但 1 个逻辑像素会变成 1.25、1.5、1.75 个物理像素，1px 线条无法在所有位置保持完全相同的物理覆盖；
8. QSS、`QPainter`、SVG 预栅格化、原生控件文本和图形效果中间缓冲同时存在，各自的像素对齐、抗锯齿与合成路径并不相同；
9. 主题、尺寸、字体、圆角、描边和固定几何分散在大量文件中，已有共享组件只完成了部分收敛，未建立“唯一渲染所有权”。

因此，本项目目前属于一种“半收敛 UI 架构”：

- 已经有主题、共享输入框、共享圆角面板和共享卡片等抽象；
- 但页面级 QSS、自绘控件和 Windows 窗口外壳仍可绕过这些抽象；
- 某些测试只断言“使用了共享组件”，没有验证共享组件的像素行为是否正确；
- 抽象数量增加了，但渲染路径没有减少，反而形成多重覆盖。

这比单纯缺少设计系统更难维护。后续不应继续通过局部增加 `font-family`、调整某一条 `border-radius`、把 1.5 改成 1.7 或给单个控件补 margin 来处理。

## 2. 审计方法与证据边界

本次使用四类证据：

1. 静态链路追踪：
   - `QApplication.setFont()`；
   - `AppTheme.font_family`；
   - `setFont()`、QSS `font-family` 与 `font-weight`；
   - `QGraphicsDropShadowEffect`；
   - `RoundedSurfaceFrame`、QSS 圆角和 DWM 配置；
   - `devicePixelRatio` 与图标缓存。
2. Qt 运行时字体探针：
   - `QFontInfo`；
   - `QTextLayout` / glyph run 的真实字体；
   - 微软雅黑 400/500/600/700 权重映射；
   - QSS 与 `setFont()` 冲突后的最终字体。
3. 图形效果对照探针：
   - 在当前 DPR 1.75 环境中分别渲染带/不带 `QGraphicsDropShadowEffect` 的同构控件树；
   - 比较透明子标签区域和文字区域的像素差异。
4. 现有测试审阅：
   - 字体测试是否使用生产启动字体；
   - 圆角测试是否验证真实边缘；
   - 是否存在 1.0/1.25/1.5/1.75/2.0 缩放矩阵；
   - 是否覆盖多显示器 DPR 切换。

证据边界：

- 图形效果像素探针证明“启用效果后渲染结果发生变化”，不单独证明所有肉眼问题都由阴影效果引起；
- 分数 DPR 是线宽差异的重要条件，但颜色、透明合成、路径坐标和显示器子像素布局也会影响最终观感；
- 本审计不建议未验证就全局切换 DPI rounding policy；该操作会改变整个应用尺寸，不是局部修复。

## 3. 当前渲染链路

### 3.1 字体链路

```text
main.py
  QApplication.setFont(Microsoft YaHei, 10pt, PreferFullHinting)
        |
        +-- 大多数 QLabel / QPushButton / QWidget 直接继承
        |
        +-- 页面 QSS 只覆盖 font-size / font-weight
        |
        +-- 7 类共享 QSS 显式重写 font-family 为主题字体栈
        |      |
        |      +-- QSS 优先于 QWidget.setFont()
        |
        +-- 品牌标题局部 setFont(Segoe UI)
        |
        +-- 日志/占位符局部 Consolas / monospace
```

生产字体的真正权威来源仍是 `main.py`，不是主题系统。主题字体栈只覆盖少量输入框、组合框、SpinBox 和弹窗标题。

### 3.2 主窗口合成链路

```text
Windows DWM / 原生窗口样式
  + FramelessWindowHint
  + WA_TranslucentBackground
  + WS_THICKFRAME / WS_CAPTION
  + DwmExtendFrameIntoClientArea(-1)
  + DWMWCP_DONOTROUND
        |
        v
透明 QMainWindow
        |
        v
RoundedSurfaceFrame(window_container)
  + 自绘背景
  + 自绘 1px 圆角边框
  + QGraphicsDropShadowEffect   <-- 作用于整个子树
        |
        +-- TitleBar：QSS 再画顶部圆角
        |
        +-- Sidebar：QSS 再画左下圆角
        |
        +-- Panel / ScrollArea / viewport / detail：重复右下圆角
        |
        +-- DesignSystemCard
               + 自绘圆角和边框
               + 默认 QGraphicsDropShadowEffect  <-- 可能形成嵌套效果
               + 文本、按钮、输入框和自绘控件
```

这条链路至少有四类“外壳所有者”：Windows DWM、顶层透明窗口、根 `RoundedSurfaceFrame`、子控件 QSS。没有任何一层拥有完整且排他的职责。

## 4. 字体执行链路问题

### 4.1 双重字体权威

当前同时存在：

- `main.py`：`QFont("Microsoft YaHei")`；
- `theme.py`：`'Microsoft YaHei', 'Microsoft YaHei UI', 'Segoe UI Variable', ...`。

两者当前以同一字体开头，所以常规 Windows 环境看起来正常。但它们不是同一份数据，也没有同步机制。

潜在后果：

- 修改主题字体栈不会自动修改 `QApplication.font()`；
- 大量只设置字号的页面仍会继续使用旧应用字体；
- 少数显式写 `font-family` 的控件先切到新字体；
- 同一页面出现字体混用，但源码检查只看到主题值已经更新。

### 4.2 QSS 覆盖局部 `setFont()`

顶部工作模式组合框先执行：

```python
mode_font.setFamily("Segoe UI")
self._work_mode_combo.setFont(mode_font)
```

但 `StyledComboBox` 的 QSS 又声明：

```text
font-family: Microsoft YaHei, Microsoft YaHei UI, ...
```

运行时最终字体为 Microsoft YaHei。该 `setFont()` 不是有效策略，只是死配置。

这说明当前代码没有规定：

- 字体由 QFont API 管理；
- 还是由 QSS 管理；
- 特殊角色应在哪一层覆盖；
- 覆盖后由谁负责验证最终 `QFont`。

### 4.3 Segoe UI 的中文回退不可控

当前机器实测：

| 请求字体 | 英文 glyph | 中文 glyph |
|---|---|---|
| `Microsoft YaHei` | Microsoft YaHei | Microsoft YaHei |
| `Segoe UI` | Segoe UI | SimSun |
| `Segoe UI -> Microsoft YaHei` | Segoe UI | Microsoft YaHei |
| `Microsoft YaHei -> Segoe UI` | Microsoft YaHei | Microsoft YaHei |

所以“只设置 Segoe UI，中文自然回退到微软雅黑”不是可靠假设。品牌标题目前是纯英文，因此没有直接问题；任何未来加入中文、全角标点或动态文本的品牌控件都必须提供显式中文 fallback。

### 4.4 微软雅黑权重不是连续变量

当前 Windows 字体数据库中，Microsoft YaHei / Microsoft YaHei UI 只有 Light、Regular、Bold。运行时映射为：

| QSS 权重 | 实际字形 |
|---:|---|
| 400 | Regular |
| 500 | Regular |
| 600 | Bold |
| 700 | Bold |

因此 500 没有形成中等强调，600 又直接跳到粗体。当前仍有多处硬编码 500/600；小字号 600 可能显得突然变粗，600 与 700 又没有层级差。

### 4.5 pt 与 px 混合

- 应用默认字体：10pt；
- 主题与绝大部分 QSS：11px、12px、13px、15px、16px、20px；
- 局部自绘预览又使用文档点数转换为像素。

10pt 在 96 DPI 下约为 13.33px，所以默认环境中看起来接近 13px。但二者的设备与辅助功能语义不同。固定 px 更容易维持布局，pt 更接近设备无关字号；混用后，字体与控件高度可能在某些缩放或用户文字放大设置下不同步。

### 4.6 Full Hinting 是全局策略，不是局部修复

`PreferFullHinting` 会继承到普通微软雅黑控件，也会被复制到品牌 Segoe UI 字体和显式 QSS 字体对象。运行时探针确认该 hinting preference 在当前 PySide6 中继续存在。

它可能让部分小字号更锐利，但不解决：

- 图形效果中间缓冲；
- 分数 DPR 的边线覆盖；
- 圆角路径像素对齐；
- 字体 fallback；
- QSS 与 QFont 的优先级。

所以不能把 Full Hinting 当成整套渲染系统的统一答案。

## 5. 缩放、线宽与转角问题

### 5.1 PassThrough 的收益与代价

`PassThrough` 的收益是严格跟随 Windows 125%、150%、175% 等设置，不把用户选择强行放大或缩小到整数倍率。

代价是：

| 逻辑尺寸 | 125% | 150% | 175% |
|---:|---:|---:|---:|
| 1px 描边 | 1.25 物理像素 | 1.5 物理像素 | 1.75 物理像素 |
| 1.2px 描边 | 1.5 物理像素 | 1.8 物理像素 | 2.1 物理像素 |
| 1.5px 描边 | 1.875 物理像素 | 2.25 物理像素 | 2.625 物理像素 |

显示器不能真正点亮 1.75 个物理像素，只能通过相邻像素不同覆盖率模拟。这会使同一条线在不同位置、方向、背景和合成层下显得粗细略有差异。

Qt 6 本身默认使用 PassThrough，但 Qt 官方迁移说明明确指出：Qt Widgets 在 175% 等非整数缩放下可能出现 graphical glitches，并建议在确有问题时评估 rounding policy。该说明意味着当前现象不是项目独有，但项目的多重自绘与效果链会放大它。

### 5.2 描边宽度没有统一语义

当前自绘代码中同时出现 1、1.0、1.2、1.5、1.6、1.7、1.8、2 等描边宽度。例如组合框箭头在不同模式下分别使用 1.5、1.7、1.8；SpinBox 箭头使用 1.6。

这些值没有对应统一 token，也没有定义：

- 是逻辑像素还是希望得到的物理像素；
- 是 hairline、standard、emphasis 还是 icon stroke；
- 是否应根据 DPR 取整；
- 是否允许同一图标在不同控件中改变笔宽。

因此“调到肉眼差不多”的局部修改会不断累积。

### 5.3 QPen 默认端点和连接方式不适合所有图标

大量 `QPen(color, width)` 没有显式设置：

- `capStyle`；
- `joinStyle`；
- `cosmetic`；
- DPR snapping。

Qt 的默认值是 SquareCap + BevelJoin。对于 chevron、对勾、折线和小尺寸图标，SquareCap / BevelJoin 会产生平头或削角；在 1.5～1.8px 且分数 DPR 下，这种差异会更明显。Lucide SVG 本身使用 round cap / round join，但手绘 chevron 没有继承这套几何语义，所以同一个应用内的箭头转角会有两种风格。

### 5.4 `RoundedSurfaceFrame` 对 2px 边框的 inset 计算错误

当前实现只要存在边框就固定使用：

```python
inset = 0.5
```

正确的几何边界至少应依据 `border_width / 2`。当主题卡片选中状态使用 2px 边框时，路径仍只内缩 0.5px，外侧半个像素会落到控件边界之外并被裁切，结果可能表现为：

- 边框实际小于请求宽度；
- 上/左与下/右覆盖不同；
- 圆角外缘被切平；
- 1px 与 2px 状态切换时边缘抖动。

这是已确认的几何定义错误，不只是审美问题。

### 5.5 圆角绘制没有单一所有者

根 `RoundedSurfaceFrame` 已经绘制窗口圆角，但下游又重复设置：

- TitleBar 顶部左右圆角；
- Sidebar 左下圆角；
- WorkbenchPanel 右下圆角；
- detail scroll 右下圆角；
- detail container 右下圆角；
- scroll viewport 右下圆角。

同一右下角可能被四个不同 QWidget/QSS 背景分别栅格化。即使半径数值相同，它们的实际矩形边界、裁剪区域、DPR 相位和 QSS/QPainter 算法也可能不同，容易形成接缝、局部尖角或深浅不同的抗锯齿边。

`RoundedSurfaceFrame.childEvent()` 只调用 `child.setAutoFillBackground(False)`。这不能禁止子控件的 QSS `background` 绘制，也没有给整个子树建立抗锯齿圆角 clip。其注释“子控件不会覆盖圆角”比真实能力更强，属于错误的架构承诺。

## 6. 图形效果是当前最高风险渲染分叉

### 6.1 根容器阴影作用于整个应用子树

主窗口执行：

```python
self._container.setGraphicsEffect(self._shadow)
```

Qt 官方文档明确说明，`QWidget.setGraphicsEffect()` 会把效果应用到该控件及其所有子控件。也就是说，这不是只给圆角背景画一圈阴影，而是把标题、面板、文字、输入框、预览和所有卡片一起放入 graphics effect 渲染管线。

图形效果的工作方式位于 source 与 destination 之间，并可从 source 生成 pixmap。即使 Qt 内部对具体效果做了优化，也不能再假设所有文字与 1px 边线都与无效果控件走完全相同的直接绘制路径。

### 6.2 卡片默认再次安装阴影

`DesignSystemCard` 构造时默认：

```python
self._shadow_enabled = True
self.setGraphicsEffect(self._shadow)
```

静态扫描发现约 93 个 `Card` / `SurfaceCard` / `DesignSystemCard` 构造匹配点，只有少量导航卡片显式 `shadow=False`。因此很多文字可能处于：

```text
主窗口根 graphics effect
  -> 卡片 graphics effect
     -> QLabel / 输入框 / 自绘文字
```

这种嵌套中间渲染非常可能造成以下差异：

- 卡片内外同字号文字锐度不同；
- 透明 QLabel 与父背景的合成不同；
- 细边线颜色和覆盖率发生变化；
- 动态内容更新使整张卡片效果源失效并重绘；
- 大量卡片同时存在时增加离屏缓冲与重绘成本。

### 6.3 DPR 1.75 对照探针

在当前 DPR 1.75 环境中，构造 300×80 白色圆角容器及透明 QLabel，对比启用/禁用 `QGraphicsDropShadowEffect` 后的抓图像素：

| 场景 | 容器内部变化像素 | 最大 RGBA 通道差总和 |
|---|---:|---:|
| 透明空 QLabel | 2052 | 114 |
| 同位置含中英文文本 | 3830 | 635 |

该探针不能直接等价于生产窗口截图，但确认了两件事：

1. 图形效果不是“只在外侧多画阴影、内部完全不变”的透明操作；
2. 透明子控件和文字会让差异显著增加。

所以根容器和通用卡片上的 graphics effect 应列为 P0 验证与拆除候选。

## 7. 图标与多显示器 DPR 问题

图标系统将 SVG 预先栅格化为 `QPixmap`，DPR 来源是：

```python
app.devicePixelRatio()
```

问题：

1. 这是应用级 DPR，不是目标 widget/window 当前屏幕的 DPR；
2. 缓存 key 包含 DPR，但没有监听 `screenChanged` 或 `DevicePixelRatioChange`；
3. 窗口从 175% 显示器移到 100%/150% 显示器时，缓存图标可能继续使用旧 DPR；
4. SVG 路径虽然有 round cap / round join，但错误的预栅格化尺寸和二次缩放仍会导致线宽、清晰度和转角变化。

当前没有多显示器 DPR 切换测试，也没有统一的 target DPR 获取接口。

建议优先让 `QIcon` 在目标尺寸请求时由 SVG engine 渲染，或至少让图标 API 接收目标 widget/window，并在 DPR 变化事件中失效对应缓存。

## 8. 架构整洁度评估

### 8.1 静态规模

| 指标 | 当前值 |
|---|---:|
| `AppTheme` 字段数 | 256 |
| `theme.py` 行数 | 1436 |
| `setStyleSheet()` 调用 | 445 |
| 含 `setStyleSheet()` 的文件 | 121 |
| 含自定义 `QPainter` 的文件 | 19 |
| 字面量 `setFixedSize/Width/Height` 匹配 | 90 |
| 字面量圆角匹配 | 22 |
| 字面量字体大小匹配 | 23 |
| 字面量字体权重匹配 | 23 |
| 字面量 QPen 宽度匹配 | 20 |
| 显式使用主题字体栈的位置 | 7 |

这些数字不是缺陷数量，但能说明样式写入权分布很广。

### 8.2 `AppTheme` 已成为 God Object

`AppTheme` 同时包含：

- 核心颜色；
- 语义状态颜色；
- 字体；
- 全局间距；
- 按钮、输入框、ComboBox、SpinBox 尺寸；
- 面板、预览、导航、标题编号等业务组件几何；
- 阴影与动画。

主题切换本应主要处理颜色与少量密度/排版策略，现在却承载大量组件内部尺寸。结果是：

- 每个新增控件倾向继续给 `AppTheme` 增加字段；
- token 很多，但仍存在大量局部数字；
- 主题对象看似统一，实际上无法阻止页面绕过；
- 难以区分哪些值是跨应用语义，哪些只是某一组件实现细节。

### 8.3 共享组件只统一了名称，没有统一绘制契约

例如“Card”已经集中到 `DesignSystemCard`，但该集中同时把 graphics effect 默认扩散给所有卡片。`RoundedSurfaceFrame` 统一了圆角绘制入口，却没有统一子树 clip、DPR snapping 或不同边框宽度的几何规则。

这说明当前测试和重构经常以“是否使用共享类”为完成标准，而不是以“是否只有一条正确渲染路径”为标准。

### 8.4 测试在固化实现，而不是保护结果

现有圆角测试主要断言：

- MainWindow 使用 `RoundedSurfaceFrame`；
- BaseDialog 使用 `RoundedSurfaceFrame`；
- TitleBar/Sidebar/Panel 中都出现 `shell_radius`；
- Card 中出现 `QGraphicsDropShadowEffect`。

这些测试会把重复圆角和 graphics effect 当成架构要求，却没有验证：

- 1px/2px 边框四边是否同宽；
- 125%/150%/175% 是否出现边缘断裂；
- 卡片内外文字像素是否一致；
- 子控件背景是否越过父圆角；
- 移动到不同 DPR 屏幕后图标是否重新渲染。

字体测试也主要扫描源码字符串。测试 fixture 的 offscreen `QApplication` 默认是 `Sans Serif 9pt`，没有执行生产环境的 `Microsoft YaHei 10pt` 初始化，因此布局测试与生产字体度量并不一致。

### 8.5 总体判断

“堆屎山”不是严谨的技术分类，但用户感受到的随机性是有证据的。更准确的描述是：

> UI 层已经出现高耦合、分布式样式写入、重复渲染所有权和实现导向测试；共享抽象数量较多，但抽象之间没有稳定的边界协议。

当前还没有到不可重构的程度，因为主题、共享输入、自绘 surface 和测试基础已经存在。问题在于需要停止继续横向增加局部抽象，先纵向收敛字体、surface、stroke、effect、DPR 五条基础链路。

## 9. 根因优先级

### P0：直接影响渲染一致性

1. 主窗口根容器 graphics effect 覆盖整个 UI 子树；
2. `DesignSystemCard` 默认 graphics effect，形成潜在嵌套效果；
3. `RoundedSurfaceFrame` 对 2px/3px 边框仍固定 inset 0.5；
4. 圆角由父 surface 和多个子 QSS 重复绘制；
5. 字体存在 QApplication/QSS 双权威；
6. 测试未复用生产字体初始化。

### P1：在分数缩放与多显示器下放大

1. 自绘描边没有 DPR snapping；
2. QPen 端点/连接方式未形成统一 token；
3. 图标使用应用级 DPR，缺少屏幕切换失效；
4. pt/px 混用；
5. 500/600 权重继续散落；
6. QSS、自绘、SVG 之间缺少统一 stroke/radius 语义。

### P2：维护性与持续回归风险

1. `AppTheme` 256 字段；
2. 445 个局部样式写入点；
3. 大量固定尺寸与字面量；
4. 架构测试断言实现关键字；
5. Qt5 兼容注释/分支残留在明确的 PySide6 项目中；
6. 缺少 100%～200% 和多显示器自动/人工验收矩阵。

## 10. 目标架构

### 10.1 Typography 单一来源

新建独立排版策略层，而不是继续把字体塞进颜色主题：

```python
UI_FONT_FAMILIES = (
    "Microsoft YaHei",
    "Microsoft YaHei UI",
    "Segoe UI",
)

BRAND_FONT_FAMILIES = (
    "Segoe UI",
    "Microsoft YaHei",
    "Microsoft YaHei UI",
)

MONO_FONT_FAMILIES = (
    "Consolas",
    "Cascadia Mono",
    "Microsoft YaHei",
)
```

规则：

- QApplication 设置 UI families；
- 普通 QSS 不写 `font-family`；
- 品牌与等宽角色使用 QFont API 明确覆盖；
- 所有覆盖都用 `setFamilies()`，不使用单一 `setFamily()`；
- CJK 只使用 400/700 视觉层级，500 仅作语义别名或取消；
- 提供生产与测试共用的 `apply_application_typography(app)`。

### 10.2 Surface 单一所有者

窗口、弹窗和卡片需要明确三层：

1. Window chrome：DWM 或自绘外壳二选一；
2. Surface：负责背景、圆角、边框；
3. Content：只负责内容布局，不重复绘制外壳圆角。

推荐优先试验：

- 移除根内容容器的 `QGraphicsDropShadowEffect`；
- Windows 11 优先使用 DWM 阴影/圆角，或使用独立 sibling/shadow window，不让阴影 effect 包裹内容子树；
- Card 默认无 graphics effect，阴影只给少量真正浮起的 overlay/modal；
- 删除 Panel、ScrollArea、viewport、detail container 的重复 shell radius；
- `RoundedSurfaceFrame` 修正 border inset，并定义是否负责 clip。

### 10.3 Stroke 与像素对齐契约

定义语义而不是散落小数：

```text
hairline       = 1 physical pixel
border         = round(1 logical px * DPR) physical pixels
focus border   = round(2 logical px * DPR) physical pixels
icon stroke    = 与 Lucide 2/24 比例一致
```

自绘 helper 应统一：

- 取得目标 paint device/window 的 DPR；
- 把物理宽度取整后换算回逻辑宽度；
- 根据物理笔宽奇偶对 centerline 做像素相位对齐；
- 小图标默认 RoundCap + RoundJoin；
- 圆角边框使用 `border_width / 2` inset；
- 轴对齐 hairline 与缩放图形分开处理。

### 10.4 DPR-aware 图标

- 图标渲染 API 接收目标 widget/window；
- 使用 `windowHandle().devicePixelRatio()` 或目标 screen DPR；
- 监听 `QEvent.DevicePixelRatioChange` / screen change；
- 按目标 DPR 失效缓存；
- 尽量保留 SVG 到 QIcon 的矢量渲染链，减少手工预栅格化。

### 10.5 主题拆分

将 `AppTheme` 拆为：

- `ColorScheme`：颜色；
- `TypographyScale`：字号、字重语义；
- `DensityScale`：间距与控件高度；
- `ShapeScale`：圆角、标准边框；
- 组件内部几何保留在组件 spec，不进入全局 theme。

主题切换只切颜色时，不应触发所有尺寸和字体策略重新定义。

## 11. 建议执行顺序

### Phase 0：建立可重复基线

1. 抽取生产字体初始化并用于 pytest fixture；
2. 建立 1.0、1.25、1.5、1.75、2.0 `QT_SCALE_FACTOR` 截图脚本；
3. 固定代表性页面：标题栏、方案页、主题页、弹窗、输入框、带阴影卡片；
4. 记录卡片内外同文本、1px/2px 圆角边框和 SVG/手绘箭头；
5. 增加双显示器 100% ↔ 175% 人工迁移用例。

### Phase 1：先拆 graphics effect

1. A/B 禁用根 `_container` 阴影；
2. A/B 禁用 `DesignSystemCard` 默认阴影；
3. 比较字体、线宽、圆角和性能；
4. 只保留浮层型组件的阴影；
5. 再决定使用 DWM 阴影还是独立阴影 surface。

这是最高收益阶段。未完成该阶段前，不建议大规模微调字体 hinting 或描边小数。

### Phase 2：字体链路统一

1. 引入 `TypographyPolicy`；
2. QApplication 使用 `setFamilies()`；
3. 删除普通控件 QSS `font-family`；
4. 修正品牌/中文 fallback；
5. 清理无效的 TitleBar mode `setFont()`；
6. 归一 400/700，处理所有硬编码 500/600。

### Phase 3：Surface 与 Stroke 统一

1. 修复 `RoundedSurfaceFrame` inset；
2. 建立 DPR-aware pen helper；
3. 统一 RoundCap/RoundJoin；
4. 删除嵌套 shell radius；
5. 明确 child background/clip 契约；
6. 迁移 ComboBox、SpinBox、radio、separator 和手绘箭头。

### Phase 4：图标与多显示器

1. 改为目标窗口 DPR；
2. DPR change 时失效缓存；
3. 验证 100% ↔ 175% 移动；
4. 检查图标逻辑尺寸、物理尺寸和 stroke 一致性。

### Phase 5：主题与样式治理

1. 拆分 256 字段主题对象；
2. 禁止业务页面新增裸 `font-size`、`font-weight`、`border-radius`、QPen width；
3. 把 445 个样式调用逐步收敛到组件级 style builder；
4. 将“源码包含某共享类”的测试替换为行为与渲染契约测试。

## 12. 验收矩阵

### 12.1 字体

- 普通中文 UI glyph 必须是 Microsoft YaHei；
- 品牌英文为 Segoe UI，混入中文时明确回退 Microsoft YaHei；
- 卡片内外相同文本的字体、字号、实际字重一致；
- 400、500、600、700 不再被错误当作四个可见层级；
- 生产和测试 `QApplication.font()` 一致。

### 12.2 边线与圆角

- 1px、2px 边框四边物理覆盖一致；
- 圆角上/下、左/右对称；
- focus 状态切换不发生几何抖动；
- 同一 chevron 在 ComboBox、SpinBox、分页等控件中 stroke/cap/join 一致；
- 子控件背景不覆盖父 surface 圆角。

### 12.3 缩放

- 100%、125%、150%、175%、200%；
- 正常窗口、最大化、弹窗、tooltip、toast；
- 单屏启动与跨屏移动；
- 页面滚动、主题切换和动态卡片刷新后保持一致。

### 12.4 性能

- 统计 graphics effect 数量；
- 卡片动态刷新时不重绘整个窗口子树；
- 主窗口移动和缩放无明显掉帧；
- 大量卡片页面内存和 repaint 次数可接受。

## 13. 不建议的快速修复

1. 不要把所有字体统一改成 `Microsoft YaHei UI`；
2. 不要只把 `font-weight: 600` 批量替换为 700 而不判断语义；
3. 不要继续为每个控件试出一个 1.5/1.6/1.7/1.8 的笔宽；
4. 不要只调 `PassThrough` 为 Round 就宣布修复；
5. 不要在父 surface 和所有子 viewport 上同时补相同圆角；
6. 不要给更多内容容器安装 `QGraphicsDropShadowEffect`；
7. 不要用 `setMask()` 作为第一方案解决抗锯齿圆角，整数 region mask 本身可能产生锯齿；
8. 不要继续用源码字符串测试代替真实字体、DPR 和像素行为测试。

## 14. 官方资料

- Qt `QFont` 字体匹配、families、fallback 与 hinting：<https://doc.qt.io/qt-6/qfont.html>
- Qt Style Sheet 优先级与 QWidget style wrapper：<https://doc.qt.io/qt-6/stylesheet.html>
- Qt 高 DPI 与测试环境变量：<https://doc.qt.io/qt-6.8/highdpi.html>
- Qt 6 迁移说明中关于 PassThrough 与非整数缩放 graphical glitches：<https://doc.qt.io/qt-6/portingguide.html>
- Qt `QGraphicsEffect` 中间渲染链：<https://doc.qt.io/qt-6/qgraphicseffect.html>
- Qt `QWidget.setGraphicsEffect()` 作用于控件及所有子控件：<https://doc.qt.io/qt-6.5/qwidget.html>
- Qt `QPen` 默认 SquareCap / BevelJoin、cosmetic pen：<https://doc.qt.io/qt-6.8/qpen.html>
- Microsoft YaHei / Microsoft YaHei UI 字体与可用系统：<https://learn.microsoft.com/en-us/typography/font-list/microsoft-yahei>

## 15. 第一阶段执行结果（2026-07-12）

已落地：

1. 新增 `src/shared/ui/typography_policy.py`（此处记录第一阶段当时的状态，字体链与 hinting 已在第二阶段纠正）：
   - 第一阶段 UI 字体链曾设为 Microsoft YaHei → Microsoft YaHei UI → Segoe UI；
   - 品牌字体链固定为 Segoe UI → Microsoft YaHei → Microsoft YaHei UI；
   - QApplication 使用整数 13px；
   - 生产启动和 pytest session 复用同一初始化函数。
2. 普通共享输入框、ComboBox、SpinBox、弹窗消息不再由 QSS 重复声明默认字体家族；特殊等宽输入仍允许显式 override。
3. 微软雅黑 `font_weight_medium` 收敛到 400，清除 UI 源码中的硬编码 500/600，强调统一使用语义 700 token。
4. 主窗口阴影 effect 从内容 `_container` 移到无内容的 `_shadow_surface` 同级背景层；运行时确认内容容器 `graphicsEffect() is None`。
5. `DesignSystemCard`、`SummaryGrid` 和 `SegmentedControl` 不再给包含文字的持久内容控件安装 graphics effect。
6. 新增 `paint_geometry.py`：
   - 设计 token 保持整数逻辑宽度；
   - 在 painter 边界把描边换算为整数物理像素；
   - 统一 RoundCap / RoundJoin；
   - 分数只存在于底层换算，不进入主题、QSS 或业务层。
7. `RoundedSurfaceFrame`：
   - border inset 改为实际渲染宽度的一半；
   - fill 与 border 使用独立路径；
   - 2px/3px 边框不再固定按 0.5px 内缩；
   - 修正文档中对子控件 QSS 背景 clip 能力的错误承诺。
8. 输入框边框、分隔线、ComboBox/SpinBox chevron、radio 和 dashed separator 接入统一描边 helper。
9. 图标从“启动屏幕单 DPR 位图”改为内含 1.0/1.25/1.5/1.75/2.0/2.5/3.0 多 DPR pixmap 的 QIcon；175% 请求实测得到 35×35 物理像素、20px 逻辑尺寸。
10. 删除 PySide6 项目中已冗余的 Qt5 high-DPI attribute 分支，保留明确的 PassThrough 策略。

新增守卫：

- 禁止 UI 源码重新引入浮点 `font-size`；
- 禁止硬编码 `font-weight: 500/600`；
- 断言生产和测试使用相同字体；
- 断言 1px 在 DPR 1.75 下映射为 2 个物理像素；
- 断言内容 Card 不带 graphics effect；
- 断言主窗口阴影只挂在背景 sibling；
- 断言图标目录不再读取 application DPR。

验证：

- 针对性 UI/字体/圆角/输入/ComboBox 测试：56 passed；
- 扩大 UI/主题/布局分组：283 passed，6 failed；
- 6 个失败均来自当前工作树中与本次渲染修复无关的既有状态：模板面板图标源码断言、3 个 scene release gate、1 个 scene dashboard 维度数据、1 个图片面板固定高度守卫；
- 全量 pytest 在 304 秒命令上限到达前未完成，不能记为通过或失败；
- 修改文件 `compileall` 通过；
- `git diff --check` 通过；
- 当前环境未安装 Ruff，因此未执行 Ruff 检查。

尚未伪装成“已经完成”的部分：

- 121 个文件中的页面级 QSS 尚未全部迁移；
- Window/TitleBar/Sidebar/Panel 的重复外壳圆角仍需在建立单一 chrome painter 后删除；
- TemplateStylePreview、Toast、Tooltip 等允许型浮层 effect 尚需按组件角色复核；
- 100%～200% 五倍率真实截图基线与跨屏自动化仍需继续建设。

## 16. 最终判断

当前字体显示、线宽与圆角问题是系统性渲染架构问题，优先级不应再按“哪个控件最难看”排序，而应按渲染链上游排序：

```text
graphics effect / window shell
  -> font authority / surface ownership
  -> DPR-aware stroke / icon
  -> component migration
  -> page-level cleanup
```

最关键的第一步不是更换微软雅黑，也不是立刻改变 Windows 缩放策略，而是移除包裹内容子树的阴影效果并建立真实缩放基线。只有先让文字、边线和圆角回到直接且单一的绘制路径，后续字体、hinting、描边和圆角参数调整才具有稳定意义。

## 17. 第一阶段回归发现：`标题编号` 字形仍不自然（2026-07-12）

### 17.1 截图定位

用户回传截图中的背景主色为 `#EDF0F8`，文字主色为 `#1E293B`。这两个值分别对应 `AppTheme.bg_hover` 和 `AppTheme.text_primary`，因此可排除 20px/700 的详情摘要标题，实际来源是左侧 `NavigationCard` 的悬停态标题：

- `src/shared/ui/navigation_card.py`；
- 13px（`font_size_md`）；
- 400（`font_weight_normal`）；
- Microsoft YaHei；
- 继承应用字体上的 `PreferFullHinting`；
- 卡片当前没有 graphics effect，故本例不是阴影中间纹理导致的二次采样。

### 17.2 像素级复现结果

在当前 Windows 屏幕 DPR 1.75 下，对同一文本、字号、颜色和背景进行了原生 Qt A/B 栅格化：

| 模式 | 字形物理包围盒 | 非背景像素 | 完全实色像素 | 观察 |
|---|---:|---:|---:|---|
| `PreferDefaultHinting` | 92×22 | 1068 | 404 | 笔画较自然，转角更平滑 |
| `PreferNoHinting` | 92×23 | 1330 | 200 | 灰阶过渡更多，但整体略虚 |
| `PreferFullHinting` | 92×24 | 1141 | 462 | 笔画被强制加重，局部转角和横竖比例不自然 |

回传截图的主要颜色计数、92×24 包围盒和字形高度与 `PreferFullHinting` 输出一致。截图中橙色、蓝色边缘是 Windows ClearType 子像素分量，不是 PNG 压缩噪声。

结论：第一阶段把 `PreferFullHinting` 设成全局字体契约是错误的。它确实能增强部分小字号笔画，但在 175% 等非整数缩放下也会强制调整轮廓，使同一字号出现更粗的实色覆盖、更高的物理包围盒以及不自然的转角。本例说明“统一强制 Full Hinting”不能作为清晰度修复。

### 17.3 字体栈仍有结构问题

当前普通 UI 字体链为：

```text
Microsoft YaHei -> Microsoft YaHei UI -> Segoe UI
```

混排实测表明，这个顺序让中文和西文 7 个 glyph 全部由 Microsoft YaHei 处理，Segoe UI 实际不会承载普通 UI 的西文。更合理的 Windows UI 顺序应是：

```text
Segoe UI -> Microsoft YaHei UI -> Microsoft YaHei
```

该顺序下，`A1` 等西文/数字由 Segoe UI 渲染，4 个中文字形由 Microsoft YaHei UI 显式回退。Microsoft YaHei 与 Microsoft YaHei UI 的同尺寸中文轮廓在本机实测相同，UI 变体主要改变垂直 metrics；所以仅交换 YaHei/YaHei UI 不能修复本截图的笔画问题，但可以修正混排链路和行高语义。

### 17.4 语义字号没有真正单一来源

目前存在两个看似统一、实际可独立漂移的来源：

1. `typography_policy.py::TypographyScale`；
2. `theme.py::font_size_xs/sm/md/lg/xl/xxl`。

`NavigationCard` 又直接把通用 `font_size_md=13` 当作导航标题。换言之，系统统一了数值，却没有统一“这个文字是什么角色”。这会继续产生页面标题、卡片标题、导航标题各自临时挑选 `md/lg/xl` 的问题。

建议最终收敛为语义角色，例如 `body`、`caption`、`navigation_title`、`section_title`、`page_title`，由一个 typography registry 同时提供 families、pixel size、weight 和 hinting。控件调用 `apply_text_role()`，QSS 只负责颜色、背景和边框，不再分散声明 `font-size` / `font-weight`。

### 17.5 下一阶段修复优先级

1. 删除全局 `PreferFullHinting`，恢复 `PreferDefaultHinting`，不要改成全局 `PreferNoHinting`；
2. 把普通 UI 字体链改为 Segoe UI → Microsoft YaHei UI → Microsoft YaHei；
3. 为导航标题建立显式语义 role，并 A/B 13px 与 14px；初步结果显示 14px/default 为 99×24 物理包围盒，比 13px/full 的“同高强行加粗”更自然；
4. 导航卡片普通、hover、selected 状态保持同一字号和字重，只通过颜色、背景和图标表达状态，避免 400→700 引起字面密度跳变；
5. 建立 100%/125%/150%/175%/200% 的真实字形截图基线，至少覆盖中文、英文、数字和中西混排；
6. 增加守卫：应用字体不得强制 Full Hinting，普通 UI 的首选西文字体为 Segoe UI，中文 glyph run 必须明确落到 YaHei UI/YaHei，语义字体角色不得回退为任意页面级数值。

### 17.6 关于 `13.87px`

不应按 DPR 动态反算并取整字体字号。13px 逻辑字号在 DPR 1.75 下自然对应 22.75 个物理像素，这属于绘制边界的正常分数映射，不等于业务层出现 13.87px。真正需要禁止的是 point size、DPI、DPR 和 QSS 多次换算后把分数字号重新写回控件。应用层继续只存整数逻辑 pixel size，由系统默认 hinting 和字体栅格器处理物理像素覆盖。

## 18. 第二阶段执行结果：语义字体与原生 Hinting（2026-07-12）

已执行：

1. 删除 `build_font()` 中的全局 `PreferFullHinting`，所有应用字体恢复 Qt/Windows 原生 `PreferDefaultHinting`；
2. 普通 UI 与品牌字体链统一为 Segoe UI → Microsoft YaHei UI → Microsoft YaHei；
3. 新增 `TextRole`、`TypographySpec`、`TYPOGRAPHY_ROLES`、`font_for_role()` 和 `apply_text_role()`；
4. `TypographyScale` 增加 11px micro 与 14px navigation title，主题原有 xs～xxl 兼容字段全部从该 scale 派生，不再维护第二套数字；
5. `NavigationCard` 标题从页面 QSS 的 13px 和状态相关 400/700，迁移为 `NAVIGATION_TITLE` 的固定 14px/400；hover/selected 只改变颜色、背景和图标；
6. 标题 QSS 不再声明字号与字重，因此不会与 `QFont` 语义角色形成双重 authority；
7. Windows 文本渲染守则同步加入原生 hinting、混排 glyph run 和交互态字重稳定性检查。
8. `build_font()` 对分数字号直接抛出 `TypeError`、对非正字号抛出 `ValueError`，不再用 `int()` 静默吞掉 13.87px 一类错误输入。

原生 175% 运行时复核：

```text
application font: Segoe UI -> Microsoft YaHei UI -> Microsoft YaHei
application size/weight/hinting: 13px / 400 / PreferDefaultHinting
navigation title: 14px / 400 / PreferDefaultHinting
"标题编号 A1" glyph runs: Microsoft YaHei UI=4, Segoe UI=3
```

这说明字体家族列表、中文实际 fallback、西文字形、语义字号和 hinting 已按同一链路生效，而不是只修改了源码字符串。

## 19. 第二阶段回归反证：问题主体不是字体，而是 Tooltip 覆盖（2026-07-12）

### 19.1 必须撤回的错误判断

第二阶段存在三个方法论错误：

1. 把“交互态不应随机改变排版”误解成“选中态不能加粗”，删除了产品原有的 selected=700 强调；
2. 在排查 hinting 时同时把导航标题从 13px 改为 14px，无法再进行单变量归因；
3. 只验证单个 QLabel，没有验证 Tooltip 打开时的完整导航列表和浮层 z-order。

因此，第二阶段“导航标题固定 14px/400”不是最终契约，必须纠正。

### 19.2 新截图的像素级证据

截图尺寸为 188×211 物理像素，屏幕 DPR 为 1.75。无遮挡的“正文排版”约为 98×24，符合当前 14px/400 的实际输出。

“标题编号”的异常集中在后两个字，且与右上白色 Tooltip 的阴影区域完全重合：

| 区域 | 空白背景 | 比声明前景 `#1E293B` 更暗的像素 |
|---|---:|---:|
| “正文排版”四字 | `#FFFFFF` | 0 |
| “标” | `#FFFFFF` | 0 |
| “题” | `#FFFFFF` | 0 |
| “编” | 阴影渐变 | 95 |
| “号” | 阴影渐变 | 146 |

阴影最重处把白底压到约 `#E6E6E6`，相当于约 9.8% 黑色覆盖。相同覆盖作用到文字核心色：

```text
#1E293B × 0.902 ≈ #1B2535
```

截图中“编号”的最暗核心像素恰为 `#1B2535`。字体栅格器不会把不透明前景画得比声明前景更暗；这个结果只能来自文字绘制完成后又被上层阴影合成。

结论：截图中最严重的“后两字逐渐加粗、发黑”不是字体字重随机变化，而是 Tooltip 窗口及其阴影覆盖了下一张导航卡片。

### 19.3 Tooltip 架构确实存在双链

`NavigationCard.set_subtitle()` 直接调用 `_subtitle.setToolTip()`。项目的 `GlobalTooltipController` 只接管带 `_alavette_tooltip_enabled=True` 私有属性的控件，因此该导航摘要继续走 Qt 原生 QToolTip：

```text
NavigationCard.setToolTip
  -> native QToolTip（白底、系统阴影、跟随鼠标）
  -> 阴影落到下一张卡片标题
```

而显式调用 `set_global_tooltip()` 的少数控件走另一条链。当前 `src` 中约有 154 处直接 `.setToolTip(`，生产代码中显式 `set_global_tooltip(` 只有少数调用；测试甚至主动断言普通 tooltip 不应被全局控制器接管。所谓“全局 Tooltip”目前名不副实。

此外，现有自定义 Tooltip 自身也同时存在两层 effect：

1. 含 QLabel 子控件的 `_surface` 挂 `QGraphicsDropShadowEffect`；
2. 整个 popup 再挂 `QGraphicsOpacityEffect` 做淡入。

即使把 NavigationCard 简单迁移过去，Tooltip 自己的文字仍会经过两次离屏合成。修复必须先清理 Tooltip painter/effect ownership，不能只替换一个 API 名称。

### 19.4 选中加粗丢失是确定性代码回归

当前 `NAVIGATION_TITLE` 固定为 400，selected 只改变背景和文字颜色；测试和守则还错误地锁定了“selected 前后同权重”。这与用户原始交互契约相反。

正确模型应是两个明确语义状态，并继续通过 QFont API 应用，而不是把 weight 塞回 QSS：

```text
NAVIGATION_TITLE         = 13px / 400
NAVIGATION_TITLE_ACTIVE  = 13px / 700
```

hover 保持 400，selected 使用真实 Bold 700。175% 实测两者物理包围盒均为约 92×22，中文占位几何不变，只有墨量和真实字重改变，因此可以恢复强调而不引入标题位置抖动。

### 19.5 普通 UI 与品牌字体不能共用一条万能栈

Segoe-first 适合品牌英文，但不适合作为中文主导界面的唯一默认栈。当前普通 UI 的 Segoe-first 方案使中文标题由 Microsoft YaHei UI fallback，而 QFont 的首选 metrics 来自 Segoe UI；混合摘要还会拆成 Segoe 与 YaHei UI 两个 glyph run。

最小回归且保持既有 line metrics 的角色化方案是：

```text
CJK_UI_FONT_FAMILIES   = Microsoft YaHei -> Microsoft YaHei UI -> Segoe UI
LATIN_UI_FONT_FAMILIES = Segoe UI -> Microsoft YaHei -> Microsoft YaHei UI
BRAND_FONT_FAMILIES    = LATIN_UI_FONT_FAMILIES
```

Microsoft YaHei-primary 在本机 12/13/14px 的 line metrics 与当前 Segoe-primary 一致，同时中西混排可保持单一 YaHei glyph run；Microsoft YaHei UI-primary 会让相同字号的 line box 再缩短 1 个逻辑像素，本轮没有必要引入该额外布局变量。品牌标题和明确纯西文角色继续使用 Segoe-first。

### 19.6 字号与 font engine 对照结论

- 原 13px + 默认 hinting：“标题编号”约 92×22；
- 当前 14px + 默认 hinting：约 99×24，标题和卡片节奏都被放大；
- 13px/700 与 13px/400 的中文包围盒相同，可安全恢复 selected emphasis；
- `NoSubpixelAntialias` 在当前 Windows/PySide6 后端实测与默认输出逐像素相同，不能作为可靠修复；
- `NoAntialias` 会产生硬锯齿，不可用；
- Windows QPA 的 FreeType font engine 能产生更均匀的灰阶轮廓，但会改变 Bold CJK 与 Latin advance，属于全局排版引擎迁移，必须经过完整截图和换行回归，不能作为局部热修复；
- 不应做 DPR 反算、分数逻辑字号或 baseline snapping。

### 19.7 真正收敛的执行顺序

1. 回退导航标题 14px，恢复明确的 13px normal/active 两个语义角色；
2. 普通中文 UI 恢复 CJK-first，品牌/明确 Latin 角色保持 Segoe-first；
3. Tooltip controller 默认接管所有非空 `widget.toolTip()`，仅显式 opt-out 才允许原生 tooltip，删除当前双链测试契约；
4. 自定义 Tooltip 移除包裹文字的 DropShadowEffect 与 OpacityEffect；优先无阴影直接显示，若保留 elevation，只允许背景 sibling 拥有效果；
5. NavigationCard 仅在摘要实际发生 elide 时提供 tooltip，role=nav，优先放在导航栏右侧；定位测试必须断言 popup/shadow 不与下一卡标题相交；
6. QSS 继续只管理颜色和表面，字号、家族、字重全部由语义 QFont role 提供；
7. 建立三类截图基线：无 Tooltip、Tooltip 展开、selected/hover 切换；每类覆盖 100/125/150/175/200%；
8. 增加运行时 glyph-run 守卫：普通中西混排 UI 使用 CJK-primary 单 run，品牌英文使用 Segoe，中文 fallback 明确可控。

这一路径保留整数逻辑字号与 PassThrough，不再把浮层合成、字体匹配、字号重设计和交互语义混成一次修改。

## 20. 第三阶段执行结果：按反证修复 Tooltip、状态字体与角色栈（2026-07-12）

### 20.1 已落地实现

1. 普通 UI 字体恢复 CJK-first：Microsoft YaHei → Microsoft YaHei UI → Segoe UI；
2. 新增独立 Latin/brand 栈：Segoe UI → Microsoft YaHei → Microsoft YaHei UI；
3. `NAVIGATION_TITLE` 恢复 13px/400，并新增 `NAVIGATION_TITLE_ACTIVE` 13px/700；
4. NavigationCard selected 通过 `apply_text_role()` 切换真实 Bold，hover 继续保持 Regular；
5. 导航摘要迁移到 Caption 12px/400 语义 QFont，标题和摘要 QSS 均不再声明字号与字重；
6. 摘要只有实际发生中间省略时才保留完整 tooltip，扩宽恢复全文后立即清空 tooltip；
7. 导航 tooltip 明确使用 role=nav、placement=right，不再出现在下一卡标题上方；
8. `GlobalTooltipController` 默认接管所有非空 `QWidget.toolTip()`，只有显式 `disable_global_tooltip()` 才允许原生平台 tooltip；
9. TooltipPopup 删除包含文字 surface 上的 DropShadowEffect，也删除整个 popup 上的 OpacityEffect；popup、surface、label 的 graphicsEffect 均为空；
10. Tooltip label 使用 Caption 语义字体和 PlainText，长文本限制在 360px 后换行，QSS 只负责颜色、边框和圆角；
11. 显式 right placement 的 fallback 顺序调整为 right → left → top → bottom，只有前三者都无法容纳时才落到下方。

### 20.2 175% Windows 原生验证

```text
DPR: 1.75
application font: Microsoft YaHei -> Microsoft YaHei UI -> Segoe UI
application role: 13px / 400 / PreferDefaultHinting
ordinary UI "标题 A1": Microsoft YaHei Regular, 1 glyph run
brand "Alavette 标题": Segoe UI + Microsoft YaHei fallback
initial navigation weights: selected=700, idle=400
after selection switch: old=400, new=700
selected "标题编号": Microsoft YaHei Bold, 1 glyph run
tooltip: role=nav, placement=right, delay=80ms
tooltip intersects next title: false
popup/surface/label graphicsEffect: None / None / None
```

原生截图中 Tooltip 位于导航摘要右侧；selected 标题恢复粗体；Tooltip 及其窗口范围不再覆盖下一张卡片标题。

### 20.3 守卫与验证

- 普通 `widget.setToolTip()` 默认被共享 controller 拦截，原生 tooltip 必须显式 opt-out；
- 导航窄宽时 tooltip 保存完整摘要，扩宽后 tooltip 清空；
- popup 不含包裹文字的 graphics effect，label 固定 Caption 12px/400；
- 导航 idle/hover 为 13px/400，selected 为 13px/700，families、size、hinting 保持一致；
- DynamicNavigationRail 首卡自动选中及后续切换均验证 400/700 正确转移；
- 右侧 Tooltip 几何不与下一标题矩形相交；
- 普通 UI 和品牌字体栈由独立测试固定；
- offscreen 常规分组 74 passed、1 个原生 glyph-run 测试按设计 skipped；
- 同一 glyph-run 测试在 Windows 原生 backend 单独执行：1 passed。

这一阶段修复的是已经由像素证据确认的合成和状态链问题，没有改变 PassThrough、没有引入分数字号、没有切换全局 font engine，也没有做 DPR 反算或 baseline snapping。

## 21. 第四次回归分析：常态文字的 DirectWrite 子像素相位（2026-07-12）

### 21.1 “固定值”链路没有再次串错

截图文字来自标题编号面板的行距类型 `StyledComboBox`。运行时最终状态：

```text
DPR: 1.75
font: Microsoft YaHei Regular
logical size / weight: 13px / 400
hinting: PreferDefaultHinting
glyph run: Microsoft YaHei, single run
state: enabled / non-focus / popup hidden / non-editable
ancestor graphics effects: all None
ancestor opacity: all 1.0
```

StyledComboBox 不调用 `super().paintEvent()` 绘制当前值，而是在自己的 `paintEvent()` 中先画输入表面，再由 `_paint_current_text()` 使用 `self.font()` 和 `QPainter.drawText()` 直接绘制一次。因此本例不存在 native QComboBox 与自绘文字叠加。

截图背景为纯 `#FFFFFF`，前景为 `#1E293B`；不存在比声明前景更暗的像素，27 种抗锯齿颜色全部位于前景到白色背景的单次 ClearType 插值范围。没有 Tooltip、阴影、opacity、graphics effect、二次缩放或字体 fallback 证据。

将截图与本机生产 StyledComboBox 在相同子像素相位下归一比较，78×32 patch 的 2496/2496 个像素完全一致。这说明用户看到的是当前 Windows 字体后端的预期输出，而不是另一条遗漏的 UI 绘制链。

### 21.2 真正根因：13×1.75=22.75

13px 全角 CJK glyph 的逻辑 advance 为 13px，在 175% 下变成 22.75 个物理像素。连续汉字的起点相位按以下顺序轮转：

```text
P -> P+0.75 -> P+0.50 -> P+0.25 -> P
```

同一窗口内，将完全相同的“固定值”ComboBox 只水平移动 1 个逻辑像素，得到：

| 起始物理相位 | 非白 footprint | 完全前景 core | 归一总墨量 | 彩色子像素 |
|---:|---:|---:|---:|---:|
| 0.00 | 749 | 385 | 552.79 | 363 |
| 0.75 | 758 | 331 | 552.89 | 426 |
| 0.50 | 816 | 314 | 553.10 | 502 |
| 0.25 | 767 | 328 | 552.97 | 439 |

总墨量差异小于 0.06%，说明字体真实设计字重没有改变；但完全前景 core 相差 22.6%，彩色 fringe 的分配也显著不同，所以人眼会感到线宽、转角和彩边不一致。用户截图的 core=331 及调色板与 0.75 相位精确匹配。

这也解释了为什么：

- `Microsoft YaHei` 与 `Microsoft YaHei UI` 互换无效：本机同字号中文 outline 像素相同；
- `NoSubpixelAntialias` 无效：当前 Windows Qt 后端实测逐像素不变；
- `PreferNoHinting` 仍随相位变化且更虚；
- `PreferFullHinting` 能让四相位一致，但总墨量明显增加、转角变硬，正是第一张截图已经否决的视觉结果。

### 21.3 两条真实可行路线

#### 路线 A：保留 DirectWrite，接受系统 ClearType 边界

可做的工程收敛：

1. compact control 可 A/B 12px；12×1.75=21，连续全角 CJK 字符不再发生 glyph 间相位轮转；
2. 关键自绘控件可以在 paint boundary 把 text origin 对齐到统一物理相位；
3. StyledComboBox 移除 QSS `font-size`，只应用语义 QFont role；
4. 继续建立多 DPR 截图基线。

边界：12px 只能稳定连续全角 CJK advance，不能保证不同控件的起始相位，也不能保证任意 Latin glyph；origin snapping 只覆盖自绘控件，QLabel/QLineEdit 仍由 DirectWrite 控制。若要求所有原生文本逐像素一致，就必须接管所有文字绘制，代价大且会伤害 IME、选择、无障碍和平台行为，不建议。

#### 路线 B：Windows 全局使用 Qt FreeType font engine

同一“固定值”四相位实测：

```text
footprint: 883 / 883 / 883 / 883
core:      194 / 194 / 194 / 194
ink:       554.50 / 554.50 / 554.50 / 554.50
colored:   0 / 0 / 0 / 0
```

Latin `Fixed A1` 的四相位也逐项完全一致。FreeType 保留 13px 设计尺寸，使用稳定灰阶抗锯齿，不需要把所有 QLabel、QLineEdit 和 ComboBox 改成自绘。

代价：这是全局字体后端迁移。Regular “固定值”的 advance 仍为 39 逻辑像素，但部分 Bold CJK/Latin advance 会增加，例如 13px 的四字粗体可由 52 变为 56 逻辑像素，因此必须检查按钮宽度、selected 导航、elide、换行和固定宽布局。

当前验证：在 `windows:fontengine=freetype` 原生 backend 下，Combo、输入、导航、UI rendering、small-widget 和 workbench layout 相关测试 116 passed；尚未完成 100/125/150/175/200% 全窗口截图矩阵，因此不能直接宣告生产切换完成。

### 21.4 是否需要大规模重构

结论分开看：

- 为解决本截图的线宽/彩边问题：不需要先大规模重构控件；优先做可回退的 FreeType backend A/B 和全倍率视觉验收。
- 为清理字体架构：需要中型、分阶段 typography migration，但它不是本截图的直接修复。

当前源码盘点：

```text
含 font-size QSS 的文件: 85
含 font-weight QSS 的文件: 60
含 font-family QSS 的文件: 4
自定义 drawText 文件: 7
直接 setFont 文件: 10
实际 apply_text_role 调用点: 5（不含 helper 自身）
```

StyledComboBox 当前同时存在 QApplication 13px、组件 QSS 13px、custom painter 读取 `self.font()` 三层 authority；运行时三者恰好一致，所以不是本图根因，但长期应迁移为单一 semantic role。

建议决策顺序：

1. 增加启动前可配置的 DirectWrite/FreeType backend 开关，切换必须重启；
2. 生成 100/125/150/175/200% 的主要页面 A/B 截图；
3. 对比常态文本、真实 Bold、Latin/CJK 混排、换行与 elide；
4. 若 FreeType 视觉验收通过，再设为 Windows 默认并保留 DirectWrite 回退；
5. 独立推进 85 个文件的语义字体迁移，不把它作为 backend 切换的前置条件。

因此，“彻底解决视觉相位”更像一次受控的渲染后端迁移；“彻底清理字体代码”才是中型架构重构。两者必须拆开实施。

## 22. 第五阶段执行完成：后端迁移、真实字重与输入字体权威收敛（2026-07-12）

### 22.1 启动链按 Qt 官方参数语法重写

最终生产默认采用 FreeType，同时保留 DirectWrite 和 system 两条重启级回退：

```text
默认                 -> windows:fontengine=freetype
--font-engine directwrite -> 删除 fontengine，使用 Windows 原生默认
--font-engine system      -> 不改写宿主已有 QPA 配置
```

Qt 的 Windows platform 参数语法是 `windows:key=value,key=value`。早期实现把多个参数串成重复冒号，并尝试写入未受支持的 `fontengine=directwrite`；这两点已经纠正。现在会：

1. 使用逗号序列化多个 QPA option；
2. FreeType 只写入官方支持的 `fontengine=freetype`；
3. DirectWrite 删除 `fontengine` 与冲突的 `nodirectwrite`；
4. 兼容并自动清理短期版本曾写出的 `:fontengine=directwrite`；
5. 保留 `darkmode`、`nocolorfonts` 等无冲突 option；
6. 不覆盖 offscreen、minimal、非 Windows 或显式选择的其他 QPA plugin。

优先级为命令行 → `ALAVETTE_FORM_FONT_ENGINE` → 已有 Windows fontengine → 生产默认。源代码入口在导入 `src.qt_api` 前执行；PyInstaller runtime hook 会在冻结应用加载 Qt 前读取同一个命令行 option，因此不存在“先注入 FreeType、main 再撤销”的双阶段状态。Windows 两个启动 bat 均透传 `%*`。

### 22.2 FreeType 的真正深层兼容：微软雅黑 TTC 字重映射

完整矩阵第一次运行暴露出一个不能忽略的回归：未注册系统 TTC 时，Qt FreeType 能绘制 `Microsoft YaHei` Regular，却没有把英文 family name 正确关联到 Bold face：

```text
DirectWrite 13px/700: Microsoft YaHei Bold，四字 advance=52
FreeType   13px/700: Microsoft YaHei Regular + synthetic bold，advance=56
```

这会让 selected 状态变宽 7.69%，可能触发 elide、按钮裁切和换行。修复不是降低字重，也不是补偿宽度，而是在 `QApplication` 创建后、应用字体与任何 UI 模块导入前，把 Windows 已安装的三个 TTC 注册为 application fonts：

```text
%WINDIR%/Fonts/msyh.ttc
%WINDIR%/Fonts/msyhbd.ttc
%WINDIR%/Fonts/msyhl.ttc
```

字体文件只从操作系统读取，不进入仓库或安装包。注册后 FreeType 与 DirectWrite 都解析为 `Microsoft YaHei Bold`，13px 四字 advance 同为 52；Regular 三字“固定值”同为 39。这样保留了选中加粗，又消除了合成粗体导致的布局漂移。

启动前还会纯文件系统预检这三个 TTC；任一缺失时，在导入 PySide6 前自动撤销 FreeType 参数并回退 DirectWrite。这样精简版/定制 Windows 不会静默进入合成粗体状态。

### 22.3 “固定值”与共享输入链已成为单一字体权威

当前高频输入契约：

```text
QApplication BODY       13px / 400 / CJK-first
StyledComboBox          TextRole.BODY
Combo editable editor   同一 TextRole.BODY
Combo popup view/delegate 同一 QFont
StyledSpinBox/editor    TextRole.BODY
shared QLineEdit helper TextRole.BODY
QSS                     仅表面、颜色、padding、selection，不声明默认字体
```

真实 `StyleDetail` 中显示“固定值”的 `_line_type_combo` 已有运行时回归测试，确认本体和 popup 都是 CJK-first、13px、400，且三项字体 QSS 均为空。静态守卫同时禁止 `QLineEdit/QComboBox/QSpinBox/QDoubleSpinBox` 类型选择器重新声明 `font-size/font-weight/font-family`，并对 input helper 的特殊逃逸调用做精确白名单。

这意味着这张截图已经没有 application font、父级 QSS、组件 QSS、editor、popup、delegate 之间的随机竞争。自绘 Combo 只读取 `self.font()` 一次。

### 22.4 最终 2×5 原生矩阵：解决了什么，仍不能承诺什么

最终矩阵实际执行 DirectWrite/FreeType × 100/125/150/175/200%，共 10 个独立 Windows Qt 进程、40 个文本样本、160 个起始相位。产物：

```text
scripts/audit_windows_font_matrix.py
output/audits/windows_font_matrix_2026-07-12/
  10 PNG + 10 cell JSON + matrix.json + summary.md
```

完整矩阵汇总：

| 后端 | 样本 | 跨四相位逐像素一致 | 几何一致 | 分布指标一致 | 彩色子像素 |
|---|---:|---:|---:|---:|---:|
| DirectWrite | 20 | 8 | 15 | 8 | 42180 |
| FreeType | 20 | 8 | 12 | 10 | 0 |

175% 下更直接的视觉指标：

| 文本 | 后端 | footprint | 完全前景 core | 彩色子像素 |
|---|---|---|---|---|
| 固定值 Regular | DirectWrite | 749–816 | 314–385 | 363–502 |
| 固定值 Regular | FreeType | 889–889 | 247–247 | 0 |
| 标题编号 Regular | DirectWrite | 1060–1082 | 370–404 | 663–709 |
| 标题编号 Regular | FreeType | 1232–1233 | 309–309 | 0 |
| 标题编号 Bold | DirectWrite | 1400–1417 | 804–820 | 579–607 |
| 标题编号 Bold | FreeType | 1594–1597 | 766–766 | 0 |

因此最终结论必须精确表达：FreeType 消除了用户最敏感的 ClearType 彩边机制，并在 175% 保持 core 墨量稳定；它没有让所有分数起点逐像素相同，bbox 仍可能因灰度覆盖跨过阈值而差 1 个物理像素。后者是分数缩放采样边界，不应再用 13.87px、DPR 反算、Full Hinting 或全面自绘去“修平”。

### 22.5 防止 13.87px 与链路再次发散

1. `build_font()` 只接受正整数 logical pixel，bool、float、零和负数全部拒绝；
2. `TypographyScale` 是语义字号唯一来源；theme 的旧尺寸名只是兼容映射；
3. DPR 只允许进入图片、stroke 和 paint geometry 边界，禁止乘进字体；
4. QApplication 使用 PassThrough，禁止通过 rounding policy 隐式改字号；
5. 输入控件字体由 QFont role 控制，QSS 字体声明有静态守卫；
6. backend 只在 QApplication 前选择，运行中不允许切换；
7. 真实 glyph-run 测试同时固定 CJK Regular、品牌 Latin/fallback 和 CJK Bold face；
8. 视觉矩阵把像素一致、几何一致、分布一致和彩色 fringe 分开记录，禁止用单一截图宣称“完全一致”。

### 22.6 验收结果与架构边界

- 原生 DirectWrite 核心组：187 passed；布局/主题/Workbench 广组：302 passed（排除 2 个已确认独立问题）；
- 原生 FreeType 高价值字体/输入/导航组：修复 TTC 映射后 112 passed；此前扩大组除 family 本地化 alias 契约外无布局失败，该 alias 也随 TTC 映射修复；
- Combo/Input 语义字体专项：120 passed、1 skipped；
- 字体矩阵契约：5 passed，10/10 原生 cell 完成；
- PyInstaller 实际构建成功，日志确认 custom runtime hook 先于 Qt runtime hook 收集；冻结 GUI offscreen 启动 smoke 成功；
- 已知失败仍是图片 presenter 的既有 fixedHeight 守卫、测试用非 QWidget 替换 panel stack 导致的 native 生命周期崩溃、以及个别 native clipboard 测试前置条件，均与字体链无关。

不需要为这次常态文字问题大规模重写 QLabel/QLineEdit/IME/无障碍链。真正应该持续迁移的是剩余展示型 label 的语义 role；本次已经把会直接影响输入、选择、popup 和截图问题的高频边界收敛，并用静态守卫阻止这些边界重新退化。生产默认、回退、打包、真实字重、输入权威、五档矩阵与文档现已形成一条闭环。
