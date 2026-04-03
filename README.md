# Alavette Form V1.0

毕业论文 / 学位论文 `docx` 格式修订桌面工具（**PySide6 + python-docx**）。

## 当前状态

- 当前 GUI 绑定已统一迁移到 **PySide6**
- 项目自身源码按 **MIT** 发布
- 第三方依赖仍保留各自许可证，详见 `THIRD_PARTY_NOTICES.md`

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

打包脚本会：

- 使用 `PyInstaller`
- 从 `main.py` 构建桌面应用
- 带上 `defaults/`
- 带上 `LICENSE`
- 带上 `THIRD_PARTY_NOTICES.md`

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
