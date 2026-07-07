# StylePresentationEnvelope 语义词表与构造守门执行记录

日期：2026-06-29

## 1. 背景

前两轮已经把三类展示入口收进 `StylePresentationEnvelope` 命名工厂：

- `from_template_page(...)`
- `from_preview_projection(...)`
- `from_execution_result(...)`

但如果固定词仍然以字符串形式散落在工厂实现里，后续仍会出现两个问题：

1. “模板基线”“本次使用”“调分区”等词没有明确归属，后续新增页面容易复制旧字符串。
2. 业务代码虽然当前没有直接构造 envelope，但缺少测试守门，后续很容易回退。

本轮目标是把展示语义词集中到共享层，并用架构测试防止业务层重新直接实例化 envelope。

## 2. 本轮改动

### 2.1 集中语义词表

在 `src/shared/ui/style_presentation_envelope.py` 中新增并导出语义常量：

| 常量 | 值 | 用途 |
| --- | --- | --- |
| `STYLE_PRESENTATION_KIND_SECTION_PARAGRAPH` | `section_paragraph` | 场景分区段落预览 |
| `STYLE_PRESENTATION_KIND_TEMPLATE_PAGE` | `template_page` | 模板页面级预览 |
| `STYLE_PRESENTATION_KIND_EXECUTION_RECEIPT` | `execution_receipt` | 执行后样式回执 |
| `STYLE_PRESENTATION_TITLE_PREVIEW` | `样式预览` | 预览标题 |
| `STYLE_PRESENTATION_TITLE_SOURCE` | `样式来源` | 回执标题 |
| `STYLE_PRESENTATION_SOURCE_TEMPLATE_BASELINE` | `模板基线` | 模板来源状态 |
| `STYLE_PRESENTATION_SOURCE_CURRENT_RUN` | `本次使用` | 执行回执来源状态 |
| `STYLE_PRESENTATION_ACTION_ADJUST_SECTION` | `调分区` | 场景覆盖动作 |
| `STYLE_PRESENTATION_TEMPLATE_FALLBACK` | `当前模板` | 模板缺省名称 |

这些常量现在被 `StylePresentationEnvelope` 的工厂方法使用，避免固定词在共享语义层内部继续漂浮。

### 2.2 增加业务直构守门

新增测试：

```python
tests/test_small_widget_architecture.py::test_style_presentation_envelope_business_code_uses_named_factories
```

守门范围：

- `src/shared/**/*.py`
- `src/ui/**/*.py`

允许：

- `src/shared/ui/style_presentation_envelope.py` 内部使用 `cls(...)`
- 测试文件直接构造 envelope，用于覆盖兼容行为

禁止：

- 业务代码出现 `StylePresentationEnvelope(...)`

## 3. 这轮对“说人话”的价值

用户看到的固定词应该是产品语言，不应该散落在页面实现里。

现在这些词的归属更清楚：

```text
模板页：样式预览 / 模板基线 / 当前模板
分区页：样式预览 / 调分区
执行后：样式来源 / 本次使用
```

后续如果要把“调分区”改成更自然的“调整分区样式”，不需要搜业务页面；如果要把“本次使用”改成“本次执行使用”，也只需要改共享语义层。

## 4. 当前边界

当前推荐边界：

| 层 | 可以做什么 | 不应该做什么 |
| --- | --- | --- |
| 业务页面 | 传入模板名、摘要、分区状态、projection | 直接实例化 envelope |
| envelope 工厂 | 决定 kind、标题、来源、动作词 | 依赖具体 Qt 控件 |
| 控件层 | 读取 envelope 并同步 Qt 属性 | 自己拼业务文案 |
| 测试层 | 构造 envelope 覆盖兼容路径 | 不代表业务代码可以直构 |

## 5. 验证

已执行：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_presentation_envelope.py tests/test_small_widget_architecture.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_presentation_envelope_builds_template_page_metadata tests/test_small_widget_architecture.py::test_style_presentation_envelope_builds_execution_receipt_from_result tests/test_small_widget_architecture.py::test_style_presentation_envelope_business_code_uses_named_factories tests/test_template_style_preview.py::test_template_style_preview_exposes_template_page_presentation_envelope tests/test_workbench_execution_center.py::test_execution_adapter_builds_success_result_state -q
```

结果：

```text
5 passed
```

## 6. 后续

这轮守住的是展示语义入口。下一步更值得继续推进的是内容板块计划：

- 来源：模板基线、跟随模板、独立样式
- 范围：影响哪些分区
- 规则：是否覆盖、是否恢复
- 编辑：当前可编辑字段
- 预览：页面级或段落级效果
- 回执：本次执行实际使用

也就是继续推进 `StyleManagementContentPlan`，让页面不只是共享 envelope，还能共享“该展示哪些板块”的规划。
