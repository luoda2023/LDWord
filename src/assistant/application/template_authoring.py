"""Assistant-owned bridge from provider JSON to the strict template library."""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.config.template_authoring_workspace import (
    TemplateImportBatch,
    import_template_authoring_result_text,
)


_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*(?P<body>.*?)\s*```\s*$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class AssistantTemplateAuthoringCompletion:
    """One isolated provider-result import attempt."""

    mode_id: str
    result_text: str
    batch: TemplateImportBatch
    strategy: str = ""

    @property
    def succeeded(self) -> bool:
        return bool(self.batch.successes)


def normalize_template_authoring_result_text(value: str) -> str:
    """Remove common provider wrappers while preserving the JSON contract."""

    text = str(value or "").strip()
    fenced = _JSON_FENCE_RE.match(text)
    if fenced is not None:
        return fenced.group("body").strip()
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        return text[first : last + 1].strip()
    return text


def complete_template_authoring(
    *,
    mode_id: str,
    provider_text: str,
    strategy: str = "",
) -> AssistantTemplateAuthoringCompletion:
    """Persist and strictly import one model-produced template envelope."""

    normalized = normalize_template_authoring_result_text(provider_text)
    batch = import_template_authoring_result_text(mode_id, normalized)
    return AssistantTemplateAuthoringCompletion(
        mode_id=str(mode_id or "").strip(),
        result_text=normalized,
        batch=batch,
        strategy=str(strategy or "").strip(),
    )


__all__ = [
    "AssistantTemplateAuthoringCompletion",
    "complete_template_authoring",
    "normalize_template_authoring_result_text",
]
