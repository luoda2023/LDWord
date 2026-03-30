# PyQt5 到 PySide6 迁移与 MIT 发布对齐设计

- 日期：2026-03-27
- 范围：`Lark-Formatter V1.0` 全仓 GUI / demo / 测试中的 Qt 绑定层
- 目标：让 `1.0` 的发布口径与 `0.2 LTS` 对齐——**项目源码 MIT，第三方依赖保留各自许可证**，移除 `PyQt5` 带来的 GPL / 商业许可绑定风险

## 1. 背景

当前 `1.0` 直接依赖 `PyQt5`：

- `main.py`
- `src/shared/ui/*`
- `src/ui/*`
- `demo_*.py`
- 若干本地测试 / 诊断脚本

同时还存在典型 PyQt 专属 API：

- `pyqtSignal`
- `pyqtProperty`
- `exec_()`

这使得当前仓库无法沿用 `0.2 LTS` 的 MIT 发布口径。问题不在 `install_env.bat`，而在于：

1. 代码层直接绑定 `PyQt5`
2. 运行时 / 打包产物也会继承 `PyQt5` 的许可要求

而 `0.2 LTS` 使用的是 `PySide6`，并通过 `THIRD_PARTY_NOTICES.md` 明确声明：

- 项目自身源码：MIT
- 第三方依赖：仍保留各自许可证
- 打包二进制时需单独满足 Qt / PySide6 的许可要求

## 2. 目标

1. 从 `1.0` 仓库中移除运行时对 `PyQt5` 的依赖
2. 统一切换到 `PySide6`
3. 建立一个集中式 Qt 兼容入口，避免后续再次全仓散落绑定实现
4. 保持当前 UI 视觉与行为稳定，不借机重写业务逻辑
5. 补齐与 `0.2 LTS` 一致的 MIT 源码发布说明文件

## 3. 非目标

1. 本次不追求“整个桌面二进制成品纯 MIT”
2. 本次不更换 Qt 技术栈
3. 本次不顺带做无关 UI 重构
4. 本次不处理与许可无关的业务功能扩展

## 4. 目标发布口径

迁移完成后的发布口径应明确为：

1. **仓库源码：MIT**
2. **第三方依赖：保留各自许可证**
3. **若打包桌面应用：需单独遵守 Qt / PySide6 对应许可义务**

也就是说，目标是与 `0.2 LTS` 一致的“MIT 源码仓库”路线，而不是宣称“整个可分发成品只有 MIT”。

## 5. 架构设计

### 5.1 新增 Qt 兼容入口

新增：

```text
src/qt_api.py
```

职责：

- 统一导出常用 Qt 类型
- 统一导出 `Signal` / `Property`
- 统一导出 `QSvgRenderer`
- 提供 `exec_dialog()` / `exec_application()` 这类兼容 helper（如确有必要）

约束：

- 业务 / UI 文件后续只允许依赖 `src.qt_api`
- 不再直接在业务代码中写 `from PyQt5...` 或 `from PySide6...`

### 5.2 分批迁移策略

按风险从低到高分四批：

#### 第一批：发布与兼容基础设施

- `LICENSE`
- `THIRD_PARTY_NOTICES.md`
- `requirements.txt`
- `src/qt_api.py`
- 针对许可证与兼容入口的测试

#### 第二批：共享 UI 层

- `src/shared/ui/*`

原因：

- 文件集中
- 复用度最高
- 替换后可一次性消除大部分 `PyQt5` 直连

#### 第三批：主界面与面板

- `src/ui/*`
- `main.py`

这是实际运行主路径，必须在 shared/ui 稳定后再迁移。

#### 第四批：demo / 诊断脚本 / 本地测试脚本

- `demo_*.py`
- `test_*.py`

这些不是正式运行主路径，但如果保留在仓库中，也不能继续直接依赖 `PyQt5`。

## 6. API 迁移规则

### 6.1 直接映射

- `pyqtSignal` -> `Signal`
- `pyqtProperty` -> `Property`
- `app.exec_()` -> `app.exec()`
- `dialog.exec_()` -> `dialog.exec()`
- `from PyQt5.QtSvg import QSvgRenderer` -> 通过 `src.qt_api` 导入 `QSvgRenderer`

### 6.2 高风险兼容点

迁移时要特别验证：

1. Hi-DPI 设置
2. 枚举值访问方式
3. 自绘控件（`QPainter` / `QPen` / `QBrush`）
4. `QSvgRenderer` 图标路径
5. 自定义弹层与事件过滤器
6. theme / signal 绑定行为

## 7. 验证策略

### 7.1 自动化验证

至少新增 / 更新以下验证：

1. 兼容层测试：`src.qt_api` 必须基于 `PySide6`
2. 仓库运行时源码扫描：`src/` 与入口脚本不再出现 `PyQt5`
3. 现有架构测试继续通过
4. 关键 UI 导入测试继续通过

### 7.2 手工验证

至少手工确认：

1. GUI 能正常启动
2. 图标能正常显示
3. 已改造控件主题切换正常
4. 对话框可正常弹出
5. demo 预览仍可打开

## 8. 风险与对策

### 风险 1：机械替换后运行期 API 不兼容

对策：

- 每批次先写失败测试
- 批量替换后立刻跑定向测试
- 再做小范围手工启动验证

### 风险 2：仓库文档仍误导为“整个成品纯 MIT”

对策：

- README / NOTICES 明确区分“项目源码许可证”和“第三方依赖许可证”

### 风险 3：未来再次回到散落直连绑定

对策：

- 引入 `src.qt_api.py`
- 增加源码扫描测试，禁止新增 `PyQt5` 直连

## 9. 完成定义

当以下条件同时满足时，视为本次任务完成：

1. `src/`、`main.py`、demo 脚本中不再直接依赖 `PyQt5`
2. 运行时 Qt 绑定统一为 `PySide6`
3. `LICENSE`、`THIRD_PARTY_NOTICES.md`、`requirements.txt` 已补齐
4. 自动化测试通过
5. GUI 启动验证通过
6. 发布口径与 `0.2 LTS` 对齐
