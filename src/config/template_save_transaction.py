"""Best-effort transactional persistence for one or more template files.

Every payload is serialized to a same-directory staging file before any target
is replaced.  Commit failures restore the original targets from same-directory
backups so a normal runtime error cannot leave a half-saved template batch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkstemp
from typing import Iterable

from src.config.loader import save_template
from src.config.template import TemplateConfig


@dataclass(frozen=True, slots=True)
class TemplateSaveItem:
    template: TemplateConfig
    target: Path


class TemplateSaveTransactionError(RuntimeError):
    """A batch save failed and one or more originals could not be restored."""


def _path_key(path: Path) -> str:
    try:
        value = str(path.resolve(strict=False))
    except (OSError, RuntimeError):
        value = str(path.absolute())
    return value.casefold() if os.name == "nt" else value


def _reserve_sidecar(target: Path, marker: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = mkstemp(
        dir=target.parent,
        prefix=f".{target.stem}.",
        suffix=f".{marker}{target.suffix}",
    )
    os.close(descriptor)
    return Path(raw_path)


def save_template_batch(items: Iterable[TemplateSaveItem]) -> tuple[Path, ...]:
    """Persist a unique set of template targets with staging and rollback."""

    requests = tuple(
        TemplateSaveItem(item.template, Path(item.target))
        for item in items
    )
    if not requests:
        return ()

    seen: dict[str, Path] = {}
    for item in requests:
        key = _path_key(item.target)
        previous = seen.get(key)
        if previous is not None:
            raise ValueError(
                f"duplicate template save target: {previous} and {item.target}"
            )
        seen[key] = item.target

    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    touched: list[Path] = []
    try:
        # Serialize every payload first.  A serialization or permission error
        # therefore occurs before any authoritative file is moved.
        for item in requests:
            stage = _reserve_sidecar(item.target, "stage")
            staged[item.target] = stage
            save_template(item.template, stage)

        for item in requests:
            target = item.target
            backup: Path | None = None
            if target.exists():
                backup = _reserve_sidecar(target, "backup")
                try:
                    os.replace(target, backup)
                except Exception:
                    try:
                        backup.unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise
            backups[target] = backup
            touched.append(target)
            os.replace(staged[target], target)

        for backup in backups.values():
            if backup is not None:
                try:
                    backup.unlink(missing_ok=True)
                except OSError:
                    # A stale hidden backup is preferable to failing a commit
                    # after every authoritative target was replaced.
                    pass
        return tuple(item.target for item in requests)
    except Exception as exc:
        rollback_failures: list[str] = []
        for target in reversed(touched):
            backup = backups.get(target)
            try:
                target.unlink(missing_ok=True)
                if backup is not None and backup.exists():
                    os.replace(backup, target)
            except OSError as rollback_exc:
                rollback_failures.append(f"{target}: {rollback_exc}")
        if rollback_failures:
            raise TemplateSaveTransactionError(
                "template batch save failed and rollback was incomplete: "
                + "; ".join(rollback_failures)
            ) from exc
        raise
    finally:
        for stage in staged.values():
            try:
                stage.unlink(missing_ok=True)
            except OSError:
                pass


__all__ = [
    "TemplateSaveItem",
    "TemplateSaveTransactionError",
    "save_template_batch",
]
