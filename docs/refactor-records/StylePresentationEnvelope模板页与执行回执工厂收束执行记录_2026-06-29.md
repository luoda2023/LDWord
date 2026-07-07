# StylePresentationEnvelope 模板页与执行回执工厂收束执行记录

日期：2026-06-29

## 1. 背景

上一轮已经把场景分区段落预览的 projection 转换收进 `StylePresentationEnvelope.from_preview_projection(...)`。继续审计后发现，模板页面级预览和 Workbench 执行后样式回执仍然在业务模块里直接构造 `StylePresentationEnvelope(...)`。

这会留下两个问题：

1. 固定展示词仍然散落在业务页，例如“样式预览”“模板基线”“样式来源”“本次使用”。
2. 后续要统一模板管理、场景样式、Workbench 回执的可读性时，仍然需要逐个页面改文案。

本轮目标是让业务页面只传上下文数据，展示语义由共享 envelope 工厂生成。

## 2. 本轮改动

### 2.1 新增模板页工厂

新增：

```python
StylePresentationEnvelope.from_template_page(...)
```

职责：

- 统一 `kind = template_page`
- 统一 `title = 样式预览`
- 统一 `source_label = 模板基线`
- 根据 `template_label` 生成 `当前模板：xxx`
- 接收业务层已经生成的摘要和动作词

迁移位置：

- `src/ui/panels/template_format.py`
- `src/ui/panels/template_style_preview.py`

### 2.2 新增执行回执工厂

新增：

```python
StylePresentationEnvelope.from_execution_result(...)
```

职责：

- 统一 `kind = execution_receipt`
- 统一 `title = 样式来源`
- 统一 `source_label = 本次使用`
- 优先消费执行结果里的 `summary`
- 没有 summary 时，用 `template_label + section_status` 生成可读回执
- 没有结构化数据时，回退到兼容 summary

迁移位置：

- `src/ui/adapters/workbench_execution_adapter.py`

## 3. 当前统一入口

现在三个核心展示阶段对应三个命名工厂：

| 展示阶段 | 工厂 | 消费控件 |
| --- | --- | --- |
| 模板页面级预览 | `from_template_page(...)` | `TemplateStylePreview` |
| 场景分区段落预览 | `from_preview_projection(...)` | `StylePreview` |
| 执行后样式回执 | `from_execution_result(...)` | `StyleResultReceiptRow` |

这意味着页面级、分区级、执行后不再各自决定展示词，而是共享同一组 envelope 字段：

- `kind`
- `title`
- `source_label`
- `summary`
- `detail`
- `action_label`

## 4. 对模板管理一致性的意义

模板管理现在承担的是“默认样式基线”，场景样式承担的是“覆盖层”，Workbench 承担的是“本次实际使用结果”。

这三者需要说同一种话：

```text
模板页：样式预览 / 模板基线 / 当前模板
场景页：分区名称 / 跟随模板或独立样式 / 调分区
执行后：样式来源 / 本次使用 / 模板与分区覆盖情况
```

本轮之后，这些固定说法已经不再散落在业务页，而是收进 `StylePresentationEnvelope`。后续继续优化界面文案时，可以改共享工厂，而不是逐个页面找字符串。

## 5. 审计结果

本轮迁移后，业务代码中已经搜不到直接构造：

```powershell
rg -n "return StylePresentationEnvelope\(|StylePresentationEnvelope\(" src/ui src/shared -g "*.py"
```

结果：无业务直接构造点。

说明：

- `src/shared/ui/style_presentation_envelope.py` 内部使用 `cls(...)` 是共享工厂自身实现，不属于业务散落。
- 测试文件中仍允许直接构造 envelope，用于覆盖控件接收外部 envelope 的兼容能力。

## 6. 新增测试

新增：

- `tests/test_small_widget_architecture.py::test_style_presentation_envelope_builds_template_page_metadata`
- `tests/test_small_widget_architecture.py::test_style_presentation_envelope_builds_execution_receipt_from_result`

继续覆盖：

- `tests/test_template_style_preview.py::test_template_style_preview_exposes_template_page_presentation_envelope`
- `tests/test_workbench_execution_center.py::test_execution_adapter_builds_success_result_state`

## 7. 验证

已执行：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_presentation_envelope.py src/ui/panels/template_format.py src/ui/panels/template_style_preview.py src/ui/adapters/workbench_execution_adapter.py tests/test_small_widget_architecture.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_presentation_envelope_builds_template_page_metadata tests/test_small_widget_architecture.py::test_style_presentation_envelope_builds_execution_receipt_from_result tests/test_template_style_preview.py::test_template_style_preview_exposes_template_page_presentation_envelope tests/test_workbench_execution_center.py::test_execution_adapter_builds_success_result_state -q
```

结果：

```text
4 passed
```

## 8. 后续剩余

本轮完成的是“语义工厂收束”，还没有完成最终优秀设计所需的全部内容：

1. `StyleManagementContentPlan` 仍未建立，样式管理区块的来源、范围、规则、编辑、预览、回执还需要进一步内容计划化。
2. 主界面冗余说明句还需要继续删除，并用按钮、状态词、tooltip 承担解释。
3. 状态词和动作词还需要进一步集中，例如“看模板”“调分区”“编辑正文”“本次使用”。
4. 需要继续做视觉层复核，确认用户看到的是同一套流程，而不是同一批底层类。

## 9. 本轮结论

样式控件与模板管理的复用已经从“共享控件”推进到“共享展示语义入口”。

现在模板预览、场景分区预览、执行后回执都能通过 `StylePresentationEnvelope` 的命名工厂表达。后续再做内容板块重排时，就有了更稳的底座：页面只决定场景，语义层决定怎么说人话，控件层决定怎么显示。

## 10. 追加记录：语义词表与构造守门

追加日期：2026-06-29

在继续审计中发现，虽然业务代码已经不再直接构造 envelope，但固定词仍然需要进一步集中，否则“样式预览”“模板基线”“样式来源”“本次使用”“调分区”等词仍然缺少明确归属。

追加调整：

- 在 `src/shared/ui/style_presentation_envelope.py` 中新增 `STYLE_PRESENTATION_*` 语义常量。
- `from_template_page(...)`、`from_preview_projection(...)`、`from_execution_result(...)`、`from_summary(...)` 改为使用这些常量。
- 新增 `tests/test_small_widget_architecture.py::test_style_presentation_envelope_business_code_uses_named_factories`，防止 `src/shared` 和 `src/ui` 的业务代码重新出现 `StylePresentationEnvelope(...)` 直构。

这一步让 envelope 复用从“一次性迁移”变成“有测试守门的架构边界”。
