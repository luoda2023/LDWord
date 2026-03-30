# HeadingNumberingPanel 设计需求与修改边界

> 本文档是标题编号面板重构的**唯一设计参照**。

---

## 一、引擎能力

### 占位符 (heading_numbering.py `_PLACEHOLDER_FORMAT`)

| 占位符 | 格式 | 示例 |
|--------|------|------|
| `{nn}` | arabic | 1, 2, 3 |
| `{cn}` | cn_lower | 一, 二, 三 |
| `{CN}` | cn_upper | 壹, 贰, 叁 |
| `{rn}` | roman_lower | ⅰ, ⅱ, ⅲ |
| `{RN}` | roman_upper | Ⅰ, Ⅱ, Ⅲ |
| `{cc}` | circled | ①, ②, ③ |
| `{al}` | alpha_lower | a, b, c |
| `{AL}` | alpha_upper | A, B, C |

### core_style 自动展开 (heading_numbering.py `_CORE_STYLE_AUTO_EXPAND`)

| core_style key | 展开 | 效果 |
|----------------|------|------|
| `arabic` | `{nn}` | 1 |
| `arabic_paren` | `{nn})` | 1) |
| `chinese_lower` | `{cn}、` | 一、 |
| `chinese_upper` | `{CN}、` | 壹、 |
| `chinese_chapter` | `第{cn}章` | 第一章 |
| `chinese_section` | `第{cn}节` | 第一节 |
| `chinese_paren` | `({cn})` | (一) |
| `roman_upper` | `{RN}` | Ⅰ |
| `roman_lower` | `{rn}` | ⅰ |
| `circled` | `{cc}` | ① |
| `circled_paren` | `{cc}` | ① |
| `alpha_upper` | `{AL}` | A |
| `alpha_lower` | `{al}` | a |

> **约束**: UI 所有 core_style key 必须与此表一致。

### Chain 组合

| chain | 含义 | 示例 |
|-------|------|------|
| `current_only` | 仅当前级 | `3` |
| `parent.current` | 上.当前 | `1.3` |
| `parent.parent.current` | 上上.上.当前 | `2.1.3` |

- `chain_separator` = 多级连接符 (默认 `.`)
- 父级用 `reference_core_style`, 当前级用 `display_core_style`

---

## 二、数据模型

### HeadingLevelBindingConfig (template.py L96-112)

| 字段 | 默认 | UI 编辑 | 模式 |
|------|------|---------|------|
| `enabled` | `False` | ✅ | 所有 |
| `display_template` | `""` | ✅ | 专家 |
| `display_core_style` | `"arabic"` | ✅ | 组合 |
| `reference_core_style` | `"arabic"` | ✅ | 组合 |
| `chain` | `"current_only"` | ✅ | 组合/专家 |
| `chain_separator` | `"."` | ✅ | 组合 |
| `title_separator` | `"\u3000"` | ✅ | 组合 |
| `include_in_toc` | `True` | ✅ | 简单 |
| `display_shell` | `"plain"` | ❌ | 旧字段 |
| `ooxml_*` | — | ❌ | 内部 |
| `start_at` | `1` | ❌ | 暂不 |
| `restart_on` | `None` | ❌ | 暂不 |

### HeadingModelConfig (template.py L218-243)

| 字段 | UI 编辑 |
|------|---------|
| `max_heading_levels` (1~8) | ✅ 标题级数 |
| `non_numbered_title_texts` | ✅ 非编号精确匹配 |
| `non_numbered_prefixes` | ✅ 非编号前缀匹配 |

### 持久化策略

- **唯一真相源** = `level_bindings` (thesis.yaml)
- **不存** `active_preset` — UI 启动时比对推断
- config 层零 UI 污染

---

## 三、UI 设计

### 面板布局

```
┌─────────────────────────────────────────────────┐
│ 标题级数 [4▾]  预设方案 [论文标准▾]  [简单 组合 专家] │
├─────────────────────────────────────────────────┤
│ 层级 │ 预览                        │ 目录       │  ← 永远可见
│ H1   │ 第一章                      │  [✓]       │
│ H2   │ 1.1                        │  [✓]       │
│ H3   │（一）                       │  [✓]       │
│ H4   │ a)                         │  [ ]       │
├─── 编辑区 (简单模式隐藏, visibility) ───────────┤
│ H1  外壳[第{}章] 样式[一二三] 引用[1 2 3] 链[仅当前] │
│ H2  ...                                        │
├─── 非编号标题 (折叠) ──────────────────────────┤
│ 精确: 参考文献, 致谢, 摘要, ...                  │
│ 前缀: 附录, 附件, Appendix, ...                 │
└─────────────────────────────────────────────────┘
```

### 三模式

| 模式 | 可见 | 可编辑 |
|------|------|--------|
| 简单 | 预览表 | 预设下拉 + 目录勾选 |
| 组合 | 预览表 + 编辑区 | 外壳/样式/引用/链/分隔符 |
| 专家 | 预览表 + 编辑区 | display_template / chain 直编 |

### 预设交互

- 选预设 → 展开写入 level_bindings → 刷新
- 改任何字段 → `detect_active_preset()` 比对 → 不匹配则显示"自定义"
- "自定义" 项 `setEnabled(False)`, 不可主动选中

---

## 四、KI 设计系统合规

| 规范 | 方式 |
|------|------|
| 36px 行高 | `t.control_height_md` |
| 主题适配 | `get_theme()` + `on_theme_changed()` |
| `:disabled` 样式 | QComboBox/QLineEdit/QCheckBox |
| 弹性布局 | `QSizePolicy`, 不 setFixedWidth (除层级标签) |
| QSS 隔离 | `setObjectName("HeadingNumberingPanel")` + `hn_*` |
| 滚动 | `QScrollArea(NoFrame)` |
| 模式切换 | `setVisible()`, 不 `setEnabled()` |
| 安全清理 | `blockSignals(True) + setParent(None)` |

---

## 五、修改边界

### ✅ 本次改动

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/ui/panels/heading_numbering_panel.py` | ✅ 已创建 | 面板主体 |
| `src/ui/adapters/heading_numbering_adapter.py` | ✅ 已创建 | 数据适配 |
| `src/config/heading_presets.py` | ✅ 已创建 | 预设目录 |
| `src/ui/panels/__init__.py` | ✅ 已创建 | 空包 |
| `src/ui/adapters/__init__.py` | ✅ 已创建 | 空包 |

### 🔜 后续改动 (S6 集成)

| 文件 | 改什么 |
|------|--------|
| `src/ui/panel_registry.py` | 注册 HeadingNumberingPanel |
| `src/ui/bridge.py` | 如需跨面板事件 |

### ❌ 不动

| 文件 | 原因 |
|------|------|
| `src/modules/structure/heading_numbering.py` | 引擎稳定, 79 测试 |
| `src/config/template.py` | 不加 UI 字段 |
| `src/modules/basic/paragraph_style.py` | max_levels 已实现 |
| `defaults/thesis.yaml` | 模板不变 |
| `src/shared/ui/theme.py` | 现有 token 够用 |
