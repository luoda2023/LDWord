"""Typed intake and binding services for attachment resources."""

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

__all__ = [
    "AttachmentIntakeError",
    "AttachmentRequirementAction",
    "AttachmentRequirementKind",
    "AttachmentRequirementOwner",
    "AttachmentRequirementProjection",
    "AttachmentRequirementReport",
    "AttachmentRequirementState",
    "AttachmentTokenRequirement",
    "attachment_extensions_for_types",
    "build_attachment_binding",
    "build_directory_attachment_binding",
    "build_single_attachment_binding",
    "inspect_attachment_file",
    "project_attachment_token_requirements",
    "scan_attachment_token_requirements",
]
