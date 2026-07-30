# Workbench「执行输出 / 问题处理」必要性深度审计

> 日期：2026-07-10  
> 范围：快速执行页在拖入试卷 Markdown 后突然出现的大型「问题处理」区域  
> 性质：产品信息架构、交互语义与代码链路审计  
> 原始边界：本文负责分析和重构边界定义  
> 执行状态：已于 2026-07-10 按本文四阶段完成收敛，详见[执行记录](../refactor-records/Workbench执行输出问题处理收敛执行记录_2026-07-10.md)

## 1. 结论先行

用户的直觉基本正确：

> 当前快速执行页中的整套「问题处理」面板，没有必要以常驻、默认展开的形式存在。

它不是生成文档主流程所必需的安全机制，而是把以下五类生命周期完全不同的信息，强行塞进了同一套“问题工单”界面：

1. 运行前资料提示；
2. 静态产品能力或插件边界；
3. 开发期配置完整性审计；
4. Word 对象预检确认；
5. 运行后的诊断、批量问题和结果入口。

因此，当前页面同时像预检器、工单系统、开发诊断台、帮助中心和结果浏览器。用户只是完成了“拖入题稿”，界面却自动完成了“打开问题中心、选择第一项、展开详情、展示内部证据”等一系列额外动作。

建议不是简单地压缩样式，而是重新划分责任：

- 快速执行主区只保留“生成按钮 + 单一可信状态 + 一个条件动作”；
- 整个内嵌「问题处理」面板从主流程删除；
- 真正的多问题诊断改为按需打开的“检查详情”抽屉或结果详情页；
- Schema、来源、参数归属、控件契约等内部证据迁到高级诊断；
- 插件与专业边界迁到方案说明或能力范围；
- 后端资料预检、对象预检和 Pipeline 安全保护必须保留。

换句话说：

> 应删除的是过度设计的前台问题管理器，不是底层检测与运行保护。

## 2. 截图中到底发生了什么

截图里实际上只有两条 issue：

1. “资料字段缺失：paper_title、subject、grade、duration、total_score”；
2. “插件 / 专业边界”的静态建议确认。

但页面把第一条问题继续拆成字段、Schema、当前资料来源等多行“证据”，再加上顶部状态、修复按钮、问题计数、筛选器、列表、详情和底部摘要，造成了“突然出现很多问题”的视觉错觉。

### 2.1 一个问题被重复呈现了至少六次

同一份资料预检结果被投射到：

1. 顶部橙色状态；
2. 右侧“补资料”按钮；
3. “2 项、1 项阻断”的队列摘要；
4. 问题列表第一行；
5. 下方详情标题、影响、动作；
6. 证据中的字段、Schema、来源逐行记录。

主要代码链如下：

- 生成资料问题：<code>src/ui/panels/workbench/quick_execution_detail.py:2428-2442</code>
- 写入顶部状态：<code>quick_execution_detail.py:2443-2467</code>
- 显示“补资料”：<code>quick_execution_detail.py:2449-2452</code>
- 显示问题面板：<code>quick_execution_detail.py:2453-2456</code>
- 再生成队列摘要：<code>quick_execution_detail.py:2025-2053</code>
- 再把详情投影成证据行：<code>src/ui/adapters/workbench_issue_projection.py:95-121</code>

这不是偶发的样式问题，而是当前信息架构没有规定“一个问题只能有一个主呈现位置”。

### 2.2 为什么拖入后会突然整块展开

当前代码主动采用了以下默认行为：

- 问题区域的初始状态就是展开：<code>quick_execution_detail.py:235</code>
- 一旦检测到 issue，立即显示整个 body：<code>quick_execution_detail.py:1995-2004</code>
- 填充列表后自动选择第一项：<code>quick_execution_detail.py:2167-2171</code>
- 选中后立即展示完整详情和证据：<code>quick_execution_detail.py:2191-2259</code>

也就是说，拖拽本身没有生成很多新数据；它只是触发了预检刷新，而页面又将预检结果自动展开到最深层。

这违反了渐进披露原则。用户完成的是“提供输入”，系统却未经请求自动进入了“诊断详情模式”。

### 2.3 为什么列表文字会重叠

列表项同时存在两套绘制：

- 原生 <code>QListWidgetItem</code> 保存并绘制完整文本：<code>quick_execution_detail.py:2145</code>
- 同一个 item 又安装了自定义透明行组件：<code>quick_execution_detail.py:2152</code>
- 自定义行组件再次绘制标签、标题和状态：<code>quick_execution_detail.py:2840-2866</code>
- 选中态 QSS 又让底层原生文字变成蓝色：<code>quick_execution_detail.py:2538-2545</code>

因此截图中并不是同一句文案被数据层重复添加，而是原生 item 文本与自定义 widget 在同一位置发生了双重绘制。

如果整块问题列表从主流程迁出，这个缺陷会自然消失；如果未来在抽屉中复用列表，也必须只保留一种绘制方式。

## 3. 当前两条问题是否真的应该出现

### 3.1 “资料字段缺失”在当前考试 Markdown 流程中是错误阻断

考试方案绑定了内部 Schema：

- <code>config_library/plans/exam/builtin/exam.json:81-84</code> 绑定 <code>exam_items_v1</code>
- <code>src/config/material_schema_registry.py:273-284</code> 定义相关资料字段

页面生成资料 issue 时却将字段、资产和 Schema 缺口统一硬编码为 <code>blocking=True</code>：

- <code>src/ui/adapters/workbench_material_issues.py:46-95</code>

这与实际运行策略矛盾：

- 考试方案配置 <code>require_material_package: false</code>
- 考试方案配置 <code>failure_policy: warn</code>
- 见 <code>config_library/plans/exam/builtin/exam.json:70-90</code>

真正运行时只在 <code>failure_policy == "block"</code> 时阻断普通资料缺口：

- <code>src/ui/panels/workbench/execution_runtime.py:114-144</code>

更关键的是，Markdown 执行路径会先解析题稿，再把解析出的信息注入运行上下文：

- Markdown 路径分流：<code>execution_runtime.py:102-112</code>
- 解析并注入字段：<code>execution_runtime.py:236-244</code>

而快速执行页面虽然已经用同一份 Markdown 展示题量、分值、答案和解析状态：

- <code>quick_execution_detail.py:984-1085</code>

却没有把解析结果回填到页面使用的 <code>_material_context</code>。页面继续拿空资料上下文做通用 Schema 检查：

- <code>quick_execution_detail.py:2428-2435</code>

于是形成了三套不一致的真相：

| 层级 | 当前判断 |
|---|---|
| 页面通用资料预检 | 五个字段缺失，并声称阻断 |
| 考试方案策略 | 缺失只警告，不要求资料包 |
| Markdown 实际运行 | 先解析题稿，再注入可用信息 |

因此截图里的“1 项阻断”和“会阻断本次运行”不能被视为真实执行结论。

#### 3.1.1 试卷自身的权威校验也不要求这五项全部存在

试卷题稿的领域校验位于：

- <code>src/shared/engine/exam_question_schema.py:1159-1195</code>

其语义是：

- 标题缺失只产生 warning；
- sections 缺失或为空才是 error；
- 并不要求 subject、grade、duration 和声明总分必须齐全。

这进一步说明：把五个元数据字段统一包装成阻断，既不符合方案配置，也不符合试卷领域校验。

#### 3.1.2 与既有试卷导入审计结论冲突

已有审计 <code>docs/audits/试卷MD题稿导入链路审阅分析_2026-07-10.md</code> 已明确指出：

- 考试场景的用户心智模型是一份 Markdown 题稿；
- <code>exam_items_v1</code> 是内部结构，不应表现为前台“资料包”；
- 题稿解析问题应归属输入源卡片；
- 不应在生成区额外制造一套“资料字段缺失”主流程。

当前问题面板重新把内部 Schema 暴露成用户必须处理的资料问题，正好与该方向相反。

### 3.2 “插件 / 专业边界”不是当前文件的运行问题

第二条 issue 来自静态能力边界，不是拖入当前 Markdown 后发现的异常：

- 生成函数：<code>src/ui/adapters/workbench_boundary_issues.py:19-45</code>
- 场景边界声明：<code>src/config/scene_coverage_manifest.py:637-680</code>

页面在每次 issue 刷新时无条件追加这类静态项目：

- <code>quick_execution_detail.py:2440</code>
- 静态缓存还包含 coverage、parameter、sample、control：<code>quick_execution_detail.py:2470-2485</code>

这些信息本质上属于：

- 产品能力范围；
- 方案说明；
- 发布治理；
- 开发期配置审计；
- 特定高风险行为发生时的确认。

它们不应在用户每次执行时被包装成“待处理问题”。

其“处理”动作也没有形成真实闭环：

- <code>plugin_manual_gate → quick_execute</code>：<code>src/ui/adapters/workbench_issue_navigation.py:161-164</code>
- 路由最终仍返回当前功能卡：<code>workbench_issue_navigation.py:846-852</code>

用户点击“处理”后仍回到当前快速执行页，并没有一个能够解除问题的具体动作。

因此，第二条 issue 应直接退出当前文件的运行问题队列。

## 4. 当前面板为何会演变到这么重

正式产品规格并没有要求快速执行区内嵌一套完整问题工单系统。

### 4.1 原始规格只要求紧凑状态与动态执行反馈

<code>docs/superpowers/specs/2026-03-31-workbench-homepage-redesign-v3-final.md</code> 的核心要求是：

- 执行控制由大按钮和一行就绪状态组成：<code>:168-181</code>
- ready 可执行；
- warning 仍可执行；
- error 才禁用；
- 执行后动态出现进度、模块列表、可折叠日志和结果：<code>:183-221</code>
- 强调“简洁的默认 + 强大的扩展 + 清晰的反馈”：<code>:574-590</code>

<code>docs/superpowers/specs/2026-03-30-execution-center-enhancement-design.md</code> 也将执行中心定义为：

- 启动 / 取消；
- 就绪态；
- 阶段与进度；
- 最终摘要；
- 见 <code>:72-82</code>、<code>:120-132</code>。

<code>docs/superpowers/specs/2026-03-28-workbench-command-center-redesign.md</code> 更明确要求：

- 命令区显示文档、策略、就绪态和执行；
- 不显示深层编辑、大段说明、冗长路径和详细日志；
- 见 <code>:90-115</code>；
- 执行区应固定、稳定、不能随着内容无边界增长：<code>:179-228</code>；
- 最近运行单独负责报告、错误与可选日志：<code>:229-244</code>。

结论是：正式规格要求的是紧凑执行控制，不是截图中的完整问题中心。

### 4.2 后续实现从“抽屉”漂移成了“嵌入式诊断台”

<code>docs/audits/场景功能分布边界与文案精简深度分析_2026-06-28.md</code> 曾明确提出：

- Workbench 应保持四区分工：<code>:139-147</code>
- 问题处理应是独立抽屉：<code>:159-171</code>
- 高级证据不是主流程节点：<code>:173</code>
- 前台只展示状态、动作、阻断和结果：<code>:177-195</code>
- 问题队列应折叠进抽屉：<code>:335</code>、<code>:378</code>

但后续实现采用了内联面板：<code>:386-402</code>。之后又不断向这个内联区域添加详情、证据和复检能力，使其“更像抽屉”：<code>:478-519</code>。

结果是：

1. 设计目标说“从主流程迁出”；
2. 实现却把它嵌入主页面；
3. 为弥补嵌入区域能力不足，又继续增加筛选、动作、详情和证据；
4. 最终形成今天截图中的大块诊断台。

这是典型的设计漂移，不是一个突然出现的孤立样式缺陷。

### 4.3 项目已经有过一次类似的正确收敛

<code>docs/refactor-records/Workbench执行输出常见说法浏览器移除执行记录_2026-06-30.md:20-36</code> 已经把“执行输出不应承载证据浏览器”作为重构原则：

- 删除筛选与列表；
- 保留一行摘要；
- 详细证据退出执行主区。

本次「问题处理」与当时的证据浏览器是同一类信息架构问题，可以沿用相同原则。

## 5. 逐区必要性判断

| 区域 | 是否保留 | 原因与目标位置 |
|---|---|---|
| “生成文档”按钮 | 保留 | 主任务入口 |
| 顶部状态容器 | 保留并重做 | 真正承担可生成、运行中、完成、失败；不要铺原始字段列表 |
| “补资料” | 条件保留 | 只在真实且可修复的资料缺口中作为唯一 CTA；考试 MD 场景可改为“补充信息（可选）”或不显示 |
| “问题处理”标题与计数 | 从主区删除 | 2 条信息不需要建立工单中心；有需要时改成“查看检查详情（N）” |
| “收起” | 删除 | 整个内联面板退出后不再需要 |
| “全部问题”筛选 | 删除 | 当前仅 2 项；高级抽屉达到约 8–10 条真实问题后才有价值 |
| “全部动作”筛选 | 删除 | 暴露内部 action group，普通用户没有决策价值 |
| 全局“处理” | 删除 | 与“补资料”重复；文案抽象；插件边界甚至自循环 |
| “已处理” | 立即删除 | 只改变内存标签，不验证问题是否真正修复 |
| “忽略” | 立即删除 | 不影响执行、不持久化，却让用户误以为风险已消失 |
| 问题列表 | 迁出主区 | 多个真实输入或运行问题可在检查抽屉 / 结果详情中呈现 |
| 自动选中首项 | 删除 | 用户没有主动请求查看详情 |
| 详情标题与元信息 | 主区删除 | 重复列表标题，并暴露内部类别、负责人和状态概念 |
| “影响”区 | 并入一句准确告警 | 当前多为按 action group 拼出的通用模板 |
| “动作”说明 | 删除 | 只是再次描述按钮行为 |
| “证据”区 | 迁到高级诊断 | 字段、Schema、来源等面向开发与支持，不面向普通生成流程 |
| “复检” | 主区删除 | 能监听的资料变化应自动刷新；外部状态才需要手动复检 |
| 常驻执行日志 | 默认折叠 | 运行后或失败时出现；不要与空闲态问题面板共同占满页面 |

## 6. “已处理 / 忽略”不是冗余，而是错误控制

这两个按钮目前只修改内存中的 issue dataclass：

- UI 调用：<code>quick_execution_detail.py:1770-1802</code>
- adapter 只执行 <code>replace(item, status=...)</code>：<code>src/ui/adapters/workbench_execution_adapter.py:554-573</code>

它们不会：

- 修改资料；
- 修改题稿；
- 修改方案；
- 写入持久状态；
- 改变 Runner 判断；
- 在重新检测后保留。

下一次预检刷新会重新创建全部 issue：

- <code>quick_execution_detail.py:2432-2440</code>

而阻断统计只统计 <code>blocking</code>，完全不考虑 status：

- <code>workbench_execution_adapter.py:295-299</code>

实际执行也不消费这些 issue 状态：

- <code>src/ui/panels/workbench/panel_v2.py:997-1012</code>

本地离屏实例复现得到：

| 操作 | 结果 |
|---|---|
| 初始状态 | 生成按钮可用，面板默认展开，显示 1 项阻断 |
| 点击“忽略” | issue 状态变为 ignored，但阻断数仍为 1 |
| 点击“复检” | issue 被重建，状态恢复 open |

这会制造严重误导：

- 详情可能表示“已忽略”；
- 标题仍显示“1 项阻断”；
- 实际执行仍完全不读取“忽略”。

因此它们不应等待后续优化，而应作为第一优先级删除。

## 7. 哪些底层能力必须保留

删除问题面板不等于删除检测。

### 7.1 资料运行时预检

必须保留：

- 资料要求诊断：<code>src/ui/panels/workbench/material_preflight.py:17-109</code>
- 失败策略：<code>material_preflight.py:460-471</code>
- Runner 阻断判断：<code>execution_runtime.py:114-144</code>
- Markdown 专用解析与验证：<code>execution_runtime.py:219-319</code>

这些逻辑并不依赖问题面板。正确做法是让页面展示 Runner 的真实门禁结论，而不是独立推导一套更严格的结论。

### 7.2 Word 对象预检

必须保留两层保护：

- 点击执行前的预检与确认：<code>src/ui/panels/workbench/panel_v2.py:997-1014</code>、<code>:1121-1200</code>
- Pipeline 内的权威保护：<code>src/pipeline/runner.py:240-248</code>、<code>:491-524</code>

Pipeline 会根据策略：

- 阻止严格 / 高风险执行；
- 对特定风险对象跳过相应模块；
- 把结论写入上下文和报告。

所以通用问题列表不是安全机制。

但不能直接删掉当前 <code>set_object_preflight_confirmation()</code> 提供的反馈：

- <code>quick_execution_detail.py:1393-1427</code>

否则首次点击可能被正确拦下，却没有清晰的继续或取消入口。它应替换成紧凑确认条或明确对话框，例如：

> 检测到 1 个对象风险，1 个模块将跳过。  
> [取消] [继续生成]

### 7.3 运行后诊断与结果入口

执行结果会生成以下 issue：

- 输出覆盖提醒；
- 方案范围 / 样式诊断；
- 批量资料问题；
- 题图修复队列；
- 题图事务报告入口。

生成位置：

- <code>src/ui/adapters/workbench_execution_adapter.py:211-221</code>

当前页面将它们继续塞回同一个问题列表：

- <code>quick_execution_detail.py:1485-1499</code>

这些数据模型和修复路由应保留，但显示位置应迁到“执行历史 / 结果详情”，主区只给出：

> 已完成，发现 2 项运行提醒。 [查看结果详情]

项目已有可复用目标：

- <code>ExecutionHistoryDetailPane</code> 已在 <code>panel_v2.py:279</code> 实例化；
- 执行控制器已向它写入结果：<code>src/ui/panels/workbench/execution_controller.py:205-272</code>；
- 但它尚未进入 <code>panel_v2.py:281-313</code> 的 <code>detail_map</code>，目前不是正常可导航页面。

因此它适合作为运行后 issue 的迁移承载区。

## 8. 推荐的目标信息架构

### 8.1 主流程

快速执行区只保留一行：

| 主动作 | 单一状态 | 条件动作 |
|---|---|---|
| 生成文档 | 可生成 / 生成中 45% / 已完成 / 失败 | 补充信息 / 去补齐 / 查看结果详情 |

推荐状态语义：

#### 无问题

> 可生成

#### 非阻断提醒

> 可生成；部分试卷信息未识别，将使用默认值。  
> [补充信息（可选）] [查看详情]

生成按钮保持可用。

#### 真阻断

> 无法生成：缺少必需资料。  
> [去补齐]

生成按钮禁用，且页面与 Runner 使用同一个阻断结论。

#### 对象风险确认

> 检测到 1 个对象风险，继续后将跳过 1 个模块。  
> [取消] [继续生成]

#### 运行完成

> 已完成；生成 1 个文件，发现 2 项提醒。  
> [查看结果详情]

### 8.2 信息归属

| 信息类型 | 应归属的位置 |
|---|---|
| Markdown 解析错误、题目结构错误 | 输入源卡片 |
| 真实必需资料缺口 | 生成区紧凑阻断条 |
| 可选元数据缺失 | 生成区轻提示或输入源详情 |
| Word 对象风险 | 执行前确认条 / 对话框 |
| 多项真实检查结果 | 默认关闭的检查详情抽屉 |
| Schema、来源、内部证据 | 高级诊断 |
| 插件、法律、专业能力边界 | 方案概览 / 帮助 / 能力范围 |
| 参数归属、样本 fixture、控件契约 | 开发审计和自动化测试 |
| 运行后诊断与修复入口 | 执行历史 / 结果详情 |

### 8.3 建议建立唯一门禁模型

当前 UI 预检、普通 Runner 和 Markdown Runner 分别推导状态，已经发生语义漂移。建议提取共享的 <code>ExecutionGateDecision</code>：

| 字段 | 含义 |
|---|---|
| <code>can_run</code> | 当前是否允许执行 |
| <code>requires_confirmation</code> | 是否需要用户显式确认 |
| <code>blocking_reasons</code> | 真正阻断原因 |
| <code>warning_reasons</code> | 不阻断提醒 |
| <code>primary_action</code> | 唯一主修复动作 |

页面只渲染该决策，Runner 也以同一决策或同一底层策略为依据。这样可避免再次出现“页面说阻断，按钮却可点击，实际运行又不阻断”的三方矛盾。

## 9. 代码拆除与迁移边界

### 9.1 可从快速执行页删除

主要范围：

- 面板、标题、筛选器、列表、详情、证据、状态按钮：  
  <code>src/ui/panels/workbench/quick_execution_detail.py:631-817</code>
- 问题查询、筛选、导航、证据动作、已处理 / 忽略：  
  <code>quick_execution_detail.py:1610-1802</code>
- 面板渲染、自动选中、筛选和资料问题修复入口周边：  
  <code>quick_execution_detail.py:1967-2406</code>
- 专属样式：  
  <code>quick_execution_detail.py:2497-2568</code>、<code>:2632-2653</code>
- 问题行、详情、显示名、计数等辅助函数：  
  <code>quick_execution_detail.py:2704-3090</code>

静态分析显示：

- <code>quick_execution_detail.py</code> 全文件约 3110 行；
- 名称包含 issue 的函数约 57 个；
- 仅这些函数体约 956 行；
- 加上约 187 行面板 UI 构造，整套问题 UI 占用约 1100 行代码。

这说明它已经不是一个轻量提醒，而是文件内的一套子产品。

### 9.2 可解除连接，但底层审计暂时保留

下列审计不应继续进入快速执行页：

- 插件与专业边界：<code>src/ui/adapters/workbench_boundary_issues.py:19-46</code>
- 样本 fixture 完整性：<code>workbench_boundary_issues.py:49-89</code>
- 参数归属注册表审计：<code>src/ui/adapters/workbench_execution_adapter.py:1151-1172</code>
- UI 控件契约注册表审计：<code>workbench_execution_adapter.py:1175-1254</code>

建议先解除它们与 <code>_emit_summary_changed()</code> 的连接，不立即删除底层函数。它们仍可服务于：

- 自动化审计；
- 方案治理；
- 发布检查；
- 开发诊断报告。

### 9.3 信号和导航

面板消失后，可以删除或停止公开的快速执行页 API：

- <code>current_issue_items</code>
- <code>current_filtered_issue_items</code>
- <code>set_issue_queue_filter</code>
- <code>set_issue_queue_action_filter</code>
- <code>set_issue_status</code>
- <code>set_active_issue</code>
- <code>current_active_issue_id</code>
- <code>current_issue_evidence_actions</code>

需要先迁移再删除：

- <code>issue_repair_requested</code>：<code>quick_execution_detail.py:190</code>
- 外层连接：<code>src/ui/panels/workbench/panel_v2.py:469</code>
- 通用修复路由：<code>panel_v2.py:797-861</code>

通用 <code>_open_issue_repair_target()</code> 仍可被结果详情或方案页复用，不必随面板一起删除。

“返回快速执行页后重新选择原 issue”的往返状态可删除：

- 携带 issue 上下文：<code>panel_v2.py:752-763</code>
- 返回后重新选中：<code>panel_v2.py:863-878</code>

如果未来保留独立检查抽屉，则应把这套状态迁到抽屉控制器，而不是继续由快速执行详情承担。

## 10. 测试与审计迁移

当前大量测试保护的是“控件存在和队列行为”，并不等于这些控件具有产品必要性。测试在这里固化了实现，而不是证明了需求。

### 10.1 删除或重写为紧凑状态契约

重点范围：

- <code>tests/test_quick_execution_detail_architecture.py:615-730</code>
- <code>tests/test_quick_execution_detail_architecture.py:1145-1299</code>
- <code>tests/test_quick_execution_detail_architecture.py:1606-1643</code>
- <code>tests/test_quick_execution_detail_architecture.py:1949-2094</code>
- <code>tests/test_workbench_detail_architecture.py:357-470</code>
- <code>tests/test_ui_copy_guardrails.py:662-724</code>

应把测试目标从：

- 是否存在双筛选器；
- 是否自动选择第一条；
- 是否能标记已处理 / 忽略；
- 是否逐行展示 evidence；

改为：

- 用户能否明确判断是否可生成；
- warning 是否仍允许执行；
- 真 blocker 是否禁用执行；
- 页面与 Runner 的阻断语义是否一致；
- 修复后是否自动恢复；
- 静态产品边界是否不再污染当前文件问题；
- 运行详情是否仍可按需访问。

### 10.2 必须保留的行为测试

对象预检的安全测试必须保留，只改变 UI 断言载体：

- warning 首次不创建 worker、确认后继续：  
  <code>tests/test_workbench_execution_session_architecture.py:495-580</code>
- strict finding 不创建 worker：  
  <code>tests/test_workbench_execution_session_architecture.py:584-630</code>

原本对问题列表或日志的断言，应改为对确认条 / 确认对话框和门禁状态的断言。

以下底层 adapter / runtime 能力也应保留：

- 资料要求计算；
- 对象预检转换；
- 输出、批量和题图结果转换；
- 修复导航目标计算；
- Pipeline 风险保护。

但原有“一律 <code>blocking=True</code>”测试契约必须改成策略感知。

### 10.3 需要同步更新的源码证据型审计

以下审计通过源码字符串要求“问题队列”存在，重构后必须改为验证新的真实目标：

- <code>src/config/scene_control_consistency_audit.py:56-76</code>
- <code>src/config/scene_material_repair_flow_audit.py:431-466</code>
- <code>src/config/scene_material_repair_flow_audit.py:501-524</code>
- <code>src/config/scene_object_preflight_action_audit.py:74-80</code>
- <code>src/config/scene_repair_routing.py:301-320</code>

新证据目标应是：

- 统一执行门禁；
- 紧凑对象确认；
- 唯一修复动作；
- 可访问的运行结果详情。

不能为了让旧审计通过而保留错误 UI。

### 10.4 建议新增的回归测试

1. 考试方案 <code>failure_policy=warn</code> 时，缺少可选元数据仍允许生成；
2. 真正 <code>failure_policy=block</code> 时，页面与 Runner 同时阻断；
3. Markdown 已解析字段不会再次产生假的“资料字段缺失”；
4. 静态插件 / 专业边界不进入当前文件问题；
5. 拖入题稿后页面高度不会突然被内联诊断面板撑开；
6. 对象 warning 仍要求显式确认，strict finding 仍禁止执行；
7. 运行后诊断可以从结果详情访问；
8. 列表若在抽屉复用，不再发生原生文本与自定义 widget 双重绘制；
9. 状态只有一个权威来源，不出现“按钮可用但文案说阻断”；
10. 输入源解析问题留在输入源卡片，不扩散到生成区重复呈现。

## 11. 推荐实施顺序

### 阶段 1：立即止血

1. 停止把静态 coverage、parameter、sample、control 审计追加到当前运行问题；
2. 删除“已处理 / 忽略”虚假控制；
3. 修复双重绘制；
4. 页面资料状态遵循 <code>failure_policy</code>；
5. 考试 Markdown 不再基于空 <code>_material_context</code>制造假阻断。

### 阶段 2：替换主界面

1. 建立统一 <code>ExecutionGateDecision</code>；
2. 将主区收敛为“按钮 + 状态 + 条件动作”；
3. 用紧凑确认条 / 对话框替代对象预检问题列表；
4. 日志默认折叠，只在运行中、失败或用户主动展开时出现。

### 阶段 3：迁移结果能力

1. 将 <code>ExecutionResultState.issue_items</code> 接到执行历史 / 结果详情；
2. 保留必要修复路由；
3. 只在主区显示“查看 N 项运行详情”；
4. 将内部 evidence 收进高级诊断。

### 阶段 4：清理遗留

1. 删除内联问题面板 builder、筛选、列表、详情、证据和专属样式；
2. 删除 active issue 往返状态；
3. 清理已无消费者的 UI adapter 和控件；
4. 重写直接耦合旧队列的测试与源码证据审计；
5. 做一次拖入、执行前确认、运行中、成功、失败五状态视觉回归。

## 12. 最终产品判断

截图红框里的内容不能被简单判断为“全都毫无价值”，但可以明确判断为：

- 绝大部分不应存在于当前页面；
- 其中一部分属于错误或虚假控制，应直接删除；
- 一部分属于底层安全能力，应保留但换成紧凑反馈；
- 一部分属于运行结果，应迁到结果详情；
- 一部分属于内部治理信息，应彻底退出普通用户主流程。

最终快速执行页真正需要的只有：

1. 生成按钮；
2. 单一、准确、可解释的执行状态；
3. 一个明确且上下文相关的修复动作；
4. 必要时的对象风险确认；
5. 运行后的结果详情入口。

当前整套「问题处理」大面板没有必要继续内嵌在快速执行页。其存在不仅造成视觉冗余，还掩盖了更重要的问题：页面展示的“阻断”并非 Runner 的真实门禁结论。

因此，推荐的重构原则是：

> 主流程只表达用户下一步；检测仍在后台运行；证据按需出现；真正的安全门禁由同一个权威模型决定。
