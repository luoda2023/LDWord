# LDWord

<p align="center">
  <strong>本地优先的 Windows 文档生产与规范化工作台</strong>
</p>

<p align="center">
  <a href="#运行环境"><img alt="Windows 10 / 11" src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?style=flat-square&logo=windows11&logoColor=white"></a>
  <a href="pyproject.toml"><img alt="Python 3.10–3.12" src="https://img.shields.io/badge/Python-3.10--3.12-3776AB?style=flat-square&logo=python&logoColor=white"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-2EA44F?style=flat-square"></a>
</p>

<p align="center">
  <a href="#为什么选择-ldword">为什么选择</a> ·
  <a href="#基本工作流程">工作流程</a> ·
  <a href="#从源码运行">源码运行</a> ·
  <a href="#常见问题">常见问题</a> ·
  <a href="#许可证">许可证</a>
</p>

---

LDWord 基于 PySide6 与 python-docx，将原始 Word 文档、处理方案、格式模板、母版和资料包组合为可复用流程。它会在执行前检查复杂对象和资料完整性，并输出规范化 DOCX、变更报告及场景化交付版本。文档默认只在本机处理，不会自动上传。

## 为什么选择 LDWord？

复杂 Word 文档的处理通常不只是修改字号和行距。论文、试卷、公文和通用业务文档各有不同的页面、标题、编号、表格、目录、题注及交付要求；规则往往分散在样例、模板和人工经验中，重复执行费时，也容易遗漏修订、批注、宏、文本框或嵌入对象等特殊内容。

**LDWord** 将原始 DOCX、处理方案、格式模板、母版和资料包组织在同一个桌面工作台中。已经确认的规则可以重复使用；正式处理前，应用会检查文档风险和资料完整性，再根据所选配置生成文档和报告。核心处理默认在本机完成，文档不会自动上传。

- **统一工作台** — 当前提供通用、试卷、论文和公文四种工作模式
- **规则复用** — 将页面、正文、标题、编号、表格、目录、题注和页眉页脚规则保存在模板中
- **执行前检查** — 识别宏、嵌入对象、修订、批注、隐藏文本、文本框、内容控件和域等特殊内容
- **配置分工明确** — 方案控制处理范围和风险策略，模板定义版式，资料包组织字段、图片、附件和结构化内容
- **保留处理记录** — 根据工作模式生成 DOCX、对比稿、JSON/Markdown 报告或场景化交付包
- **本地优先** — 核心文档处理在本机完成；需要联网的可选能力必须由用户显式配置和触发

LDWord 适合需要重复执行 Word 排版规范、批量套用模板、生成交付版本或保留变更证据的个人与团队。它不是 Microsoft Word 的完整替代品，也不会在缺少明确规则时擅自改写原稿。

## 当前工作模式

| 模式 | 主要用途 |
| --- | --- |
| 通用 | 按选定方案和模板处理常规 DOCX 文档 |
| 试卷 | 处理试卷类文档及其结构化资料 |
| 工程文档 | 工程界文档生成专家：可研/初设/招投标/施组/专项方案/交底/结算/概算等分阶段大纲与报告 |
| 论文 | 统一论文类文档的页面、正文、标题、编号、表格和题注等格式 |
| 公文 | 按文种及相应配置处理公文类文档 |

不同模式共享相同的方案、模板、检查和执行基础，但可用字段、资料类型和交付规则可能不同。

## 工程文档版（工程界文档生成专家）

工程文档版把工程项目按行业惯例划分为六个阶段，内置对应的大纲、要素提问与自检清单，
供 AI 按阶段生成不同文本并汇总成一份完整报告文档：

| 阶段 | 内置文档类型 |
| --- | --- |
| 决策立项 | 可行性研究报告、项目建议书、投资估算 |
| 设计报批 | 初步设计说明、设计概算、施工图设计说明 |
| 招投标与合同 | 招标文件、投标文件、施工/分包/采购合同 |
| 施工实施 | 施工组织设计、专项施工方案、技术交底、工艺标准 |
| 竣工结算 | 工程结算书、结算审计方案、签证索赔报告 |
| 贯穿造价分析 | 造价分析手册、定额分析、目标成本测算、PPT 汇报大纲 |

- 在标题栏切换到「工程文档版」后，进入「AI 文档助手」直接说“写一份可行性研究报告 / 施工组织设计 /
  专项施工方案 / 工程结算书……”即可按对应阶段大纲起草。
- AI 起草默认按整篇输出；对长文档会自动按大纲逐章调用模型并顺序拼接成一份完整 Markdown 草稿，
  再编译为可编辑的 DOCX。
- 大纲数据位于 `config_library/engineering_stages/*.json`，可按需扩展阶段与文档类型。

## 基本工作流程

| 阶段 | 操作 | 结果 |
| --- | --- | --- |
| 1. 准备 | 选择原始 DOCX；按需要加入字段、图片、附件或结构化资料 | 待处理文档和资料集合 |
| 2. 配置 | 选择工作模式、处理方案、格式模板和输出位置 | 本次任务的执行配置 |
| 3. 检查 | 查看资料完整性和复杂 Word 对象提示 | 可执行、需确认或应阻断的检查结果 |
| 4. 执行 | 确认后运行处理流程 | 新的 DOCX、报告或交付文件 |
| 5. 复核 | 对照原稿检查内容、分页和版式 | 可供继续编辑或正式交付的版本 |

应用不会代替最终人工复核。涉及正式公文、论文提交、考试材料或其他重要交付时，应在 Microsoft Word 中打开输出文件并完成最后检查。

## 方案、模板与资料包

- **方案**：决定启用哪些处理模块、采用什么风险策略，以及生成哪些交付内容。
- **模板**：保存页面、字体、段落、标题、编号、表格、目录、题注和页眉页脚等版式规则。
- **母版**：为特定工作模式提供可复用的文档结构或基准内容。
- **资料包**：集中管理字段、内容文件、时间计划、图片、附件和多份结构化资料。

这几类配置彼此独立，便于在不改动原始文档的情况下复用同一套处理规则，或为不同任务组合不同配置。

## 输入、输出与边界

### 输入

- GUI 以 DOCX 为核心输入。
- Markdown、XLSX 和其他结构化资料是否可用，由当前工作模式和方案决定。
- XLSX 主要用于批量字段或结构化资料，不作为 Word 版式正文。
- CLI 当前只直接接收 DOCX。

### 输出

根据工作模式和方案，应用可以生成：

- 处理后的 DOCX
- 对比稿或其他辅助版本
- JSON/Markdown 变更报告
- 包含多个文件的场景化交付目录

### 已知边界

- 精确分页和部分复杂 Word 对象能力可能依赖本机 Microsoft Office；不可用时应用会降级或提示。
- 自动化处理无法覆盖所有人工排版判断，特别是高度定制的版式、浮动对象和跨页布局。
- 应始终保留原始文档，并在正式交付前人工检查输出结果。
- 当前版本以 Windows 桌面环境为主要运行目标。

## 运行环境

- Windows 10 或 Windows 11
- Python 3.10～3.12；推荐使用 CPython 3.12 x64
- 源码运行需要安装 `requirements.txt` 中的依赖
- 部分能力可能调用本机 Microsoft Office

## 从源码运行

> [!NOTE]
> 当前仓库提供源码运行方式。安装版或便携版会在完成相应的打包、许可核对和发布验证后，通过官网 https://dicad.cn 提供。

在 PowerShell 中运行：

```powershell
# 获取源码（源码包可从 https://dicad.cn 下载）
cd LDWord

# 创建并激活虚拟环境
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装运行时依赖
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 启动桌面界面
python main.py --gui
```

也可以使用仓库提供的 Windows 脚本：

```powershell
# 安装或更新环境
.\install_env.bat

# 启动桌面界面
.\start_app.bat

# 带控制台启动，便于查看诊断信息
.\start_app_debug.bat
```

## 文档体检

体检工具用于只读分析 DOCX：统计字数与内容元素，检查修订痕迹、批注和
文档属性中的个人信息（作者、公司等），帮助你在正式交付前完成脱敏与
风险复核。体检不会修改原文档。

GUI：偏好设置 → 关于软件 → 文档体检 → 选择文档并体检。

命令行：

```powershell
python main.py report.docx --inspect
```
报告会同时输出到控制台，并保存在文档同目录的 *_体检报告.txt* 中。

## 基本使用

1. 启动应用并选择工作模式。
2. 添加需要处理的 DOCX。
3. 选择方案和模板；按需要补充母版或资料包。
4. 检查应用给出的资料完整性和文档风险提示。
5. 选择输出位置并执行。
6. 打开生成的文档和报告，完成最终人工复核。

## 命令行

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

## 数据、隐私与安全

- 核心文档处理默认在本机完成，应用不会自动上传用户文档。
- 需要联网的可选能力必须由用户显式配置和触发；其数据处理方式还取决于用户选择的服务提供方。
- 不要把真实业务文档、个人资料、密钥、令牌或证书上传到 Issue、Pull Request 或公开讨论中。
- 分享日志、报告或复现样例前，应检查文件正文、属性、批注、修订记录和嵌入对象，并完成脱敏。
- 发现安全漏洞请通过官网 https://dicad.cn 提供的渠道私密报告，具体要求见 [SECURITY.md](SECURITY.md)。

## 常见问题

<details>
<summary><strong>LDWord 会覆盖原始文档吗？</strong></summary>

应用以生成新的输出文件为主要工作方式。无论采用何种流程，都建议保留一份未处理的原始文档，并将输出写入单独目录。

</details>

<details>
<summary><strong>处理文档时必须安装 Microsoft Office 吗？</strong></summary>

多数基于 DOCX 结构的处理不要求启动 Microsoft Word。精确分页、部分复杂对象识别或 Office 兼容能力可能依赖本机 Microsoft Office；不可用时，应用会降级或给出提示。

</details>

<details>
<summary><strong>文档会被发送到网络服务吗？</strong></summary>

核心处理默认在本机完成，不会自动上传文档。只有用户主动配置并触发联网能力时，相关数据才可能发送给所选服务提供方；使用前应确认该服务的隐私政策和数据处理范围。

</details>

<details>
<summary><strong>为什么处理完成后仍然需要人工复核？</strong></summary>

DOCX 可以包含浮动对象、域、修订、嵌入内容和依赖 Word 排版引擎的布局。自动化流程可以执行明确规则并报告已知风险，但不能替代对内容准确性、分页和最终视觉效果的人工判断。

</details>

<details>
<summary><strong>目前支持哪些文件类型？</strong></summary>

GUI 和 CLI 均以 DOCX 为核心。XLSX、Markdown、图片和附件可以作为部分工作模式的辅助资料，但是否可用取决于当前方案，不等同于把这些文件直接作为 Word 正文处理。

</details>

## 开发与贡献

缺陷报告、功能建议和代码贡献都应说明实际使用场景与验证方式。提交改动前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，并遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

复现文档必须使用合成数据或经过彻底脱敏的内容。安全问题不要通过公开 Issue 报告。

### 源码结构

公开仓库只保留运行、许可证合规和必要协作所需内容。主要目录如下：

```text
main.py                 应用入口
src/                    核心运行时代码
defaults/               内置默认配置
config_library/         内置方案与模板
count_profiles/         字数统计规则
licenses/               第三方许可证原文及结构化清单
requirements.txt        运行时依赖
pyproject.toml          Python 项目元数据
```

测试资料、个人配置、构建产物、日志和真实用户文档不会进入公开发布快照。

### 协作文档

| 文档 | 用途 |
| --- | --- |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 开发环境、提交规范与验证要求 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 社区协作行为准则 |
| [SECURITY.md](SECURITY.md) | 支持范围与漏洞报告方式 |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | 第三方组件及许可说明 |

## 许可证

LDWord 的项目自有源码按 [MIT License](LICENSE) 发布，版权所有 © 2026 LUODA。

第三方依赖、字体、图标和其他资源继续适用各自许可证。概要见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，结构化依赖清单见 [`licenses/manifest.json`](licenses/manifest.json)，完整许可文本见 [`licenses/`](licenses/)。

MIT 许可证适用于项目自有源码，不会改变第三方组件原有的许可条件。分发桌面二进制版本时，还需要同时遵守随包组件的许可证和通知要求。
