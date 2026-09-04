"""Shared shell for paragraph-style editing surfaces."""

from __future__ import annotations

from collections.abc import Sequence

from src.qt_api import QSizePolicy, QVBoxLayout, QWidget, Signal
from src.shared.ui.paragraph_style_surface import StyleControlSurface
from src.shared.ui.style_owner_status_strip import StyleOwnerStatusStrip
from src.shared.ui.style_owner_toolbar import StyleControlOwnerToolbar, StyleOwnerOption
from src.shared.ui.style_presentation_envelope import StylePresentationEnvelope
from src.shared.ui.style_preview import StylePreview
from src.shared.ui.style_preview_surface import StylePreviewSurface
from src.shared.ui.theme import bind_theme, get_theme


class StyleEditingSection(QWidget):
    """Reusable shell combining owner controls, preview, and style surface."""

    current_key_changed = Signal(str)
    action_requested = Signal()
    style_changed = Signal()

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_editing",
        owner_options: Sequence[StyleOwnerOption] = (),
        show_owner_toolbar: bool = True,
        owner_title: str = "编辑样式",
        selector_label: str = "编辑对象",
        action_label: str = "恢复",
        show_owner_status: bool = True,
        show_preview: bool = True,
        preview_object_name: str | None = None,
        chrome_parent: QWidget | None = None,
        embed_chrome: bool = True,
        surface_object_name_prefix: str | None = None,
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_editing").strip()
        surface_prefix = str(surface_object_name_prefix or prefix).strip()
        self.setObjectName(f"{prefix}_section")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)

        self._chrome_widget = QWidget(chrome_parent or self)
        self._chrome_widget.setObjectName(f"{prefix}_chrome")
        chrome_layout = QVBoxLayout(self._chrome_widget)
        chrome_layout.setContentsMargins(0, 0, 0, 0)
        chrome_layout.setSpacing(6)

        self._owner_status: StyleOwnerStatusStrip | None = None
        if show_owner_status:
            self._owner_status = StyleOwnerStatusStrip(
                self._chrome_widget,
                object_name_prefix=f"{prefix}_status",
            )
            chrome_layout.addWidget(self._owner_status)

        self._owner_toolbar: StyleControlOwnerToolbar | None = None
        if show_owner_toolbar:
            self._owner_toolbar = StyleControlOwnerToolbar(
                self._chrome_widget,
                title=owner_title,
                selector_label=selector_label,
                action_label=action_label,
                object_name_prefix=f"{prefix}_owner",
            )
            self._owner_toolbar.set_options(tuple(owner_options))
            self._owner_toolbar.current_key_changed.connect(
                self.current_key_changed.emit
            )
            self._owner_toolbar.action_requested.connect(self.action_requested.emit)
            chrome_layout.addWidget(self._owner_toolbar)

        self._preview_surface: StylePreviewSurface | None = None
        self._preview: StylePreview | None = None
        if show_preview:
            self._preview_surface = StylePreviewSurface(
                self._chrome_widget,
                object_name_prefix=f"{prefix}_preview",
                renderer_kind="paragraph",
                show_metadata=False,
            )
            self._preview = StylePreview(self._preview_surface)
            self._preview.setObjectName(preview_object_name or f"{prefix}_preview")
            self._preview_surface.set_renderer(
                self._preview,
                renderer_kind="paragraph",
            )
            chrome_layout.addWidget(self._preview_surface)

        chrome_enabled = bool(show_owner_status or show_owner_toolbar or show_preview)
        self._chrome_widget.setVisible(chrome_enabled)
        if embed_chrome and chrome_enabled:
            layout.addWidget(self._chrome_widget)

        self._style_surface = StyleControlSurface(
            self,
            object_name_prefix=surface_prefix,
        )
        self._style_surface.style_changed.connect(self.style_changed.emit)
        layout.addWidget(self._style_surface)

        bind_theme(self, self.apply_theme)
        self.apply_theme()

    @property
    def chrome_widget(self) -> QWidget:
        return self._chrome_widget

    @property
    def owner_toolbar(self) -> StyleControlOwnerToolbar | None:
        return self._owner_toolbar

    @property
    def owner_status(self) -> StyleOwnerStatusStrip | None:
        return self._owner_status

    @property
    def selector(self):
        return self._owner_toolbar.selector if self._owner_toolbar is not None else None

    @property
    def action_button(self):
        return (
            self._owner_toolbar.action_button
            if self._owner_toolbar is not None
            else None
        )

    @property
    def hint_label(self):
        return self._owner_toolbar.hint_label if self._owner_toolbar is not None else None

    @property
    def preview(self) -> StylePreview | None:
        return self._preview

    @property
    def preview_surface(self) -> StylePreviewSurface | None:
        return self._preview_surface

    @property
    def style_surface(self) -> StyleControlSurface:
        return self._style_surface

    @property
    def editor(self):
        return self._style_surface.editor

    @property
    def unit_labels(self):
        return (self.editor.line_value_suffix,)

    def set_owner_options(self, options: Sequence[StyleOwnerOption]) -> None:
        if self._owner_toolbar is not None:
            self._owner_toolbar.set_options(tuple(options))

    def set_current_key(self, key: str) -> bool:
        if self._owner_toolbar is None:
            return False
        return self._owner_toolbar.set_current_key(key)

    def current_key(self) -> str:
        if self._owner_toolbar is None:
            return ""
        return self._owner_toolbar.current_key()

    def set_action_enabled(self, enabled: bool) -> None:
        if self._owner_toolbar is not None:
            self._owner_toolbar.set_action_enabled(enabled)

    def set_hint(self, text: str) -> None:
        if self._owner_toolbar is not None:
            self._owner_toolbar.set_hint(text)

    def apply_preview_projection(
        self,
        projection,
        *,
        empty_text: str = "",
        envelope: StylePresentationEnvelope | object | None = None,
    ) -> None:
        if self._preview_surface is None:
            return
        self._preview_surface.apply_preview_projection(
            projection,
            envelope=envelope,
            empty_text=empty_text,
        )

    def apply_owner_state(self, owner_state) -> None:
        self._style_surface.apply_state(owner_state.surface_state)
        if self._owner_status is not None:
            self._owner_status.apply_owner_state(owner_state)
        self.set_action_enabled(owner_state.action_enabled)
        self.set_hint(owner_state.hint)

    def apply_theme(self) -> None:
        layout = self.layout()
        if layout is not None:
            layout.setSpacing(get_theme().template_detail_section_gap)
        chrome_layout = self._chrome_widget.layout()
        if chrome_layout is not None:
            chrome_layout.setSpacing(6)
        if self._owner_toolbar is not None:
            self._owner_toolbar.apply_theme()
        if self._owner_status is not None:
            self._owner_status.apply_theme()

__all__ = ["StyleEditingSection"]
