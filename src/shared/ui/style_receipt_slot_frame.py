"""Cardless style receipt slot for embedded execution result surfaces."""

from __future__ import annotations

from src.qt_api import QSizePolicy, QVBoxLayout, QWidget
from src.shared.ui.style_result_receipt_row import StyleResultReceiptRow


class StyleReceiptSlotFrame(QWidget):
    """A lightweight receipt-only surface that can live inside existing cards."""

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_receipt_slot",
        mode: str = "execution_receipt_review",
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_receipt_slot").strip()
        self._mode = str(mode or "execution_receipt_review").strip()
        self.setObjectName(f"{prefix}_slot")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._receipt_row = StyleResultReceiptRow(
            self,
            object_name_prefix=prefix,
        )
        layout.addWidget(self._receipt_row)
        self._sync_properties()
        self.setVisible(False)

    @property
    def receipt_row(self) -> StyleResultReceiptRow:
        return self._receipt_row

    def has_receipt(self) -> bool:
        return not self._receipt_row.isHidden()

    def apply_envelope(self, envelope: object | None) -> None:
        self._receipt_row.apply_envelope(envelope)
        self.sync_to_receipt()

    def set_summary(self, text: str) -> None:
        self._receipt_row.set_summary(text)
        self.sync_to_receipt()

    def sync_to_receipt(self) -> None:
        self.setVisible(self.has_receipt())
        self.updateGeometry()

    def _sync_properties(self) -> None:
        self.setProperty("style_management_mode", self._mode)
        self.setProperty("style_management_content_plan", "receipt")
        for section in ("source", "scope", "rules", "difference", "editor", "preview"):
            self.setProperty(f"style_management_has_{section}", False)
        self.setProperty("style_management_has_receipt", True)
        self.setProperty("style_receipt_slot_surface", "embedded")


__all__ = ["StyleReceiptSlotFrame"]
