# SceneStyleRulesBlock 内部控件兼容别名清理执行记录

日期：2026-06-29

## 1. 本轮目标

前几轮已经把场景分区样式区逐步收敛到 `SceneStyleRulesBlock`：

- 分区开关状态：`set_override_checked(...)`
- 导航目标：`navigation_widget_for_field(...)`
- 字段控件定位：`editor_widget_for_field(...)`
- 编辑器可编辑态：`set_editor_editable(...)`
- 写回 `StyleConfig`：`apply_editor_to_style(...)`
- 批量字段写入：`set_editor_values(...)`

本轮继续清理 `_StyleRulesDetail` 中已经失去必要性的兼容别名。目标是让 `ScenePanel` 不再持有 `ParagraphStyleEditor` 内部字段控件的直接引用。

## 2. 原问题

清理前，`src/ui/panels/scene_panel.py` 初始化中仍保留这些别名：

```text
_section_style_editor
_section_font_cn
_section_font_en
_section_size_combo
_section_bold_switch
_section_italic_switch
_section_emphasis
_section_alignment_combo
_section_special_indent
_section_left_indent
_section_right_indent
_section_line_type_combo
_section_line_value
_section_line_value_suffix
_section_space_before
_section_space_after
```

这些字段曾经服务于旧测试和旧页面逻辑。但当前生产代码和测试已经改为通过 `SceneStyleRulesBlock` 访问：

```text
editor_widget_for_field(...)
navigation_widget_for_field(...)
set_editor_values(...)
apply_editor_to_style(...)
```

因此这些别名已经变成结构噪音。继续保留它们会带来两个问题：

1. 误导后续开发继续直接操作 editor 内部控件。
2. 让未来重排“来源 / 范围 / 规则 / 差异 / 编辑 / 预览”板块时，旧字段名仍像隐形依赖一样留在页面层。

## 3. 本轮代码调整

### 3.1 删除 ScenePanel 内部控件别名

文件：`src/ui/panels/scene_panel.py`

删除 `_StyleRulesDetail.__init__` 中对段落样式编辑器内部控件的别名赋值。

保留：

```python
self._unit_labels.extend(self._style_rules_block.unit_labels)
```

原因是单位标签仍属于当前主题同步链路，且它通过 block 公开的 `unit_labels` 获取，不再需要页面层保存每个字段控件。

### 3.2 更新架构守门测试

文件：`tests/test_scene_panel_architecture.py`

补强 `test_scene_panel_controls_follow_template_management_contract`，禁止 `scene_panel.py` 重新出现这些赋值：

```text
self._section_style_editor =
self._section_font_cn =
self._section_font_en =
self._section_size_combo =
self._section_bold_switch =
self._section_italic_switch =
self._section_emphasis =
self._section_alignment_combo =
self._section_special_indent =
self._section_left_indent =
self._section_right_indent =
self._section_line_type_combo =
self._section_line_value =
self._section_line_value_suffix =
self._section_space_before =
self._section_space_after =
```

这让“页面层不再保存 editor 内部字段引用”成为自动化契约，而不是口头约定。

### 3.3 更新运行时一致性审计证据

文件：`src/config/scene_control_runtime_consistency_audit.py`

将审计证据中的：

```text
ScenePanel._section_style_editor
```

替换为：

```text
SceneStyleRulesBlock.editor
```

这样审计口径也和当前对象边界一致：场景侧样式字段复用的入口是 `SceneStyleRulesBlock`，不是 `ScenePanel` 的私有别名。

## 4. 对模板管理一致性的意义

模板管理的一致性不是“页面里也放一堆相同字段控件”，而是让页面使用同一种对象语言：

```text
模板管理：编辑模板基线样式对象
场景样式：编辑当前场景的分区覆盖对象
执行回执：展示本次实际使用的样式对象
```

旧别名属于“页面知道控件内部结构”的阶段。清理后，场景页更接近这个边界：

```text
_StyleRulesDetail
  负责场景 / 模板状态协调
  负责调用服务写回 scene
  不保存 editor 内部字段控件

SceneStyleRulesBlock
  负责样式对象区的控件定位、编辑器写入、开关、预览和状态同步

ParagraphStyleEditor
  负责真实字段控件和 StyleConfig 读写
```

这为后续真正优化界面提供了更干净的基础。只要测试和页面都不依赖 `_section_font_cn` 这类字段，就可以更安全地移动、折叠或重组字段区。

## 5. 后续建议

### P0：继续清理其它对象区的类似别名

本轮只处理分区样式字段控件。后续可以审计其它区域是否也存在类似模式：

```text
页面层保存共享 block 内部控件
测试直接操作内部控件而不是对象 API
审计文档仍引用旧页面私有字段
```

优先级最高的是和模板管理同源的样式相关区域，其次才是输出、资料、规则等业务区域。

### P1：继续向可见 UI 优化推进

代码边界清理已经逐步具备条件。下一阶段可以更大胆地处理可见体验：

1. 未启用独立样式时折叠字段编辑区。
2. 把“来源、范围、规则、差异、编辑、预览”做成稳定板块。
3. 删除首屏里的内部 key、计数和长说明。
4. 让主界面只显示短状态和明确动作。

## 6. 本轮验证

已执行：

```powershell
python -X utf8 -m py_compile src\ui\panels\scene_panel.py src\config\scene_control_runtime_consistency_audit.py
```

结果：通过。

已执行：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract tests\test_scene_panel_architecture.py::test_scene_panel_scope_style_override_editor_writes_section_styles tests\test_scene_panel_architecture.py::test_scene_style_rules_block_wraps_override_section_as_stable_object -q
```

结果：

```text
3 passed in 13.82s
```

## 7. 本轮结论

本轮删除了场景样式区最后一批 editor 内部控件兼容别名，并把审计证据同步到 `SceneStyleRulesBlock.editor`。这一步继续减少页面层对控件实现的了解，让后续做真正的样式区内容板块重排、冗余文本删除和模板管理一致化更稳。
