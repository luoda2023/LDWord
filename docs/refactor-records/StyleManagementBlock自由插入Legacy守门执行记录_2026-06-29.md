# StyleManagementBlock 自由插入 Legacy 守门执行记录

日期：2026-06-29

## 1. 背景

`StyleManagementBlock` 已经逐步补齐命名入口：

- `rule_control`
- `preview_slot`
- `receipt_slot`

但为了兼容历史调用，构造参数里仍然保留：

```python
management_widgets: Sequence[QWidget] = ()
```

这个入口如果继续被业务页面使用，就会绕过 `source/scope/rules/editor/preview/receipt` 的内容计划，重新把共享 block 当作普通容器。

本轮目标不是删除兼容入口，而是让它变成可审计的 legacy 入口，并禁止业务层继续使用。

## 2. 本轮改动

`StyleManagementBlock` 新增：

```python
block.legacy_management_widgets
```

并同步 Qt 属性：

```text
style_management_has_legacy_widgets
```

含义：

- `legacy_management_widgets` 保存传入的自由插入 widget。
- `style_management_has_legacy_widgets=True` 表示这个 block 仍然使用了兼容自由插入。
- 新页面应优先使用 `rule_control`、`preview_slot`、`receipt_slot`。

## 3. 架构守门

新增测试：

```python
tests/test_small_widget_architecture.py::test_style_management_block_business_code_uses_named_slots
```

扫描范围：

- `src/shared/**/*.py`
- `src/ui/**/*.py`

例外：

- `src/shared/ui/style_management_block.py` 自身可以保留 `management_widgets` 参数。

禁止：

- 业务调用方出现 `management_widgets=`

这意味着后续新增页面如果想塞规则、预览、回执，必须走命名 slot。

## 4. 验证

已执行：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_management_block.py tests/test_small_widget_architecture.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_management_block_named_preview_and_receipt_slots_update_plan tests/test_small_widget_architecture.py::test_style_management_block_legacy_widgets_are_auditable tests/test_small_widget_architecture.py::test_style_management_block_business_code_uses_named_slots -q
```

结果：

```text
3 passed
```

## 5. 结论

`management_widgets` 现在不再是“推荐扩展点”，而是可审计的 legacy 兼容层。

这一步把 `StyleManagementBlock` 的边界进一步收紧：规则、预览、回执都有命名槽位；自由插入仍可兼容旧代码，但业务层不应继续新增使用。
