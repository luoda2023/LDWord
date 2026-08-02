"""Centralized application naming metadata."""

APP_DISPLAY_NAME = "Alavette Form"
APP_SEMVER = "1.0.0"
APP_RELEASE_LINE = "V" + ".".join(APP_SEMVER.split(".")[:2])
APP_VERSION = f"V{APP_SEMVER}"
APP_FILE_VERSION = (*tuple(int(part) for part in APP_SEMVER.split(".")), 0)
APP_DISPLAY_NAME_FULL = f"{APP_DISPLAY_NAME} {APP_VERSION}"

APP_CLI_NAME = "alavette-form"
APP_PACKAGE_NAME = "Alavette-Form"

APP_LOG_FILE = "alavette_form.log"
APP_TEMP_DIR_NAME = "alavette_form_refresh"
APP_DATA_DIR_NAME = "Alavette-Form"
APP_HOME_DIR_NAME = ".alavette_form"
APP_CUSTOM_THEMES_ENV = "ALAVETTE_FORM_CUSTOM_THEMES_FILE"
