"""Versioned document plan drafted by the assistant and approved by a user."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.assistant.contracts.serialization import mapping_tuple, payload_sha256, plain_data
from src.assistant.contracts.task_plan import (
    ARTIFACT_KIND_EXAM,
    ARTIFACT_KIND_NARRATIVE,
    DeliveryContract,
    GenerationContract,
    ProductionContract,
    SOURCE_ROLE_STRUCTURED_SOURCE,
    SourceArtifactRef,
    TaskCapabilityRef,
)


DOCUMENT_PLAN_SCHEMA_VERSION = "form-document-plan-v3"


@dataclass(frozen=True, slots=True)
class OutputPolicy:
    output_root: str = ""
    filename_suffix: str = "_formatted"
    overwrite: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_root": self.output_root,
            "filename_suffix": self.filename_suffix,
            "overwrite": bool(self.overwrite),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "OutputPolicy":
        data = value or {}
        return cls(
            output_root=str(data.get("output_root") or ""),
            filename_suffix=str(data.get("filename_suffix") or "_formatted"),
            overwrite=bool(data.get("overwrite", False)),
        )


@dataclass(frozen=True, slots=True)
class PlanBlockingIssue:
    code: str
    message: str
    action_id: str = "open_workbench"

    def __post_init__(self) -> None:
        if not str(self.code or "").strip() or not str(self.message or "").strip():
            raise ValueError("Plan blocking issue requires code and message")

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "action_id": self.action_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlanBlockingIssue":
        return cls(
            code=str(value.get("code") or ""),
            message=str(value.get("message") or ""),
            action_id=str(value.get("action_id") or "open_workbench"),
        )


@dataclass(frozen=True, slots=True)
class DocumentPlan:
    plan_id: str
    revision: int
    intent: str
    created_by_turn_id: str
    input_document_ref: Mapping[str, Any] = field(default_factory=dict)
    work_mode_id: str = ""
    scene_ref: Mapping[str, Any] = field(default_factory=dict)
    template_ref: Mapping[str, Any] = field(default_factory=dict)
    theme_ref: Mapping[str, Any] = field(default_factory=dict)
    material_refs: tuple[dict[str, Any], ...] = ()
    material_snapshot_ref: Mapping[str, Any] = field(default_factory=dict)
    content_fragment_refs: tuple[dict[str, Any], ...] = ()
    output_policy: OutputPolicy = field(default_factory=OutputPolicy)
    operation: str = "transform"
    capability_ref: TaskCapabilityRef = field(default_factory=TaskCapabilityRef)
    source_artifacts: tuple[SourceArtifactRef, ...] = ()
    generation_contract: GenerationContract = field(
        default_factory=GenerationContract
    )
    production_contract: ProductionContract = field(
        default_factory=ProductionContract
    )
    delivery_contract: DeliveryContract = field(default_factory=DeliveryContract)
    warnings: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    blocking_issues: tuple[PlanBlockingIssue, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.plan_id or "").strip():
            raise ValueError("Document plan_id is required")
        if int(self.revision) < 1:
            raise ValueError("Document plan revision must be at least 1")
        if not str(self.intent or "").strip():
            raise ValueError("Document plan intent is required")
        if not str(self.created_by_turn_id or "").strip():
            raise ValueError("Document plan created_by_turn_id is required")
        for name in (
            "input_document_ref",
            "scene_ref",
            "template_ref",
            "theme_ref",
            "material_snapshot_ref",
        ):
            object.__setattr__(self, name, dict(plain_data(getattr(self, name))))
        object.__setattr__(self, "material_refs", mapping_tuple(self.material_refs))
        object.__setattr__(self, "content_fragment_refs", mapping_tuple(self.content_fragment_refs))
        object.__setattr__(
            self,
            "capability_ref",
            (
                TaskCapabilityRef.from_dict(self.capability_ref)
                if isinstance(self.capability_ref, Mapping)
                else self.capability_ref
            ),
        )
        object.__setattr__(
            self,
            "source_artifacts",
            tuple(
                SourceArtifactRef.from_dict(item)
                if isinstance(item, Mapping)
                else item
                for item in self.source_artifacts
            ),
        )
        object.__setattr__(
            self,
            "generation_contract",
            (
                GenerationContract.from_dict(self.generation_contract)
                if isinstance(self.generation_contract, Mapping)
                else self.generation_contract
            ),
        )
        object.__setattr__(
            self,
            "production_contract",
            (
                ProductionContract.from_dict(self.production_contract)
                if isinstance(self.production_contract, Mapping)
                else self.production_contract
            ),
        )
        object.__setattr__(
            self,
            "delivery_contract",
            (
                DeliveryContract.from_dict(self.delivery_contract)
                if isinstance(self.delivery_contract, Mapping)
                else self.delivery_contract
            ),
        )
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))
        object.__setattr__(
            self,
            "unresolved_questions",
            tuple(str(item) for item in self.unresolved_questions),
        )
        object.__setattr__(
            self,
            "blocking_issues",
            tuple(
                PlanBlockingIssue.from_dict(item)
                if isinstance(item, Mapping)
                else item
                for item in self.blocking_issues
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DOCUMENT_PLAN_SCHEMA_VERSION,
            "contract_kind": "document_plan",
            "plan_id": self.plan_id,
            "revision": self.revision,
            "intent": self.intent,
            "input_document_ref": dict(self.input_document_ref),
            "work_mode_id": self.work_mode_id,
            "scene_ref": dict(self.scene_ref),
            "template_ref": dict(self.template_ref),
            "theme_ref": dict(self.theme_ref),
            "material_refs": [dict(item) for item in self.material_refs],
            "material_snapshot_ref": dict(self.material_snapshot_ref),
            "content_fragment_refs": [dict(item) for item in self.content_fragment_refs],
            "output_policy": self.output_policy.to_dict(),
            "operation": self.operation,
            "capability_ref": self.capability_ref.to_dict(),
            "source_artifacts": [
                artifact.to_dict() for artifact in self.source_artifacts
            ],
            "generation_contract": self.generation_contract.to_dict(),
            "production_contract": self.production_contract.to_dict(),
            "delivery_contract": self.delivery_contract.to_dict(),
            "warnings": list(self.warnings),
            "unresolved_questions": list(self.unresolved_questions),
            "blocking_issues": [
                issue.to_dict() for issue in self.blocking_issues
            ],
            "created_by_turn_id": self.created_by_turn_id,
        }

    @property
    def fingerprint(self) -> str:
        return payload_sha256(self.to_dict())

    @property
    def generation_required(self) -> bool:
        return bool(self.generation_contract.required)

    @property
    def production_input_artifact(self) -> SourceArtifactRef | None:
        requested_role = self.production_contract.input_role
        for artifact in self.source_artifacts:
            if artifact.role == requested_role and artifact.path:
                return artifact
        return None

    @property
    def production_input_ref(self) -> dict[str, Any]:
        artifact = self.production_input_artifact
        if artifact is not None:
            return artifact.to_dict()
        return dict(self.input_document_ref)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DocumentPlan":
        generation_data = (
            value.get("generation_contract")
            if isinstance(value.get("generation_contract"), Mapping)
            else None
        )
        production_data = (
            value.get("production_contract")
            if isinstance(value.get("production_contract"), Mapping)
            else None
        )
        delivery_data = (
            value.get("delivery_contract")
            if isinstance(value.get("delivery_contract"), Mapping)
            else None
        )
        scene_ref = (
            value.get("scene_ref")
            if isinstance(value.get("scene_ref"), Mapping)
            else {}
        )
        work_mode_id = str(value.get("work_mode_id") or "")
        legacy_generation_mode = str(scene_ref.get("generation_mode") or "")
        if generation_data is None and legacy_generation_mode in {
            "from_prompt",
            "from_material",
            "generated_draft",
        }:
            is_exam = work_mode_id == "exam"
            generation_data = {
                "required": True,
                "artifact_kind": (
                    ARTIFACT_KIND_EXAM if is_exam else ARTIFACT_KIND_NARRATIVE
                ),
                "prompt_profile_id": (
                    "assistant.exam-paper-markdown.v1"
                    if is_exam
                    else "assistant.narrative-markdown.v1"
                ),
                "validator_id": "exam_items_v1" if is_exam else "content-ir-v2",
            }
            if is_exam and production_data is None:
                production_data = {
                    "input_role": SOURCE_ROLE_STRUCTURED_SOURCE,
                    "artifact_kind": ARTIFACT_KIND_EXAM,
                    "validator_id": "exam_items_v1",
                    "terminal_assembler": "exam",
                    "accepted_suffixes": [".md", ".markdown"],
                }
            if is_exam and delivery_data is None:
                delivery_data = {
                    "default_preset_id": "student",
                    "preset_ids": ["student", "answer"],
                    "required_artifact_keys": ["student", "answer_key"],
                }
        return cls(
            plan_id=str(value.get("plan_id") or ""),
            revision=int(value.get("revision") or 0),
            intent=str(value.get("intent") or ""),
            created_by_turn_id=str(value.get("created_by_turn_id") or ""),
            input_document_ref=value.get("input_document_ref") if isinstance(value.get("input_document_ref"), Mapping) else {},
            work_mode_id=work_mode_id,
            scene_ref=scene_ref,
            template_ref=value.get("template_ref") if isinstance(value.get("template_ref"), Mapping) else {},
            theme_ref=value.get("theme_ref") if isinstance(value.get("theme_ref"), Mapping) else {},
            material_refs=mapping_tuple(value.get("material_refs")),
            material_snapshot_ref=(
                value.get("material_snapshot_ref")
                if isinstance(value.get("material_snapshot_ref"), Mapping)
                else {}
            ),
            content_fragment_refs=mapping_tuple(value.get("content_fragment_refs")),
            output_policy=OutputPolicy.from_dict(
                value.get("output_policy") if isinstance(value.get("output_policy"), Mapping) else None
            ),
            operation=str(value.get("operation") or "transform"),
            capability_ref=TaskCapabilityRef.from_dict(
                value.get("capability_ref")
                if isinstance(value.get("capability_ref"), Mapping)
                else None
            ),
            source_artifacts=tuple(
                SourceArtifactRef.from_dict(item)
                for item in (value.get("source_artifacts") or ())
                if isinstance(item, Mapping)
            ),
            generation_contract=GenerationContract.from_dict(
                generation_data
            ),
            production_contract=ProductionContract.from_dict(
                production_data
            ),
            delivery_contract=DeliveryContract.from_dict(
                delivery_data
            ),
            warnings=tuple(str(item) for item in value.get("warnings", ())),
            unresolved_questions=tuple(str(item) for item in value.get("unresolved_questions", ())),
            blocking_issues=tuple(
                PlanBlockingIssue.from_dict(item)
                for item in value.get("blocking_issues", ())
                if isinstance(item, Mapping)
            ),
        )


__all__ = [
    "DOCUMENT_PLAN_SCHEMA_VERSION",
    "DocumentPlan",
    "OutputPolicy",
    "PlanBlockingIssue",
]
