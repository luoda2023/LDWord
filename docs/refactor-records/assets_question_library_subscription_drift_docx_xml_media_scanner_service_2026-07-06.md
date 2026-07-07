# 第 47 步：DOCX XML/media Scanner 独立服务化记录
日期：2026-07-06

## 目标

在第 45、46 步完成 file recovery center 投影、artifact、record 服务化之后，本步把真实 DOCX XML/media 一致性扫描逻辑从 `AssetsPanel` 中拆出，放入独立文件系统服务：

- `src/services/material_assets/word_docx_recovery.py`

本步迁移的是 scanner，不迁移 deep repair 写回器。也就是说：
- service 负责读取 DOCX zip、解析 Word XML / `.rels`、计算关系和媒体一致性状态
- panel 保留 deep repair 改写 DOCX、manifest 写入、history append、metadata 回填、archive save 和 UI 编排

## 新增服务 API

- `normalize_docx_relationship_target`
- `docx_part_relationships_path`
- `docx_image_part_kind`
- `docx_image_part_names`
- `scan_docx_xml_media`

同时保留旧私有 alias：
- `_question_figure_master_subscription_drift_normalize_docx_relationship_target`
- `_question_figure_master_subscription_drift_docx_part_relationships_path`
- `_question_figure_master_subscription_drift_docx_image_part_kind`
- `_question_figure_master_subscription_drift_docx_image_part_names`
- `_question_figure_master_subscription_drift_docx_xml_media_scan`

## 职责变化

`word_docx_recovery.py` 现在负责：
- 判断 DOCX 是否缺失或非法
- 扫描 `word/document.xml`
- 扫描 header/footer XML 中的图片关系
- 解析对应 `.rels`
- 归一化 relationship target 到 `word/media/...`
- 计算 missing relationship、unreferenced relationship、missing media、orphan media
- 输出统一 scan row，供 file recovery center、historical DOCX repair、deep repair 和非题图族流程复用

`AssetsPanel` 现在只保留兼容 wrapper：
- `_question_figure_master_subscription_drift_docx_xml_media_scan`
- `_question_figure_master_subscription_drift_normalize_docx_relationship_target`
- `_question_figure_master_subscription_drift_docx_part_relationships_path`
- `_question_figure_master_subscription_drift_docx_image_part_kind`
- `_question_figure_master_subscription_drift_docx_image_part_names`

这些 wrapper 只转调 service，现有面板调用点和旧测试不需要大面积改名。

## 为什么单独建模块

DOCX scanner 是文件系统能力，不属于 question library 的行投影或 record schema。把它继续塞进 `question_library.py` 会让 service 层重新变胖。

单独模块的好处：
- scanner 可以被题图和非题图素材族共同复用
- scanner 的测试可以脱离 Qt 面板
- 后续 deep repair 写回器可以继续拆到同一文件系统服务族
- `AssetsPanel` 进一步减少纯文件解析逻辑

## 测试覆盖

新增 `tests/test_material_asset_services.py::test_material_asset_service_exposes_public_docx_recovery_api`：
- 使用手工 zip 构造最小 DOCX
- 验证 consistent scan
- 验证 missing media 触发 `xml_media_repair_required`
- 验证 relationship target/path/kind helper
- 验证 `material_assets` 聚合导出和旧私有 alias

保留并继续通过面板用例：
- file recovery center scan
- file recovery center manifest 写入
- historical DOCX repair
- word XML/media deep repair

## 后续建议

第 48 步建议继续抽 deep repair 写回器：
- 将 `_question_figure_master_subscription_drift_docx_xml_media_deep_repair` 移入 `word_docx_recovery.py`
- 同步抽 content types 更新 helper
- 用 fixture 覆盖 missing relationship、unreferenced relationship、missing media、orphan media 的修复路径
- 面板只负责选择输入/输出路径、写 manifest、追加治理记录
