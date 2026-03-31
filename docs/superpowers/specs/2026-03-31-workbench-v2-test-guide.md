# Workbench V2 测试说明

## 已完成功能

### 1. 核心 UI 控件
- ✅ NavigationCard - 导航卡片
- ✅ DynamicNavigationRail - 动态导航栏
- ✅ FileDropZone - 文件拖拽选择
- ✅ FeatureToggleRow - 功能开关行

### 2. 快速执行卡片
- ✅ 输入文档区（拖拽+浏览）
- ✅ 场景模板选择
- ✅ Strict Mode 开关
- ✅ 高级功能折叠区（5个功能开关）
- ✅ 输出文档配置
- ✅ 执行按钮和状态提示

### 3. 布局
- ✅ Master-Detail 左右布局
- ✅ 左侧导航栏（220px 固定宽度）
- ✅ 右侧详情区（可滚动）

## 如何测试

### 方法 1: 直接替换
在主窗口中替换旧面板：
```python
# 修改 src/ui/main_window.py 或相应的面板注册位置
from src.ui.panels.workbench.panel_v2 import WorkbenchPanelV2 as WorkbenchPanel
```

### 方法 2: 并行测试
保留旧面板，添加新面板作为独立标签页

## 当前状态

**可用功能：**
- 左侧导航卡片切换
- 快速执行卡片的所有 UI 元素
- 文件拖拽选择
- 高级功能开关

**待实现：**
- 执行逻辑集成
- 执行反馈（进度条+模块状态+日志）
- 配置管理功能
- 动态高级功能卡片
- 功能开关与左侧卡片的联动

## 下一步

按照优先级：
1. 实现执行反馈控件（ExecutionProgressWidget）
2. 集成现有的 ExecutionWorker
3. 实现配置管理
4. 实现动态卡片系统
