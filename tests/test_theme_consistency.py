from src.shared.ui.theme import BLUE_GREEN, DARK, LIGHT, OCEAN, RED_BLUE, ROSE


def test_builtin_themes_pass_contrast_guardrails():
    themes = {
        "LIGHT": LIGHT,
        "DARK": DARK,
        "OCEAN": OCEAN,
        "ROSE": ROSE,
        "BLUE_GREEN": BLUE_GREEN,
        "RED_BLUE": RED_BLUE,
    }

    warnings = {
        name: theme.validate_contrast()
        for name, theme in themes.items()
        if theme.validate_contrast()
    }

    assert warnings == {}
