# DetailSummaryCard 通用摘要卡命名边界执行记录

日期：2026-06-29

## 1. 本轮目标

前几轮已经把样式管理链路推进到：

- `StyleManagementBlock` 模式契约
- `StyleRuleControlDeck` 分区样式规则控制区
- `StyleResultReceiptRow` 执行后样式回执

但还有一个命名边界问题：`StyleManagementBlock` 已经服务模板正文和场景分区样式，却仍直接实例化 `TemplateSummaryCard`。这会让后续新增场景页或 Workbench 页误以为“详情摘要卡是模板专属组件”，继续造成命名和心理模型分叉。

本轮目标不是全仓库大改名，而是先给跨模板/场景共享模块一个通用入口：

```text
DetailSummaryCard：通用详情摘要卡
TemplateSummaryCard：模板详情页兼容名称
```

## 2. 本轮代码落点

### 2.1 新增 DetailSummaryCard

文件：

- `src/shared/ui/template_summary_card.py`

变更：

- 新增 `DetailSummaryCard`，承载原摘要卡实现。
- `TemplateSummaryCard(DetailSummaryCard)` 保留旧名称兼容。
- 新增 `apply_detail_summary_action_button`，承载通用详情摘要卡按钮样式。
- `apply_template_summary_action_button = apply_detail_summary_action_button` 保留旧名称兼容。
- `__all__` 同时导出 `DetailSummaryCard`、`TemplateSummaryCard` 和两个按钮样式入口。

判断：

这样做避免一次性改动所有模板详情页，同时让新共享模块可以使用更准确的通用名称。

### 2.2 StyleManagementBlock 使用通用名称

文件：

- `src/shared/ui/style_management_block.py`

变更：

```python
from src.shared.ui.template_summary_card import DetailSummaryCard

self._card = DetailSummaryCard(...)
```

替代原来的：

```python
TemplateSummaryCard(...)
```

意义：

`StyleManagementBlock` 是跨模板/场景的共享结构，使用 `DetailSummaryCard` 能表达“详情摘要卡”而不是“模板摘要卡”。

### 2.3 共享 UI 导出

文件：

- `src/shared/ui/__init__.py`

新增导出：

- `DetailSummaryCard`

## 3. 本轮测试

新增/更新：

- `tests/test_summary_grid.py::test_template_summary_card_keeps_detail_summary_card_compatibility`
- `tests/test_template_style_detail.py::test_style_detail_reuses_shared_controls`
- `tests/test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout`
- `tests/test_ui_exports.py`

验证点：

- `TemplateSummaryCard` 仍是 `DetailSummaryCard` 的兼容子类。
- `StyleManagementBlock` 源码中使用 `DetailSummaryCard`。
- `StyleManagementBlock` 源码中不再直接实例化 `TemplateSummaryCard`。
- 共享 UI 导出包含 `DetailSummaryCard`。
- `StyleRuleControlDeck` 使用 `apply_detail_summary_action_button`，不再依赖模板专属按钮样式命名。

已运行：

```powershell
python -X utf8 -m py_compile src/shared/ui/template_summary_card.py src/shared/ui/style_management_block.py src/shared/ui/__init__.py tests/test_template_style_detail.py tests/test_scene_panel_architecture.py tests/test_summary_grid.py tests/test_ui_exports.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_summary_grid.py::test_template_summary_card_keeps_detail_summary_card_compatibility tests/test_template_style_detail.py::test_style_detail_reuses_shared_controls tests/test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests/test_ui_exports.py -q
```

结果：

```text
4 passed
```

## 4. 当前边界

本轮没有把所有模板详情页中的 `TemplateSummaryCard` 改成 `DetailSummaryCard`。原因：

- 模板详情页继续使用 `TemplateSummaryCard` 是语义正确的。
- 大量旧测试和模板面板逻辑依赖 `_summary_card` 与模板详情页命名，强行全量改名收益不高。
- 当前真正跨域复用的是 `StyleManagementBlock`，先改它更符合风险控制。

后续可以逐步推进：

1. 新增场景/Workbench 详情页时优先使用 `DetailSummaryCard`。
2. 如发现非模板模块仍直接使用 `TemplateSummaryCard`，改为 `DetailSummaryCard`。
3. `TemplateSummaryHeader` 已在后续泛化为 `DetailSummaryHeader`，旧名作为同对象别名保留。

## 5. 本轮判断

这一轮不是视觉变化，而是命名边界修正。它让“模板详情摘要卡”的成熟样式可以继续被复用，但跨模板/场景的共享模块不再背着模板专属名字。

这能减少后续开发时的误判：`StyleManagementBlock` 的摘要结构属于通用详情页能力，而不是模板管理私有能力。
