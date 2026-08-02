# Alavette Form

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4)
![Python](https://img.shields.io/badge/Python-3.10--3.12-3776AB)
![License](https://img.shields.io/badge/source%20license-MIT-2ea44f)

**本地优先的 Windows 文档生产与规范化工作台。**

Alavette Form 基于 PySide6 与 python-docx，将原始 Word 文档、处理方案、格式模板、母版和资料包组合为可复用流程。它会在执行前检查复杂对象和资料完整性，并输出规范化 DOCX、变更报告及场景化交付版本。文档默认只在本机处理，不会自动上传。

## 核心能力

- **场景化工作流**：当前提供通用、试卷、论文和公文四种工作模式。
- **方案与模板**：统一管理处理范围、模块开关、页面、正文、标题、编号、表格、目录、题注及页眉页脚。
- **资料包**：组织字段、内容文件、时间计划、图片、附件和多份结构化资料。
- **执行前检查**：识别宏、嵌入对象、修订、批注、隐藏文本、文本框、内容控件和域等高风险内容。
- **可追溯交付**：生成多版本 DOCX、对比稿、JSON/Markdown 报告及场景化交付包。
- **本地优先**：核心文档处理在本机完成；需要联网的可选能力必须由用户显式配置和触发。

## 适用场景

Alavette Form 适合需要重复执行 Word 排版规范、批量套用模板、生成交付版本或保留变更证据的个人与团队。它不是 Microsoft Word 的完整替代品，也不会尝试在没有明确规则时自动改写原稿。

## 环境要求

- Windows 10 或 Windows 11
- Python 3.10～3.12；推荐使用 CPython 3.12 x64
- 部分精确分页及复杂 Word 对象能力依赖本机 Microsoft Office；不可用时应用会降级并给出提示

## 快速开始

在 PowerShell 中运行：

```powershell
# 获取源码
git clone https://github.com/Alouetter/Alavette-Form.git
cd Alavette-Form

# 创建并激活虚拟环境
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装运行时依赖
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 启动桌面界面
python main.py --gui
```

仓库也提供一键脚本：

```powershell
.\install_env.bat
.\start_app.bat
```

## 命令行用法

```powershell
python main.py input.docx --scene path\to\scene.yaml --template path\to\template.yaml --output output
```

主要参数：

- `input`：输入的 `.docx` 文件
- `--scene` / `-s`：方案配置文件（YAML 或 JSON）
- `--template` / `-t`：显式模板配置文件（YAML 或 JSON）
- `--output` / `-o`：输出目录
- `--document-type`：公文模式使用的文种 ID
- `--gui`：启动桌面界面

运行 `python main.py --help` 可查看完整说明。

## 输入与处理边界

- GUI 以 DOCX 为核心输入；Markdown、XLSX 和结构化资料是否可用由工作模式与方案决定。
- XLSX 主要承载批量字段或结构化资料，不作为 Word 版式正文。
- CLI 当前仅直接接收 DOCX。
- 请始终保留原始文档，并在正式交付前人工检查输出结果。

## 源码结构

```text
main.py                 应用入口
src/                    核心运行时代码
defaults/               内置默认配置
config_library/         内置方案与模板
count_profiles/         字数统计规则
icons/                  应用图标与界面资源
licenses/               第三方许可证原文及结构化清单
```

公开仓库只保留运行、构建、许可证合规和必要协作所需内容；测试资料、个人配置、构建产物、日志及真实用户文档不会进入公开发布快照。

## 参与贡献

提交改动前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。缺陷报告应使用脱敏、可复现的最小样例，不要上传真实业务文档、个人信息、密钥或令牌。

安全问题请按 [SECURITY.md](SECURITY.md) 使用 GitHub 私密漏洞报告渠道，不要在公开 Issue 中披露细节。

## 许可证

Alavette Form 的项目自有源码按 [MIT License](LICENSE) 发布，版权所有 © 2026 王云雀Alouette。

第三方依赖、字体、图标和其他资源继续适用各自许可证；概要见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，完整许可文本见 [`licenses/`](licenses/)。因此，桌面二进制发行包不能简单表述为“仅使用 MIT 许可证”。
