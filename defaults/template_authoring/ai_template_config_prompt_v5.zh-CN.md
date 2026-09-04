# AI 排版模板生成提示词（V5）

当前工作模式：`{{WORK_MODE_LABEL}}`（`{{WORK_MODE_ID}}`）
创作 Profile：`{{PROFILE_ID}}`（V{{PROFILE_VERSION}}）
基准模板：`{{BASELINE_TEMPLATE_ID}}`

## 使用方式

应用会为每次模板创作自动提供以下材料：

1. 本提示词；
2. `{{BASELINE_FILENAME}}`；
3. 且只提供一种来源证据：附件正文中的文本规范，或从 DOCX 提取的结构化格式证据。

不要把原始 Word 正文与结构化格式证据再次混合输入，也不要在一种来源证据不足时读取或推断另一种来源。

AI 返回结果必须是一个 `.json` 文件。把它放进 `{{INBOX_NAME}}` 文件夹，应用会核对工作模式、Profile、基准指纹和字段完整性后再导入。

系统会为每次创作明确指定且只指定一种证据来源：

- **文本规范生成**：只读取附件正文中明确写出的规范条款，不读取或推断 Word 外观；
- **Word 格式克隆**：只读取结构化 DOCX 格式证据，不读取正文中的自然语言要求。

两种功能相互独立，不得混用、互相补值或在证据不足时切换来源。

## 你的职责边界

你只生成“可复用的排版外观模板”，不能把固定文档骨架、处理行为或逐份变化的资料塞进模板。

### Master（母版）边界

{{MASTER_BOUNDARIES}}

### Scene（方案）边界

{{SCENE_BOUNDARIES}}

### Material（资料）边界

{{MATERIAL_BOUNDARIES}}

如果 Word 范例中出现这些非模板信息，不要改写到 `template` 中；请用简短文本分别记录到结果 envelope 的 `observations.master`、`observations.scene`、`observations.material`。无法可靠归类或当前模板无法表达的内容放入 `observations.unsupported`。

## 模板可写范围

除 `name` 和 `description` 外，只允许修改以下 `template` 顶层根：

{{AUTHORABLE_ROOTS}}

以下根虽然仍存在于兼容版 `TemplateConfig`，但实际属于 Scene 或 Output 层，必须与基准逐值完全一致：

{{FROZEN_ROOTS}}

当前模式必须保留以下样式角色及其完整字段：

{{REQUIRED_STYLE_ROLES}}

不得删除任何嵌套字段、必需样式角色或编号 catalog 项。集合与规则数组可依据来源证据整体替换或重新分组；页码 `phases` 可以拆分、合并，但基准覆盖范围不得丢失、不同阶段不得重叠。无法确认时保留基准值。

## 输出合同

1. 只输出 JSON，不要输出 Markdown 代码块、注释、解释或前后缀。
2. 输出根对象的 `kind` 必须是 `{{RESULT_KIND}}`，`schema_version` 必须是 `{{SCHEMA_VERSION}}`。
3. 从基准 envelope 原样复制 `mode_id`、`profile_id`、`profile_version`、`baseline_template_id`、`baseline_sha256`、`prompt_version`、`prompt_sha256` 和 `contract_fingerprint`，不得猜测或修改。
4. 完整复制基准中的 `template` 对象，再只修改 `name`、`description` 和上方列出的可写根。
5. `name` 必须改成能识别来源的具体名称，例如“重庆人文科技学院 2026 届艺术类毕业设计说明格式”；不能保留基准占位名称或“默认格式”。
6. `description` 应简短说明来源和适用范围。
7. 数值必须保持数值，布尔值必须保持布尔值，数组和对象必须保持原类型。
8. 标题编号、目录级别和标题样式必须相互一致；不确定时保留基准值。
9. `observations` 必须且只能包含 `master`、`scene`、`material`、`unsupported` 四个文本数组；没有内容时使用空数组。
10. 不得新增 envelope 字段，不得输出旧版 Scene 字段，也不得输出 patch。

结果结构必须为：

```text
kind: {{RESULT_KIND}}
schema_version: {{SCHEMA_VERSION}}
mode_id/profile_id/profile_version: 从基准原样复制
baseline_template_id/baseline_sha256: 从基准原样复制
prompt_version/prompt_sha256/contract_fingerprint: 从基准原样复制
template: 完整 TemplateConfig 对象
observations:
  master: 文本数组
  scene: 文本数组
  material: 文本数组
  unsupported: 文本数组
```

Word 文档是来源证据，不是要复制进 JSON 的正文内容。输出前请检查：模式与指纹已原样复制、冻结根未改变、基准结构无删除、必需样式仍完整、JSON 语法有效。
