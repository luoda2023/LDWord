# UI 控件缺口分析与补充计划

- 日期：2026-03-31
- 状态：Draft
- 目标：分析现有 UI 控件库，识别缺口，规划补充方案

## 1. 现有控件盘点

### 1.1 已导出的控件（在 __init__.py 中）

| 控件名 | 用途 | 新设计中是否需要 |
|--------|------|-----------------|
| SearchInput | 搜索输入框 | ✓ 配置管理中搜索配置 |
| StyledComboBox | 下拉选择框 | ✓ 场景模板选择、数据源选择 |
| ThemedRadioButton | 单选按钮 | ✓ 覆盖策略选择 |
| ThemedSlider | 滑块 | ✓ 编号深度设置 |
| FontCombo | 字体选择 | ✗ 新设计中不需要 |
| SizeCombo | 尺寸选择 | ✗ 新设计中不需要 |
| NumberingPreset | 编号预设 | ✓ 标题编号方案选择 |
| SpacingInput | 间距输入 | ✗ 新设计中不需要 |

### 1.2 已实现但未导出的控件

| 控件名 | 用途 | 新设计中是否需要 |
|--------|------|-----------------|
| Card | 卡片容器 | ✓ 需要升级为支持选中态 |
| CollapsibleSection | 可折叠区域 | ✓ 高级功能折叠区 |
| ProgressIndicator | 进度指示器 | ✓ 执行进度条（需增强） |
| StatusIndicator | 状态指示器 | ✓ 模块状态、就绪状态 |
| FormRow | 表单行 | ✓ 各种配置项 |
| ToggleSwitch | 开关 | ✓ 功能开关、Strict Mode |
| IconButton | 图标按钮 | ✓ 各种操作按钮 |
| ModuleStepList | 模块步骤列表 | ✓ 可能复用于模块状态列表 |
| FolderPicker | 文件夹选择器 | ✓ 输出目录选择 |
| ColorPicker | 颜色选择器 | ✗ 新设计中不需要 |
| OverrideBadge | 覆盖标识 | ✓ 配置覆盖提示 |

### 1.3 对话框类控件

| 控件名 | 用途 | 新设计中是否需要 |
|--------|------|-----------------|
| BaseDialog | 对话框基类 | ✓ 可能需要 |
| ConfirmDialog | 确认对话框 | ✓ 删除配置确认 |
| ErrorDialog | 错误对话框 | ✓ 错误提示 |

## 2. 新设计需求 vs 现有控件

### 2.1 快速执行卡片需求

| 需求 | 现有控件 | 缺口 |
|------|---------|------|
| 文档选择器（拖拽+浏览） | FolderPicker（部分） | ✗ 需要新建 FileDropZone |
| 文档信息卡片 | Card | ✓ 可复用 |
| 场景模板下拉 | StyledComboBox | ✓ 可复用 |
| Strict Mode 开关 | ToggleSwitch | ✓ 可复用 |
| 高级功能折叠区 | CollapsibleSection | ✓ 可复用 |
| 功能开关+配置按钮 | - | ✗ 需要新建 FeatureToggleRow |
| 输出目录选择 | FolderPicker | ✓ 可复用 |
| 执行按钮 | QPushButton + 样式 | ✓ 可复用 |
| 就绪状态提示 | StatusIndicator | ✓ 可复用 |
| 实时进度条 | ProgressIndicator | △ 需要增强 |
| 模块状态列表 | ModuleStepList | △ 需要调整 |
| 日志流 | - | ✗ 需要新建 LogStreamWidget |

### 2.2 左侧导航需求

| 需求 | 现有控件 | 缺口 |
|------|---------|------|
| 动态导航栏容器 | - | ✗ 需要新建 DynamicNavigationRail |
| 导航卡片（可选中） | Card | △ 需要升级支持选中态 |
| 状态标识（badge） | OverrideBadge | △ 需要调整为通用 Badge |

### 2.3 配置管理卡片需求

| 需求 | 现有控件 | 缺口 |
|------|---------|------|
| 配置列表 | - | ✗ 需要新建 ConfigListWidget |
| 配置卡片 | Card | ✓ 可复用 |
| 搜索框 | SearchInput | ✓ 可复用 |
| 操作按钮组 | IconButton | ✓ 可复用 |

### 2.4 高级功能卡片需求

| 需求 | 现有控件 | 缺口 |
|------|---------|------|
| 编号方案选择 | NumberingPreset | ✓ 可复用 |
| 深度滑块 | ThemedSlider | ✓ 可复用 |
| 实时预览区 | - | ✗ 需要新建 PreviewPanel |
| 映射规则表格 | - | ✗ 需要新建 MappingTable |
| 模块列表（可拖拽） | ModuleStepList | △ 需要增强拖拽功能 |

## 3. 必须新建的控件

### 3.1 核心布局控件

#### DynamicNavigationRail
**职责：** 左侧动态导航栏容器

**功能：**
- 支持动态增减卡片
- 管理卡片选中状态
- 卡片间的切换动画

**API：**
```python
class DynamicNavigationRail(QWidget):
    card_selected = Signal(str)  # 卡片ID

    def add_card(self, card_id: str, card: NavigationCard)
    def remove_card(self, card_id: str)
    def select_card(self, card_id: str)
    def get_selected_card_id(self) -> str
```

#### NavigationCard (升级现有 Card)
**职责：** 左侧导航卡片

**新增功能：**
- 选中态样式（背景色、左边框）
- hover 态
- 状态标识位置（右上角 badge）
- 点击选中

**API：**
```python
class NavigationCard(Card):
    clicked = Signal()

    def set_selected(self, selected: bool)
    def set_badge(self, text: str, variant: str)  # variant: success/warning/error
    def set_subtitle(self, text: str)
```

### 3.2 输入控件

#### FileDropZone
**职责：** 文件拖拽+浏览选择器

**功能：**
- 支持拖拽文件
- 点击浏览文件
- 显示最近文件下拉
- 文件信息预览

**API：**
```python
class FileDropZone(QWidget):
    file_selected = Signal(str)  # 文件路径

    def set_file(self, path: str)
    def get_file_path(self) -> str
    def set_recent_files(self, files: list[str])
```

#### FeatureToggleRow
**职责：** 功能开关 + 配置按钮组合

**功能：**
- 勾选框 + 功能名称 + [配置] 按钮
- 勾选时启用配置按钮
- 取消勾选时禁用配置按钮

**API：**
```python
class FeatureToggleRow(QWidget):
    toggled = Signal(bool)
    config_clicked = Signal()

    def set_checked(self, checked: bool)
    def is_checked(self) -> bool
```

### 3.3 执行反馈控件

#### ExecutionProgressWidget
**职责：** 三合一执行反馈（进度条+模块状态+日志）

**功能：**
- 总体进度条
- 当前模块名称
- 模块状态列表
- 日志流（可折叠）

**API：**
```python
class ExecutionProgressWidget(QWidget):
    cancel_clicked = Signal()

    def set_progress(self, current: int, total: int, module: str)
    def update_module_status(self, module: str, status: str, progress: int)
    def append_log(self, level: str, message: str)
    def set_completed(self, success: bool, summary: dict)
```

#### ModuleStatusList
**职责：** 模块状态列表

**功能：**
- 显示所有模块及其状态
- 状态图标：等待/执行中/完成/失败
- 点击展开查看模块详细日志

**API：**
```python
class ModuleStatusList(QWidget):
    module_clicked = Signal(str)

    def add_module(self, module_id: str, name: str)
    def update_status(self, module_id: str, status: str, progress: int)
```

#### LogStreamWidget
**职责：** 日志流显示

**功能：**
- 实时滚动显示日志
- 日志级别筛选（全部/错误/警告/信息）
- 复制日志
- 导出日志

**API：**
```python
class LogStreamWidget(QWidget):
    def append_log(self, level: str, message: str, timestamp: str)
    def clear_logs(self)
    def set_filter(self, level: str)
    def export_logs(self, path: str)
```

### 3.4 配置管理控件

#### ConfigListWidget
**职责：** 配置列表

**功能：**
- 显示已保存的配置列表
- 每个配置显示：名称、描述、时间
- 操作按钮：加载、重命名、删除
- 搜索和排序

**API：**
```python
class ConfigListWidget(QWidget):
    config_loaded = Signal(str)  # 配置ID
    config_deleted = Signal(str)

    def add_config(self, config_id: str, name: str, desc: str, time: str)
    def remove_config(self, config_id: str)
    def set_search_text(self, text: str)
```

### 3.5 高级功能控件

#### MappingTable
**职责：** 映射规则配置表格

**功能：**
- 表格形式显示映射规则
- 支持添加/删除行
- 支持编辑单元格

**API：**
```python
class MappingTable(QWidget):
    mapping_changed = Signal()

    def add_row(self, source: str, target: str)
    def remove_row(self, index: int)
    def get_mappings(self) -> list[dict]
```

#### PreviewPanel
**职责：** 实时预览面板

**功能：**
- 显示配置效果预览
- 支持不同类型的预览（文本、列表等）

**API：**
```python
class PreviewPanel(QWidget):
    def set_preview_content(self, content: str, content_type: str)
```

## 4. 需要升级的现有控件

### 4.1 Card → NavigationCard
**升级内容：**
- 添加选中态样式
- 添加 hover 态
- 添加 badge 支持
- 添加点击事件

### 4.2 ProgressIndicator → ExecutionProgressWidget
**升级内容：**
- 集成模块状态列表
- 集成日志流
- 支持完成后的结果摘要

### 4.3 ModuleStepList → DraggableModuleList
**升级内容：**
- 添加拖拽排序功能
- 添加勾选框（启用/禁用）
- 添加依赖关系提示

## 5. 前瞻性控件建议

### 5.1 通用基础控件

#### Badge
**职责：** 通用标识组件

**用途：**
- 状态标识（成功/警告/错误）
- 数量标识
- 新功能标识

**优先级：** 高

#### EmptyState
**职责：** 空状态占位

**用途：**
- 无配置时的提示
- 无历史记录时的提示
- 无数据时的引导

**优先级：** 中

#### Tooltip
**职责：** 工具提示

**用途：**
- 功能说明
- 快捷键提示
- 错误原因说明

**优先级：** 中

### 5.2 高级交互控件

#### SplitPane
**职责：** 可调整大小的分割面板

**用途：**
- 左右分栏的尺寸调整
- 日志区域的高度调整

**优先级：** 低

#### ContextMenu
**职责：** 右键菜单

**用途：**
- 配置列表的右键操作
- 日志的右键复制

**优先级：** 低
#### Notification / Toast
**职责：** 轻量级通知

**用途：**
- 配置保存成功提示
- 执行完成通知
- 错误提示

**优先级：** 中

### 5.3 数据展示控件

#### Timeline
**职责：** 时间线展示

**用途：**
- 执行历史的时间线视图
- 配置修改历史

**优先级：** 低

#### DataTable
**职责：** 通用数据表格

**用途：**
- 映射规则表格
- 执行历史列表
- 配置对比

**优先级：** 中

## 6. 控件开发优先级

### 6.1 P0 - 必须立即开发（阻塞新设计）

1. **DynamicNavigationRail** - 核心布局
2. **NavigationCard** - 核心布局
3. **FileDropZone** - 快速执行核心功能
4. **FeatureToggleRow** - 快速执行核心功能
5. **ExecutionProgressWidget** - 执行反馈核心

### 6.2 P1 - 高优先级（影响体验）

6. **ModuleStatusList** - 执行反馈
7. **LogStreamWidget** - 执行反馈
8. **ConfigListWidget** - 配置管理
9. **Badge** - 通用组件

### 6.3 P2 - 中优先级（增强功能）

10. **MappingTable** - 内容填充功能
11. **PreviewPanel** - 标题编号预览
12. **DraggableModuleList** - 模块控制
13. **EmptyState** - 空状态提示
14. **Notification** - 操作反馈

### 6.4 P3 - 低优先级（未来增强）

15. **SplitPane** - 布局优化
16. **ContextMenu** - 交互增强
17. **Timeline** - 历史可视化
18. **DataTable** - 通用表格


## 7. 实施建议

### 7.1 控件开发顺序

**Phase 1: 核心布局（1-2 周）**
- DynamicNavigationRail
- NavigationCard（升级 Card）
- 基础样式和主题支持

**Phase 2: 快速执行（2 周）**
- FileDropZone
- FeatureToggleRow
- 集成现有控件（StyledComboBox, ToggleSwitch, FormRow）

**Phase 3: 执行反馈（2 周）**
- ExecutionProgressWidget
- ModuleStatusList
- LogStreamWidget

**Phase 4: 配置管理（1 周）**
- ConfigListWidget
- Badge

**Phase 5: 高级功能（2-3 周）**
- MappingTable
- PreviewPanel
- DraggableModuleList

### 7.2 控件复用策略

**直接复用（无需修改）：**
- StyledComboBox
- ThemedRadioButton
- ThemedSlider
- ToggleSwitch
- FormRow
- IconButton
- SearchInput
- FolderPicker
- CollapsibleSection

**轻度调整后复用：**
- Card → NavigationCard（添加选中态）
- ProgressIndicator → ExecutionProgressWidget（集成模块状态和日志）
- ModuleStepList → DraggableModuleList（添加拖拽）
- OverrideBadge → Badge（泛化为通用组件）

**需要新建：**
- DynamicNavigationRail
- FileDropZone
- FeatureToggleRow
- ModuleStatusList
- LogStreamWidget
- ConfigListWidget
- MappingTable
- PreviewPanel


### 7.3 __init__.py 导出更新

当前 `src/shared/ui/__init__.py` 只导出了 10 个组件，但实际有 30+ 个组件。

**建议：**
1. 将所有稳定的共享组件都添加到 `__all__`
2. 按类别组织导出（布局、输入、反馈、对话框等）
3. 新开发的组件从一开始就加入导出列表

## 8. 控件设计原则

### 8.1 一致性原则

- 所有控件使用统一的主题系统（`bind_theme`）
- 统一的尺寸规范（高度、间距、圆角）
- 统一的颜色语义（primary/success/warning/error）

### 8.2 可组合性原则

- 控件职责单一，易于组合
- 通过信号/槽机制通信
- 避免控件间的强耦合

### 8.3 可扩展性原则

- 预留扩展接口
- 支持自定义样式
- 支持插槽（slot）机制

## 9. 总结

### 9.1 现状

- 现有 30+ 个 UI 控件，但只有 10 个被导出
- 大部分基础控件已经具备，但缺少新设计所需的专用控件
- 现有控件质量较高，可以直接复用或轻度调整

### 9.2 缺口

**必须新建的控件（8 个）：**
1. DynamicNavigationRail
2. FileDropZone
3. FeatureToggleRow
4. ExecutionProgressWidget
5. ModuleStatusList
6. LogStreamWidget
7. ConfigListWidget
8. MappingTable

**需要升级的控件（4 个）：**
1. Card → NavigationCard
2. ProgressIndicator → ExecutionProgressWidget
3. ModuleStepList → DraggableModuleList
4. OverrideBadge → Badge

### 9.3 前瞻性建议

**通用基础控件（优先级中）：**
- Badge（已有 OverrideBadge，需泛化）
- EmptyState
- Tooltip
- Notification

**高级交互控件（优先级低）：**
- SplitPane
- ContextMenu
- Timeline
- DataTable

这些控件不是新设计的必需品，但可以提升整体体验，建议在核心功能完成后逐步补充。

