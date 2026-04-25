# UI Surface / 圆角实现盘点

- 日期：2026-04-02
- 目标：列出项目内所有主要圆角实现方式，标记高 DPI / 一致性风险，并给出一劳永逸的收敛方案

## 1. 当前实现方式总览

项目里现在并存 4 类圆角/表面实现：

1. 自绘表面容器
2. QSS 卡片/面板圆角
3. QSS 控件圆角
4. 自绘控件圆角

这 4 类并存本身不是问题，问题在于：

- 同一层级的 UI 表面没有统一到同一种机制
- 高 DPI 下，QSS 圆角、透明背景、自绘边框、阴影会互相叠出假边框/缺角
- 一些关键表面现在混用“自绘外框 + 矩形内容层”的叠法，容易出现边缘破口

## 2. 现有实现方式清单

### 2.1 自绘表面容器

共享基类：

- [rounded_surface.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/rounded_surface.py)

当前使用者：

- [main_window.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/main_window.py)
- [base_dialog.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/base_dialog.py)
- [quick_execution_drop_area.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/quick_execution_drop_area.py)

特点：

- 圆角和边框来自同一个绘制源
- 更适合窗口壳、弹窗、拖拽区、浮层、大面积关键表面
- 高 DPI 下更可控

已发现风险：

- [quick_execution_drop_area.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/quick_execution_drop_area.py) 外层自绘边框与内部全尺寸内容层叠加，需要内容 inset 才能避免压边

### 2.2 QSS 卡片/面板圆角

共享卡片基类：

- [card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/card.py)

卡片派生 / 依赖：

- [navigation_card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/navigation_card.py)
- [strategy_card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/strategy_card.py)
- [heading_quick_card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/heading_quick_card.py)
- [quick_fill_card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/quick_fill_card.py)
- [config_management_detail.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/config_management_detail.py)
- [feature_detail_panes.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/feature_detail_panes.py)
- [config_list_widget.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/config_list_widget.py)
- [recent_run_panel.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/recent_run_panel.py)

特点：

- 目前主要走 `border-radius + background + border + QGraphicsDropShadowEffect`
- 适合普通信息卡和轻量卡片
- 但与自绘表面体系不统一

已发现风险：

- [card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/card.py) 仍然是 QSS 圆角 + 阴影，和 `RoundedSurfaceFrame` 体系并存
- [navigation_card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/navigation_card.py) 在卡片基类之上再用 QSS 改背景，后续如果统一卡片底层，需要一起迁移

### 2.3 QSS 壳层/边缘圆角

文件：

- [title_bar.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/title_bar.py)
- [sidebar.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/sidebar.py)
- [theme_panel.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/theme_panel.py)
- [workbench/styles.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/styles.py)
- [main_window.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/main_window.py) 里的 `_PlaceholderPanel`

特点：

- 局部边缘修饰，大多依赖父层已经正确裁剪
- 不是“真正的壳层实现”，更像视觉补边

已发现风险：

- 如果父层壳体换半径，而这些局部边缘没同步，就会出现拼接错位
- 这类代码应继续减少，尽量只保留“局部拼边”用途

### 2.4 QSS 控件圆角

共享 builder / style helper：

- [button_style.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/button_style.py)
- [input_style.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/input_style.py)
- [selection_control_style.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/selection_control_style.py)
- [dialog_style.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/dialog_style.py)

直接使用 token 的控件：

- [badge.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/badge.py)
- [color_picker.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/color_picker.py)
- [collapsible_section.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/collapsible_section.py)
- [icon_button.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/icon_button.py)
- [log_stream_widget.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/log_stream_widget.py)
- [progress_indicator.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/progress_indicator.py)
- [search_input.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/search_input.py)
- [styled_combo_box.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/styled_combo_box.py)
- [style_preview.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/style_preview.py)
- [heading_numbering_styles.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/heading_numbering_styles.py)
- [workbench/styles.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/styles.py)
- [quick_execution_detail.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/quick_execution_detail.py)

特点：

- 这类圆角通常适合按钮、输入框、标签、小块背景
- 不建议迁移到自绘 surface
- 关键是保持 token 统一，不允许局部硬编码

已发现风险：

- [theme_panel.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/theme_panel.py) 仍有 `18px`、`6px`、`2px` 这类硬编码
- [quick_execution_drop_area.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/quick_execution_drop_area.py) 内部图标和清除按钮也还有 `6px`、`14px` 的局部硬编码

### 2.5 自绘控件圆角

文件：

- [rounded_surface.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/rounded_surface.py)
- [toggle_switch.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/toggle_switch.py)
- [themed_slider.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/themed_slider.py)
- [theme_panel.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/theme_panel.py) 预览绘制

特点：

- 适合开关、滑块、预览板、自定义表面
- 高 DPI 更稳定，但必须严格管理几何和内容层叠关系

## 3. 高 DPI / 一致性风险清单

高风险：

- [card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/card.py)
  QSS 圆角 + 阴影，是目前普通卡片体系的核心，和自绘 surface 分裂
- [navigation_card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/navigation_card.py)
  在 `Card` 之上再次靠 QSS 改背景状态，后续统一时必须一起迁移
- [quick_execution_drop_area.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/quick_execution_drop_area.py)
  已迁入自绘 surface，但内部内容层和外层边框仍是独立层叠，需要继续做内容层统一裁剪
- [theme_panel.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/theme_panel.py)
  同时混用了多种自绘圆角和硬编码值

中风险：

- [title_bar.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/title_bar.py)
- [sidebar.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/sidebar.py)
- [workbench/styles.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/styles.py)
- [base_dialog.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/base_dialog.py)
- [main_window.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/main_window.py)

低风险：

- builder 型控件样式，如 [button_style.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/button_style.py)、[input_style.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/input_style.py)
- 轻量角标/按钮小圆角，如 [badge.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/badge.py)、[search_input.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/search_input.py)

## 4. 一劳永逸的收敛方案

### 4.1 官方表面原语

后续项目只允许 3 类官方表面实现：

1. `RoundedSurfaceFrame`
2. `Card` / `NavigationCard`
3. 共享 style builder（按钮、输入框、选择控件）

规则：

- 窗口壳、弹窗、拖拽区、浮层、大面积关键容器 → `RoundedSurfaceFrame`
- 普通信息卡、导航卡、轻量功能卡 → 统一 Card 体系
- 按钮/输入框/checkbox/radio/搜索框/下拉 → 共享 QSS builder

### 4.2 token 规则

统一保留：

- `shell_radius`
- `radius_md`
- `radius_sm`
- `radius_xs`
- `radius_full`

禁止新增无 token 支撑的硬编码圆角值。

### 4.3 高 DPI 规则

- 关键表面优先使用 `RoundedSurfaceFrame`
- 不允许“自绘 1px 边框 + 全尺寸矩形内容层”直接叠加
- 需要边框露出的表面，内容层必须有明确 inset 或共享同样的裁剪路径
- grab/像素测试一律按真实图像像素，不按逻辑尺寸硬取点

## 5. 建议执行顺序

第一批：表面体系收敛

- 把 [card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/card.py) 迁入 `RoundedSurfaceFrame` 体系
- 同步调整 [navigation_card.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/shared/ui/navigation_card.py)
- 确立“Card family”和“Surface family”的清晰边界

第二批：高风险特殊容器

- 收尾 [quick_execution_drop_area.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/workbench/quick_execution_drop_area.py) 的内容层圆角一致性
- 清理 [theme_panel.py](/C:/Users/Administrator/Desktop/Lark-Formatter%201.0/Lark-Formatter%20V1.0/src/ui/panels/theme_panel.py) 的多套硬编码绘制逻辑

第三批：硬编码清扫

- 把所有 `6px`、`14px`、`18px` 这类非 token 圆角值逐步替换成 theme token
- 删除遗留 `.bak` 文件里的旧实现噪音

## 6. 当前建议

如果要“一劳永逸全部解决问题”，下一步最值得做的不是继续点修单个 bug，而是：

1. 迁移 `Card` 基类到共享自绘 surface
2. 一起迁移 `NavigationCard`
3. 补一组高 DPI 像素回归测试，锁住：
   - 主窗口壳
   - 弹窗壳
   - 普通卡片
   - 导航卡片
   - 拖拽区

做到这一步，项目里大多数“圆角实现逻辑不一致”问题才会真正开始收敛。
