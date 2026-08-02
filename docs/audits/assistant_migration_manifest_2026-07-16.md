# AI 文档助手迁移来源清单

> 日期：2026-07-16  
> 目标仓库：Alavette Form  
> 用途：记录 Alavette Design 体验参考与 Alavette Flow 源码派生范围，确保迁移可审计、可打包、无本机目录依赖。

## 1. 来源基线

| 来源 | 本地参考目录 | Git 基线 | 使用方式 |
|---|---|---|---|
| Alavette Design | `<LOCAL_PATH>` | `cb51361710c3edd853144c310b3f7636e9833df1` | 迁移 ConversationPanel / SessionSidebar 的信息架构、控件层级、布局比例与交互合同；以 Form 类型和状态源重写，未逐行复制源码 |
| Alavette Flow | `<LOCAL_PATH>` | `80560581b54f0817ab05f1efa3536253477cc755` | 在 MIT 许可下裁剪、改名并重构中立运行时基础 |

迁移时 Alavette Flow 工作区存在未提交变更，因此下表同时记录实际读取文件的 SHA-256。Git 基线用于标识仓库历史位置，文件哈希用于标识本次实际参考快照。

## 2. Design 源界面到 Form 目标界面

| Design 实际参考文件 | 参考快照 SHA-256 | Form 目标文件 | 迁移方式 |
|---|---|---|---|
| `alavette_host/desktop_qt/conversation/session_sidebar.py` | `2e447dd848a3207e42a96575e11ef263f57d52d15583f19c87b1c3c64839d1ee` | `src/assistant/ui/session_sidebar.py` | 只迁移已闭环的对话、新任务、置顶和最近任务结构；委托、项目、计划、长期记忆、技能中心因 Form 无完整领域链路而删除；会话操作改接 Form Coordinator |
| `alavette_host/desktop_qt/conversation/conversation_panel.py` | `800330950e2597f867c4317c2eed55ef03aa9942550a4c013c01b1f8489b85e2` | `src/assistant/ui/assistant_panel.py` | 迁移“会话侧栏 + 中央 Stack”组合关系；以 `first_level` 与 `embedded` 两种互斥宿主表达 |
| `alavette_host/desktop_qt/conversation/new_task_view.py` | `6ddf5140d5e1116cb323348d49695fca3d1372594bb7fe76be2e524225aab72b` | `src/assistant/ui/creative_home.py` | 迁移空态创作入口、Hero Composer、快速开始与固定任务视窗；按原体验合同重写透视网格、固定环境面片、动态面片和可见性生命周期；补充 Form 的 Provider readiness、DOCX 前置条件、发送门控和自定义任务 CRUD |
| `alavette_host/desktop_qt/conversation/task_workspace.py` | `82b3035173fb0bd4e42748c22f44f5bb3ed0daf5b90b0ffd39f78c324a880673` | `src/assistant/ui/assistant_panel.py`、`interaction_card.py` | 迁移活动会话的消息/交互卡语义；保留 Form 计划、预检、批准和生产状态机 |

Design 原代码依赖 `alavette_flow.app.ai`、ProjectOps、长期记忆、技能中心、主题和菜单合同。目标实现没有运行时导入该仓库，也没有复制其任务存储；这是可审计的语义适配迁移，不是把整个 Design 包嵌入 Form。

## 3. Flow 源文件到 Form 目标文件

| Flow 实际参考文件 | 参考快照 SHA-256 | Form 目标文件 | 主要修改 |
|---|---|---|---|
| `alavette_flow/app/assistant_kernel/messages.py` | `f89ccecb3ad536f8f5a2c73ed19a8f751f699c66d66175a1d2d36b2777046437` | `src/assistant/contracts/messages.py` | 移除 Flow 产品语义；改为 Form 版本化纯数据合同；强化序列化校验 |
| `alavette_flow/app/assistant_kernel/cancellation.py` | `9639bb0c4ddfedacead7bcfce1233e0d3aaf31f0254d5f2be1b60b35f9f7aff2` | `src/assistant/runtime/cancellation.py` | 保留线程安全取消核心；改名并缩小公开接口 |
| `alavette_flow/app/assistant_kernel/events.py` | `ccc8e0b70a25d61b5cf1148019753ea358b175469c16d88e98026afb29c45eae` | `src/assistant/runtime/events.py` | 仅保留 Form 助手需要的公开流式事件；移除 Flow 专属事件 |
| `alavette_platform/providers/generation_adapters/openai_provider.py`、Provider runtime stream/cancellation 设计 | 以 Git 基线和本清单日期为准 | `src/assistant/runtime/providers/openai_compatible.py` | 使用 Python 标准库重写为依赖轻量的 Chat Completions SSE 适配器；增加输出前有界重试、取消、超时和错误归类；不引入 OpenAI SDK |

其余 `src/assistant/` 代码为面向 Alavette Form 边界的新实现，包括 `DocumentPlan`、`DisclosureGrant`、`ExecutionApproval`、Tool Gateway、Form 生产适配、DocumentFragment 内容生成、执行日志和恢复。

## 4. 许可与分发

- Alavette Flow 采用 MIT License；原始版权与许可全文位于 `licenses/static/alavette-flow/LICENSE`。
- `THIRD_PARTY_NOTICES.md` 和 `licenses/manifest.json` 已登记派生模块。
- 打包产物不得读取或依赖上述两个桌面参考目录。
- 源码注释只标记实际派生的文件，不把 Design 的视觉原则误标为源码复制。

## 5. 边界结论

- Design 只影响体验合同，不拥有 Form 产品事实。
- Flow 只提供中立会话/Provider 基础，不直接访问 Form 服务层。
- Form 的场景、模板、资料、预检、DocumentFragment 和生产执行仍由现有 Form 模块拥有。

## 6. 迁移后完整性加固（2026-07-16 第三轮）

本轮没有扩大 Design 或 Flow 的源码派生范围，只对已迁入 Form 的交互与 Provider 边界进行一致性加固：

| 加固项 | Form 目标文件 | 迁移边界 |
|---|---|---|
| 模型状态与设置入口 | `src/assistant/ui/creative_home.py`、`assistant_panel.py` | 遵循 Design 的信息层级，状态源仍是 Form Profile/Router |
| 设置页直达意图 | `src/ui/bridge.py`、`preferences_panel.py` | 新增 Form 内部导航合同，不导入 Design 路由系统 |
| 连接状态持久化 | `src/assistant/runtime/providers/profiles.py` | 扩展 Form Profile，不复制 Flow 的产品 Profile |
| 恢复与重试 | `src/assistant/ui/assistant_panel.py` | 沿用 Form Session/Message 合同，不引入 Flow 任务编排 |
| 真实 HTTP 回环验证 | `tests/test_assistant_providers.py` | 验证已迁入的 OpenAI-compatible SSE 边界，不声明新 Provider 类型 |

因此许可结论不变：Design 仍仅作体验参考，Flow 的 MIT 派生仍仅限已登记的中立运行时部分，本轮无新的上游文件或许可条目。

## 7. 活动对话工作区纠偏（2026-07-17）

此前清单只把 `task_workspace.py` 概括映射到 Panel 与 Interaction Card，不足以表达真实活动对话迁移。本轮补充实际参考范围：

| Design 实际参考文件 | Form 目标文件 | 使用方式 |
|---|---|---|
| `conversation/task_header.py` | `src/assistant/ui/assistant_panel.py` | 参考 56px 任务头、任务身份与更多操作层级；以 Form Session 菜单重写 |
| `conversation/task_composer.py` | `src/assistant/ui/creative_home.py` | 参考 154px Compact Composer 几何和运行中发送/停止语义；复用 Form Provider 与 Bridge 状态 |
| `conversation/task_message_stream.py` | `src/assistant/ui/assistant_panel.py`、`conversation_view.py` | 参考阅读列、滚动跟随和跳到最新合同；以 Qt Widget 重写 |
| `conversation/message_item_widgets.py`、`message_render_types.py` | `src/assistant/ui/conversation_view.py` | 参考用户/AI 非对称呈现、860/820/640 宽度和无头像 AI 回复；不复制 Delegate 或 Flow 对象 |

底层流式投影继续使用已登记的 Flow `events.py` 派生合同；本轮只是把现有 `AssistantTurnWorker.event_received` 接到 UI，没有新增 Flow 源码派生。活动页静态背景、响应式宽度、Markdown 控件和视觉证据脚本均为 Form 新实现，因此许可范围不扩大。
