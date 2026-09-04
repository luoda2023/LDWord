"""Canonical presentation semantics for local path actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class PathAction(str, Enum):
    """User intent represented by a path-related control."""

    CHOOSE_IMAGE = "choose_image"
    CHOOSE_FILE = "choose_file"
    CHOOSE_DIRECTORY = "choose_directory"
    OPEN_FILE = "open_file"
    REVEAL_IN_FOLDER = "reveal_in_folder"


@dataclass(frozen=True, slots=True)
class PathActionPresentation:
    icon_name: str
    accessible_name: str


_PRESENTATIONS = MappingProxyType(
    {
        PathAction.CHOOSE_IMAGE: PathActionPresentation("image", "选择图片"),
        PathAction.CHOOSE_FILE: PathActionPresentation("file-text", "选择文件"),
        PathAction.CHOOSE_DIRECTORY: PathActionPresentation(
            "folder-output",
            "选择文件夹",
        ),
        PathAction.OPEN_FILE: PathActionPresentation(
            "square-arrow-out-up-right",
            "打开文件",
        ),
        PathAction.REVEAL_IN_FOLDER: PathActionPresentation(
            "folder-open",
            "打开所在文件夹",
        ),
    }
)


def path_action_presentation(action: PathAction) -> PathActionPresentation:
    """Return the one icon/meaning contract for a local path action."""

    return _PRESENTATIONS[PathAction(action)]


__all__ = ["PathAction", "PathActionPresentation", "path_action_presentation"]
