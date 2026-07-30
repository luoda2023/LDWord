# Alavette Form V1.0

Windows 本地优先的场景化文档生产与规范化工作台（**PySide6 + python-docx**）。

Alavette Form 将原始文档、处理方案、格式模板、母版和资料包组合为可复用流程，在执行前检查复杂 Word 对象与资料完整性，并生成规范化 DOCX、变更报告和场景化交付版本。文档默认仅在本机处理，不会自动上传。

## 产品能力

- **7 个工作模式**：通用版、试卷版、论文版、标书版、公文版、技术文档版、报告版
- **方案配置**：控制处理范围、模块开关、风险策略和交付预设
- **模板管理**：配置页面、正文与标题、编号、表格、页眉页脚、目录和题注
- **资料包**：管理字段、内容文件、时间计划、图片、附件和多份资料
- **执行安全**：检查宏、嵌入对象、修订、批注、隐藏文本、文本框、内容控件和域等风险
- **可追溯交付**：支持多版本 DOCX、对比稿、JSON/Markdown 报告及场景化交付包

## 输入边界

- GUI 以 DOCX 为核心输入；Markdown、XLSX 和结构化资料由具体工作模式与方案决定是否可用
- XLSX 主要用于批量字段或结构化资料，不作为 Word 版式正文
- CLI 当前仅接受 DOCX，并可显式指定方案、模板和输出目录
- 精确 Word 分页和部分复杂对象能力可能依赖本机 Microsoft Office；不可用时软件会降级并提示

## 当前状态

- 当前 GUI 绑定已统一迁移到 **PySide6**
- 项目自身源码按 **MIT** 发布
- 第三方软件与界面资源仍保留各自许可证，概要见 `THIRD_PARTY_NOTICES.md`，完整原文见 `licenses/`

产品范围、需求边界和验收口径见：

- `docs/product/Alavette_Form_V1.0_Reverse_Engineered_PRD.md`
- `docs/product/Alavette_Form_V1.0_P0_Execution_Tracker.md`

## 环境要求

- Windows（提供 `.bat` 启动与打包脚本）
- Python 3.10+

## 快速开始

```powershell
# 1) 安装依赖
.\install_env.bat

# 2) 启动 GUI
.\start_app.bat

# 3) 带控制台启动
.\start_app_debug.bat
```

也可以直接运行：

```powershell
python main.py --gui
```

## 打包发布

```powershell
.\package_release.bat
```

默认输出目录：

- `dist/Alavette-Form_V1.0/`
- `dist/Alavette-Form_V1.0.zip`

打包脚本会：

- 使用 `PyInstaller`
- 从 `main.py` 构建桌面应用
- 带上 `defaults/`
- 带上 `LICENSE`
- 带上 `THIRD_PARTY_NOTICES.md`
- 根据当前虚拟环境生成 `licenses/manifest.json`，并带上全部原始许可文件
- 清理未使用的 Qt add-on payload
- 生成压缩发布包

## MIT 开源发布口径

本项目遵循与 `0.2 LTS` 一致的发布口径：

- **项目自身源码：MIT**
- **第三方依赖：保持各自许可证**
- **桌面二进制分发：仍需遵守 Qt / PySide6 的许可证要求**

因此：

- 可以说“本项目源码仓库按 MIT 发布”
- 不能把整个桌面成品简单描述为“只有 MIT”

## 公开发布自检

公开仓库前可运行：

```powershell
# 若刚执行过安装 / 打包 / 预览，先清理本地产物
.\clean_public_release.bat

# 普通扫描
.\check_public_release.bat

# 严格模式
.\check_public_release.bat --strict
```

公开发布检查清单见：

- `docs/OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md`

## 关键文件

- `main.py`：应用入口
- `src/qt_api.py`：统一 Qt 绑定入口
- `requirements.txt`：运行时依赖
- `LICENSE`：项目源码许可证
- `THIRD_PARTY_NOTICES.md`：第三方依赖许可证说明
- `licenses/components.json`：需要随包披露的运行组件与界面资源配置
- `licenses/manifest.json`：应用内连续许可正文与发布检查使用的结构化发行清单
- `scripts/build_license_bundle.py`：从当前环境收集组件版本和原始许可文件
