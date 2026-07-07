"""Compatibility exports for scene preset definitions.

The implementation lives in ``src.config.scene_presets`` so config and audit
modules do not depend on the UI package. UI callers keep this import path while
the migration settles.
"""

from src.config.scene_presets import *  # noqa: F401,F403
