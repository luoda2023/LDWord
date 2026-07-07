# 第 48 步：DOCX XML/media Deep Repair 写回器服务化记录
日期：2026-07-06

## 目标

在第 47 步把 DOCX XML/media scanner 拆到 `word_docx_recovery.py` 之后，本步继续迁移真实 DOCX 写回修复器。

迁移到 service 的能力：
- 更新 `[Content_Types].xml`
- 解析可用图片素材路径
- 修复缺失 media 文件
- 移除 orphan media
- 移除未被 XML 引用的 relationship
- 为缺失 relationship 写入新 relationship
- 写出 repaired DOCX
- 重新扫描 repaired DOCX 并生成 deep repair 结果

保留在 `AssetsPanel` 的能力：
- 选择 batch / archive / profile 上下文
- 生成 deep repair artifact id 和 manifest 路径
- 写 JSON / Markdown manifest
- 构造治理 history record
- 追加 history、回填 metadata、保存 archive、刷新 UI

## 新增服务 API

- `docx_image_content_type`
- `update_docx_content_types`
- `available_asset_image_paths`
- `deep_repair_docx_xml_media`

同步保留旧 alias：
- `_question_figure_master_subscription_drift_docx_image_content_type`
- `_question_figure_master_subscription_drift_update_docx_content_types`
- `_question_figure_master_subscription_drift_available_asset_image_paths`
- `_question_figure_master_subscription_drift_docx_xml_media_deep_repair`

## 职责变化

`word_docx_recovery.py` 现在承担完整 DOCX 文件层职责：
- scanner：只读 DOCX 并产出一致性状态
- deep repair：根据 scanner 结果和可用图片素材写出修复后的 DOCX

`AssetsPanel` 的旧函数名现在只是 wrapper：
- `_question_figure_master_subscription_drift_update_docx_content_types`
- `_question_figure_master_subscription_drift_available_asset_image_paths`
- `_question_figure_master_subscription_drift_docx_xml_media_deep_repair`

这样保留了现有调用点，同时把文件解析/写回逻辑从 UI 文件中剥离。

## 测试覆盖

扩展 `tests/test_material_asset_services.py::test_material_asset_service_exposes_public_docx_recovery_api`：
- 使用最小 DOCX zip 构造缺失 media 场景
- 调用 `deep_repair_docx_xml_media`
- 验证 repaired DOCX 存在
- 验证 repaired DOCX 再次扫描为 `xml_media_consistent`
- 验证 missing media repaired count
- 验证 `available_asset_image_paths`
- 验证 `update_docx_content_types`
- 验证 `material_assets` 聚合导出和旧私有 alias

继续保留面板侧真实链路测试：
- file recovery center
- historical DOCX repair
- word XML/media deep repair manifest 和 metadata

## 后续建议

第 49 步建议迁移 word XML/media deep repair 的 artifact / record builder：
- 把 artifact id、payload、markdown 构造下沉到 service
- 把 history record builder 下沉到 service
- `AssetsPanel` 继续只负责 manifest 落盘、history append、metadata 回填和 UI 刷新

完成后，deep repair 链路也会和 file recovery center 一样形成清晰边界：文件服务负责 DOCX，question library service 负责治理记录，panel 负责编排。
