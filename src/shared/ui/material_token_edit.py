"""Reusable material-token surface with frozen structure and core editing."""

from __future__ import annotations

from src.shared.ui.projected_text_edit import (
    EditActivation,
    ProjectedTextEdit,
    TextSurface,
)
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.text_projection import TextElideMode
from src.shared.ui.theme import get_theme
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    material_token_prefix,
    normalize_material_token,
    parse_material_token,
)


class MaterialTokenEdit(ProjectedTextEdit):
    """Display an exact ``{{Token}}`` with one-click copy.

    Editable instances enter rename mode on double-click and return to the
    read-only display state on editing completion.  Copy-only instances keep
    the same visual and clipboard contract without exposing rename behavior.
    """

    def __init__(
        self,
        text: object = "",
        parent=None,
        *,
        editable: bool = True,
        namespace: MaterialTokenNamespace | str | None = None,
    ) -> None:
        self._completed = False
        self._default_namespace = (
            None
            if namespace is None
            else MaterialTokenNamespace(str(getattr(namespace, "value", namespace)))
        )
        super().__init__(
            text,
            parent,
            editable=editable,
            activation=(
                EditActivation.COPY_DOUBLE_EDIT
                if editable
                else EditActivation.COPY_ONLY
            ),
            surface=TextSurface.PLAIN,
            elide_mode=TextElideMode.RIGHT,
            font_weight=get_theme().font_weight_emphasis,
            show_full_text_tooltip=True,
            expand_editor_on_overflow=True,
        )
        apply_size_class(self, "md")
        self._apply_theme()

    def setCompleted(self, completed: bool) -> None:  # noqa: N802
        self._completed = bool(completed)
        self._apply_theme()

    def isTokenEditable(self) -> bool:  # noqa: N802
        return self.isInlineEditable()

    def _canonical_from_input(self, value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if raw.startswith("{{") or raw.startswith("@"):
            return normalize_material_token(raw)
        return normalize_material_token(raw, namespace=self._default_namespace)

    def _split_canonical(self, canonical: str) -> tuple[str, str, str]:
        raw = str(canonical or "").strip()
        if not raw:
            return (
                material_token_prefix(self._default_namespace)
                if self._default_namespace is not None
                else "",
                "",
                "}}" if self._default_namespace is not None else "",
            )
        ref = parse_material_token(raw)
        return ref.locked_prefix, ref.identifier, "}}"

    def _compose_canonical(
        self,
        prefix: str,
        core: str,
        suffix: str,
    ) -> str:
        editable_core = str(core or "")
        if not editable_core:
            return ""
        resolved_prefix = str(prefix or "")
        resolved_suffix = str(suffix or "")
        if not resolved_prefix and self._default_namespace is not None:
            resolved_prefix = material_token_prefix(self._default_namespace)
            resolved_suffix = "}}"
        return resolved_prefix + editable_core + resolved_suffix

    def _expanded_editor_title(self) -> str:
        return "编辑占位符名称"

    def _expanded_editor_hint(self) -> str:
        return "前后结构会自动保留 · 点击卡片外完成修改"

    def _display_text_color(self, theme) -> str:
        if not self.text():
            return theme.text_hint
        return theme.primary if self._completed else theme.text_primary

    def _apply_theme(self) -> None:
        self._font_weight = get_theme().font_weight_emphasis
        super()._apply_theme()


__all__ = ["MaterialTokenEdit"]
