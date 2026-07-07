# StylePresentationEnvelope 预览回执语义层执行记录

日期：2026-06-29

后续进展：

- Workbench 执行状态链路已接入 envelope：`ExecutionResultState` 和 `RecentRunState` 新增 `style_source_envelope`，执行中心与最近结果优先按 envelope 渲染回执，详见 `docs/refactor-records/Workbench样式回执Envelope状态链路执行记录_2026-06-29.md`。
- 模板页面级预览已接入 `template_page` envelope：`TemplateStylePreview` 暴露 `presentation_envelope`，模板概览说明也改为读取同一 envelope summary，详见 `docs/refactor-records/TemplateStylePreview页面级Envelope接入执行记录_2026-06-29.md`。
- 场景分区段落预览已接入 `section_paragraph` envelope：`StyleEditingSection` 会把段落 preview projection 映射为 envelope，再交给 `StylePreview.apply_envelope(...)`，详见 `docs/refactor-records/SceneSectionParagraphEnvelope接入执行记录_2026-06-29.md`。

## 1. 本轮判断

上一轮已经把模板管理和场景分区样式的外壳收敛到 `StyleManagementBlock`，也把摘要卡、标题行、规则控制区和执行后回执拆成共享控件。但继续对照模板管理后，仍然有一个不够优秀的点：

```text
模板页面级预览、场景分区段落预览、Workbench 执行后回执
都在回答“用户最终会按什么样式看到/处理”，
但它们的标题、来源、摘要、详情和动作语义仍然各自散落。
```

这会造成两个问题：

1. 控件看起来逐渐一致，但文案和状态语言仍可能分叉。
2. 后续删除冗余说明时，没有一个统一的展示语义层来承接“这块到底在说明什么”。

所以本轮不继续加解释文案，而是先抽一个轻量语义对象：

```text
StylePresentationEnvelope
```

它不负责绘制 UI，只负责把展示语义统一成同一组字段。

## 2. 新增语义层

新增文件：

- `src/shared/ui/style_presentation_envelope.py`

核心字段：

| 字段 | 用途 |
| --- | --- |
| `kind` | 展示类型，如 `template_page`、`section_paragraph`、`execution_receipt` |
| `title` | 展示块标题或对象名 |
| `source_label` | 来源或状态标签，如“模板基线”“独立样式” |
| `summary` | 一句话摘要 |
| `detail` | 进一步详情 |
| `action_label` | 对应动作文案 |

它提供的规范化方法：

| 方法 | 作用 |
| --- | --- |
| `from_object(...)` | 从兼容对象读取展示字段 |
| `from_summary(...)` | 兼容旧的执行后样式来源字符串 |
| `receipt_summary(...)` | 生成执行后回执完整文本 |
| `display_detail(...)` | 去掉重复标题前缀，避免“样式来源：样式来源：...” |
| `preview_source_label(...)` | 给预览控件提供来源标签 |
| `preview_detail(...)` | 给预览控件提供 tooltip/detail |
| `preview_sample_text(...)` | 给段落预览生成默认示例文本 |

## 3. 已接入位置

### 3.1 `StyleResultReceiptRow`

文件：

- `src/shared/ui/style_result_receipt_row.py`

新增正式入口：

```text
row.apply_envelope(StylePresentationEnvelope(...))
```

保留旧入口：

```text
row.set_summary("样式来源：...")
```

这样 Workbench 现有调用不用马上迁移，但以后执行结果、报告回流、只读复核都可以直接传同一类 envelope。

当前回执行为：

```text
title: 样式来源
summary: 本次按模板“默认格式”处理
detail: 参考文献（行距）使用场景独立样式。

-> 样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。
```

同时写入控件属性：

- `style_presentation_kind`
- `style_presentation_title`

这些属性让测试和后续页面编排可以判断“这是执行回执”，而不是只读一段普通字符串。

### 3.2 `StylePreview`

文件：

- `src/shared/ui/style_preview.py`

新增可选入口：

```text
preview.apply_envelope(envelope, projection=None)
```

这个入口不会替代 `StylePreviewProjection`。当前设计是：

```text
StylePresentationEnvelope：回答“这块展示代表什么”
StylePreviewProjection：回答“这段文字应该怎么画”
```

所以样式绘制仍然稳定走原来的 projection，envelope 只补充标题、来源、详情和动作语义。

控件属性：

- `style_presentation_kind`
- `style_presentation_title`
- `style_presentation_action_label`

## 4. 为什么这是合适的第一片

这轮没有直接重做模板页面级预览，因为那会把视觉布局、页面尺寸、模板参数汇总和段落预览混在一起，风险太大。

更合理的顺序是：

1. 先统一展示语义层。
2. 回执先接入，因为它最轻、最只读、风险最小。
3. 段落预览补入口，但不改变现有绘制路径。
4. 后续已让模板页面级预览声明自己的 `template_page` envelope。

这符合当前项目状态：底层链路已经打通，但还需要逐步把页面语言和控件边界收束。

## 5. 和模板管理一致性的关系

模板管理现在相对优秀的地方是：它始终围绕“当前模板、参数概览、样式预览、导入导出”组织，不把内部工程证据直接塞进主流程。

场景样式要和它保持一致，应该遵守同一套展示语法：

| 位置 | 展示对象 | 用户问题 |
| --- | --- | --- |
| 模板管理 | `template_page` envelope | 这个模板整体长什么样 |
| 场景分区样式 | `section_paragraph` envelope | 这个分区是否跟随模板，当前有效样式是什么 |
| Workbench 回执 | `execution_receipt` envelope | 刚才实际按哪个模板和哪些独立样式执行 |

这样三处不是强行用同一个 UI，而是共享同一套“说人话”的字段。

## 6. 当前未完成

本轮只闭合第一片，不把以下能力伪装成完成：

1. 模板页面级预览已开始消费 `StylePresentationEnvelope`，但场景跳转与只读复核还没有系统性读取 `template_page` envelope。
2. 场景样式页的段落预览已由 envelope 驱动，但规则控制区、差异摘要和部分说明文案还没有完全迁移。
3. `StyleManagementBlock` 还没有正式增加 `preview_slot` / `receipt_slot`。
4. Workbench 执行结果状态对象已开始直接携带 envelope，但 `style_source_summary` 仍作为报告、日志和旧调用方的兼容文本保留。

## 7. 后续建议

### P0：执行结果状态对象携带 envelope

让 `ExecutionResultState` 增加只读展示 envelope 字段，`style_source_summary` 保留为导出兼容文本。

### P1：模板页面级预览声明 `template_page`

模板预览不需要改成 `StylePreview`，但应该输出：

```text
kind = template_page
title = 当前模板
source_label = 模板基线
summary = 页面、正文、标题、表格等关键样式
action_label = 编辑正文 / 导入导出
```

### P1：`StyleManagementBlock` 增加展示 slot

继续把自由插入收敛为：

```text
preview_slot
receipt_slot
```

避免后续页面继续把任意 widget 塞进摘要区。

### P2：删除可由控件表达的说明文案

当模板、分区、回执都能从 envelope 表达“标题、来源、摘要、详情、动作”后，就可以继续删除主界面上的冗余说明句，只保留必要的 tooltip 和空状态。

## 8. 验证

本轮新增和更新测试：

- `tests/test_small_widget_architecture.py::test_style_presentation_envelope_normalizes_preview_metadata`
- `tests/test_small_widget_architecture.py::test_style_result_receipt_row_projects_readonly_style_source_summary`
- `tests/test_ui_exports.py`

已通过聚焦验证：

```text
4 passed
```

## 9. 追加记录：分区预览 projection 工厂

追加日期：2026-06-29

`StylePresentationEnvelope` 已新增 `from_preview_projection(...)`，用于把段落样式预览 projection 统一转换为 `section_paragraph` envelope。

这次追加的意义：

- 分区预览不再由 `StyleEditingSection` 私有拼装展示语义。
- `StylePreview`、`StyleEditingSection`、场景分区页可以共享同一套标题、来源、摘要、详情、动作词规则。
- 后续 `template_page` 和 `execution_receipt` 也应继续向同类工厂收敛。

## 10. 追加记录：模板页与执行回执工厂

追加日期：2026-06-29

`template_page` 和 `execution_receipt` 已继续向同类工厂收敛：

- `StylePresentationEnvelope.from_template_page(...)`
- `StylePresentationEnvelope.from_execution_result(...)`

迁移后：

- `src/ui/panels/template_format.py` 不再直接构造模板页 envelope。
- `src/ui/panels/template_style_preview.py` 默认态不再直接构造模板页 envelope。
- `src/ui/adapters/workbench_execution_adapter.py` 不再直接构造执行回执 envelope。

当前业务代码中已经搜不到 `StylePresentationEnvelope(...)` 直接构造点，说明模板页、分区预览、执行回执都已经通过命名工厂进入共享语义层。
