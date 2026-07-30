"""PyInstaller runtime hook: configure Qt before the application imports it."""

import sys

from src.shared.ui.font_engine_policy import (
    configure_application_windows_font_engine,
    requested_font_engine_from_argv,
)


configure_application_windows_font_engine(
    requested_font_engine_from_argv(sys.argv[1:])
)
