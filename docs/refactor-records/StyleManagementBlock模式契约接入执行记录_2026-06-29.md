# StyleManagementBlock 模式契约接入执行记录

日期：2026-06-29

## 1. 本轮目标

上一轮已经把 Workbench 执行后的样式来源回执闭合。本轮继续推进另一条 P0：`StyleManagementBlock` 虽然已经是模板正文和场景分区样式的共享块，但调用方仍然通过一组自由布尔参数决定是否显示 owner、preview、恢复动作和只读折叠。

这种写法的风险是：

```text
控件被复用了，但页面模式没有被复用。
后续新增入口时，很容易再拼出一套“看起来相似但行为不一致”的样式管理块。
```

本轮目标是把“模板基线编辑”和“场景分区样式”两种组合方式命名为稳定模式契约。

## 2. 本轮代码落点

### 2.1 新增共享模式契约

文件：

- `src/shared/ui/style_management_block.py`

新增：

- `StyleManagementContract`
- `STYLE_MANAGEMENT_CONTRACTS`
- `style_management_contract(mode)`

当前模式：

| mode | 用途 | owner toolbar | owner status | preview | readonly 折叠 |
| --- | --- | --- | --- | --- | --- |
| `custom` | 兼容自由配置 | 开 | 开 | 开 | 否 |
| `template_baseline_edit` | 模板正文基线编辑 | 关 | 开 | 关 | 否 |
| `scene_section_rules` | 场景分区样式规则 | 开 | 开 | 开 | 是 |
| `readonly_review` | 后续只读复核/回执预留 | 关 | 开 | 开 | 是 |

`StyleManagementBlock` 现在支持：

```python
StyleManagementBlock(..., mode="template_baseline_edit")
StyleManagementBlock(..., mode="scene_section_rules")
```

仍保留旧参数覆盖能力，避免一次性破坏已有调用。

### 2.2 模板正文排版接入模式

文件：

- `src/ui/panels/template_style_detail.py`

变更：

```python
StyleManagementBlock(
    ...,
    mode="template_baseline_edit",
)
```

替代原来的：

```python
show_owner_toolbar=False
show_preview=False
```

意义：

模板正文页不再手工关闭局部控件，而是声明自己属于“模板基线编辑”模式。

### 2.3 场景分区样式接入模式

文件：

- `src/ui/panels/scene_style_override_sections.py`

变更：

```python
StyleManagementBlock(
    ...,
    mode="scene_section_rules",
)
```

替代原来的：

```python
owner_title="编辑样式"
selector_label="编辑分区"
action_label="恢复模板"
collapse_surface_when_readonly=True
```

意义：

分区样式页不再手工描述“编辑分区 / 恢复模板 / 只读折叠”，而是声明自己属于“场景分区样式规则”模式。

### 2.4 共享 UI 导出

文件：

- `src/shared/ui/__init__.py`

新增导出：

- `StyleManagementContract`
- `style_management_contract`

这样后续页面或测试可以通过共享 UI 入口消费契约。

## 3. 本轮测试

新增/扩展：

- `tests/test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts`
- `tests/test_template_style_detail.py::test_style_detail_syncs_widget_values_from_template`
- `tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface`

验证点：

- `template_baseline_edit` 默认隐藏 owner toolbar 和 preview，但保留 owner status。
- `scene_section_rules` 默认显示 owner toolbar、preview，恢复按钮文案为 `恢复模板`。
- `scene_section_rules` 在跟随模板只读态会折叠字段表单。
- 模板正文页实际挂载 `style_management_mode=template_baseline_edit`。
- 场景分区样式页实际挂载 `style_management_mode=scene_section_rules`。

已运行：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_management_block.py src/shared/ui/__init__.py src/ui/panels/template_style_detail.py src/ui/panels/scene_style_override_sections.py tests/test_small_widget_architecture.py tests/test_template_style_detail.py tests/test_scene_panel_architecture.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests/test_small_widget_architecture.py::test_style_management_block_wraps_summary_controls_preview_and_surface tests/test_template_style_detail.py::test_style_detail_syncs_widget_values_from_template tests/test_template_style_detail.py::test_style_detail_reuses_shared_controls tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface -q
```

结果：

```text
5 passed
```

宽一点的相关回归：

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py tests/test_template_style_detail.py tests/test_scene_panel_architecture.py -q
```

结果：

```text
100 passed
```

共享 UI 导出回归：

```powershell
python -X utf8 -m pytest tests/test_ui_exports.py -q
```

结果：

```text
1 passed
```

## 4. 当前边界

本轮没有做大幅视觉重排，也没有把分区独立样式开关和差异条抽成 `StyleRuleControlDeck`。原因是当前 P0 要先解决“同一个共享块在不同入口下如何声明模式”的问题。

后续仍需要继续推进：

1. 抽 `StyleRuleControlDeck`，收束独立样式开关、差异条、全部跟随模板和撤销恢复。
2. 将 `readonly_review` 接入后续执行回执/只读复核场景。
3. 泛化 `TemplateSummaryCard` 命名，降低模板专属命名对场景/Workbench 的误导。
4. 做截图审计，确认模式化后模板正文和场景分区样式仍保持预期视觉节奏。

## 5. 本轮判断

这一轮把 `StyleManagementBlock` 从“共享容器”推进成“共享模式契约”的第一步。以后模板页和场景页不再各自拼 owner、preview、恢复按钮和只读折叠，而是选择明确模式。

这不会立刻让界面变成最终优秀形态，但它把后续优化的边界钉住了：样式管理块的复用不再只靠控件名称相同，而是靠模式语义相同。
