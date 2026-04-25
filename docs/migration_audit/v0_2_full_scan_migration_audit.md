# V0.2 Full-Scan Migration Audit

## 2026-04 Refresh

- `TemplateConfig` has regained feature-config hosting for `table / toc / caption / header_footer / reference_style / formula_* / output`, and `resolve_config()` now merges scene feature overrides into runtime config.
- `paragraph_style` now has a real unit-injection chain for `pt / cm / chars`, with OOXML sync helpers wired into runtime formatting.
- `reference_format` now maps `hanging_indent_cm` and spacing/font overrides into real paragraph + OOXML output instead of stopping at config.
- `heading_recognition` is no longer a thin heading-only heuristic. It now builds a richer `DocTree` with front/back matter candidates, order validation, explicit `body` insertion, TOC/reference fallbacks, and paragraph-to-section lookup suitable for downstream modules.
- `section_format` now consumes the richer `DocTree` and restores a conservative layer of logical section-boundary protection by inserting `nextPage` breaks before front/body/back matter boundaries and in-body chapter starts when safe.
- `toc` now includes existing-TOC formatting, suspicious-range fallback, TOC style sync, shared-style fallback, explicit thesis template role styles (`toc_title / toc_chapter / toc_level1 / toc_level2`), and a real `mode` split where `plain` rebuilds ordinary TOC paragraphs instead of silently falling back to native fields.
- `caption` now includes conservative missing-caption insertion for image/table anchors, schema-backed `auto_insert`, schema-backed `format_inserted` field/text routing, a fixed OOXML insertion path that reaches real `python-docx` paragraphs, and restored figure-caption continuation handling for immediate `(a)/(b)/(c)`-style subfigure lines.
- `citation_link` now exists in V1.0 as a real module again. Current recovery covers numbered reference-target bookmarks plus simple bracketed body citations (`[1]`, `[1,2]`, `[3-5]`) rewritten as REF fields in plain-text paragraphs.
- `whitespace_normalize` now exists in V1.0 as a real module again. Current recovery covers baseline space/tab/zero-width cleanup plus conservative full/half-width conversion, while skipping complex field/math/object paragraphs.
- `validation` exists in V1.0, but is still lightweight compared with 0.2.

## Current Priority Snapshot

- `doc_tree / section semantics`: partially restored, but still below 0.2's full confidence/recovery model.
- `section_format`: partially restored; logical boundary protection is back, but 0.2's full title-treatment, fallback recovery, and broader structure-repair strategy are still missing.
- `toc`: medium recovery; native/plain dual-path is back, but plain mode is still text-only (no page-number field strategy yet), and broader front/back matter rebuild coverage is still simplified compared with 0.2.
- `caption`: medium recovery; numbering/style/auto-insert, field/text dual-route control, and conservative continuation handling are back, but broader continuation semantics and finer field-preservation behavior are still simplified compared with 0.2.
- `citation_link`: minimally restored, but still below 0.2 in bookmark repair, EndNote/legacy field normalization, split-run citation repair, and richer reference-numbering recovery.
- `whitespace_normalize`: minimally restored, but still below 0.2 in richer context heuristics, partial-run fallback behavior, and broader paragraph-type exemptions.
- `formula_convert`, `formula_to_table`, `formula_style`: still materially unported.

## Scope

本次审计针对 `C:\Users\Administrator\Desktop\Lark-Formatter 1.0\lark-formatter V0.2 LTS\src` 做全量扫描。

产出分两层：

- 全量索引：[`v0_2_code_index.json`](./v0_2_code_index.json)
- 摘要索引：[`v0_2_code_index_summary.md`](./v0_2_code_index_summary.md)

索引记录了：

- 全部源码文件路径
- 行数
- 顶层类 / 函数
- 起止行号

这份文档在索引之上，额外整理：

- 0.2 的功能面
- 0.2 的隐性策略面
- V1.0 当前对位情况
- 后续迁移优先级

## Coverage Summary

- 已索引文件：82
- Python 文件：81
- 策略热点最高的文件：
  - `engine/rules/section_format.py`：4059 行
  - `engine/rules/table_format.py`：2413 行
  - `engine/rules/toc_format.py`：2104 行
  - `engine/rules/md_cleanup.py`：1989 行
  - `docx_io/style_clone.py`：1863 行
  - `engine/rules/formula_style.py`：1347 行
  - `engine/rules/citation_link.py`：1124 行
  - `engine/pipeline.py`：1164 行
  - `engine/doc_tree.py`：952 行
  - `engine/rules/caption_format.py`：876 行

## Module Surface Map

| 0.2 Rule / Layer | 0.2 Location | 0.2 Responsibility | V1.0 Counterpart | Current Status |
| --- | --- | --- | --- | --- |
| `page_setup` | `engine/rules/page_setup.py` | 页面尺寸、页边距、页眉页脚距离 | `modules/basic/page_setup.py` | 已迁移，待等价复核 |
| `style_manager` | `engine/rules/style_manager.py` | 样式定义级排版注入 | `modules/basic/paragraph_style.py` + `modules/basic/section_format.py` | 部分迁移 |
| `heading_detect` | `engine/rules/heading_detect.py` | 标题识别与保护策略 | `modules/structure/heading_recognition.py` | 明显弱化 |
| `heading_numbering` | `engine/rules/heading_numbering.py` | 标题编号应用 | `modules/structure/heading_numbering.py` | 已迁移，待等价复核 |
| `toc_format` | `engine/rules/toc_format.py` | 目录重建、格式化、守护与回退 | `modules/structure/toc.py` | 大量缺失 |
| `caption_format` | `engine/rules/caption_format.py` | 图表题注识别、插入、编号、格式化 | `modules/table/caption.py` | 部分迁移 |
| `table_format` | `engine/rules/table_format.py` | 表格宽度、边框、行距、三线表、语义保护 | `modules/table/table_format.py` | 已迁移，待等价复核 |
| `section_format` | `engine/rules/section_format.py` | 分区级样式应用、范围保护、结构修正 | `modules/basic/section_format.py` | 高风险弱化 |
| `header_footer` | `engine/rules/header_footer.py` | 页眉页脚内容 + 段落/字体格式 | `modules/basic/header_footer.py` | 能力缩窄 |
| `reference_format` | 0.2 由 `section_format/style_manager` 等链路承担 + scene 样式 | 参考文献段落排版 | `modules/special/reference_format.py` | 已补到部分等价 |
| `whitespace_normalize` | `engine/rules/whitespace_normalize.py` | 空白与全半角策略 | 无等价模块 | 未迁移 |
| `citation_link` | `engine/rules/citation_link.py` | 文内引文与文后条目链接 | 无等价模块 | 未迁移 |
| `formula_convert` | `engine/rules/formula_convert.py` | 公式转换主链 | 无等价模块 | 未迁移 |
| `formula_to_table` | `engine/rules/formula_to_table.py` | 公式转表格 | 无等价模块 | 未迁移 |
| `formula_style` | `engine/rules/formula_style.py` | 公式样式统一 | 无等价模块 | 未迁移 |
| `equation_table_format` | `engine/rules/equation_table_format.py` | 公式表格编号与格式 | `modules/special/equation_table_format.py` | 已迁移，待等价复核 |
| `validation` | `engine/validation.py` | 严格模式最终校验 | 无等价模块 | 未迁移 |

## Strategy Hotspots

### 1. Document Structure Tree / Logical Section Inference

关键文件：

- `engine/doc_tree.py`

关键代码段：

- `_score_paragraph()`：`engine/doc_tree.py:212`
  - 多信号加权识别分区标题，而不是只靠标题文字。
- `DocTree.build()`：`engine/doc_tree.py:315`
  - 扫描全篇，构建逻辑分区。
- `_detect_toc_by_style()`：`engine/doc_tree.py:445`
  - 基于 `TOC 1/2/3` 等样式反推目录区。
- `_detect_references_by_content()`：`engine/doc_tree.py:752`
  - 在没有“参考文献”标题时，通过连续条目内容兜底识别 references。
- `get_section()` / `get_section_for_paragraph()`：`engine/doc_tree.py:938`、`engine/doc_tree.py:944`

策略价值：

- 把“正文 / 目录 / 摘要 / 参考文献 / 附录 / 致谢 / 简历”切成逻辑区块。
- 为后续 `heading_detect / toc_format / section_format / validation` 提供统一语义底座。
- 带有顺序校验、置信度阈值、内容兜底、纠偏逻辑。

V1.0 对位：

- `modules/structure/heading_recognition.py:71`
- `modules/structure/heading_recognition.py:86`

判断：

- V1.0 当前只有轻量 `DocTree + section_ranges`，与 0.2 的多信号加权分区树不等价。
- 这是后续迁移的 P0 基础设施。

### 2. Heading Detection Guards

关键文件：

- `engine/rules/heading_detect.py`

关键代码段：

- `_looks_like_tabular_numeric_line()`：`engine/rules/heading_detect.py:123-145`
- `_looks_like_tabular_structured_line()`：`engine/rules/heading_detect.py:148-196`
- `_looks_like_broken_toc_entry_line()`：`engine/rules/heading_detect.py:199-207`
- `_looks_like_chapter_outline_sentence()`：`engine/rules/heading_detect.py:210-235`
- `_detect_by_outline()`：`engine/rules/heading_detect.py:286-296`
- `_heading_confidence_score()`：`engine/rules/heading_detect.py:309-516`
- `HeadingDetectRule.apply()`：`engine/rules/heading_detect.py:518-645`

策略价值：

- 避免把表格行、目录条目、书签报错行、章节说明性句子误识别为标题。
- 允许样式、outline level、编号模式、视觉特征混合判定。
- 对“非编号后置标题”“front matter 标题”有专门白名单。

V1.0 对位：

- `_detect_heading()`：`modules/structure/heading_recognition.py:146`
- `_build_section_ranges()`：`modules/structure/heading_recognition.py:198`

判断：

- V1.0 标题识别明显更薄，当前最大问题不是“识别不到”，而是“缺保护策略，容易误识别”。

### 3. TOC Rebuild / Guard / Fallback

关键文件：

- `engine/rules/toc_format.py`

关键代码段：

- `_native_toc_field_instruction()`：`engine/rules/toc_format.py:73-108`
- `_fallback_collect_headings()`：`engine/rules/toc_format.py:288-331`
- `_build_front_matter_toc_entries()`：`engine/rules/toc_format.py:477-522`
- `_build_back_matter_toc_entries()`：`engine/rules/toc_format.py:525-607`
- `_format_toc_para()`：`engine/rules/toc_format.py:956-1017`
- `_normalize_toc_heading_style()`：`engine/rules/toc_format.py:1183-1201`
- `TocFormatRule.apply()`：`engine/rules/toc_format.py:1373-1610`
- `_fallback_toc_section()`：`engine/rules/toc_format.py:2001-2057`
- `_format_existing_toc_paras()`：`engine/rules/toc_format.py:2060-2103`

策略价值：

- 不只是插入 TOC 域，还负责：
  - 目录标题样式修正
  - 目录条目格式化
  - 前置分区 / 后置分区目录项补建
  - heading 检测失效时的 fallback
  - TOC 区间可疑性判断
  - rebuild coverage guard，避免破坏已有目录

V1.0 对位：

- `modules/structure/toc.py:32`
- `_find_insert_position()`：`modules/structure/toc.py:110`
- `_insert_toc()`：`modules/structure/toc.py:141`

判断：

- V1.0 当前只迁了“TOC 域生成/更新”这一小层，0.2 的目录内容识别、守护、格式化几乎没回来。
- 这是 P0/P1 级缺口，不应继续被视为“已完成”。

### 4. Caption Numbering / Caption Paragraph Strategy

关键文件：

- `engine/rules/caption_format.py`

关键代码段：

- `_parse_caption_numbering_format()`：`engine/rules/caption_format.py:347`
- `_format_caption_para()`：`engine/rules/caption_format.py:542`
- `_insert_caption_para()`：`engine/rules/caption_format.py:586`
- `CaptionFormatRule.apply()`：`engine/rules/caption_format.py:635`

策略价值：

- 支持 `chapter.seq / chapter-seq / chapter:seq / ...` 这类编号格式
- 图题注 / 表题注独立样式
- 已有题注重建
- 无题注时插入
- 域代码编号与纯文本编号双模式
- 图注续行处理

V1.0 对位：

- `modules/table/caption.py:67`
- `_resolve_caption_style()`：`modules/table/caption.py:147`
- `_apply_caption_style()`：`modules/table/caption.py:165`
- `_scan_captions()`：`modules/table/caption.py:203`

判断：

- 目前只补回了“题注段落样式”和一部分样式继承。
- 0.2 的高级编号语义、插入语义、续行语义还没迁回来。

### 5. Section-Level Formatting / Boundary Protection

关键文件：

- `engine/rules/section_format.py`

关键代码段：

- 文件级入口：`engine/rules/section_format.py`（4059 行）
- 结构与格式耦合较深，是 0.2 的核心总控之一。

策略价值：

- 分区级样式应用
- cover / body / references / abstract / appendix 等边界保护
- 结构调整后的索引修正
- 与 `doc_tree`、`heading_detect`、`caption_format`、`toc_format` 强耦合

V1.0 对位：

- `modules/basic/section_format.py`

判断：

- 当前必须视为“高风险弱化”，不能仅按文件名判断为已迁移。

### 6. Table Heuristics / Semantic Preservation

关键文件：

- `engine/rules/table_format.py`

关键代码段：

- 文件级入口：`engine/rules/table_format.py`（2413 行）
- 与题注识别、公式表格、页面宽度、边框、表头重建强相关。

策略价值：

- 不只是格式化表格，更包含：
  - 公式表格识别
  - 题注文本识别保护
  - 表格宽度估算
  - 三线表语义保护
  - 结构异常修正

V1.0 对位：

- `modules/table/table_format.py`

判断：

- 名义上已迁，但必须做策略级复核，不能只看结果样式。

### 7. Citation Link Strategy

关键文件：

- `engine/rules/citation_link.py`

关键代码段：

- 条目编号提取：`engine/rules/citation_link.py:58-152`
- `CitationLinkRule.apply()`：`engine/rules/citation_link.py:971-1123`

策略价值：

- 文内引文与参考文献条目双向链接
- 编号规范化
- 书签名生成、去重、匹配保护

V1.0 对位：

- 当前无等价模块

判断：

- 完整缺失，后续必须单独立项。

### 8. Formula Pipeline and Fallback

关键文件：

- `engine/rules/formula_convert.py`
- `engine/rules/formula_to_table.py`
- `engine/rules/formula_style.py`
- `docx_io/mathtype_office_fallback.py`

关键代码段：

- `FormulaConvertRule.apply()`：`engine/rules/formula_convert.py:248-547`
- `FormulaStyleRule.apply()`：`engine/rules/formula_style.py:1000-1346`
- `docx_io/mathtype_office_fallback.py`
- `engine/pipeline.py` 内的 fallback 调度

策略价值：

- 不可信转换保护
- 公式来源清洗
- Office/MathType 兜底
- 公式表格样式统一

V1.0 对位：

- 当前只有 `equation_table_format`

判断：

- 公式处理链整体未迁。

### 9. OOXML Fidelity / Clone / Repair

关键文件：

- `docx_io/style_clone.py`
- `utils/indent.py`
- `utils/line_spacing.py`
- `utils/ooxml.py`
- `docx_io/field_refresh.py`
- `docx_io/sanitize.py`
- `engine/page_scope.py`

关键代码段：

- `_read_xml_indent_info()`：`docx_io/style_clone.py:221-314`
- `_read_xml_spacing_info()`：`docx_io/style_clone.py:324-375`
- `_build_style_config()`：`docx_io/style_clone.py:378-552`
- `_build_style_config_from_paragraph()`：`docx_io/style_clone.py:569-678`
- `config_indent_value_to_pt()`：`utils/indent.py:53-61`
- `resolve_style_config_indents()`：`utils/indent.py:170-238`
- `sync_indent_ooxml()`：`utils/indent.py:276-359`
- `apply_style_config_indents()`：`utils/indent.py:362-389`
- `normalize_line_spacing()`：`utils/line_spacing.py:16-40`
- `sync_spacing_ooxml()`：`utils/line_spacing.py:102-131`
- `refresh_doc_fields_with_word()`：`docx_io/field_refresh.py:311-355`
- `sanitize_docx()`：`docx_io/sanitize.py:21-60`
- `page_ranges_to_paragraph_ranges()`：`engine/page_scope.py:589-638`

策略价值：

- 这层不是业务模块，但决定：
  - 单位语义是否保真
  - 样式 round-trip 是否可靠
  - 域刷新/目录/页码是否稳定
  - 脏文档是否能先自救
  - 按页范围执行是否准确

V1.0 对位：

- 目前只在正文链补回了 `indent_ops / line_spacing_ops`
- 其他 OOXML fidelity 能力未系统回归

判断：

- 这是“迁移底座”，不是可选项。

## Current V1.0 Reality Check

V1.0 当前已经接近 0.2 的部分：

- `paragraph_style` 的单位真实注入链
- `reference_format` 的样式 + 规则覆盖
- `caption` 的题注段落格式层

V1.0 当前明显不足的部分：

- `DocTree` 分区识别策略
- `heading_detect` 保护策略
- `toc_format` 的目录内容识别、守护、格式化
- `caption_format` 的高级编号语义与插入语义
- `citation_link`
- `whitespace_normalize`
- `formula_convert / formula_to_table / formula_style`
- `validation`

## Migration Waves

### Wave 0: Inventory / Strategy Audit

先完成 0.2 全量索引与策略台账。

状态：

- 已完成索引
- 本文档为第一版策略审计

### Wave 1: Strategy Foundation

优先迁：

- `doc_tree`
- `heading_detect`
- 目录 / 题注 / 正文分区共同依赖的 guard / fallback 逻辑

理由：

- 如果这一层不迁，后续模块即使“功能名”回来了，稳定性也回不去。

### Wave 2: TOC Full Recovery

目标：

- 从当前 `toc` 的“插域”恢复到接近 0.2 的“目录格式与保护系统”

应至少包含：

- 目录区 fallback
- rebuild guard
- existing TOC normalize
- TOC 标题样式定义同步
- TOC 条目样式定义同步

### Wave 3: Caption Full Recovery

目标：

- 从当前“编号 + 样式”恢复到接近 0.2 的题注系统

应至少包含：

- `figure_prefix / table_prefix / separator / numbering_format`
- 已有题注重建
- 无题注插入
- 图注续行策略
- 是否保留 field/text 双路线的设计决策

### Wave 4: Missing Rules

补齐当前 V1.0 还不存在的 0.2 能力：

- `citation_link`
- `whitespace_normalize`
- `formula_convert`
- `formula_to_table`
- `formula_style`
- `validation`

## Working Rule For Future Migration

后续迁移必须按两张清单推进：

1. 功能清单
2. 策略清单

禁止只按 UI 或模块名判断“已迁移”。

判断标准必须至少包含：

- 配置字段是否真正生效
- 识别策略是否等价
- 守护 / fallback / coverage 逻辑是否等价
- OOXML 写入语义是否等价
- 结构调整后索引修正是否等价

## Next Recommended Step

建议下一步不是继续盲补单个 UI，而是正式启动：

- `Wave 1: DocTree + HeadingDetect` 策略迁移

原因：

- `toc / caption / section_format / reference / validation` 都依赖这一层
- 这一步不完成，后面的“功能移植”会持续建立在不稳定识别之上
