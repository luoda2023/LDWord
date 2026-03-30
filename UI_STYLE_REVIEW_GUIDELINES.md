# Lark Formatter V1.0 —— UI 控件样式设计与审阅指南

本文档用于团队内部传阅，对 Lark Formatter 项目的 UI 控件进行视觉样式审查。项目中目前所有的 UI 视觉元素均已抽离并在 `demo_style_gallery.py` 中集中展示。

请运行以下命令启动全量控件画廊，对照本文档进行审阅：
```bash
python demo_style_gallery.py
```

---

> [!IMPORTANT]
> **Current selection-controls boundary (2026-03-28):**
> - `QCheckBox` remains on the shared QSS helper path.
> - Round Radio / Slider geometry must be reviewed on `ThemedRadioButton` / `ThemedSlider`, not on `QRadioButton::indicator` or `QSlider::handle`.
> - If a page still relies on old Radio / Slider QSS geometry, treat that as architecture debt rather than the target review baseline.

## 🎨 第一部分：设计原则与修改边界

在提出视觉修改意见或直接修改代码时，请务必遵守以下边界规则：

### ✅ 【允许的修改边界】（我们希望优化的点）
1. **色彩体系 (Tokens)**：可以重新定义 `src/shared/ui/theme.py` 中的 `AppTheme` 属性色值。我们可以增加新的语义 Token（如 `border_hover`, `bg_button_pressed` 等）。
2. **尺寸与间距**：控件的具体高度 (`32px` vs `36px`)、圆角大小 (`radius_sm`, `radius_md`)、内外边距 (Padding/Margin)。
3. **排版与字体**：字号阶梯 (`11px` 到 `20px`) 的定义、字体粗细、行高。
4. **视觉质感**：卡片的阴影参数 (`QGraphicsDropShadowEffect`)、边框颜色与粗细。
5. **动画细节**：`ToggleSwitch`、`CollapsibleSection` 等带有动画效果的控件，可以调整其 `QPropertyAnimation` 的时长、缓动曲线，或增加色彩过渡动画。
6. **图标替换**：项目统一使用 [Lucide Icons](https://lucide.dev/) (SVG, 线条风格)。可以要求在 `catalog.py` 中更换其他 Lucide 图标或修改其笔触粗细 (`stroke-width`)。

### ❌ 【不可修改的底线】（涉及核心架构，禁止改动）
1. **禁止硬编码颜色**：**绝对禁止**在具体的 PyQt 控件类（如 `.setStyleSheet("color: #FF0000")`）中写死颜色值。所有颜色**必须**通过 `get_theme().xxx` 动态获取，以保证 Light/Dark/Ocean 三套主题的无缝切换。
2. **禁止改变信号与槽逻辑**：控件释放的业务信号（如 `search_changed`, `toggled_signal`）以及数据流向禁止修改。我们只做“视觉换皮”，不动“内部器官”。
3. **禁止弃用原生自适应布局**：不能使用绝对坐标定位 (`setGeometry(x, y, w, h)`)。必须使用 Qt 的 `QHBoxLayout`/`QVBoxLayout` 并结合 `stretch`。支持窗口自适应是最基本要求。
4. **SVG 图标规范**：禁止使用带多色填充的位图 (PNG/JPG)，必须维持单一 currentColor 颜色填充的 SVG 线路图格式，以便通过代码动态上色（如夜间模式图标变白）。

### 🛑 【交互防误触底线】
1. **下拉框滚轮劫持**：必须全局禁用 `QComboBox` 和 `QSpinBox` / `QDoubleSpinBox` 在未获得焦点时的鼠标滚轮事件（`wheelEvent`）。防止用户在页面 `QScrollArea` 滚动时，由于鼠标掠过输入框而导致参数被意外篡改。
   *(目前已在入口文件通过全局 `eventFilter` 统一拦截 `QEvent.Wheel` 解决。新增表单模块时不要破坏此拦截链。)*
2. **SpinBox Enter 行为修正**：`QSpinBox` / `QDoubleSpinBox` 按 Enter 后的默认行为已修改为：提交值 → 取消全选 → 释放焦点。由 `src/shared/ui/input_guard.py` 的 `GlobalInputGuard` 统一管理。交互设计：
   - 单击 → 定位光标（精确编辑）
   - 双击 → 全选文本（Qt 原生行为，保留）
   - Enter → 确认值并离开输入框
   - 滚轮 → 被拦截（防误触）

---

## ⚠️ 第〇部分：风险防护规则（所有 UI 修改必须遵守）

以下规则源自已发生的真实 Bug，任何 UI 代码修改都必须逐条检查。

### R1: 全局 EventFilter 不得吞噬非目标事件
- App 级 `eventFilter` 中 `return True` 会阻断事件传播。必须确认拦截的事件类型和目标对象是精确匹配的。
- 拦截 `KeyPress(Enter)` 时，不得影响对话框 `QPushButton.setDefault(True)` 的 Enter 触发。
- **规范**：如果不确定是否影响其他控件，优先使用 `clearFocus()` 替代 `return True`。

### R2: QSS 选择器必须限定作用域
- **禁止**使用裸类型选择器覆盖伪状态（如 `QPushButton:disabled { ... }`），会覆盖所有实例。
- **必须**使用 `#objectName:disabled` 限定到具体控件。
- 例外：基础属性的裸类型选择器是允许的（如 `QLabel { color: ... }`）。

### R3: 临时文件必须有生命周期管理
- `tempfile.mkstemp()` 创建的文件**必须**在不再需要时清理。
- 在可能多次调用的函数中，**必须**缓存路径并在下次调用前清理。
- 推荐模式：`self._temp_files = []` + 重入时先遍历 `os.remove()`。

### R4: 颜色值必须走 Theme Token
- **绝对禁止**在 QSS 中使用硬编码十六进制颜色（如 `#FF7875`）。
- 所有颜色**必须**通过 `{t.xxx}` 引用 Token。不足时先在 `AppTheme` 中新增，再在所有预设中赋值。

### R5: 新控件必须声明完整的四态 QSS
- 必须定义：默认态、`:hover`、`:pressed`、`:disabled`，遗漏任意一态会回退到系统默认样式。

### R6: demo 控件必须与 Section 2 保持参数一致
- Focus Preview 区域的控件必须和 Section 2 的同类控件使用相同的 `setFixedHeight`、`setObjectName` 等参数。

### R7: QWidget 子类必须启用 `WA_StyledBackground`
- `QWidget` 子类默认**不渲染** QSS 的 `background` 和 `border`。
- 如果自定义 `QWidget` 需要通过 QSS 显示边框/背景，**必须**在 `__init__` 中调用 `self.setAttribute(Qt.WA_StyledBackground, True)`。
- 这是 Qt 的已知陷阱，不加此属性会导致控件"透明"。

### R8: Lucide 图标必须先注册到 catalog
- 使用 `get_icon(name, ...)` 前，**必须**确认 `name` 已存在于 `catalog.py` 的 `_SVG` 字典中。
- 如果 key 不存在，`get_icon` 会**静默返回空 `QIcon()`**，不会报错——图标直接消失。
- 新增图标时，从 [Lucide Icons](https://lucide.dev/) 获取 SVG，保持 `stroke="currentColor"` 占位。

### R9: 新增主题必须通过对比度验证
- `AppTheme` 提供 `validate_contrast()` 方法，检查 5 对关键 Token 的亮度差。
- **新增或修改主题后**，必须运行 `theme.validate_contrast()` 确认返回空列表。
- `set_theme()` 已在开发模式 (`__debug__`) 下自动打印警告，但**不会阻塞运行**。
- 阈值参考：`text_on_primary` vs `primary` ≥40%，`border` vs `bg_card` ≥12%，`border_light` vs `bg_card` ≥10%。

---

## 📋 第二部分：控件全览与审阅重点

目前项目共包含 **24 种** 核心自定义控件 + 一系列 Qt 原生控件。请按以下类目逐一审阅 `demo_style_gallery.py` 中的渲染效果并提出意见：

### 1. 全局设计系统 (Design System Tokens)
- **审阅位置**：Section 1
- **审阅要点**：
  - `primary` / `accent` (品牌蓝、强调橙) 是否符合产品定位？
  - Light/Dark/Ocean 三套预设下，文字色 (`text_primary`, `text_secondary`, `text_hint`) 的对比度是否达标（不要太刺眼也不要太暗淡）？
  - 阴影扩散半径 (`radius_sm`=4px, `radius_md`=8px) 是否符合现代 UI 偏好的“圆润感”？

### 2. 原生基础控件 (Native Controls)
- **包含控件**：`QPushButton` (Primary/Secondary/Danger/Disabled 4态)、`QLineEdit`, `QComboBox`, `QSpinBox`, `QCheckBox`, `ThemedRadioButton`, `ThemedSlider`, `QTabWidget`
- **文件位置**：样式在 `demo_style_gallery.py` 的全局 QSS 中统一定义。
- **审阅要点**：
  - 按钮的 Hover 态、Pressed 态颜色反馈是否明显？禁用态 (Disabled) 的灰度是否清晰传达“不可点击”语义？
  - 下拉框 (ComboBox) 和文本框 (LineEdit) 获取焦点 (Focus) 时的边框高亮是否与主题融合？
  - 表单高度统一采用 32px 或 36px，纵向韵律是否齐整？
  - `ThemedRadioButton` / `ThemedSlider` 的圆形几何是否在高 DPI 下依旧保持真圆，而不是被旧的 QSS 子控件盒模型拉扁？

### 3. 自定义输入反馈 (Custom Inputs)
- **包含控件**：
  - `ToggleSwitch` (胶囊开关)：目前由 `QPainter` 手绘，尺寸为 44x24，滑块占比是否和谐？过渡动画是否流畅？
  - `SearchInput` (搜索框)：带右侧清除 ✕ 按钮，搜索放大镜图标的占位是否合理？
  - `SpacingInput` (间距输入)：浮点数框与右侧单位组合，宽度分配是否舒适？
  - `FolderPicker` (文件夹选择器)
  - `PlaceholderEdit` (占位符编辑器，用于填写 `{nn}` 等变量)
  - `ColorPicker` (颜色拾取器)

### 4. 容器与排版层 (Containers & Layouts)
- **包含控件**：
  - `Card` (卡片，`card.py`)：带标题栏和底层阴影的白色/深色块。阴影模糊度 (`shadow_blur_md`) 和卡片边框 (`border`) 是否有冲突？
  - `CollapsibleSection` (折叠面板)：高级设置收起/展开的过渡效果，箭头 `>` 是否需要更换成加号 `+`？
  - `FormRow` (表单行组合)：`[左侧120px标签 + 右侧组件]` 模型，留白比例是否合适？

### 5. 提示与状态 (Feedback & Indicators)
- **包含控件**：
  - `StatusIndicator`：用于绘制各步骤状态（成功黄、警告橙、错误红、加载中等圆形 Badge）。小尺寸展示时矢量边缘是否锐利？
  - `ProgressIndicator`：处理文档时的底部横向进度条+步骤名文本，取消按钮的位置是否合理？
  - `OverrideBadge`：表示参数被“覆写”的小闪电徽标 ⚡，以及灰色的原始值恢复按钮。
  - `ModuleStepList`：任务管道的待办清单列表。

### 6. 弹窗对话框体系 (Dialogs)
- **调用入口**：`info()`, `success()`, `warning()`, `error()`, `confirm()`, `input_text()` (`src/shared/ui/dialogs.py`)
- **审阅要点**：
  - 采用了 **无边框双层解耦透明底座** 的自绘逻辑，以解决高分屏文字发虚。
  - 对话框的毛玻璃阴影扩散范围 (`shadow_blur_xl`) 是否高级？
  - 错误弹窗 (`error`) 附带的日志路径单行展示区域，报错代码的等宽字体 (`Consolas`) 与红字背景板是否醒目？
  - 危险确认 (`confirm(destructive=True)`) 弹窗中的主按钮标红效果是否起到足够的警示作用？

---

## 📝 下一步行动建议

1. **直接修改 Token**：若仅涉及颜色、基础字号的微调，同事可直接在 `src/shared/ui/theme.py` 中的 `AppTheme` 对应预设处修改参数。
2. **提出形态修改意见**：对于需要重写 `paintEvent`（如胶囊开关动画重构）或大量 QSS 布局调整（如调整原生 QTabWidget 的样式表）的需求，请在此文档后 **追加需求说明 (TODO 列表)**，交由大语言模型或客户端研发人员执行。
3. **补充新控件**：如果现有 24 个组件无法满足未来的新需求（例如需要多选标签框 TagInput、级联选择器 Cascader），请汇总并在架构层面提议新增 `src/shared/ui/xxxx.py`。
