# Lark-Formatter V1.0 修复总表与复审记录

> 日期：2026-03-25  
> 复审基线：`../V1.0建设规划/V1.0_总体规划.md`、`CODE_REVIEW.md`  
> 说明：**本文件现为唯一活跃的修复/迁移记录文档**；后续修复请统一追加到这里。

---

## 1. 文档治理结果

为避免根目录下出现多份修复说明相互漂移，本轮已将修复类文档统一收口为：

| 文档 | 状态 | 用途 |
|---|---|---|
| `CODE_REVIEW.md` | 活跃 | 代码审阅基线与问题清单 |
| `FIX_REVIEW_2026-03-25.md` | 活跃 | 修复总表、架构收口、验证结果 |
| `CONFIG_CONTEXT_SCHEMA_CLEANUP_2026-03-25.md` | 归档 | 内容已并入本文件 4.1 |
| `HEADING_CONFIG_CLEANUP_2026-03-25.md` | 归档 | 内容已并入本文件 4.2 |
| `MIGRATION_NORMALIZE_FIX_2026-03-25.md` | 归档 | 内容已并入本文件 4.3 |
| `PARAGRAPH_STYLE_NUMBERING_FIX_2026-03-25.md` | 归档 | 内容已并入本文件 4.4 |

以后如果继续整改：

1. 审阅结论继续写入 `CODE_REVIEW.md`
2. 修复落地、验证结果、迁移说明统一写入本文件
3. 不再新增平行修复 `.md`

---

## 2. 当前结论

当前代码状态可以概括为三句话：

1. **不是屎山，主架构方向是对的。**
2. **上一轮最实质的运行风险已经基本收口。**
3. **本轮进一步把“补丁式修复”往更清晰的层次里回收。**

已完成收口的重点包括：

- 模块开关与实际运行逻辑对齐
- `caption` 对 `heading_recognition` 的软依赖尾巴收干净
- TOC / 域代码不再重复维护且 dirty 范围收窄
- 输出策略从“双写”收口为单一出口
- `strict_mode` 真正接入执行链
- config / context / schema 的幽灵字段继续清理
- heading 兼容逻辑从 runtime/schema 收回到 normalize 层
- `paragraph_style` 不再只改 run，而是同步 Word 样式定义

---

## 3. 已完成修复（问题 1~5）

### 3.1 模块开关与实际运行逻辑对齐

**问题本质**

- `SceneWorkspace.is_module_enabled()` 对未知模块默认 `False`
- 旧版 `main.py` 过滤模块时，对未知模块默认 `True`
- 这会导致：没有写进 `module_switches` 的模块，在运行时被默认启用

**本轮收口**

- 在 `src/config/migration.py` 中统一模块开关归一化
- 默认开关集直接来自注册表 `ModuleMeta.enabled_by_default`
- 历史别名仍兼容：
  - `citation_link` -> `reference_format`
  - `equation_table_fmt` -> `equation_table_format`
  - 以及旧 pipeline/module 别名映射
- `resolve_config()` 与 `main.py` 统一使用归一化后的结果

**结果**

- 默认启用集与实际注册模块一致
- 未注册/未实现的遗留 key 不再误启用
- 默认行为只由注册表维护，避免 Scene / main / runtime 三处漂移

### 3.2 `caption` 软依赖语义收干净

**问题本质**

`caption` 虽声明了：

- `soft_after=("heading_recognition",)`

但旧实现仍保留：

- `consumes=("doc_tree", "heading_map")`

导致关闭 `heading_recognition` 后，初始化阶段仍会因缺少 `doc_tree` / `heading_map` 报错。

**本轮收口**

- 在 `src/modules/table/caption.py` 中移除这两个硬消费声明
- 保留软依赖，让模块自行回退到全局编号路径

**结果**

- 开启 `heading_recognition`：按章节编号
- 关闭 `heading_recognition`：回退为全局编号
- 不再因软依赖缺失而阻断管线启动

### 3.3 TOC / 域代码收口

**问题本质**

旧实现存在三类问题：

1. `toc.py` 通过整段 XML 字符串搜索 `"TOC"`
2. dirty 标记会污染所有复杂域的 `begin`
3. `header_footer.py` / `toc.py` 各自内联一套复杂域构建逻辑

**本轮收口**

- 在 `src/shared/engine/field_builder.py` 中补齐统一入口：
  - `build_toc_instruction()`
  - `build_complex_field(..., result_text=..., mark_dirty=...)`
  - `iter_field_instructions()`
- `src/modules/structure/toc.py` 改为复用 `iter_field_instructions()` 检测 TOC
- dirty 只作用于 TOC 域本身
- `src/modules/basic/header_footer.py` 的页码域检测也复用同一套共享逻辑

**结果**

- TOC 检测不再依赖脆弱的整段 XML 文本搜索
- dirty 不再误伤 PAGE 等其他复杂域
- 复杂域构建逻辑开始收口到共享层，而不是继续散落在模块内部

### 3.4 输出策略统一

**问题本质**

旧行为是双重输出：

- `Pipeline` 先在源文件旁生成 `*_new.docx`
- CLI 再额外输出 `output/*_formatted.docx`

这会造成路径语义不清、输出重复。

**本轮收口**

- `Pipeline` 增加 `output_dir` / `output_suffix`
- `_save_outputs()` 只按最终策略保存一次
- CLI 改为直接读取 `result.output_paths["final"]`

**结果**

- 最终输出只保留一份
- 输出职责收口到 Pipeline + result path，而不是 CLI 再次二次保存

### 3.5 `strict_mode` 真正接入执行链

**问题本质**

旧版 `strict_mode` 只停留在配置层，模块 `validate()` / `apply()` 失败时不会真正改变执行策略。

**本轮收口**

- `src/pipeline/runner.py` 新增严格模式判断路径
- `validate()` 出现 fatal issue 时：
  - `strict_mode=True`：立即失败返回
  - `strict_mode=False`：记录失败并跳过该模块
- `apply()` 抛异常时：
  - `strict_mode=True`：立即失败返回
  - `strict_mode=False`：降级为 `partial_success`

**结果**

- 严格模式真正变成“遇错即停”
- 非严格模式允许继续执行，并在结果中保留失败项信息

---

## 4. 架构清理与归一化

### 4.1 Config / Context / Schema 清理

这一部分主要是为了清掉“schema 里没有、运行时也没真正接线、模块里却靠 `getattr()` 硬读”的幽灵路径。

**已落地内容**

1. `format_scope` 正式进入显式 schema
   - `src/config/scene.py::FormatScopeConfig`
   - `src/pipeline/context.py::PipelineContext.format_scope`
   - `Pipeline` 执行时把 `config.format_scope` 透传到 context

2. `ResolvedConfig` 中的 runtime payload 显式化
   - `md_cleanup`
   - `whitespace`
   - `citation_link`
   - `formula_convert`
   - `chem_typography`
   - `entity_data`
   - `entity_assets_dir`
   - `images`
   - `replacements`

3. 新增显式 runtime 数据结构
   - `src/config/resolved.py::ImageInsertionItem`
   - `src/config/resolved.py::ReplacementRule`

4. `resolve_config()` 负责把传入 payload 归一为上述显式结构

**结果**

- 运行时配置不再依赖隐式 stub / 幽灵字段
- `context` 与 `config` 的边界更明确
- 后续模块继续接线时，可以直接围绕显式 dataclass 扩展，而不是再堆 `Any` + `getattr()`

### 4.2 Heading 配置清理

这一部分的目标，是把 heading 相关兼容逻辑从 runtime/schema 撤回到 migration/normalize 层，避免出现“双轨配置”。

**已落地内容**

- 删除 runtime/schema 中的顶层 `heading`
- 删除 `HeadingStyleConfig` 旧路径
- 删除 `TemplateConfig.heading`
- 删除 `ResolvedConfig.heading`
- `heading_recognition` 不再声明 `requires_config=("heading",)`
- 运行时只保留：
  - `heading_numbering`
  - `heading_model`

**结果**

- 模块、resolver、tests 的口径统一为 `heading_numbering + heading_model`
- 顶层 `heading` 退回为 pure legacy 输入，只允许在 migration 层被吸收
- 减少后续开发对“旧 heading 还能不能直接读”的误解

### 4.3 Migration / Normalize 收口

为了避免 `migration.py` 继续膨胀成“大杂烩兼容文件”，本轮又做了一次拆层。

**已落地内容**

- 新增：`src/config/heading_normalize.py`
- 抽出：`normalize_heading_numbering_payload()`
- `migration.py` 保留通用 normalize / orchestration
- heading-numbering 兼容细节独立收口到 `heading_normalize.py`

**当前兼容吸收范围**

- `heading_numbering.levels`
- `heading_numbering_v2`
- legacy top-level `heading`
- shell / chain / display_template 的旧表示法

**结果**

- `migration.py` 更接近“总调度层”
- heading 兼容逻辑有了独立边界，后续继续瘦身会更容易

### 4.4 Paragraph Style / Numbering 收口

这一部分主要解决两个问题：

1. `paragraph_style` 以前只改现有 run，不改 Word 样式定义
2. `_should_skip_numbering()` 的边界行为覆盖不足

**已落地内容**

- 新增：`src/shared/engine/style_ops.py`
  - `apply_style_text_format()`
- `src/modules/basic/paragraph_style.py` 现在会同步 `Heading 1..8` 的 Word 样式定义
- 同步内容包括：
  - `style.font.name`
  - `w:rFonts/@ascii`
  - `w:rFonts/@hAnsi`
  - `w:rFonts/@cs`
  - `w:rFonts/@eastAsia`
  - `style.font.size`
  - `w:sz`
  - `w:szCs`
- `tests/test_phase3_structure.py` 补充 `_should_skip_numbering()` 边界用例

**结果**

- 不仅现有段落 run 被修正，Word 中后续手动套用标题样式也会继承正确字体/字号
- 样式定义写入逻辑被抽到共享层，避免继续堆 OOXML 细节到 `paragraph_style.py`

---

## 5. 验证结果

### 5.1 全量测试

```bash
python -m pytest -q
78 passed in 1.00s
```

### 5.2 样例文档回归

执行过的样例：

```bash
$env:PYTHONIOENCODING='utf-8'
python .\main.py ".\tests\TEST-1\测试文档_new.docx" -o ".\tests\TEST-1\output_style_font_sync"
python .\main.py ".\tests\TEST-1\中图分类号.docx" -o ".\tests\TEST-1\output_style_font_sync_2"
```

结果：

- 两份样例文档均执行成功
- 第二份文档 `中图分类号.docx` 已覆盖不同文档结构
- `Heading 2` 样式定义验证通过：
  - `font.name = Times New Roman`
  - `font.size.pt = 14.0`
  - `w:rFonts ascii/hAnsi/cs = Times New Roman`
  - `w:rFonts eastAsia = 黑体`
  - `w:sz = 28`
  - `w:szCs = 28`

### 5.3 关键测试补点

本轮重点补强的测试包括：

- `tests/test_phase1_config.py`
  - 模块开关默认集与注册表一致
  - 历史模块别名归一
  - legacy template / scene / overrides 归一化
  - runtime payload 显式 materialize
- `tests/test_phase3_basic.py`
  - `test_paragraph_style_syncs_heading_style_definition_text_format`
- `tests/test_phase3_structure.py`
  - TOC dirty 范围收窄
  - `test_should_skip_numbering_edge_cases`
- `tests/test_phase3_table.py`
  - `caption` 在无 `heading_recognition` 时回退执行
- `tests/test_phase5_e2e.py`
  - dirty propagation 口径对齐到 `heading_numbering`

---

## 6. 本轮涉及文件（按主题归类）

### 运行风险修复

- `main.py`
- `src/config/scene.py`
- `src/config/resolver.py`
- `src/config/migration.py`
- `src/modules/table/caption.py`
- `src/modules/structure/toc.py`
- `src/modules/basic/header_footer.py`
- `src/shared/engine/field_builder.py`
- `src/pipeline/runner.py`

### 架构清理

- `src/config/template.py`
- `src/config/resolved.py`
- `src/config/resolver.py`
- `src/config/migration.py`
- `src/config/heading_normalize.py`
- `src/pipeline/context.py`
- `src/modules/structure/heading_recognition.py`
- `src/modules/basic/paragraph_style.py`
- `src/shared/engine/style_ops.py`

### 测试

- `tests/test_phase0_smoke.py`
- `tests/test_phase1_config.py`
- `tests/test_phase3_basic.py`
- `tests/test_phase3_table.py`
- `tests/test_phase3_structure.py`
- `tests/test_phase5_e2e.py`

---

## 7. 归档文档映射

为防止后续再次出现多份文档各写一半，现将专项文档固定映射如下：

| 归档文档 | 请查看本文件章节 |
|---|---|
| `CONFIG_CONTEXT_SCHEMA_CLEANUP_2026-03-25.md` | 4.1 |
| `HEADING_CONFIG_CLEANUP_2026-03-25.md` | 4.2 |
| `MIGRATION_NORMALIZE_FIX_2026-03-25.md` | 4.3 |
| `PARAGRAPH_STYLE_NUMBERING_FIX_2026-03-25.md` | 4.4、5 |

这些归档文件将只保留跳转/说明，不再独立维护正文。

---

## 8. 给同事复审时建议重点看什么

建议重点复核这 5 个点：

1. **默认启用集是否符合当前产品预期**
   - 尤其是 `reference_format`、`equation_table_format`、`chem_typography`

2. **`strict_mode` 的产品语义是否已经定稿**
   - 当前实现：严格模式即停，非严格模式返回 `partial_success`

3. **legacy 输入吸收范围是否还缺别名**
   - 尤其是旧 scene / pipeline / module 名

4. **Word 样式定义同步是否还要继续扩展**
   - 当前已覆盖字体/字号
   - 后续如果需要，可再考虑粗体/斜体等样式定义同步

5. **`migration.py` 是否还要继续瘦身**
   - 当前 heading 兼容已拆出
   - 后续仍可继续压缩剩余 legacy 分支

---

## 9. 一句话总结

这轮整理的核心不是再补一层补丁，而是把已经做过的修复**收口成更清晰的文档结构和更清楚的代码边界**：

- 审阅结论收口到 `CODE_REVIEW.md`
- 修复记录收口到本文件
- 专项修复说明降级为归档跳转
- 代码层把运行风险、schema 清理、heading 兼容、Word 样式定义写入分别压回到更合适的层里

---

## 10. 二轮复审后追加收口

基于本轮复审，又补做了两项“最小必要修复”：

### 10.1 模块开关增加“依赖闭包”收口

问题：

- 仅按 `config.is_module_enabled()` 过滤模块时
- 如果用户手动关闭上游硬依赖模块，但保留下游模块
- `Pipeline` 初始化阶段仍会直接因为 `depends_on` 缺失而报错

本轮处理：

- 新增 `src/pipeline/scheduler.py::select_enabled_modules()`
- 规则是：
  1. 先尊重显式模块开关
  2. 再把硬依赖未满足的模块自动剪掉
  3. 递归执行，直到启用集满足依赖闭包
- `src/cli_runner.py` 已改为使用该函数
- 对被自动剪掉的模块，会在 CLI 中输出提示，而不是静默处理

结果：

- 不会再因为“场景开关合法、但依赖集不闭合”导致 CLI 在建管线时直接崩掉
- 同时也没有偷偷把用户明确关闭的模块又自动重新启用

### 10.2 TOC 数据流声明与实际读取对齐

问题：

- `toc` 原先声明 `consumes=("doc_tree",)`
- 但插入位置的自动判断实际读取的是 `heading_map`

本轮处理：

- `src/modules/structure/toc.py`
  - 将 `consumes` 调整为 `("heading_map",)`
- 对应测试已同步更新

结果：

- data-flow contract 与真实执行路径一致
- 避免后续继续出现“声明消费一个字段，实际读另一个字段”的隐性漂移

---

## 11. 清理策略：如何避免把旧问题重新放出来

你提的这个担心是对的：**很多旧代码虽然不好看，但本质上是“历史问题抑制器”**。  
如果只是机械删掉，很容易把以前压住的 bug 放出来。

所以当前采用的清理原则不是“直接删”，而是：

1. **先识别它原来在抑制什么问题**
2. **先把那个历史问题变成测试 / 契约 / 显式规则**
3. **再把旧实现迁移到更干净的层**
4. **确认回归通过后，才删掉旧壳**

本轮就是按这个方式做的：

- `heading` 兼容逻辑  
  - 不是直接删除  
  - 而是先保留 legacy 输入，再收口到 `heading_normalize.py`
- Word 标题样式定义同步  
  - 不是删掉旧 run 级处理  
  - 而是在保留现有行为的前提下补样式定义级同步
- 模块依赖闭包  
  - 不是粗暴放开 `depends_on`  
  - 而是把“非法启用集”收口到调度层

另外，这轮我**刻意没有**做一类高风险“伪清理”：

- 没有强行删除 `Pipeline` 里对 `SimpleNamespace` 的兼容回退
- 原因是它现在仍承担测试/轻量调用兼容作用
- 在没有补齐更合适替代物之前，先不动它，避免把现有调用方式打断

也就是说，后面的清理策略会继续遵守：

- **先固化行为，再替换实现**
- **先把隐式防御转成显式测试，再删旧代码**
- **宁可慢一点，也不做“看起来更干净、实际上放出旧 bug”的清理**
