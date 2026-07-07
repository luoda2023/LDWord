# 高层场景能力矩阵 V34：CountProfile 场景覆盖审计与计数口径闭环

日期：2026-06-19

## 1. 背景

V33 已把产品成熟度升级缺口拆成八类 domain，其中 `rule_governance`、`report_artifact`、`structured_source` 都会触及 CountProfile。N2.170 的目标不是做一个“全局字数统计器”，而是证明高频场景的计数语义能沿着下面链路闭合：

```text
planned family / coverage pack
-> CountProfile
-> scope / included scopes / excluded scopes / primary metrics / section limits
-> scene family execution defaults
-> ValidationModule + CountEngine
-> tracker + JSON/Markdown report
-> rule source / manual / plugin boundary
```

## 2. N2.170 实现范围

新增/修改：

- 新增 `src/config/scene_count_profile_audit.py`；
- 新增 `scripts/export_scene_count_profile_audit.py`；
- 新增 `tests/test_scene_count_profile_audit.py`；
- `scene_count_profile_audit` 进入 release gate；
- dashboard source 从 15 扩展到 16；
- dashboard 新增 `CountProfiles` card；
- drilldown 从 10/169 扩展到 11/184，新增 `count_profile`；
- summary projection 在 evidence chain 中显示 CountProfile family 覆盖；
- CI workflow 和 release shell 清单纳入 N2.170 测试与导出脚本。

## 3. 当前自动化基线

| 指标 | 值 |
| --- | ---: |
| registered CountProfiles | 20 |
| family-referenced CountProfiles | 17 |
| rule-source-backed CountProfiles | 11 |
| registry-only CountProfiles | 2 |
| rule-source-only CountProfiles | 1 |
| section-limit CountProfiles | 1 |
| unique scopes | 19 |
| unique primary metrics | 18 |
| family rows | 15 |
| ready family rows | 14 |
| boundary family rows | 1 |
| pack rows | 12 |
| count-profile packs | 10 |
| ready count-profile packs | 10 |
| runtime consumers | 5 |
| report surfaces | 8 |
| release gate issues | 0 |
| warnings | 2 |
| missing source evidence | 0 |

两个 warning 是有意保留的视角信号：

- `basic`：通用 fallback profile，不能当作高频场景专属口径；
- `word_xml_full`：全 Word XML 审计口径，适合后续 ObjectPreflight / fixed-layout / OOXML 风险审计，不应误认为某个业务 family 的默认计数规则。

## 4. 关键视角

### 4.1 Family 视角

15 个 planned family 全部进入 CountProfile audit：

- 14 个 family `ready`；
- `ip_patent_documents` 是 `boundary`，因为它是 plugin/manual-only family，不提供核心执行默认；
- 每个 ready family 的执行默认 `compliance_profile.count_profile_id` 都落在 family 声明的 `count_profiles` 内；
- `journal_en` 同时声明 `journal_words` 与 `journal_display_items`，但执行默认是 `journal_words`；
- `project_application` 同时声明 `application_word_limits` 与 `attachment_inventory`，但执行默认是 `application_word_limits`；
- `regulated_disclosure_documents` 同时声明 `disclosure_section_inventory` 与 `attachment_inventory`，执行默认是 `disclosure_section_inventory`。

### 4.2 Pack 视角

12 个 pack 中，10 个有 CountProfile 语义并全部 ready：

- `quick_formatting` 不适用 CountProfile；
- `import_ai_boundary` 不适用 CountProfile；
- `professional_disclosure` ready，但其计数语义仍带专业边界；
- `bidding_materials` 的 family 默认是 `attachment_inventory`，而 `bid_package` 通过 rule source 单独出现。

### 4.3 Profile 视角

20 个注册 profile 被分成三类：

- family-backed：17 个；
- rule-source-only：1 个，`bid_package`；
- registry-only：2 个，`basic` 与 `word_xml_full`。

`bid_package` 是本轮显性化的边界点：它被 `procurement_bidding_rule_defaults` 引用，但不在 `qualification_archive_packages.count_profiles` 中。这意味着“标书正文包计数”和“资质归档附件 inventory”仍需要在后续招投标 family 拆分中继续产品化；N2.170 不把它当作缺失错误，但也不再让它隐身。

## 5. 报告与执行闭环

N2.170 锁定的 runtime consumers：

- `ValidationModule`；
- `CountEngine`；
- `ChangeTracker`；
- `JSON report`；
- `Markdown report`。

N2.170 锁定的 report surfaces：

- `counts.profile_id`；
- `counts.profile_name`；
- `counts.profile_source`；
- `counts.scope`；
- `counts.included_scopes`；
- `counts.excluded_scopes`；
- `counts.primary_metrics`；
- `counts.counts`。

这说明 CountProfile 不只是 registry 字符串，它已经能进入执行、tracker 和报告。N2.170 first slice 仍不承诺外部学校、期刊、招采、监管系统的最终权威口径；这些必须继续通过 rule source review、manual confirmation 或 plugin boundary 表达。

## 6. 与后续路线的关系

| 阶段 | 关系 |
| --- | --- |
| N2.171 InputSourceProfile | CountProfile 的 scope 需要与 DOCX/JSON/Markdown/XLSX/PDF/OCR/LaTeX/AI 事实源边界对齐 |
| N2.172 ObjectPreflight | `word_xml_full` 可作为 headers/footers/footnotes/comments/textboxes/hidden text/tracked changes/fields 的审计口径 |
| N2.173 用户旅程 fixture | 每个高频 family 需要成功、降级、失败/人工门下的 count report fixture |
| N2.174 歧义澄清 UI | 用户说“字数/词数/附件数”时，要区分场景、profile、rule source 和边界 |
| N2.175 场景控件一致性 | CountProfile selector 必须与模板/场景共享控件语义保持一致 |
| N2.176 DeliveryPreset | count report 必须跟多版本输出、归档包、资料包一起交付 |
| N2.177 MaterialSchema | attachment/material inventory profile 要能回到字段和附件修复入口 |
| N2.178 fixed-layout profile | 表格、文本框、内容控件、行高等固定版式对象需要统一审计口径 |

## 7. 验证

```text
python -m pytest tests/test_scene_count_profile_audit.py tests/test_scene_matrix_dashboard.py tests/test_scene_matrix_drilldown.py tests/test_release_shell.py -q
结果：25 passed

python scripts\verify_scene_matrix_release_gate.py
结果：passed；count_profiles=14/15；dashboard sources=16；drilldowns=11/11

python -m pytest <scene-matrix 专项集合> -q
结果：144 passed

python -m pytest -q
结果：1352 passed, 4 warnings
```

## N2.171 更新：计数口径与输入事实源对齐

V36 已补齐 `InputSourceProfile` 横向审计，`CountProfile` 不再只回答“怎么算”，还必须能被追问“从什么输入事实源算”。当前输入源基线为 15 个 family、12 个 input-source pack、6 类核心 accepted format、4 类 structured format、4 类 boundary input source、8 类 render source、0 个 blocking issue。

对 V34 的影响：

- DOCX/Markdown/JSON/XLSX/BibTeX/CSL JSON 被拆成不同事实源角色，避免单一“文档输入”误导计数口径。
- PDF/OCR、完整 LaTeX、AI 生成、复杂图形属于 handoff/plugin/manual boundary，不能作为 CountProfile 的稳定事实源。
- `exam_teaching` 已同时保留 `exam_items_v1` 和 `teaching_assets_v1`，试卷题源和教学资料不再在结构化输入链路上断开。
- 下一步 CountProfile 的 report fixture 应显示输入来源、计数 scope、排除范围、降级项和人工确认项。
