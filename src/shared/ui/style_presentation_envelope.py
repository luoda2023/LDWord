"""Shared presentation metadata for style preview and receipts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


STYLE_PRESENTATION_KIND_SECTION_PARAGRAPH = "section_paragraph"
STYLE_PRESENTATION_KIND_EXECUTION_RECEIPT = "execution_receipt"

STYLE_PRESENTATION_TITLE_PREVIEW = "样式预览"
STYLE_PRESENTATION_TITLE_SOURCE = "样式来源"
STYLE_PRESENTATION_SOURCE_CURRENT_RUN = "本次使用"
STYLE_PRESENTATION_ACTION_ADJUST_SECTION = "调整样式"


@dataclass(frozen=True, slots=True)
class StylePresentationEnvelope:
    """Normalize style presentation copy across preview and readonly receipts."""

    kind: str = STYLE_PRESENTATION_KIND_SECTION_PARAGRAPH
    title: str = ""
    source_label: str = ""
    summary: str = ""
    detail: str = ""
    action_label: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "kind",
            _clean(self.kind) or STYLE_PRESENTATION_KIND_SECTION_PARAGRAPH,
        )
        object.__setattr__(self, "title", _clean(self.title))
        object.__setattr__(self, "source_label", _clean(self.source_label))
        object.__setattr__(self, "summary", _clean(self.summary))
        object.__setattr__(self, "detail", _clean(self.detail))
        object.__setattr__(self, "action_label", _clean(self.action_label))

    @classmethod
    def from_object(
        cls,
        envelope,
        *,
        kind: str = STYLE_PRESENTATION_KIND_SECTION_PARAGRAPH,
        title: str = "",
    ) -> "StylePresentationEnvelope":
        """Build from an object with compatible presentation attributes."""

        if envelope is None:
            return cls(kind=kind, title=title)
        if isinstance(envelope, cls):
            if kind == STYLE_PRESENTATION_KIND_SECTION_PARAGRAPH and not title:
                return envelope
            return cls(
                kind=kind or envelope.kind,
                title=title or envelope.title,
                source_label=envelope.source_label,
                summary=envelope.summary,
                detail=envelope.detail,
                action_label=envelope.action_label,
            )
        return cls(
            kind=_attr(envelope, "kind", kind),
            title=_attr(envelope, "title", title),
            source_label=_attr(envelope, "source_label", ""),
            summary=_attr(envelope, "summary", ""),
            detail=_attr(envelope, "detail", ""),
            action_label=_attr(envelope, "action_label", ""),
        )

    @classmethod
    def from_preview_projection(
        cls,
        projection,
        *,
        kind: str = STYLE_PRESENTATION_KIND_SECTION_PARAGRAPH,
        title: str = "",
        action_label: str = "",
    ) -> "StylePresentationEnvelope":
        """Build shared preview metadata from a paragraph preview projection."""

        if projection is None:
            return cls(kind=kind, title=title)

        source_label = _attr(projection, "source_label", "")
        summary = _attr(projection, "summary", "") or source_label
        resolved_action = action_label or _attr(projection, "action_label", "")
        if not resolved_action and _attr(projection, "variant_key", ""):
            resolved_action = STYLE_PRESENTATION_ACTION_ADJUST_SECTION

        return cls(
            kind=kind,
            title=title
            or _attr(projection, "label", "")
            or _attr(projection, "title", "")
            or STYLE_PRESENTATION_TITLE_PREVIEW,
            source_label=source_label,
            summary=summary,
            detail=_attr(projection, "detail", ""),
            action_label=resolved_action,
        )

    @classmethod
    def from_execution_result(
        cls,
        style_source,
        *,
        fallback: str = "",
        title: str = STYLE_PRESENTATION_TITLE_SOURCE,
    ) -> "StylePresentationEnvelope":
        """Build shared metadata for a readonly execution style receipt."""

        fallback_text = _clean(fallback)
        if not style_source:
            return cls.from_summary(
                fallback_text,
                kind=STYLE_PRESENTATION_KIND_EXECUTION_RECEIPT,
                title=title,
            )

        summary = _source_value(style_source, "summary")
        if summary:
            return cls(
                kind=STYLE_PRESENTATION_KIND_EXECUTION_RECEIPT,
                title=title,
                source_label=STYLE_PRESENTATION_SOURCE_CURRENT_RUN,
                summary=summary,
            )

        template_label = _source_value(style_source, "template_label")
        if template_label:
            return cls(
                kind=STYLE_PRESENTATION_KIND_EXECUTION_RECEIPT,
                title=title,
                source_label=STYLE_PRESENTATION_SOURCE_CURRENT_RUN,
                summary=f"本次使用模板“{template_label}”。",
            )

        return cls.from_summary(
            fallback_text,
            kind=STYLE_PRESENTATION_KIND_EXECUTION_RECEIPT,
            title=title,
        )

    @classmethod
    def from_summary(
        cls,
        text: str,
        *,
        kind: str = STYLE_PRESENTATION_KIND_EXECUTION_RECEIPT,
        title: str = STYLE_PRESENTATION_TITLE_SOURCE,
    ) -> "StylePresentationEnvelope":
        """Build a receipt envelope from the legacy flat summary string."""

        summary = _clean(text)
        return cls(kind=kind, title=title, summary=summary)

    def is_empty(self) -> bool:
        return not any((self.title, self.source_label, self.summary, self.detail))

    def display_title(self, fallback: str = "") -> str:
        return self.title or self.source_label or _clean(fallback)

    def display_detail(self, *, title_fallback: str = "") -> str:
        title = self.display_title(title_fallback)
        values: list[str] = []
        for value in (self.summary, self.detail):
            detail = _strip_leading_title(value, title)
            if detail and detail not in values:
                values.append(detail)
        return "；".join(values)

    def receipt_summary(
        self,
        *,
        title_fallback: str = STYLE_PRESENTATION_TITLE_SOURCE,
    ) -> str:
        title = self.display_title(title_fallback)
        detail = self.display_detail(title_fallback=title)
        if not detail:
            return ""
        return f"{title}：{detail}"

    def preview_source_label(self, *, fallback: str = "") -> str:
        return self.source_label or self.title or _clean(fallback)

    def preview_detail(self, *, fallback: str = "") -> str:
        return self.detail or self.summary or _clean(fallback)

    def preview_sample_text(self, *, fallback: str = "") -> str:
        title = self.display_title()
        summary = self.summary or self.detail
        if title and summary:
            return f"{title}：{summary}"
        return summary or title or _clean(fallback)

    def tooltip_text(self) -> str:
        source = self.preview_source_label()
        detail = self.preview_detail()
        if source and detail:
            return f"{source}：{detail}"
        return source or detail


def _attr(source, name: str, default: str) -> str:
    return _clean(getattr(source, name, default))


def _source_value(source, name: str) -> str:
    if isinstance(source, Mapping):
        return _clean(source.get(name))
    return _attr(source, name, "")


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _strip_leading_title(value: str, title: str) -> str:
    text = _clean(value)
    if not text:
        return ""
    for candidate in (title, STYLE_PRESENTATION_TITLE_SOURCE):
        clean_title = _clean(candidate)
        if not clean_title:
            continue
        for separator in ("：", ":"):
            prefix = f"{clean_title}{separator}"
            if text.startswith(prefix):
                return text.removeprefix(prefix).strip()
    return text


__all__ = [
    "STYLE_PRESENTATION_ACTION_ADJUST_SECTION",
    "STYLE_PRESENTATION_KIND_EXECUTION_RECEIPT",
    "STYLE_PRESENTATION_KIND_SECTION_PARAGRAPH",
    "STYLE_PRESENTATION_SOURCE_CURRENT_RUN",
    "STYLE_PRESENTATION_TITLE_PREVIEW",
    "STYLE_PRESENTATION_TITLE_SOURCE",
    "StylePresentationEnvelope",
]
