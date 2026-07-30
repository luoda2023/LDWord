"""Durable, content-addressed material context bound to a document plan."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from src.assistant.contracts.serialization import payload_sha256, plain_data
from src.config.material_context import MaterialExecutionContext


MATERIAL_CONTEXT_SNAPSHOT_SCHEMA_VERSION = "form-material-context-snapshot-v1"


@dataclass(frozen=True, slots=True)
class MaterialContextSnapshot:
    context: Mapping[str, object]
    digest: str
    function_errors: Mapping[str, str]
    timeline_issues: tuple[dict[str, object], ...]
    schema_version: str = MATERIAL_CONTEXT_SNAPSHOT_SCHEMA_VERSION

    @classmethod
    def capture(
        cls,
        context: MaterialExecutionContext | None,
    ) -> "MaterialContextSnapshot":
        source = (
            context.clone()
            if isinstance(context, MaterialExecutionContext)
            else MaterialExecutionContext()
        )
        resolution = source.resolve_material_fields()
        frozen = source.with_frozen_field_resolution(resolution)
        context_payload = dict(plain_data(frozen.to_payload()))
        function_errors = {
            str(key): str(value)
            for key, value in resolution.function_errors.items()
        }
        timeline_issues = tuple(
            dict(plain_data(asdict(issue)))
            for issue in resolution.timeline_issues
        )
        digest = _snapshot_digest(
            context_payload,
            function_errors,
            timeline_issues,
        )
        return cls(
            context=context_payload,
            digest=digest,
            function_errors=function_errors,
            timeline_issues=timeline_issues,
        )

    def __post_init__(self) -> None:
        if self.schema_version != MATERIAL_CONTEXT_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("Unsupported material context snapshot schema")
        context = dict(plain_data(self.context))
        function_errors = {
            str(key): str(value)
            for key, value in self.function_errors.items()
        }
        timeline_issues = tuple(
            dict(plain_data(item)) for item in self.timeline_issues
        )
        expected = _snapshot_digest(
            context,
            function_errors,
            timeline_issues,
        )
        if not self.digest or self.digest != expected:
            raise ValueError("Material context snapshot digest mismatch")
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "function_errors", function_errors)
        object.__setattr__(self, "timeline_issues", timeline_issues)

    @property
    def has_resolution_errors(self) -> bool:
        return bool(
            self.function_errors
            or any(
                str(item.get("severity") or "").casefold() == "error"
                for item in self.timeline_issues
            )
        )

    def restore(self) -> MaterialExecutionContext:
        return MaterialExecutionContext.from_payload(self.context)

    def reference(self) -> dict[str, object]:
        context = self.restore()
        return {
            "schema_version": self.schema_version,
            "digest": self.digest,
            "package_id": context.package_id,
            "profile_id": context.profile_id,
            "field_count": len(context.frozen_field_values),
            "asset_count": len(context.asset_items),
            "content_count": len(context.content_bindings),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "digest": self.digest,
            "context": dict(self.context),
            "function_errors": dict(self.function_errors),
            "timeline_issues": [dict(item) for item in self.timeline_issues],
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> "MaterialContextSnapshot":
        context = value.get("context")
        function_errors = value.get("function_errors")
        timeline_issues = value.get("timeline_issues")
        return cls(
            schema_version=str(value.get("schema_version") or ""),
            digest=str(value.get("digest") or ""),
            context=dict(context) if isinstance(context, Mapping) else {},
            function_errors=(
                {
                    str(key): str(item)
                    for key, item in function_errors.items()
                }
                if isinstance(function_errors, Mapping)
                else {}
            ),
            timeline_issues=tuple(
                dict(item)
                for item in (
                    timeline_issues
                    if isinstance(timeline_issues, (list, tuple))
                    else ()
                )
                if isinstance(item, Mapping)
            ),
        )


def material_context_digest(
    context: MaterialExecutionContext | None,
) -> str:
    return MaterialContextSnapshot.capture(context).digest


def _snapshot_digest(
    context: Mapping[str, object],
    function_errors: Mapping[str, str],
    timeline_issues: tuple[dict[str, object], ...],
) -> str:
    return payload_sha256(
        {
            "schema_version": MATERIAL_CONTEXT_SNAPSHOT_SCHEMA_VERSION,
            "context": dict(context),
            "function_errors": dict(function_errors),
            "timeline_issues": [dict(item) for item in timeline_issues],
        }
    )


__all__ = [
    "MATERIAL_CONTEXT_SNAPSHOT_SCHEMA_VERSION",
    "MaterialContextSnapshot",
    "material_context_digest",
]
