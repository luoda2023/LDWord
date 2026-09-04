# LDWord AI 长文档生成的完整链路（源码级）

> 版本基线：main @ 0f5e0a3（2026-09-04）。本文回答三个问题：
> ① 左侧“第一步/第二步”是什么、每一步是否必须走完；② AI 生成文本和排版到底怎么衔接；
> ③ 你要的“几百~上千页、严格按你自己的目录、不重复”的大书/大报告，应该加在哪里、怎么加。

---

## 一、两条工作流（先记住这个总图）

```
┌─ 工作流①：排版装配（本地、确定性的“套版”链路）───────────────┐
│  顶栏 TitleBar 选“工作模式”(work_mode.py) → 决定左侧可见面板     │
│  ①方案(规则/阶段) ②模板(版式) ③资料包(素材) → ④工作台(排版交付)   │
│  输入 docx/doc/wps → 本地预检 → 确认 → 生成 Word                  │
└──────────────────────────────────────────────────────────────┘
        ▲ 产出“已排好版的成品 docx”（最终交付物）

┌─ 工作流②：AI 创作（云端大模型写正文）───────────────────────────┐
│  左侧②AI创作 → 聊天框输入需求 → 生成“计划卡片”                    │
│  → 点[生成并校验内容] → 分章调用 AI → 编译出“草稿 docx”           │
│  →（可选）把草稿交给工作流① 再排版 = 最终成品                     │
└──────────────────────────────────────────────────────────────┘
        ▲ 产出“AI 写的正文草稿 docx”（还需①来套版式）
```

- 两条工作流可以**独立**用，也可以**串起来**（AI 先写草稿，再回工作台排版）。
- 左侧“①排版装配 / ②AI创作”是**两条主线**，不是每步都必须走完；只有你当前走的那条线的步骤要闭环。

---

## 二、工作流②（AI 长文）一步一步到底发生什么 —— 源码链路

### 第 1 步：输入与建会话
用户在聊天框输入 → `assistant_panel.py` 收到 → `turn_flow_mixin._send_message()`
→ 无会话时 `session_coordinator.create_session()`（默认带当前选中的模型）→ 消息入 `AssistantSession`。

### 第 2 步：判断“走本地排版 还是 走 AI 起草”
`turn_flow_mixin._submit_message()` → `evaluate_request_policy(请求文本, 当前工作模式, 有没有附件)`
- 命中“排版/处理文档”类需求 → 走**本地确定性链路**（见工作流①）；
- 命中“起草/生成/写”类需求 → 产生一个**文档计划(DocumentPlan)**（`_create_local_form_plan`），
  计划里带 `generation_required=True` 与对应的 `prompt_profile_id`。

### 第 3 步：计划卡片（你看到的“配置卡片”）
`document_workflow_mixin._plan_message()` 把 `DocumentPlan` 呈现成一张卡。
计划本身**没有正文**——正文要 AI 生成。这就是为什么“必须先点【生成并校验内容】”。

### 第 4 步：点【生成并校验内容】→ 真正调 AI
`document_workflow_mixin._start_content_generation()`：
1. 若 plan 的模式/文种决定走**工程大纲**（`prompt_profile_id == ENGINEERING_PROMPT_PROFILE_ID`），
   则 `_resolve_engineering_request_outline(...)` 调
   `engineering_stage_library.resolve_engineering_guide(你的意图文本)` ——
   **按自然语言关键词去匹配**内置 6 阶段库里某一篇文种，返回：
   `(stage_id, 文种, 章标题们, 每章要点们)`。
2. 组装 `ContentGenerationRequest(..., outline_titles=章标题们, outline_notes=每章要点们, ...)`
   （字段在 `content_generation_service.py` 的 `ContentGenerationRequest` 里）。
3. 真正干活的是 `content_generation_service._generate_engineering_sections()`：
   - 逐章 `for index, title in enumerate(titles)`：
     - 把「全篇大纲 + 本章标题 + 本章要点 + 前文记忆摘要(刚加的防重复)」拼成提示词；
     - 单独一次模型调用只写**这一章**；
     - 结果按章收进 `chapter_markdowns`。
   - 全部章写完 → `adapter.compile_generated(...)`：
     - 把整篇 Markdown 编译成 `draft_id.md`；
     - 再 `compile_content_material` → 合成 `draft_id.composed.docx`（**AI 草稿 docx**）。

### 第 5 步：草稿发布与排版
`_on_content_generation_finished()` → 草稿作为“已生成文档产物”呈现。
若要套版式 → 用工作流①把这份 docx 再走一遍排版；或直接交付。

---

## 三、关键结论：为什么“几百上千页、按我自己的目录”现在做不到

逐条对照你的目标：

| 你的要求 | 现状 | 卡点 |
|---|---|---|
| 几百~上千页长文 | 一次性点生成后逐章调用，无“续写/断点/分卷” | 单次生成跑完即止，无法中途续、跨天续 |
| **严格按我给的目录** | 大纲只能来自内置库里**关键词匹配**的那一篇 | `outline_titles` 字段已支持，但入口写死成 `resolve_engineering_guide(意图)`，**没有“用户自带目录→解析成 titles”的入口** |
| 不重复（几十章间不串内容） | 我刚加了“前文记忆摘要”拼进每章 | 只防“相邻章节重复”，几十章长文上下文仍可能漂移 |
| 一个对话里“聊→生成→排版” | 拆成两套机制 | 需要用户在界面里切换，尚无不中断的一键链路 |

**最小可行下一步（按优先级）：**
1. **支持用户自带目录**（核心）：识别意图中的“第一章…第二章…”或附带 .txt/.md 大纲附件，
   解析成 `outline_titles / outline_notes`，直接喂给已就绪的 `ContentGenerationRequest`；
   命中内置库时仍用内置库，两不冲突。
2. **长文续写/断点**：按 `chapter_index` 落盘，生成中断后可从下一章续跑（复用已存在的 session/draft 持久化）。
3. **更强防重复**：把“已写全文”或“各章摘要索引”注入每章，替换现在的 220 字摘要。
4. 界面侧：在“AI创作”里加一个“长文档/按目录写”的入口与进度，避免在聊天里硬塞超长需求。

> 说明：功能 2~4 依赖功能 1 才有意义；而功能 1 在现在代码里改动面很小
> （`document_workflow_mixin._resolve_engineering_request_outline` 一处解析入口即可）。
