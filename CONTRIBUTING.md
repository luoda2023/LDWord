# Contributing

感谢参与 Alavette Form。提交改动前，请先确认变更符合本地优先、原稿保护、显式授权和可追溯交付原则。

## 开发流程

1. 使用受支持的 Python 版本创建独立环境并运行 `install_env.bat`。
2. 从短生命周期分支完成单一主题改动，不提交 `.venv/`、构建产物、日志、用户资料或真实文档。
3. 为行为变化补充或更新测试和文档。
4. 运行 `python scripts/engineering_gate.py`；影响场景能力时再运行 `python scripts/verify_scene_matrix_release_gate.py`。
5. 提交 Pull Request，说明用户影响、风险、验证命令和隐私/许可影响。

## 代码与测试

- 保持 UI、应用服务、领域模型和基础设施边界；不要把业务规则重新堆入 Panel。
- 修复缺陷时优先提供可复现的回归测试。
- 测试数据必须合成或彻底脱敏，不得包含客户、单位或个人资料。
- 新增依赖必须说明用途、许可证和二进制发布影响，并同步许可清单与发布锁文件。

## 安全问题

安全漏洞不要通过公开 Issue 提交，按 `SECURITY.md` 使用私密报告渠道。
