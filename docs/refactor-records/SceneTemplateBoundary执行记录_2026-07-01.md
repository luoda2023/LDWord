# Scene / Template 边界执行记录

日期：2026-07-01

关联记录：

- `docs/refactor-records/SceneTemplateBoundary边界确认记录_2026-07-01.md`
- `docs/audits/SceneTemplateBoundary修复方案_2026-07-01.md`

## 1. 本轮结论

本轮最终确认的程序边界是：

```text
模板：定义文档结构、章节识别、默认格式。
场景：定义这次任务怎么做、处理到什么程度、是否有格式例外。
运行时：把模板结构识别到当前文档，再按场景策略执行。
```

因此，场景页不再把正文、参考文献、附录、摘要、目录等硬编码区域当成主路径展示。那些名称属于模板结构和运行时识别结果，不属于场景重新定义。

## 2. 已落地修复

### 2.1 新增场景作用边界

新增 `SceneApplicationBoundaryConfig`：

```python
mode: follow_template | body_only | full_document | confirm_before_apply
confirm_before_apply: bool
```

它只表达高层任务边界：

- 跟随模板默认
- 仅正文
- 全文
- 执行前确认

它不创建章节，也不解释“什么是参考文献/附录/摘要”。

### 2.2 保留旧 `format_scope`，但降级为兼容层

`format_scope.sections` 仍保留，原因是执行中心、旧场景配置和部分诊断队列仍依赖旧字段。

新的解释是：

```text
format_scope.sections 是旧场景的处理门禁兼容字段。
它不能再作为场景页的章节定义来源。
```

迁移层会从旧 `format_scope` 推断新的 `application_boundary`，避免旧配置直接失效。

### 2.3 场景 UI 主路径改名

场景主路径已收敛为：

- `处理范围` -> `作用边界`
- `分区样式` -> `格式例外`
- `格式与模板` -> `场景策略`
- `套用格式` -> `套用模板`

同时移除了场景概览里容易让用户误解的 `核对依据` 主路径。

### 2.4 作用边界不再展示 9 个硬编码区域

`SceneScopeZoneSection` 现在展示高层边界模式控件。

旧的区域 checklist 仍在内部保留，但主界面隐藏，用于兼容旧信号和旧测试路径。

### 2.5 格式例外不再被旧处理范围反向控制

本轮明确了一个关键边界：

```text
section_styles 是格式例外。
format_scope.sections 是旧处理门禁。
旧门禁不能决定格式例外是否存在。
```

所以关闭旧 `format_scope.sections["references"]` 不会自动让 `references_body` 的格式例外消失。格式例外只表达“这个模板识别出的结构需要局部不同格式”。

### 2.6 文案清理

主路径里已去掉容易混淆的表达：

- 不再使用“先在处理范围中启用某分区”来解释格式例外。
- 不再用“几个分区独立样式”作为格式差异汇总。
- 格式差异汇总改为“几个格式例外”。

### 2.7 运行时边界接入

本轮已把 `application_boundary` 接入运行链路：

- `ResolvedConfig` 增加 `application_boundary`。
- `resolve_config()` 先解析 `scene_application_boundary_for_runtime(scene)`，再把它投影为兼容的 `format_scope`。
- `PipelineContext` 增加 `application_boundary`。
- `PipelineRunner` 把解析后的 `application_boundary` 传入上下文。
- `pipeline.scheduler.validate_data_flow()` 把 `application_boundary` 作为运行上下文可用字段。

这意味着新语义已经进入执行上下文；旧 `format_scope` 仍作为兼容投影保留。

### 2.8 场景策略概览收敛

场景概览现在按用户能直接理解的方式表达：

- `资料包`：是否开启资料包，以及未开启时只处理当前文档。
- `作用边界`：跟随模板默认、仅正文、全文或执行前确认。
- `套用模板`：当前使用哪个模板。
- `格式例外`：是否存在相对模板的局部覆盖。

`交付结果` 不是默认主信息，只在多版本、资料清单、资料包、结构化中间件或非最终 Word 等特殊交付时显示。

`执行预览` 和 `编号策略` 目前仍是概览里的执行入口/预览信息，不再被记录为场景结构定义。后续若继续降噪，应把编号策略放到执行前选择或更贴近模板/执行配置的入口中。

### 2.9 视觉审计同步

模板概览已经不再显示旧的“样式来源”行，这是边界收敛后的正确结果。

因此同步调整了 `scripts/export_style_source_visual_audit.py`：

- 不再强行导出模板概览里的旧 `_style_source_row`。
- 场景概览按新的场景策略设置行记录。
- 工作台执行前预览继续验证共享样式来源行。

## 3. 当前仍保留的兼容边界

以下内容暂时不删除：

- `format_scope`
- `available_sections`
- 执行中心里指向 `format_scope.sections.*` 的旧修复队列路径
- 报告中用于描述旧执行结果的“场景独立样式”措辞
- `scene_scope_service` 中写入旧 `format_scope.sections` 的兼容方法

原因是这些位置属于旧运行链路和历史报告语义，不是场景配置主界面。直接删除会扩大风险。

后续更稳的迁移方式是：

```text
执行前解析 application_boundary
-> 写入 ResolvedConfig / ExecutionContext
-> 运行时继续接收兼容后的 format_scope
-> 等执行中心和诊断队列迁完后，再考虑隐藏或删除旧字段
```

## 4. 验证结果

本轮已通过：

```powershell
python -m pytest tests\test_scene_panel_architecture.py tests\test_scene_overview_projection.py tests\test_small_widget_architecture.py tests\test_style_variant_semantics.py tests\test_style_difference_projection.py tests\test_phase1_config.py::test_scene_workspace tests\test_phase1_config.py::test_scene_application_boundary_normalizes_legacy_format_scope tests\test_phase1_config.py::test_resolve_config_basic tests\test_phase1_config.py::test_resolve_config_projects_application_boundary_to_runtime_scope tests\test_phase1_config.py::test_resolve_config_infers_boundary_from_legacy_scope_when_needed tests\test_phase0_smoke.py::test_pipeline_injects_format_scope_into_context tests\test_scene_parameter_ownership.py tests\test_ui_copy_guardrails.py::test_scene_visible_copy_guard_keeps_machine_terms_out_of_main_paths tests\test_ui_copy_guardrails.py::test_scene_overview_summary_main_copy_hides_internal_keys_and_counts tests\test_field_display_names.py tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_scene_summary_includes_profile_contracts tests\test_workbench_execution_center.py::test_execution_center_shows_style_difference_without_receipt tests\test_workbench_execution_center.py::test_execution_center_result_state_renders_style_source_receipt tests\test_style_source_visual_audit.py -q
```

结果：

```text
152 passed
```

补充验证：

```powershell
python -m py_compile src\config\scene.py src\config\resolved.py src\config\resolver.py src\pipeline\context.py src\pipeline\runner.py src\pipeline\scheduler.py src\ui\panels\scene_scope_service.py src\ui\panels\scene_style_override_service.py src\config\scene_parameter_ownership.py src\ui\adapters\field_display_names.py src\ui\adapters\workbench_execution_adapter.py src\ui\panels\workbench\quick_execution_detail.py src\ui\panels\workbench\scene_presets.py src\ui\panels\scene_panel.py src\ui\panels\scene_summary_projection.py src\ui\panels\scene_overview_projection.py src\ui\panels\scene_scope_sections.py src\config\style_difference_projection.py src\config\style_source_report_summary.py src\shared\ui\style_presentation_envelope.py scripts\export_style_source_visual_audit.py
```

结果：

```text
通过
```

文案残留检查：

```powershell
rg -n "处理范围|分区样式|核对依据|这套场景会做什么|先在处理范围|处理范围未启用|分区独立样式|分区已调整|个分区|调分区|分区：" src tests
```

结果只剩：

```text
src\shared\ui\style_presentation_envelope.py 中的旧报告兼容替换。
tests 中的保护断言和旧输入样例。
```

## 5. 最终确认

当前修复后，程序语义是合理的：

```text
模板管结构。
场景管策略。
格式例外是相对模板的局部覆盖。
旧 format_scope 是兼容门禁，不是新的章节模型。
```

这可以避免模板和场景重复定义章节，也避免用户误以为“处理范围”和“格式例外”会互相创建或删除章节。
