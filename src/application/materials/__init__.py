"""Material-package application services."""

from .commands import MaterialCommandResult, MaterialPackageService
from .contracts import (
    PACKAGE_CONTRACT_EXTENSIONS_KEY,
    default_material_contract_id,
    get_material_contract,
    get_package_material_contract,
    material_contract_from_schema,
)
from .execution import (
    ExecutionMaterialFinalizeRequest,
    ExecutionMaterialGroup,
    ExecutionMaterialRecord,
    ExecutionMaterialSnapshot,
    ExecutionResource,
    MaterialRunBindRequest,
    MaterialRunBindResult,
    bind_material_run,
    execution_material_snapshot_from_payload,
    execution_material_snapshot_to_payload,
    finalize_execution_material_snapshot,
    image_policy_role_cardinality,
    image_policy_role_label,
    project_execution_material_record_snapshot,
)
from .import_workflow import (
    ImportCandidate,
    ImportMappingProfile,
    MaterialImportDraft,
    inspect_material_workbook,
    inspect_material_workbook_headers,
)
from .library_binding import bind_repository_material_run
from .preview import (
    RUNTIME_IMAGE_WATERMARK_KEY,
    MaterialPreviewSnapshot,
    MaterialRuntimeFieldPreview,
    project_material_preview,
)

__all__ = [
    "PACKAGE_CONTRACT_EXTENSIONS_KEY",
    "RUNTIME_IMAGE_WATERMARK_KEY",
    "ExecutionMaterialFinalizeRequest",
    "ExecutionMaterialGroup",
    "ExecutionMaterialRecord",
    "ExecutionMaterialSnapshot",
    "ExecutionResource",
    "ImportCandidate",
    "ImportMappingProfile",
    "MaterialCommandResult",
    "MaterialImportDraft",
    "MaterialPackageService",
    "MaterialPreviewSnapshot",
    "MaterialRunBindRequest",
    "MaterialRunBindResult",
    "MaterialRuntimeFieldPreview",
    "bind_material_run",
    "bind_repository_material_run",
    "default_material_contract_id",
    "execution_material_snapshot_from_payload",
    "execution_material_snapshot_to_payload",
    "finalize_execution_material_snapshot",
    "get_material_contract",
    "get_package_material_contract",
    "image_policy_role_cardinality",
    "image_policy_role_label",
    "inspect_material_workbook",
    "inspect_material_workbook_headers",
    "material_contract_from_schema",
    "project_execution_material_record_snapshot",
    "project_material_preview",
]
