# Workbench 样式来源共享控件接入执行记录（2026-06-29）

后续进展：模板管理概览也已接入同一套 `StyleSourceProjection + StyleSourceCompactRow`，样式来源链路已从模板源头、场景概览到 Workbench 执行前形成第一轮闭环，详见 `docs/refactor-records/模板管理样式来源共享控件闭环执行记录_2026-06-29.md`。

## 1. 本轮继续推进的问题

前两轮已经完成：

- `StyleSourceProjection`：统一“模板基线 + 分区状态 + 双动作”的数据投影。
- `StyleSourceCompactRow`：统一“样式来源”的紧凑 UI 控件。
- 场景概览接入共享控件。

但 Workbench 快速执行页仍然没有接入同一套表达。用户在执行前只能看到：

- `场景与模板` 两个下拉框。
- `高级调整` 标题行里一条很长的运行摘要。

这导致执行链路和场景规划仍不够一致：场景概览已经能清楚看到“模板：... / 分区：...”，到了 Workbench 又退回成另一个表达系统。

本轮把 Workbench 快速执行页也接入 `StyleSourceProjection + StyleSourceCompactRow`。

## 2. 设计目标

Workbench 不做样式编辑，它只做执行前确认。因此这里的样式来源行应是只读确认 + 定位入口：

```text
模板：默认流程
分区：全部分区跟随模板
```

如果场景存在分区独立样式：

```text
模板：默认流程
分区：1 个分区使用独立样式：参考文献
```

按钮语义保持与场景概览一致：

| 按钮 | Workbench 中的行为 |
| --- | --- |
| 看模板 | 走现有修复/定位路由到模板页 |
| 调分区 | 走现有修复/定位路由到场景分区样式页 |

不新增导航协议，直接复用 Workbench 已有的 `issue_repair_requested` 链路。

## 3. 已执行代码改动

### 3.1 快速执行页引入共享控件和投影

文件：`src/ui/panels/workbench/quick_execution_detail.py`

新增导入：

- `StyleSourceCompactRow`
- `build_style_source_projection`

### 3.2 场景与模板卡增加样式来源行

在 `_build_scene_section()` 中，两个下拉框下方新增：

```text
self._style_source_row = StyleSourceCompactRow(...)
```

它被加入 `场景与模板` 卡，位于场景/模板选择之后。

### 3.3 同步样式来源状态

新增：

```text
_sync_style_source_row()
```

同步时使用：

```text
build_style_source_projection(
    self._current_scene,
    template_label=self._active_template_label(),
)
```

同步触发点：

- `_apply_scene()`
- `_on_zone_toggled()`
- `_set_current_template_id()`
- `set_strategy_context()`

这样外部场景切换、模板切换、legacy 策略设置都会刷新 Workbench 的样式来源行。

### 3.4 双动作接入既有路由

新增：

```text
_on_style_source_navigation_requested()
```

路由规则：

| target_card_id | 发出的 Workbench 定位请求 |
| --- | --- |
| `tpl_*` | `issue_repair_requested("template", "")` |
| `scn_style_rules` | `issue_repair_requested("scene_style_field", "scene.section_styles.*.line_spacing_pt")` |
| 其他 `scn_*` | `issue_repair_requested("scene", "")` |

其中：

- `template` 已由 Workbench 导航注册表映射到 `tpl_overview`。
- `scene_style_field` 已映射到 `scn_style_rules`。

## 4. 测试补充

文件：`tests/test_quick_execution_detail_architecture.py`

新增：

```text
test_quick_execution_detail_uses_shared_style_source_row
```

覆盖：

- `_style_source_row` 是 `StyleSourceCompactRow`。
- Workbench 显示模板线。
- Workbench 显示分区线。
- 独立分区显示为 `分区：1 个分区使用独立样式：参考文献`。
- 双按钮为 `看模板 / 调分区`。
- 点击按钮后发出既有定位请求。

同时扩展现有状态测试：

- `set_strategy_context(template_name="汇报演示")` 后，样式来源模板线也同步为 `模板：汇报演示...`。

## 5. 已验证

编译检查：

```powershell
python -X utf8 -m py_compile src/ui/panels/workbench/quick_execution_detail.py tests/test_quick_execution_detail_architecture.py
```

结果：通过。

聚焦回归：

```powershell
python -X utf8 -m pytest tests/test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests/test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_radio_controls tests/test_quick_execution_detail_architecture.py::test_quick_execution_detail_reports_presenter_derived_status_and_snapshot tests/test_workbench_detail_architecture.py::test_workbench_panel_routes_issue_repair_targets_to_existing_surfaces -q
```

结果：

```text
4 passed
```

Workbench 快速执行与导航相关回归：

```powershell
python -X utf8 -m pytest tests/test_quick_execution_detail_architecture.py tests/test_quick_execution_presenter.py tests/test_workbench_detail_architecture.py::test_workbench_panel_routes_issue_repair_targets_to_existing_surfaces tests/test_workbench_detail_architecture.py::test_workbench_panel_round_trips_active_issue_from_repair_navigation tests/test_workbench_issue_navigation.py -q
```

结果：

```text
65 passed
```

场景、共享控件、Workbench 与文案护栏合并回归：

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py tests/test_scene_overview_projection.py tests/test_scene_panel_architecture.py tests/test_ui_copy_guardrails.py tests/test_quick_execution_detail_architecture.py tests/test_quick_execution_presenter.py tests/test_workbench_issue_navigation.py -q
```

结果：

```text
151 passed
```

旧样式实现词和坏清洗结果检索：

结果：在 `src/ui`、`src/shared`、`src/config`、Workbench 相关测试与场景相关测试中无命中。

## 6. 当前边界

已完成：

- Workbench 快速执行页接入共享样式来源控件。
- Workbench 使用当前执行页可见模板名，而不是硬编码模板库名称。
- `看模板 / 调分区` 通过既有定位链路跳转。
- 场景概览与 Workbench 的样式来源表达开始统一。

未完成：

- 模板管理概览已接入 `StyleSourceCompactRow`，但字段级差异投影和真实窗口视觉验证仍待继续。
- Workbench 的样式来源行还没有隐藏/只读模式配置，当前仍显示两个定位按钮。
- `diff_tags` 仍是独立分区名称，不是字段级差异。
- 真实 Windows 窗口截图仍未补。

## 7. 下一步建议

### P2：模板管理概览深化

模板管理的“当前模板”区域已经使用同一套控件。后续重点不再是“有没有这张行”，而是继续补字段级差异、显式模式和真实窗口视觉验证。

### P2：控件模式深化

后续已给 `StyleSourceProjection` 增加 `view_mode`，当前模式包括：

- `readonly`：只显示模板和分区状态。
- `template_baseline`：模板管理概览使用，只显示模板侧动作。
- `scene_editable`：场景概览使用，显示模板和分区动作。
- `execution_review`：Workbench 使用；有独立分区时显示分区定位，全部跟随模板时只保留模板定位。

后续已补 Qt offscreen 三入口视觉审计，并继续压缩长模板摘要、隐藏 Workbench 跟随模板时的分区动作、把场景双按钮改成宽屏横排，详见 `docs/refactor-records/样式来源三入口视觉审计执行记录_2026-06-29.md`、`docs/refactor-records/样式来源摘要压缩与执行复核减负记录_2026-06-29.md` 与 `docs/refactor-records/样式来源双动作响应式布局减负记录_2026-06-29.md`。剩余工作是真实 Windows 字体和第一屏节奏验证，而不是继续增加说明文本。

### P2：字段级差异投影

将 `diff_tags` 从分区名称升级为字段差异，如字体、字号、缩进、行距。

## 8. 当前判断

这轮把样式来源链路从“场景概览统一”推进到“执行前检查统一”。后续模板管理概览也已接入同一控件，链路比之前更连续，边界也更清楚：模板管理定义基线，场景表达偏离，Workbench 负责确认和定位。
