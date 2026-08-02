# Open Source MIT Release Checklist

本清单用于把当前仓库整理为适合公开发布的 **MIT 开源版**。

> 目标：公开你拥有权利的源码与原创文档；同时清楚区分“项目源码 MIT”与“第三方依赖仍保留各自许可证”。

---

## 预检脚本

正式发布前建议先运行：

```powershell
# 仅移除明确的旧 build/dist 生成目录，不删除虚拟环境、日志或用户数据
.\clean_public_release.bat

.\check_public_release.bat

# 严格模式：发现问题时返回非 0
.\check_public_release.bat --strict
```

---

## 必须保留

- `README.md`
- `CHANGELOG.md`
- `RELEASE_NOTES.md`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `LICENSE`
- `THIRD_PARTY_NOTICES.md`
- `licenses/components.json`
- `licenses/manifest.json`
- `licenses/static/` 与 `licenses/packages/`
- `requirements.txt`
- `main.py`
- `src/`
- `defaults/`
- `docs/user/`（Markdown 正文、演示截图和快速开始示例）

---

## 不建议公开的本地产物

- `.venv/`
- `build/`
- `dist/`
- `.pytest_cache/`
- `__pycache__/`
- `crash.log`
- `demo_crash.log`
- `alavette_form.log`
- 各类临时输出文档、对比稿、扫描报告

---

## 许可证说明必须清楚

- 项目自身源码：**MIT**
- `PySide6` / `Qt`：**不是 MIT**
- 当前社区版二进制发行采用 **LGPLv3**；同时保留上游声明的 LGPLv3/GPLv3 许可选择信息
- `Lucide Icons`：**ISC**；其中部分 Feather 衍生图标为 **MIT**
- 打包的桌面应用：仍需单独满足 Qt / PySide6 许可证要求

不要把最终桌面成品简单表述为“整个项目只有 MIT”。

---

## 发布前自查

- [ ] `README.md` 已说明 MIT 源码口径
- [ ] `docs/user/` 中的快速开始、完整手册、截图和示例文件已同步到当前版本
- [ ] 二进制发布包根目录包含两份用户文档 PDF 和快速开始示例 DOCX
- [ ] `THIRD_PARTY_NOTICES.md` 已说明第三方依赖许可证
- [ ] `licenses/manifest.json` 中的组件数量、版本和许可文件均通过发布检查
- [ ] Lucide、Feather、Qt、PDFium、Python 与 OpenSSL 等随包内容均已纳入许可清单
- [ ] `requirements.txt` 使用 `PySide6_Essentials`，不再依赖 `PyQt5`
- [ ] 当前候选提交已冻结，`git status --porcelain` 为空，并已推送到真实发布远端
- [ ] 使用 `scripts/stage_source_release.py` 从候选提交导出隔离源码树
- [ ] 对隔离源码树运行 `.\check_public_release.bat --strict --root <staging>`
- [ ] GitHub Actions 中 `Scene Matrix Release Gate` 已通过
- [ ] 运行 `python scripts/engineering_gate.py`、场景门禁和 `pytest -q tests`
- [ ] 官方构建使用 CPython 3.12 x64 且 `scripts/verify_release_environment.py` 通过
- [ ] 正式 EXE 的 Windows 版本资源、数字签名和时间戳均验证通过
- [ ] 最终 ZIP 附带 CycloneDX SBOM、RELEASE_MANIFEST、SHA-256 和门禁日志
- [ ] Windows 10/11、Office 有/无、多 DPI、非 ASCII 路径与覆盖升级人工矩阵已签字
- [ ] `SECURITY.md` 中的私密漏洞报告入口和行为事件联系渠道已由项目所有者配置
- [ ] 确认 `build/`、`dist/`、`.venv/` 等目录不会进入公开仓库
