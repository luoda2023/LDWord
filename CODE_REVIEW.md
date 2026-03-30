# Lark-Formatter V1.0 代码审阅报告

> **审阅范围**：`src/` 全部 ~90 个 Python 文件，对照唯一规划基线 `V1.0建设规划/V1.0_总体规划.md`  
> **审阅日期**：2026-03-24
>
> **文档治理更新（2026-03-25）**：`V1.0建设规划/` 目录中的其余规划 `.md` 已降级为归档/索引文件；本报告中提到的“规划文档”默认均指 `V1.0_总体规划.md`。后续修复/迁移记录统一收口到 `FIX_REVIEW_2026-03-25.md`，其余专项修复 `.md` 仅保留归档跳转说明。

---

## 总体评价

| 维度 | 评分 | 说明 |
|------|:----:|------|
| 架构方向 | ⭐⭐⭐⭐ | 三层配置 + Pipeline + 模块化方向正确 |
| 代码可读性 | ⭐⭐⭐⭐ | 文件短小、注释充分、命名规范 |
| 规划-代码一致性 | ⭐⭐⭐☆ | 存在多处偏差（见下文） |
| 数据流安全性 | ⭐⭐⭐☆ | consumes/provides 校验有盲区 |
| 可维护性 | ⭐⭐⭐⭐ | 隔离原则执行良好，但有退化风险 |

**总结**：不是屎山。架构方向正确、代码整洁度高。主要问题是**配置层接口定义与模块实现不同步**。

---

## 🔴 P0 — 必须修复（3 项）

### 1. `consumes` 与 `soft_after` 语义冲突

**涉及文件**：`paragraph_style.py`、`header_footer.py`、`caption.py`

**问题**：模块声明 `consumes=("doc_tree",)` 但依赖关系用 `soft_after` 而非 `depends_on`。当 `heading_recognition` 被关闭时，`soft_after` 允许缺失，但 `validate_data_flow()` 会因 `doc_tree` 未提供而**报错阻止管线启动**。

**示例**（`paragraph_style.py` L52-59）：
```python
meta = ModuleMeta(
    name="paragraph_style",
    soft_after=("heading_recognition",),   # 软依赖 → 可缺失
    consumes=("doc_tree",),                # 硬消费 → 校验不通过!
)
```

**修复方案**：  
- A：将 `doc_tree` 从 `consumes` 移除（代码中已用 `if doc_tree is not None` 防御）  
- B：引入 `soft_consumes` 语义（软消费，不参与校验）

---

### 2. `ResolvedConfig` 存在大量无类型 `Any` 字段

**涉及文件**：`src/config/resolved.py` L97-105

```python
heading: Any = None
table_style: Any = None
watermark: Any = None
chem: Any = None
reference_style: Any = None
images: list | None = None
replacements: list | None = None
```

**问题**：
- 这些字段没有对应的 `dataclass` 定义
- `resolver.py` 中从未填充这些字段 — **始终为 `None`**
- 各模块通过 `getattr(config, "heading", None)` 读取，失败时静默跳过
- 导致 `heading_numbering`、`table_format` 等模块的**配置驱动逻辑完全不生效**

**修复方案**：为每个 `Any` 字段创建对应的 `dataclass`，或删除无用字段并从场景配置中正确传递。

---

### 3. `main.py` 的 `result.changes` 字段不存在

**涉及文件**：`main.py` L112-116

```python
if hasattr(result, "changes") and result.changes:
    changes = result.changes
elif hasattr(result, "tracker_items"):
    changes = result.tracker_items
```

**问题**：`PipelineResult` 的 dataclass 中没有 `changes` 或 `tracker_items` 字段。实际数据在 `result.tracker`（`ChangeTracker` 实例）中。**CLI 报告永远没有变更记录**。

**修复方案**：
```python
changes = []
if result.tracker:
    changes = [
        {"rule_name": r.rule_name, "target": r.target, ...}
        for r in result.tracker.get_all()
    ]
```

---

## 🟡 P1 — 建议修复（7 项）

### 4. 模块注册表性能问题

**涉及文件**：`src/modules/registry.py` L79-88

`create_modules_by_names()` 和 `list_module_names()` 每次调用都**实例化全部模块**仅为读 `meta.name`。`meta` 是类属性，应使用 `cls.meta.name`。

---

### 5. 模块分类与规划文档不一致

| 规划分类 | 实际位置 | 问题 |
|---------|---------|------|
| `validate/md_cleanup.py` | `special/md_cleanup.py` | 分错类 |
| `validate/validation.py` | 不存在 | 未实现 |
| `validate/whitespace_normalize.py` | 不存在 | 未实现 |
| `fill/text_transform.py` | 不存在 | 未实现 |
| `special/cover_page.py` | 不存在 | 未实现 |
| `special/signature_block.py` | 不存在 | 未实现 |
| `special/official_doc.py` | 不存在 | 未实现 |
| — | `special/chem_typography.py` | 规划未列出但已实现 |
| — | `special/reference_format.py` | 规划中为 `citation_link.py`，改名 |
| — | `table/figure_table_center.py` | 规划未列出但已实现 |
| — | `fill/placeholder_replace.py` | 规划未列出但已实现 |

`validate/` 子目录完全缺失。`md_cleanup` 错放在 `special/` 中。

---

### 6. 多处通过 `getattr` 绕过类型化配置

| 模块 | 代码行 | `getattr` 目标 |
|------|-------|---------------|
| `section_format` | L53 | `config.section_break_type` |
| `heading_numbering` | L72 | `config.heading` |
| `table_format` | ~L60 | `config.table_style` |
| `toc` | L53-57 | `toc_cfg.enabled`, `toc_cfg.max_level` |
| `header_footer` | L57-62 | `hf_cfg.header_mode` 等 |

这些字段在 `ResolvedConfig` 和子 `dataclass` 中不存在，`getattr` 始终返回 `None`/默认值，相关逻辑**永远不生效**。

---

### 7. 域代码构建逻辑重复

`header_footer.py` L224-250 和 `toc.py` L162-191 各自内联了完整的域代码构建逻辑（BEGIN→INSTR→SEPARATE→RESULT→END），而 `shared/engine/field_builder.py` 已存在专用工具。违反原则「不使用 shared/ 之外的内联工具函数」。

---

### 8. 东亚字体设置逻辑重复

- `paragraph_style.py` L283-288 — `_set_run_east_asian_font()`
- `header_footer.py` L215-217 — 内联相同逻辑

应抽取到 `shared/engine/run_ops.py`。

---

### 9. `font_resolver._is_available` 始终返回 `True`

`shared/engine/font_resolver.py` L111-115：
```python
def _is_available(name: str) -> bool:
    return True  # 简化实现
```

字体解析的 fallback 链永远不触发，`list_system_fonts()` 永远不被调用。整个字体解析模块实质为**空操作**。

---

### 10. Pipeline 不调用模块的 `validate()` 方法

`BaseModule.validate()` 已定义但 `Pipeline.execute()` 中从未调用。规划中「执行前前置校验」功能不生效。

---

## 🟢 P2 — 优化建议（6 项）

### 11. `_apply_overrides` 对 `dict` 类型中间节点处理不完整

`resolver.py` L113-129：当覆盖路径中间节点是 `dict` 而非 `dataclass` 时，`setattr` 会失败。建议添加 `dict` 分支。

### 12. `units.py` 文档声称 Decimal 精度但实际用 float

文档「使用 Decimal 精度」与实际不符，应修正文档或改用 `Decimal`。

### 13. `_has_existing_toc` 暴力搜索整个文档 XML

`toc.py` L86-90 将整个 body 序列化为字符串再搜索 "TOC"，性能差且可能误匹配。应改用 XPath。

### 14. `_mark_toc_for_update` 标脏所有域

`toc.py` L93-99 会将所有 `fldChar begin` 设为 dirty，影响范围超出 TOC（图表编号、交叉引用等也会被标脏）。

### 15. `SceneWorkspace.module_switches` 与实际注册模块不同步

硬编码的开关列表包含未实现模块（`text_transform`、`cover_page` 等），而已实现模块（`chem_typography`、`reference_format`、`figure_table_center`、`placeholder_replace`）未列入。

### 16. `table_format.py` 已达 431 行，接近 500 行红线

后续扩展易超限，建议提前拆分。

---

## 问题汇总

| 优先级 | 数量 | 关键问题 |
|:------:|:----:|---------|
| 🔴 P0 | 3 | consumes/soft_after 冲突、Any 字段未填充、result.changes 不存在 |
| 🟡 P1 | 7 | 注册表性能、分类不一致、getattr 绕过、重复代码、字体解析空操作、validate 未调用 |
| 🟢 P2 | 6 | 文档不一致、TOC 暴力搜索、域标脏范围、开关不同步、行数红线 |

---

*审阅版本：v2.0 | 更新日期：2026-03-24*



