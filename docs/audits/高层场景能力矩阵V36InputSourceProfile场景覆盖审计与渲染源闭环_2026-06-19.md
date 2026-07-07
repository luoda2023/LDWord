# 高层场景能力矩阵 V36 InputSourceProfile 场景覆盖审计与渲染源闭环
日期：2026-06-19

## 1. 文档定位

V36 对应 N2.171，目标是把 V35 的第三个能力槽位 `InputFactSource` 正式落成可审计、可导出、可进入 dashboard/drilldown/release gate 的一等维度。

这一轮不新增顶层场景入口，也不把 PDF/OCR、完整 LaTeX 工程、AI 生成、复杂图形生成冒充为核心能力。它解决的是一个更基础的问题：

```text
每个高频场景到底接受什么输入，什么输入是结构化事实源，
哪些输入只能作为人工/插件/导入边界，最终又由哪些模板、资料包或中间产物参与渲染。
```

如果这条链路缺失，场景矩阵会出现三类高频误判：

1. UI 显示能处理某个场景，但执行层不知道材料从哪里来。
2. 执行层可以生成 Word，但报告无法解释输入事实源、结构化来源和渲染来源。
3. PDF/OCR、LaTeX、AI、复杂图形等边界输入被误看成核心 Word 自动化能力。

## 2. 参考输入和取证边界

本轮吸收以下本地事实源：

- `src/config/scene.py` 中的 `InputSourceProfile`、`DeliveryPreset`、`SceneWorkspace`。
- `src/config/scene_family_registry.py` 中 planned family 的 `input_formats`、`material_schema_ids`、markdown/latex policy。
- `src/config/scene_family_application.py` 中 family defaults 对 `SceneWorkspace.input_source_profile` 的落地。
- `src/ui/panels/workbench/scene_presets.py` 中前端预设输入 profile。
- `src/ui/panels/workbench/execution_runtime.py` 中执行前 input preflight。
- `src/config/material_schema_registry.py` 中结构化资料 schema。
- `src/config/scene_delivery_preset_audit.py` 中 delivery/rendering target。
- `src/config/scene_import_handoff_audit.py` 中 PDF/OCR、LaTeX、AI 导入边界。
- `src/config/plugin_manual_gate.py` 中人工/插件门。
- V29-V35 规划文档、Count Engine 技术记录、试卷生成技术记录。

外部 ChatGPT share 链接当前只稳定暴露登录壳页，正文没有可直接取证内容。本轮仅把它作为方向提示：Word 自动生成必须区分结构化输入、模板渲染、后处理、对象安全和交付链路，不把不可见正文当作事实依据。

## 3. V36 的核心定义

### 3.1 输入来源不是文件扩展名

`InputSourceProfile` 不是简单的上传格式白名单。它需要回答：

| 问题 | 应落到的字段或审计视角 |
| --- | --- |
| 用户可以交什么输入 | `accepted_formats` |
| 哪些输入是机器事实源 | `structured_formats`、`material_schema_ids` |
| Markdown 是事实源还是预览源 | `markdown_policy` |
| LaTeX 是公式片段还是完整工程边界 | `latex_policy`、`high_risk_imports` |
| 资料不满足时是 warning 还是 blocking | `failure_policy` |
| 输入最终由哪些产物参与渲染 | `delivery_preset_ids`、`render_source_ids`、`target_template_ids` |
| 哪些输入只允许插件/人工/导入 handoff | `boundary_input_source_ids`、`plugin/manual gate` |

### 3.2 渲染来源必须与输入来源相连

V36 将 render source 显式化为：

- `template:<id>`：目标模板或兼容模板。
- `final_docx`：最终 Word 交付物。
- `compare_docx`：审阅、差异、签署、修订类交付物。
- `structured_intermediate`：JSON/Markdown/AST/题库等中间结构。
- `material_manifest`：字段、附件、图片、签章、人员、项目等资料清单。
- `material_package`：交付包或归档包中的资料实体。

这使场景矩阵可以检查“输入源是否能一路走到输出源”，而不是只检查 pack/family 是否存在。

### 3.3 边界输入必须明确用户承诺

V36 固定四类高风险输入为边界输入：

| 边界输入 | 当前归属 | 核心结论 |
| --- | --- | --- |
| `pdf_ocr_import` | `import_ai_boundary` + handoff | 需要置信度、人工确认和目标场景 handoff，不承诺无损转换 |
| `full_latex_project` | `import_ai_boundary` + handoff | 公式片段可以治理，完整工程不当作普通样式处理 |
| `ai_content_generation` | `import_ai_boundary` 或领域插件 | 核心可接收结构化结果，不承诺事实/质量责任 |
| `complex_diagram_generation` | 插件或图片资产 | 核心支持图片占位/替换/尺寸，不承诺自动制图 |

## 4. 高频场景输入能力矩阵

| 场景包 | 主要 family | 核心输入 | 结构化事实源 | 边界输入 | 渲染源判断 |
| --- | --- | --- | --- | --- | --- |
| `quick_formatting` | 无固定 family | DOCX、Markdown | JSON 中间描述 | 无 | 模板、最终 DOCX、对比 DOCX、结构化中间产物 |
| `chinese_academic` | `thesis_cn` | DOCX、Markdown、JSON | JSON | 无 | 论文模板、最终 DOCX、对比 DOCX、结构化中间产物 |
| `english_journal` | `journal_en` | DOCX、Markdown、BibTeX、CSL JSON | BibTeX、CSL JSON、JSON | 无 | 最终 DOCX、对比 DOCX、结构化中间产物、资料包 |
| `exam_education` | `exam_teaching` | DOCX、Markdown、JSON、XLSX | JSON、XLSX、题目 schema、教学资料 schema | AI 生成、复杂图形 | 最终 DOCX、对比 DOCX、结构化中间产物、资料清单 |
| `bidding_materials` | `qualification_archive_packages` | DOCX、XLSX、JSON | JSON、XLSX、附件/资质 schema | 无 | 资料包、清单、最终 DOCX、投标模板 |
| `official_policy` | `meeting_policy_documents` | DOCX、Markdown、JSON | JSON | 无 | 公文模板、正式/内部/归档交付、结构化中间产物 |
| `technical_long_docs` | `long_document_publishing` | DOCX、Markdown | JSON | 无 | 技术模板、最终 DOCX、对比 DOCX、资料包 |
| `application_reports` | `project_application`、`product_sales_documents` | DOCX、Markdown、XLSX、JSON | JSON、XLSX、申报/产品资料 schema | 无 | 报告模板、资料包、结构化中间产物 |
| `contract_delivery` | 合同/签署链路 | DOCX、JSON | JSON、合同参与方/字段 schema | 法律意见不进入核心 | 最终 DOCX、对比 DOCX、签署包、字段一致性报告 |
| `batch_forms` | `hr_batch_documents`、`form_batch_documents` | DOCX、XLSX、JSON | JSON、XLSX、人员/表单 schema | 无 | 批量最终 DOCX、资料清单、结构化中间产物 |
| `professional_disclosure` | 财务、披露、双语、专利等 | DOCX、XLSX、JSON、Markdown | JSON、XLSX、专业资料 schema | AI 生成、专业判断、IP/法律/医疗等人工门 | 审阅/公开/归档/资料包交付 |
| `import_ai_boundary` | 导入/AI 边界 | 无核心格式 | 无 | PDF/OCR、完整 LaTeX、AI、复杂图形 | 只做 handoff、置信度、人工确认和目标场景路由 |

## 5. Word/OpenXML 视角复核

V36 的输入源划分必须贴住 Word 本身的 XML 结构，而不是只看用户上传文件名。

| Word/OpenXML 部件 | 对输入源矩阵的影响 | 当前判断 |
| --- | --- | --- |
| `word/document.xml` 段落、运行、表格主体 | DOCX 核心编辑事实源 | 已纳入 DOCX 输入和最终渲染链 |
| `word/styles.xml` 样式 | 模板管理和场景控件一致性的事实源 | 已由模板管理和 control contract 链路承接 |
| `word/numbering.xml` 编号 | 学术、技术长文、公文、合同均高频 | 仍需 ObjectPreflight/action closure 深化 |
| `w:tbl`、`w:tr`、`w:tc` | 批量表单、证书、答题卡、固定版式高频 | 行高 `w:trHeight` 仍归入 N2.178 fixed-layout profile |
| `headers`、`footers`、页码、节属性 | 论文、公文、合同、技术文档高频 | 已进入 Word risk 视角，仍需 journey fixture |
| footnotes/endnotes/comments/revisions | 学术、审阅、合同、披露高频 | 已在风险面中可见，但执行动作闭环仍需 N2.172 |
| text box、shape、image、OLE、embedded package | 复杂 Word 对象风险 | 不应由 InputSourceProfile 单独承诺，需 ObjectPreflight |
| relationships、media、altChunk | 外部资源和导入风险 | PDF/OCR、HTML/Markdown/AI 导入需边界和置信度 |
| macros、ActiveX、field codes | 安全和对象预检风险 | 核心不默认执行，必须进入 preflight/report |

结论：V36 解决的是“输入事实源和渲染源是否可追踪”。它不替代 ObjectPreflight，不替代 fixed-layout 行高实现，也不替代模板管理的具体样式写入。

## 6. 本轮落地基线

新增审计源：

- `src/config/scene_input_source_audit.py`
- `scripts/export_scene_input_source_audit.py`
- `tests/test_scene_input_source_audit.py`

接入链路：

- release gate 新增 `scene_input_source_audit` check。
- dashboard 新增 source `scene_input_source_audit`。
- dashboard fact source/evidence chain 纳入输入源完整性。
- dashboard row 新增 `input_formats`、`input_structured_formats`、`input_render_source_ids`、`input_boundary_source_ids`、`input_source_issue_count`。
- dashboard card 新增 `input_sources`。
- drilldown 新增 `input_source` item。
- summary projection 显示 input packs 和 InputSourceProfile family 覆盖。
- CI workflow 新增 `tests/test_scene_input_source_audit.py`。

当前基线：

| 指标 | 值 |
| --- | ---: |
| family rows | 15 |
| ready family rows | 14 |
| boundary family rows | 1 |
| pack rows | 12 |
| input-source packs | 12 |
| ready input-source packs | 12 |
| accepted formats | 6 |
| structured formats | 4 |
| material-required families | 12 |
| markdown-enabled families | 12 |
| LaTeX-fragment families | 8 |
| render sources | 8 |
| target templates | 3 |
| boundary input sources | 4 |
| format rows | 10 |
| blocking issues | 0 |
| warnings | 5 |
| missing source evidence | 0 |
| dashboard sources | 17 |
| drilldowns | 12 |
| normalized drilldown rows | 199 |

dashboard 当前有 3 个 `needs_depth` pack：

- `exam_education`：AI 出题、复杂图形属于边界输入，但结构化题源、教学资料 schema 和 Word 渲染链已打通。
- `professional_disclosure`：专业披露类允许结构化资料，但 AI/专业判断仍需人工/插件边界。
- `import_ai_boundary`：自身就是 PDF/OCR、LaTeX、AI、复杂图形边界，不是核心可执行包。

这 3 个 warning 不阻断 release gate，但会阻止产品叙述把它们误说成完全 Green/L5。

## 7. 对高层场景能力矩阵的完善结论

V36 后，高层矩阵的“高频场景不遗漏”需要同时满足五条：

1. 用户话术进入 request-cell，不是只出现在规划文档。
2. 话术落到 pack/family/profile/schema/preset/gate/handoff/negative 中的一类。
3. 输入事实源有 `InputSourceProfile` 或明确边界输入。
4. 渲染来源能追到模板、最终 DOCX、对比 DOCX、结构化中间产物或资料包。
5. dashboard、drilldown、release gate、summary projection 均能显示同一条链。

因此后续新增高频场景时，不应优先问“要不要新增一个入口”，而应先问：

- 它是否已有可复用 pack。
- 它是否只需要新增 family/profile/schema/preset。
- 它的真实输入源是否为 DOCX/Markdown/JSON/XLSX/BibTeX/CSL JSON。
- 它是否其实是 PDF/OCR、LaTeX、AI、复杂图形等边界输入。
- 它是否需要新的 MaterialSchema、CountProfile、DeliveryPreset 或 fixed-layout profile。
- 它是否已经有成功、降级、失败、人工门的 fixture 证据。

## 8. 仍未闭合的视角

V36 不把以下内容伪装成已完成：

| 后续项 | 为什么仍重要 | 建议阶段 |
| --- | --- | --- |
| ObjectPreflight 动作闭环 | 需要把 fields、comments、revisions、headers/footers、text boxes、OLE、rels 等风险从“可见”推进到“可执行处理策略” | N2.172 |
| 高频用户旅程 fixture | 需要覆盖成功、降级、失败、人工门，不只静态 fixture | N2.173 |
| 歧义澄清 UI | 高风险输入和相邻 pack 需要可交互确认 | N2.174 |
| 场景控件运行时一致性 | 控件命名、单位、禁用、布局要和模板管理一致，并进入运行时验证 | N2.175 |
| DeliveryPreset 执行完整性 | 需要验证最终 DOCX、对比 DOCX、报告、资料包、结构化中间产物真正产出 | N2.176 |
| MaterialSchema 录入和修复链路 | 需要从缺字段、缺附件、图片/签章缺失走到可修复 UI 和报告 | N2.177 |
| fixed-layout profile | `TableConfig.row_height_pt` 和 Word `w:trHeight` 应正式进入行高模板管理，或从模型退场 | N2.178 |
| Word story 全覆盖 | header/footer/footnote/endnote/comment/revision/textbox 等 story 的处理策略要进入动作闭环 | N2.172/N2.173 |
| import confidence report | PDF/OCR、AI、LaTeX handoff 需要置信度、不可恢复项和人工确认记录 | N2.172/N2.174 |

## 9. 验证命令

```text
python -m pytest tests/test_scene_input_source_audit.py tests/test_scene_matrix_dashboard.py tests/test_scene_matrix_drilldown.py tests/test_release_shell.py tests/test_scene_family_application.py -q
结果：52 passed

python scripts\export_scene_input_source_audit.py --format json
结果：passed，0 blocking issues，5 warnings

python scripts\verify_scene_matrix_release_gate.py
结果：passed，input_sources=12/12，drilldowns=12/12

python -m pytest <scene-matrix 专项集合> -q
结果：141 passed

python -m pytest -q
结果：244 秒超时，未取得全量通过结论；本轮以 release gate 与 scene-matrix 专项集合作为闭环验证。
```

## N2.172 更新：ObjectPreflight 动作闭环

V37 已将 V36 中保留的 Word/OpenXML 风险后续项推进为自动化审计源：新增 `scene_object_preflight_action_audit`，覆盖 11 个 ObjectPreflight scan target、15 个 planned family、report/workbench issue、repair route、sample fixture behavior 和 release gate。

当前基线为 11 个 scan target、10 个 ready target、5 个 high-risk target、10 个 fixture-backed target、3 个 blockable target、11 个 skippable target、7 个 manual-confirmation target、15 个 family、0 个 blocking issue、3 个 warning。dashboard source 从 17 增至 18，drilldown 从 12/199 增至 13/225。

这一步明确了 V36 中“输入 DOCX 内部对象风险”的治理边界：ObjectPreflight 负责 detect/warn/block/skip/manual/repair/report/workbench 链路；fixed-layout 的 `w:trHeight`、内容控件填充和文本框替换继续归 N2.178 产品化，不混入通用扫描目标。
