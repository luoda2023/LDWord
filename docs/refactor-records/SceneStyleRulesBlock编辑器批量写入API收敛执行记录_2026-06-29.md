# SceneStyleRulesBlock 编辑器批量写入 API 收敛执行记录

日期：2026-06-29

## 1. 本轮目标

上一轮已经把导航高亮、字段控件定位、分区开关状态等观察点收敛到 `SceneStyleRulesBlock`。本轮继续处理测试和页面边界里的另一个问题：测试为了模拟用户编辑分区样式，仍然直接操作 `ParagraphStyleEditor` 内部控件。

旧写法类似：

```python
scope._section_font_cn.set_font_name(...)
scope._section_size_combo.set_pt(...)
scope._section_bold_switch.setChecked(...)
scope._section_special_indent.set_value(...)
```

这会让测试知道太多底层控件结构。后续如果要把样式编辑区重排为更接近模板管理的板块结构，测试会反过来锁死旧布局。

本轮目标是把这类编辑动作提升为对象级语义：

```python
scope._style_rules_block.set_editor_values(...)
```

## 2. 本轮代码调整

### 2.1 共享编辑器增加批量字段写入

文件：`src/shared/ui/paragraph_style_editor.py`

新增：

```python
ParagraphStyleEditor.set_values(...)
```

支持字段：

```text
font_cn
font_en
size_pt
bold
italic
alignment
special_indent
left_indent
right_indent
line_spacing_type
line_spacing_pt
space_before
space_after
```

实现原则：

1. 使用 `_UNSET` 区分“未传入”和“传入空值”。
2. 批量写入期间打开 `_is_syncing`，避免每个底层控件单独触发样式变化。
3. 写入完成后刷新启用态，并在非同步场景下只发出一次 `style_changed`。
4. `line_spacing_type` 改变时同步行距值控件的范围、单位标签和启用态。

这让共享编辑器既能被模板管理继续复用，也能被场景分区样式以更高层方式驱动。

### 2.2 SceneStyleRulesBlock 增加对象级转发

文件：`src/ui/panels/scene_style_rules_block.py`

新增：

```python
SceneStyleRulesBlock.set_editor_values(**values)
```

它当前只转发到：

```python
self.editor.set_values(**values)
```

价值不在于减少代码行数，而在于继续让 `_StyleRulesDetail` 和测试面向“场景分区样式对象区”，而不是面向 `ParagraphStyleEditor` 内部字段。

### 2.3 测试改走 block API

文件：`tests/test_scene_panel_architecture.py`

本轮迁移了三类访问：

| 场景 | 旧方式 | 新方式 |
| --- | --- | --- |
| 模拟用户编辑字段 | 逐个调用 `_section_*` 控件 | `scope._style_rules_block.set_editor_values(...)` |
| 行距类型切换 | `_set_combo_by_data(scope._section_line_type_combo, "exact")` | `scope._style_rules_block.set_editor_values(line_spacing_type="exact")` |
| 字段启用态观察 | `_section_font_cn.isEnabled()` / `_section_line_value.isEnabled()` | `editor_widget_for_field(...).isEnabled()` |

同时补强 `test_scene_style_rules_block_wraps_override_section_as_stable_object`：

```python
block.set_editor_values(font_cn="黑体", bold=True, line_spacing_type="single")
block.apply_editor_to_style(target_style)
```

用于证明 block 级 API 可以真实写入共享编辑器并回写 `StyleConfig`。

## 3. 对一致性设计的意义

模板管理和场景分区样式要保持一致，不只是复用相同控件，而是要复用相同的对象语言：

```text
设置当前编辑器字段
读取当前字段到 StyleConfig
定位某个字段控件
定位某个分区开关
切换是否可编辑
```

本轮之后，场景分区样式测试不再用下面的语言表达核心链路：

```text
我知道 editor 里有 _section_font_cn
我知道行距类型是 _section_line_type_combo
我知道缩进控件叫 _section_special_indent
```

而是改成：

```text
我设置当前样式编辑器字段
我检查 font_cn 字段控件是否可用
我检查 line_spacing_pt 字段控件是否可用
```

这让后续重新规划内容板块更安全。比如未启用独立样式时折叠字段区、把编辑区移动到预览之后、或把来源/差异/规则重新分区，测试不应因为内部控件摆放变化而失败。

## 4. 仍然保留的兼容面

本轮没有删除 `_StyleRulesDetail` 中的兼容别名，例如：

```text
_section_font_cn
_section_line_value
_section_alignment_combo
```

原因是它们可能仍被其它旧测试、调试入口或后续迁移步骤引用。当前更稳妥的节奏是：

1. 先让新增测试和核心测试面向 block API。
2. 再逐步删掉不再使用的兼容别名。
3. 最后收紧架构守门，禁止页面层继续新增直接 editor 字段访问。

## 5. 后续建议

### P0：继续把页面同步动作组合进 block

下一轮可以评估这些组合动作是否进入 `SceneStyleRulesBlock`：

```text
set_current_scene_style_state(...)
sync_visible_variants(...)
apply_owner_preview_and_difference(...)
restore_current_variant_to_template(...)
```

不要一次性把业务投影全塞进 block。更好的边界是：页面计算业务状态，block 执行样式对象区的 UI 同步。

### P1：为冗余文本清理补守门测试

当前视觉问题仍然不只是 API 边界。还需要补主界面文本守门，限制这些内容出现在主阅读层：

```text
内部 key
registry 计数
长风险说明
泛化操作说明句
```

这些信息应该进入 tooltip、审计详情或高级诊断，而不是占据首屏卡片。

### P1：拆清处理范围和分区样式

处理范围回答“这次处理哪些区域”，分区样式回答“这些区域的样式是否跟随模板”。后续信息架构上仍建议继续拆开，避免一个页面同时承担范围、开关、规则、编辑、预览、恢复全部。

## 6. 本轮验证

已执行：

```powershell
python -X utf8 -m py_compile src\shared\ui\paragraph_style_editor.py src\ui\panels\scene_style_rules_block.py
```

结果：通过。

已执行：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py::test_scene_style_rules_block_wraps_override_section_as_stable_object tests\test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract tests\test_scene_panel_architecture.py::test_scene_panel_scope_style_override_editor_writes_section_styles tests\test_scene_panel_architecture.py::test_scene_panel_restore_all_section_styles_returns_every_partition_to_template -q
```

结果：

```text
4 passed in 21.43s
```

## 7. 本轮结论

本轮继续把场景分区样式从“页面层拼装控件”推进到“对象区提供语义 API”。这一步不会立刻改变用户可见界面，但它直接服务于后续真正的设计优化：重排样式板块、折叠未启用字段区、减少冗余说明文字，并让场景样式管理和模板管理在对象边界上保持一致。
