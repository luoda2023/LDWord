"""Base types and metadata for pipeline modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docx import Document

    from src.config.resolved import ResolvedConfig
    from src.pipeline.context import PipelineContext
    from src.pipeline.tracker import ChangeTracker


@dataclass(frozen=True)
class ModuleMeta:
    """Immutable module metadata consumed by scheduler/pipeline layers."""

    name: str
    description: str
    category: str

    depends_on: tuple[str, ...] = ()
    soft_after: tuple[str, ...] = ()

    consumes: tuple[str, ...] = ()
    soft_consumes: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()

    requires_config: tuple[str, ...] = ()

    modifies_structure: bool = False
    enabled_by_default: bool = False


@dataclass
class Issue:
    """Validation issue emitted by a module."""

    level: str
    module_name: str
    message: str
    location: str = ""


class BaseModule(ABC):
    """Abstract base class for all pipeline modules."""

    meta: ModuleMeta

    @abstractmethod
    def apply(
        self,
        doc: Document,
        config: ResolvedConfig,
        tracker: ChangeTracker,
        context: PipelineContext,
    ) -> None:
        """Run the module and mutate ``doc`` in place."""
        ...

    def validate(
        self,
        doc: Document,
        config: ResolvedConfig,
        context: PipelineContext,
    ) -> list[Issue]:
        """Optional preflight validation hook."""
        return []

    def estimate_impact(
        self,
        doc: Document,
        config: ResolvedConfig,
    ) -> dict[str, int]:
        """Optional UI-facing impact estimate."""
        return {}
