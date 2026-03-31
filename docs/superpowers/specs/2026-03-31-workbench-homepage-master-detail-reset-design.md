# Workbench Homepage Master-Detail Reset Design

- 日期：2026-03-31
- 状态：Draft / 供后续规划使用
- 目标：把当前 Workbench 首页的所有关键纠偏点收敛到一个文档里，供后续由他人继续规划与拆解

## 1. 背景

当前 Workbench 首页已经完成了真实执行链路、ExecutionWorker / ExecutionCenter / RecentRunPanel 等一系列生产路径打通，但首页信息架构走偏了。

当前落地出来的是一套 **command-center 双栏仪表盘**：

- 顶部 task command bar
- 中间左侧 strategy card + quick capability grid
- 中间右侧 execution center
- 底部 recent run

这条线基本符合以下旧文档：

- `docs/superpowers/specs/2026-03-28-workbench-command-center-redesign.md`
- `docs/superpowers/specs/2026-03-30-workbench-ui-polish-design.md`

但这 **不是** 用户当前明确要求的首页模型。

用户实际要的是更接近 DingTalk / 飞书工作台的 **主从式首页**：

- 左侧：纵向二级选择卡片
- 右侧：当前选中对象的详情与执行区

也就是说，问题已经不是“视觉不够好”，而是“首页 IA 本身不对”。

本设计文档的任务不是继续优化旧双栏仪表盘，而是正式把首页目标重置为 **master-detail 工作台**，并同步定义共享 UI 池收编方向。

## 2. 结论先行

后续首页不应再按“左边若干卡片 + 右边固定执行中心”的 dashboard 模型继续扩写。

后续首页应切换为：

1. 保留顶部任务条作为全局上下文
2. 中央主体改为 **左侧二级选择卡片 rail + 右侧 detail pane**
3. 左侧卡片不再是“装饰性的快捷卡”
4. 左侧每一项必须是一个**明确对象**
5. 右侧内容必须严格随左侧选中对象切换
6. 新定义出来的控件不能只埋在 `workbench/` 私有目录里，必须回流 `src/shared/ui/`
7. 当前 `Card` 视觉基线不合格，需要重做 shared `Card V2`

## 3. 为什么必须重置

### 3.1 旧 spec 与当前真实目标已经分叉

旧 Workbench 首页设计文件描述的是：

- strategy card
- quick capability 2-column grid
- fixed execution center

这解释了为什么当前实现虽然“有两列”，但和用户说的“两列”完全不是一回事。

用户说的“两列”不是：

- 左边一堆卡片
- 右边执行中心

而是：

- 左边一个纵向二级对象选择区
- 右边一个随选中对象变化的详情区

### 3.2 当前首页没有吃到已有 UI 池成果

当前 Workbench 首页虽然用了少量 shared 样式/基础卡片，但整体上仍然是 page-local 拼装：

- `src/ui/panels/workbench/command_bar.py`
- `src/ui/panels/workbench/execution_center.py`
- `src/ui/panels/workbench/strategy_card.py`
- `src/ui/panels/workbench/heading_quick_card.py`
- `src/ui/panels/workbench/quick_fill_card.py`
- `src/ui/panels/workbench/recent_run_panel.py`

这导致两个问题：

1. 前期已经沉淀的共享控件语言没有系统复用
2. Workbench 新做出来的东西也没有回流共享池

### 3.3 当前 `Card` 基线不足以承载新的主从式首页

现有 `src/shared/ui/card.py` 适合做简单通用容器，但不适合作为下一阶段工作台的视觉基础。

问题包括：

- 表达层级弱
- 选中态语义弱
- summary / action / detail / selectable 等角色未分化
- 只能算“通用盒子”，不是稳定的页面语义基件

所以接下来不应该继续在旧 `Card` 上堆 objectName QSS，而是要定义 `Card V2`。

## 4. 当前状态审计

### 4.1 当前首页结构

当前首页主结构在：

- `src/ui/panels/workbench/panel.py`

当前结构是：

- `_command_bar`
- `_middle_container`
  - `_left_column`
    - `_strategy_card`
    - `_capability_grid`
      - `_heading_quick_card`
      - `_quick_fill_card`
  - `_right_column`
    - `_execution_center`
- `_recent_run_panel`

### 4.2 已有共享控件资产

当前仓库里已经存在、应当优先复用或升级的 shared UI 资产至少包括：

- `src/shared/ui/card.py`
- `src/shared/ui/search_input.py`
- `src/shared/ui/progress_indicator.py`
- `src/shared/ui/status_indicator.py`
- `src/shared/ui/collapsible_section.py`
- `src/shared/ui/form_row.py`
- `src/shared/ui/icon_button.py`
- `src/shared/ui/styled_combo_box.py`
- `src/shared/ui/toggle_switch.py`
- `src/shared/ui/module_step_list.py`

其中一部分甚至没有被暴露到 `src/shared/ui/__init__.py` 的公共导出面。

### 4.3 已有但不应继续 page-local 生长的 Workbench 组件

以下组件里有可复用的页面模式，但目前都还是 page-local：

- `TaskCommandBar`
- `ExecutionCenter`
- `StrategyCard`
- `RecentRunPanel`
- `HeadingQuickCard`
- `QuickFillCard`
- `CapabilityGrid`

后续不能继续把这些组件只留在 Workbench 私有目录里各写各的。

## 5. 首页新的产品定位

首页仍然是高频工作台，而不是向导页。

它仍然服务以下高频操作：

1. 快速换文档，保持当前策略，重新执行
2. 快速换策略，保持当前文档，重新执行
3. 快速调整某个高频对象，然后执行
4. 立即查看最近结果与报告

但首页的信息架构不再用“多个并列卡片区”表达，而改为：

> 先选对象，再看对象详情，再在对象上下文中执行动作

## 6. 新首页总体结构

## 6.1 页面骨架

新首页采用三层结构：

### 顶部：Global Task Strip

保留顶部全局任务条，但它只负责：

- 当前文档
- 当前策略
- 总体就绪态
- 主执行入口

它是全局 strip，不再承担页面主体组织角色。

### 中部：Master-Detail 主体

中部改为：

- 左：纵向二级选择卡片 rail
- 右：当前选中对象的 detail pane

这部分是本次重置的核心。

### 底部：可并入右侧 detail，非强制独立横向大区

`RecentRunPanel` 不再必须维持独立整页底栏形态。

它可以：

1. 作为右侧 detail pane 的一个结果区块存在
2. 或者仅在“输出与报告”对象下成为主内容

默认不再保留旧版那种固定横向底栏作为首页骨架要求。

## 6.2 为什么不再保留旧的底部 recent-run 大区

因为新首页的核心是对象驱动。

一旦首页切换为 master-detail，结果与报告应该是一个“对象”或“上下文区块”，而不是继续占一个独立横向结构层。

否则页面会重新退回：

- 上面一层
- 中间一层
- 下面再一层

最终又会变回旧 dashboard。

## 7. 左侧二级卡片定义

## 7.1 推荐模型：对象优先

左侧二级卡片推荐采用 **对象优先** 模型，而不是能力域优先或阶段优先。

原因：

1. 用户最容易理解“我现在在看哪个对象”
2. 右侧 detail pane 可以稳定映射
3. 不会重新长成“按阶段走”的向导页
4. 不会把多个能力硬塞进一个抽象分组里

## 7.2 左侧固定对象列表

推荐左侧固定为以下对象：

1. `当前任务`
2. `文档`
3. `执行策略`
4. `标题编号`
5. `Quick Fill`
6. `输出与报告`

后续如需扩展，也必须继续遵守“对象优先”原则，而不是继续在左侧堆散卡片。

## 7.3 每个左侧对象卡片的语义

### 1. 当前任务

表示整个运行任务的全局快照。

左卡片应显示：

- 当前文档名
- 当前策略名
- 总体就绪态
- 最近一次运行状态

### 2. 文档

表示当前输入文档对象。

左卡片应显示：

- 当前文档名
- 文档路径摘要
- 输出目录摘要
- 基础校验状态

### 3. 执行策略

表示当前执行策略对象。

这里的“执行策略”必须明确理解为：

- 模板绑定
- 场景绑定
- strict mode
- 模块画像
- 本次运行快捷覆盖项

它不是一个抽象标题，也不是若干小功能卡的总称。

### 4. 标题编号

表示标题编号规则对象。

左卡片应显示：

- 当前编号方案摘要
- 深度摘要
- 是否联动目录
- 是否存在覆盖项

### 5. Quick Fill

表示内容填充对象。

左卡片应显示：

- 数据来源摘要
- 当前实体/资产摘要
- 映射完成度
- 是否阻塞执行

### 6. 输出与报告

表示最近执行结果对象。

左卡片应显示：

- 最近输出文件摘要
- 最近报告状态
- 顶层错误摘要
- 打开入口状态

## 8. 右侧 detail pane 的通用契约

不论左侧选中哪个对象，右侧 detail pane 都应遵守统一结构契约。

推荐包含以下 5 类元素：

1. `对象头部`
2. `对象详情`
3. `对象动作`
4. `与执行的关系`
5. `最近结果/异常摘要`

这 5 类元素不一定都长成独立视觉卡，但语义上必须存在。

## 8.1 对象头部

用于回答：

- 现在看的是谁
- 这个对象当前状态如何
- 这个对象有没有主动作

## 8.2 对象详情

用于回答：

- 这个对象当前配置是什么
- 当前值是什么
- 哪些值是基础绑定，哪些是本次运行覆盖

## 8.3 对象动作

用于回答：

- 这个对象能做什么
- 切换、编辑、重置、另存为、进入高级配置等动作在哪里

## 8.4 与执行的关系

用于回答：

- 这个对象是否影响执行
- 阻塞点是什么
- 执行按钮是否应该出现在这里

## 8.5 最近结果/异常摘要

用于回答：

- 这个对象最近一次产生了什么结果
- 有没有错误
- 有没有报告入口

## 9. “执行策略”右侧 detail pane 的明确落地定义

当前最容易被误解的就是“执行策略”。

因此这里单独定义。

当左侧选中 `执行策略` 时，右侧必须至少出现以下 6 个区块：

### 1. 策略头部

显示：

- 策略名
- 策略来源类型
- 最近使用/修改信息
- 主动作入口

### 2. 策略绑定

显示：

- 当前模板
- 当前场景
- strict mode
- 模块画像/启用模块摘要

### 3. 本次运行覆盖项

显示：

- 标题编号覆盖摘要
- Quick Fill 覆盖摘要
- 其他首页高频覆盖项摘要

这个区块非常关键。

因为它把“策略本体”和“本次运行临时修改”明确分开，避免用户不知道自己到底改的是策略，还是本次运行临时状态。

### 4. 策略动作

显示：

- 切换策略
- 另存为策略
- 复制策略
- 重命名策略
- 恢复基线

### 5. 运行上下文

显示：

- 当前文档对该策略是否可执行
- 缺失项
- 输出位置摘要
- 主执行按钮

### 6. 最近结果摘要

显示：

- 最近输出文件
- JSON / Markdown 报告
- 顶层错误摘要

## 10. 其他对象右侧的内容映射

为了保证后续规划者不再抽象化右侧内容，这里把剩余对象的右侧最低内容要求写死。

### `当前任务`

右侧至少包括：

- 文档与策略总览
- 总体就绪态
- 主执行入口
- 最近一次运行结果

### `文档`

右侧至少包括：

- 文件信息
- 更换文档动作
- 输出目录
- 基础校验与阻塞项

### `标题编号`

右侧至少包括：

- 当前编号方案摘要
- 深度与目录联动
- 快速调整项
- 高级配置入口
- 该对象对执行的影响

### `Quick Fill`

右侧至少包括：

- 数据源
- 当前实体
- 映射完成度
- 预览填充范围
- 阻塞项与执行影响

### `输出与报告`

右侧至少包括：

- 最近输出文件
- JSON 报告
- Markdown 报告
- 错误摘要
- 打开目录/打开文件动作

## 11. 共享 UI 池重构方向

## 11.1 总原则

后续不允许继续把首页控件只做成 `workbench/` 私有组件。

这次首页重置过程中产生的稳定 UI 形态，必须回流 `src/shared/ui/`。

## 11.2 可直接复用的 shared 资产

以下组件可直接复用或在轻改后复用：

- `Card`
- `SearchInput`
- `ProgressIndicator`
- `StatusIndicator`
- `CollapsibleSection`
- `FormRow`
- `IconButton`
- `ToggleSwitch`
- `StyledComboBox`

## 11.3 可参考但需要泛化的现有组件

以下组件不应直接照搬，但可以提炼出共享模式：

- `ModuleStepList`
- `TaskCommandBar`
- `ExecutionCenter`
- `StrategyCard`
- `RecentRunPanel`

## 11.4 需要新增到 shared 池的组件

后续建议新增或正式化以下 shared 组件：

### 1. `MasterDetailShell`

职责：

- 左 rail + 右 detail 布局容器
- 支持空状态
- 支持无选中状态
- 支持响应式折叠策略

### 2. `SecondarySelectionRail`

职责：

- 纵向对象卡片列表
- 选中态
- hover / active / disabled
- 支持 title / subtitle / meta / badge

### 3. `SecondarySelectionCard`

职责：

- 单个对象卡片
- 支持 selected / warning / blocked / recent-result 状态表达

### 4. `DetailPane`

职责：

- 右侧 detail 主容器
- 统一头部与 section 组织规则

### 5. `DetailHeader`

职责：

- 对象标题
- 状态
- 次级说明
- 头部动作

### 6. `Badge / Tag / Pill`

职责：

- 小标签
- 来源标识
- 状态标识
- 覆盖项标识

### 7. `EmptyState / Skeleton`

职责：

- 无对象
- 加载中
- 缺失数据

### 8. `ResultMetaList`

职责：

- 输出文件
- 报告路径
- 错误摘要

## 11.5 shared 导出面要同步补齐

如果后续这些 shared 组件正式落地，`src/shared/ui/__init__.py` 必须同步调整，不能再让实际存在的共享组件散落在目录里但不对外导出。

## 12. `Card V2` 重做要求

## 12.1 为什么必须做 `Card V2`

当前 `Card` 只能胜任：

- 基础容器
- 简单标题 + 内容

但新首页需要的卡片角色已经明显分化：

- 可选对象卡片
- 结果摘要卡
- 动作卡
- 详情区块卡
- quiet meta card

这些不应继续通过 objectName + 局部 QSS 硬扭出来。

## 12.2 `Card V2` 目标

`Card V2` 至少要支持以下语义 variant：

1. `summary`
2. `detail`
3. `action`
4. `selection`
5. `quiet`

## 12.3 `selection` 卡片的最低要求

对于左侧二级选择卡片，`Card V2` 的 `selection` 语义至少要支持：

- selected
- hover
- blocked
- warning
- recent-success

并且要能表达：

- title
- subtitle
- meta line
- badge / tag
- trailing state indicator

## 12.4 视觉方向

新 `Card V2` 不应继续是“朴素白盒 + 细边框 + 阴影”的默认企业后台卡。

它应当：

- 层级明确
- selected 态足够强
- 详情区与选择区区分明显
- 结果/异常状态有稳定语言

## 13. Workbench 与 shared 的边界

## 13.1 应回到 shared 的

以下模式应视为 shared 资产：

- master-detail shell
- secondary selection rail
- selection card
- detail pane
- detail header
- badge/tag/pill
- result meta list
- card v2

## 13.2 应留在 Workbench 的

以下内容仍然属于 Workbench 业务层：

- `CurrentTaskState`
- `StrategySummaryState`
- `ExecutionResultState`
- Workbench adapters
- Workbench 业务命名与对象装配
- 真实执行调用链

也就是说：

shared 提供 **页面语言与控件**
Workbench 提供 **业务状态与装配**

## 14. 旧文档与本设计的关系

本设计文档用于统一收编当前首页重置方向。

后续规划时，建议按以下原则处理旧文档：

### 14.1 仍然有效的部分

- Workbench 已接通真实执行链路
- ExecutionCenter / ExecutionWorker / RecentRunPanel 的执行逻辑成果
- Workbench 业务状态与 adapter 方向

### 14.2 对首页 IA 已不再作为基线的部分

以下旧文档中涉及“首页布局骨架”的部分，不应继续作为首页基线：

- `2026-03-28-workbench-command-center-redesign.md`
- `2026-03-30-workbench-ui-polish-design.md`

原因不是这些文档无价值，而是它们描述的是旧 homepage model。

### 14.3 后续规划者应如何使用本设计

后续规划者应：

1. 以本设计文档作为首页 IA 基线
2. 把旧文档中与执行逻辑、状态、桥接相关的有效成果保留
3. 不再按旧 command-center 双栏结构继续扩页

## 15. 非目标

本轮重置不要求立即完成以下内容：

1. 所有能力对象一次性全部开发完成
2. Quick Fill 全量高级编辑器落地
3. 所有 shared 组件一次性做完
4. 主题系统整体推倒重来
5. 立即清理所有旧 Workbench 文件

## 16. 给后续规划者的建议起点

如果这份文档交给其他同事继续规划，推荐先做下面 3 件事：

### 1. 先冻结首页 IA

先确认：

- 左侧是否按对象优先固定为 6 项
- 顶部 strip 是否保留
- bottom recent-run 是否吸收进右侧 detail

### 2. 再定义 shared UI slice

先决定第一批 shared 组件：

- `Card V2`
- `SecondarySelectionCard`
- `SecondarySelectionRail`
- `DetailPane`
- `DetailHeader`

### 3. 最后再拆 Workbench 落地顺序

顺序建议是：

1. shared UI 基线
2. 首页 master-detail 骨架
3. `执行策略` 对象先落地
4. `文档` / `当前任务`
5. `标题编号`
6. `Quick Fill`
7. `输出与报告`

## 17. 一句话总结

当前 Workbench 首页后续不应继续优化旧式 command-center 双栏卡片页，而应重置为：

> 顶部全局任务条 + 左侧对象化二级选择卡片 + 右侧对象详情与执行区

并且这次重置产生的稳定页面模式，必须同步回流到 `src/shared/ui/`，以 shared `Card V2` 和 master-detail 控件族作为新的 UI 基线。
