# AI 对话窗口 Design 与 Flow 样式迁移差异深度审计

> 审计日期：2026-07-28  
> 审计对象：Alavette Form 一级功能「AI 文档助手」的活动对话窗口  
> 用户截图：`<LOCAL_PATH>`
> 本轮范围：只分析、定义迁移边界和验收标准，不修改对话 UI 代码

---

## 1. 结论先行

用户判断成立：当前活动对话窗口**没有完成 Alavette Design 对话组件的正确迁移**。

当前实现不是“Design 对话组件 + Flow 交互状态”的移植结果，而是：

1. 从 Design 复制了少数尺寸常量，例如消息列 `860px`、助手内容 `820px`、用户气泡 `640px`、紧凑输入器 `154px`；
2. 使用 Form 自己的 `QScrollArea + QWidget + QTextEdit + 通用卡片` 重新拼装了一个外观近似的页面；
3. 保留了 Form 原有会话、模型调用、计划和文档生产链；
4. 没有迁移 Design 真正决定“对话感”的消息排版、输入器状态、滚动锚点、动作显隐和类型化卡片；
5. 没有把 Flow 的活动/只读交互状态、receipt、恢复状态和共享 Composer State 完整投影到 UI。

因此，当前状态应定义为：

| 层级 | 当前完成度 | 判断 |
|---|---:|---|
| 一级功能入口与独立面板 | 已有 | 基本成立 |
| Design 数字常量 | 部分迁移 | 不能代表组件迁移完成 |
| Design 控件层级与视觉状态 | 明显不完整 | 截图差异的主要来源 |
| Design 消息流行为 | 明显不完整 | 当前是另一套渲染架构 |
| Flow 交互语义投影 | 部分迁移 | 状态被压成通用文本卡片 |
| Form 文档生产主链 | 已保留 | 不应因重做 UI 被替换 |

最准确的结论是：

> 当前对话区是“复制了若干 Design 参数的 Form 自定义壳”，不是完整的 Design 组件迁移；Flow 也只迁移了部分业务概念，没有形成完整的 UI 状态投影。

下一轮不应该继续单点调颜色、边距或按钮，而应先把活动对话区收敛成一套明确的组件边界，再分层迁移。

---

## 2. 审计基线和可信度说明

### 2.1 仓库快照

| 仓库 | HEAD | 已跟踪脏项 | 本文用途 |
|---|---|---:|---|
| Alavette Design | `cb51361710c3edd853144c310b3f7636e9833df1` | 129 | 视觉、控件层级、消息排版和交互反馈基线 |
| Alavette Flow | `80560581b54f0817ab05f1efa3536253477cc755` | 358 | 交互状态、恢复、receipt、Composer State 和 ViewModel 基线 |
| Alavette Form | `9284471e0f182d9ee2174b631f53dbb726ded740` | 410 | 当前实现和截图差异核对 |

三个仓库均有未提交修改。因此：

- 本文分析的是 **2026-07-28 本机实际工作树**；
- commit 只用于定位基线，不能代表本文读取的每一行都来自该 commit；
- 实施时必须冻结所采用文件的哈希，不能只写“来自 Design/Flow”。

### 2.2 Design 与 Flow 不是同一个可直接覆盖的 UI 版本

同名文件对比结果：

| 文件 | Design / Flow 状态 | 结论 |
|---|---|---|
| `message_item_widgets.py` | SHA256 完全相同 | 可作为跨仓库一致的消息项视觉证据 |
| `task_composer.py` | 不同；diff 约 399 行 | 不能盲目选一个全量覆盖 |
| `task_message_stream.py` | 不同 | 消息流必须先选定权威版本和适配边界 |
| `task_workspace.py` | 不同 | Flow 业务范围更大，不应整页嵌入 Form |

其中：

- Design 的 `message_item_widgets.py` 与 Flow 对应文件哈希均为  
  `1DFAF8E3C5A5F29FD9861B652B6A69AAA1DD3140CF00F23AE6390DA831DA8BD5`；
- Design Composer 哈希为  
  `5C8ED76C83F409F03E79BB0D341280D56021B45B88905509DD02C9BE0CF3E536`；
- Flow Composer 哈希为  
  `3C2DDA30DFCC21DFD9DB08019E96DA42D8E8B6B202EF03EAE783761DA17D192F`。

所以正确的来源分工应是：

- **Design 决定长什么样、控件如何组织、反馈如何出现；**
- **Flow 决定当前处于什么状态、哪个动作仍可执行、恢复后如何续跑；**
- **Form 决定支持哪些真实能力、文档怎样生产、哪些控件不应出现。**

---

## 3. 本次审计读取的权威文件

### 3.1 Design 视觉和交互基线

根目录：`<LOCAL_PATH>`

| 文件 | 主要证据 |
|---|---|
| `alavette_host/desktop_qt/conversation/task_workspace.py` | Header、MessageStream、Composer 的真实层级和响应式预算 |
| `alavette_host/desktop_qt/conversation/task_header.py` | 56px 头部、左右边距、图标、更多操作和背景 |
| `alavette_host/desktop_qt/conversation/task_composer.py` | 154px Compact Composer 的完整控件树、占位、附件、模型入口和状态 |
| `alavette_host/desktop_qt/conversation/task_message_stream.py` | Model/Delegate 消息流、滚动锚点、自动跟随和悬浮动作 |
| `alavette_host/desktop_qt/conversation/message_render_types.py` | 阅读列、段落、标题、引用、代码、表格和动作尺寸 |
| `alavette_host/desktop_qt/conversation/message_item_widgets.py` | 用户/助手消息项和 hover action 的视觉解剖 |
| `alavette_host/desktop_qt/text_style.py` | 消息正文、标题、元信息的语义字号和行高 |

### 3.2 Flow 状态和交互语义基线

根目录：`<LOCAL_PATH>`

| 文件 | 主要证据 |
|---|---|
| `alavette_flow/app/assistant_ui/composer_state.py` | 首页和活动会话共享 Draft、附件、运行偏好的状态模型 |
| `alavette_flow/app/assistant_ui/conversation_view_model.py` | persisted/live/pending/recovery 合并、receipt、active/read-only |
| `alavette_flow/app/assistant_ui/question_interaction_state.py` | 问题卡的编辑、提交、等待恢复和重新可用状态 |
| `alavette_flow/app/assistant_ui/cards.py` | question、permission、approval、recovery 等类型化卡片 |
| `alavette_flow/app/assistant_ui/view_model.py` | 文本、Render Block、Card、Turn State 和 Continuation 的统一投影 |

### 3.3 Form 当前实现

| 文件 | 当前职责 |
|---|---|
| `src/assistant/ui/assistant_panel.py` | 活动页控件树、消息全量重建、滚动、卡片装配 |
| `src/assistant/ui/creative_home.py` | 当前 Hero/Compact Composer 的本地重写 |
| `src/assistant/ui/conversation_view.py` | 当前消息行、Markdown、消息动作和活动页网格 |
| `src/assistant/ui/interaction_card.py` | 所有交互类型共用的通用卡片 |
| `src/assistant/application/plan_presentation.py` | 将 DocumentPlan 拼成截图中的多行文本 |
| `tests/test_assistant_panel.py` | 当前测试覆盖和测试盲区 |

---

## 4. Design 对话工作区的真实结构

Design 的活动会话不是“滚动区中塞若干 QWidget，再放一个输入框”，其结构是：

```text
TaskWorkspace
├─ TaskHeader                         固定 56px
└─ WorkspaceBody
   ├─ Main
   │  ├─ TaskMessageStream            QListView + Model + Delegate
   │  └─ ComposerWrap                 与消息列共享横向预算
   │     ├─ ObjectContextRow
   │     ├─ Queue / Source Notice
   │     └─ TaskComposer(compact)      固定 154px
   └─ Optional Context Host
```

关键不是某个单独尺寸，而是这些组件共享同一个几何预算：

- `task_workspace.py:88-95` 定义主区、阅读保护宽度、Composer 边距和 Context 宽度；
- `task_workspace.py:159-165` 为 Composer Wrap 设置 `24/12/24/12`；
- `task_workspace.py:745-775` 根据可用宽度同时更新 Composer 边距和 MessageStream 阅读列；
- `task_workspace.py:795-809` 活动工作区、主区、Body 和 Composer Wrap 都使用 `bg_window`；
- `task_workspace.py:193-198` 拖放观察范围同时覆盖消息流、viewport、Composer Wrap 和 Composer。

当前 Form 只复制了部分宽度数字，没有复制“消息列和 Composer 共用一套横向预算”这一核心约束。

---

## 5. 截图逐项诊断

以下诊断对应用户本次截图，而不是抽象审美评价。

### 5.1 活动页背景不是 Design 的默认活动工作区

截图中消息区存在透视网格。

当前来源：

- `conversation_view.py:35-60` 的 `AssistantConversationSurface.paintEvent()` 主动绘制 42px 网格；
- `assistant_panel.py:2564-2571` 将消息 viewport 和 host 设为透明，因此网格持续透出。

Design 来源：

- `task_workspace.py:795-809` 的活动工作区统一使用 `bg_window`；
- Design 的 `TaskWorkspace` 没有活动页透视网格绘制。

判断：

- 如果目标是严格还原 Design，活动会话应是干净的 `bg_window`，网格只属于创作首页；
- 如果此前产品决策要求活动页也保留背景，网格可以保留，但必须登记为 **Form 有意偏离**，不能再称为 Design 原样迁移。

这项需要产品选择，不能通过“继续调淡一点”假装两者相同。

### 5.2 输入器蓝色描边是永久状态，不是交互状态

截图中 Composer 无论是否 hover 都呈现高强调蓝色边框。

当前来源：

- `creative_home.py:619-622`：Compact Composer 永久使用 `border_focus`；
- Hero Composer 甚至永久使用 `2px border_focus`。

Design 来源：

- `task_composer.py:1935-1942`：
  - 默认 `border: 1px solid t.border`；
  - 仅 `:hover` 切换到 `border_focus`；
  - 编辑器 focus 自身无额外边框。

因此当前视觉把“正在关注/可交互”的强反馈变成了常驻装饰，导致页面持续紧张、输入器压过消息内容。

### 5.3 占位文字的焦点行为不等价

截图中输入器已呈现明显焦点状态，但占位文字仍然存在。

当前来源：

- `creative_home.py:197-205` 直接使用原生 `QTextEdit.setPlaceholderText()`。

Design 来源：

- `task_composer.py:1002-1009` 使用独立的自定义 Placeholder Label；
- `task_composer.py:1869-1879` 只有“内容为空且未聚焦”时显示；
- 等待恢复是唯一例外，届时它承担状态提示而非普通占位。

这不是单纯文字不同，而是焦点状态机没有迁移。

### 5.4 Composer Footer 控件树不是 Design 控件树

当前截图 Footer：

```text
附件图标 | 大片空白 | “模型” | 原生下拉框 | 齿轮 | 发送
```

当前代码：

- `creative_home.py:239-295` 分别创建 model label、`StyledComboBox`、设置齿轮和发送按钮；
- 当前 Compact 模式只是把附件按钮改为 32px 图标。

Design Footer：

```text
附件 / Web / Knowledge / Memory / Scope / Prompt
| 自适应空白 |
Context Ring | 单个 ModelSettings Chip | 圆形 Send/Stop
```

其中：

- `_ComposerToolButton` 是 34px 低噪声图标按钮；
- `_ContextUsageRing` 用圆环承载上下文预算状态；
- `_ModelSettingsButton` 将模型和推理设置收敛为一个 34px、92–132px 的入口；
- 原始 provider/reasoning/access selector 默认隐藏；
- Footer 在窄宽度下会自动降密度，而不是压缩原生下拉框。

Form 不支持的 Web、Memory、Skills 不应该为了“像”而硬加回来；但模型入口的**视觉组织方式**仍应迁移。建议只保留：

```text
附件 | 状态/阻塞提示 | 弹性空白 | 单个模型设置 Chip | 圆形发送/停止
```

### 5.5 Compact 输入字号迁移错误

当前：

- `creative_home.py:624-630` Hero 和 Compact 共用 `font_size_lg`。

Design：

- `task_composer.py:1951-1957` Hero 使用 `font_size_lg`，Compact 使用 `font_size_md`；
- Placeholder 同样按模式切换字号。

这会让截图中的 154px 输入器显得比 Design 更空、更重、更像一个缩小后的 Hero 输入框。

### 5.6 助手消息被渲染成普通 QTextEdit 文本块

当前：

- `conversation_view.py:63-101` 使用自动增高的 `QTextEdit`；
- 完成消息调用 `setMarkdown()`；
- `conversation_view.py:430-437` 只统一设置一个 `font_size_md`；
- 没有 Design 的段落、标题、列表、引用、代码和表格布局规范。

Design：

- `message_render_types.py:10-18` 定义 860/820/640 阅读列和整体边距；
- `message_render_types.py:47-56` 分别定义 paragraph、heading、list、quote、code、table、math 的块间距；
- `text_style.py:24-40` 给正文、用户消息、元信息、标题设置不同字号与行高；
- `TaskMessageStream` 由 `QListView + Model + Delegate` 进行分块布局、命中测试和绘制。

所以当前问题不是“字体还差一点”，而是 Markdown 渲染层级完全不同。继续给 `QTextEdit` 添加 QSS 无法获得 Design 的排版结果。

### 5.7 “复制 / 引用 / 重试”常驻文字破坏消息节奏

截图中每条助手消息下方永久显示三段文字操作。

当前来源：

- `conversation_view.py:351-384` 创建并永久显示三个文字按钮；
- Footer 只要不是 live 且有文字就可见。

Design 来源：

- `message_render_types.py:25-26` 消息动作尺寸为 22px，间距 3px；
- `message_item_widgets.py:168-215` 动作默认隐藏，只在 hover 时显示；
- 用户和助手动作使用紧凑图标，不是常驻文字导航。

当前动作区会把每条助手回复都切成“正文 + 一行工具栏”，显著增加纵向噪声。

正确迁移应同时满足：

- 鼠标 hover 时显示；
- 键盘 focus 时也能发现和操作；
- touch/无 hover 环境有替代入口；
- 不应只做“默认隐藏”，否则会形成可发现性和无障碍回退。

### 5.8 “生成计划”是诊断文本，不是类型化任务卡

截图卡片内容包含：

- 输入；
- 工作模式；
- 方案；
- 模板；
- 输出；
- 待补充；
- 提示。

当前来源：

- `plan_presentation.py:72-97` 将所有字段和空行拼成一段字符串；
- `interaction_card.py:12-65` 所有 question、permission、plan、progress、artifact 都使用同一个：
  `Eyebrow + Title + Body QLabel + Button Row`；
- `assistant_panel.py:1445-1465` 对所有 Interaction/Artifact Block 使用同一个通用卡片。

问题包括：

1. 机器合同字段被直接暴露给用户；
2. “custom/default”等内部 ID 会和中文用户语言混用；
3. 当前缺项、下一步动作和仅供追溯的信息没有视觉分层；
4. 历史卡片与当前可操作卡片没有明显的 active/read-only 差异；
5. 一个 `QLabel` 无法表达问题表单、权限范围、进度、产物和恢复状态。

Flow 已有类型化语义：

- question；
- permission；
- workflow approval；
- recovery；
- candidate / confirmation；
- receipt；
- active / read-only。

正确方向不是继续给通用卡片加条件，而是建立卡片渲染器注册表。

### 5.9 卡片底部动作在截图中被截断

截图中“选择文档”位于消息视口底部，部分内容被 Composer 边界切断。

从控件树看，Composer 是消息滚动区的兄弟控件，不是直接覆盖在卡片上。因此不能简单归因于 `z-index` 或绝对定位。

更可能的架构原因是：

- `_render_active_session()` 全量删除并重建所有消息；
- 只在一次 `QTimer.singleShot(0, ...)` 中滚到底；
- `_AutoHeightMarkdown` 又会在 `documentSizeChanged` 时继续改变高度；
- 当前只保存 scrollbar 的裸数值，没有保存“哪条消息 + 消息内偏移”的锚点；
- 最后一张卡片缺少在全部异步几何稳定后再次 `ensureVisible` 的机制。

Design 已实现：

- `_capture_scroll_anchor()`；
- `_restore_scroll_anchor()`；
- insert、resize、geometry change 后的多阶段恢复；
- 用户滚动后的自动跟随抑制；
- viewport 内悬浮的 Jump-to-latest 按钮。

这项需要下一轮用运行态复现确认具体时序，但现有代码架构已经足以证明：当前实现没有 Design 的几何稳定和锚点保证。

### 5.10 Jump-to-latest 的形态也不同

当前：

- `assistant_panel.py:355-367` 使用“回到最新消息”文字 + 图标按钮；
- 按钮占据 Composer 上方单独一行布局；
- 阈值固定为距底部 64px。

Design：

- 使用 viewport 内 36px 左右的圆形悬浮按钮；
- 不额外占据纵向布局空间；
- 是否显示同时考虑未读尾部和动态阈值；
- 用户滚动会抑制自动跟随。

---

## 6. 当前实现与 Design 的组件级差异

### 6.1 Workspace 与 Header

| 项目 | Design | 当前 Form | 判断 |
|---|---|---|---|
| Header 高度 | 56px | 基本按 56px 组织 | 接近 |
| Header 左右边距 | 28 / 16 | 已局部参考 | 接近 |
| Header 背景 | `bg_window` | `bg_card` | 不一致 |
| 活动页背景 | 干净 `bg_window` | 自绘透视网格 | 明确偏离 |
| Context/Object Dock | 有明确对象语义 | 当前一级功能中弱化/隐藏 | 可按 Form 能力裁剪 |
| 主区横向预算 | Stream 与 Composer 同步 | Composer 960、消息 860、卡片 820 分别计算 | 不一致 |

### 6.2 Message Stream

| 项目 | Design | 当前 Form | 风险 |
|---|---|---|---|
| 容器 | `QListView + Model + Delegate` | `QScrollArea + QWidget` | 大会话性能和状态稳定性 |
| 更新 | 增量 Model 变化 | 全量销毁重建 | 焦点、选择、hover 和滚动丢失 |
| 滚动保持 | 消息 ID 锚点 + 偏移 | 裸 scrollbar value | 高度变化后错位 |
| 自动跟随 | 用户滚动抑制 + 未读尾部 | 距底 64px | 语义过粗 |
| Jump 按钮 | viewport 悬浮圆形 | 单独文字行 | 占空间、视觉噪声 |
| Markdown | 分块布局和绘制 | `QTextEdit.setMarkdown()` | 排版不等价 |
| 消息动作 | hover/focus 低噪声图标 | 常驻文字按钮 | 视觉节奏错误 |

### 6.3 Composer

| 项目 | Design Compact | 当前 Form Compact | 判断 |
|---|---|---|---|
| 高度 | 154px | 154px | 数字一致 |
| 内边距 | 18/14/20/14 | 18/14/20/14 | 数字一致 |
| 默认边框 | 中性 `border` | 强调 `border_focus` | 状态错误 |
| Hover 边框 | `border_focus` | 与默认无差异 | 无反馈层级 |
| 编辑字号 | `font_size_md` | `font_size_lg` | 错误 |
| Placeholder | 自定义 Label，focus 隐藏 | 原生 Placeholder | 行为错误 |
| 模型控件 | 单个 ModelSettings Chip | Label + Combo + Gear | 控件树错误 |
| Context Ring | 有 | 无 | 可按能力裁剪或改为状态提示 |
| 附件 | Chip/Strip、多状态、拖放 | 单 DOCX 本地行 | 只完成最小功能 |
| Busy/Recovery | 输入只读、控件门控、占位变化 | 局部 disabled/busy | 不完整 |
| Footer 响应式 | 520/640 降密度 | 无同等级策略 | 窄宽度风险 |

### 6.4 Interaction Cards

| 项目 | Flow/Design 语义 | 当前 Form | 判断 |
|---|---|---|---|
| 问题 | 编辑/已填/提交/等待恢复 | 文本 + 按钮 | 不完整 |
| 权限 | 范围、一次性授权、结果 receipt | 文本 + 按钮 | 不完整 |
| 审批 | active/read-only、批准结果 | 文本 + 按钮 | 不完整 |
| 计划 | 摘要、缺项、下一步、可展开详情 | 原始字段串 | 信息结构错误 |
| 进度 | 阶段、状态、取消/恢复 | 通用卡片 | 语义弱 |
| 产物 | 名称、类型、位置、打开/重试 | 通用卡片 | 语义弱 |
| 历史状态 | 只读并保留 receipt | 没有统一约束 | 可能重复执行 |

---

## 7. Flow 应迁移的是状态语义，不是整套产品 UI

Flow 的价值在于避免 UI 只看“最后一段文本”。

### 7.1 共享 Composer State

`composer_state.py:54-96` 定义：

- `draft_text`；
- `attachments`；
- `runtime_preferences`；
- 提交时冻结成不可变 `AssistantComposerIntent`。

这说明首页 Hero Composer 和活动会话 Compact Composer 应是**同一个状态源的两个展示壳**，而不是两个控件互相手工抄值。

Form 当前已经共享了部分业务对象，但 UI 层仍有两个本地 Composer 实例和手工同步路径。继续为两处分别添加控件，会加剧状态漂移。

### 7.2 Active 与 Read-only

`conversation_view_model.py` 会把：

- persisted；
- transient/live；
- pending；
- recovery

合并成统一条目，并保留：

- `receipts`；
- `interaction_mode`；
- `provenance`；
- lineage/turn 归属。

同时，新的 active 交互出现后，旧交互会转为 read-only。

这比“卡片上是否还有按钮”更严格。Form 应迁移这个合同，避免：

- 重启后旧批准按钮重新可点；
- 同一个 permission 重复提交；
- live 卡和 persisted 卡重复显示；
- 恢复卡与历史卡状态混淆。

### 7.3 Question Interaction State

Flow 的 Question State 至少包括：

```text
available
→ editing
→ ready_to_submit
→ pending_resume
→ submitted
→ available_again（恢复失败后）
```

当前通用卡片没有状态容器，无法可靠表达上述过程。问题卡不能只做成“正文 + 继续”。

### 7.4 不能照搬的 Flow 内容

Flow 中与其自身产品相关的：

- deliverable parent task；
- milestones；
- daily work；
- fixed time；
- Flow 专属工具权限；
- Web / Memory / Skills 默认开关

不应直接出现在 Form。

Form 应只迁移：

- 状态模型；
- active/read-only 合同；
- receipt 和去重；
- recovery 生命周期；
- ViewModel → typed renderer 的投影方式。

---

## 8. 为什么以前的“迁移通过”没有发现这些问题

现有测试：

`tests/test_assistant_panel.py:820-855`

名称为：

`test_active_conversation_migrates_design_message_and_composer_contract`

实际只断言：

1. 有两条消息；
2. role 包含 user 和 assistant；
3. Composer objectName 正确；
4. Composer 高度为 154；
5. Send 宽度为 32；
6. Provider Combo 位于 Composer；
7. Header Icon 可见；
8. Session Toggle 隐藏；
9. `grab()` 得到的图像宽度大于 0。

它没有断言：

- 默认边框是不是中性色；
- hover/focus 是否按 Design 切换；
- Placeholder 在 focus 时是否隐藏；
- Compact 字号是否正确；
- 模型入口是否为一个 Chip；
- 消息动作是否默认隐藏；
- Markdown 标题、列表、代码和引用是否正确；
- 用户/助手消息的真实边距；
- 最后一张卡片是否完整可见；
- active/read-only 卡片状态；
- DPI 下是否截断；
- 截图与 Design 基准是否相似。

`tests/test_assistant_panel.py:1203-1245` 只验证重绘后 scrollbar value 仍为 0 和 Jump 按钮出现，没有验证消息 ID 锚点、动态高度或末卡可见性。

`tests/test_assistant_panel.py:1312-1336` 只验证通用卡片存在、类型字符串和按钮文字，没有验证不同类型卡片是否有不同结构和生命周期。

因此：

> 测试名称把“存在性/尺寸契约”误写成了“Design 迁移契约”。当前 UI 明显偏离而测试仍通过，是测试口径不正确，不是用户主观感受有误。

---

## 9. 正确的目标架构

不建议从 Design 或 Flow 直接整页复制。建议建立 Form 自己的适配层：

```text
FormAssistantWorkspace
├─ AssistantTaskHeaderAdapter
│  └─ 迁移 Design 结构与视觉，连接 Form Session 操作
├─ AssistantConversationList
│  ├─ AssistantConversationViewModel
│  ├─ MessageRowRenderer
│  ├─ TypedCardRendererRegistry
│  └─ ScrollAnchorController
└─ AssistantComposerAdapter
   ├─ AssistantComposerState（单一状态源）
   ├─ Design Compact/Hero 两种外观
   └─ Form Provider / DOCX / Send / Stop 能力适配
```

数据方向：

```text
Form Session / Turn / DocumentPlan
            │
            ▼
AssistantConversationViewModel
  ├─ text blocks
  ├─ source blocks
  ├─ typed interaction blocks
  ├─ active/read-only
  ├─ receipt / recovery
  └─ live turn state
            │
            ▼
Design-aligned renderers
            │
            ▼
Form actions / production commands
```

核心原则：

1. 视觉组件不直接读取 DocumentPlan 内部结构；
2. Plan Presenter 不再输出一大段诊断文本，而是输出结构化字段；
3. Renderer 不决定业务是否可执行，只消费 ViewModel 的 action state；
4. 所有动作必须回到 Form 现有 Coordinator/Production 主链；
5. 不从外部仓库建立运行时 import；
6. 不为每个新状态继续向通用卡片添加 `if interaction_type == ...`。

---

## 10. 推荐的组件迁移边界

### 10.1 必须严格迁移

- Header 56px 的结构和低噪声操作反馈；
- Stream 与 Composer 共享阅读列/横向边距预算；
- Compact Composer 默认、hover、focus、busy、recovery 状态；
- 自定义 Placeholder 的显示规则；
- Compact 模式字号；
- 单个模型设置 Chip；
- 圆形 Send/Stop；
- 附件 Chip 的必要信息和移除行为；
- 用户/助手消息的阅读列和上下边距；
- 语义消息排版；
- hover/focus 消息动作；
- scroll anchor、auto-follow suppression 和悬浮 Jump-to-latest；
- 最后一条消息/卡片完整可见保证。

### 10.2 按 Form 能力适配

- 附件先只支持 DOCX，但 UI 仍使用 Design 的 Chip/Strip 形态；
- Model Chip 显示 Form Provider Profile，而不是 Flow Provider；
- Context Ring 可映射为上下文/材料预算；若没有真实数据，先不显示；
- ObjectContextRow 仅在 Form 真正支持引用对象时出现；
- 卡片类型只实现 Form 当前真实存在的：
  question、disclosure/permission、plan candidate、plan、preflight、approval、
  progress、artifact、recovery。

### 10.3 明确不迁移

- 不支持的 Web、Memory、Skills 控件；
- Flow 专属任务/里程碑/日程 deliverable 卡片；
- Flow 全局 Shell、侧栏和 Context Panel；
- Design/Flow 外部仓库的运行时依赖；
- 仅为了看起来丰富而增加的无后端按钮；
- 当前已经被用户明确删除的不完整侧栏入口。

---

## 11. 计划卡的目标信息结构

当前“文档处理计划”卡应从诊断文本改为结构化、渐进披露。

默认态只显示：

```text
生成计划
文档处理计划

输入       未选择文档
下一步     选择要处理的 DOCX

[选择文档]
```

如果输入已经齐全：

```text
生成计划
试卷组装计划

材料       高二数学资料包 · 12 份
交付       试卷 + 答案 + 解析
状态       可以执行

[检查并继续]  [查看详情]
```

“模式 / 方案 / 模板 / 输出路径 / 内部 capability”只在以下情况下显示：

- 用户需要修改；
- 该字段发生冲突；
- 进入“查看详情”；
- 失败恢复需要说明。

不能把内部值 `custom/default` 直接作为主视觉信息。

---

## 12. 不同实施方案对比

| 方案 | 优点 | 主要问题 | 结论 |
|---|---|---|---|
| 整体复制 Design Workspace | 初始外观接近 | 依赖巨大、业务信号不匹配、会引入 Context/Memory 等无关能力 | 不采用 |
| 整体嵌入 Flow Workspace | 状态较丰富 | 产品边界不同，会带入 Flow 业务和数据模型 | 不采用 |
| 继续修补现有 QWidget 页面 | 单次改动小 | 架构差异会不断产生新补丁，视觉和行为难以收敛 | 不采用 |
| 复制数字和 QSS | 最快 | 已经证明不能得到组件等价 | 不采用 |
| **按组件合同重新移植并适配 Form** | 边界清晰、可测试、保留现有主链 | 需要一次结构性重构 | **推荐** |

---

## 13. 建议实施顺序（本轮不执行）

### 阶段 0：冻结视觉与状态合同

先形成：

- Design 基准截图；
- 当前 Form 基准截图；
- 100%、125%、150%、200% DPI；
- 宽度 760、900、1120、1440；
- 空会话、短会话、长会话、流式、问题、审批、计划、产物、恢复。

没有基准前不进入改造。

### 阶段 1：Composer 单独收敛

先替换当前本地重写的 Footer 和状态：

- 中性默认边框；
- hover/focus 正确；
- Placeholder focus 隐藏；
- Compact 字号；
- 单个模型 Chip；
- 圆形 Send/Stop；
- shared Composer State；
- 附件 Chip；
- busy/recovery 门控。

这个阶段不改文档生产链。

### 阶段 2：消息流结构化

将：

`QScrollArea + 全量 QWidget 重建`

替换为：

`稳定 Model + 增量 Row + ScrollAnchorController`

不要求逐行复制 Design 的 9000 行 Delegate，但必须实现同等级合同：

- 稳定 row identity；
- 增量更新；
- 动态高度后恢复锚点；
- 用户滚动抑制；
- selection/hover 不因流式更新丢失；
- 最后一项安全可见。

### 阶段 3：消息排版和动作

- 建立语义 Block Renderer；
- 实现正文、标题、列表、引用、代码、表格的独立间距；
- 消息动作改成低噪声图标；
- 增加键盘 focus 和无 hover 回退；
- Source/Attachment 使用 Chip，而不是混在正文。

### 阶段 4：类型化卡片

建立：

```text
renderer_registry = {
    "question": QuestionCard,
    "permission": PermissionCard,
    "plan_candidate": PlanCandidateCard,
    "plan": PlanCard,
    "preflight": PreflightCard,
    "approval": ApprovalCard,
    "progress": ProgressCard,
    "artifact": ArtifactCard,
    "recovery": RecoveryCard,
}
```

旧卡片只保留为未知类型的只读 Fallback，不能继续承担全部主链。

### 阶段 5：Flow 状态适配

- active/read-only；
- receipt；
- pending/recovery overlay；
- question state；
- duplicate action suppression；
- Composer pending recovery。

### 阶段 6：验证和清理

- 删除旧 `AssistantConversationMessage` 和通用主路径；
- 删除重复宽度常量；
- 删除旧 model label/combo/gear 组合；
- 修正测试名称；
- 用截图 diff、状态测试和真实主链测试共同验收。

---

## 14. 必须建立的验收标准

### 14.1 视觉

- [ ] 默认 Composer 不使用 `border_focus`；
- [ ] hover 时边框变化，focus 不产生双重描边；
- [ ] Compact 编辑文字使用 `font_size_md`；
- [ ] 空输入获得焦点后，普通 Placeholder 消失；
- [ ] 模型和设置不再拆成 `Label + Combo + Gear`；
- [ ] 消息正文、标题、列表、引用和代码有可辨识层级；
- [ ] 消息操作默认不占据一整行文字空间；
- [ ] 用户气泡最大 640、助手内容最大 820、阅读列最大 860；
- [ ] Stream 和 Composer 使用同一中心轴与边距预算；
- [ ] 计划卡默认只显示完成任务必需的信息；
- [ ] 最后一张卡片和按钮在 Composer 上方完整可见；
- [ ] 100%–200% DPI 下无裁切和重叠。

### 14.2 交互

- [ ] Enter 发送，Shift+Enter 换行；
- [ ] busy 时发送按钮切换为 Stop；
- [ ] pending recovery 时输入器只读且状态明确；
- [ ] 附件可添加、替换、移除，提交时冻结；
- [ ] 首页和活动会话共享同一份 Draft/Attachment State；
- [ ] 用户主动上滚后，流式更新不把视口强制拉到底；
- [ ] 点击 Jump-to-latest 后恢复自动跟随；
- [ ] 动态 Markdown 高度变化后阅读锚点不跳；
- [ ] 历史交互卡只读，只有最新有效卡可执行；
- [ ] 相同 receipt 不会重复提交。

### 14.3 主链

- [ ] UI 重构不替换 Form Session Coordinator；
- [ ] UI 重构不替换 Provider Runtime；
- [ ] UI 重构不替换 DocumentPlan / Preflight / Approval / Production；
- [ ] AI 生成到组装试卷继续使用既有能力契约；
- [ ] 取消和恢复仍归属正确 session/turn；
- [ ] 错误卡提供可执行恢复动作，而不是只显示诊断文本。

---

## 15. 必须补充的测试

### 15.1 Composer

- 默认、hover、focus 三态边框；
- Placeholder focus 显隐；
- Hero/Compact 字号；
- Model Chip 唯一性；
- 520/640px Footer 降密度；
- busy、stop、pending recovery；
- Draft/Attachment 跨两个展示壳一致。

### 15.2 Message Stream

- 以 message ID 保存锚点，而不是 scrollbar 数值；
- 流式增量不销毁已有行；
- Markdown 高度二次变化后锚点稳定；
- 最后一张大卡完整可见；
- Jump-to-latest 为 overlay，不改变正文布局；
- hover action 和 keyboard focus；
- 100 条以上消息的更新耗时和内存。

### 15.3 Typed Cards

- 每种卡片有独立结构测试；
- active/read-only 转换；
- receipt 去重；
- question 的 editing → pending_resume → submitted；
- approval 只能提交一次；
- recovery 失败后 available_again；
- Plan 摘要不暴露内部 ID。

### 15.4 视觉回归

每个 DPI/宽度组合至少覆盖：

1. 普通短回复；
2. 多段 Markdown；
3. 用户附件；
4. Plan Card；
5. Question/Permission；
6. 流式生成；
7. 失败和恢复；
8. 长会话上滚。

“`grab().width() > 0`”不能继续作为视觉迁移完成的证据。

---

## 16. 风险和防止再次堆补丁的规则

### 风险 1：继续保留两套 Composer 控件树

后果：模型、附件、Draft、Busy、Recovery 每增加一个状态就要同步两次。

规则：两种外观可以有两个 View，但只能有一个 `AssistantComposerState`。

### 风险 2：继续扩展通用 InteractionCard

后果：一个类累积十几种条件分支，按钮状态和历史状态互相污染。

规则：通用卡只作为未知类型只读 fallback；主路径全部类型化。

### 风险 3：只做 QSS，不改渲染结构

后果：看似接近一张截图，但 Markdown、hover、滚动和 DPI 仍然错误。

规则：每个视觉差异必须找到对应的控件结构或状态来源，禁止只提交“调色修复”。

### 风险 4：直接复制 Design/Flow 文件

后果：引入 Form 不支持的 Context、Memory、Skills、Deliverables 和外部依赖。

规则：迁移“合同和结构”，通过 Form adapter 接入，不建立跨仓库运行时 import。

### 风险 5：测试名称大于测试内容

后果：以后再次出现“测试全绿但用户一眼看出不对”。

规则：测试名称必须准确表达断言；视觉等价只能由具体状态断言和基准截图共同证明。

---

## 17. 最终判断

当前对话窗口的主要问题不是某个颜色、圆角或按钮位置，而是四个基础层没有迁移：

1. **Design Workspace 的共同几何预算没有迁移；**
2. **Design MessageStream 的语义排版和滚动行为没有迁移；**
3. **Design Composer 的控件树和状态反馈没有迁移；**
4. **Flow 的类型化交互状态没有完整投影。**

当前页面保留了 Form 的真实业务主链，这是正确的；但 UI 层仍然是局部重写，应进行一次有边界的结构性纠偏。

推荐实施结论：

> 以 Design 为视觉和交互合同，以 Flow 为 UI 状态语义，以 Form 为唯一业务执行源；重新移植 MessageStream、Composer 和 Typed Card 三个组件边界，不复制整个外部 Shell，也不继续给现有通用 QWidget 页面叠加补丁。

在完成阶段 0 的截图基线和状态合同前，不建议开始改 UI。

---

## 18. 第二轮补充结论：Design 是完整的展示语法，Form 是更完整的执行语法

进一步检查后，应当修正一个容易造成错误实施的表述：

> Design 并不只是提供“好看的对话框”；它已经定义了一套完整的对话展示语法。Form 也不只是提供“按钮背后的接口”；它已经建立了更完整、更安全的文档执行语法。

两者的优势不是同一层，因此不需要二选一：

| 层级 | Design 优势 | Form 优势 | 正确组合方式 |
|---|---|---|---|
| 文件 | 从输入 Chip、消息文件卡到产物卡的完整生命周期视觉 | 本地路径、正文授权、内容哈希、生成草稿和正式输出均有真实状态 | Form 文件状态投影成 Design 文件组件 |
| 选择 | 单选、多选、其他输入、跳过、提交门控、回执 | 计划、预检、审批、恢复动作已经连接真实命令 | Design 选择控件只发 ActionIntent，由 Form 判定能否执行 |
| AI 正文 | 标题、列表、引用、代码、表格、流式、失败和来源均有语义样式 | Provider、Turn、Source、Cancellation、Persistence 已接通 | Form 的消息数据进入 Design Block Renderer |
| 计划 | 可表达候选、确认和多状态 | `DocumentPlan` 有版本、能力、生成、生产、交付合同 | 不显示原始 Plan 字段，建立 Plan Presentation |
| 预检/审批 | 有状态卡和低噪声动作语言 | 有不可伪造的哈希绑定和 Approval Receipt | Design 只显示 Form Receipt 的公开投影 |
| 产物 | 文件卡、图片卡、预览和动作区完整 | 真实生成 DOCX，试卷还验证学生卷和答案卷的交付完整性 | 每个真实产物投影为一张 Design Artifact Card |

因此下一轮的核心设计原则应改成：

```text
Design Presentation Grammar
            +
Flow Interaction Semantics
            +
Form Domain / Execution Truth
            =
Form AI 文档助手的最终对话体验
```

不能采用的方向：

- 把 Form 链路搬进 Design 仓库；
- 把 Design 控件直接绑定到生产 Adapter；
- 为了复用 Design 而把 Form 的 DocumentPlan 降级成文本；
- 为了保留 Form 而继续使用粗糙的通用 QLabel 卡片；
- 让 UI 自己判断试卷、公文或报告应该走哪条生产链。

---

## 19. Design 文件视觉不是一个控件，而是四阶段文件语言

Design 中“文件框”至少有四种不同形态。当前 Form 只实现了一个附件标签和一个通用 Artifact Card，丢失了文件在对话中的阶段感。

### 19.1 阶段 A：Composer 中待发送的附件 Chip

来源：

`Alavette Design/alavette_host/desktop_qt/conversation/task_composer.py:476-566`

结构：

```text
┌──────────────────────────────────────┐
│ 文件图标  文件名…  DOCX 后缀   ×    │
└──────────────────────────────────────┘
```

定义：

- 高度 `34px`；
- 最大宽度 `268px`；
- 左右内边距 `10 / 7`；
- 文件名最大宽度 `154px`，超出省略；
- 后缀使用独立小标签；
- 删除按钮 `20 × 20px`；
- 默认使用 `bg_selected + border_light`；
- hover 使用 `primary_light + border_focus`；
- 图片、链接、文件夹、普通文件使用不同图标；
- 超出可展示数量时使用 `+N` Overflow Chip。

语义：

- 这是“准备随本轮发送”的临时状态；
- 可以移除；
- 尚未代表模型已经读取；
- 提交时应冻结为本轮附件快照。

Form 当前已有：

- `context_refs`；
- 会话归属；
- 发送前文件存在性过滤；
- `DisclosureGrant`；
- 文件内容 fingerprint。

所以 Form 不缺真实数据，只缺正确的 Chip 展示和“待发送/已授权”的状态区分。

### 19.2 阶段 B：拖入窗口时的全局 Drop Overlay

来源：

`attachment_drop_zone.py:13-146`

Design 不是只让 Composer 接受 drop，而是在：

- MessageStream；
- MessageStream viewport；
- Composer Wrap；
- Composer

上建立统一 Drop Zone。

拖入时显示：

- `bg_window` 86% 透明覆盖层；
- primary 58% 描边；
- `radius_lg`；
- 120px 导入图标；
- “松开以添加”标题。

价值：

- 用户无需精确拖到回形针或编辑框；
- Drop 目标清楚；
- 不会误以为文件已发送；
- 不需要额外常驻“准备材料”按钮。

Form 如果保留仅 DOCX 能力，Overlay 应在拖入不支持格式时保持不可接受状态，不能先显示成功反馈再报错。

### 19.3 阶段 C：用户消息中的附件预览卡

来源：

`task_message_stream.py:5607-5785`、`6129-6213`

Design 对已发送附件使用：

- 卡片宽 `138px`；
- 卡片高 `108px`；
- 预览区高 `68px`；
- 卡间距 `10px`；
- 整条附件带高 `128px`；
- 最多自然展示四张；
- 更多附件横向滚动；
- 有独立 7px 滚动条；
- 文件名省略；
- 后缀 Badge；
- hover 提升边框；
- 文件丢失时显示 `MISSING` 和 warning icon；
- 图片使用真实缩略图，其他文件使用类型图标；
- 点击命中区域打开预览。

这是一种“本轮已经发送了哪些材料”的历史证据，不应与 Composer 中可删除的附件使用同一个控件。

Form 当前 `AssistantMessage.source_refs` 已随用户消息持久化，且至少包含：

```text
type
source_type
title
path
media_type
```

因此可以直接投影出：

- title；
- suffix；
- 本地存在/缺失；
- preview target；
- file type；
- message_id 归属。

缺少但可在纯投影层派生的字段：

- `suffix = Path(path).suffix`；
- `exists = Path(path).is_file()`；
- `preview_kind = docx / image / file`。

不应把这些展示字段反写进 `DocumentPlan`。

### 19.4 阶段 D：AI 产物文件卡

来源：

`task_message_stream.py:5787-6051`

Design 对 AI 产物使用另一种更强的文件卡：

- 普通文件卡高 `92px`；
- 左侧图标盒 `64px`；
- 文件图标 `48px`；
- 右侧动作 `30px`；
- 产物卡纵向堆叠，间距 `8px`；
- 文件卡可打开；
- 动作区预留打开、归档、另存为；
- 图片产物使用缩略图卡；
- hover 时卡片边框和文字增强；
- 文件卡主体和动作命中区分离，避免点击冲突。

当前 Form 在链路中已经产生两类真实产物：

1. AI 生成并经本地编译验证的中间草稿；
2. Form 生产引擎生成的最终 DOCX。

但 UI 把它们都压成：

```text
标题 + 一段说明 + 按钮
```

尤其试卷成功后，Form 实际交付：

- 学生卷；
- 答案卷。

当前最终消息却只保存 `primary_output_path` 为一个 reference，其他产物仅以名称出现在 body 中。这会让底层已经完整的多产物链在 UI 中退化成“生成了一个文档”。

正确投影应是：

```text
文档已生成

┌ 学生卷.docx                         打开  另存为 ┐
└───────────────────────────────────────────────┘
┌ 答案卷.docx                         打开  另存为 ┐
└───────────────────────────────────────────────┘

已通过交付完整性检查
```

每个文件卡必须来自真实 `output_paths`，不能根据文件名猜测交付类型。

### 19.5 四种文件形态不能合并成一个万能 FileCard

| 形态 | 是否可删除 | 是否可打开 | 是否持久化 | 是否表示模型已读取 | 是否表示正式产物 |
|---|---:|---:|---:|---:|---:|
| Composer Chip | 是 | 可选 | Draft State | 否 | 否 |
| User Attachment Card | 否 | 是 | Message Source Ref | 本轮已授权后可视为是 | 否 |
| Source Chip | 否 | 是 | Evidence/Source Ref | 作为回复依据 | 否 |
| Assistant Artifact Card | 否 | 是 | Artifact/Execution Result | 不适用 | 草稿或正式产物 |

可以共享视觉 token 和 `FilePresentation` 数据类，但不能共享同一交互状态机。

---

## 20. Design 选择控件是一套决策状态，不只是 Checkbox

### 20.1 User Question Panel

来源：

`task_message_stream.py:4321-4910`

Design 已定义：

- 面板 padding `12px`；
- 面板 gap `8px`；
- 选项高 `30px`；
- 选项间距 `7px`；
- Footer 高 `30px`；
- 顶部标题和问题进度 `1/N`；
- 单题只呈现当前问题，避免一次铺满；
- 最多四个标准选项；
- “其他”内联输入；
- “跳过本题”；
- 单选和多选；
- 已选项使用 `square-check`；
- hover、selected、disabled 使用不同填充和边框；
- 未回答完整时禁用提交；
- 上一题、下一题、提交、退出有不同动作样式；
- 提交后显示只读 Receipt Panel。

状态不是 `checked: bool`，而是：

```text
request
├─ current_question_index
├─ selections[question][option]
├─ custom_answers[question]
├─ skipped_questions
├─ unresolved_questions
├─ requires_user_action
└─ state
```

因此 Form 如果未来接入可验证 continuation，不能直接把问题卡做成一组普通 `QCheckBox`。

### 20.2 Candidate Row

来源：

`candidate_row.py:18-173`

Candidate Row 的选择状态包括：

```text
pending
accepted
dismissed
```

不同状态改变：

- 左侧 3px accent；
- Checkbox 内容；
- 标题颜色；
- dismissed 删除线；
- Action 文案；
- Accept/Undo/Restore 行为；
- Skip 是否可见。

这适合表达：

- 多个待确认处理项；
- 多份资料的采用/忽略；
- AI 建议中的候选修改。

但当前 Form 的 `plan_candidate` 是“是否创建一份本地计划”的单一确认，不应为了复用 Candidate Row 强行制造 checkbox 列表。单一 plan candidate 应使用 Confirmation Card；只有真实存在多个候选项时才使用 Candidate List。

### 20.3 Permission 与 Approval 不能共用一种按钮颜色

Design 的 permission action：

- Allow 使用 primary；
- Deny 使用 warning/danger；
- hover 只增强当前动作；
- disabled 降低 fill 和 border；
- 图标和文案在同一小按钮内。

Form 的执行审批是更强的领域动作：

- Approval 绑定 plan revision；
- 绑定 preflight evidence hash；
- 绑定 input hash；
- 绑定 output root。

所以执行审批卡必须显示“正在批准的公开摘要”，不能只显示一个蓝色“确认”按钮。

建议最低信息：

```text
执行前检查已通过

输入       文件名 · 哈希短码
方案       当前方案与模板已锁定
输出       目标目录名
影响       创建新文件，不覆盖输入

[确认并生成文档]  [返回修改]
```

公开摘要来自 `PreflightReceipt`，真实授权仍由 `ExecutionApproval.authorizes()` 判断。

### 20.4 Receipt 是选择控件闭环的一部分

Design 对问题提交后会把活动面板替换为：

- 已补充信息；
- 已全部跳过；
- 已退出提问。

这说明正确生命周期是：

```text
Active Interaction
→ Action Submitted
→ Pending
→ Durable Receipt / Read-only History
```

当前 Form 的消息合同没有统一 receipt 字段，也没有 active/read-only 字段。这不是纯样式问题，属于展示状态投影缺口。

---

## 21. Design 的 AI 回复正文是一套 Block Renderer

### 21.1 正文不是一个 QTextEdit

Design 的 AI 正文先经过：

`message_blocks.py`

转换为：

```text
paragraph
heading
list
hr
quote
code
table
math
streaming_text
live_status
failure_notice
```

然后由 `TaskMessageStream` 分别测量、布局、绘制和命中。

当前 Form 的 `_AutoHeightMarkdown` 只调用：

```text
QTextEdit.setMarkdown()
```

这会丢失：

- Block 间距；
- 自定义标题导轨；
- Quote Surface；
- Code Header 和 Copy；
- Table Cell Surface；
- 横向/纵向代码滚动条；
- block selection；
- streaming 未闭合 Markdown 处理；
- failure/live 的独立语义。

### 21.2 字体不是统一字号

Design 的语义字号：

| Role | 作用 |
|---|---|
| `message.body` | AI 正文，最小 14px，行高 1.46 |
| `message.user` | 用户气泡，行高 1.26 |
| `message.meta` | 来源、回执、过程信息 |
| `message.live_status` | 流式状态，使用 primary |
| `message.failure_notice` | 失败说明 |
| `message.heading1/2/3` | 分级标题 |

当前 Form 对 AI Markdown 只设置 `font_size_md`，没有行高和分级字体。

### 21.3 标题有内容轴，不只是加粗

Design Heading：

- 左侧 3px 内容轴；
- H1/H2/H3 通过 alpha 区分；
- 正文向右缩进 12px；
- Indicator 只对齐标题第一行；
- 标题本身使用独立的字体度量。

这使长回复中的结构非常清楚。当前 `QTextEdit` 只使用 Qt 默认 Markdown 标题样式，视觉上容易像一整块普通文本。

### 21.4 引用是独立 Surface

Design Quote：

- quote 背景；
- quote 边框；
- 左侧 primary 指示条；
- 左右和上下独立 padding；
- 正文使用 secondary 色；
- 保留可选择文本。

这类样式适合 Form 显示：

- 引用材料中的原文；
- 模型依据；
- 预检说明中的外部信息。

不能把 Form 内部诊断文本伪装成引用。

### 21.5 Code、Table 和 Math 有独立交互

Code：

- Surface；
- 语言标签；
- 独立 Copy；
- 不自动折行；
- 横向和纵向滚动；
- 最大高度约束。

Table：

- Header/Cell 不同 Surface；
- 网格；
- 列对齐；
- Cell padding；
- Copy；
- Block selection。

Math：

- 独立 Surface 和 padding。

即使 Form 当前主要生成文档，用户仍会在对话中看到：

- 结构化题目；
- 表格字段；
- Markdown 片段；
- 校验摘要。

因此 AI 正文 Renderer 仍有实际价值，不是为了展示代码而过度设计。

### 21.6 流式文本有不完整 Markdown 容错

Design 对流式文本不会在每个 token 后直接完整重建所有 Markdown：

- 检测 Markdown hint；
- 对未闭合 `**` 和反引号做容错；
- 标题、引用、列表按当前行做临时文档；
- 通过 reveal interval 和 layout interval 控制重排；
- 跟随消息锚点而不是裸 scrollbar。

Form 当前虽然能收到 delta，但 `_AutoHeightMarkdown` 的展示层没有同等级的流式排版策略。

### 21.7 Live、Failure、Reasoning 和 Final Answer 分层

Design 将以下内容分开：

- Live Status；
- Public Reasoning/Process；
- Final Answer；
- Failure Notice；
- User Question Receipt；
- Final Delivery Detail。

当前 Form 把 Process Step 和 Public Reasoning 又投影成一张通用“处理摘要”卡，导致最终回答之后再出现一个大块说明。

更合理的映射：

| Form 数据 | Design 呈现 |
|---|---|
| Turn Event Status | Live Status Row |
| `process_steps` | 可折叠 Process Detail |
| `public_reasoning_summary` | Process Summary，不进入主正文 |
| `visible_text` | Final Answer Blocks |
| `error` | Failure Notice / Recovery Card |
| `source_refs` | Source Footer |
| execution delivery detail | Final Delivery Detail |

---

## 22. Design 来源组件能够直接改善 Form 的可信度表达

来源：

`message_source_widgets.py:12-265`

Design Source Strip：

- 标题为“来源 · N 条”；
- 宽屏最多显示三个 Source Chip；
- 小于 680px 显示两个；
- 小于 520px 显示一个；
- 其余折叠为 `+N`；
- Active Source 使用 primary 8% 背景；
- 点击后发出包含 selection 的 EvidenceSet；
- 展开模式使用 Source Row；
- Source Row 有 file/search 类型图标。

Form 已经有：

- `AssistantRuntimeResult.source_refs`；
- Message `source_refs` 持久化；
- `_open_message_reference()`；
- 文件和 URL 打开能力。

因此当前“来源条”不需要创造新链路，只需建立 Source Presentation：

```text
source_id
title
source_type
path / url
snippet
active
available
```

需要注意：

- Provider 返回的来源和用户上传的附件不是同一个概念；
- 用户附件应显示“附件”，AI 引用应显示“来源”；
- 绝对本地路径不能发送给云模型，但可以保留在本地 UI reference；
- Source Chip 的点击只负责打开/预览，不应改变 DocumentPlan。

---

## 23. Form 的真实链路为何更完整

### 23.1 会话是持久化单一事实源

`AssistantSession` 持久化：

- messages；
- draft；
- provider/model；
- active_plan；
- pending_continuation；
- document_job；
- context_refs；
- turn_status。

`AssistantSessionCoordinator` 对每次 append/update 都保存 Session。

这意味着 UI 可以被替换，但不应该另建第二套会话数据库或卡片状态库。

### 23.2 发送前冻结上下文并创建一次性披露授权

`assistant_panel.py:698-825`

发送时：

1. 确认当前会话没有冲突操作；
2. 创建或同步 Session Provider Identity；
3. 冻结有效 `context_refs`；
4. 建立 `DisclosureGrant`；
5. Grant 绑定 session/provider/model/ref/field/fingerprint；
6. 用户消息和附件引用一起持久化；
7. 创建 `AssistantTurnRequest`；
8. 冻结 workspace/material snapshot；
9. 启动 Worker。

所以 Design 的附件 Chip 不能自己决定“模型会不会读”。真实授权必须继续来自这条链。

### 23.3 Turn 支持流式、取消、来源和多侧通道结果

Form 已有：

- Turn started；
- Context ready；
- Model started；
- Text delta；
- Waiting；
- Finished；
- Failed；
- Cancelled。

运行结果还包含：

- visible text；
- source refs；
- confirmation requests；
- proposed actions；
- artifacts；
- process steps；
- public reasoning summary；
- continuation ref。

当前损失发生在 `_runtime_result_messages()`：这些丰富数据被投影成多个通用 InteractionCard。底层并不弱，弱的是 Presentation。

### 23.4 AI 回复完成后先创建 Plan Candidate，不自动生产

当用户请求 Form 文档动作时：

1. AI Turn 先完成；
2. Form 冻结本轮 workspace 和 context；
3. 创建 `plan_candidate`；
4. 用户确认后才调用 `draft_plan()`；
5. 创建 typed `DocumentPlan`；
6. 将计划持久化为 `active_plan`。

这是正确的安全边界。Design 的 Confirmation/Candidate 视觉应覆盖这一步，但不能绕过用户确认。

### 23.5 DocumentPlan 是强合同，不是 UI 字符串

`DocumentPlan` 包含：

- plan ID 和 revision；
- intent 和 created turn；
- input document；
- work mode；
- scene/template/theme；
- material refs；
- fragment refs；
- output policy；
- capability；
- source artifacts；
- generation contract；
- production contract；
- delivery contract；
- warnings；
- unresolved questions。

Plan 的 `fingerprint` 来自完整序列化内容。

因此 UI 不应直接显示全部字段，也不应自行修改其中任何字段。正确方式是：

```text
DocumentPlan
→ DocumentPlanPresentationModel
→ Design PlanCard
```

### 23.6 内容生成只让模型生成受限 Artifact，结构由本地验证

Form 当前内容生成链：

```text
Provider Markdown
→ 明确 artifact_kind 路由
→ 本地 Compiler
→ Schema / Domain Validation
→ GeneratedDraft
→ SourceArtifactRef
→ bind_generated_draft(DocumentPlan)
```

试卷链尤其明确：

- 模型输出 Exam Markdown；
- `parse_exam_markdown_source()` 本地解析；
- 无题目或结构错误直接阻断；
- 生成 `GeneratedExamDraft`；
- 绑定为 `SOURCE_ROLE_STRUCTURED_SOURCE`；
- 不会静默降级成通用 DOCX。

Design 的“草稿文件卡”应显示这个真实结果，而不是把模型原始文本直接称为“文档已生成”。

### 23.7 Preflight 绑定计划、输入和资源

`PreflightReceipt` 绑定：

- plan ID/revision/fingerprint；
- input hash；
- output root；
- scene/template/master fingerprint；
- issues/warnings；
- evidence hash。

这比普通“是否可以执行”布尔值强得多。

Design Approval Card 应投影这些证据，但不能把完整本地路径和内部错误码直接呈现给用户。

### 23.8 Approval 不是普通按钮事件

`ExecutionApproval.authorizes()` 会核对：

- preflight.ready；
- plan ID；
- plan revision；
- preflight evidence hash；
- input hash；
- output root。

因此 UI 上即使旧 Approval 按钮仍可见，底层也不应执行过期计划。但视觉层仍需把旧卡转只读，避免用户产生“按钮失灵”的错觉。

### 23.9 执行前再次验证漂移

生产 Adapter 在真正执行前重新检查：

- Plan fingerprint 未变；
- Approval 确实授权当前 Preflight；
- 输入文件仍存在且 hash 未变；
- Scene/Template 未变；
- Master 未变；
- 输出目录合法；
- 输入不会被输出目录覆盖。

任何漂移都会 fail closed。

### 23.10 交付合同验证最终产物

执行后还会验证 Delivery Contract。

例如试卷要求：

- `student`；
- `answer_key`。

如果 Executor 声称 success，但缺少其中一个，Adapter 会将结果改为 failed。

这就是为什么 Form 的链路比当前 UI 看起来完整得多：UI 只显示一段“状态/产物”文字，但底层已经做了交付集合验证。

---

## 24. Form 链路仍然存在的真实缺口

“Form 链路更完整”不等于“所有场景都闭环”。以下问题不能被 Design 样式掩盖。

### 24.1 通用文本 Provider 的 Tool Call Continuation 尚不可验证

`assistant_panel.py:1157-1188`

对于 permission/approval request：

- 当前不会提供真实 Allow/Deny Resume；
- UI 明确说明没有可验证的 Tool Call 恢复通道；
- 只能改用不需要权限的方案或更换 Provider。

因此 Design Permission Button 不能直接启用。否则只是把无效链路包装得更漂亮。

状态应投影为：

```text
PermissionUnavailableCard
```

而不是：

```text
ActivePermissionCard
```

### 24.2 Plan Material Snapshot 主要保存在进程内存

当前 `_plan_material_snapshots[plan_id]` 保存发送时的 `MaterialExecutionContext` 克隆，但它不是 Session 的完整持久化字段。

重启后：

- DocumentPlan 可以恢复；
- Preflight/Job 部分状态可以恢复；
- 对应 MaterialExecutionContext 快照未必能够原样恢复。

因此“重启后继续执行同一资料包”的 UI 不应被标记为完全可恢复，除非持久化材料快照或不可变材料引用。

### 24.3 多产物结果在消息层投影不完整

底层 execution result 有 `output_paths`，但最终消息只保存一个 `primary_output_path` reference。

后果：

- 试卷的学生卷/答案卷无法各自显示文件卡；
- partial success 无法准确标出哪个产物成功、哪个失败；
- 每个产物无法独立打开或另存为。

这需要补充 Presentation Projection，必要时为 Artifact Block 增加 `references` 列表；不需要重写生产链。

### 24.4 Message Contract 缺少 Interaction 生命周期

当前 `AssistantMessage` 只有：

- text；
- interaction；
- artifact。

Interaction Data 虽可存任意 payload，但没有标准字段：

- interaction_id；
- interaction_mode；
- state；
- receipt；
- parent_turn_id；
- replaces_message_id；
- action availability。

如果只在 Renderer 中猜“最后一张卡是 active”，重启、恢复和并行会话下容易出错。

需要新增稳定的 Presentation Contract 或 ViewModel 层，而不是让每个卡片自己查 Session。

### 24.5 Progress 主要更新 Header，没有 durable stage projection

执行进度当前通过 `_conversation_title.setText()` 显示。

问题：

- 切换会话后不可见；
- 历史记录没有阶段进度；
- 成功后无法知道经历了哪些阶段；
- UI 重建时状态来源分散。

建议将 progress 投影为同一 `operation_id` 的可更新 Stage Item，而不是不断追加重复“正在处理”卡。

### 24.6 Composer 当前只支持一个 DOCX

Design 支持多个 attachment chip 和 overflow；Form 当前会话 `context_refs` 结构支持 tuple，但 Composer 实际只维护一个 `document_path`。

因此：

- 视觉可以先迁移单个 Chip；
- 不应提前显示 `+N`；
- 多附件能力应作为独立功能扩展，需同步披露授权、正文提取、fingerprint 和材料快照。

---

## 25. Design 组件与 Form 链路的逐节点映射

| Form 链路节点 | 事实源 | Design 展示组件 | 用户看到的必要信息 | Action |
|---|---|---|---|---|
| Composer 选择 DOCX | Session `context_refs` Draft | Attachment Chip | 文件名、DOCX、移除 | remove_attachment |
| 拖入 DOCX | MIME + Form 格式校验 | Drop Overlay | 松开以添加 | accept_drop |
| 用户发送 | Message `source_refs` | User Attachment Strip | 本轮发送的材料 | open_preview |
| Turn 准备 | Turn Event | Live Status | 正在理解/整理上下文 | stop |
| 模型流式输出 | Text Delta | Streaming Blocks | 增量正文 | stop |
| 模型最终回复 | `visible_text` | Assistant Body Blocks | 正文结构 | copy/quote/retry |
| 回复来源 | `source_refs` | Source Strip | 来源数量和标题 | open_source |
| 需要补充信息 | confirmation request | User Question Panel | 问题、选项、进度 | submit/skip/cancel |
| 无法恢复的权限 | capability state | Disabled Permission Card | 为什么不能继续 | settings/rewrite |
| Form Plan Candidate | `document_job.plan_candidate` | Confirmation Card | 冻结材料、不会自动生产 | create_form_plan |
| Plan Ready | `active_plan` | Plan Card | 输入、交付、缺项、下一步 | generate/preflight |
| Content Generation | Job status | Process/Progress Item | 模型生成、随后本地校验 | stop |
| Draft Ready | GeneratedDraft | Artifact File Card | 草稿名、类型、已校验 | open/regenerate/preflight |
| Preflight Running | Job status | Process Item | 本地检查中 | stop |
| Preflight Failed | Preflight Receipt | Failure/Recovery Card | 公开问题、未生产 | retry/open_workbench |
| Preflight Ready | Receipt + Plan | Approval Card | 输入 hash 短码、输出、影响 | approve_execute |
| Execution Running | execution ID | Progress Item | 阶段和 current/total | stop |
| Success | execution result | Artifact Card Stack | 每个真实交付物 | open/save_as |
| Partial Success | execution result | Mixed Artifact + Recovery | 成功文件和缺失文件 | retry_preflight |
| Failed/Cancelled | execution result | Recovery Card | 未完成原因、是否有残留产物 | retry |

这张表是后续实施最重要的边界：Renderer 只接收 Presentation，不读取 Worker 或 Adapter。

---

## 26. 建议增加纯投影层，而不是让 UI 直接解释 Domain

### 26.1 推荐的数据模型

```text
ConversationPresentation
├─ items[]
│  ├─ message_id
│  ├─ turn_id
│  ├─ role
│  ├─ body_blocks[]
│  ├─ attachments[]
│  ├─ sources[]
│  ├─ interaction
│  ├─ artifacts[]
│  ├─ process
│  └─ footer_actions[]
└─ composer
   ├─ draft
   ├─ attachments[]
   ├─ busy_state
   ├─ blocking_reason
   └─ model_presentation
```

文件展示模型：

```text
FilePresentation
├─ file_id
├─ role: input | source | draft | output
├─ title
├─ suffix
├─ local_path
├─ preview_kind
├─ exists
├─ state
├─ artifact_key
└─ actions[]
```

选择展示模型：

```text
InteractionPresentation
├─ interaction_id
├─ kind
├─ mode: active | pending | read_only | unavailable
├─ title
├─ fields[]
├─ options[]
├─ selected[]
├─ receipt
└─ actions[]
```

正文展示模型：

```text
BodyBlockPresentation
├─ kind
├─ text / rows / language
├─ level
├─ streaming
├─ selectable
└─ actions[]
```

### 26.2 投影层只做三件事

1. 将 Domain/Session 数据转成公开、稳定的展示数据；
2. 决定哪一张 Interaction 是 active，其他变 read-only；
3. 隐藏绝对路径、内部 ID 和不应暴露的诊断字段。

它不做：

- Capability 路由；
- 内容生成；
- Plan 修改；
- Preflight；
- Approval；
- Production；
- 文件写入。

### 26.3 UI 动作必须回到中央 Action Dispatcher

Design 组件只发：

```text
ActionIntent(
    action_id,
    session_id,
    message_id,
    interaction_id,
    payload
)
```

Dispatcher 再映射到 Form 现有命令：

| ActionIntent | Form 现有处理 |
|---|---|
| `create_form_plan` | `_create_form_plan_from_candidate()` |
| `generate_content_draft` | `_start_content_generation()` |
| `preflight` | `_run_preflight()` |
| `approve_execute` | `_start_execution()` |
| `open_reference` | `_open_message_reference()` |
| `retry_provider_request` | `_send_message()` |
| `retry_preflight` | `_run_preflight()` |
| `stop` | 对当前 session operation 的 cancel |

不能让 `ArtifactCard` 直接调用 `AssistantProductionAdapter`。

---

## 27. UI 替换的风险分级

### 27.1 可安全替换的纯展示层

- AI 正文 Typography；
- Heading/Quote/Code/Table Renderer；
- Attachment Chip；
- User Attachment Card；
- Source Strip；
- Artifact File Card；
- Hover Message Actions；
- Live/Failure Status；
- Composer 默认/hover/focus 样式。

这些不需要改 Form Domain Contract。

### 27.2 需要新增 Presentation Contract 的部分

- active/read-only Interaction；
- Plan 摘要字段；
- 多产物 Artifact Stack；
- Progress Stage；
- Permission Unavailable；
- Question Receipt；
- Partial Success。

这些应先新增纯投影模型，再接 UI。

### 27.3 需要补 Domain/Persistence 的部分

- 可恢复的 Question/Permission Continuation；
- Interaction Receipt 持久化；
- Material Snapshot 重启恢复；
- 多附件 Composer；
- 每个最终 Artifact 的稳定 ID 和状态。

这些不能被包含在“样式迁移”提交中偷偷实现。

---

## 28. 为避免破坏 Form 主链，实施时必须遵守的冻结项

以下模块在 UI 第一阶段应视为冻结：

- `src/assistant/application/content_generation_service.py`
- `src/assistant/adapters/content_generation_adapter.py`
- `src/assistant/application/plan_builder.py`
- `src/assistant/contracts/document_plan.py`
- `src/assistant/contracts/execution.py`
- `src/assistant/adapters/production_adapter.py`
- Form 的真实 production execution services

允许变动的第一阶段范围：

- Presentation Projector；
- UI ViewModel；
- Design-aligned components；
- AssistantPanel 的 render/action wiring；
- 与展示直接相关的测试。

只有当投影模型无法表达真实状态时，才提交单独的 Domain Contract 变更。

---

## 29. 组合后的推荐验收场景

### 场景 A：带 DOCX 的普通对话

1. Composer 显示 Attachment Chip；
2. 发送后 Chip 清空；
3. 用户消息保留 Attachment Card；
4. AI 流式正文按 Block Style 展示；
5. 来源使用 Source Strip；
6. 文件卡仍可打开；
7. 会话重启后仍能恢复历史附件卡。

### 场景 B：从提示词生成报告

1. AI 正常回答；
2. 出现 Plan Confirmation；
3. 确认后出现简洁 Plan Card；
4. 生成时显示 Process Item；
5. 草稿完成后显示 Artifact File Card；
6. Preflight Card 显示真实公开证据；
7. Approval 后执行；
8. 最终 DOCX 显示为文件卡；
9. 输入文件 hash 不变。

### 场景 C：AI 生成并组装试卷

1. Plan Card 显示“试卷生成计划”；
2. 交付显示“学生卷 + 答案卷”；
3. 题稿生成后显示结构化草稿 Artifact；
4. 本地 Schema 校验失败时显示 Recovery，不进入 Preflight；
5. Preflight 绑定 scene/template/master；
6. Approval 后进入执行；
7. 成功时显示两张文件卡；
8. 缺少任一交付物时不得显示完整成功；
9. 学生卷和答案卷可分别打开。

### 场景 D：执行期间切换会话

1. Operation 继续归属原 Session；
2. 当前会话 Composer 不误显示另一个 Session 的 busy；
3. 切回后 Progress Stage 从持久化/Worker 状态恢复；
4. Cancel 只取消当前 Session 的操作；
5. 最终 Artifact 写回原 Session。

### 场景 E：重启恢复

1. Text、Source、Artifact 恢复；
2. 历史 Interaction 只读；
3. 过期 Approval 不可点击；
4. 未持久化 Material Snapshot 的任务明确标记“需要重新确认材料”；
5. 不伪装成可无损续跑。

---

## 30. 第二轮最终判断

用户提出的修正成立：

- **Design 的完整价值在于文件、选择、正文、来源、状态和动作形成了一套统一的展示语法；**
- **Form 的完整价值在于会话、授权、计划、生成、校验、审批、生产和交付形成了一套真实执行语法。**

当前问题不是 Form 没有链路，而是：

```text
强 Domain State
→ 被压扁成弱 Message Payload
→ 再被通用 QWidget 粗糙展示
```

正确改造应是：

```text
Form Domain State
→ Pure Presentation Projector
→ Design-aligned ViewModel
→ Design File / Choice / Body / Status Components
→ ActionIntent
→ Form Existing Command Chain
```

只要坚持这个单向边界，就能做到：

- 视觉完整；
- 交互清楚；
- 不丢失 Form 链路；
- 不把业务塞回 UI；
- 不继续扩展万能卡片；
- 不引入跨仓库运行时依赖；
- 不通过堆补丁制造新的状态不一致。

---

## 31. 本轮实施结果：Design 表现层 + Form 执行链

### 31.1 实际落地的边界

本轮没有复制 Design 的业务逻辑，也没有重写 Form 的生产链。最终结构是：

```text
Form Session / Plan / Job / Continuation
→ conversation_presentation.py（纯投影，无 Qt、无文件写入）
→ Design 风格的正文、文件、选择、计划、产物组件
→ AssistantPanel 统一动作分发
→ Form 既有的生成、校验、预检、审批、组装与交付
```

因此：

- Design 决定“怎么呈现、怎么选择、怎么反馈”；
- Form 决定“当前真实状态是什么、允许执行什么、执行后如何持久化”；
- UI 不直接调用 Production Adapter；
- 文件卡、计划卡、问题卡均不自行制造业务状态；
- 页面重载后，卡片是否可操作由持久化状态重新计算，而不是由控件内存决定。

### 31.2 新增的纯展示投影

`src/assistant/ui/conversation_presentation.py` 负责：

- 输入附件、来源文件、草稿与最终产物的统一文件展示模型；
- `available / missing / external` 文件状态；
- 问题选项、单选/多选、其他输入、跳过能力；
- Plan 事实、提示、动作与色调；
- 多产物投影；
- 当前 Interaction 的 `active / read-only` 判定；
- 问题答案的稳定序列化。

这个模块不依赖 Qt，也不调用 Form 命令，因此能够单独测试，不会把领域规则散落到 Widget 中。

### 31.3 已迁移的 Design 展示能力

| 能力 | 实施结果 |
|---|---|
| Composer 附件 | 34px 紧凑 Chip，支持文件名截断、后缀、打开与移除 |
| 拖拽反馈 | 独立 Drop Overlay，只接受当前 Form 链支持的 DOCX |
| 用户附件 | 138×108 文件卡，独立于用户气泡显示 |
| AI 正文 | 标题、段落、列表、引用、代码、表格、链接具有独立语义样式 |
| 来源 | 正文下方 Source Strip，可打开真实文件或链接 |
| 问题选择 | 单选/多选状态、其他输入、显式提交、可选跳过 |
| Plan | 使用公开事实网格，隐藏内部 plan ID、revision 等诊断字段 |
| 产物 | 92px 横向文件卡；学生卷、答案卷等多产物分别显示和打开 |
| 历史交互 | 过期问题、计划、审批显示只读回执，避免重复执行 |
| 过程状态 | 流式正文、进度、失败/恢复语义均保留 |
| 响应式 | 宽屏保持阅读列；窄屏消除横向文档画布，并保留“回到最新消息”状态 |

### 31.4 已接通的动作链

```text
自然语言请求
→ Provider 返回意图/正文
→ Form 构建 Plan Candidate
→ create_form_plan
→ generate_content_draft
→ 本地结构化内容校验
→ preflight
→ approve_execute
→ Production Adapter
→ 学生卷 + 答案卷
→ Session result.output_paths
→ 对话双产物卡
```

问题卡走的是另一条真实继续链：

```text
Provider Question
→ pending_continuation 持久化
→ Design 选择控件
→ submit_question_answer
→ 使用原 continuation_id 继续 Provider 请求
→ 清除 pending_continuation
→ 原问题卡重新投影为只读回执
```

这里没有新增平行会话状态，也没有把“问题已提交”只保存在控件中。

### 31.5 关键完整性处理

1. 最终产物不再只取单一 `output_path`，会完整读取并持久化 `output_paths`。
2. 学生卷和答案卷拥有独立 `artifact_key`，能够分别打开。
3. 卡片动作由当前 Session 状态决定，历史按钮不会因为重新渲染而复活。
4. 缺失文件显示不可用状态，不伪装成可打开产物。
5. 输入附件与 AI 来源在视觉和语义上分开，避免把“用户上传”误认为“AI 引用”。
6. 窄屏重排同时监听滚动位置与滚动范围变化，长对话不会丢失“回到最新消息”入口。
7. Form 的 Plan、Preflight、Approval、Production 实现未被 UI 重写。

### 31.6 有意保留的边界

以下能力没有伪装成已完成：

- Composer 目前仍只向 Form 生产链提交一个 DOCX 主输入；消息与产物展示已支持多文件，但多输入业务契约尚未扩展。
- Tool Call Permission 没有可验证的恢复协议，因此历史 Permission 卡只读，不提供虚假的“允许并继续”按钮。
- 外部 URL 只作为来源展示；本地文件存在性与可打开性才能由客户端完整验证。
- Design 原仓库的运行时没有被加入依赖，避免跨项目样式组件反向携带业务状态。

这些是明确的领域边界，不是 UI 遗漏。未来如需扩展，应先增加 Form Contract 与持久化协议，再由当前投影层自然展示。

### 31.7 验证范围

验证分成四层：

1. 纯投影测试：文件状态、问题响应、Interaction 活性、多产物投影；
2. Qt 组件测试：附件 Chip、文件卡、拖拽遮罩、Markdown 语义样式、选择提交；
3. Panel 集成测试：Continuation 恢复、多产物落盘与对话呈现、滚动/响应式行为；
4. 真实链路终验：自然语言生成七年级数学试卷，经过 AI 题稿、本地校验、预检、审批和组装，产出学生卷与答案卷，并进入对话产物卡。

最终视觉证据由 `scripts/export_assistant_conversation_visual.py` 生成，覆盖：

- 完整桌面对话；
- 对话底部问题与多产物；
- 流式生成状态；
- 760px 紧凑窗口。

最终回归结果：

- Ruff：本轮涉及的 Assistant、投影、组件、测试和截图脚本全部通过；
- Pytest：全部 Assistant 测试与 AI 文档架构守卫共 `141 passed`；
- 真实试卷链：验证学生卷与答案卷文件均实际落盘，并以两个独立产物引用写回 Session；
- 视觉复核：桌面、底部交互、流式状态、紧凑窗口四张截图均重新生成；紧凑窗口横向滚动范围为 0。

### 31.8 实施后的最终判断

本轮已经从“把 Form 数据塞进通用卡片”调整为“让 Form 状态经过稳定投影后，使用 Design 的完整交互语法呈现”。当前主链没有新增第二套 Plan、Job 或执行状态，展示组件也不越权执行领域命令。

这使得后续新增交付物、问题类型或 Plan 事实时，优先扩展纯投影模型和对应组件即可，不需要继续向 `AssistantInteractionCard` 塞入互相冲突的业务分支。

---

## 32. 第三轮深度复核：正文排版、标题层级与 Composer 尺寸

### 32.1 本轮不是继续看“有没有写 CSS”，而是验证“Qt 最终画出了什么”

本轮同时检查了四层证据：

1. Design 与 Flow 的语义字体常量；
2. Design 当前真正启用的消息渲染器；
3. Form 当前 `_AutoHeightMarkdown` 的 `QTextDocument` 运行时块格式；
4. Design 与 Form 的 Composer 在相同宽度下的真实控件几何。

结论不是“还需要微调几个像素”，而是：

- Form 当前正文和标题的 CSS 大部分没有进入 Qt Markdown 的最终块格式；
- Design 的活跃消息渲染器与旧的兼容 QWidget 渲染器不是同一套实现；
- 当前 Composer 的外框高度接近 Design，但内部输入区、按钮尺寸和宽度约束仍不一致；
- 现有测试只确认“CSS 中出现了对应选择器”和“外框高度正确”，没有确认实际字号、行高、段距和内部几何。

### 32.2 Design 真正启用的 AI 正文渲染链

Design 当前任务对话使用：

```text
TaskMessageStream（QListView）
→ MessageListDelegate（活跃 Renderer）
→ message_blocks.py（Markdown Block）
→ message_documents.py（QTextDocument / HTML）
→ task_message_stream.py（测量、布局、绘制、选择、链接）
```

`message_item_widgets.py` 中的 `_AssistantContent`、`_MessageHeading` 等 QWidget 组件仍然存在，但源码已经明确标注为旧调用方和测试保留的兼容实现，不是当前 `TaskMessageStream` 的主渲染路径。

这解释了为什么仅移植 `message_item_widgets.py` 中的 `16 / 15 / 14px` 标题常量，仍然无法保证与 Design 当前运行画面一致。

### 32.3 Design 的“声明值”与“活跃渲染值”存在差异

Design/Flow 的语义文本定义为：

| 角色 | 声明字号 | 字重 | 声明行高 |
|---|---:|---:|---:|
| 正文 `message.body` | 14px | 400 | 1.46 |
| 一级标题 `message.heading1` | 16px | 700 | 1.34 |
| 二级标题 `message.heading2` | 15px | 700 | 1.34 |
| 三级标题 `message.heading3` | 14px | 700 | 1.34 |

但 Design 活跃 Delegate 使用 `<h1>/<h2>/<h3>` 写入 `QTextDocument.setHtml()`。在当前 Qt 运行环境中，HTML 标题标签继续应用了 Qt 自身的标题倍率，因此运行时测得：

| 角色 | Design 活跃渲染实际字号 | 单行文档实际高度 | 块后间距 |
|---|---:|---:|---:|
| 正文 | 14px | 23.359px | 9px |
| 一级标题 | 28px | 42.875px | 6px |
| 二级标题 | 21px | 32.156px | 6px |
| 三级标题 | 17px | 26.797px | 6px |
| 列表 | 14px | 按行测量 | 8px |

正文两行的运行时高度为 `46.719px`，证明 `146%` 行高确实进入了 Design 活跃 `QTextDocument` 的块格式；标题块的 `134%` 也同样生效。

因此迁移前必须先确认验收目标：

- 如果目标是“与 Design 当前运行画面一致”，应把 `14 / 28 / 21 / 17px` 及对应实际行高固化为视觉基线；
- 如果目标是“与 Design 的语义 token 声明一致”，则应修正 Design 自身 `<h1>/<h2>/<h3>` 的 Qt 倍率问题，并以 `14 / 16 / 15 / 14px` 为基线；
- 不能一部分按声明值、一部分按 Qt 默认倍率，否则 Form 会形成第三套排版。

结合用户持续要求“正确迁移 Design 当前视觉”，本审计建议优先以 Design 活跃渲染画面为验收基线，同时把最终字号显式写入 Form 的渲染规格，避免依赖 Qt 的隐式倍率。

### 32.4 Form 当前实际渲染值：CSS 存在，但没有真正控制排版

Form 当前 `_AutoHeightMarkdown` 的源码意图是：

| 角色 | CSS 中写入的值 |
|---|---:|
| 正文 | 13px / 1.46 |
| 一级标题 | 20px |
| 二级标题 | 16px |
| 三级标题 | 15px |

但 `_AutoHeightMarkdown` 使用 `QTextEdit.setMarkdown()`。离屏运行时逐块检查 `QTextBlockFormat` 与字体后，实际得到：

| 角色 | Form 运行时字号 | 实际单行高度 | 块边距 / 行高状态 |
|---|---:|---:|---|
| 正文 | 9pt，约 12px | 14px | 上 6px、下 6px；`lineHeight=0` |
| 一级标题 | 18pt，约 24px | 28px | 上下 0；`lineHeight=0` |
| 二级标题 | 13.5pt，约 18px | 21px | 上下 0；`lineHeight=0` |
| 三级标题 | 10.8pt，约 14.4px | 16px | 上下 0；`lineHeight=0` |

这说明：

1. CSS 中的 `font-size` 没有稳定覆盖 Qt Markdown 生成的标题字体；
2. `line-height: 1.46` 没有进入正文块格式；
3. H1/H2/H3 的 `margin` 没有进入标题块格式；
4. 正文当前依赖 Qt 默认 6px 上下边距补偿视觉空隙，而不是 Design 的显式 Block Spacing；
5. 当前视觉会随 Qt 版本、默认字体和 DPI 改变，不能作为稳定设计系统。

当前正文因此明显偏小、偏紧；标题层级则由 Qt 默认 Markdown 比例决定，而不是由 Form 或 Design 的语义规格决定。

### 32.5 标题不仅是字号，Design 还定义了内容轴

Design 活跃消息标题还包含：

- 左侧 `3px` 主色内容轴；
- 标题文本相对内容轴缩进 `12px`；
- H1/H2/H3 内容轴透明度分别为 `100% / 60% / 40%`；
- 标题后的 Block Spacing 为 `6px`；
- 正文、列表、引用、代码和表格分别使用独立测量与块间距。

Form 当前只是把 Markdown 全部交给一个 `QTextEdit`，没有这条内容轴，也无法用当前 CSS 稳定表达这些布局规则。

所以“标题看起来不对”的根因不只是字号错误，而是缺少：

```text
语义块解析
＋ 独立块测量
＋ 内容轴
＋ 明确块间距
＋ 稳定的字体与行高格式
```

### 32.6 Composer 外框高度接近，但内部比例并没有迁移正确

#### 活跃对话 Compact Composer

在相同 `960px` 宽度下，离屏几何测量如下：

| 项目 | Design | Form 当前 | 差异 |
|---|---:|---:|---:|
| 外框高度 | 154px | 154px | 相同 |
| 内容边距 | 18/14/20/14 | 18/14/20/14 | 相同 |
| 根间距 | 9px | 9px | 相同 |
| 空状态输入区 | `y=33, h=52` | `y=14, h=85` | Form 高 33px，约多 63% |
| 发送按钮 | `y=100, 32×32` | `y=108, 32×32` | Form 下移 8px |

当前 Form 把 `QTextEdit` 以 stretch=1 加入布局，只设置了最小高度 `52px`，因此在空状态下被自动撑到 `85px`。

Design 使用固定高度的 `_edit_frame`，空状态为 `52px`，Compact 模式不对正文区增加垂直 stretch。也就是说，Form 虽然外框同为 154px，但有效输入区域比例已经不同，视觉上自然会显得“框很长、内部很空”。

#### 首页 Hero Composer

在相同 `1180px` 宽度下：

| 项目 | Design | Form 当前 | 差异 |
|---|---:|---:|---:|
| 外框高度 | 220px | 220px | 相同 |
| 根间距 | 10px | 8px | Form 少 2px |
| 空状态输入区 | `y=30, h=84` | `y=20, h=130` | Form 高 46px，约多 55% |
| 发送按钮 | `y=166, 36×36` | `y=158, 44×44` | Form 大 8px且上移 8px |

因此首页大输入框也只是外框高度相同，内部编辑区和发送控件仍不是 Design 的比例。

### 32.7 “对话框长度不对”同时包含横向宽度问题

首页 Hero Composer 的中心宽度公式已经与 Design 对齐：

```text
available = page_width - 144
target = min(1180, max(860, available × 0.78))
```

但活跃对话 Composer 当前被额外限制为：

```text
min(960, page_width - 48)
```

Design 的 TaskWorkspace 没有 `960px` 上限；Composer 在左右各 `24px` 的容器边距内横向扩展。

因此当活跃页面宽度超过 `1008px` 后，Form 不再随页面增长：

| 活跃页面宽度 | Design 目标宽度 | Form 当前宽度 | 少占用 |
|---:|---:|---:|---:|
| 1280px | 1232px | 960px | 272px |
| 1360px | 1312px | 960px | 352px |
| 1434px | 1386px | 960px | 426px |

这正是宽屏截图中输入框显得过短、与消息区和背景构图脱节的直接原因。

### 32.8 为什么上一轮测试会通过

现有测试主要检查：

- Composer 外框高度为 154px；
- 发送按钮宽度为 32px；
- Markdown 文档默认 CSS 中存在 `h1 / blockquote / pre / table` 等选择器。

它们没有检查：

- `QTextBlockFormat.lineHeight()` 是否真正生效；
- 文本 Fragment 的最终字体大小；
- 正文多行的实际像素高度；
- H1/H2/H3 的实际尺寸和块间距；
- Compact/Hero 输入区的真实几何；
- 活跃 Composer 在 1280px 以上是否继续扩展。

因此“测试通过”和“视觉正确迁移”在当前实现中并不等价。

### 32.9 推荐的正确实施方式

不能继续在 `_AutoHeightMarkdown` 的默认 CSS 上叠加补丁。正确边界应是：

```text
Form Message / Stream Event
→ 单一 Markdown Block Parser
→ 单一 Message Presentation Model
→ Design-aligned Block Renderer
→ Form 原有 Source / Interaction / Action 链
```

具体要求：

1. 用 Block Renderer 替换 `_AutoHeightMarkdown`，不要保留两套最终正文渲染器；
2. 正文、标题、列表、引用、代码、表格分别测量和绘制；
3. 字号、字重、行高和块间距必须显式进入 `QFont`、`QTextBlockFormat` 或独立布局，不能依赖 Qt 默认 Markdown/HTML 倍率；
4. 流式阶段使用同一 Presentation Model 的 streaming block，结束后完成最终 Markdown Block 解析，避免“流式一种样式、完成后另一种样式”；
5. Composer 使用固定 Edit Frame 与明确的附件槽位，不再让空输入区自动吞掉剩余高度；
6. 活跃 Composer 去掉 `960px` 上限，跟随 TaskWorkspace 左右 24px 边距；
7. Hero 发送按钮恢复 36px，输入区恢复 84px，根间距恢复 10px；
8. 保留 Form 已经完成的 Session、Plan、Question、Artifact 和执行链，不把 Design 的业务状态复制进 UI。

### 32.10 必须新增的几何与排版守卫

后续实施至少需要以下自动化守卫：

1. 正文 Fragment 字体为目标像素值；
2. 正文块 `lineHeightType` 与目标百分比正确；
3. H1/H2/H3 的实际字体、行高和内容轴位置正确；
4. 段落、标题、列表、引用、代码、表格的块间距正确；
5. Compact 空状态、带附件、长文本三种内部几何正确；
6. Hero 空状态、带附件、长文本三种内部几何正确；
7. 活跃页面在 `760 / 1008 / 1280 / 1434px` 下无横向滚动，且 Composer 宽度符合公式；
8. 流式结束前后，同一段 Markdown 的换行和整体高度不发生异常跳变；
9. 链接点击、文本选择、复制、来源打开和历史恢复仍然可用；
10. 统一 DPI 下生成 Design 与 Form 对照截图并进行像素级人工复核。

### 32.11 本轮最终判断

当前正文、一级标题、二级标题、三级标题和 Composer 长度都不能判定为“正确迁移”。

问题优先级为：

| 优先级 | 问题 |
|---|---|
| P0 | Form 的正文与标题 CSS 没有稳定进入实际 Qt Markdown 块格式 |
| P0 | 活跃 Composer 被错误限制为最大 960px |
| P1 | Compact 输入区被 stretch 到 85px，而不是 Design 的 52px |
| P1 | Hero 输入区、根间距和发送按钮尺寸均与 Design 不一致 |
| P1 | Design 的声明字号与活跃渲染字号存在两套值，迁移前必须固化唯一验收基线 |
| P2 | 现有测试只检查声明存在，没有检查最终像素和几何 |

本轮只完成分析、运行时测量与规格固化，没有继续修改产品样式。下一轮实施应以“替换错误渲染边界”为主，不应继续通过增加 CSS 选择器修补当前 `QTextEdit.setMarkdown()`。

---

## 33. 第三轮实施结果：正文运行时排版与 Composer 几何收口

### 33.1 正文渲染边界已经替换

新增：

```text
src/assistant/ui/message_body_renderer.py
```

`AssistantMessageBodyRenderer` 继续使用单一、可选择、可点击链接的 `QTextDocument`，但不再相信 `setMarkdown()` 后的默认 CSS 结果。新的执行顺序为：

```text
Markdown 解析
→ 遍历 QTextBlock
→ 识别 headingLevel / list
→ 显式写入 QFont 像素字号
→ 显式写入 QTextBlockFormat 百分比行高
→ 显式写入段距、列表行距与标题缩进
→ 绘制标题内容轴
→ 按最终 Document Size 自适应高度
```

它保留了原组件对外接口：

- `set_markdown()`；
- `set_live_text()`；
- `append_live_text()`；
- `toPlainText()`；
- 文本选择；
- 鼠标和键盘链接打开；
- 流式文本增量更新；
- 主题更新。

因此 `AssistantPanel` 的 Session、Stream Event、复制、引用、重试和来源打开逻辑不需要重写。

### 33.2 最终运行时排版值

新的运行时守卫确认：

| 角色 | 字号 | 行高 | 块后间距 | 额外结构 |
|---|---:|---:|---:|---|
| 正文 | 14px | 146% | 9px | 保留粗体、链接和内联代码格式 |
| 一级标题 | 28px / 700 | 134% | 6px | 左缩进 12px、3px 内容轴 |
| 二级标题 | 21px / 700 | 134% | 6px | 左缩进 12px、3px 内容轴 |
| 三级标题 | 17px / 700 | 134% | 6px | 左缩进 12px、3px 内容轴 |
| 列表行 | 14px | 146% | 行间 5px | 列表结束后 8px |

这些值现在进入最终 `QTextBlockFormat` 和文本 Fragment，而不是只出现在字符串形式的 CSS 中。

标题内容轴继续使用 Design 的层级透明度：

- H1：100%；
- H2：60%；
- H3：40%。

### 33.3 Compact Composer 几何结果

在 `960px` 与 `1312px` 两种宽度下均得到：

| 项目 | 最终值 |
|---|---:|
| 外框高度 | 154px |
| 内容边距 | 18/14/20/14 |
| 根间距 | 9px |
| 空附件槽 | 0px，但保留布局位置 |
| 空状态编辑区 | `y=33, h=52` |
| 带附件编辑区 | 38px |
| 附件槽 | 34px |
| 发送按钮 | `y=100, 32×32` |
| 其他 Footer 控件高度 | 34px |

附件为空时，附件行仍保持隐藏；布局由独立零高度 Slot 占位，因此不会重新出现无意义的空白控件。

### 33.4 Hero Composer 几何结果

在 `1180px` 宽度下：

| 项目 | 最终值 |
|---|---:|
| 外框高度 | 220px |
| 根间距 | 10px |
| 空状态编辑区 | `y=30, h=84` |
| 带附件编辑区 | 56px |
| 附件槽 | 34px |
| 发送按钮 | `y=166, 36×36` |

Hero Composer 已不再把编辑区撑到 130px，也不再使用偏大的 44px 发送按钮。

### 33.5 活跃对话 Composer 宽度结果

已删除最大 `960px` 限制。最终规则为：

```text
composer_width = active_page_width - 48
```

也就是继续由左右各 `24px` 的工作区边距控制。宽屏下 Composer 会与 Design TaskWorkspace 一样继续扩展，窄屏下仍由现有响应式页面和 Drawer 规则约束。

### 33.6 自动化验证

新增的守卫覆盖：

- H1/H2/H3 最终 Fragment 像素字号；
- 正文最终像素字号；
- 标题与正文 `lineHeight()`；
- 标题左缩进和块后间距；
- 正文块后间距；
- Compact 编辑区、附件槽和发送按钮几何；
- Hero 编辑区、根间距和发送按钮几何；
- 活跃 Composer 宽度与页面宽度关系。

验证结果：

- Ruff：涉及文件全部通过；
- 新增渲染器：Ruff format 通过；
- Assistant 全量回归：`137 passed`；
- 桌面、底部交互、流式状态和 760px 紧凑窗口截图全部重新生成；
- 紧凑截图未出现 Composer 横向溢出；
- 流式接口、复制、引用、重试、来源和 Interaction Card 原测试继续通过。

### 33.7 本轮视觉证据

```text
artifacts/assistant_active_conversation_overview_typography_fix.png
artifacts/assistant_active_conversation_typography_fix.png
artifacts/assistant_active_conversation_streaming_typography_fix.png
artifacts/assistant_active_conversation_compact_typography_fix.png
```

截图已经能够确认：

- 正文不再使用过小的 Qt 默认 9pt；
- 二级标题拥有稳定字号、行高和左侧内容轴；
- 列表行距与正文阅读节奏统一；
- 活跃 Composer 在桌面宽屏中填满工作区；
- 附件 Chip 位于编辑区上方的独立 34px 槽位；
- Compact 窗口仍保留完整输入、模型与发送入口。

### 33.8 实施后的最终判断

本轮已修复第 32 章确认的两个根问题：

1. 正文与标题从“CSS 看似存在、Qt 实际不执行”改为“最终块格式可测量、可守卫”；
2. Composer 从“外框高度相同、内部比例和宽度错误”改为“内部几何和响应式宽度同时对齐”。

整个修复只发生在 Presentation/UI 层，没有修改 Form 的 Provider、Plan、Question Continuation、Preflight、Approval、Production 和产物持久化链。

---

## 34. 第四轮几何矩阵复核：阅读轴、复杂 Markdown 与窄窗边界

### 34.1 本轮检查范围

本轮不再只检查单张宽屏截图，而是对以下状态做运行时几何测量：

- 窗口宽度：`760 / 1008 / 1280 / 1600px`；
- Composer：空状态、附件状态、阻断状态；
- 消息类型：用户消息、AI 正文、Interaction Card；
- Markdown：长标题、正文、引用、列表、长代码、宽表格、内嵌图片；
- 页面状态：顶部、底部、需要纵向滚动、流式输入。

判定条件包括：

1. 控件不越界、不相互覆盖；
2. 页面和正文不产生隐藏的横向溢出；
3. 用户气泡、AI 正文和交互卡使用同一阅读列；
4. 长标题强调轴覆盖完整标题块；
5. 图片和代码在窄窗中仍可完整阅读；
6. Composer 与消息滚动区不发生遮挡。

### 34.2 Composer 多状态结果

真实应用宽度下未发现 Footer 控件碰撞：

| 模式 | 测量宽度 | 空态 | 附件态 | 阻断态 |
|---|---:|---|---|---|
| Compact | 712 / 960 / 1312px | 无越界、无重叠 | 无越界、无重叠 | 无越界、无重叠 |
| Hero | 760 / 960 / 1180 / 1386px | 无越界、无重叠 | 无越界、无重叠 | 无越界、无重叠 |

发送按钮在 Compact 中始终保持 `32×32`，在 Hero 中始终保持 `36×36`；附件态只压缩编辑区，不改变发送按钮的垂直轴。

低于产品最小工作区时，Footer 的内容最小宽度会把 Composer 撑到约 `502–610px`。当前一级功能在 `760px` 窗口下仍有 `712px` Composer，因此该边界不会进入正常产品路径；如果未来允许小于 610px 的独立浮窗，需要新增 Footer 折叠规则，不能继续强行压缩现有控件。

### 34.3 已确认并修复的阅读列错位

修复前，在 `760px` 窗口中：

```text
AI 正文：x = 20，width = 706
Interaction Card：x = 48，width = 650
```

两条主轴相差 28px；用户气泡还贴近消息视口右边缘，没有落在 Card 的右边界上。

现已统一采用 Design 的阅读列规则：

```text
reading_width = min(820, viewport_width - 96)
reading_x = max(48, (viewport_width - reading_width) / 2)
```

最终矩阵：

| 窗口 | 消息视口 | 阅读列 | 页面内相对 x | Composer | 横向滚动 |
|---:|---:|---:|---:|---:|---:|
| 760px | 746px | 650px | 48px | 712px | 0 |
| 1008px | 754px | 658px | 48px | 720px | 0 |
| 1280px | 1026px | 820px | 103px | 992px | 0 |
| 1600px | 1346px | 820px | 263px | 1312px | 0 |

AI 正文、用户气泡右边界和 Interaction Card 现在在四档宽度下使用同一条阅读轴；宽屏保持 820px 最大阅读宽度，窄屏保留左右各 48px 的安全边距。

### 34.4 长代码的隐藏裁切

Qt Markdown 会把围栏代码块标记为 `nonBreakableLines=True`。修复前，一条长代码会得到：

```text
viewport = 280px
document ideal width = 1372–1498px
horizontal maximum = 1092–1218px
```

但正文横向滚动条被隐藏，因此用户看到的是被静默裁掉的右半段。

现已在最终块格式中取消不可断行，并显式使用：

- 13px 等宽字体；
- 152% 行高；
- 左右 10px 内容内边距；
- 代码语义表面和边框；
- 阅读列内换行。

最终在 `280 / 480 / 820px` 三档下均满足：

```text
document width <= viewport width
horizontal maximum = 0
```

### 34.5 Markdown 图片的原图宽度溢出

修复前，`1434px` 宽的本地图片会直接把正文文档撑到 `1434px`，即使消息正文只有 280px 或 820px 宽；右侧同样会被静默裁切。

现已按 Design 图片块规则处理：

```text
target_width = min(420, viewport_width, intrinsic_width)
target_height = intrinsic_height × target_width / intrinsic_width
```

并将纯图片块水平居中。验证结果：

| 正文宽度 | 图片最终宽度 | 横向滚动 |
|---:|---:|---:|
| 280px | 280px | 0 |
| 480px | 420px | 0 |
| 820px | 420px | 0 |

同时将图片块行高恢复为 100%，避免正文的 146% 行高把 386px 图片错误放大成约 563px 的空白高度。

### 34.6 长标题强调轴

修复前标题强调轴由首行 `cursorRect()` 决定。标题换成 2–6 行时，轴仍只覆盖第一行。

现改为使用 `QAbstractTextDocumentLayout.blockBoundingRect()`，强调轴高度等于完整标题块高度。验证中：

- 280px 宽 H1：6 行，轴覆盖完整 246.4px 标题块；
- 480px 宽 H1：3 行，轴覆盖完整 117.8px 标题块；
- 820px 宽 H1：2 行，轴覆盖完整 74.9px 标题块。

### 34.7 引用块几何

引用块不再沿用 Qt 默认的左右各 40px 缩进。当前使用：

- 左侧文本起点 25px；
- 右侧内边距 12px；
- 上下内容留白 10px；
- 块后间距 10px；
- 浅色语义表面；
- 左侧 3px 指示轴。

这使引用与正文保持同宽语义卡，而不是在窄窗中额外损失 80px 可读宽度。

### 34.8 新增自动化守卫

新增守卫覆盖：

- 746px 消息视口下 AI 正文为 `x=48, width=650`；
- 用户气泡右边界与同一阅读列对齐；
- 围栏代码不再是不可断行块；
- 长代码不产生横向滚动；
- 1200px 测试图片被限制到 420px；
- 长标题强调轴高度等于完整标题块高度；
- 引用块左右内容边距为 25px / 12px。

本轮回归结果：

- 对话呈现与面板回归：`55 passed`；
- Assistant 全量回归：`139 passed`；
- Ruff check：通过；
- Python 编译检查：通过；
- 四档完整面板运行时横向滚动：全部为 0。

最终视觉证据：

```text
artifacts/assistant_active_conversation_overview_geometry_validated.png
artifacts/assistant_active_conversation_geometry_validated.png
artifacts/assistant_active_conversation_streaming_geometry_validated.png
artifacts/assistant_active_conversation_compact_geometry_validated.png
artifacts/assistant_complex_markdown_geometry_final.png
```

### 34.9 仍然存在但不应继续用小补丁掩盖的差异

功能几何已经安全，但以下项目仍不是 Design 的逐控件复刻：

1. Design 的代码块是独立组件，具有语言栏、复制按钮、最大 260px 高度和块内横向滚动；Form 当前为了保证内容不裁切，采用阅读列内换行；
2. Design 的复杂嵌套引用可以由独立 Block Widget 递归渲染；Form 当前仍由一个可选择文本的 `QTextDocument` 承载；
3. 远程 Markdown 图片不应由正文控件静默联网加载，当前只对已经可解析的本地图片做几何约束，外部资源继续走链接或文件卡链路。

这些差异不会破坏当前“AI 生成—确认—执行—产物”链路，也不再造成越界或内容丢失；但如果验收目标是完整复制 Design 的代码栏、复制按钮和嵌套块交互，就应把 Markdown Block Renderer 作为一个独立迁移项实施，而不是继续给单一 `QTextEdit` 增加条件分支。

### 34.10 本轮结论

本轮确认并修复了四个真实几何缺陷：

1. 窄窗消息与卡片阅读轴不一致；
2. 长代码被隐藏裁切；
3. 大图按原始尺寸撑宽正文；
4. 多行标题强调轴只覆盖第一行。

当前 760–1600px 的一级功能页面、消息流、交互卡与 Composer 已形成完整、无横向溢出的几何闭环。剩余差异集中在“代码块和复杂嵌套 Markdown 是否升级为独立交互组件”，不应与本轮已经完成的基础几何安全问题混为一谈。
