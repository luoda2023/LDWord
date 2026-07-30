"""Provider-to-compiler content generation with disclosure enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.assistant.adapters.content_generation_adapter import (
    AssistantContentGenerationAdapter,
    GeneratedDraft,
)
from src.assistant.application.capability_registry import (
    NARRATIVE_PROMPT_PROFILE_ID,
    system_prompt_for_profile,
)
from src.assistant.domain.exam_authoring_contract import (
    exam_generation_prompt_addendum,
)
from src.assistant.contracts.task_plan import (
    ARTIFACT_KIND_EXAM,
    ARTIFACT_KIND_NARRATIVE,
)
from src.assistant.contracts.permissions import DisclosureGrant
from src.assistant.runtime.cancellation import AssistantCancellationToken, is_cancelled
from src.assistant.runtime.provider_contract import (
    MAX_PROVIDER_OUTPUT_CHARACTERS,
    PROVIDER_DONE,
    PROVIDER_ERROR,
    PROVIDER_TEXT_DELTA,
    ModelGateway,
    ProviderRequest,
)


@dataclass(frozen=True, slots=True)
class ContentGenerationRequest:
    session_id: str
    turn_id: str
    prompt: str
    provider_id: str
    model_id: str
    context_text: str = ""
    context_documents: tuple[dict[str, object], ...] = ()
    context_refs: tuple[str, ...] = ()
    context_fields: tuple[str, ...] = ()
    context_fingerprints: tuple[tuple[str, str], ...] = ()
    disclosure_grant: DisclosureGrant | None = None
    capability_id: str = ""
    artifact_kind: str = ARTIFACT_KIND_NARRATIVE
    prompt_profile_id: str = NARRATIVE_PROMPT_PROFILE_ID

    def __post_init__(self) -> None:
        if not self.session_id or not self.turn_id or not self.prompt.strip():
            raise ValueError("Content generation identity and prompt are required")
        object.__setattr__(
            self,
            "context_documents",
            tuple(dict(item) for item in self.context_documents),
        )
        if self.context_text or self.context_documents:
            grant = self.disclosure_grant
            fingerprints = dict(self.context_fingerprints)
            if grant is None or not grant.permits(
                session_id=self.session_id,
                provider_id=self.provider_id,
                model_id=self.model_id,
                refs=self.context_refs,
                fields=self.context_fields,
                fingerprints=fingerprints,
            ):
                raise PermissionError("content_context_disclosure_not_authorized")


class AssistantContentGenerationService:
    def __init__(self, adapter: AssistantContentGenerationAdapter) -> None:
        self.adapter = adapter

    def generate(
        self,
        request: ContentGenerationRequest,
        gateway: ModelGateway,
        *,
        cancellation: AssistantCancellationToken | None = None,
        delta_callback=None,
    ) -> GeneratedDraft:
        unregister = (
            cancellation.register_cancel_callback(gateway.cancel)
            if cancellation is not None
            else lambda: None
        )
        system_prompt = system_prompt_for_profile(request.prompt_profile_id)
        if request.artifact_kind == ARTIFACT_KIND_EXAM:
            system_prompt += exam_generation_prompt_addendum(request.prompt)
        user_content = request.prompt.strip()
        context_text = request.context_text
        if request.context_documents:
            from src.assistant.runtime.turn_runner import build_attachment_context

            extracted, _audit = build_attachment_context(request.context_documents)
            context_text = "\n\n".join(
                part for part in (context_text.strip(), extracted.strip()) if part
            )
        if context_text:
            user_content += "\n\n以下素材已由用户明确授权用于本次生成：\n" + context_text
        provider_request = ProviderRequest(
            request_id=uuid4().hex,
            model=request.model_id,
            system_prompt=system_prompt,
            messages=({"role": "user", "content": user_content},),
            metadata={
                "session_id": request.session_id,
                "purpose": "content_generation",
                "capability_id": request.capability_id,
                "artifact_kind": request.artifact_kind,
                "prompt_profile_id": request.prompt_profile_id,
            },
        )
        parts: list[str] = []
        output_character_count = 0
        try:
            for event in gateway.stream(provider_request):
                if is_cancelled(cancellation):
                    raise RuntimeError("content_generation_cancelled")
                if event.type == PROVIDER_TEXT_DELTA:
                    output_character_count += len(event.text)
                    if output_character_count > MAX_PROVIDER_OUTPUT_CHARACTERS:
                        gateway.cancel()
                        raise RuntimeError("generated_content_too_large")
                    parts.append(event.text)
                    if delta_callback is not None:
                        delta_callback(event.text)
                elif event.type == PROVIDER_ERROR:
                    raise RuntimeError(event.text or "content_generation_provider_failed")
                elif event.type == PROVIDER_DONE and not parts and event.text:
                    if len(event.text) > MAX_PROVIDER_OUTPUT_CHARACTERS:
                        raise RuntimeError("generated_content_too_large")
                    parts.append(event.text)
            if is_cancelled(cancellation):
                raise RuntimeError("content_generation_cancelled")
            return self.adapter.compile_generated(
                session_id=request.session_id,
                markdown="".join(parts),
                artifact_kind=request.artifact_kind,
                intent=request.prompt,
                prompt_profile_id=request.prompt_profile_id,
                cancelled=(cancellation.cancelled if cancellation is not None else None),
            )
        finally:
            unregister()


__all__ = ["AssistantContentGenerationService", "ContentGenerationRequest"]
