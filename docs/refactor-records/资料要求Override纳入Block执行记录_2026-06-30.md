# 资料要求 Override 纳入 Block 执行记录

日期：2026-06-30

## 1. 本轮目标

上一轮把资料规则预览做成了可读的首要概览，但还有一个结构问题：

```text
资料规则和预览在 block 里，
必填字段 override 和资产角色 override 仍散在 _ContentDetail 里。
```

这会让边界不完整，因为这两个 override 会直接影响资料规则预览：

- `required_material_fields` 会进入字段预览；
- `required_image_roles` 会进入图片/签章预览；
- 两者也会进入执行前资料检查。

所以本轮把“资料规则 + 必填字段 override + 资产角色 override + 预览 + 修复”收成一个更准确的资料要求对象。

## 2. 本轮实现

### 2.1 新语义对象

原内部类：

```text
_MaterialRuleSelectorBlock
```

推进为：

```text
_MaterialRequirementBlock
```

它现在持有：

- 资料规则选择工具条；
- 主资料规则输入；
- 资料规则列表输入；
- 必填字段输入；
- 资产角色输入；
- 资料规则预览 SummaryGrid；
- 未识别规则替换 / 移除动作；
- 导航定位入口。

### 2.2 保留兼容别名

`_ContentDetail` 现在新增：

```text
_material_requirement_block
```

同时保留：

```text
_material_rule_selector
```

作为兼容别名，指向同一个对象。

这样已有测试和旧调用仍可用，但新的结构语义已经清楚：这一块不只是 rule selector，而是 material requirement block。

### 2.3 写回入口收敛

`_ContentDetail._on_edited()` 不再单独写：

```text
profile.required_material_fields
profile.required_image_roles
```

这些现在由：

```text
_material_requirement_block.apply_to_profile(profile)
```

统一写回。

### 2.4 导航入口收敛

`required_material_fields`、`required_image_roles` 及具体字段/角色值的定位，也进入：

```text
_material_requirement_block.navigation_widget_for_field(...)
```

`_ContentDetail` 仍保留最终 fallback，但不再自己维护这两个 override 的 alias 表。

## 3. 与模板管理的一致性

这轮让输入资料详情更接近模板管理的成熟边界：

| 模板管理对象 | 资料要求对象 |
| --- | --- |
| 样式字段编辑 | 资料规则 / 必填字段 / 资产角色编辑 |
| 当前状态摘要 | 规则概览 |
| 参数预览 | 字段 / 图片 / 附件预览 |
| 差异与证据 | tooltip 中的真实 ID / 字段 key |
| 语义 block | `_MaterialRequirementBlock` |

关键变化是：页面层不再把“资料要求”拆成多个无主控件，而是把会共同影响资料预览和执行检查的输入收在同一个对象里。

## 4. 代码落点

| 文件 | 变化 |
| --- | --- |
| `src/ui/panels/scene_panel.py` | 新增 `_MaterialRequirementBlock` 语义；必填字段与资产角色输入移入 block；`_ContentDetail` 保留旧属性别名 |
| `tests/test_scene_panel_architecture.py` | 增加结构断言：`_material_rule_selector` 与 `_material_requirement_block` 指向同一对象，必填字段和资产角色由 block 持有 |

## 5. 验证

已执行：

```text
python -X utf8 -m py_compile src\ui\panels\scene_panel.py
python -X utf8 -m py_compile tests\test_scene_panel_architecture.py
python -X utf8 -m pytest \
  tests\test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract \
  tests\test_scene_panel_architecture.py::test_scene_panel_content_detail_edits_material_schema_contract \
  tests\test_scene_panel_architecture.py::test_scene_panel_content_detail_focuses_material_schema_contract_controls \
  tests\test_scene_panel_architecture.py::test_scene_panel_content_detail_repairs_unknown_primary_material_schema \
  tests\test_scene_panel_architecture.py::test_scene_panel_content_detail_replaces_unknown_material_schema_with_selected_registry_item \
  tests\test_scene_panel_architecture.py::test_scene_panel_content_detail_recommends_replacement_for_unknown_material_schema -q
python -X utf8 -m pytest \
  tests\test_scene_panel_architecture.py::test_scene_panel_applies_contract_family_recommended_delivery_defaults -q
```

当前结果：

```text
6 passed
1 passed
```

## 6. 仍需继续

这轮只是把 override 的归属收齐，还没有把 UI 层级彻底调整到优秀。

下一步建议：

### 6.1 明细格子分层

现在资料要求 block 的预览仍是：

```text
规则概览
资料规则校验
资料规则
适用场景族
字段预览
图片/签章
附件清单
```

有了“规则概览”后，“适用场景族”更像证据，可以考虑下沉或弱化。

### 6.2 Override 文案继续人话化

“必填字段”和“资产角色”比 `schema` 好懂，但对普通用户仍偏配置语言。后续可以考虑：

```text
必填资料字段
必需图片/签章
```

同时用 placeholder 说明“没有特殊要求时留空，按资料规则执行”。

### 6.3 独立文件化

当 `_MaterialRequirementBlock` 稳定后，可以移出 `scene_panel.py`：

```text
src/ui/panels/material_requirement_block.py
```

这样执行前复核、资料面板或未来的专门资料配置页都可以复用。

## 7. 本轮结论

资料输入这块现在从：

```text
页面层散落控件
```

继续推进为：

```text
资料要求 block：编辑、预览、修复、导航统一持有
```

这比继续局部改文字更接近用户要的“功能分布更合理、边界更清晰、与模板管理保持高度复用”。
