# 资料包旧表现层参考基线

这里完整保留资料包旧 UI/UX 的 53 个 Python 源文件，来源为：

- Git commit：`a0f8cf1060c1a8e900e875af85e12a6bab667270`
- 原路径：`src/ui/panels/assets/`
- 最后主要 UI 提交：`c640dd5 Refactor template scene and workbench interfaces`

这些文件用于视觉、交互和布局恢复，不属于当前运行时模块。它们仍引用已经淘汰的
`EntityArchive`、`EntityProfile`、`MaterialBatchSelection` 和
`MaterialExecutionContext`，因此不能直接重新加入 `src`。

当前运行面板在 `src/ui/panels/assets_panel.py` 中复用了原设计的
`MasterDetailShell`、`NavigationCard`、`Card`、分区结构和响应式尺寸策略，
数据读写则统一使用 Material Package V1 应用服务。
