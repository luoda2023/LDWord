"""Stable preview surface for style-management blocks."""

from __future__ import annotations

from src.qt_api import QLabel, QSizePolicy, QVBoxLayout, QWidget
from src.shared.ui.layout_sync import refresh_layout_chain, refresh_layout_chain_later
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.theme import bind_theme, get_theme


def style_preview_renderer_protocol(widget: QWidget | None) -> str:
    """Return the preview renderer protocol implemented by a renderer widget."""

    if widget is None:
        return "none"
    if callable(getattr(widget, "apply_envelope", None)):
        return "envelope_projection"
    if callable(getattr(widget, "apply_projection", None)):
        return "projection"
    if callable(getattr(widget, "apply_presentation_envelope", None)):
        return "presentation_envelope"
    return "unsupported"


class StylePreviewSurface(QWidget):
    """Shared envelope-aware shell for style preview renderers."""

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_preview",
        renderer_widget: QWidget | None = None,
        renderer_kind: str = "",
        show_metadata: bool = True,
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_preview").strip()
        self._renderer_widget: QWidget | None = None
        self._renderer_kind = str(renderer_kind or "").strip()
        self._show_metadata = bool(show_metadata)
        self._envelope = StylePresentationEnvelope.from_object(None)
        self._preview_variant_key = ""
        self.setObjectName(f"{prefix}_surface")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().card_content_spacing)

        self._summary_label = QLabel("", self)
        self._summary_label.setObjectName(f"{prefix}_summary")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        self._detail_label = QLabel("", self)
        self._detail_label.setObjectName(f"{prefix}_detail")
        self._detail_label.setWordWrap(True)
        self._detail_label.setVisible(False)
        layout.addWidget(self._detail_label)

        if renderer_widget is not None:
            self.set_renderer(renderer_widget, renderer_kind=renderer_kind)

        self._sync_properties()
        bind_theme(self, self.apply_theme)
        self.apply_theme()

    @property
    def summary_label(self) -> QLabel:
        return self._summary_label

    @property
    def detail_label(self) -> QLabel:
        return self._detail_label

    @property
    def renderer_widget(self) -> QWidget | None:
        return self._renderer_widget

    @property
    def presentation_envelope(self) -> StylePresentationEnvelope:
        return self._envelope

    def set_renderer(
        self,
        widget: QWidget,
        *,
        renderer_kind: str = "",
    ) -> None:
        protocol = style_preview_renderer_protocol(widget)
        if protocol == "unsupported":
            raise TypeError(
                "renderer_widget must implement apply_envelope(...), "
                "apply_projection(...), or apply_presentation_envelope(...)."
            )
        layout = self.layout()
        if layout is None:
            return
        if self._renderer_widget is not None:
            layout.removeWidget(self._renderer_widget)
        self._renderer_widget = widget
        self._renderer_kind = str(renderer_kind or self._renderer_kind or "").strip()
        widget.setParent(self)
        layout.addWidget(widget)
        self._sync_properties()

    def apply_envelope(
        self,
        envelope: StylePresentationEnvelope | object | None,
        *,
        sync_renderer: bool = True,
    ) -> None:
        self._envelope = StylePresentationEnvelope.from_object(envelope)
        self._preview_variant_key = ""
        self._sync_text()
        if sync_renderer:
            self._sync_renderer_envelope()
        self._sync_properties()
        refresh_layout_chain(self)
        refresh_layout_chain_later(self)

    def apply_preview_projection(
        self,
        projection,
        *,
        envelope: StylePresentationEnvelope | object | None = None,
        empty_text: str = "",
    ) -> None:
        presentation = StylePresentationEnvelope.from_object(envelope)
        if projection is not None and presentation.is_empty():
            presentation = StylePresentationEnvelope.from_preview_projection(projection)
        self._envelope = presentation
        self._preview_variant_key = str(getattr(projection, "variant_key", "") or "")
        self._sync_renderer_preview_projection(
            projection,
            presentation,
            empty_text=empty_text,
        )
        self._sync_text()
        self._sync_properties()
        refresh_layout_chain(self)
        refresh_layout_chain_later(self)

    def apply_theme(self) -> None:
        t = get_theme()
        layout = self.layout()
        if layout is not None:
            layout.setSpacing(t.card_content_spacing)
        self._summary_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._detail_label.setStyleSheet(
            f"font-size: {t.font_size_sm - 1}px; color: {t.text_hint};"
        )

    def _sync_text(self) -> None:
        summary = self._envelope.summary
        detail = self._envelope.detail
        self._summary_label.setText(summary)
        self._summary_label.setVisible(bool(self._show_metadata and summary))
        detail_visible = bool(detail and detail != summary)
        self._detail_label.setText(detail)
        self._detail_label.setVisible(bool(self._show_metadata and detail_visible))
        self.setToolTip(self._envelope.tooltip_text())

    def _sync_renderer_envelope(self) -> None:
        renderer = self._renderer_widget
        if renderer is None:
            return
        protocol = style_preview_renderer_protocol(renderer)
        if protocol == "presentation_envelope":
            renderer.apply_presentation_envelope(self._envelope)
            return
        if protocol == "envelope_projection":
            renderer.apply_envelope(self._envelope)

    def _sync_renderer_preview_projection(
        self,
        projection,
        presentation: StylePresentationEnvelope,
        *,
        empty_text: str = "",
    ) -> None:
        renderer = self._renderer_widget
        if renderer is None:
            return
        protocol = style_preview_renderer_protocol(renderer)
        if protocol == "envelope_projection":
            renderer.apply_envelope(
                presentation,
                projection,
                empty_text=empty_text or "选择对象后预览样式",
            )
            return
        if protocol == "projection":
            renderer.apply_projection(projection, empty_text=empty_text)
            return
        if protocol == "presentation_envelope":
            renderer.apply_presentation_envelope(presentation)

    def _sync_properties(self) -> None:
        renderer_protocol = style_preview_renderer_protocol(self._renderer_widget)
        self.setProperty("style_preview_surface_renderer_kind", self._renderer_kind)
        self.setProperty("style_preview_surface_renderer_protocol", renderer_protocol)
        self.setProperty(
            "style_preview_surface_renderer_ready",
            renderer_protocol in {
                "envelope_projection",
                "projection",
                "presentation_envelope",
            },
        )
        self.setProperty("style_preview_surface_show_metadata", self._show_metadata)
        self.setProperty("style_presentation_kind", self._envelope.kind)
        self.setProperty("style_presentation_title", self._envelope.display_title())
        self.setProperty("style_presentation_variant_key", self._preview_variant_key)
        self.setProperty("style_presentation_source_label", self._envelope.source_label)
        self.setProperty("style_presentation_summary", self._envelope.summary)
        self.setProperty("style_presentation_detail", self._envelope.detail)
        self.setProperty("style_presentation_action_label", self._envelope.action_label)


__all__ = ["StylePreviewSurface", "style_preview_renderer_protocol"]
