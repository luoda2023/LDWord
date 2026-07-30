"""Typed services for delivery-only attachment materials."""

from importlib import import_module

from src.services.material_attachments.intake import (
    AttachmentIntakeError,
    attachment_extensions_for_types,
    build_attachment_binding,
    build_directory_attachment_binding,
    build_single_attachment_binding,
    inspect_attachment_file,
)
from src.services.material_attachments.requirements import (
    AttachmentRequirementAction,
    AttachmentRequirementKind,
    AttachmentRequirementOwner,
    AttachmentRequirementProjection,
    AttachmentRequirementReport,
    AttachmentRequirementState,
    AttachmentTokenRequirement,
    project_attachment_token_requirements,
    scan_attachment_token_requirements,
)
from src.services.material_attachments.preparation import (
    AttachmentPreparationReport,
    AttachmentPreparationRequirement,
    AttachmentProfileRequirement,
    build_attachment_preparation_report,
)

_PROCESSING_EXPORTS = frozenset(
    {
        "AttachmentBundleBuildRequest",
        "AttachmentBundleProcessingError",
        "AttachmentBundleService",
        "AttachmentProcessingDiagnostic",
        "process_attachment_bundle",
    }
)


def __getattr__(name: str):
    """Load execution-heavy exports only when callers actually request them.

    The content composer imports the attachment DOCX renderer during entity
    configuration startup.  Eagerly importing the processing service here
    would also initialize the image service package and create an
    entity -> composer -> attachment -> image -> entity cycle.
    """

    if name not in _PROCESSING_EXPORTS:
        raise AttributeError(name)
    processing = import_module("src.services.material_attachments.processing")
    value = getattr(processing, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _PROCESSING_EXPORTS)

__all__ = [
    "AttachmentIntakeError",
    "AttachmentBundleBuildRequest",
    "AttachmentBundleProcessingError",
    "AttachmentBundleService",
    "AttachmentProcessingDiagnostic",
    "AttachmentRequirementAction",
    "AttachmentRequirementKind",
    "AttachmentRequirementOwner",
    "AttachmentRequirementProjection",
    "AttachmentRequirementReport",
    "AttachmentRequirementState",
    "AttachmentTokenRequirement",
    "AttachmentPreparationReport",
    "AttachmentPreparationRequirement",
    "AttachmentProfileRequirement",
    "attachment_extensions_for_types",
    "build_attachment_binding",
    "build_attachment_preparation_report",
    "build_directory_attachment_binding",
    "build_single_attachment_binding",
    "inspect_attachment_file",
    "project_attachment_token_requirements",
    "process_attachment_bundle",
    "scan_attachment_token_requirements",
]
