"""Public facade for the template-authoring workbench.

The implementation is intentionally split by change reason:

- ``template_authoring_layout`` owns user-facing paths and projections;
- ``template_authoring_contract`` owns typed AI envelopes;
- ``template_import_service`` owns validation, commit, archive, and records.

Keeping this compatibility facade avoids forcing UI callers to know the
internal module topology while preventing another thousand-line service blob.
"""

from src.config.template_authoring_contract import (
    AUTHORING_BASELINE_KIND,
    AUTHORING_PROMPT_VERSION,
    AUTHORING_RESULT_KIND,
    AUTHORING_SCHEMA_VERSION,
    TemplateAuthoringContract,
    TemplateAuthoringObservations,
)
from src.config.template_authoring_layout import (
    ARCHIVE_NAME,
    AUTHORING_STATE_NAME,
    AUTHORING_WORKSPACE_NAME,
    BASELINE_FILENAME,
    FAILED_NAME,
    IMPORT_RECORDS_NAME,
    INBOX_NAME,
    PROCESSING_NAME,
    PROMPT_FILENAME,
    SUCCESS_NAME,
    WORKBENCH_INDEX_FILENAME,
    TemplateAuthoringWorkspace,
    ensure_template_authoring_workspace,
    list_template_authoring_workspace_descriptors,
    refresh_template_authoring_workbench_index,
    template_authoring_state_path,
    template_authoring_workbench_path,
    template_authoring_workspace_descriptor,
    template_authoring_workspace_path,
)
from src.config.template_import_service import (
    TemplateImportBatch,
    TemplateImportError,
    TemplateImportIssue,
    TemplateImportSuccess,
    import_template_authoring_result_text,
    process_template_import_inbox,
)


__all__ = [
    "ARCHIVE_NAME",
    "AUTHORING_BASELINE_KIND",
    "AUTHORING_PROMPT_VERSION",
    "AUTHORING_RESULT_KIND",
    "AUTHORING_SCHEMA_VERSION",
    "AUTHORING_STATE_NAME",
    "AUTHORING_WORKSPACE_NAME",
    "BASELINE_FILENAME",
    "FAILED_NAME",
    "IMPORT_RECORDS_NAME",
    "INBOX_NAME",
    "PROCESSING_NAME",
    "PROMPT_FILENAME",
    "SUCCESS_NAME",
    "TemplateAuthoringContract",
    "TemplateAuthoringObservations",
    "TemplateAuthoringWorkspace",
    "TemplateImportBatch",
    "TemplateImportError",
    "TemplateImportIssue",
    "TemplateImportSuccess",
    "WORKBENCH_INDEX_FILENAME",
    "ensure_template_authoring_workspace",
    "import_template_authoring_result_text",
    "list_template_authoring_workspace_descriptors",
    "process_template_import_inbox",
    "refresh_template_authoring_workbench_index",
    "template_authoring_state_path",
    "template_authoring_workbench_path",
    "template_authoring_workspace_descriptor",
    "template_authoring_workspace_path",
]
