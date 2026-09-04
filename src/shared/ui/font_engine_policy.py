"""Configure the Windows Qt font engine before QApplication is created.

The Windows platform plugin reads ``fontengine`` from ``QT_QPA_PLATFORM``.
Keeping the policy here gives source runs and frozen builds the same startup
contract without importing PySide6 as a side effect.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from collections.abc import MutableMapping
from collections.abc import Sequence


FONT_ENGINE_ENV_VAR = "ALAVETTE_FORM_FONT_ENGINE"
QT_PLATFORM_ENV_VAR = "QT_QPA_PLATFORM"
FONT_ENGINE_CHOICES = ("freetype", "directwrite", "system")
WINDOWS_YAHEI_FONT_FILES: tuple[str, ...] = (
    "msyh.ttc",
    "msyhbd.ttc",
    "msyhl.ttc",
)

_HEADLESS_PLATFORMS = frozenset({"offscreen", "minimal"})
_WINDOWS_PLATFORM = "windows"


@dataclass(frozen=True)
class FontEngineConfiguration:
    """Result of applying (or intentionally skipping) the startup policy."""

    engine: str | None
    source: str
    qpa_platform: str | None
    changed: bool


def windows_yahei_font_paths(
    *,
    environ: MutableMapping[str, str] | None = None,
    windows_dir: str | Path | None = None,
) -> tuple[Path, ...]:
    """Return OS font paths without importing Qt or redistributing fonts."""

    environment = os.environ if environ is None else environ
    root = Path(
        windows_dir
        if windows_dir is not None
        else environment.get("WINDIR", r"C:\Windows")
    )
    return tuple(root / "Fonts" / filename for filename in WINDOWS_YAHEI_FONT_FILES)


def missing_windows_yahei_font_paths(
    *,
    environ: MutableMapping[str, str] | None = None,
    windows_dir: str | Path | None = None,
) -> tuple[Path, ...]:
    return tuple(
        path
        for path in windows_yahei_font_paths(
            environ=environ,
            windows_dir=windows_dir,
        )
        if not path.is_file()
    )


def _platform_plugin(qpa_platform: str | None) -> str | None:
    if not qpa_platform:
        return None
    return qpa_platform.split(":", 1)[0].strip().casefold() or None


def _platform_parts(qpa_platform: str | None) -> tuple[str | None, list[str]]:
    """Split a QPA value using Qt's ``plugin:key=value,key=value`` grammar.

    A short-lived application build emitted ``:fontengine=`` as a second
    colon-delimited option.  Accept that one legacy spelling so an upgrade can
    repair it, but always serialize the canonical comma-delimited form.
    """

    if not qpa_platform:
        return None, []

    platform_segment, separator, raw_options = qpa_platform.partition(":")
    if not separator:
        return platform_segment or None, []

    raw_options = raw_options.replace(":fontengine=", ",fontengine=")
    options = [option.strip() for option in raw_options.split(",") if option.strip()]
    return platform_segment or _WINDOWS_PLATFORM, options


def _font_engine_option(qpa_platform: str | None) -> str | None:
    _platform, options = _platform_parts(qpa_platform)
    for option in options:
        key, separator, value = option.partition("=")
        if separator and key.strip().casefold() == "fontengine":
            return value.strip().casefold() or None
    return None


def _validated_engine(value: str, *, source: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in FONT_ENGINE_CHOICES:
        choices = ", ".join(FONT_ENGINE_CHOICES)
        raise ValueError(
            f"Unsupported Qt font engine {value!r} from {source}; "
            f"expected one of: {choices}."
        )
    return normalized


def _windows_platform_with_engine(
    qpa_platform: str | None,
    engine: str,
) -> str | None:
    """Return a Windows QPA value with one authoritative fontengine option."""

    # ``system`` is a true opt-out: keep any platform choice made by the host
    # process, qt.conf, or a launcher.  It is intentionally different from the
    # explicit DirectWrite fallback below.
    if engine == "system":
        return qpa_platform

    platform_segment, existing_options = _platform_parts(qpa_platform)
    platform_segment = platform_segment or _WINDOWS_PLATFORM
    options = []
    for option in existing_options:
        key = option.partition("=")[0].strip().casefold()
        if key == "fontengine":
            continue
        # This flag explicitly disables DirectWrite.  It must not survive an
        # explicit DirectWrite selection and is redundant under FreeType.
        if option.strip().casefold() == "nodirectwrite":
            continue
        options.append(option)

    # Qt documents only ``fontengine=freetype`` (and, on recent Qt, ``gdi``).
    # DirectWrite is the Windows default and is selected by omitting the
    # fontengine option; ``fontengine=directwrite`` is not a supported spelling.
    if engine == "freetype":
        options.append("fontengine=freetype")

    if engine == "directwrite" and qpa_platform is None:
        return None
    if not options:
        return platform_segment
    return f"{platform_segment}:{','.join(options)}"


def requested_font_engine_from_argv(argv: Sequence[str]) -> str | None:
    """Read the startup-only option without importing argparse or Qt.

    PyInstaller runtime hooks execute before ``main.py``.  Parsing this single
    option there prevents a temporary FreeType injection when the user asked
    for ``directwrite`` or the no-policy ``system`` mode.
    """

    for index, argument in enumerate(argv):
        if argument == "--font-engine":
            if index + 1 >= len(argv):
                return None
            return _validated_engine(argv[index + 1], source="command line")
        prefix = "--font-engine="
        if argument.startswith(prefix):
            return _validated_engine(argument[len(prefix) :], source="command line")
    return None


def configure_windows_font_engine(
    requested: str | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
    platform: str | None = None,
) -> FontEngineConfiguration:
    """Apply the Windows font-engine startup policy.

    Precedence on the native Windows platform is:

    1. an explicit ``requested`` value (the command-line option),
    2. ``ALAVETTE_FORM_FONT_ENGINE``,
    3. an existing ``QT_QPA_PLATFORM=windows:fontengine=...`` option,
    4. the production default, FreeType.

    ``offscreen`` and ``minimal`` are test/headless platforms. They are never
    replaced or decorated, even when a font engine was explicitly requested.
    The function is deliberately free of Qt imports and must run before the
    first QApplication is constructed.
    """

    environment = os.environ if environ is None else environ
    runtime_platform = sys.platform if platform is None else platform
    existing_qpa = environment.get(QT_PLATFORM_ENV_VAR)
    plugin = _platform_plugin(existing_qpa)

    if runtime_platform != "win32":
        return FontEngineConfiguration(None, "non-windows", existing_qpa, False)

    if plugin in _HEADLESS_PLATFORMS:
        return FontEngineConfiguration(None, "headless-platform", existing_qpa, False)

    # Respect any deliberately selected non-Windows QPA plugin. In
    # particular, this prevents a launch harness from being silently changed.
    if plugin not in (None, _WINDOWS_PLATFORM):
        return FontEngineConfiguration(None, "explicit-qpa-platform", existing_qpa, False)

    if requested is not None:
        engine = _validated_engine(requested, source="command line")
        source = "command-line"
    else:
        environment_value = environment.get(FONT_ENGINE_ENV_VAR, "").strip()
        if environment_value:
            engine = _validated_engine(environment_value, source=FONT_ENGINE_ENV_VAR)
            source = "environment"
        else:
            existing_engine = _font_engine_option(existing_qpa)
            if existing_engine:
                # Repair the unsupported spelling emitted by an earlier app
                # build while preserving the user's intent.
                if existing_engine == "directwrite":
                    configured_qpa = _windows_platform_with_engine(
                        existing_qpa,
                        "directwrite",
                    )
                    if configured_qpa is None:
                        environment.pop(QT_PLATFORM_ENV_VAR, None)
                    else:
                        environment[QT_PLATFORM_ENV_VAR] = configured_qpa
                    return FontEngineConfiguration(
                        "directwrite",
                        "qt-platform",
                        configured_qpa,
                        configured_qpa != existing_qpa,
                    )
                return FontEngineConfiguration(
                    existing_engine,
                    "qt-platform",
                    existing_qpa,
                    False,
                )
            engine = "freetype"
            source = "production-default"

    configured_qpa = _windows_platform_with_engine(existing_qpa, engine)
    changed = configured_qpa != existing_qpa
    if configured_qpa is None:
        environment.pop(QT_PLATFORM_ENV_VAR, None)
    else:
        environment[QT_PLATFORM_ENV_VAR] = configured_qpa

    return FontEngineConfiguration(engine, source, configured_qpa, changed)


def configure_application_windows_font_engine(
    requested: str | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
    platform: str | None = None,
    windows_dir: str | Path | None = None,
) -> FontEngineConfiguration:
    """Apply production policy and fail safely when YaHei TTC faces are absent.

    FreeType can render without these files, but the selected CJK Bold role may
    become synthetic and alter layout.  Before Qt is imported, fall back to the
    native DirectWrite backend on stripped/custom Windows installations.
    """

    environment = os.environ if environ is None else environ
    original_qpa = environment.get(QT_PLATFORM_ENV_VAR)
    result = configure_windows_font_engine(
        requested,
        environ=environment,
        platform=platform,
    )
    if result.engine != "freetype":
        return result
    if not missing_windows_yahei_font_paths(
        environ=environment,
        windows_dir=windows_dir,
    ):
        return result

    configured_qpa = _windows_platform_with_engine(
        original_qpa,
        "directwrite",
    )
    if configured_qpa is None:
        environment.pop(QT_PLATFORM_ENV_VAR, None)
    else:
        environment[QT_PLATFORM_ENV_VAR] = configured_qpa
    return FontEngineConfiguration(
        "directwrite",
        "missing-yahei-fonts-fallback",
        configured_qpa,
        configured_qpa != original_qpa,
    )


__all__ = [
    "FONT_ENGINE_CHOICES",
    "FONT_ENGINE_ENV_VAR",
    "QT_PLATFORM_ENV_VAR",
    "FontEngineConfiguration",
    "WINDOWS_YAHEI_FONT_FILES",
    "configure_application_windows_font_engine",
    "configure_windows_font_engine",
    "missing_windows_yahei_font_paths",
    "requested_font_engine_from_argv",
    "windows_yahei_font_paths",
]
