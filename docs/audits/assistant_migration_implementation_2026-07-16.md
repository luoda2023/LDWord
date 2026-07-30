# AI 文档助手迁移实施与验收记录

> 日期：2026-07-16  
> 对应分析：`AI文档助手Design与Flow迁移深度分析_2026-07-16.md`  
> 状态：源码实现已完成；AI 为 Form 全局一级功能，独立 AssistantPanel 内只保留已闭环的 Design 会话交互。委托、项目、计划、长期记忆、技能中心因链路不完整已整体删除；右侧旧 Context Rail 仍排除，避免上下文双状态。

## 1. 已落地范围

### UI 与交互

- `PANEL_SPECS` 在资料包之后新增 `assistant` 一级功能，Form 全局侧栏显示独立 Sparkles 图标。
- `create_panel("assistant", bridge)` 懒加载独立 `AssistantPanel(first_level=True)`；它由 `MainWindow.panel_stack` 持有，不属于 Workbench。
- `QuickExecutionDetail` 不承载 Assistant Card；Workbench 的 `DetailPaneController` 也不注册 `assistant_home`。
- 工作台“AI 帮我生成”只通过 Bridge 跳转到全局 Assistant 面板，侧栏直接点击与工作台入口汇聚到同一实例。
- 空态使用独立 `AssistantCreativeHome`：网格创作背景、蓝色标题锚点、“今天要创作什么？”、220px Hero Composer、智能建议与两列常用任务。
- Hero Composer 的回形针绑定当前 DOCX，书签打开任务菜单，模型下拉绑定 Provider，圆形发送按钮进入现有会话链；尚未接通的联网按钮明确禁用。
- 智能建议和常用任务只填充提示词，不自动执行；支持新增和删除本地自定义任务。
- 空态显示 Design 结构的 240px 会话栏，不显示 Assistant Header 或 280px 右上下文栏；发送首条消息后，同一一级面板原位切换到活动消息流和紧凑输入器。
- 再次从工作台进入时，有活动消息就恢复当前会话；没有消息才显示首页，避免把运行中的链路重置为空态。
- 助手输入器使用 Enter 发送、Shift+Enter 换行；切换其他全局功能后再返回，原会话和 Worker 不被销毁。
- 计划、数据披露、权限、预检、执行确认、进度、产物和恢复均使用类型化卡片，不用自由文本猜状态。

### 中立运行时与 Provider

- 消息、事件、运行结果、取消、会话、一次性 continuation 均为版本化合同。
- 支持内置离线 Mock 与 OpenAI-compatible SSE；API Key 与普通 JSON 配置分离，优先使用 Windows 凭据管理器。
- Provider 连接测试在后台执行，只发送固定 `OK`，不发送文档内容。
- 模型输出不直接写产品事实；所有 Form 操作必须经过 Tool Gateway 或应用编排层。

### 文档流程

- 已有 DOCX：自然语言需求 → 确定性场景路由 → `DocumentPlan` → 异步本地预检 → 用户确认 → 全局单租约生产 → 四类终态。
- 从需求生成：模型只输出 Markdown → 本地校验 → 现有内容编译器生成 `DocumentFragment` → 现有 Composer 生成可审阅草稿 DOCX → 同一预检/审批/生产链。
- 内容草稿可打开审阅或重新生成；每次生成产生新草稿和新计划修订，不覆盖上一版草稿。
- 禁止模型返回的 OOXML、`word/document.xml` 或未授权上下文绕过内容编译器。

### 安全、恢复与并发

- `DisclosureGrant` 合同可以精确绑定会话、Provider、模型、引用、字段与内容指纹；但当前嵌入 UI 尚未接入附件/正文披露授权，不能把合同存在描述成产品已支持正文上传。
- L0–L6 工具分级、默认拒绝和幂等合同已实现并测试；当前 Provider 仍以文本响应为主，原生工具调用与权限卡尚未接入工作台消息流。外部发布继续永久禁用。
- 工具权限暂停会持久化，匹配授权后仅能消费一次。
- 文档生产使用全局单所有者租约；结果始终归属发起会话。
- 执行开始与终态写入原子日志；重启时只有完整终态回执可恢复为成功，无回执任务明确标记为中断。
- 输入文件、方案、场景和模板均在预检后绑定哈希；执行前再次验证，避免检查后被替换。

## 2. 不引入新问题的约束

- 未重新实现 Form 生产引擎，仍调用 `ProductionExecutionRequest` 与现有执行结果合同。
- 未引入新的 Provider SDK 或 UI 框架依赖。
- AI 未配置、配置损坏或密钥不可用时回退到可解释错误，Form 原工作流仍可使用。
- 生成内容和会话存储位于应用数据目录，不写项目源码目录。
- 不覆盖输入文档；默认输出策略为新文件且 `overwrite=False`。
- 首页与活动会话共用同一个全局 `AssistantPanel`、Coordinator 和 Worker 集合；MainWindow 关闭时分别等待 Workbench 与 Assistant 的执行线程。
- 附件选择只绑定 Form 当前文档，不把“已选择”错误解释为“已授权云端上传”。
- 联网能力未接通时保持禁用，避免只迁移图标却制造虚假功能。

## 3. 验收证据

### 3.1 代码与边界

- 新增 `src/assistant/` 独立子系统，共 51 个 Python 模块；按 `contracts / storage / runtime / providers / tools / adapters / application / ui` 分层。
- 新增 16 个助手专项测试文件；下层模块的架构测试明确禁止反向导入 `src.ui`、工作台 Panel 或生产 UI。
- 源码扫描未发现助手实现中的 `TODO`、`FIXME`、`NotImplementedError` 或对两个桌面参考仓库的运行时路径依赖。
- `python -m compileall -q src tests` 通过。

### 3.2 自动化回归

2026-07-16 第二次 UI 纠偏后的执行结果：

| 测试门禁 | 结果 | 覆盖重点 |
|---|---:|---|
| 助手、工作台与主窗口生命周期组合回归 | 117 passed | 合同、存储、Provider、内容生成、计划、执行租约、独立一级 Panel、工作台跳转、主窗口懒加载、标题栏和 UI 生命周期 |
| 新首页/宿主专项 | 24 passed | 全局 AI Panel、无 Workbench 嵌套/详情宿主、Design 会话侧栏、快捷填词、附件、首次模型选择、空态到活跃态切换 |
| 完整生成链单测 | 1 passed / 35.98s | 提示词 → 草稿 → 预检 → 批准 → `success` → 真实 DOCX |
| 全仓收集 | 3988 tests collected | 全仓 240s 尝试达到超时门限；未出现失败输出，但不计为“全量通过” |
| Python 编译检查 | passed | `python -m compileall -q src tests` |

原生窗口验证曾生成 `alavette_form.log`，发布守卫准确拦截；清理该验证副产物后相关回归通过。仓库现有 `build/` 与 `dist/` 仍属于旧构建目录，不作为本轮源码可见性证据。

### 3.3 原生视觉验收

完成完整 MainWindow 的 Windows 原生 FreeType 字体截图检查：

1. Form 全局侧栏在资料包后显示独立 AI Sparkles 图标，索引为 4。
2. 选中后 `MainWindow.panel_stack.currentWidget()` 为独立 `AssistantPanel`，不是 Workbench detail。
3. Workbench 内没有 `assistant_home` 或 `_assistant_panel`；工作台按钮只发出全局面板导航。
4. 空态显示中央创作首页与 Design Session Rail，不显示 Assistant Header 或右 Context Rail。
5. 标题、Hero Composer、工具区、智能建议和两列常用任务完整出现，中文无方框字或裁切。
6. 完整主窗口截图保存在 `artifacts/assistant_first_level_panel_native.png`。

实际提示词链路从独立 AssistantPanel 完成内容草稿、预检、批准和生产，最终 `job_status=success`。输出 DOCX 使用 Word COM 渲染为单页 PNG，`status=ready`、无渲染 issues，中文一级/二级标题、项目符号和正文均无截断或重叠。

### 3.4 当前打包状态

- `scripts/windows/start_app.bat` 使用当前 `.venv` 源码，已完成上述原生与端到端验证。
- 现有 `dist/Alavette-Form_V1.0/Alavette-Form_V1.0.exe` 时间为 2026-07-12，早于 2026-07-16 的 AI 修改，是旧包，不能用于判断本轮 UI 是否存在。
- 在独立验证目录进行了四轮新包审计。前两类失败分别暴露：运行时必需的 `config_library/count_profiles` 未收集、`src.shared.ui` 与 `src.services.material_attachments` 延迟导入未收集。
- 正式打包脚本现已增加这两类数据目录、共享 UI 子模块、资料附件处理子模块，以及实体归档所需 hidden imports；相关发布外壳测试已固定这些要求。
- 第四版独立验证包验证了打包依赖与主窗口启动，但生成时间早于本次“独立一级 AI Panel”最终纠偏；它不能作为新 UI 已进入发布包的证据。正式发布前必须用已修复脚本重新构建。
- 为保护用户现有产物，本轮没有覆盖旧 `dist`；正式发布可使用已修复脚本重新生成标准目录和压缩包，不能继续分发现有 2026-07-12 旧包。

### 3.5 迁移许可

- Flow 派生文件的基线、实际参考文件 SHA-256 和 Form 目标文件已记录在 `assistant_migration_manifest_2026-07-16.md`。
- Flow MIT 许可全文已进入 `licenses/static/alavette-flow/LICENSE`。
- `THIRD_PARTY_NOTICES.md`、`licenses/components.json`、`licenses/manifest.json`、许可构建脚本和发布检查已登记 Flow 派生组件。
- Design 仅作为体验与布局原则参考，不把视觉思想错误标记成源码复制。

## 4. 最终数据与执行链路

```text
用户输入
  ├─ 已有 DOCX ─→ 确定性场景路由 ─→ DocumentPlan
  └─ 从需求生成 ─→ 模型 Markdown ─→ 本地校验
                                      └→ DocumentFragment ─→ 草稿 DOCX

DocumentPlan / 草稿 DOCX
  → 本地预检与输入哈希
  → 用户显式批准
  → 全局执行租约
  → Form 既有 ProductionExecutionRequest
  → success / partial_success / failed / cancelled
  → 原子执行日志、产物卡片与重启恢复
```

模型没有直接写 OOXML、直接调用 UI 或绕过审批的入口。Provider 失败、用户取消、权限暂停、内容生成中断和应用重启都在各自状态机中落到可解释终态。

## 5. 最终结论

本次实现完成了原分析文档定义的两个阶段，而不是只放入聊天界面：

- Design 的视觉与交互原则已经转换为适配 Form Shell 的原生 Qt 控件和响应式行为。
- Flow 的中立会话、消息、流式、Provider、取消与 continuation 思路已经去产品化后落地。
- Form 继续独占场景事实、内容编译、预检、生产执行和结果合同。

因此，新增能力可以独立失败和恢复，不改变原有非 AI 工作流，也没有引入新的模型 SDK、UI 框架或第二套文档生产引擎。当前准确完成的是“AI 文档生成与排版生产链”；附件披露、云端正文分析和 Provider 原生工具调用仍是后续集成项，不应被提前标记为完成。

## 6. 第四次 UI 纠偏实施记录：Design 会话侧栏

> 历史实施记录；其中未闭环入口已由第 7 节删除，不代表当前界面。

第 1、3 节中“一级 Panel 不显示 Session Rail”的描述已经过期。用户再次确认后，正确结构是“Form 全局一级 AI 入口 + AI Panel 自己的 Design 会话侧栏 + 中央创作/会话面板”。

### 6.1 源码变化

- 新增 `src/assistant/ui/session_sidebar.py`，按 Design `SessionSidebar` 的信息架构迁移：对话/委托、新任务、项目、计划、长期记忆、技能中心、置顶和最近任务。
- `AssistantPanel` 新增与 `embedded` 互斥的 `first_level` 布局模式；一级模式显示 240px 会话侧栏、隐藏旧右 Context Rail。
- `panel_registry.create_panel("assistant")` 改为 `AssistantPanel(first_level=True)`。
- 会话侧栏直接读取 `AssistantSessionSummary`，所有修改仍回到 `AssistantSessionCoordinator`；侧栏没有独立存储。
- 最近/置顶拆成两个真实列表；右键固定、重命名、删除，以及跨区拖拽固定/取消固定都写回会话 aggregate。
- 会话仓库调整为“置顶优先、组内最新优先”，与“最近任务”的产品语义一致。
- 新增 `projects / scheduled / long_term_memory / skill_center / delegate` 能力页：能投影 Form 真实状态的入口直接投影，缺少后端的入口明确说明未迁移，不再点击无响应。
- 图标目录补齐 Design 侧栏使用的 message-circle、git-branch、briefcase、calendar-days、database 和 wand-sparkles。

### 6.2 当前真实完成度

| 区域 | 状态 | 证据 |
|---|---|---|
| 全局一级入口 | 完成 | `PANEL_SPECS` 与 MainWindow Panel Stack |
| Design 会话侧栏结构 | 完成 | `AssistantSessionSidebar` |
| 新建/打开/草稿/重命名/删除 | 完成 | `AssistantSessionCoordinator` 与 UI 回归 |
| 置顶/取消置顶/跨区拖拽 | 完成 | `AssistantSession.pinned` 单一状态源 |
| 项目上下文 | 完成 Form 投影 | `PanelBridge` 文档/模式/方案/模板 |
| 计划概览 | 完成 Form 投影 | `active_plan / continuation / document_job` |
| 技能目录 | 完成只读投影 | 实际 `ToolRegistry.public_catalog()` |
| 长期记忆 | 未迁移 | UI 明确边界，不伪装 |
| 委托运行时 | 未迁移 | UI 明确边界，不启动伪后台任务 |
| 中央首页到 DOCX | 保持完成 | 原 Assistant Worker 与生产链未复制 |

### 6.3 新验收证据

- 助手与工作台专项回归：24 passed（纠偏后的第一轮）。
- Assistant 合同、存储、工具、Provider、恢复、内容生成、生产适配和 UI 全栈回归：82 passed / 82.15s。
- 主窗口关闭、一级面板索引、工作模式、Workbench Detail 与修复导航定向回归：6 passed / 7.36s。
- 广域主窗口组合回归曾运行至 244s 工具时限后被终止，过程中未返回失败，但不计作通过；上述 6 项定向门禁用于补足本轮改动边界。
- `test_prompt_generation_flows_through_draft_preflight_approval_and_output` 已包含在 82 项内，验证提示词 → 草稿 → 预检 → 批准 → `success` → 实际 DOCX。
- 编译检查：`python -m compileall -q src/assistant/ui src/ui/panel_registry.py src/ui/icons/catalog.py` passed。
- 主窗口结构检查：`AssistantPanel / current_index=4 / first_level=True / session_rail=True / context_rail=False`。
- Windows DirectWrite 原生截图：`artifacts/assistant_first_level_with_design_sidebar_native.png`。
- 原生结构实测：`AssistantPanel / current_index=4 / first_level=True / session_rail=True / recent_sessions=1 / context_rail=False`；中文标题、侧栏导航和最近任务无方框字或裁切。

## 7. 最终收敛实施：删除未闭环入口

根据“链路不完整即删除”的验收标准，本轮在第 6 节基础上继续收敛：

- 删除“委托”Tab 及 `mode_changed / select_mode` 逻辑；
- 删除“项目、计划、长期记忆、技能中心”四个导航按钮；
- 删除对应 `navigation_requested` 信号和中央 Capability View；
- 删除 `_show_sidebar_navigation`、`_show_utility_surface` 与全部占位/只读投影文案；
- Center Stack 从 3 页降为 2 页，只保留创作首页和活动会话；
- 删除只服务于上述入口的 git-branch、briefcase、calendar-days、database、wand-sparkles 图标；
- 保留且继续验证对话、新任务、置顶/取消置顶、最近任务、重命名、删除、草稿恢复和 DOCX 生产。

最终原生结构证据：

- 一级面板索引：4；
- 会话侧栏：可见；
- 侧栏按钮：`[对话, 新任务]`；
- 最近任务：1；
- Center Stack：2 页；
- 右 Context Rail：不可见；
- 截图：`artifacts/assistant_first_level_closed_flows_native.png`；
- 精简后 Assistant/Session/Workbench 定向回归：30 passed / 32.83s；
- 精简后 Assistant 合同、存储、Provider、工具、恢复、内容生成、生产适配与 UI 全栈回归：82 passed / 39.77s；
- `python -m compileall -q src tests` 与 `git diff --check` 通过。

## 8. 中央创作页完整视觉回迁

本轮继续修正 `src/assistant/ui/creative_home.py`，不再以固定矩形近似 Design 背景：

- 使用 42px 网格、双轴倾斜坐标和网格交点四边形恢复透视背景；
- 面片按 20–28 个目标数量动态生成，具备淡入/停留/淡出、去重叠和 Hero 区域避让；
- 动画只在页面可见时运行；
- 页面边距、3:2 上下留白、中央宽度公式、标题几何和区块间距对齐 `NewTaskView`；
- Hero 恢复为 220px 本体 + 240px 稳定槽；
- 常用任务恢复为 3 × 50px 固定视窗，自定义任务增加后滚动而不撑坏首页；
- Provider、附件、建议填充、自定义任务和发送链均继续复用 Form 已有状态源。

新增 UI 回归固定上述几何和背景变换合同。Windows DirectWrite 大窗与紧凑窗截图分别为：

- `artifacts/assistant_first_level_optimized_background_native.png`；
- `artifacts/assistant_first_level_optimized_compact_native.png`。

最终回归为 73 个 Assistant 测试全部通过；Workbench 一级路由和提示词 → 草稿 → 预检 → 批准 → DOCX 端到端用例再次通过。额外检查发现并修复了第 4 行自定义任务被内部容器压缩、滚动条不出现的问题；现在内部高度按真实行数增长，外层仍固定 150px。

## 9. 中央页交互闭环修正

本轮不再只检查几何，而是逐控件检查“意图、状态源、结果、反馈、失败恢复和键盘可用性”。实施结果：

- 删除未接入文档链的联网图标、重复任务书签、无真实含义圆环和永久禁用的“继续”；
- “智能建议”改为真实语义“快速开始”；
- 发送按钮由视觉可用改为真实状态门控：非空输入、可用 Provider、无阻断条件才可发送；
- 添加材料改为带文字按钮，选中文档后显示文件名并切换为“更换材料”；
- 检查/格式/模板类任务增加 DOCX 前置条件，并随 Bridge 文档状态实时解锁或禁用；
- 快捷任务点击后只填入并显示选中态，不创建 Session、不自动调用模型；
- 常用任务增加结果说明、键盘激活、焦点态和禁用原因；
- 自定义任务补齐新增、编辑、确认删除、12 项上限、重复名检查、持久化失败回滚；
- Provider 选择改用共享 `StyledComboBox`，没有建立第二份模型状态。

最终面板回归 18 passed，Assistant 全栈 75 passed；Workbench 一级 AI 路由与提示词到真实 DOCX 定向回归 2 passed。原生证据为 `assistant_first_level_interaction_complete_native.png`、`assistant_first_level_interaction_selected_native.png` 和 `assistant_first_level_interaction_compact_native.png`。

## 10. 背景稳定性与 Provider 就绪门禁

- 背景增加固定环境面片并提高网格可识别度，首帧不再依赖动画淡入；
- `ProviderRouter.readiness` 在不发起网络请求的前提下检查配置存在性、启用状态和密钥可读性；
- 缺 Key 的配置在首页标为未就绪并禁用，不能再进入发送；
- 配置保存补齐密钥必填、热同步、未保存修改保护、失败回滚和删除确认；
- 运行时 Provider 失效会生成可直达 AI 设置的恢复动作；
- 支持边界明确为 OpenAI-compatible Chat Completions SSE，不宣称原生支持任意厂商接口。

原生证据为 `assistant_background_restored_native.png`、`assistant_api_configuration_native.png` 和 `assistant_api_unready_blocked_native.png`；详细断点、状态表和安全边界见深度分析文档第 32 节。

## 11. 模型状态连续性与恢复链收口

本轮以“状态可信”为实施标准，完成以下收口：

- `src/ui/bridge.py`：增加偏好设置页级意图，支持未加载和已加载两种时序下直达 AI 模型页；
- `src/ui/panels/preferences_panel.py`：持久化连接测试状态，锁定测试对象，将结果回写到启动时 Profile，并区分本地、未就绪、未测试、已验证和上次失败；
- `src/assistant/runtime/providers/profiles.py`：Profile 增加 `connection_status / last_checked_at / last_check_message`，对旧 JSON 保持向后兼容；
- `src/assistant/ui/creative_home.py`：模型列表显示语义状态，增加直达设置按钮；
- `src/assistant/ui/assistant_panel.py`：活动会话紧凑输入器显示模型状态和设置按钮；配置修改后同步 Session 模型身份；Provider 失败时同时提供设置和重试动作；
- 非嵌入模式明确隐藏 `_embedded_session_combo`，修复空控件覆盖一级会话头部；
- 编辑既有 Profile 时保留 `timeout_seconds / enabled / extra_body`；仅改名保留已验证状态，地址、模型或 Key 变更则回退为未测试。

状态判定规则：

```text
本地 readiness 不通过
  → 禁止发送，显示未就绪原因

本地 readiness 通过 + 未测试/上次失败
  → 允许用户发送，但保留观测标记

本次运行失败
  → 恢复卡（直达 AI 设置 + 重新发送）
```

新增真实 HTTP 回环测试，验证 Profile、密钥、Router、`POST /chat/completions`、Bearer Header、SSE delta 和 `[DONE]` 完整边界。最终 Assistant 全栈 88 passed，偏好设置/Bridge/Workbench 边界 24 passed，Provider 专项 11 passed，`compileall` 和 `git diff --check` 通过。

视觉证据：`assistant_model_status_and_settings_native.png`、`assistant_api_status_native.png`、`assistant_provider_recovery_native.png`。完整断点表、时序图和边界见深度分析文档第 33 节。

## 12. 活动对话工作区完整迁移

本轮确认此前仅完成了一级外壳与空态首页，活动会话仍错误复用共享 `ChatBubble + MessageInput`，并且 Worker 流式事件没有连接到 Panel。实施纠偏如下：

- 新增 `src/assistant/ui/conversation_view.py`：实现 860px 阅读列、640px 右对齐浅色用户消息、820px 透明无头像 AI Markdown 回复、复制动作和活动页静态透视网格；
- `AssistantHeroComposer` 增加 `hero / compact` 双模式；活动页使用 154px 紧凑模式，Provider readiness、附件、草稿、设置导航不复制状态源；
- 活动 Header 恢复为 56px 任务头，只保留会话身份和更多操作；模型选择与设置归位到 Composer；
- `AssistantTurnWorker.event_received` 接入 UI，完整投影 `turn_started / context_ready / model_started / text_delta / failed / cancelled / finished`；
- 发送按钮运行时原位切换为停止按钮，Turn、内容生成、预检和执行共享真实取消链；
- 新增回到最新消息，用户向上阅读时不被每个 delta 强制拉到底部；
- Typed Interaction Card 继续使用 Form 的计划、预检、批准、产物和恢复状态机，只调整到同一阅读列；
- 未接入完整合同的来源入口、Web、书签、长期记忆、技能和推理面板不展示。

验证结果：Assistant 全栈 91 passed，其中包含一个受闸门控制的真实 Worker 测试，证明首个 delta 在 Turn 完成和持久化前已经到达活动消息流。原生宽屏、流式生成中和紧凑窗口证据分别为 `assistant_active_conversation_native.png`、`assistant_active_conversation_streaming_native.png`、`assistant_active_conversation_compact_native.png`。详细根因、链路和边界见深度分析文档第 34 节。
