# Changelog

本文件记录 LDWord 的发布变更。每个条目先列出本阶段【已提交并可用】的功能，
再单独列出【仅局部实现 / 待续】的能力，便于判断当前 HEAD 能做什么、还差什么。

- 已提交 = 已合入 main、在当前源码可直接使用。
- 仅局部 / 待续 = 已铺好地基（接入、占位、接口、单测）但尚未形成可用闭环。

---

## 2026-09-07 · AI 共创·逐章成书 + 内嵌 MarkText + 长文档 DOCX 交付

> 版本基线：main @ e83113d（已推送 origin/main）。本文件在本阶段首建，
> 覆盖 2026-09-04 的 AI 分章起草以来的整段演进。更早的源码级链路说明见
> docs/AI长文档生成链路说明.md。

### 一、已提交并可用（merged → e83113d）

本阶段以 21cde54..e83113d 共 12 个提交入库，配合 2026-09-04/05 的
"按附件目录逐章写作"全链路，共同打通主流程：告诉 AI 做什么、生成目录、
左侧章节目录、右侧内嵌编辑器逐章流式写作（边写边排版）、封面/分篇/分页、
导出 DOCX。

#### 1. 章节目录与统一章节识别（识别引擎）
- 统一中文"章/篇/单元/部分/卷/节"等单位的识别约定，抽成 chapter_units 单一权威来源，
  供大纲解析、_parse_outline_blocks、能力提示、DOCX 分章四处共用，避免各写一套。
  - 提交 114e972（feat(chapter-units)）
- 左侧章节目录 dock：支持"篇>章"分组、折叠/展开、每章字数/状态显示，与重写大纲卡片一致。
  - 提交 4c1f901（feat(workbench)）；配套测试 tests/test_chapter_dock_part_groups.py

#### 2. 超长文档逐章编辑引擎与记忆
- chapter_cache 逐章缓存落盘；chapter_document_editor 长文按章切分编辑（不一次性塞整篇，
  支撑几百至上千页）；system_memory 系统记忆让后续改写不失忆（默认与章节缓存同置于
  workbench 会话目录，存放位置可在偏好中切换为项目目录）。
  - 提交 2c76dad（feat(chapter-editing)）
- 排版模板 typesetting_templates 与复核 typesetting_reconcile；用户可保存为模板、覆盖，
  或点击"恢复默认模板"还原（typesetting_template_dialog）。
  - 提交 2c76dad、4c1f901

#### 3. 内嵌 MarkText（Muya）编辑器 + 可编辑 Markdown 预览
- 右侧用 QWebEngine + QWebChannel 加载真正的 MarkText(Muya) 编辑器内核（非轻量替代），
  替代早期只读 Markdown 渲染；支持可编辑、撤销/重做策略、状态 toast、格式化/工具栏图标。
  - 提交 5eb631a（feat(marktext-editor)）；配套 tests/test_undo_policy.py、
    tests/test_marktext_drag_policy.py
- 图片拖入/粘贴自动落地并生成相对路径引用；非图片拖拽有"仅支持图片"反馈。
  - 提交 5eb631a
- 编辑器品牌色/状态色跟随 Qt 主题，左右工作台提示同源不漂移。
  - 提交 5eb631a

#### 4. Markdown → DOCX 结构化导出（含图、封面、分篇）
- markdown_docx_export 把章节、GFM 表格、列表、行内样式、标题语义导出为 DOCX；
  长文档按"篇>章"分节、自动编号前缀（第N篇·第M章）、封面页、页眉页脚/页码。
  - 提交 aabd7ae（feat(docx-export)）
- 图片经资源清单解析嵌入；支持图注编号、交叉引用、降采样/无损重压以控制体积。
  - 提交 aabd7ae、925490d；配套 tests/test_markdown_docx_part_export.py
- 导出前估算页数并预览；导出确认框展示目标路径/预估页数/封面字段，供核对。
  - 提交 aabd7ae

#### 5. 封面字段映射（场景化）
- 新增 cover_field_mapping：按文档场景把资料包"项目名→封面标题、公司名→副标题"做映射，
  无覆盖时回退文档首 H1 / 内建默认；封面日期默认今天且记住上次选择。
  - 提交 21cde54；配套 tests/test_cover_field_mapping.py、tests/test_export_cover_preview.py

#### 6. AI 图占位与图片内容哈希命名
- AI 无法直接表达图片时写"【图：说明】"占位，经 ImageGenerationService 落地为图片文件
  并改写成 Markdown 图片引用；图片以内容哈希命名去重（避免 _1/_2 后缀重复入库）。
  - 提交 925490d（feat(images)）
- 注意：真正的第三方文生图 API 目前只是占位（见"仅局部 / 待续"）。

#### 7. 偏好单一来源与设置面板扩展
- app_preferences 作为全局 QSettings 偏好单一来源（撤销策略、记忆目录、导出图片质量档等），
  设置面板双入口同步。
  - 提交 15cc3c9（feat(preferences)）

#### 8. 主面板 / 侧栏整合接线
- 把章节工作台、MarkText、封面映射、范本库、AI 助手等接进主面板与侧栏注册；
  面板/目的地在 panel_registry / panel_specs 单一来源中登记。
  - 提交 b65c56d（feat(ui-integration)）

#### 9. 测试与 CI
- 12 个新增回归测试文件（章节识别/拆分/单位、排版、撤销、封面映射、导出、MarkText 拖拽等）；
  无头跑通（QT_QPA_PLATFORM=offscreen），本地合计 192 项通过。
  - 提交 76a1a1b（test）
- .github/workflows/tests.yml：GitHub Actions 跨平台无头测试工作流。
  - 提交 e83113d（ci）

#### 10. 构建 / 依赖
- 新增 Pygments 依赖、Qt shim 导出扩充、NSIS 安装打包、app 图标、muya bundle 忽略规则。
  - 提交 aec705b（build）

### 二、仅局部实现 / 待续（已铺地基，尚未形成闭环）

| 能力 | 现状 | 缺口 / 下一步 |
| --- | --- | --- |
| 真正的第三方文生图 API | ImageGenerationService 是可插拔 provider 缝隙，但默认 NoopImageGenerationProvider 不产出图片——占位符原样保留，导出时作为"待补充"图槽提示 | 接一个具体文生图后端：把中文说明适配成该后端 prompt、申请 key、在设置页暴露图片模型/服务方，点生成才联网（用户已指明是下一步，本次只搭好接缝） |
| Muya bundle 分发包 | 源码库用 marktext-develop 的 build_muya.mjs 惰性重建（node v24 可用），产物 src/assistant/ui/web/muya.bundle.* 已生成但被 .gitignore 排除 | 冻结/安装发行版需预构建打进包（spec/build 流程加一步 node build_muya.mjs），否则最终用户环境若没有 node 会退化为降级视图 |
| PPT 模板生成与自动排版 | 仓库内尚无任何 PPT 模块 | 按用户路线图为"下一步"：PPT 模板如何生成、自动排版如何套用、PPT 文/图如何生成 |
| 图片自动/批量生成入文档 | 占位→落地链路就绪，但缺"真正生成图片"与批量图队列编排 | 依赖文生图 provider 就绪后，把 AI 生成"带图 markdown"的二进制也写进章节缓存并自动生成 resource_paths 供导出 |
| 右栏编辑器在冻结环境的降级体验 | 有降级分支，但未做端到端截图回归 | 在无 bundle / 无 node 环境验证降级视图的可用性与提示 |

### 三、版本基线备注

- 本阶段前（2026-09-04）的"按附件目录逐章写作"链路基线见 docs/AI长文档生成链路说明.md
  （基线 0f5e0a3），其"最小可行下一步"已在本阶段大部分落实（用户自带目录入口已在
  709f2c2 / 9335d18 就绪）。
- 冒烟验证：无头实例化主面板/导出器等关键路径均通过；导出器对含中文章节、GFM 表格、
  行内样式的 Markdown 产出可重新打开的 DOCX（章节标题、表格单元格等结构保留）。
- 工作区遗留：marktext-develop、LDWord_Setup.exe 及 _smoke_* / _test_* 等中间产物已加入
  .gitignore（该 .gitignore 改动尚未提交）。
