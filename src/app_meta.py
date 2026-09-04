"""Centralized application naming metadata."""

APP_DISPLAY_NAME = "LDWord"
APP_AUTHOR = "LUODA"
APP_HOMEPAGE = "https://dicad.cn"

APP_SEMVER = "1.0.0"
APP_RELEASE_LINE = "V" + ".".join(APP_SEMVER.split(".")[:2])
APP_VERSION = f"V{APP_SEMVER}"
APP_FILE_VERSION = (*tuple(int(part) for part in APP_SEMVER.split(".")), 0)
APP_DISPLAY_NAME_FULL = f"{APP_DISPLAY_NAME} {APP_VERSION}"

APP_CLI_NAME = "ldword"
APP_PACKAGE_NAME = "LDWord"

APP_LOG_FILE = "ldword_form.log"
APP_TEMP_DIR_NAME = "ldword_form_refresh"
APP_DATA_DIR_NAME = "LDWord"
APP_HOME_DIR_NAME = ".ldword_form"
APP_CUSTOM_THEMES_ENV = "LDWORD_FORM_CUSTOM_THEMES_FILE"

# ── 出厂内置 LUODA 云端 AI 服务 ─────────────────────────────
# 官方模型网关代理密钥（客户可随时在“偏好设置 → AI 模型”中修改或改用
# 自己的服务；此处仅为全新安装提供开箱即用的默认连接）。
LUODA_OFFICIAL_DEFAULT_KEY = "sk-proxy-local-51f5bd4b979"
