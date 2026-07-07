# Workbench 最近结果交付显示名与日志链路归一执行记录

日期：2026-06-30

## 背景

前几轮已经把交付版本显示名下沉到 `src/config/delivery_preset_display.py`，并接入了场景面板、模板预览、输出入口、运行时 `{preset_label}`、报告 payload 的 raw/display 分层。但这还不够：用户真正判断“刚刚跑出来的是什么”的位置，往往是 Workbench 的最近结果、产物清单、执行历史日志和快速执行日志。

本轮复查发现，末端结果链路仍有断点：`RecentRunState` 和执行日志直接把 `output_paths` / `compare_paths` / `intermediate_paths` 的 key 当作用户标签展示，例如 `review: C:/tmp/review.docx`、`输出[review]...`。这会让前端选择控件已经变成“审阅稿”，跑完又退回 `review`，形成明显的理解断层。

## 与模板管理一致性的判断标准

模板管理侧已经形成了比较清晰的交互模型：用户看到的是业务名称，系统内部保留稳定字段。场景规划和 Workbench 也应遵守同一套边界：

- 用户可见的主标签使用业务显示名，例如 `final -> 最终 Word`、`review -> 审阅稿`、`answer_key -> 答案版`。
- 机器可追踪的 key 不改，例如 `output_paths["review"]`、`ArtifactItemState.group_id == "review"`、问题队列的 `repair_target_key == "review"`。
- 自定义交付版本不被强行翻译，继续保留用户自己的 label。
- 非交付版本产物不套交付词库，例如资料清单、资料包、样本清单仍显示自身 key。

这套规则与模板管理的“显示名/源字段分层”一致：主界面少讲技术 ID，但调试、路由、修复、报告追溯仍能找到原始字段。

## 本轮打通的链路

1. 最近结果摘要
   - `WorkbenchExecutionAdapter.build_recent_run_state()` 原先直接用 `_artifact_label(paths)` 拼接 raw key。
   - 现在 output / compare / intermediate 通过共享显示投影输出交付显示名。
   - 示例：`review: C:/tmp/review.docx` 改为 `审阅稿: C:/tmp/review.docx`。

2. 最近结果产物清单
   - `ArtifactItemState.label` 对交付类产物改为显示名。
   - `ArtifactItemState.group_id` 继续保留 raw preset id。
   - `ArtifactItemState.group_label` 对交付类产物改为显示名，最近结果面板分组显示为“交付 审阅稿”。

3. 报告产物分组
   - 报告文件仍通过文件名中的 raw key 推断所属交付组。
   - 报告行的 label 仍是序号，例如 `1`，避免把“第几个报告”和“交付版本”混淆。
   - 报告所属组显示为交付显示名，例如 `source_review_changes.md` 所在组显示“审阅稿”。

4. 执行历史日志
   - `WorkbenchExecutionController._sync_execution_history_result()` 不再直接展示 path map key。
   - output / compare / intermediate 日志统一走交付显示名。

5. 快速执行详情日志
   - `QuickExecutionDetail.set_execution_result()` 同步改为共享显示投影。
   - 用户最常看到的日志从 `输出文件[review]` 改为 `输出文件[审阅稿]`。

## 复用方式

新增公共投影函数：

- `src/ui/adapters/workbench_execution_adapter.py`
  - `workbench_artifact_display_items(paths, delivery_preset_labels=False)`

这个函数只负责“把 path map 转成用户可读的 label/path 列表”，不改变原始字典。最近结果摘要、执行历史日志、快速执行日志都复用它，避免面板各自维护一份 label 转换逻辑。

仍然复用已有交付词库：

- `src/config/delivery_preset_display.py`
  - `delivery_preset_display_name(...)`

也就是说，本轮没有新增第二套显示名目录，避免以后模板管理、场景配置、Workbench 结果各说各话。

## 边界裁决

本轮没有把所有 artifact label 一刀切翻译，原因如下：

- `material_manifest_paths` 是资料清单，不是交付版本；显示 `material` 仍是资料域 key。
- `material_package_paths` 是资料包产物，`zip/report` 是包内角色，不是交付版本。
- `scene_sample_manifest_paths` 是样本库入口，和交付版本无关。
- 问题队列与修复路由仍需要 raw key，例如 `output_target.review.warning`、`repair_target_key == "review"`，否则自动定位会丢锚点。

因此正确边界是：交付类产物主标签人话化，非交付类产物保持自己的领域标签；机器锚点永远不被展示名替换。

## 已验证行为

新增和更新的验证点：

- `test_execution_adapter_preserves_delivery_artifact_paths`
  - 保证 raw path map 仍是 `review/final`。
  - 保证最近结果显示 `审阅稿`、`最终 Word`。
  - 保证报告分组显示 `审阅稿`，但 `group_id` 仍是 `review`。

- `test_execution_adapter_recent_run_uses_shared_delivery_display_name_for_standard_ids`
  - 覆盖 `answer_key -> 答案版` 的标准 ID 显示链路。

- `test_quick_execution_detail_logs_delivery_artifacts`
  - 保证快速执行日志显示 `输出文件[审阅稿]`、`对比稿[审阅稿]`、`中间产物[审阅稿]`。

执行结果：

- `python -m py_compile ...` 通过。
- `pytest tests/test_recent_run_panel.py tests/test_workbench_execution_center.py tests/test_quick_execution_detail_architecture.py -q`
  - 149 passed。

## 剩余问题

1. 输出目标预检的问题文案仍会出现 raw preset id
   - 例如 `review 输出文件已存在，将被覆盖`。
   - 这是问题队列和 pipeline preflight message 的下一处断点。
   - 建议下一轮把 preflight item 增加 `display_label`，主标题显示“审阅稿”，source note 保留 `preset_id=review`。

2. `RecentRunState.artifact_label` 仍允许调用方传入任意文本
   - 当前真实执行链路已经通过 adapter 生成显示名。
   - 但面板组件自身是通用显示器，如果外部手工塞入 `输出[review]`，它仍会照实显示。
   - 后续可以逐步约束：artifact label 只能由 adapter 生成，面板不再接受手写聚合字符串。

3. 文档和 JSON manifest 仍以 raw key 为主
   - 这对机器消费是正确的。
   - 但面向用户打开的 Markdown 报告可以补一层 display map，例如 `preset_id: review` 与 `display_label: 审阅稿` 并列。

4. 视觉验收还缺最近结果截图
   - 本轮通过单元和组件测试确认链路。
   - 若继续追求优秀设计，应补一张最近结果面板运行后截图，核对“交付 审阅稿”分组、产物行文本、按钮密度与模板管理块是否一致。

## 下一步建议

优先做“输出目标预检与问题队列显示名归一”。这条链路离用户决策最近：当系统提示输出会覆盖、路径重复、目录不可写时，主文案应该说“审阅稿输出文件已存在”，而不是 `review 输出文件已存在`。raw id 应降到 tooltip、source note 或 issue target 中。

其次再清理报告 Markdown 的交付名称展示，把“用户读报告”和“系统读 JSON”分成两层。这样模板管理、场景配置、执行前预览、运行中日志、执行后产物、报告回看才算真正闭环。
