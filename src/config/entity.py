"""Public material-entity API.

Consumers should import this stable facade.  The implementation is split into
model/normalization and archive IO modules so model-only imports do not cross
into the service layer.
"""

from importlib import import_module
from typing import TYPE_CHECKING

from src.config.entity_models import (
    ENTITY_PACKAGE_VERSION,
    AssetBinding,
    AssetTokenSpec,
    EntityArchive,
    EntityProfile,
    clone_entity_profile,
)

if TYPE_CHECKING:
    from src.config.entity_archive_codec import (
        load_entity_archive,
        save_entity_archive,
    )
    from src.config.entity_bundle import save_entity_archive_bundle


_ARCHIVE_IO_EXPORTS = {
    "load_entity_archive": (
        "src.config.entity_archive_codec",
        "load_entity_archive",
    ),
    "save_entity_archive": (
        "src.config.entity_archive_codec",
        "save_entity_archive",
    ),
    "save_entity_archive_bundle": (
        "src.config.entity_bundle",
        "save_entity_archive_bundle",
    ),
}


def __getattr__(name: str):
    """Resolve archive IO only for consumers that actually request it."""

    target = _ARCHIVE_IO_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value

__all__ = [
    "ENTITY_PACKAGE_VERSION",
    "AssetBinding",
    "AssetTokenSpec",
    "EntityArchive",
    "EntityProfile",
    "clone_entity_profile",
    "load_entity_archive",
    "save_entity_archive",
    "save_entity_archive_bundle",
]
