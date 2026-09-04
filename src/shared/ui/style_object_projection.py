"""Unified projection for template editing and execution style receipts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from src.shared.ui.style_owner_state import StyleOwnerViewState
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.summary_grid import SummaryGridItem


@dataclass(frozen=True, slots=True)
class StyleObjectProjection:
    """Bundle the shared UI facts for one style-management object."""

    kind: str = ""
    object_label: str = ""
    source_label: str = ""
    scope_label: str = ""
    edit_state_label: str = ""
    summary_items: tuple[SummaryGridItem, ...] = ()
    owner_state: StyleOwnerViewState | None = None
    source: object | None = None
    preview: StylePresentationEnvelope = field(
        default_factory=lambda: StylePresentationEnvelope.from_object(None)
    )
    preview_projection: object | None = None
    receipt: StylePresentationEnvelope | None = None
    empty_preview_text: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _clean(self.kind))
        object.__setattr__(self, "object_label", _clean(self.object_label))
        object.__setattr__(self, "source_label", _clean(self.source_label))
        object.__setattr__(self, "scope_label", _clean(self.scope_label))
        object.__setattr__(self, "edit_state_label", _clean(self.edit_state_label))
        object.__setattr__(self, "summary_items", tuple(self.summary_items))
        object.__setattr__(
            self,
            "preview",
            StylePresentationEnvelope.from_object(self.preview),
        )
        receipt = self.receipt
        object.__setattr__(
            self,
            "receipt",
            StylePresentationEnvelope.from_object(receipt) if receipt is not None else None,
        )
        object.__setattr__(self, "empty_preview_text", _clean(self.empty_preview_text))

    @classmethod
    def from_owner_state(
        cls,
        *,
        kind: str,
        object_label: str,
        owner_state: StyleOwnerViewState,
        summary_items: Sequence[SummaryGridItem] = (),
        preview: StylePresentationEnvelope | object | None = None,
        source: object | None = None,
        preview_projection: object | None = None,
        receipt: StylePresentationEnvelope | object | None = None,
        empty_preview_text: str = "",
    ) -> "StyleObjectProjection":
        """Create a projection from the owner-state values already used by panes."""

        return cls(
            kind=kind,
            object_label=object_label,
            source_label=owner_state.source_status,
            scope_label=owner_state.scope_status,
            edit_state_label=owner_state.edit_status,
            summary_items=tuple(summary_items),
            owner_state=owner_state,
            source=source,
            preview=(
                StylePresentationEnvelope.from_object(preview)
                if preview is not None
                else StylePresentationEnvelope.from_object(None)
            ),
            preview_projection=preview_projection,
            receipt=(
                StylePresentationEnvelope.from_object(receipt)
                if receipt is not None
                else None
            ),
            empty_preview_text=empty_preview_text,
        )

    @classmethod
    def from_object(cls, projection) -> "StyleObjectProjection":
        """Normalize object-compatible projections for StyleManagementBlock."""

        if isinstance(projection, cls):
            return projection
        if projection is None:
            return cls()
        receipt = getattr(projection, "receipt", None)
        return cls(
            kind=getattr(projection, "kind", ""),
            object_label=getattr(projection, "object_label", ""),
            source_label=getattr(projection, "source_label", ""),
            scope_label=getattr(projection, "scope_label", ""),
            edit_state_label=getattr(projection, "edit_state_label", ""),
            summary_items=tuple(getattr(projection, "summary_items", ()) or ()),
            owner_state=getattr(projection, "owner_state", None),
            source=getattr(projection, "source", None),
            preview=StylePresentationEnvelope.from_object(
                getattr(projection, "preview", None)
            ),
            preview_projection=getattr(projection, "preview_projection", None),
            receipt=(
                StylePresentationEnvelope.from_object(receipt)
                if receipt is not None
                else None
            ),
            empty_preview_text=getattr(projection, "empty_preview_text", ""),
        )


def _clean(value) -> str:
    return " ".join(str(value or "").split())


__all__ = ["StyleObjectProjection"]
