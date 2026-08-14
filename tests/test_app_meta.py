import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import app_meta


def test_display_names_match_expected_branding():
    assert app_meta.APP_DISPLAY_NAME == "Alavette Form"
    assert app_meta.APP_DISPLAY_NAME_FULL == "Alavette Form V1.0.1"
    assert app_meta.APP_VERSION == "V1.0.1"
    assert app_meta.APP_RELEASE_LINE == "V1.0"
    assert app_meta.APP_DISPLAY_NAME in app_meta.APP_DISPLAY_NAME_FULL


def test_release_versions_have_one_semantic_source_of_truth():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version = re.search(
        r'^version\s*=\s*"([^"]+)"',
        pyproject,
        flags=re.MULTILINE,
    )

    assert project_version is not None
    assert app_meta.APP_SEMVER == project_version.group(1) == "1.0.1"
    assert app_meta.APP_VERSION == "V1.0.1"
    assert app_meta.APP_FILE_VERSION == (1, 0, 1, 0)


def test_package_and_cli_names_use_expected_safe_formats():
    assert app_meta.APP_CLI_NAME == "alavette-form"
    assert app_meta.APP_PACKAGE_NAME == "Alavette-Form"
    assert " " not in app_meta.APP_CLI_NAME
    assert " " not in app_meta.APP_PACKAGE_NAME


def test_internal_runtime_identifiers_use_new_slug():
    assert app_meta.APP_LOG_FILE == "alavette_form.log"
    assert app_meta.APP_TEMP_DIR_NAME == "alavette_form_refresh"
    assert app_meta.APP_DATA_DIR_NAME == "Alavette-Form"
    assert app_meta.APP_HOME_DIR_NAME == ".alavette_form"
    assert app_meta.APP_CUSTOM_THEMES_ENV == "ALAVETTE_FORM_CUSTOM_THEMES_FILE"
