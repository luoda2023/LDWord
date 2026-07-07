# StyleManagementBlock 规则控制命名 Slot 执行记录

日期：2026-06-29

后续进展：`rule_control` 已从命名 slot 进一步收紧为必须实现 `apply_projection(...)` 的策略控制槽，并通过 `style_management_rule_control_protocol` / `style_management_rule_control_ready` 可观测，详见 `docs/refactor-records/StyleManagementBlock策略控制槽协议守门执行记录_2026-06-30.md`。

## 1. 本轮目标

上一轮第三次深度审计确认了一个 P0 问题：`StyleManagementBlock` 虽然已经成为模板正文和场景分区样式的共享块，但它仍通过 `management_widgets` 接收任意控件。

这会带来两个风险：

- 场景分区样式虽然已经抽出了 `StyleRuleControlDeck`，但接入方式仍像“把一个 widget 临时塞进摘要卡”。
- 后续新页面可能继续把长说明、临时按钮组或局部卡片放进 `StyleManagementBlock`，破坏模板管理的阅读节奏。

本轮目标是先收束最明确的一类插槽：

```text
rule_control：样式规则控制区
```

它用于承载分区独立样式开关、差异对照、全部跟随模板和撤销恢复等规则控制能力。

## 2. 本轮代码落点

### 2.1 StyleManagementBlock 新增命名 slot

文件：

- `src/shared/ui/style_management_block.py`

新增参数：

```python
rule_control: QWidget | None = None
```

新增属性：

```python
@property
def rule_control(self) -> QWidget | None:
    return self._rule_control
```

布局顺序：

```text
DetailSummaryCard
-> SummaryGrid
-> rule_control
-> legacy management_widgets
-> StyleEditingSection chrome
-> StyleEditingSection field surface
```

`management_widgets` 暂时保留作为兼容入口，但新场景链路不再使用它。

### 2.2 SceneStyleOverrideSection 改用命名 slot

文件：

- `src/ui/panels/scene_style_override_sections.py`

变更前：

```python
StyleManagementBlock(
    ...,
    management_widgets=(self._rule_control_deck,),
)
```

变更后：

```python
StyleManagementBlock(
    ...,
    rule_control=self._rule_control_deck,
)
```

意义：

`StyleRuleControlDeck` 现在不是普通插入控件，而是 `StyleManagementBlock` 明确承认的“规则控制区”。

## 3. 测试守门

更新文件：

- `tests/test_small_widget_architecture.py`
- `tests/test_scene_panel_architecture.py`

新增/更新验证点：

- `StyleManagementBlock.rule_control` 指向传入的规则控制 widget。
- 规则控制 widget 的父级仍是 `DetailSummaryCard`。
- `SceneStyleOverrideSection` 源码必须使用 `rule_control=self._rule_control_deck`。
- `SceneStyleOverrideSection` 源码不得再使用 `management_widgets=`。
- 运行时 `section._style_management_block.rule_control is section.rule_control_deck`。

## 4. 已验证

语法检查：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_management_block.py src/ui/panels/scene_style_override_sections.py tests/test_small_widget_architecture.py tests/test_scene_panel_architecture.py
```

结果：通过。

焦点回归：

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_management_block_wraps_summary_controls_preview_and_surface tests/test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface -q
```

结果：

```text
3 passed
```

宽回归：

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py tests/test_scene_panel_architecture.py tests/test_template_style_detail.py tests/test_ui_exports.py -q
```

结果：

```text
103 passed
```

## 5. 当前边界

本轮没有直接删除 `management_widgets`。原因：

- 旧测试和未来未知调用可能仍依赖这个兼容入口。
- 当前目标是先让场景分区样式这条主链路使用命名 slot。
- 直接删除会把风险扩大到非样式规则区块，不利于逐步收束。

但本轮已经建立了新规则：

```text
新共享样式规则区不得再通过 management_widgets 接入。
```

后续如果发现其它稳定语义区，也应继续抽成命名 slot，例如：

- `source_widget`
- `preview_widget`
- `receipt_widget`

## 6. 本轮判断

这一步让样式管理的复用更接近模板管理的设计方式：页面不再只是复用同一批底层控件，而是复用同一套板块语义。

现在分区样式规则的链路变为：

```text
SceneStyleOverrideSection
-> StyleManagementBlock(rule_control=StyleRuleControlDeck)
-> StyleEditingSection
-> StyleControlSurface
-> ParagraphStyleEditor
```

这比原来的“`management_widgets=(self._rule_control_deck,)`”更清晰，也更容易继续做后续两件事：

1. 把 `management_widgets` 完全降级为兼容层。
2. 继续抽 `preview`、`receipt` 等命名 slot，让模板、场景、Workbench 的样式语法完全一致。
