# StyleSourceSlot 来源槽位接入记录

日期：2026-06-30

后续追加：本轮已继续把模板管理概览、场景概览、Workbench 执行前复核三个来源入口都迁移到 `StyleSourceSlot`。文件名保留“执行前复核”，但本文记录的是三入口来源槽位收束。

后续进展：`StylePolicyControlDeck` 已作为通用策略控制外壳落地，详见 `docs/refactor-records/StylePolicyControlDeck抽象接入记录_2026-06-30.md`。

## 1. 本轮目标

上一轮已经把执行前复核接入了统一样式对象：

```text
QuickExecutionDetail
-> build_execution_prereview_style_projection(...)
-> StyleObjectProjection(source + difference)
-> StyleManagementBlock.apply_style_object_projection(...)
```

但当时 source slot 仍然是一个普通 `QWidget` 容器：

```text
普通 QWidget
-> 场景/模板选择行
-> StyleSourceCompactRow
```

因此 `StyleManagementBlock` 只能在容器里查找第一个支持 `apply_projection(...)` 的子控件。这个行为能跑通，但边界不够干净：

- block 知道 source slot 可能只是一个容器。
- 页面仍然直接构造并连接 `StyleSourceCompactRow`。
- 后续若要把模板管理、场景规划、执行前复核统一成同一套样式对象语法，source slot 还缺少明确契约。

本轮目标是新增显式槽位，并先接入执行前复核：

```text
StyleSourceSlot
-> apply_projection(...)
-> 内部承载 StyleSourceCompactRow
-> 可插入上下文控件，例如场景/模板选择行
```

## 2. 新增共享控件

新增文件：

```text
src/shared/ui/style_source_slot.py
```

新增类：

```python
StyleSourceSlot
```

它的职责是：

- 作为 `StyleManagementBlock.source_slot` 的稳定承载控件。
- 公开 `apply_projection(...)`，让 block 不需要知道内部 row。
- 内部默认创建 `StyleSourceCompactRow`。
- 转发 `navigate_requested`。
- 允许通过 `add_context_widget(...)` 插入上下文控件。

当前执行前复核用它插入：

```text
场景/模板选择行
StyleSourceCompactRow
```

这样视觉结构不变，但对象边界变清晰。

## 3. QuickExecutionDetail 迁移

涉及文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

迁移前：

```text
_style_prereview_source_slot = QWidget(...)
QVBoxLayout(_style_prereview_source_slot)
source_slot_layout.addWidget(selector_row)
_style_source_row = StyleSourceCompactRow(...)
source_slot_layout.addWidget(_style_source_row)
```

迁移后：

```text
_style_prereview_source_slot = StyleSourceSlot(...)
_style_prereview_source_slot.add_context_widget(selector_row)
_style_source_row = _style_prereview_source_slot.source_row
```

导航连接也从 row 上移到 slot：

```text
StyleSourceSlot.navigate_requested
-> QuickExecutionDetail._on_style_source_navigation_requested(...)
```

这意味着页面仍可保留 `_style_source_row` 作为兼容观察点，但实际交互边界已经变成 slot。

## 4. 模板管理概览迁移

涉及文件：

```text
src/ui/panels/template_panel.py
```

迁移前：

```text
_style_source_row = StyleSourceCompactRow(...)
_selector_card.add_widget(_style_source_row)
_style_source_row.apply_projection(...)
```

迁移后：

```text
_style_source_slot = StyleSourceSlot(...)
_style_source_row = _style_source_slot.source_row
_selector_card.add_widget(_style_source_slot)
_style_source_slot.apply_projection(...)
```

模板概览仍然展示同一行：

```text
样式来源 / 模板基线 / 模板：默认格式，作为样式基线 / 场景分区：默认跟随此模板
```

但投影入口已经从 row 升级到 slot。

## 5. 场景概览迁移

涉及文件：

```text
src/ui/panels/scene_panel.py
```

迁移前：

```text
_setting_rows["style_source"] = StyleSourceCompactRow(...)
```

迁移后：

```text
_setting_rows["style_source"] = StyleSourceSlot(...)
```

为保持概览层原有摘要读取方式，`StyleSourceSlot` 新增：

```python
summary_text()
```

该方法委托内部 `StyleSourceCompactRow.summary_text()`，因此场景概览收集首屏文本时，不需要知道样式来源行已经变成 slot。

## 6. 对 StyleManagementBlock 的意义

这轮没有移除 `StyleManagementBlock._apply_slot_projection(...)` 的递归兼容路径，因为历史页面可能仍会把普通容器作为 slot。

但三个主要来源入口已经不再依赖直接 row 投影：

```text
StyleManagementBlock.apply_style_object_projection(...)
-> _apply_slot_projection(source_slot, source_projection)
-> StyleSourceSlot.apply_projection(...)
-> StyleSourceCompactRow.apply_projection(...)
```

后续可以继续评估是否收紧递归 fallback。

## 7. 测试更新

新增/更新测试：

```text
tests/test_small_widget_architecture.py
tests/test_quick_execution_detail_architecture.py
tests/test_ui_exports.py
tests/test_template_panel_architecture.py
tests/test_scene_panel_architecture.py
```

新增覆盖点：

- `StyleSourceSlot` 能包装 `StyleSourceCompactRow`。
- `StyleSourceSlot.add_context_widget(...)` 会把上下文控件放在来源行前面。
- `StyleSourceSlot.apply_projection(...)` 会更新内部 row。
- `StyleSourceSlot` 会转发 `navigate_requested`。
- `StyleSourceSlot` 通过 `src.shared.ui` 导出。
- `QuickExecutionDetail._style_prereview_source_slot` 是 `StyleSourceSlot`。
- 执行前复核源码不再出现 `QVBoxLayout(self._style_prereview_source_slot)`。
- 执行前复核仍不直接调用 `_style_source_row.apply_projection(...)`。
- 模板概览 `_style_source_slot` 是 `StyleSourceSlot`。
- 模板概览不再直接调用 `_style_source_row.apply_projection(...)`。
- 场景概览 `_setting_rows["style_source"]` 是 `StyleSourceSlot`。
- 场景概览仍可通过 `summary_text()` 汇总首屏可读文本。
- `scene_panel.py` 不再直接创建 `StyleSourceCompactRow(...)`。

## 8. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_source_slot.py src\shared\ui\__init__.py src\ui\panels\workbench\quick_execution_detail.py tests\test_small_widget_architecture.py tests\test_quick_execution_detail_architecture.py tests\test_ui_exports.py
```

结果：通过。

追加执行三入口语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_source_slot.py src\ui\panels\template_panel.py src\ui\panels\scene_panel.py tests\test_template_panel_architecture.py tests\test_scene_panel_architecture.py
```

结果：通过。

已执行聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_source_slot_wraps_compact_row_context_and_projection tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
3 passed in 1.42s
```

追加执行三入口聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_template_panel_architecture.py::test_template_panel_overview_uses_shared_style_source_row_for_baseline tests\test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests\test_scene_panel_architecture.py::test_scene_panel_overview_shows_planning_family_governance tests\test_scene_panel_architecture.py::test_scene_panel_overview_actions_emit_contextual_navigation_intents tests\test_scene_panel_architecture.py::test_scene_panel_template_preview_summary_renders_without_overlap_at_narrow_width tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_small_widget_architecture.py::test_style_source_slot_wraps_compact_row_context_and_projection -q
```

结果：

```text
7 passed in 5.70s
```

已执行相关架构回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_quick_execution_detail_architecture.py tests\test_ui_exports.py tests\test_design_system_refactor.py::test_quick_execution_plain_card_headers_use_design_system_card_slots -q
```

结果：

```text
90 passed in 50.43s
```

追加执行共享小控件、执行前详情、模板概览和导出回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_quick_execution_detail_architecture.py tests\test_template_panel_architecture.py tests\test_ui_exports.py -q
```

结果：

```text
103 passed in 22.54s
```

追加执行完整场景架构回归：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
59 passed in 56.16s
```

## 9. 当前边界状态

已经改善：

- 执行前复核 source slot 从普通容器升级为明确控件。
- 模板管理概览来源行从 row 升级为 slot。
- 场景概览来源行从 row 升级为 slot。
- 页面层不再手动给 source row 建布局。
- source 投影有了稳定落点。
- `StyleSourceCompactRow` 继续作为渲染行复用，不破坏既有视觉。

仍未完成：

- `StyleManagementBlock._apply_slot_projection(...)` 仍保留递归兼容。
- `StylePreviewSurface` 已落地，并已接入模板概览、场景分区与执行前复核。
- `StylePolicyControlDeck` 已落地，但尚未由模板管理或执行前复核实际消费。

## 10. 下一步建议

下一轮可以沿两条线选一条继续：

```text
线 A：收紧 StyleManagementBlock._apply_slot_projection(...) 的递归兼容边界。
线 B：新增 StylePreviewSurface，统一模板正文、场景分区和执行前复核的预览外壳。
```

如果目标是尽快让用户感知“更说人话”，优先线 B；如果目标是继续收窄架构边界，优先线 A。
