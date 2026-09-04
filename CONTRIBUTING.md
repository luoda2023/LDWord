# Contributing

感谢你关注 LDWord。我们欢迎边界清晰、可复现并且不会损害用户文档与隐私的改进。

## 开始之前

- 缺陷请先确认可以在最新代码上复现，并使用合成或彻底脱敏的样例。
- 功能建议请说明使用场景、预期收益和不在范围内的内容。
- 安全漏洞请按 [SECURITY.md](SECURITY.md) 私密报告，不要创建公开 Issue。
- 较大的行为或架构改动，建议先创建 Issue 对齐范围，再投入实现。

## 本地开发

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

提交前至少运行：

```powershell
python -m compileall -q main.py src
python main.py --help
```

如果改动覆盖已有自动化测试，请同时运行相关测试并在 Pull Request 中记录命令和结果。

## Pull Request 要求

- 一个 Pull Request 聚焦一个主题，并说明用户可见影响。
- 行为变化应补充测试或明确可复现的人工验证步骤。
- 不要提交 `.venv/`、构建产物、日志、个人配置、真实文档或任何凭据。
- 新增依赖、字体、图标或外部资源时，必须说明许可证和二进制分发影响，并同步第三方许可清单。
- 保持 UI、应用服务、领域模型和基础设施之间的边界，不要把新的业务规则直接堆入界面组件。

## 隐私与测试数据

测试数据必须为合成数据或经过彻底脱敏。请特别检查文件属性、批注、修订记录、嵌入对象和 DOCX 包内 XML，它们可能保留作者、单位或其他个人信息。
