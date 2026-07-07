# Scene / Template 场景能力再审执行记录

日期：2026-07-01

关联记录：

- `docs/refactor-records/SceneTemplateBoundary边界确认记录_2026-07-01.md`
- `docs/audits/SceneTemplateBoundary修复方案_2026-07-01.md`
- `docs/refactor-records/SceneTemplateBoundary执行记录_2026-07-01.md`

## 1. 再审结论

本轮确认：不能把“参考文献、公式、图表、页眉页脚”等完整领域直接归给模板或场景。

正确边界是按语义拆开：

```text
模板：决定文档长什么样。
场景：决定这类文档要做什么、依赖什么资料、遇到风险怎么办、最终交付什么。
执行能力：决定本次运行哪些处理步骤。
```

因此，场景页不应再用“表格与图表、页面元素、公式规范、参考文献”作为主能力名。这些名称会让用户以为场景在重新定义模板外观。

## 2. 本轮落地

### 2.1 能力命名改为执行语义

`src/ui/panels/workbench/scene_presets.py` 中的可见能力组改为：

- `图表处理`
- `公式处理`
- `引用处理`
- `风险检查`
- `资料包与填充`

这些能力组仍然映射到原有 `module_switches`，只改变用户理解层：

```text
它们是运行时处理开关，不是格式基线配置。
```

减法修正：`目录页眉` 不再作为可见能力组展示。页眉页脚、页码、目录层级和目录样式已经归入模板，场景页不再提供平行入口。

### 2.2 场景页不再直接编辑模板外观字段

`src/ui/panels/scene_panel.py` 中：

- `图表处理` 不再编辑 `scene.table` / `scene.caption`，只写 `table_format`、`caption`、`figure_table_center` 模块开关。
- `目录页眉` 详情页从场景主路径撤下；不再只读展示模板页码策略，也不再提供页眉页脚/目录开关表单。
- `公式处理` 不再编辑 `scene.formula_table.formula_font_name`，只保留公式输出、低置信度、Office 兜底和按模板统一的场景策略。
- `引用处理` 明确只处理 `citation_link`，不再用“参考文献排版样式”描述。

`src/ui/panels/workbench/scene_presets.py` 中仍保留 `_build_switches(page_elements=...)` 参数，仅用于旧预设展开到内部 `header_footer` / `toc` 开关，避免历史配置失效；它不是新的可见场景策略。

### 2.3 解析层收紧模板覆盖

`src/config/resolver.py` 中 `_SCENE_FEATURE_FIELDS` 不再包含：

- `table`
- `header_footer`
- `toc`
- `caption`
- `formula_table`
- `reference_style`

这些字段不再因为 `SceneWorkspace` 同名字段非默认就自动覆盖模板。

仍然保留的 scene-owned runtime policy 字段：

- `formula_style`
- `equation_numbering`
- `watermark`
- `output`

显式 `template_overrides` 和执行前 `session_overrides` 仍可覆盖模板字段，用于兼容旧配置和用户明确的临时覆盖。

## 3. 最终边界

### 图表

- 模板：表格边框、配色、布局、续表样式、题注样式。
- 场景：是否处理表格、是否处理题注、是否调整图表位置、复杂对象如何风险提示。

### 目录与页眉

- 模板：页眉页脚、页码、目录层级和样式。
- 场景：不再提供可见主入口。历史场景里的内部 `header_footer` / `toc` 开关只作为兼容读取，不再被包装成用户需要二次确认的场景策略。

### 公式

- 模板：公式字体、字号、间距、公式表格视觉基线。
- 场景：公式转换方式、低置信度策略、Office 兜底、是否按模板统一。

### 引用与参考文献

- 模板：参考文献列表排版。
- 场景：正文引用与参考条目的编号/链接行为。
- 资料包/专业检查：BibTeX、CSL、学校/期刊规则、引用缺失和来源真实性。

### 资料包

- 场景/资料层：资料规则、必填字段、图片/签章角色、资料缺失策略。
- 模板不负责资料是否齐全。

## 4. 验收口径

本轮新增和调整的测试口径：

- `tests/test_config_feature_hosting.py`
  - 场景旧同名外观字段不再自动覆盖模板。
  - 显式 `template_overrides` 仍可覆盖模板。
  - 公式处理、水印和输出等 scene-owned policy 字段仍进入运行配置。
- `tests/test_workbench_navigation_architecture.py`
  - 工作台共享能力卡使用新的执行语义命名，并确认 `page_elements` 不再进入可见能力注册表。
- `tests/test_scene_panel_architecture.py`
  - 场景页主路径使用 `执行能力` 和 `资料包`。
  - 场景页不再挂载 `scn_page_elem` / `_page_elem`。

## 5. 保留项

`SceneWorkspace` 里仍保留旧的 `table/header_footer/toc/caption/formula_table/reference_style` 字段，原因是旧配置保存、迁移读取和测试路径仍依赖它们。

但从本轮开始，它们的语义变为：

```text
旧版场景内嵌模板字段，保留用于兼容和迁移。
新路径不再把它们作为场景主配置。
```
