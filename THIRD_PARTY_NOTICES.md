# Third-Party Notices

LDWord 使用并随发行包提供以下第三方软件与资源。
每个组件继续适用其原始许可证；完整原文位于 `licenses/` 目录，也可在软件的“第三方组件”窗口中查看。

| 组件 | 版本 | 用途 | 本发行版采用许可证 |
|---|---|---|---|
| Alavette Flow source-derived modules | 2026-07-16 source snapshot | AI 会话消息、取消、事件与 Provider 适配基础 | MIT |
| Python | 3.12.10 | 应用运行环境 | PSF-2.0 |
| Qt for Python (PySide6) | 6.11.1 | 桌面界面与窗口组件 | LGPL-3.0 |
| python-docx | 1.2.0 | Word 文档读写 | MIT |
| lxml | 6.1.1 | XML 文档处理 | BSD-3-Clause |
| latex2mathml | 3.79.0 | LaTeX 公式转换为 MathML | MIT |
| olefile | 0.47 | MathType/OLE 复合文档解析 | BSD-2-Clause + PIL |
| typing_extensions | 4.16.0 | Python 类型兼容支持 | PSF-2.0 |
| Pillow | 12.3.0 | 图片读取与处理 | MIT-CMU |
| markdown-it-py | 4.2.0 | Markdown 内容解析 | MIT |
| mdurl | 0.1.2 | Markdown 链接地址处理 | MIT |
| PyYAML | 6.0.3 | YAML 配置读取 | MIT |
| openpyxl | 3.1.5 | Excel 工作簿读写 | MIT |
| et_xmlfile | 2.0.0 | OpenXML 流式写入 | MIT |
| pypdfium2 / PDFium | 5.11.0 | PDF 页面渲染 | Apache-2.0 / BSD |
| pywin32 | 312 | Windows 系统与 Office 集成 | PSF-2.0 |
| Lucide Icons | 内嵌快照 | 应用界面图标 | ISC + MIT |
| OpenSSL | 3.0.16 | 随发行包提供的加密运行库 | Apache-2.0 |

## Lucide 与 Feather

应用界面内嵌 Lucide Icons 的 SVG 路径。Lucide 采用 ISC 许可证；其中部分图标源自 Feather Icons，并适用 MIT 许可证。完整官方声明随 `licenses/static/lucide/LICENSE` 提供。

## Qt for Python

PySide6、Shiboken6 与 Qt 并非 MIT 组件。上游社区版声明可选 LGPLv3/GPLv3；本发行版采用 LGPLv3，并随附 LGPLv3 及其所引用的 GPLv3 原文。

## Alavette Flow 源码派生模块

AI 文档助手中的消息合同、协作式取消、公开运行时事件和 OpenAI-compatible 流式适配器，基于 Alavette Flow 的 MIT 许可实现进行裁剪与重构。完整 MIT 许可随 `licenses/static/alavette-flow/LICENSE` 提供。LDWord 不在运行时依赖本地 Alavette Flow 工作区。

## 发行原则

- 项目自身代码：MIT。
- 第三方软件、图标和二进制：保留各自原始许可。
- `licenses/manifest.json` 是应用内许可浏览器和发行检查使用的结构化清单。
