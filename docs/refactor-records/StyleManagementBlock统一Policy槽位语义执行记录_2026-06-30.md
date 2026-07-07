# StyleManagementBlock 统一 Policy 槽位语义执行记录

日期：2026-06-30

## 1. 本轮目标

上一轮已经把场景分区当前态同步到了 `StylePolicyControlDeck`，但继续审计后发现还有一个更底层的命名断点：

```text
用户/设计层：source / policy / editor / preview / receipt
代码旧协议：source / scope / rules / difference / editor / preview / receipt
```

其中 `rules` 实际承载的是样式策略区，也就是 `StylePolicyControlDeck`。如果继续把它叫 `rules`，模板管理、场景规划、执行前复核在设计语言上仍会分叉：文档说是 policy，控件属性说是 rules，测试也只能验证旧名。

本轮目标不是删除旧名，而是新增 `policy` 作为稳定语义别名，让后续统一五槽位时有可测试、可巡检、可迁移的入口。

## 2. 当前问题

### 2.1 已经存在的好基础

`StyleManagementBlock` 已经有：

- `StyleManagementContentPlan`
- `style_management_content_plan`
- `source_slot`
- `scope_slot`
- `rule_control`
- `difference_slot`
- `preview_slot`
- `receipt_slot`

这说明内容板块抽象已经存在。

### 2.2 仍不够统一的地方

| 旧表达 | 真实含义 | 问题 |
| --- | --- | --- |
| `rules` | 样式策略区 | 设计层不会把“rules”理解为统一策略槽 |
| `rule_control` | `StylePolicyControlDeck` | 控件类型已经是 policy，但外层属性仍是 rule |
| `style_management_has_rules` | 是否有策略区 | 测试和巡检读到的是旧语义 |
| `style_management_rule_control_ready` | policy projection 是否可用 | readiness 的名字仍停留在旧包装 |

这类问题不会立刻造成 UI 崩坏，但会让后续每个页面继续各说各话。

## 3. 本轮实现

### 3.1 `StyleManagementContentPlan` 新增 policy 语义

新增：

```python
slots()
encoded_slots()
policy
```

含义：

```text
sections(): 兼容旧内部名，仍返回 rules
slots():    面向设计和页面巡检，返回 policy
```

示例：

```text
sections = source|scope|rules|difference|editor|preview
slots    = source|scope|policy|difference|editor|preview
```

### 3.2 `StyleManagementBlock` 新增 policy 属性

新增 widget 属性：

| 属性 | 含义 |
| --- | --- |
| `style_management_slot_plan` | 用户/设计语义槽位计划 |
| `style_management_has_policy` | 是否启用策略槽 |
| `style_management_has_policy_slot` | 是否有真实策略控件 |
| `style_management_policy_control_protocol` | 策略控件协议 |
| `style_management_policy_control_ready` | 策略控件是否能接收投影 |

保留旧属性：

| 旧属性 | 保留原因 |
| --- | --- |
| `style_management_content_plan` | 兼容已有测试和审计文档 |
| `style_management_has_rules` | 避免一次性破坏旧链路 |
| `style_management_rule_control_protocol` | 兼容场景样式旧包装 |
| `style_management_rule_control_ready` | 兼容既有守门 |

## 4. 三入口对齐结果

### 4.1 模板样式编辑

```text
content_plan = source|scope|editor
slot_plan    = source|scope|editor
has_policy   = False
```

说明：模板基线编辑页本身不展示策略开关，仍以参数编辑为主。

### 4.2 场景分区样式

```text
content_plan = source|scope|rules|difference|editor|preview
slot_plan    = source|scope|policy|difference|editor|preview
has_policy   = True
policy_ready = True
```

说明：场景页继续兼容旧 `rules`，但设计巡检可以用 `policy` 判断策略区。

### 4.3 执行前复核

未挂策略控件的基础模式：

```text
slot_plan  = source|scope|difference
has_policy = False
```

真实执行前复核页面挂入只读 `StylePolicyControlDeck` 后：

```text
slot_plan  = source|scope|policy|difference|preview
has_policy = True
policy_ready = True
```

这证明 `StyleManagementBlock` 不再只靠 mode 判断槽位，而能根据真实 slot 组合得到有效结构。

## 5. 代码落点

| 文件 | 变更 |
| --- | --- |
| `src/shared/ui/style_management_block.py` | `StyleManagementContentPlan` 增加 `slots()` / `encoded_slots()` / `policy`；`StyleManagementBlock` 增加 policy 语义属性 |
| `tests/test_small_widget_architecture.py` | 守住模板、场景、执行前复核三类 block 的 `slot_plan` 和 policy 属性 |
| `tests/test_quick_execution_detail_architecture.py` | 守住执行前复核真实页面挂入只读 policy deck 后的 `slot_plan` |

## 6. 验证

已通过：

```bash
python -X utf8 -m py_compile src\shared\ui\style_management_block.py tests\test_small_widget_architecture.py tests\test_quick_execution_detail_architecture.py
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row -q
```

结果：

```text
2 passed
```

## 7. 后续差距

### P0：逐步把业务页面巡检改读 `slot_plan`

后续测试和页面巡检应优先读：

```text
style_management_slot_plan
style_management_has_policy
style_management_policy_control_ready
```

旧的 `rules` 属性暂时保留，但不应作为新设计文档和新测试的主表达。

### P0：模板管理补只读 policy 槽入口

模板页现在 `has_policy=False` 是合理的当前态，但不是最终优秀态。后续如果要让模板管理成为“基线 + 被哪些场景覆盖”的总入口，应新增只读 policy 槽：

```text
模板样式
-> 被场景 A / 场景 B 覆盖
-> 点击进入对应场景分区样式
```

### P1：把 difference 纳入 receipt 语义

目前 `difference` 仍是独立槽位。长期看可以继续保留，但在用户心智上它更像 receipt 的一部分：

```text
preview: 现在长什么样
receipt: 与基线差在哪里、执行会怎么处理
```

后续可考虑新增 `style_management_feedback_plan` 或把差异摘要并入 receipt 语义层。

## 8. 本轮结论

这轮推进的是命名边界，不是视觉大改。它解决的是复用体系里一个很容易被忽略的问题：同一个控件底层已经叫 `StylePolicyControlDeck`，外层板块却还叫 `rules`。

现在开始，新的设计和测试可以使用 `policy` 作为统一策略槽位名称。旧 `rules` 继续兼容，降低迁移风险；新 `policy` 负责承接后续模板管理、场景规划、执行前复核的高复用统一规划。
