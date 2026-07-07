# Assets 企业/遗留能力边界审计

日期：2026-07-06

## 结论

`AssetsPanel` 里仍保留大量企业素材库/主数据治理流程。它们不是本地 Word 格式化工具的核心路径，应从产品边界上先冻结和隔离，而不是继续作为主线功能拆细。

本次第六步已新增代码边界：

```text
src/ui/panels/assets/enterprise_boundary.py
```

该模块提供稳定 registry，用于标记能力组的处置策略：

- `keep`：本地核心能力，继续保留并服务层化。
- `isolate`：可用但必须隔离，不应扩展为主线。
- `freeze`：企业/远程/治理能力，暂不增强，只保持不破坏。
- `delete_candidate`：删除或归档候选，需要后续活跃使用审计。

## 当前审计范围

基于当前 `src/ui/panels/assets_panel.py` 顶层函数扫描，第五步后主文件仍约 67421 行。主要剩余能力群如下：

| 能力群 | 当前规模 | 边界判断 | 说明 |
| --- | ---: | --- | --- |
| 本地题图基础能力 | 已抽出主线 helper，主文件仍有少量行投影 | `keep` | 题图筛选、排序、标签、metadata、preview reference 是本地生成 Word 的必要能力。 |
| 本地修复审计 | 已抽出 | `keep` | 本地修复/回滚证据有价值，不依赖外部服务。 |
| 轻量共享缓存 | 已抽出 | `isolate` | 本地缓存路径、索引、清理确认可保留，但不继续扩成治理平台。 |
| 远程预览下载 | 少量函数仍在主文件 | `isolate` | 可以作为可选预览来源，但要和远程写回分开。 |
| 远程写回 | 约 173 个函数 | `freeze` | 需要外部素材库/主数据服务，不是本地格式化核心。 |
| 企业鉴权/外部权限/签名 URL | 约 34 个函数，包含在远程写回中 | `freeze` | 只有企业素材库后端存在时才成立。 |
| 主数据版本/注册表/订阅锁 | 约 42 个函数 | `freeze` | 假设存在跨包主数据中心，本项目当前不拥有该系统。 |
| 订阅漂移恢复 | 约 227 个函数 | `freeze` | 这是企业事故恢复流程，不属于格式化工具主线。 |
| 非题图素材族远端治理 | 约 245 个函数 | `delete_candidate` | 距离当前本地题图路径最远，后续应做活跃使用审计。 |

## 能力分类

代码 registry 中的能力 key：

```text
local_question_figures                         keep
local_question_audit                           keep
lightweight_shared_cache                       isolate
remote_preview_download                        isolate
enterprise_remote_auth                         freeze
remote_writeback                               freeze
master_data_governance                         freeze
subscription_drift_recovery                    freeze
non_question_asset_family_remote_governance    delete_candidate
```

## 为什么不继续拆远程写回

远程写回不是“把代码搬到新模块就健康”的问题。它的业务假设是：

1. 有中心化素材库。
2. 有主数据版本和 registry。
3. 有远端 current snapshot。
4. 有 writeback URL、signed URL refresh、enterprise auth、external permission callback。
5. 有批量事务、回滚、二次补偿、失败队列、SLA 和后台任务消费者。

当前项目没有内置这些后端契约。继续把这些函数拆成主线模块，会让本地格式化工具误变成企业素材治理平台。

## 保留主线

主线应继续围绕：

1. 本地素材选择。
2. 批量导入素材路径和基础 metadata。
3. 题图与模板占位符匹配。
4. 图片 preview 和本地 fallback。
5. Word 输出时稳定替换图片。
6. 本地修复/回滚审计。
7. 轻量缓存，避免重复下载。

## 隔离策略

### `keep`

保留并继续优化。后续应从 `src/ui/panels/assets/` 进一步沉到服务层：

```text
src/services/material_assets/
```

### `isolate`

保留但不扩大。远程预览和共享缓存只为本地体验服务，不应引入写回、SLA、审批、治理队列。

### `freeze`

暂不增强、不新增测试面、不继续 UI 主线拆分。只做必要兼容修复。未来如果确实需要企业素材库，应重建为：

```text
src/services/enterprise_assets/
src/connectors/enterprise_assets/
```

而不是继续留在 `AssetsPanel`。

### `delete_candidate`

先做活跃使用审计。若没有真实入口、真实后端或真实用户流程，应归档或删除。

## 后续建议

第七步建议不再从远程/治理函数开始，而是做服务层抽取：

```text
src/services/material_assets/question_figures.py
src/services/material_assets/cache.py
src/services/material_assets/audit.py
```

同时将远程/治理函数群列为 enterprise/legacy workstream，单独评估：

1. 是否有真实后端契约。
2. 是否有真实 UI 入口。
3. 是否有真实用户工作流。
4. 是否仍需保留对应测试。
5. 是否可以隐藏、冻结、归档或删除。

## 验收证据

本次第六步应以以下证据验收：

1. `enterprise_boundary.py` 存在并可导入。
2. `src.ui.panels.assets` 包导出边界 registry。
3. 远程写回、订阅漂移、非题图远端治理被分类为 `freeze` 或 `delete_candidate`。
4. 新模块不 import `assets_panel.py`。
5. 定向测试通过。
6. 工程门禁通过。
