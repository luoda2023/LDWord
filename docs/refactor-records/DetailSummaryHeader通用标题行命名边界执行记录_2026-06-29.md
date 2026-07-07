# DetailSummaryHeader 通用标题行命名边界执行记录

日期：2026-06-29

## 1. 本轮目标

前几轮已经完成：

- `DetailSummaryCard` 替代共享块内部的 `TemplateSummaryCard`
- `apply_detail_summary_action_button` 替代共享控件内部的模板专属按钮样式命名
- `StyleManagementBlock(rule_control=...)` 替代场景分区样式的自由插槽
- `SceneStyleOverrideSection` 新增 `management_block / rule_control_deck / editing_section` 稳定入口

但 `DetailSummaryCard` 内部仍实例化 `TemplateSummaryHeader`。这会让共享摘要卡继续带着模板专属命名，和“模板管理样式可复用到场景/Workbench”的目标不完全一致。

本轮目标：

```text
DetailSummaryHeader：通用详情摘要标题行
TemplateSummaryHeader：模板详情页旧名兼容
```

## 2. 本轮代码落点

### 2.1 新增 DetailSummaryHeader

文件：

- `src/shared/ui/template_summary_header.py`

变更：

```python
class DetailSummaryHeader(QWidget):
    ...

TemplateSummaryHeader = DetailSummaryHeader
```

判断：

旧名使用“同对象别名”，而不是子类。原因是 Qt 的 `findChild(TemplateSummaryHeader)` 依赖真实类对象；如果旧名只是子类，而实际实例是 `DetailSummaryHeader`，旧查找会失效。

### 2.2 DetailSummaryCard 改用通用 Header

文件：

- `src/shared/ui/template_summary_card.py`

变更：

```python
from src.shared.ui.template_summary_header import DetailSummaryHeader

self.header = DetailSummaryHeader(title, icon_name, parent=self)
```

这样共享摘要卡内部不再依赖模板专属类名。

### 2.3 摘要卡首帧高度同步修复

文件：

- `src/shared/ui/template_summary_card.py`

回归时发现一个旧问题：部分模板详情页在第一次 `processEvents()` 后，`DetailSummaryCard` 的 `minimumHeight` 和 `sizeHint` 已经回到正确内容高度，但实际几何高度还停留在“初始宽度不足时算出的多行高度”。原因是 `_sync_content_height_limit()` 在 min/max 已正确时过早返回，没有推动父布局重新排布。

本轮调整：

- show / resize / set_summary_items 后排队一次延迟高度同步。
- 当 min/max 已正确但实际高度仍不等于内容高度时，继续触发布局刷新。

这样模板页摘要卡能在首帧更快收敛到真实内容高度。

### 2.4 共享 UI 导出

文件：

- `src/shared/ui/__init__.py`

新增导出：

- `DetailSummaryHeader`

旧导出保留：

- `TemplateSummaryHeader`

## 3. 测试守门

更新文件：

- `tests/test_summary_grid.py`
- `tests/test_template_style_detail.py`
- `tests/test_template_page_detail.py`
- `tests/test_ui_exports.py`

验证点：

- `TemplateSummaryHeader is DetailSummaryHeader`。
- `DetailSummaryCard.header` 是 `DetailSummaryHeader`。
- 旧的 `TemplateSummaryHeader` 查找仍然兼容。
- `template_summary_card.py` 使用 `DetailSummaryHeader(`，不再使用 `TemplateSummaryHeader(`。
- 模板摘要卡高度首帧等于内容高度提示。
- 正文排版页通过 `StyleManagementBlock` 内部布局验证摘要和编辑区节奏。
- `src.shared.ui` 导出 `DetailSummaryHeader`。

## 4. 已验证

语法检查：

```powershell
python -X utf8 -m py_compile src/shared/ui/template_summary_header.py src/shared/ui/template_summary_card.py src/shared/ui/__init__.py tests/test_summary_grid.py tests/test_template_style_detail.py tests/test_template_page_detail.py tests/test_ui_exports.py
```

结果：通过。

焦点回归：

```powershell
python -X utf8 -m pytest tests/test_summary_grid.py::test_template_summary_header_keeps_detail_summary_header_compatibility tests/test_summary_grid.py::test_detail_summary_card_uses_detail_summary_header tests/test_template_style_detail.py::test_style_detail_reuses_shared_controls tests/test_template_style_detail.py::test_style_detail_organizes_body_controls_into_cards tests/test_ui_exports.py -q
```

结果：

```text
5 passed
```

宽回归：

```powershell
python -X utf8 -m pytest tests/test_summary_grid.py tests/test_template_style_detail.py tests/test_template_page_detail.py tests/test_ui_exports.py tests/test_scene_panel_architecture.py -q
```

结果：

```text
110 passed
```

## 5. 当前边界

本轮没有把文件名 `template_summary_header.py` 改成 `detail_summary_header.py`。原因：

- 文件移动会牵涉多个旧导入和文档引用，收益低于风险。
- 当前核心目标是实现名、共享卡内部依赖和导出边界先泛化。
- 旧模板详情页继续导入 `TemplateSummaryHeader` 是可接受的兼容用法。

后续如果要继续清理，可以新增 `detail_summary_header.py` 轻量转发模块，再逐步迁移非模板调用。

## 6. 本轮判断

这轮继续消除了共享摘要体系里的模板专属命名残留。

现在摘要卡链路是：

```text
DetailSummaryCard
-> DetailSummaryHeader
-> SummaryGrid
```

模板旧名仍可用：

```text
TemplateSummaryCard = DetailSummaryCard 的兼容子类
TemplateSummaryHeader = DetailSummaryHeader 的兼容别名
```

这让模板管理的成熟样式继续可复用，同时避免新共享模块继续误以为“摘要标题行是模板私有控件”。
