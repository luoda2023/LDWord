# N2.181 高层业务能力矩阵规划与审计记录

本文件用于把“场景能力矩阵不遗漏高频适用场景、边界不混淆”从讨论口径固化为可审计源。它不是新增一批可执行场景，而是定义业务能力层：每个高频能力必须能追到 pack/family、request-cell、真实 DOCX fixture、成功/降级/失败/人工门路径、输入资料、输出产物、OOXML 风险、控件一致性和边界声明。

## 吸纳资料

- `count_engine_tech_record`：吸纳为 CountProfile/CountEngine 原则。字数不是单一计数器，必须是 profile-driven multi-metric CountEngine，支持 Word-like、中文字符/汉字、英文 words、字符数、章节范围、参考文献/图表/公式等多口径，并通过 rule source/profile 决定采用口径。
- `exam_generator_tech_stack_record`：吸纳为 Exam/Teaching 场景原则。AI 只负责生成结构化内容，正式事实源应为 JSON，Markdown 是预览/人工检查层，Word 是输出层；学生版、教师版、答案版、解析版应由同一结构源和 DeliveryPreset/ContentVisibilityRule 生成。复杂几何图、AI 内容质量和专业题目正确性进入 plugin/manual gate。
- 公开 ChatGPT share 对话不作为 release gate 证据源。外部对话如果不能稳定读取，必须沉淀为仓库内 Markdown、registry 或测试，避免规划断链。

## 矩阵完整性标准

每个高层业务能力至少要回答以下问题：

| 维度 | 必须回答的问题 | 承载源 |
| --- | --- | --- |
| 高频入口 | 用户会如何自然表达？是否含 matched、ambiguous、manual boundary、negative？ | request-cell registry、task lexicon |
| 承载层 | 是顶层 pack、planned family、profile/schema/preset，还是 plugin/manual gate？ | coverage manifest、family registry |
| 事实源 | DOCX、Markdown、JSON、XLSX、附件包中哪个是机器事实源？ | InputSourceProfile、MaterialSchema |
| 旅程深度 | 是否覆盖成功/降级/失败/人工门；import 是否覆盖 handoff？ | user journey fixture audit |
| 真实 fixture | 是否有真实 DOCX fixture、OOXML surface、expected behavior、report expectation？ | sample fixture registry |
| 输出与报告 | 最终 DOCX、compare、report、intermediate、material package、artifact browser 是否可见？ | report/artifact drilldown |
| 控件一致性 | 场景控件命名、单位、分组、禁用态是否与模板管理一致？ | control runtime consistency |
| 边界 | 法律/财务/专利/医学/翻译质量、AI 内容质量、OCR/PDF/完整 LaTeX 是否留在 manual/plugin gate？ | plugin/manual boundary |

## 能力族划分

N2.181 当前将高频能力划为 17 个 business capability row：

| 能力组 | 能力行 | 承载 |
| --- | --- | --- |
| general_word_formatting | quick_word_formatting | `quick_formatting` |
| academic_and_submission | thesis_cn、journal_en | `chinese_academic`、`english_journal` |
| education_exam | exam_teaching | `exam_education` |
| application_and_business_reports | project_application、product_sales_documents | `application_reports` |
| contract_and_legal_boundary | contract_delivery | `contract_delivery` |
| batch_and_fixed_form | hr_batch_documents、form_batch_documents | `batch_forms` |
| official_archive | meeting_policy_documents | `official_policy` |
| technical_and_long_docs | long_document_publishing | `technical_long_docs` |
| bidding_and_qualification | qualification_archive_packages | `bidding_materials` |
| professional_manual_boundary | finance_quote_documents、ip_patent_documents、bilingual_translation_documents、regulated_disclosure_documents | `professional_disclosure` |
| import_ai_boundary | import_ai_assistance_boundary | `import_ai_boundary` |

## 边界策略

- `core_auto`：普通自动能力，必须仍有边界声明。
- `core_with_boundary_note`：核心可自动执行，但法律、真实性、投稿权威规则等必须报告边界。
- `core_with_manual_gate`：核心流程可执行，但某些子任务必须走人工确认，例如复杂图形、AI 题目质量。
- `professional_manual_gate`：专业判断型能力只做资料、格式、报告和边界提示，不承诺法律/财务/专利/医学/翻译质量判断。
- `import_handoff_boundary`：导入、OCR、PDF、AI 转换先进入人工确认/置信度报告，再 handoff 到目标 Word 场景。

## 当前审计基线

- business capabilities：17
- ready capabilities：17
- P1/P1_CANDIDATE：11
- P1/P1_CANDIDATE ready：11
- boundary capabilities：6
- manual-gate capabilities：11
- unique request cells：49
- unique DOCX fixtures：32
- missing journey groups：0
- absorbed external records：2
- blocking issues：0（完成 dashboard/drilldown/release gate 接线后）
- warnings：0

## 当前闭合解释

高层业务能力矩阵的 P0/P1/P1_CANDIDATE journey groups 已闭合，但这不等于所有场景都达到 Green/L5。以下条目是已进入 release gate 的第一片真实 fixture 证据：

- `quick_word_formatting` 已补 degraded 第一片：`quick_formatting_preserve_fields_degraded` 绑定 `quick_template_cleanup`，用字段/批注 OOXML surface 与 `preserve_layout` 表达快速清理遇到高风险 Word 对象时保留/警告而非盲改。
- `thesis_cn` 已补 degraded 第一片：`chinese_academic_rule_source_degraded` 绑定 `chinese_thesis_count`，用字段/批注/隐藏文本 OOXML surface 与 `skip_report + rule_source_governance` 表达学校规则不可确认、公式/引用置信度不足时的边界报告。
- `journal_en` 已补 degraded/manual 第一片：`english_journal_bibtex_csl_degraded` 绑定 `english_journal_submission_package`，用 `skip_report + citation_source_report` 表达 BibTeX/CSL 不完整；`english_journal_publisher_rule_manual_boundary` 绑定 `english_journal_response_letter`，经 `journal_publisher_rule_review_gate` 表达 publisher-final layout 与未审期刊规则边界。
- `exam_teaching` 已补 success/degraded/manual boundary 第一片：`exam_education_structured_multiversion` 覆盖答题卡/解析版的结构化源成功路径，`exam_education_controls_textboxes` 仅挂 `exam_multi_version`，用 `skip_report + manual_confirmation` 表达复杂图/AI 题目质量降级与人工门禁。
- `contract_delivery` 已补 degraded/manual 第一片：`contract_delivery_signature_fields_degraded` 绑定合同签署字段一致性和签署包字段请求，用 `skip_report + preserve_layout` 表达缺签章/字段不一致降级；`ambiguous_contract_legal_review` 让“合同法律审查签署包”同时命中合同交付和专业法律边界，并经 `professional_disclosure_review_gate` 暴露法律意见人工门。
- `hr_batch_documents` 与 `form_batch_documents` 已补 manual boundary 第一片：`batch_forms_hr_missing_fields_manual_boundary` 绑定 HR 批量证明/offer 缺字段，表达单条记录失败隔离和人工修复；`batch_forms_fixed_layout_placeholder_manual_boundary` 绑定固定版式证书套打，表达残留占位符、固定行高和版位不确定时的人工确认。
- `meeting_policy_documents` 已补 manual boundary 第一片：`official_policy_formal_archive_manual_boundary` 绑定正式通知/归档请求，用 `preserve_layout + manual_confirmation` 表达正式稿/内部稿、水印状态、编号保留和归档交付状态的人工确认边界。
- `long_document_publishing` 已补 manual boundary 第一片：`technical_long_docs_chapter_inventory_manual_boundary` 绑定技术 SOP 章节 inventory 请求，用字段、批注、嵌入包和 `manual_confirmation` 表达章节清单、交叉引用状态、归档包完整性必须交付前确认。
- `qualification_archive_packages` 已补 degraded/manual 第一片：`bidding_materials_missing_attachment_degraded` 绑定营业执照资质附件包请求，用 `skip_report + attachment_inventory + missing_items_report` 表达缺证照/营业执照/PDF 图片附件时降级为缺项清单；`bidding_materials_original_copy_manual_boundary` 绑定标书正副本盖章请求，用 `manual_confirmation + qualification_authenticity_boundary_report` 表达正副本状态、盖章状态、有效期元数据、资质真实性和资格有效性必须人工确认。
- `project_application` 与 `product_sales_documents` 已补 user journey 深度第一片：项目申报用 `application_reports_project_attachment_degraded` 与 `application_reports_project_budget_manual_boundary` 表达附件缺项/规则来源降级、预算附件和申报系统状态人工确认；产品售前用 `application_reports_product_asset_degraded` 与 `application_reports_product_version_manual_boundary` 表达产品图片/案例资产降级、客户/内部版本和销售主张人工确认。
- `professional_disclosure` 与 `import_ai_boundary` 已补 degraded 第一片：`professional_disclosure_source_quality_degraded` 表达表格、附件证据和专业来源不完整时先降级为来源质量报告；`import_ai_boundary_conversion_confidence_degraded` 表达 OCR/PDF/AI 转换置信度不足时先给 conversion confidence report 再 handoff。

## 控件样式一致性要求

场景配置中的控件样式控制必须与模板管理保持同一语言：

- 缩进、特殊缩进、行距、段前段后、固定行高等共享参数，不允许场景页另起命名或单位。
- 行高应归 fixed-layout profile，而不是普通 TableConfig 残留参数。
- 公式、输出、水印、资料 schema、plugin/manual gate 归场景运行时控件，但仍要复用 control contract 的命名、单位、禁用态和报告字段。
- 控件 UI 的同名字段必须能追到 runtime consumer、report field 和测试；否则只能停留在 planned/boundary，不得宣传为可执行能力。

## 后续落点

1. 当前不再有 business capability missing journey group，user journey fixture warning 也已清零；后续优先处理产品深度，而不是继续扩大顶层入口。
2. 继续把 exam_teaching 的结构化 JSON -> Markdown preview -> Word multi-version 从 fixture 证据推进到运行时执行链，并补题目 schema/UI 编辑闭环。
3. 给 thesis/journal/project/long-doc 补 CountProfile rule-source fixture，落实 profile-driven multi-metric CountEngine。
4. 将 project/product/professional/import 的第一片 fixture 证据继续推进到执行报告、修复入口、artifact drilldown 和可视化验收。
5. 将业务能力矩阵持续接入 dashboard、drilldown、release gate、summary projection 和文档总账。
