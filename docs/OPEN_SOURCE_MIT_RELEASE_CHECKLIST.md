# Open Source MIT Release Checklist

本清单用于把当前仓库整理为适合公开发布的 **MIT 开源版**。

> 目标：公开你拥有权利的源码与原创文档；同时清楚区分“项目源码 MIT”与“第三方依赖仍保留各自许可证”。

---

## 预检脚本

正式发布前建议先运行：

```powershell
.\clean_public_release.bat

.\check_public_release.bat

# 严格模式：发现问题时返回非 0
.\check_public_release.bat --strict
```

---

## 必须保留

- `README.md`
- `LICENSE`
- `THIRD_PARTY_NOTICES.md`
- `requirements.txt`
- `main.py`
- `src/`
- `defaults/`

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
- 打包的桌面应用：仍需单独满足 Qt / PySide6 许可证要求

不要把最终桌面成品简单表述为“整个项目只有 MIT”。

---

## 发布前自查

- [ ] `README.md` 已说明 MIT 源码口径
- [ ] `THIRD_PARTY_NOTICES.md` 已说明第三方依赖许可证
- [ ] `requirements.txt` 使用 `PySide6`，不再依赖 `PyQt5`
- [ ] 若刚执行过安装 / 打包 / 预览，先运行 `.\clean_public_release.bat`
- [ ] 运行 `.\check_public_release.bat --strict`
- [ ] 运行 `pytest tests -v`
- [ ] 确认 `build/`、`dist/`、`.venv/` 等目录不会进入公开仓库
