# Third-Party Notices

本项目**自身源码**采用 **MIT License** 发布。  
第三方依赖及其许可证**不会**因为本项目采用 MIT 而改变；安装、运行、分发或打包时，仍需分别遵守各依赖自身许可证。

## Runtime / build dependencies

| Dependency | License note |
|---|---|
| python-docx | MIT |
| PySide6 | LGPL / GPL / Commercial（以官方发布说明为准） |
| Pillow | HPND-style / historical PIL license family |
| lxml | BSD-like |
| PyYAML | MIT |
| pywin32 | PSF |
| pytest | MIT |

## Important note on PySide6 / Qt

`PySide6` / `Qt` **不是 MIT**。

如果你只是公开源码仓库，通常应至少保留：

- `LICENSE`
- `THIRD_PARTY_NOTICES.md`
- 依赖清单（如 `requirements.txt`）

如果你进一步分发：

- 打包 exe
- 安装包
- 带 Qt 运行时的桌面发布物

则还需要**单独检查并满足** Qt / PySide6 对应许可证要求。

## Project policy

- 项目自身代码：MIT
- 第三方依赖：保留各自原许可证
- 本仓库不试图重新许可任何第三方库、第三方模板、第三方素材或第三方规范文本
