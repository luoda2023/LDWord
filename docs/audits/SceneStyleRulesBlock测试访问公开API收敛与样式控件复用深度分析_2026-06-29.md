# SceneStyleRulesBlock 测试访问公开 API 收敛与样式控件复用深度分析

日期：2026-06-29

## 1. 本轮结论

这轮判断是：样式区和模板管理的一致性，不能只靠视觉上长得相似，也不能只靠底层控件复用。真正需要稳定的是四层边界：

| 层级 | 应该统一的内容 | 当前状态 | 本轮处理 |
| --- | --- | --- | --- |
| 用户任务 | 模板是基线，场景是覆盖，执行是回执 | 大方向已经清楚 | 继续记录为主线 |
| 内容板块 | 来源、范围、规则、差异、编辑、预览 | 已有 `StyleManagementBlock` 和 content plan | 仍需继续把页面文案和布局压回这些板块 |
| 对象边界 | 页面不直接知道底层控件字典和 editor 内部字段 | `SceneStyleRulesBlock` 已建立，但测试仍有旧访问 | 本轮收敛测试观察点 |
| 控件实现 | 字体、字号、缩进、行距等字段控件复用 | 已通过 `StyleEditingSection` / `StyleControlSurface` 复用 | 保持，不重复造控件 |

因此，后续优化不应该继续堆说明文字。正确方向是：让结构本身说明用户正在做什么，让页面只表达“当前来源、影响范围、是否独立、哪里可编辑、预览结果”，把内部 key、统计数、长风险解释都下沉到 tooltip、审计详情或高级面板。

## 2. 当前链路对照

模板管理链路已经接近稳定对象管理：

```text
模板详情
  -> StyleManagementBlock
  -> StyleEditingSection
  -> StyleControlSurface
  -> ParagraphStyleEditor
```

用户理解的是“我正在编辑模板基线样式”。页面可以围绕一个对象展开：当前模板、参数概览、预览、字段编辑。

场景分区样式链路现在是：

```text
_StyleRulesDetail
  -> SceneStyleRulesBlock
  -> SceneStyleOverrideSection
  -> StyleManagementBlock
  -> StyleRuleControlDeck
  -> StyleEditingSection
  -> StyleControlSurface
```

这条链路已经在控件层高度复用模板管理，但用户仍可能觉得“不说人话”，原因是场景侧多了两类任务：

1. 处理范围：本次处理哪些文档区域。
2. 分区样式：这些区域跟随模板，还是被当前场景单独覆盖。

这两件事有关联，但不是同一个任务。后续必须继续把 `scn_scope` 和 `scn_style_rules` 的边界做清楚，避免用户以为“勾选处理范围”等于“启用样式覆盖”。

## 3. 本轮发现的边界问题

上一轮已经把开关状态、导航目标、编辑器写回逐步收进 `SceneStyleRulesBlock`。但测试里仍有几处直接访问旧内部字段：

```python
scope._variant_toggles["references_body"]
scope._section_font_cn
scope._section_line_value
```

这说明对象边界还没有完全被测试保护住。即使生产代码已经改走 block API，测试如果继续依赖内部控件字典和 editor 字段，后续重排控件、替换布局或拆分板块时，测试会把旧结构锁死。

本轮选择先迁移“观察点”，不迁移“编辑动作”：

| 类型 | 旧访问 | 新访问 |
| --- | --- | --- |
| 分区开关高亮 | `_variant_toggles["references_body"]` | `override_toggle_for_variant("references_body")` |
| 字体字段高亮 | `_section_font_cn.property(...)` | `editor_widget_for_field("font_cn").property(...)` |
| 行距字段高亮 | `_section_line_value.property(...)` | `editor_widget_for_field("line_spacing_pt").property(...)` |
| 批量恢复状态 | `_variant_toggles[...] .isChecked()` | 从 block 取得 toggle 后检查状态 |
| 测试触发开关 | 直接 `setChecked(True)` | `set_override_checked("references_body", True)` |

这样做的意义不是减少几行代码，而是把测试语言改成用户和产品语言：

```text
我要参考文献正文的样式开关
我要中文字体字段的导航目标
我要行距字段的导航目标
```

而不是：

```text
我知道内部有一个 dict
我知道 editor 里有一个 font_cn 控件
```

## 4. 与模板管理一致性的真实标准

后续不要追求“场景页面和模板页面每一块完全一样”。两者的业务不同。真正应该一致的是信息顺序和控件归属：

| 信息顺序 | 模板管理 | 场景分区样式 |
| --- | --- | --- |
| 当前对象 | 当前模板 / 当前样式项 | 当前场景 / 当前分区 |
| 来源 | 模板基线 | 跟随模板或当前场景覆盖 |
| 影响范围 | 模板内对应样式项 | 标题、正文、参考文献、附录等分区 |
| 规则 | 模板参数规则 | 是否启用独立样式，哪些分区覆盖 |
| 差异 | 模板字段变化 | 当前场景相对模板的字段变化 |
| 编辑 | 字段控件 | 同一套字段控件 |
| 预览 | 页面或段落效果 | 当前分区有效样式效果 |

因此，`SceneStyleRulesBlock` 的目标不是替代所有业务逻辑，而是成为场景分区样式的稳定对象区：

```text
页面层负责：
  当前 scene / template 是谁
  业务投影如何计算
  何时保存回 scene

SceneStyleRulesBlock 负责：
  分区样式区有哪些控件
  哪个分区开关对应哪个目标
  哪个字段控件对应哪个 field_id
  如何切换可编辑态
  如何把 editor 写回 StyleConfig
```

只要页面层继续直接访问 `_variant_toggles`、`_section_style_editor`、`_section_font_cn` 这类内部结构，模板管理和场景样式就还只是“控件复用”，不是“对象复用”。

## 5. 内容板块应该继续重排

当前样式区最需要继续优化的是板块边界，而不是再加解释文案。建议目标结构如下：

```text
分区样式
  1. 来源
     跟随模板 / 已独立覆盖 / 未启用

  2. 范围
     哪些分区参与处理，哪些分区有样式覆盖

  3. 规则
     分区开关、恢复当前分区、恢复全部、撤销恢复

  4. 差异
     当前分区相对模板改了哪些字段

  5. 编辑
     只在启用独立样式后展开字段控件

  6. 预览
     当前分区有效样式，而不是技术说明
```

这里有两个关键点：

1. 未启用独立样式时，不应展示大面积灰色字段控件。主界面只保留来源、预览和“启用独立样式”入口。
2. 字段区只承担编辑，不承担解释。为什么不可编辑、为什么跟随模板、改了哪些字段，应由来源区和差异区表达。

## 6. 冗余文本处理原则

当前“看不懂”的一部分来自文字太多，但根因是文字在替结构补课。后续应按下面规则清理：

| 内容类型 | 主界面处理 | 下沉位置 |
| --- | --- | --- |
| 内部 key，如 `quick_formatting`、`green_l5` | 不直接显示 | tooltip 或开发诊断 |
| 计数，如 `template 13 / scene 37` | 只显示用户结论 | 详情面板或审计报告 |
| 风险长句 | 只显示短状态 | tooltip、详情弹窗、报告 |
| 禁用原因 | 一句短状态 | 控件 tooltip |
| 操作说明 | 改成按钮或行内动作 | 不用正文解释代替操作 |

主界面应该只留下这几类短语：

```text
跟随模板
已独立覆盖
未启用
可编辑
已调整 3 项
恢复为模板
启用独立样式
```

## 7. 本轮代码调整

文件：`tests/test_scene_panel_architecture.py`

本轮调整了测试访问方式：

1. 导航到 `section_styles.references_body.font_cn` 时，参考文献分区开关从 `scope._style_rules_block.override_toggle_for_variant("references_body")` 获取。
2. 导航到 `scene.section_styles.references_body.font_cn` 时，中文字体字段从 `scope._style_rules_block.editor_widget_for_field("font_cn")` 获取。
3. 导航到 `scene.section_styles.*.line_spacing_pt` 时，行距字段从 `scope._style_rules_block.editor_widget_for_field("line_spacing_pt")` 获取。
4. 单分区启用独立样式的测试触发改为 `scope._style_rules_block.set_override_checked("references_body", True)`。
5. 批量恢复和撤销恢复测试中的分区开关状态断言，改为通过 block 取得 toggle 后检查。

本轮没有删除 `_section_font_cn`、`_section_line_value` 等兼容字段。它们仍用于模拟用户编辑动作，例如设置字体、字号、缩进、行距。下一轮可以继续为这些编辑动作建立更高层的测试 helper 或 block API。

## 8. 后续必要开发

### P0：继续减少页面层直接接触 editor 内部字段

下一步可以处理这些测试和调用点：

```text
_section_font_cn.set_font_name(...)
_section_font_en.set_font_name(...)
_section_size_combo.set_pt(...)
_section_bold_switch.setChecked(...)
_section_line_type_combo
_section_space_before
_section_space_after
```

建议不要简单暴露更多控件属性，而是优先设计测试级或对象级写入能力，例如：

```python
SceneStyleRulesBlock.apply_editor_patch(
    font_cn="黑体",
    font_en="Arial",
    size_pt=14.0,
    bold=True,
)
```

如果直接暴露 `field_widget(...)` 给所有写操作，边界会再次退回“页面知道控件内部结构”。因此这一步需要谨慎。

### P0：把场景样式状态同步继续收进 block

目前 `_StyleRulesDetail` 仍负责较多 UI 同步。后续可以评估将以下动作组合成 block 级 API：

```text
apply_owner_state(...)
apply_preview_projection(...)
apply_comparison_projection(...)
sync_variant_rows(...)
set_restore_all_enabled(...)
set_undo_restore_all_enabled(...)
```

其中部分 API 已经存在，下一步是减少页面层的组合编排，让页面层更像投影协调器，而不是 UI 装配器。

### P1：视觉结构上拆清处理范围和分区样式

如果目标是优秀设计，建议把两者在第一层导航或详情内明确拆开：

```text
处理范围：本次处理哪些区域
分区样式：这些区域的样式是否跟随模板
```

用户不应该在同一个长页面里同时理解处理范围、样式覆盖、字段编辑、预览和恢复全部。拆分后可以减少大量解释文字。

### P1：建立主界面文本守门

建议补静态测试或快照测试，约束主界面不出现明显内部文本：

```text
template 13 / scene 37
quick_formatting
custom_basic
green_l5
manual / 提示
```

这些信息不是完全没用，而是不应该出现在主阅读层。

## 9. 本轮验证

已执行：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py::test_scene_style_rules_block_wraps_override_section_as_stable_object tests\test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract tests\test_scene_panel_architecture.py::test_scene_panel_scope_style_override_editor_writes_section_styles tests\test_scene_panel_architecture.py::test_scene_panel_restore_all_section_styles_returns_every_partition_to_template tests\test_ui_layout_hardening.py::test_template_and_scene_style_shells_keep_summary_preview_surface_order tests\test_ui_layout_hardening.py::test_scene_style_management_block_collapses_readonly_surface -q
```

结果：

```text
6 passed in 40.18s
```

## 10. 本轮结论

本轮没有改可见 UI，但推进了一个很关键的工程边界：测试开始通过 `SceneStyleRulesBlock` 的公开语义入口观察场景样式控件，而不是继续锁定内部字典和 editor 字段。

这对后续真正优化界面很重要。只有当测试和页面都不依赖内部控件摆放方式时，才能安全地继续重排内容板块、折叠未启用编辑区、删除冗余说明文本，并把场景分区样式做成和模板管理一致的高复用对象区。
