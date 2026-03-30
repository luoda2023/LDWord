# 项目级可复用 Themed Selection Controls 设计

- 日期：2026-03-28
- 决策：采用方案 B
- 范围：构建项目级可复用的自绘选择控件体系，第一阶段覆盖 Radio / Slider
- 目标：彻底摆脱 Qt 原生 QSS 子控件几何的不稳定性，同时保持接近原生 Qt 的 API 和工程接入方式

---

> [!IMPORTANT]
> **Implementation status update (2026-03-28):**
> - Runtime code has already switched the gallery onto `ThemedRadioButton` / `ThemedSlider`.
> - The old merged shared stylesheet path is no longer the active Radio route.
> - `src/shared/ui/selection_control_style.py` now remains as a Checkbox-only helper via `build_checkbox_stylesheet()`.

## 1. 背景

当前项目里的两个视觉问题都不是简单的“圆角数值调错了”，而是更底层的结构性问题：

1. `QRadioButton::indicator` 的 `width/height/border-radius` 由 QSS 书写，但 Qt 最终绘制的外轮廓会把边框算进去，导致“内容框尺寸”和“最终外轮廓尺寸”不一致。
2. `QSlider::handle:horizontal` 的最终几何并不完全受 `width/height` 控制，而会被 groove、margin、style 子控件规则共同影响，因此视觉上容易变成椭圆或胶囊。
3. 当前测试只验证 QSS 字符串存在，不验证 Qt 最终实际分配和绘制出的几何，导致“测试全绿但视觉依然错误”。

这说明问题根因不是页面布局、不是当前主题色值，也不是某一个页面局部写法，而是：

> 当前项目仍把“几何真相”交给 Qt 原生 style / QSS 子控件规则决定。

如果目标是长期稳定、MIT 开源友好、后续二次开发可控，那么不能继续在 `QRadioButton::indicator` / `QSlider::handle` 上做修修补补，而应该把这些圆形几何收回到项目自身控制。

---

## 2. 产品目标

### 2.1 核心目标

建立一套项目自有的选择控件体系：

- 对外使用方式尽量接近原生 Qt
- 对内完全由项目自己控制几何、绘制、状态切换和 DPI 行为
- 第一阶段直接解决当前最明显的两个问题：Radio 外圈不圆、Slider handle 像椭圆

### 2.2 成功标准

第一阶段完成后，以下条件必须成立：

1. `ThemedRadioButton` 的外圈和内点在 100% / 125% / 150% 缩放下都保持真正圆形。
2. `ThemedSlider` 的滑块在水平模式下保持真正圆形，不再依赖 `QSlider::handle` 的 QSS 盒模型。
3. Gallery 和真实业务页面使用同一套控件类，而不是一个自绘、一个 QSS。
4. 运行时测试开始验证“最终渲染结果或最终几何”，而不是只验证样式字符串。
5. 新控件代码保持项目自有实现，不引入第三方受限代码，不破坏当前 MIT 源码发布路线。

### 2.3 非目标

本次设计明确不做：

- 不一次性重写全项目所有表单控件
- 不做 Qt 全局 monkey-patch
- 不为了“像原生”而重新依赖原生 `QStyle` 去决定核心圆形几何
- 不在第一阶段实现 Slider tick marks、复杂 inverted controls、垂直 slider 全量变体，除非现有项目已经在使用

---

## 3. 架构决策

### 3.1 总体路线

采用“项目自有控件 + Qt 抽象基类”的结构：

- `ThemedRadioButton` 基于 `QAbstractButton`
- `ThemedSlider` 基于 `QAbstractSlider`

而不是：

- 继续依赖 `QRadioButton` / `QSlider` 的原生 indicator / handle 子控件绘制
- 也不是完全脱离 Qt，自己重造一整套 UI 框架

### 3.2 为什么不用 `QRadioButton` / `QSlider` 继续强行自绘

继续继承 `QRadioButton` / `QSlider` 最大的问题是：

- 它们仍然天然携带原生 style / subcontrol 语义
- 很容易在焦点、hit area、sizeHint、style option 或 QSS 叠加时再次和系统行为打架
- 你看起来是在“自绘”，实际仍被原生几何约束拖住

因此本次方案要做的是：

> 只复用 Qt 的事件、状态、信号、焦点和可访问性基础设施；不复用 Qt 原生圆形子控件几何。

### 3.3 为什么这是 MIT 开源和二次开发最友好的路线

- 自定义控件实现全部来自项目自身，可继续放在 MIT 源码树中
- 不复制第三方 GPL 风格控件代码
- 不依赖 Qt 私有 style 细节，减少未来升级时的隐性兼容成本
- 二次开发者以后改的是项目自有 token、geometry、paint 逻辑，而不是继续猜 Qt QSS 行为

---

## 4. 组件设计

### 4.1 第一阶段组件

#### A. `ThemedRadioButton`

职责：

- 替代当前依赖 `QRadioButton::indicator` 的圆形单选控件
- 负责绘制外圈、内点、focus ring、hover/pressed/disabled 状态
- 支持文本标签和标准 button 信号

建议能力：

- `setText()` / `text()`
- `setChecked()` / `isChecked()`
- `toggled` / `clicked`
- `setEnabled()` / `isEnabled()`
- `sizeHint()` / `minimumSizeHint()`
- hover、focus、keyboard navigation
- 明确的 indicator rect 与 label rect 计算逻辑

#### B. `ThemedSlider`

职责：

- 替代当前依赖 `QSlider::groove` / `QSlider::handle` 的圆形滑块
- 负责绘制轨道、已选区、圆形 handle、hover/pressed/focus/disabled 状态
- 保留接近原生 slider 的 value / range / signal 行为

建议能力：

- `setRange()` / `minimum()` / `maximum()`
- `setValue()` / `value()`
- `setSingleStep()` / `singleStep()`
- `setPageStep()` / `pageStep()`
- `valueChanged` / `sliderMoved` / `sliderPressed` / `sliderReleased`
- orientation 支持；第一阶段优先保障 horizontal
- 自己计算 groove rect / active rect / handle center

### 4.2 配套共享模块

#### C. `selection_control_metrics.py`

职责：

- 根据 `AppTheme` 输出 Radio / Slider 需要的几何指标
- 在进入绘制前统一做 clamp，避免 0、负值、边框过粗等非法组合

#### D. `selection_control_painter.py`

职责：

- 存放共享的绘制辅助逻辑
- 比如：画 focus ring、画圆形 ring、画圆形 dot、画轨道、画 handle 阴影
- 保证 Radio 和 Slider 在“圆形语言”上统一，而不是各写一套

#### E. `selection_control_tokens`（内聚在 `AppTheme` 内）

职责：

- 扩展当前 theme token，使其从“QSS 样式 token”变成“控件几何 + 状态 token”
- 第一阶段新增以 geometry-first 为核心的字段，而不是继续围绕 `border-radius` 补丁命名

---

## 5. 主题与几何模型

### 5.1 Radio token 方向

建议核心字段：

- `radio_indicator_diameter`
- `radio_ring_width`
- `radio_dot_diameter`
- `radio_label_gap`
- `radio_hit_padding_x`
- `radio_hit_padding_y`
- `radio_color_ring`
- `radio_color_ring_hover`
- `radio_color_ring_checked`
- `radio_color_ring_disabled`
- `radio_color_dot`
- `radio_color_dot_disabled`
- `radio_color_bg`
- `radio_color_bg_disabled`
- `radio_focus_ring_color`
- `radio_focus_ring_width`

设计原则：

- 圆形的唯一真相由 `diameter` 决定
- dot 大小由 `dot_diameter` 决定，不再通过 QSS gradient 的 stop 比例猜测
- 所有状态变体都围绕同一组明确几何计算

### 5.2 Slider token 方向

建议核心字段：

- `slider_track_height`
- `slider_handle_diameter`
- `slider_handle_ring_width`
- `slider_active_track_color`
- `slider_inactive_track_color`
- `slider_handle_color`
- `slider_handle_border_color`
- `slider_handle_hover_border_color`
- `slider_handle_pressed_border_color`
- `slider_handle_disabled_color`
- `slider_focus_ring_color`
- `slider_focus_ring_width`
- `slider_hit_extra_radius`

设计原则：

- handle 几何只由 `slider_handle_diameter` 决定
- 轨道与 handle 的相对关系由项目自己的 rect 计算决定
- 所有视觉圆形都以外轮廓为真值，不允许再出现“内容框 20，实际外框 22”这种隐式偏移

---

## 6. 绘制与状态模型

### 6.1 绘制原则

所有圆形绘制都遵守以下规则：

1. 使用 `QPainter` + `QRectF` + `Antialiasing`
2. 用“明确外轮廓直径”计算圆，而不是通过 border-radius 推导
3. 所有圆形绘制都经过统一的像素对齐规则，避免 1px ring 在高 DPI 下发虚
4. Radio 和 Slider 的 focus ring、disabled 节奏、hover 节奏共享视觉语言

### 6.2 状态快照

在 `paintEvent` 前先整理状态快照，而不是在绘制时到处判断：

- enabled / disabled
- checked（Radio）
- hover
- pressed
- focused
- orientation（Slider）
- current value, min, max（Slider）

这样做的好处是：

- 绘制更纯粹
- 测试更容易
- 后续二次开发更容易替换 state-to-style 映射

---

## 7. API 兼容策略

### 7.1 总原则

对外尽量像原生 Qt，但不承诺 100% 全量兼容。

原因：

- 本项目需要的是“替换当前实际使用场景”，不是复刻整个 Qt 控件宇宙
- 全量兼容会极大抬高实现成本，并把项目重新绑回原生行为包袱

### 7.2 第一阶段兼容范围

#### `ThemedRadioButton`

必须兼容：

- 文本
- checked 状态
- toggled / clicked 信号
- enabled / disabled
- 焦点与键盘触发
- sizeHint 行为可预测

可后续扩展：

- icon 模式
- 更复杂的富文本 label
- 更强的 accessibility 补充

#### `ThemedSlider`

必须兼容：

- horizontal 模式
- range / value / single step / page step
- 点击、拖动、键盘、滚轮
- valueChanged / sliderMoved / sliderPressed / sliderReleased
- 焦点态

明确暂缓：

- tick marks
- 非项目现用的复杂样式位
- 在第一阶段用 QSS 改造绘制外观

---

## 8. 接入与迁移策略

### 8.1 接入原则

采用显式替换，不做全局 monkey-patch。

也就是说：

- 业务页面要明确从 `src.shared.ui` 导入 `ThemedRadioButton` / `ThemedSlider`
- 旧的 `QRadioButton` / `QSlider` 代码逐点替换
- preview 和真实 UI 都走同一套类

### 8.2 第一阶段迁移点

优先替换：

1. `demo_style_gallery.py` 中的 Radio / Slider 展示
2. 当前真实业务页里实际使用这些控件的页面
3. 相关测试里的控件引用与断言方式

### 8.3 保留旧体系的边界

- `QCheckBox` 暂时继续留在当前 shared QSS builder 中
- 运行时边界已经收缩为 `build_checkbox_stylesheet()`；旧的 merged builder 只保留历史阶段语义，不再作为当前代码路径
- 最终状态是：
  - Checkbox 仍可由 QSS 管理
  - Radio / Slider 改为自绘控件
  - 后续若需要，再决定是否把 Checkbox 也纳入自绘体系

---

## 9. 测试策略

### 9.1 当前测试缺口

当前失败经验已经证明，只测试 QSS 文本是不够的。

必须新增“运行时几何测试”和“渲染结果测试”。

### 9.2 第一阶段测试结构

#### A. 几何测试

验证：

- `ThemedRadioButton` 计算出的 indicator rect 宽高相等
- `ThemedSlider` 计算出的 handle rect 宽高相等
- 各状态下外轮廓直径和 token 一致
- clamp 后的 metrics 合法

#### B. API 行为测试

验证：

- Radio 的 checked/toggled/clicked 正常工作
- Slider 的 value/range/keyboard/dragging 正常工作
- disabled 时交互被正确阻断

#### C. 渲染测试

通过 offscreen `grab()` 或 `render()`：

- 检查非透明像素的外接框接近正方形
- 检查 hover / checked / disabled 时核心视觉区域存在变化
- 在至少 100% 与 125% 缩放下做 smoke verification

#### D. 架构测试

验证：

- gallery 不再通过 `QSlider::handle:horizontal` 和 `QRadioButton::indicator` 控制圆形几何
- 真实页面与 preview 都导入新控件
- 不存在第二套私有 Radio / Slider 圆形绘制体系

---

## 10. 错误处理与稳定性要求

### 10.1 几何防御

所有 metrics 都必须在进入绘制前统一 clamp：

- diameter >= 最小可用值
- ring_width 不可大于半径
- dot_diameter 不可大于内圆
- focus ring 不可把控件撑裂布局

### 10.2 状态一致性

- 鼠标 hover、pressed、focus、disabled 的状态更新必须触发 repaint
- Slider 拖动中与拖动后信号顺序要稳定
- Radio 在 button group 下的互斥行为必须与项目现有使用习惯兼容

### 10.3 尺寸一致性

- `sizeHint()` 必须以控件真实几何为基础
- hit area 可以比视觉圆形更大，但视觉圆形本身不能再被布局或边框隐式扩展成非圆

---

## 11. 开源与许可证边界

本次方案的许可证原则：

1. 新控件实现全部使用项目自有代码
2. 不复制 GPL 风格控件库代码、资源或受限实现细节
3. 保持当前仓库“项目源码 MIT、第三方依赖各自许可证”的公开口径
4. 继续沿用仓库现有的 `OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md` 和 `THIRD_PARTY_NOTICES.md` 约束

这意味着：

- 这次重构不会让 MIT 发布路线更差
- 但也不会把 PySide6 / Qt 这类第三方依赖 magically 变成 MIT
- 设计上要尽量避免与 Qt 私有样式实现深耦合，降低未来合规和维护成本

---

## 12. 分阶段落地建议

### Phase 1

- 新增 `ThemedRadioButton`
- 新增 `ThemedSlider`
- 新增 geometry / painter 辅助模块
- 扩展主题 token
- 替换 gallery 和首批真实业务页面
- 建立运行时几何测试

### Phase 2

- 评估 `QCheckBox` 是否进入自绘体系
- 将 Selection Controls 统一成更完整的家族语言
- 扩展到 toggle / preset selector / list selection 等选中态控件

---

## 13. 关键取舍总结

本次设计的最终取舍是：

- 不是继续调 QSS
- 不是完全脱离 Qt
- 而是：
  - 保留 Qt 抽象控件基类提供的事件、状态、信号、焦点基础设施
  - 收回项目真正关心的圆形几何和绘制控制权
  - 对外提供接近原生 Qt 的 API
  - 对内建立项目自有的稳定控件体系

这是当前在“长期稳定、兼容、可维护、二次开发、MIT 源码发布”之间最平衡、也最可持续的方案。

---

## 14. 自检

- 没有留 TODO / TBD 占位
- 范围聚焦在 Radio / Slider 第一阶段
- 已明确非目标，避免全量重构失控
- 已明确不做 monkey-patch
- 已明确真实 UI 与 preview 共用同一套控件类
