# UI 控件统一收编与 Token 化重构设计

- 日期：2026-03-26
- 范围：QPushButton / SearchInput / QComboBox 系列（含 FontCombo、SizeCombo、NumberingPreset）
- 目标目录：`src/shared/ui/`

## 1. 背景与问题

当前 UI 控件体系存在三类结构性问题：

1. **正式实现与 demo 实现分叉**
   - `demo_style_gallery.py` 中定义了 `_SearchLineEdit`、`_StyledComboBox`。
   - `src/shared/ui/` 中又存在 `SearchInput`、`FontCombo`、`SizeCombo`、`NumberingPreset`。
   - 结果是样式、行为、维护入口不唯一，后续修改容易遗漏。

2. **Theme token 未覆盖全部视觉常量**
   - 颜色大多已走 `get_theme()`。
   - 但圆角、高度、padding、间距、图标尺寸、箭头区宽度、popup 偏移等仍存在大量局部 magic number。

3. **样式治理边界不清**
   - 同类控件同时被全局 QSS、局部 QSS、本地 demo 类管理。
   - `objectName` 同时承担“对象身份”和“样式 variant”用途，不利于维护和测试。

本次重构按“短痛”策略处理：允许改类名、文件结构、API，只要求最终界面和行为稳定，并为后续规划清空阻碍。

## 2. 重构目标

1. **demo 只负责展示，不再定义正式控件实现。**
2. **所有正式控件统一收编到 `src/shared/ui/`。**
3. **所有视觉常量必须 token 化，禁止在控件内继续写 magic number。**
4. **所有 ComboBox 派生控件统一建立在同一个基础实现上。**
5. **按钮 variant 改为 property 驱动，禁止再用重复 `objectName` 充当样式类别。**
6. **Focus Preview 与 Section 2 的控件实例参数必须同源，避免预览与正式展示分叉。**

## 3. 非目标

1. 本次不扩展新的业务功能。
2. 本次不改变用户可感知的交互语义（滚轮拦截、Enter 行为、弹层行为保持一致）。
3. 本次不引入过度抽象的样式注册中心；优先建立清晰、可维护的基础组件即可。

## 4. 目标结构

重构后目录结构如下：

```text
src/shared/ui/
  theme.py
  button_style.py
  search_input.py
  styled_combo_box.py
  font_combo.py
  size_combo.py
  numbering_preset.py
```

其中：

- `theme.py`：主题与设计 token 的唯一源。
- `button_style.py`：按钮 variant 属性与样式应用 helper。
- `search_input.py`：唯一正式搜索输入控件。
- `styled_combo_box.py`：唯一正式下拉基类，封装 popup shell、item view、箭头绘制、弹层定位。
- `font_combo.py` / `size_combo.py` / `numbering_preset.py`：只保留领域数据与信号，统一继承 `StyledComboBox`。
- `demo_style_gallery.py`：只 import 正式控件并组装展示，不再定义本地替代类。

## 5. 组件设计

### 5.1 SearchInput

保留 `src/shared/ui/search_input.py`，但重构为唯一正式实现。

职责：

- 搜索图标展示
- 分隔线展示
- 内嵌 `QLineEdit`
- 清除按钮
- debounce 信号
- focus 视觉反馈
- 主题切换刷新

约束：

- 启用 `WA_StyledBackground`
- 所有尺寸、圆角、padding、图标尺寸走 token
- 删除重复 `setStyleSheet()` 调用
- 对外保留稳定的搜索行为接口（`search_changed` / `search_submitted` / `clear()` / 文本读取）

`demo_style_gallery.py` 中的 `_SearchLineEdit` 删除，统一改用 `SearchInput`。

### 5.2 StyledComboBox

新增 `src/shared/ui/styled_combo_box.py`，作为唯一正式下拉基类。

职责：

- 替换原生 popup view 为 `QListView`
- 管理 popup shell 的背景、边框、圆角
- 管理 item view / item hover / selected 样式
- 管理箭头绘制
- 管理 popup 重定位和宽度同步
- 主题切换刷新

约束：

- 不允许子类继续各自定义视觉基建
- 不允许同时再被另一套局部 QSS 覆盖同一组核心样式
- 弹层黑角修复逻辑必须留在基类中，避免下游重复实现

### 5.3 FontCombo / SizeCombo / NumberingPreset

三者都继承 `StyledComboBox`。

职责边界：

- 子类只负责：数据填充、领域信号、必要的编辑能力
- 基类负责：视觉样式、popup 呈现、箭头、主题刷新

这样可以确保所有 Combo 派生控件样式统一，不再分叉。

### 5.4 按钮 variant

按钮样式从 `objectName` 迁移到动态属性：

- `variant=primary`
- `variant=secondary`
- `variant=danger`

由 `button_style.py` 提供 helper，例如：

```python
apply_button_variant(button, "primary")
```

设计原因：

- `objectName` 应用于对象身份，而不是样式类别
- 动态属性更适合复用型 variant 样式
- 测试与调试时更容易区分“实例身份”和“样式归类”

## 6. Token 设计

### 6.1 继续沿用的现有 token

- `radius_sm`
- `radius_md`
- `spacing_sm`
- `spacing_md`
- `control_height_md`
- `font_size_md`
- `border`
- `border_focus`
- `bg_input`
- `bg_hover`
- `bg_selected`
- `text_primary`
- `text_disabled`
- `text_hint`
- `icon_secondary`

### 6.2 本次新增 token

#### 按钮
- `button_radius`
- `button_padding_x`
- `button_padding_y`
- `button_height_md`
- `button_font_weight`

#### 输入框 / SearchInput
- `input_radius`
- `input_padding_x`
- `input_padding_y`
- `input_icon_size`
- `input_clear_button_size`
- `input_separator_width`
- `input_separator_height`

#### Combo / Popup
- `combo_arrow_zone_width`
- `combo_arrow_size`
- `combo_popup_padding`
- `combo_popup_item_padding_x`
- `combo_popup_item_padding_y`
- `combo_popup_offset_y`
- `combo_popup_radius`

#### SpinBox
- `spin_button_width`

说明：

- 本次 token 补齐的原则是：凡是跨控件、跨场景可能复用或影响视觉一致性的数字，都必须进入 theme。
- 仅允许少数纯算法性值保留局部（例如绘制箭头时由尺寸推导出的临时中间量）。

## 7. demo_style_gallery 的角色调整

`demo_style_gallery.py` 在重构后只承担两种职责：

1. 组装并展示正式控件
2. 验证不同主题下的可视化效果

明确禁止：

- 定义正式控件类
- 复制 shared 控件逻辑
- 为正式控件额外偷偷维护另一套视觉实现

Focus Preview 与 Section 2 中使用的控件必须复用同一套构造入口或工厂，参数来源一致。

## 8. 样式治理规则

1. **正式控件唯一实现源在 `src/shared/ui/`。**
2. **所有视觉常量必须来自 theme token。**
3. **同一类控件只能有一个视觉真源。**
4. **领域控件不得再自行扩张视觉基建。**
5. **按钮 variant 走 property，不走重复 objectName。**
6. **demo 禁止定义 shared 控件替代品。**

## 9. 迁移顺序

### 第 1 步：补齐 token
- 修改 `theme.py`
- 增加本次需要的 button / input / combo / spin token
- 保证所有主题预设均有值

### 第 2 步：重构 SearchInput
- 清理重复样式设置
- 接入 token
- 保留主题切换与 debounce 行为
- 删除 demo 中 `_SearchLineEdit` 并切换调用点

### 第 3 步：新增 StyledComboBox
- 抽出 `_StyledComboBox` 正式化到 shared
- 接入 token
- 保留 popup shell 方案和黑角修复成果

### 第 4 步：统一 Combo 派生控件
- `FontCombo` 继承新基类
- `SizeCombo` 继承新基类
- `NumberingPreset` 继承新基类
- 清理各自局部视觉常量

### 第 5 步：重构按钮 variant
- 引入 `button_style.py`
- 把按钮样式由 `objectName` 改为 property 驱动
- 更新 demo 和面板使用点

### 第 6 步：收敛 demo
- 删除本地控件实现
- 统一 Focus Preview 与 Section 2 参数来源
- 只保留展示逻辑

## 10. 测试与验证

### 10.1 自动化验证

至少补充以下验证：

1. SearchInput 主题样式相关测试
2. StyledComboBox popup shell / view QSS 生成测试
3. Combo 派生控件继承结构测试
4. 按钮 variant helper 的属性/QSS 应用测试
5. 现有 UI smoke test 保持通过

### 10.2 手工验证

在 `demo_style_gallery.py` 中确认：

1. Light/Dark/Ocean 等主题切换正常
2. SearchInput focus / clear / 输入行为正常
3. ComboBox popup 无黑角、无锯齿、无局部样式分叉
4. SpinBox / DoubleSpinBox 滚轮拦截、Enter 行为正常
5. Focus Preview 与 Section 2 风格一致
6. FontCombo / SizeCombo / NumberingPreset 视觉与 popup 行为一致

## 11. 验收标准

重构完成后必须满足：

1. `demo_style_gallery.py` 不再包含 `_SearchLineEdit` 与 `_StyledComboBox` 等正式控件定义
2. `SearchInput` 成为唯一正式搜索输入控件
3. `FontCombo / SizeCombo / NumberingPreset` 均建立在统一 Combo 基类上
4. 截图范围内控件不再存在本地 magic number 样式常量
5. 颜色、尺寸、圆角、padding、偏移均可通过 theme token 调整
6. 视觉与交互效果不回退
7. 后续新增 Combo 类控件无需复制 popup 方案

## 12. 风险与控制

### 风险 1：重构期间样式回退
控制：先补最小测试，再逐个替换调用点，保留 demo 可视化验证窗口。

### 风险 2：领域控件行为受基类影响
控制：基类只收编视觉和 popup 基建，不随意改领域数据逻辑。

### 风险 3：token 一次性补太多导致使用混乱
控制：命名按按钮 / 输入框 / Combo / Spin 四组聚类，避免含义重叠。

## 13. 最终决策

本次采用“统一收编到 `src/shared/ui/` + 建立可复用基类 + 全量 token 化”的路线，不采用最小修补方案，也不引入更重的样式注册中心。

这是一次面向长期维护的结构重构，而不是局部补丁。
