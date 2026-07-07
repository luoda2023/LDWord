# 第 51 步：Word XML/media Deep Repair Metadata 回填服务化记录
日期：2026-07-06

## 目标

在第 49 步完成 deep repair artifact/record builder 服务化、第 50 步完成 entries/actions 投影服务化之后，本步骤继续拆出 deep repair profile metadata 回填中的可测试业务逻辑。

本步骤迁移的是无 UI 依赖的纯数据逻辑：
- 从 deep repair record 反解析 source/asset_id 命中集合
- 生成 profile asset item metadata patch
- 根据 payload metadata 的 source/asset_id 命中目标素材
- 返回更新后的 payload 列表和 updated 标记

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_source_asset_pairs`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_metadata_patch`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_payloads_with_metadata`

同步补齐：
- `src/services/material_assets/__init__.py` 聚合导出
- `question_library.py` 旧私有 alias
- `AssetsPanel` 本地 metadata-to-profile wrapper
- `tests/test_material_asset_services.py` patch、payload 更新、无命中分支和 alias 断言

## 职责变化

`question_library.py` 现在负责：
- 从 `subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_items` 中提取 source/asset_id
- 把 deep repair record 字段映射到 `master_subscription_drift_*` metadata 字段
- 对 payload 列表进行命中更新
- 在没有 source/asset_id 或 payload 未命中时返回 `updated=False`

`AssetsPanel` 现在只负责：
- 调用服务函数获得新 payloads 和 updated
- 在 updated 时写回 `profile.asset_items`

## 为什么这样拆

metadata 回填原来在面板里同时做“record 字段映射、payload 命中、profile 写回”。其中前两件是纯业务规则，应该可在服务测试里验证；最后一件是对 `EntityProfile` 的副作用，仍留在面板即可。

这样拆以后：
- deep repair 的 record、projection、metadata 三段治理逻辑都在 service 层有稳定入口
- 面板不再理解 deep repair metadata 字段清单
- 后续如果要调整 metadata schema，只需要改服务和服务测试

## 测试覆盖

扩展 `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`：
- metadata patch 包含 status 和计数字段
- source/asset_id pairs 能从 deep repair record items 中提取
- 命中的 payload 被写入 deep repair metadata
- 未命中的 payload 保持不写入 deep repair metadata
- 全部未命中时返回 `updated=False`
- `material_assets` 聚合导出和 `question_library` 私有 alias 保持兼容

继续保留 `tests/test_assets_panel_architecture.py` 的真实面板侧 metadata 回填验证，确保 wrapper 写回 `profile.asset_items` 的副作用没有丢。

## 当前剩余边界

本步骤没有迁移：
- file recovery center metadata 回填
- historical DOCX repair metadata 回填
- 其他 subscription drift recovery metadata 回填
- `EntityProfile` 本身的写操作

后续第 52 步可以选择：
- 用同样模式抽 file recovery center / historical DOCX repair metadata patch
- 或转向 `non-question asset family recovery`，开始削减 `AssetsPanel` 后半区的大块治理逻辑
