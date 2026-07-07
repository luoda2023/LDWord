# 高层场景能力矩阵 V37 ObjectPreflight 动作闭环审计与 Word 对象风险治理
日期：2026-06-19

## 1. 文档定位

V37 对应 N2.172，承接 V36 的输入来源闭环。V36 回答“材料从哪里来、如何结构化、最终如何渲染”，V37 回答“输入 DOCX 内部的 Word/OOXML 风险对象被发现后，系统到底怎么处理”。

本轮不重新实现 DOCX 扫描器，也不把所有 Word 对象都变成自动修复能力。它新增的是一个动作闭环审计：

```text
Word/OOXML 风险目标
-> ObjectPreflight scan target
-> scene family 推荐/实际扫描策略
-> warn/block/skip/manual/preserve action
-> report/workbench issue
-> repair route
-> sample fixture behavior
-> release gate
```

这样可以避免“风险面在规划文档里可见，但运行时只有一条 warning 字符串”的断链。

## 2. 审计范围

N2.172 固定 11 个 ObjectPreflight scan target：

| Target | 风险含义 | 当前动作闭环 |
| --- | --- | --- |
| `ole_objects` | OLE 对象、嵌入对象 | detect、warn、block、skip module、manual confirmation、repair route |
| `embedded_workbooks` | 嵌入 Excel 工作簿 | detect、warn、block、skip module、fixture |
| `embedded_packages` | 嵌入包、附件关系 | detect、warn、skip module、fixture |
| `visio_drawings` | Visio/复杂绘图关系 | detect、warn、skip module、repair route；缺独立 fixture |
| `macros` | VBA 宏 | detect、warn、block、skip module、manual confirmation、fixture |
| `tracked_changes` | 修订、插入、删除、移动 | detect、warn、skip module、fixture |
| `comments` | 批注 | detect、warn、skip module、manual confirmation、fixture |
| `hidden_text` | 隐藏文字 | detect、warn、skip module、manual confirmation、fixture |
| `textboxes` | 文本框、shape 文本 | detect、warn、skip module、manual confirmation、preserve layout |
| `content_controls` | 内容控件、结构化文档标签 | detect、warn、skip module、manual confirmation、preserve layout |
| `fields` | Word 字段、TOC/PAGE/REF 等 | detect、warn、skip module、manual confirmation、preserve layout |

## 3. 本轮新增自动化资产

新增：

- `src/config/scene_object_preflight_action_audit.py`
  - 定义 target row、family row、source evidence；
  - 横向检查 11 个 scan target 和 15 个 planned family；
  - 验证扫描器、pipeline、report writer、Workbench issue queue、repair route、sample fixture、word risk audit 的证据链。
- `scripts/export_scene_object_preflight_action_audit.py`
  - 支持 JSON/Markdown；
  - 支持 `--target`、`--family` 过滤。
- `tests/test_scene_object_preflight_action_audit.py`
  - 锁定 target/family/action/fixture/warning 基线；
  - 锁定 macros、fields、visio_drawings、contract_delivery、long_document_publishing 等关键链路。

接入：

- `scripts/verify_scene_matrix_release_gate.py`
  - 新增 `scene_object_preflight_action_audit` check；
  - release payload 增加 ObjectPreflight target/family/action/source evidence 计数；
  - human summary 增加 `object_preflight_actions=10/11`。
- `src/config/scene_matrix_dashboard.py`
  - dashboard source 从 17 增至 18；
  - `word_risk`、`evidence_chain` lens 纳入 `scene_object_preflight_action_audit`；
  - dashboard row 增加 `object_preflight_target_ids`、`object_preflight_action_count`、`object_preflight_action_issue_count`、`object_preflight_action_warning_count`；
  - 新增 `object_preflight_actions` card。
- `src/config/scene_matrix_drilldown.py`
  - required drilldown 从 12 增至 13；
  - 新增 `object_preflight_action` drilldown；
  - normalized rows 从 199 增至 225。
- `src/ui/panels/scene_summary_projection.py`
  - evidence chain summary 增加 `10/11 ObjectPreflight actions`；
  - drilldown summary 增加 ObjectPreflight actions。
- `.github/workflows/scene-matrix-release-gate.yml`
  - CI 专项清单加入 `tests/test_scene_object_preflight_action_audit.py`。

## 4. 当前基线

| 指标 | 值 |
| --- | ---: |
| scan targets | 11 |
| ready targets | 10 |
| warning targets | 1 |
| high-risk targets | 5 |
| fixture-backed targets | 10 |
| blockable targets | 3 |
| skippable targets | 11 |
| manual-confirmation targets | 7 |
| family rows | 15 |
| ready family rows | 12 |
| boundary family rows | 1 |
| strict family rows | 2 |
| family rows with fixture | 12 |
| blocking issues | 0 |
| warnings | 3 |
| missing source evidence | 0 |
| dashboard sources | 18 |
| drilldowns | 13 |
| normalized drilldown rows | 225 |

3 个 warning 的含义：

- `visio_drawings` 缺独立 fixture：当前能 detect/warn/skip/route，但还没有最小 Visio fixture 证明真实包行为。
- `finance_quote_documents` 缺 family 级 fixture：专业披露 pack 有样本，但财务报价 family 自身还缺独立样本。
- `bilingual_translation_documents` 缺 family 级 fixture：专业披露 pack 有样本，但双语术语审阅 family 自身还缺独立样本。

这些 warning 不阻断 release gate，但会继续阻止 Green/L5 宣称。

## 5. Word/OpenXML 视角复核

N2.172 将 Word 风险从“文档部件名”推进到“动作策略”：

| Word/OpenXML 风险 | 当前治理动作 | 未完成深水区 |
| --- | --- | --- |
| `w:fldSimple`、`w:instrText`、`fldChar` | 字段扫描、报告、Workbench issue、模块跳过 | 字段刷新/失效后的可交互修复还需用户旅程 fixture |
| `comments.xml`、`w:commentRangeStart` | 批注扫描、报告、Workbench issue | 批注接受/保留/清理策略还需场景化动作 |
| `w:ins`、`w:del`、`w:moveFrom`、`w:moveTo` | 修订扫描、报告、模块跳过 | 是否接受修订仍需人工确认 UI |
| `w:vanish`、`w:webHidden` | 隐藏文字扫描和计数影响说明 | 可视化高亮/修复入口仍需旅程补充 |
| `w:txbxContent`、`wps:txbx`、`v:textbox` | 文本框扫描和 fixed-layout 路由 | 复杂 shape 内文本的可编辑修复仍需深化 |
| `w:sdt`、`w:tag`、`w:alias` | 内容控件扫描、fixed-layout 填充/保护路径 | 内容控件映射 UI 仍需更多样本 |
| `word/embeddings/*`、OLE relationship | OLE/嵌入对象扫描、阻断/跳过/人工门 | 对不同 OLE 类型的更细分策略仍需扩展 |
| `vbaProject.bin` | 宏扫描、阻断、人工确认 | 宏安全策略只做阻断，不做宏内容分析 |
| `word/_rels/*.rels` | 关系扫描和包风险报告 | 外部链接、附件、媒体关系的 artifact browser 仍需 N2.176 |

## 6. 与 fixed-layout/row height 的关系

当前工作树显示 `TableConfig.row_height_pt` 不再只是残留参数：`fixed_layout`、`FixedLayoutRowHeightPolicy`、`w:trHeight` 写入、repair route 和测试已经存在。V37 不把它并入通用 ObjectPreflight target，而是保留为 fixed-layout profile 深水区：

- ObjectPreflight 负责发现内容控件、文本框、字段、嵌入对象等风险。
- fixed-layout profile 负责 `w:trHeight`、内容控件填充、文本框替换、占位符残留等固定版式行为。
- N2.178 仍需要补产品化体验与更多 fixture，但“行高完全残留”这个判断在当前工作树下已不准确。

## 7. 后续闭环

N2.172 后仍未闭合：

| 后续项 | 目标 |
| --- | --- |
| N2.173 高频用户旅程 fixture | 把成功、降级、失败、人工门路径变成真实用户旅程样本 |
| N2.174 歧义澄清 UI | 对相邻场景、风险对象、导入边界给出可交互确认 |
| N2.175 场景控件运行时一致性 | 验证模板管理同名控件和场景控件在 UI/执行/报告中一致 |
| N2.176 DeliveryPreset 执行完整性 | 验证最终 DOCX、对比 DOCX、资料包、报告、中间产物真实产出 |
| N2.177 MaterialSchema 录入与修复链路 | 缺字段/缺资产/资料冲突能路由到修复入口 |
| N2.178 fixed-layout profile 产品化 | 深化 `w:trHeight`、内容控件、文本框、证书/答题卡等固定版式场景 |

## 8. 验证

```text
python -m pytest tests/test_scene_object_preflight_action_audit.py tests/test_scene_matrix_dashboard.py tests/test_scene_matrix_drilldown.py tests/test_release_shell.py -q
结果：25 passed

python scripts\verify_scene_matrix_release_gate.py
结果：passed，object_preflight_actions=10/11，drilldowns=13/13

python -m pytest <scene-matrix 专项集合> -q
结果：145 passed

python -m pytest -q
结果：1361 passed，4 warnings（openpyxl datetime deprecation）
```
