# Alavette Form V1.0

Windows 本地优先的场景化文档生产与规范化工作台（**PySide6 + python-docx**）。

Alavette Form 将原始文档、处理方案、格式模板、母版和资料包组合为可复用流程，在执行前检查复杂 Word 对象与资料完整性，并生成规范化 DOCX、变更报告和场景化交付版本。文档默认仅在本机处理，不会自动上传。

## 产品能力

- **4 个当前可用工作模式**：通用版、试卷版、论文版、公文版
- **暂缓场景**：标书版、技术文档版、报告版保留内部定义，但当前界面隐藏，暂不深度开发
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

## 用户文档

- [10 分钟快速开始](docs/user/quick-start.md)
- [完整用户手册](docs/user/user-guide.md)
- [Obsidian 用户文档入口](docs/user/00-开始这里.md)
- 发布版 PDF、Obsidian 文档包和演示 DOCX 由 `scripts/build_user_documentation.py` 生成，输出到 `artifacts/user-docs/v1.0/`

## 环境要求

- Windows（提供 `.bat` 启动与打包脚本）
- 源码运行与开发：Python 3.10～3.12
- V1.0 官方 Windows 构建：CPython 3.12 x64，并严格匹配 `requirements-release.lock`

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
# 正式发布必须先在环境中提供代码签名证书指纹
$env:ALAVETTE_SIGN_CERT_SHA1 = "<40 位证书 SHA-1 指纹>"
.\package_release.bat

# 无证书时只能生成带 UNSIGNED-QA 标识的内部验证包
.\package_release.bat --unsigned-qa
```

构建要求 Git 工作区完全干净。输出目录绑定当前 commit：

- 正式包：`artifacts/releases/<commit>/`
- 内部无签名包：`artifacts/release-qa/<commit>/`

每次构建同时生成推荐分发的 `Alavette-Form-Setup-<version>-x64.exe`
和备用的 `Alavette-Form-Portable-<version>-x64.zip`。安装器使用固定的 V1
产品身份执行原位更新；补丁版本只更新语义版本号，不更换 AppId 或安装目录。

打包脚本会：

- 从当前干净提交导出隔离源码树，并校验逐文件 SHA-256 清单
- 强制执行工程门禁、场景矩阵门禁、全量回归、`pip check` 和源码发布扫描
- 使用锁定的 CPython 3.12 / PyInstaller 6.21.0 从版本控制中的 spec 构建
- 带上 `defaults/`、`LICENSE`、`THIRD_PARTY_NOTICES.md` 和结构化许可文件
- 生成并带上《快速开始》PDF、《用户手册》PDF、Obsidian 文档包和快速开始示例 DOCX
- 根据锁定环境生成 `licenses/manifest.json`，并带上全部原始许可文件
- 清理未使用的 Qt add-on payload
- 写入 Windows FileVersion/ProductVersion，正式包执行签名、时间戳和签名验证
- 生成 CycloneDX SBOM、最终文件哈希清单、ZIP SHA-256 和全部门禁日志
- 对最终二进制树做严格扫描后原子发布；任一步失败都不会生成正式目录

正式构建还依赖 Microsoft Word 导出两份 PDF。`UNSIGNED-QA` 只跳过签名，不跳过其他门禁，也不得对外发布。

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
# 只清理明确的旧构建目录；不会删除 .venv、日志或用户资料
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
- `requirements-release.lock`：Windows V1.0 官方构建的精确依赖约束
- `LICENSE`：项目源码许可证
- `THIRD_PARTY_NOTICES.md`：第三方依赖许可证说明
- `licenses/components.json`：需要随包披露的运行组件与界面资源配置
- `licenses/manifest.json`：应用内连续许可正文与发布检查使用的结构化发行清单
- `scripts/build_license_bundle.py`：从当前环境收集组件版本和原始许可文件
- `scripts/build_release.py`：隔离、门禁、签名、清单和原子发布入口
- `SECURITY.md`：漏洞报告与支持范围
- `RELEASE_NOTES.md`：V1.0 候选发布说明与已知边界
