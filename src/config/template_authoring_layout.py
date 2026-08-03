"""Stable user-facing template workbench layout and index projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from src.config import library
from src.config.atomic_io import atomic_write_text
from src.config.builtin_templates import create_builtin_template
from src.config.template import TemplateConfig
from src.config.template_authoring_contract import (
    AUTHORING_PROMPT_VERSION,
    AUTHORING_RESULT_KIND,
    AUTHORING_SCHEMA_VERSION,
    TemplateAuthoringBaselineEnvelope,
    TemplateAuthoringContract,
    TemplateAuthoringContractError,
    canonical_json_sha256,
    read_json_object,
)
from src.config.template_authoring_profile import (
    TemplateAuthoringProfile,
    get_template_authoring_profile_by_id,
)
from src.config.work_mode import (
    WorkModeSpec,
    default_work_mode,
    get_work_mode,
    list_template_authoring_work_modes,
)


AUTHORING_WORKSPACE_NAME = "template_workbench"
AUTHORING_STATE_NAME = "template_authoring_state"
WORKBENCH_INDEX_FILENAME = "模板工作台索引.md"
PROMPT_FILENAME = "AI模板生成提示词.md"
BASELINE_FILENAME = "模板配置基准.json"
INBOX_NAME = "待导入"
ARCHIVE_NAME = "archive"
IMPORT_RECORDS_NAME = "records"
PROCESSING_NAME = "processing"
SUCCESS_NAME = "success"
FAILED_NAME = "failed"
CONTRACTS_NAME = "contracts"
CONTRACT_BASELINE_FILENAME = "baseline.json"
CONTRACT_PROMPT_FILENAME = "prompt.md"
BASELINE_NAME_PLACEHOLDER = "请替换为来源文档对应的具体模板名称"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROMPT_RESOURCE_PATH = (
    _PROJECT_ROOT
    / "defaults"
    / "template_authoring"
    / "ai_template_config_prompt_v5.zh-CN.md"
)


@dataclass(frozen=True, slots=True)
class TemplateAuthoringWorkspace:
    mode_id: str
    workbench_root: Path
    state_root: Path
    root: Path
    prompt_path: Path
    baseline_path: Path
    inbox_path: Path
    processing_dir: Path
    archive_dir: Path
    records_dir: Path
    success_dir: Path
    failed_dir: Path
    contracts_dir: Path


def template_authoring_workbench_path() -> Path:
    """Return the projection root beside, never inside, runtime templates."""

    return library.TEMPLATE_LIBRARY_DIR.parent / AUTHORING_WORKSPACE_NAME


def template_authoring_workspace_path(mode_id: str | None = None) -> Path:
    """Return a stable physical path based only on durable ``mode_id``."""

    mode = _resolve_work_mode(mode_id)
    return template_authoring_workbench_path() / mode.mode_id


def template_authoring_state_path() -> Path:
    """Return the internal import state root outside the user-facing board."""

    return library.TEMPLATE_LIBRARY_DIR.parent / AUTHORING_STATE_NAME


def template_authoring_workspace_descriptor(
    mode_id: str | None = None,
) -> TemplateAuthoringWorkspace:
    mode = _resolve_work_mode(mode_id)
    return _workspace_descriptor_for_mode(mode)


def _workspace_descriptor_for_mode(
    mode: WorkModeSpec,
) -> TemplateAuthoringWorkspace:
    root = template_authoring_workbench_path() / mode.mode_id
    state_root = template_authoring_state_path() / mode.mode_id
    records_dir = state_root / IMPORT_RECORDS_NAME
    return TemplateAuthoringWorkspace(
        mode_id=mode.mode_id,
        workbench_root=template_authoring_workbench_path(),
        state_root=state_root,
        root=root,
        prompt_path=root / PROMPT_FILENAME,
        baseline_path=root / BASELINE_FILENAME,
        inbox_path=root / INBOX_NAME,
        processing_dir=state_root / PROCESSING_NAME,
        archive_dir=state_root / ARCHIVE_NAME,
        records_dir=records_dir,
        success_dir=records_dir / SUCCESS_NAME,
        failed_dir=records_dir / FAILED_NAME,
        contracts_dir=state_root / CONTRACTS_NAME,
    )


def list_template_authoring_workspace_descriptors(
    *,
    include_inactive: bool = False,
) -> tuple[TemplateAuthoringWorkspace, ...]:
    return tuple(
        _workspace_descriptor_for_mode(mode)
        for mode in list_template_authoring_work_modes(
            include_inactive=include_inactive
        )
    )


def ensure_template_authoring_workspace(
    mode_id: str | None = None,
) -> TemplateAuthoringWorkspace:
    """Create or refresh one mode board only."""

    mode = _resolve_work_mode(mode_id)
    profile = _profile_for_mode(mode)
    # Resolve immutable product inputs before creating either runtime-library
    # or workbench directories.  A newly registered mode without an exact
    # mode-scoped baseline must fail without leaving a partial board behind.
    baseline = _create_mode_baseline(mode)
    prompt_source = _PROMPT_RESOURCE_PATH.read_text(encoding="utf-8")
    library.ensure_template_library()
    workbench_root = template_authoring_workbench_path()
    workbench_root.mkdir(parents=True, exist_ok=True)
    workspace = _ensure_mode_workspace(
        mode,
        profile=profile,
        prompt_source=prompt_source,
        baseline=baseline,
    )
    _write_workbench_index()
    return workspace


def refresh_template_authoring_workbench_index() -> Path:
    """Refresh the single root index without materializing mode boards."""

    return _write_workbench_index()


def _ensure_mode_workspace(
    mode: WorkModeSpec,
    *,
    profile: TemplateAuthoringProfile,
    prompt_source: str,
    baseline: TemplateConfig,
) -> TemplateAuthoringWorkspace:
    workspace = _workspace_descriptor_for_mode(mode)
    for directory in (workspace.root, workspace.inbox_path):
        directory.mkdir(parents=True, exist_ok=True)

    # Preserve the contract that was visible to an in-flight assistant before
    # refreshing the workbench files.  This migration is intentionally done
    # first so a prompt/profile rollout cannot strand a valid older result.
    _archive_existing_contract_bundle(workspace)

    baseline_template_payload = asdict(baseline)
    prompt = _render_prompt(
        prompt_source,
        mode=mode,
        profile=profile,
    )
    contract = TemplateAuthoringContract(
        mode_id=mode.mode_id,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        baseline_template_id=mode.default_template_id,
        baseline_sha256=canonical_json_sha256(baseline_template_payload),
        prompt_version=AUTHORING_PROMPT_VERSION,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    )
    baseline_envelope = TemplateAuthoringBaselineEnvelope(
        contract=contract,
        template=baseline_template_payload,
    )
    baseline_text = json.dumps(
        baseline_envelope.to_payload(),
        ensure_ascii=False,
        indent=2,
    )
    _write_text_if_changed(workspace.prompt_path, prompt)
    _write_text_if_changed(
        workspace.baseline_path,
        baseline_text,
    )
    _write_contract_bundle(
        workspace,
        contract=contract,
        baseline_text=baseline_text,
        prompt_text=prompt,
    )
    return workspace


def _archive_existing_contract_bundle(
    workspace: TemplateAuthoringWorkspace,
) -> None:
    """Best-effort migration of the previously published contract."""

    if not workspace.baseline_path.is_file() or not workspace.prompt_path.is_file():
        return
    try:
        baseline_text = workspace.baseline_path.read_text(encoding="utf-8")
        prompt_text = workspace.prompt_path.read_text(encoding="utf-8")
        baseline = TemplateAuthoringBaselineEnvelope.from_payload(
            read_json_object(workspace.baseline_path)
        )
        contract = baseline.contract
        if contract.mode_id != workspace.mode_id:
            return
        if canonical_json_sha256(baseline.template) != contract.baseline_sha256:
            return
        if hashlib.sha256(prompt_text.encode("utf-8")).hexdigest() != contract.prompt_sha256:
            return
        _write_contract_bundle(
            workspace,
            contract=contract,
            baseline_text=baseline_text,
            prompt_text=prompt_text,
        )
    except (OSError, UnicodeError, TemplateAuthoringContractError):
        # A corrupt current projection is replaced below; it must never be
        # promoted into trusted history.
        return


def _write_contract_bundle(
    workspace: TemplateAuthoringWorkspace,
    *,
    contract: TemplateAuthoringContract,
    baseline_text: str,
    prompt_text: str,
) -> Path:
    """Persist one content-addressed baseline/prompt pair for later imports."""

    bundle_dir = workspace.contracts_dir / contract.fingerprint
    bundle_dir.mkdir(parents=True, exist_ok=True)
    _write_text_if_changed(
        bundle_dir / CONTRACT_BASELINE_FILENAME,
        baseline_text,
    )
    _write_text_if_changed(
        bundle_dir / CONTRACT_PROMPT_FILENAME,
        prompt_text,
    )
    return bundle_dir


def _render_prompt(
    prompt_source: str,
    *,
    mode: WorkModeSpec,
    profile: TemplateAuthoringProfile,
) -> str:
    return (
        prompt_source.replace("{{WORK_MODE_LABEL}}", mode.label)
        .replace("{{WORK_MODE_ID}}", mode.mode_id)
        .replace("{{PROFILE_ID}}", profile.profile_id)
        .replace("{{PROFILE_VERSION}}", str(profile.version))
        .replace("{{BASELINE_TEMPLATE_ID}}", mode.default_template_id)
        .replace("{{BASELINE_FILENAME}}", BASELINE_FILENAME)
        .replace("{{INBOX_NAME}}", INBOX_NAME)
        .replace("{{AUTHORABLE_ROOTS}}", _markdown_code_list(profile.authorable_roots))
        .replace("{{FROZEN_ROOTS}}", _markdown_code_list(profile.frozen_roots))
        .replace(
            "{{REQUIRED_STYLE_ROLES}}",
            _markdown_code_list(profile.required_style_roles),
        )
        .replace("{{MASTER_BOUNDARIES}}", _markdown_text_list(profile.master_boundaries))
        .replace("{{SCENE_BOUNDARIES}}", _markdown_text_list(profile.scene_boundaries))
        .replace(
            "{{MATERIAL_BOUNDARIES}}",
            _markdown_text_list(profile.material_boundaries),
        )
        .replace(
            "{{RESULT_KIND}}",
            AUTHORING_RESULT_KIND,
        )
        .replace("{{SCHEMA_VERSION}}", str(AUTHORING_SCHEMA_VERSION))
    )


def _write_workbench_index() -> Path:
    root = template_authoring_workbench_path()
    root.mkdir(parents=True, exist_ok=True)
    sections = [
        "# 模板工作台索引",
        "",
        "工作模式的数量和显示顺序来自当前产品注册表；物理目录使用稳定 mode_id，模式重排不会搬动用户资料。",
        "",
        "| 工作模式 | 稳定标识 | 状态 | 工作台目录 |",
        "| --- | --- | --- | --- |",
    ]
    registered_modes = list_template_authoring_work_modes(include_inactive=True)
    registered_ids = {mode.mode_id for mode in registered_modes}
    for mode in registered_modes:
        status = "启用" if mode.status == "active" else f"已停用（{mode.status}）"
        directory_status = "已创建" if (root / mode.mode_id).is_dir() else "按需创建"
        sections.append(
            f"| {_markdown_cell(mode.label)} | `{mode.mode_id}` | "
            f"{status}，{directory_status} | `{mode.mode_id}/` |"
        )
    for directory in sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir() and path.name not in registered_ids
        ),
        key=lambda path: path.name.casefold(),
    ):
        sections.append(
            f"| 历史未注册模式 | `{_markdown_cell(directory.name)}` | "
            f"保留、不监听 | `{_markdown_cell(directory.name)}/` |"
        )
    sections.extend(
        [
            "",
            "模式工作台按需创建；停用模式的用户目录不会被自动删除。",
        ]
    )
    return _write_text_if_changed(
        root / WORKBENCH_INDEX_FILENAME,
        "\n".join(sections),
    )


def _create_mode_baseline(mode: WorkModeSpec) -> TemplateConfig:
    baseline = create_builtin_template(
        mode.default_template_id,
        mode_id=mode.mode_id,
    )
    baseline.name = BASELINE_NAME_PLACEHOLDER
    baseline.description = (
        f"{mode.label}（{mode.mode_id}）AI 模板生成基准。"
        "生成结果必须替换名称和说明，并保持当前 TemplateConfig 完整结构。"
    )
    return baseline


def _profile_for_mode(mode: WorkModeSpec) -> TemplateAuthoringProfile:
    profile_id = str(mode.template_authoring_profile_id or "").strip()
    if not profile_id:
        raise ValueError(f"work mode does not support template authoring: {mode.mode_id}")
    profile = get_template_authoring_profile_by_id(profile_id)
    if profile is None:
        raise ValueError(
            f"work mode references an unknown template authoring profile: "
            f"{mode.mode_id}/{profile_id}"
        )
    return profile


def _resolve_work_mode(mode_id: str | None) -> WorkModeSpec:
    requested = str(mode_id or "").strip()
    if not requested:
        return default_work_mode()
    resolved = get_work_mode(requested)
    if resolved is None:
        raise ValueError(f"unknown work mode: {requested}")
    return resolved


def _markdown_code_list(values: tuple[str, ...]) -> str:
    return "\n".join(f"- `{value}`" for value in values)


def _markdown_text_list(values: tuple[str, ...]) -> str:
    return "\n".join(f"- {value}" for value in values)


def _markdown_cell(value: str) -> str:
    return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _write_text_if_changed(path: Path, text: str) -> Path:
    try:
        if path.read_text(encoding="utf-8") == text:
            return path
    except (FileNotFoundError, OSError, UnicodeError):
        pass
    return atomic_write_text(path, text, encoding="utf-8")


__all__ = [
    "ARCHIVE_NAME",
    "AUTHORING_STATE_NAME",
    "AUTHORING_WORKSPACE_NAME",
    "BASELINE_FILENAME",
    "BASELINE_NAME_PLACEHOLDER",
    "CONTRACTS_NAME",
    "CONTRACT_BASELINE_FILENAME",
    "CONTRACT_PROMPT_FILENAME",
    "FAILED_NAME",
    "IMPORT_RECORDS_NAME",
    "INBOX_NAME",
    "PROCESSING_NAME",
    "PROMPT_FILENAME",
    "SUCCESS_NAME",
    "TemplateAuthoringWorkspace",
    "WORKBENCH_INDEX_FILENAME",
    "ensure_template_authoring_workspace",
    "list_template_authoring_workspace_descriptors",
    "refresh_template_authoring_workbench_index",
    "template_authoring_state_path",
    "template_authoring_workbench_path",
    "template_authoring_workspace_descriptor",
    "template_authoring_workspace_path",
]
