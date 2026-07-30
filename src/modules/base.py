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
    enabled_by_default: bool | None = None
    # Stored as a serialized value to keep the module base layer independent
    # from pipeline orchestration.  The phase adapter is the sole authority
    # that coerces this value to ``Phase``.
    execution_phase: str = ""
    # Stored as a serialized value for the same reason.  The module adapter
    # validates it against the closed document-scope behavior contract.
    scope_behavior: str = ""

    def __post_init__(self) -> None:
        if self.enabled_by_default is None:
            from src.modules.default_switches import default_enabled_for_module

            object.__setattr__(
                self,
                "enabled_by_default",
                default_enabled_for_module(self.name),
            )
        elif type(self.enabled_by_default) is not bool:
            raise TypeError("enabled_by_default must be a boolean")
        if not isinstance(self.execution_phase, str):
            raise TypeError("execution_phase must be a string")
        if self.execution_phase != self.execution_phase.strip():
            raise ValueError("execution_phase cannot contain surrounding whitespace")
        if not isinstance(self.scope_behavior, str):
            raise TypeError("scope_behavior must be a string")
        if self.scope_behavior != self.scope_behavior.strip():
            raise ValueError("scope_behavior cannot contain surrounding whitespace")


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
