# Scene / Template 边界修复方案

日期：2026-07-01

关联记录：

- `docs/refactor-records/SceneTemplateBoundary边界确认记录_2026-07-01.md`

## 1. 修复目标

把当前“模板章节规划”和“场景处理范围”之间的重复定义收束掉。

最终程序应满足：

```text
模板定义文档结构和默认格式。
场景定义任务边界和格式例外。
运行时根据模板识别当前文档，再按场景边界执行。
```

本方案不是一次性删除旧字段，而是分阶段迁移，保证已有配置和运行逻辑不被突然破坏。

## 2. 当前需要修复的问题

### 2.1 场景 UI 重复展示章节区域

当前入口：

- `src/ui/panels/scene_panel.py`
  - `CARD_DEFINITIONS["scn_scope"] = ("处理范围", ...)`
  - `CARD_DEFINITIONS["scn_style_rules"] = ("分区样式", ...)`
- `src/ui/panels/scene_scope_sections.py`
  - `SCENE_SCOPE_ZONE_SECTION_TITLE = "处理范围"`
  - `SCENE_SCOPE_ZONE_SECTION_DESCRIPTION = "选择本场景要处理的文档区域。"`
- `src/ui/panels/scene_overview_projection.py`
  - `SceneOverviewRowSpec(key="scope", label="处理范围", ...)`

问题：

`处理范围` 当前直接展示 `format_scope.sections` 的 9 个区域，用户会理解成“场景在定义文档章节”。

### 2.2 场景格式例外命名不清

当前入口：

- `src/ui/panels/scene_panel.py`
  - `CARD_DEFINITIONS["scn_style_rules"] = ("分区样式", ...)`
- `src/ui/panels/scene_style_override_sections.py`
  - `SCENE_STYLE_OVERRIDE_SECTION_TITLE = "分区样式"`
- `src/ui/panels/scene_overview_projection.py`
  - `使用{template}，分区样式跟随模板`

问题：

`分区样式` 没有表达“这是相对模板的例外”，容易被误解成场景里又有一套区域格式体系。

### 2.3 摘要文案把两类职责绑在一起

当前入口：

- `src/ui/panels/scene_summary_projection.py`
  - `detail="分区样式在独立页面设置。"`

问题：

处理门禁和格式例外被同一句话绑在一起，进一步强化了“处理范围”和“分区样式”互相定义的错觉。

### 2.4 数据模型仍保留历史硬编码区域

当前入口：

- `src/config/scene.py`
  - `FormatScopeConfig.sections`
  - `SceneWorkspace.available_sections`
  - `SceneWorkspace.section_styles`

问题：

这些字段暂时不能删除，但也不能作为新 UI 的主模型继续扩散。

## 3. 修复原则

### 3.1 不破坏旧配置

旧字段保留：

- `format_scope`
- `available_sections`
- `section_styles`

但它们进入兼容层，不再作为新 UI 的主要解释模型。

### 3.2 不再让场景定义章节

新 UI 不出现“正文、参考文献、附录、摘要、目录”等硬编码 checkbox。

这些名称只能来自：

- 模板结构规划
- 当前文档运行时识别结果

### 3.3 场景只保留高层边界

场景只表达：

- 跟随模板默认
- 仅正文
- 全文
- 执行前确认

这些是“任务边界”，不是“章节定义”。

### 3.4 格式覆盖必须被描述为例外

`section_styles` 在 UI 上统一表达为：

```text
格式例外
```

含义：

```text
默认全部跟随模板；只有需要局部不同格式时才添加例外。
```

## 4. 目标 UI

### 4.1 场景概览

目标：

```text
当前场景

场景策略
  资料包：未开启
  套用模板：默认格式
  作用边界：跟随模板默认
  格式例外：无
```

变化：

- `处理范围` 改为 `作用边界`
- `套用格式` 改为 `套用模板`
- `分区样式跟随模板` 改为 `无格式例外` 或 `N 个格式例外`

### 4.2 左侧导航

目标分组：

```text
场景概览

场景策略
  作用边界
  格式例外
  启用模块

输入与资料
  输入与资料

输出
  输出设置
```

变化：

- `格式与模板` 改为 `场景策略`
- `处理范围` 改为 `作用边界`
- `分区样式` 改为 `格式例外`

### 4.3 作用边界详情页

目标：

```text
作用边界
章节识别来自当前模板；这里仅设置本场景允许处理到哪里。

[跟随模板默认]
[仅正文]
[全文]
[执行前确认]

模板结构预览：正文、参考文献、附录...
```

约束：

- 模板结构预览只读。
- 不允许在这里新增/删除章节类型。
- 不直接编辑 `format_scope.sections` 的 9 个硬编码开关。

### 4.4 格式例外详情页

目标：

```text
格式例外
默认全部跟随模板；只有需要局部不同格式时才添加例外。

当前：无格式例外
```

有例外时：

```text
参考文献：独立格式
附录：独立格式
```

约束：

- 例外必须绑定模板识别出的结构。
- 不允许创建新结构。
- 关闭作用边界时，应提示该例外不会生效，但不让格式例外反过来决定区域是否存在。

## 5. 数据模型修复方案

### 5.1 新增场景作用边界语义层

建议新增轻量配置，例如：

```python
@dataclass
class SceneApplicationBoundaryConfig:
    mode: str = "follow_template"
    confirm_before_apply: bool = False
```

可选 `mode`：

- `follow_template`
- `body_only`
- `full_document`
- `confirm_before_apply`

说明：

这不是章节定义，只是运行时过滤策略。

### 5.2 保留 `FormatScopeConfig` 为兼容层

过渡期：

```text
format_scope.sections 继续用于旧场景读取和旧运行逻辑。
新 UI 不直接编辑它。
```

后续迁移：

```text
format_scope.sections -> SceneApplicationBoundaryConfig.mode
```

兼容规则：

- 全部或大部分区域开启：推断为 `follow_template` 或 `full_document`
- 仅正文开启：推断为 `body_only`
- 复杂组合：推断为 `confirm_before_apply`，并保留旧字段作为高级兼容数据

### 5.3 `section_styles` 改为格式例外解释

保留字段：

```python
section_styles: dict
```

但 UI 和文案必须改为：

```text
格式例外
```

而不是：

```text
分区样式
```

### 5.4 场景概览的最终信息边界

场景概览只回答用户一眼需要知道的事：

```text
这个场景是否用资料包。
这个场景套用哪个模板。
这个场景允许处理到什么程度。
这个场景有没有相对模板的格式例外。
```

因此，概览中的主卡片应收敛为：

- `资料包`
- `作用边界`
- `套用模板`
- `格式例外`

其中 `套用模板` 和 `格式例外` 可以合并在同一个设置行中表达：

```text
使用默认格式，无格式例外
使用默认格式，参考文献有格式例外
```

`交付结果` 不作为默认主信息。只有当场景存在多版本、资料清单、资料包、结构化中间件或非最终 Word 的特殊交付时，才在概览中出现。

`执行预览` 和 `编号策略` 不属于场景结构定义。它们可以作为执行入口或执行前预览存在，但不能被解释成“场景重新定义章节/编号规则”。后续 UI 清理时，应优先把编号策略归到执行前选择或对应的模板/执行配置里，避免与模板章节规划重复。

### 5.5 不再保留“核对依据”主路径

`核对依据`、样本文档、覆盖证据和常见说法属于诊断资料，不属于普通用户第一屏。它们只适合放进折叠的高级/诊断区域，用来追溯场景覆盖是否足够。

## 6. 分阶段执行计划

### P0：文案和边界记录

状态：已开始。

已完成：

- 新增边界确认记录：
  - `docs/refactor-records/SceneTemplateBoundary边界确认记录_2026-07-01.md`

本轮新增：

- 本修复方案：
  - `docs/audits/SceneTemplateBoundary修复方案_2026-07-01.md`

### P1：低风险 UI 改名

目标：

只改用户可见命名，不改数据结构。

文件：

- `src/ui/panels/scene_panel.py`
- `src/ui/panels/scene_scope_sections.py`
- `src/ui/panels/scene_style_override_sections.py`
- `src/ui/panels/scene_overview_projection.py`
- `src/ui/panels/scene_summary_projection.py`

改动：

- `处理范围` -> `作用边界`
- `分区样式` -> `格式例外`
- `套用格式` -> `套用模板`
- `分区样式跟随模板` -> `无格式例外`
- 删除 `分区样式在独立页面设置。`

测试：

- `tests/test_scene_panel_architecture.py`
- `tests/test_scene_overview_projection.py`
- `tests/test_ui_copy_guardrails.py`

验收：

```text
主 UI 不再出现“处理范围”“分区样式”。
概览能解释“模板”和“例外”的关系。
```

### P2：隐藏硬编码区域 checkbox

目标：

不再让用户直接编辑 9 个硬编码区域。

文件：

- `src/ui/panels/scene_scope_sections.py`
- `src/ui/panels/scene_panel.py`
- `src/ui/panels/scene_summary_projection.py`

改动：

- `作用边界` 详情页改为高层模式选择。
- 旧 checkbox 移到高级兼容区，默认隐藏。
- 区域列表改为只读预览，并明确来源：
  - 模板结构
  - 当前文档识别结果

测试：

- 原 `format_scope.sections.*` 导航测试暂时保留，但归类为兼容入口。
- 新增作用边界模式测试。

验收：

```text
普通用户路径不再出现 9 个区域 checkbox。
旧场景仍能加载。
```

### P3：引入作用边界配置

目标：

让场景模型有明确的新语义层。

文件：

- `src/config/scene.py`
- `src/config/library.py`
- 场景保存/加载相关测试

改动：

- 新增 `SceneApplicationBoundaryConfig`
- `SceneWorkspace` 增加 `application_boundary`
- 老配置加载时从 `format_scope` 推断新字段
- 保存时保留旧字段一段时间，避免破坏兼容

测试：

- 新旧 scene JSON round-trip
- 默认场景迁移
- 内置场景迁移

验收：

```text
新 UI 写 application_boundary。
旧 format_scope 仍能读。
```

### P4：运行时接入模板结构识别

目标：

实际执行时不再以场景硬编码区域作为结构来源。

改动方向：

```text
TemplateConfig.heading_model
-> 当前文档结构识别
-> SceneApplicationBoundaryConfig 过滤
-> section_styles 格式例外
```

验收：

```text
章节识别结果来自模板。
场景只决定是否处理、是否确认、是否加格式例外。
```

### P5：清理兼容层

目标：

确认所有场景迁移完成后，再决定是否删除或降级 `format_scope.sections`。

前置条件：

- 所有内置场景有 `application_boundary`
- 所有 UI 不再依赖 `format_scope.sections` 做主路径
- 运行时通过模板结构投影执行

## 7. 测试守门清单

必须新增或调整测试：

### 7.1 文案守门

禁止主路径出现：

- `处理范围`
- `分区样式`
- `分区样式在独立页面设置`

允许兼容代码或旧测试中出现，但必须不在用户主路径。

### 7.2 结构来源守门

测试断言：

```text
场景主 UI 不直接展示硬编码区域 checkbox。
区域预览标注来源为模板或运行时识别。
格式例外不创建区域。
```

### 7.3 兼容守门

测试断言：

```text
旧场景 format_scope.sections 可以读取。
旧 section_styles 可以读取。
保存不会丢失旧字段。
```

### 7.4 行为守门

测试断言：

```text
作用边界为 body_only 时，仅允许正文策略。
作用边界为 follow_template 时，由模板结构决定。
格式例外只在命中结构上生效。
```

## 8. 风险与处理

### 8.1 风险：一次性删除 `format_scope` 会破坏旧场景

处理：

不删除，先兼容读取。

### 8.2 风险：运行时尚未有完整模板结构投影

处理：

P1/P2 只改 UI 和解释，不动运行时核心。

### 8.3 风险：格式例外仍依赖旧 variant key

处理：

短期继续用 `references_body`、`appendix_body` 等 key。
长期让这些 key 映射到模板结构 ID。

### 8.4 风险：测试大量依赖旧命名

处理：

分阶段更新测试：

- P1 改文案测试
- P2 改 UI 结构测试
- P3 改数据模型测试
- P4 改运行时语义测试

## 9. 最终验收标准

最终通过标准：

1. 用户主路径只看到 `作用边界` 和 `格式例外`。
2. 用户不会看到场景自带的一套章节 checkbox。
3. 模板章节规划是唯一结构来源。
4. 场景不再定义章节，只定义任务边界。
5. 格式例外只能覆盖模板结构，不能创建结构。
6. 旧场景配置能加载，不丢数据。
7. 执行逻辑能按模板识别结果和场景边界运行。

## 10. 推荐下一步

下一步优先做 P1：

```text
低风险 UI 改名 + 文案收敛
```

原因：

- 不动数据结构。
- 不动运行时。
- 能立刻降低用户困惑。

P1 完成后再做 P2，把硬编码 checkbox 从普通路径拿掉。
