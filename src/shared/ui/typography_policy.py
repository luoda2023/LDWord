"""Single source of truth for application UI typography.

UI font sizes are integer logical pixels. Device-pixel-ratio handling belongs
to the paint/asset boundary and must never be multiplied into these values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
from typing import Protocol

from src.qt_api import QFont, QFontDatabase
from src.shared.ui.font_engine_policy import (
    WINDOWS_YAHEI_FONT_FILES,
    windows_yahei_font_paths,
)


CJK_UI_FONT_FAMILIES: tuple[str, ...] = (
    "Microsoft YaHei",
    "Microsoft YaHei UI",
    "Segoe UI",
)
LATIN_UI_FONT_FAMILIES: tuple[str, ...] = (
    "Segoe UI",
    "Microsoft YaHei",
    "Microsoft YaHei UI",
)
UI_FONT_FAMILIES = CJK_UI_FONT_FAMILIES
BRAND_FONT_FAMILIES = LATIN_UI_FONT_FAMILIES
MONO_FONT_FAMILIES: tuple[str, ...] = (
    "Consolas",
    "Cascadia Mono",
    "Microsoft YaHei",
)

# Microsoft YaHei is shipped as TrueType Collections containing both the
# document and UI family names.  Qt's Windows FreeType database can discover
# the regular face but, on current Qt 6, may fail to associate the installed
# Bold face with the English family name.  Registering the existing OS files
# as application fonts repairs that mapping without redistributing the fonts.
@dataclass(frozen=True)
class WindowsUIFontRegistration:
    """Evidence from registering the OS-provided YaHei TTC faces."""

    attempted: bool
    registered_paths: tuple[str, ...] = ()
    registered_families: tuple[str, ...] = ()
    missing_paths: tuple[str, ...] = ()
    failed_paths: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.attempted and not self.missing_paths and not self.failed_paths


def register_windows_ui_fonts_for_freetype(
    font_engine: str | None,
    *,
    windows_dir: str | Path | None = None,
) -> WindowsUIFontRegistration:
    """Make YaHei Regular/Bold/Light resolvable by the FreeType backend.

    This must run after ``QApplication`` exists and before any application
    widget/font is constructed.  DirectWrite and non-Windows processes use the
    native font database and deliberately skip this compatibility bridge.
    """

    if sys.platform != "win32" or str(font_engine or "").casefold() != "freetype":
        return WindowsUIFontRegistration(attempted=False)

    registered_paths: list[str] = []
    registered_families: list[str] = []
    missing_paths: list[str] = []
    failed_paths: list[str] = []

    for path in windows_yahei_font_paths(windows_dir=windows_dir):
        normalized_path = str(path)
        if not path.is_file():
            missing_paths.append(normalized_path)
            continue
        font_id = QFontDatabase.addApplicationFont(normalized_path)
        if font_id < 0:
            failed_paths.append(normalized_path)
            continue
        registered_paths.append(normalized_path)
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family not in registered_families:
                registered_families.append(family)

    return WindowsUIFontRegistration(
        attempted=True,
        registered_paths=tuple(registered_paths),
        registered_families=tuple(registered_families),
        missing_paths=tuple(missing_paths),
        failed_paths=tuple(failed_paths),
    )


def qss_font_family(families: tuple[str, ...]) -> str:
    return ", ".join(f"'{family}'" for family in families)


UI_FONT_FAMILY_QSS = qss_font_family(UI_FONT_FAMILIES)
BRAND_FONT_FAMILY_QSS = qss_font_family(BRAND_FONT_FAMILIES)
MONO_FONT_FAMILY_QSS = qss_font_family(MONO_FONT_FAMILIES)


@dataclass(frozen=True)
class TypographyScale:
    micro_px: int = 11
    caption_px: int = 12
    body_px: int = 13
    navigation_title_px: int = 13
    subtitle_px: int = 15
    title_px: int = 16
    page_title_px: int = 20
    regular_weight: int = 400
    emphasis_weight: int = 700


DEFAULT_TYPOGRAPHY = TypographyScale()


class TextRole(str, Enum):
    """Semantic UI text roles; widgets must not infer roles from size aliases."""

    MICRO = "micro"
    CAPTION = "caption"
    BODY = "body"
    NAVIGATION_TITLE = "navigation_title"
    NAVIGATION_TITLE_ACTIVE = "navigation_title_active"
    SUBTITLE = "subtitle"
    TITLE = "title"
    PAGE_TITLE = "page_title"


@dataclass(frozen=True)
class TypographySpec:
    pixel_size: int
    weight: int
    families: tuple[str, ...] = UI_FONT_FAMILIES


TYPOGRAPHY_ROLES: dict[TextRole, TypographySpec] = {
    TextRole.MICRO: TypographySpec(
        DEFAULT_TYPOGRAPHY.micro_px,
        DEFAULT_TYPOGRAPHY.regular_weight,
    ),
    TextRole.CAPTION: TypographySpec(
        DEFAULT_TYPOGRAPHY.caption_px,
        DEFAULT_TYPOGRAPHY.regular_weight,
    ),
    TextRole.BODY: TypographySpec(
        DEFAULT_TYPOGRAPHY.body_px,
        DEFAULT_TYPOGRAPHY.regular_weight,
    ),
    TextRole.NAVIGATION_TITLE: TypographySpec(
        DEFAULT_TYPOGRAPHY.navigation_title_px,
        DEFAULT_TYPOGRAPHY.regular_weight,
    ),
    TextRole.NAVIGATION_TITLE_ACTIVE: TypographySpec(
        DEFAULT_TYPOGRAPHY.navigation_title_px,
        DEFAULT_TYPOGRAPHY.emphasis_weight,
    ),
    TextRole.SUBTITLE: TypographySpec(
        DEFAULT_TYPOGRAPHY.subtitle_px,
        DEFAULT_TYPOGRAPHY.emphasis_weight,
    ),
    TextRole.TITLE: TypographySpec(
        DEFAULT_TYPOGRAPHY.title_px,
        DEFAULT_TYPOGRAPHY.emphasis_weight,
    ),
    TextRole.PAGE_TITLE: TypographySpec(
        DEFAULT_TYPOGRAPHY.page_title_px,
        DEFAULT_TYPOGRAPHY.emphasis_weight,
    ),
}


class _FontTarget(Protocol):
    def setFont(self, font: QFont) -> None: ...


def build_font(
    families: tuple[str, ...],
    *,
    pixel_size: int,
    weight: int = 400,
    kerning: bool = True,
) -> QFont:
    """Build a deterministic integer-logical-pixel UI font."""

    if isinstance(pixel_size, bool) or not isinstance(pixel_size, int):
        raise TypeError("pixel_size must be an integer logical pixel value")
    if pixel_size < 1:
        raise ValueError("pixel_size must be positive")

    font = QFont()
    font.setFamilies(list(families))
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight(int(weight)))
    font.setKerning(bool(kerning))
    return font


def font_for_role(role: TextRole) -> QFont:
    """Return a complete font for a semantic role using native hinting."""

    spec = TYPOGRAPHY_ROLES[TextRole(role)]
    return build_font(
        spec.families,
        pixel_size=spec.pixel_size,
        weight=spec.weight,
    )


def apply_text_role(target: _FontTarget, role: TextRole) -> QFont:
    """Apply one centralized role without duplicating font declarations in QSS."""

    font = font_for_role(role)
    target.setFont(font)
    return font


def application_font() -> QFont:
    return font_for_role(TextRole.BODY)


def brand_font(*, pixel_size: int, weight: int = 700) -> QFont:
    return build_font(
        BRAND_FONT_FAMILIES,
        pixel_size=pixel_size,
        weight=weight,
    )


def apply_application_typography(app) -> QFont:
    """Apply the same production typography contract used by widget tests."""

    font = application_font()
    app.setFont(font)
    return font


__all__ = [
    "BRAND_FONT_FAMILIES",
    "BRAND_FONT_FAMILY_QSS",
    "CJK_UI_FONT_FAMILIES",
    "DEFAULT_TYPOGRAPHY",
    "MONO_FONT_FAMILIES",
    "MONO_FONT_FAMILY_QSS",
    "LATIN_UI_FONT_FAMILIES",
    "TYPOGRAPHY_ROLES",
    "TextRole",
    "TypographyScale",
    "TypographySpec",
    "UI_FONT_FAMILIES",
    "UI_FONT_FAMILY_QSS",
    "WINDOWS_YAHEI_FONT_FILES",
    "WindowsUIFontRegistration",
    "apply_text_role",
    "application_font",
    "apply_application_typography",
    "brand_font",
    "build_font",
    "font_for_role",
    "qss_font_family",
    "register_windows_ui_fonts_for_freetype",
    "windows_yahei_font_paths",
]
