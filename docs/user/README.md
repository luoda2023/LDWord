# Alavette Form V1.0 用户文档

这里是面向最终用户的文档源。公开发布时，用户优先阅读发布包根目录中的 PDF：

- `Alavette Form V1.0 - 快速开始.pdf`：第一次使用，目标是在 10 分钟内生成并找到第一份新文档。
- `Alavette Form V1.0 - 用户手册.pdf`：场景教程、概念参考、排障和边界说明。

Markdown 是正文的维护源：

- [Obsidian 入口](00-开始这里.md)
- [快速开始](quick-start.md)
- [完整用户手册](user-guide.md)
- [截图清单](_meta/screenshot-manifest.yml)

直接在 Obsidian 中打开整个 `docs/user/` 文件夹，即可使用 Wiki 链接、图片嵌入和文档导航。构建脚本也会生成一份自包含的 Obsidian 文档包。

## 当前版本口径

V1.0 正式开放四种工作模式：

1. 通用版
2. 试卷版
3. 论文版
4. 公文版

标书版、技术文档版和报告版尚未作为 V1.0 正式入口开放，不应出现在面向用户的功能承诺中。

## 构建

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\export_user_manual_visuals.py
python scripts\build_user_documentation.py
powershell -ExecutionPolicy Bypass -File scripts\windows\export_user_documentation_pdf.ps1
```

构建结果写入 `artifacts/user-docs/v1.0/`。PDF 导出需要本机安装 Microsoft Word。

## 发布验收

发布前必须确认：

- 截图来自当前版本，中文没有方框、乱码或截断；
- 示例文件、截图和正文不含真实用户名、业务资料、密钥或私有路径；
- 所有界面名称与最终程序一致；
- 快速开始可以由首次用户独立完成；
- PDF 每页已渲染检查，没有溢出、孤立标题、空白页或不可读图片；
- 发布包根目录包含快速开始和完整用户手册。
