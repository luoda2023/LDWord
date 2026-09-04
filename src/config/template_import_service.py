"""Serialized, UI-independent template import application service."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import wraps
import hashlib
import os
from pathlib import Path
from threading import RLock
import time
from typing import Any, Callable, Mapping, ParamSpec, TypeVar
from uuid import uuid4

from src.config.atomic_io import atomic_write_text
from src.config.library import (
    ConfigLibraryEntry,
    save_template_to_library,
    template_user_dir,
)
from src.config.template import TemplateConfig
from src.config.template_identity import allocate_template_id
from src.config.template_authoring_contract import (
    AUTHORING_BASELINE_KIND,
    AUTHORING_RESULT_KIND,
    TemplateAuthoringBaselineEnvelope,
    TemplateAuthoringContract,
    TemplateAuthoringContractError,
    TemplateAuthoringObservations,
    TemplateAuthoringResultEnvelope,
    canonical_json_sha256,
    read_json_object,
)
from src.config.template_authoring_layout import (
    BASELINE_FILENAME,
    CONTRACT_BASELINE_FILENAME,
    CONTRACT_PROMPT_FILENAME,
    PROMPT_FILENAME,
    TemplateAuthoringWorkspace,
    ensure_template_authoring_workspace,
)
from src.config.template_authoring_profile import (
    TemplateAuthoringProfile,
    get_template_authoring_profile_by_id,
)
from src.config.template_payload_codec import (
    TemplatePayloadCodecError,
    materialize_template_payload,
    validate_authored_template_boundary,
)
from src.config.template_authoring_semantics import (
    TemplateAuthoringSemanticError,
    validate_authored_template_semantics,
)
from src.config.work_mode import get_work_mode
from src.shared.engine.page_number_planner import (
    collect_static_page_number_diagnostics,
)


_MAX_IMPORT_BYTES = 16 * 1024 * 1024
_IMPORT_OPERATION_LOCK = RLock()
_P = ParamSpec("_P")
_R = TypeVar("_R")


def _serialize_import_operation(
    operation: Callable[_P, _R],
) -> Callable[_P, _R]:
    """Keep assistant commits and watched-inbox recovery mutually exclusive."""

    @wraps(operation)
    def serialized(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with _IMPORT_OPERATION_LOCK:
            return operation(*args, **kwargs)

    return serialized


class LegacyTemplateImportAdapter:
    """Accept only complete, lossless TemplateConfig payloads without provenance."""

    def load(self, payload: Mapping[str, Any]) -> TemplateConfig:
        return materialize_template_payload(payload)


class TemplateImportError(ValueError):
    """A source cannot be committed without data loss or boundary drift."""


@dataclass(frozen=True, slots=True)
class TemplateImportIssue:
    code: str
    stage: str
    message: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class TemplateImportSuccess:
    entry: ConfigLibraryEntry
    archived_path: Path
    observations: TemplateAuthoringObservations
    contract: TemplateAuthoringContract | None


@dataclass(frozen=True, slots=True)
class TemplateImportBatch:
    successes: tuple[TemplateImportSuccess, ...] = ()
    rejections: tuple[TemplateImportIssue, ...] = ()
    warnings: tuple[TemplateImportIssue, ...] = ()
    pending_count: int = 0

    @property
    def imported_entries(self) -> tuple[ConfigLibraryEntry, ...]:
        return tuple(success.entry for success in self.successes)

    @property
    def has_activity(self) -> bool:
        return bool(self.successes or self.rejections or self.warnings)


@dataclass(frozen=True, slots=True)
class _LoadedExternalTemplate:
    template: TemplateConfig
    observations: TemplateAuthoringObservations
    contract: TemplateAuthoringContract | None


@_serialize_import_operation
def process_template_import_inbox(
    mode_id: str,
    *,
    settle_seconds: float = 0.75,
) -> TemplateImportBatch:
    """Validate and commit stable JSON files for exactly one work mode."""

    workspace = ensure_template_authoring_workspace(mode_id)
    successes: list[TemplateImportSuccess] = []
    rejections: list[TemplateImportIssue] = []
    warnings: list[TemplateImportIssue] = []
    pending_count = 0
    now = time.time()

    for source, is_new_inbox_file in _import_candidates(workspace):
        if is_new_inbox_file:
            try:
                age_seconds = max(0.0, now - source.stat().st_mtime)
            except OSError:
                pending_count += 1
                continue
            if settle_seconds > 0 and age_seconds < settle_seconds:
                pending_count += 1
                continue
            try:
                source = _move_to_unique_destination(
                    source,
                    workspace.processing_dir,
                )
            except (PermissionError, OSError):
                pending_count += 1
                continue

        try:
            loaded = _load_external_template_strict(
                source,
                mode_id=workspace.mode_id,
                baseline_path=workspace.baseline_path,
                contracts_dir=workspace.contracts_dir,
            )
            template_id = allocate_template_id(
                name=loaded.template.name,
                mode_id=workspace.mode_id,
                equivalent_template=loaded.template,
            )
            target_path = template_user_dir(workspace.mode_id) / f"{template_id}.json"
            target_existed = target_path.exists()
        except TemplateImportError as exc:
            rejections.append(
                _reject_source(
                    source,
                    workspace,
                    code="validation_failed",
                    stage="validation",
                    reason=str(exc),
                )
            )
            continue
        except (PermissionError, OSError) as exc:
            if _looks_temporary(exc):
                pending_count += 1
                continue
            rejections.append(
                _reject_source(
                    source,
                    workspace,
                    code="source_unreadable",
                    stage="read",
                    reason=str(exc),
                )
            )
            continue

        try:
            entry = save_template_to_library(
                loaded.template,
                template_id=template_id,
                mode_id=workspace.mode_id,
            )
            _verify_saved_template(entry.path, loaded.template)
        except (OSError, ValueError, TypeError) as exc:
            if not target_existed:
                try:
                    target_path.unlink(missing_ok=True)
                except OSError:
                    pass
            failed_source = source
            try:
                failed_source = _move_to_unique_destination(
                    source,
                    workspace.failed_dir,
                )
            except OSError:
                pass
            reason = f"正式写入用户模板库失败：{exc}"
            _write_failure_explanation(failed_source, reason)
            rejections.append(
                TemplateImportIssue(
                    code="commit_failed",
                    stage="commit",
                    message=f"{failed_source.name}：{reason}",
                    source_path=failed_source,
                )
            )
            continue

        try:
            archived_path = _move_to_unique_destination(
                source,
                workspace.archive_dir,
            )
        except (PermissionError, OSError) as exc:
            pending_count += 1
            if not _looks_temporary(exc):
                warnings.append(
                    TemplateImportIssue(
                        code="archive_pending",
                        stage="archive",
                        message=(
                            f"{source.name}：模板已写入，但来源文件尚未归档，"
                            f"后台将继续重试：{exc}"
                        ),
                        source_path=source,
                    )
                )
            continue

        success = TemplateImportSuccess(
            entry=entry,
            archived_path=archived_path,
            observations=loaded.observations,
            contract=loaded.contract,
        )
        successes.append(success)
        try:
            _write_success_record(workspace, success=success)
        except OSError as exc:
            warnings.append(
                TemplateImportIssue(
                    code="audit_record_failed",
                    stage="audit",
                    message=(
                        f"{archived_path.name}：模板已导入，但成功记录写入失败：{exc}"
                    ),
                    source_path=archived_path,
                )
            )

    return TemplateImportBatch(
        successes=tuple(successes),
        rejections=tuple(rejections),
        warnings=tuple(warnings),
        pending_count=pending_count,
    )


@_serialize_import_operation
def import_template_authoring_result_text(
    mode_id: str,
    result_text: str,
) -> TemplateImportBatch:
    """Validate and commit exactly one assistant-produced authoring result.

    Unlike the watched-inbox entry point, this function never consumes other
    files the user may have placed in the workbench.  The provider output is
    first persisted in the recoverable processing area, then goes through the
    same strict contract, boundary, round-trip, archive, and audit checks.
    """

    workspace = ensure_template_authoring_workspace(mode_id)
    workspace.processing_dir.mkdir(parents=True, exist_ok=True)
    source = workspace.processing_dir / f"assistant-{uuid4().hex}.json"
    atomic_write_text(source, str(result_text or ""), encoding="utf-8")

    try:
        loaded = _load_external_template_strict(
            source,
            mode_id=workspace.mode_id,
            baseline_path=workspace.baseline_path,
            contracts_dir=workspace.contracts_dir,
        )
        template_id = allocate_template_id(
            name=loaded.template.name,
            mode_id=workspace.mode_id,
            equivalent_template=loaded.template,
        )
        target_path = template_user_dir(workspace.mode_id) / f"{template_id}.json"
        target_existed = target_path.exists()
    except (TemplateImportError, PermissionError, OSError) as exc:
        issue = _reject_source(
            source,
            workspace,
            code=(
                "validation_failed"
                if isinstance(exc, TemplateImportError)
                else "source_unreadable"
            ),
            stage=("validation" if isinstance(exc, TemplateImportError) else "read"),
            reason=str(exc),
        )
        return TemplateImportBatch(rejections=(issue,))

    try:
        entry = save_template_to_library(
            loaded.template,
            template_id=template_id,
            mode_id=workspace.mode_id,
        )
        _verify_saved_template(entry.path, loaded.template)
    except (OSError, ValueError, TypeError) as exc:
        if not target_existed:
            try:
                target_path.unlink(missing_ok=True)
            except OSError:
                pass
        failed_source = source
        try:
            failed_source = _move_to_unique_destination(
                source,
                workspace.failed_dir,
            )
        except OSError:
            pass
        reason = f"正式写入用户模板库失败：{exc}"
        try:
            _write_failure_explanation(failed_source, reason)
        except OSError:
            pass
        return TemplateImportBatch(
            rejections=(
                TemplateImportIssue(
                    code="commit_failed",
                    stage="commit",
                    message=f"{failed_source.name}：{reason}",
                    source_path=failed_source,
                ),
            )
        )

    try:
        archived_path = _move_to_unique_destination(
            source,
            workspace.archive_dir,
        )
    except (PermissionError, OSError) as exc:
        success = TemplateImportSuccess(
            entry=entry,
            archived_path=source,
            observations=loaded.observations,
            contract=loaded.contract,
        )
        return TemplateImportBatch(
            successes=(success,),
            warnings=(
                TemplateImportIssue(
                    code="archive_pending",
                    stage="archive",
                    message=(
                        f"{source.name}：模板已写入，但来源文件尚未归档，"
                        f"后台将继续重试：{exc}"
                    ),
                    source_path=source,
                ),
            ),
            pending_count=1,
        )

    success = TemplateImportSuccess(
        entry=entry,
        archived_path=archived_path,
        observations=loaded.observations,
        contract=loaded.contract,
    )
    warnings: list[TemplateImportIssue] = []
    try:
        _write_success_record(workspace, success=success)
    except OSError as exc:
        warnings.append(
            TemplateImportIssue(
                code="audit_record_failed",
                stage="audit",
                message=(
                    f"{archived_path.name}：模板已导入，但成功记录写入失败：{exc}"
                ),
                source_path=archived_path,
            )
        )
    return TemplateImportBatch(successes=(success,), warnings=tuple(warnings))


def revalidate_template_authoring_failure(
    mode_id: str,
    failed_result_path: Path | str,
) -> TemplateImportBatch:
    """Re-run a preserved failed result against the latest validator.

    The original failure artifact remains untouched as audit evidence.  The
    retried copy follows the same isolated processing/commit path as a fresh
    assistant result, so this cannot consume other inbox files.
    """

    workspace = ensure_template_authoring_workspace(mode_id)
    source = Path(failed_result_path).expanduser()
    try:
        resolved = source.resolve(strict=True)
        failed_root = workspace.failed_dir.resolve(strict=False)
        if (
            not resolved.is_relative_to(failed_root)
            or not resolved.is_file()
            or resolved.suffix.casefold() != ".json"
        ):
            raise TemplateImportError("只能重新校验当前模式失败记录目录中的 JSON 结果")
        if resolved.stat().st_size > _MAX_IMPORT_BYTES:
            raise TemplateImportError("模板 JSON 超过 16 MB，已停止重新校验")
        result_text = resolved.read_text(encoding="utf-8-sig")
    except (TemplateImportError, OSError, UnicodeError) as exc:
        return TemplateImportBatch(
            rejections=(
                TemplateImportIssue(
                    code="revalidation_source_invalid",
                    stage="read",
                    message=str(exc),
                    source_path=source,
                ),
            )
        )
    return import_template_authoring_result_text(workspace.mode_id, result_text)


def _import_candidates(
    workspace: TemplateAuthoringWorkspace,
) -> tuple[tuple[Path, bool], ...]:
    """Return recoverable processing files before newly arrived inbox files."""

    def json_files(directory: Path) -> tuple[Path, ...]:
        try:
            return tuple(
                sorted(
                    (
                        path
                        for path in directory.iterdir()
                        if path.is_file() and path.suffix.casefold() == ".json"
                    ),
                    key=lambda path: path.name.casefold(),
                )
            )
        except (FileNotFoundError, OSError):
            return ()

    return tuple(
        [(path, False) for path in json_files(workspace.processing_dir)]
        + [(path, True) for path in json_files(workspace.inbox_path)]
    )


def _load_external_template_strict(
    path: Path,
    *,
    mode_id: str,
    baseline_path: Path,
    contracts_dir: Path,
) -> _LoadedExternalTemplate:
    if path.stat().st_size > _MAX_IMPORT_BYTES:
        raise TemplateImportError("模板 JSON 超过 16 MB，已停止自动导入")
    try:
        raw = read_json_object(path)
    except TemplateAuthoringContractError as exc:
        raise TemplateImportError(str(exc)) from exc

    if "kind" not in raw:
        try:
            template = LegacyTemplateImportAdapter().load(raw)
        except TemplatePayloadCodecError as exc:
            raise TemplateImportError(str(exc)) from exc
        return _LoadedExternalTemplate(
            template=template,
            observations=TemplateAuthoringObservations(),
            contract=None,
        )
    if raw.get("kind") == AUTHORING_BASELINE_KIND:
        raise TemplateImportError("检测到模板生成基准文件，请放入 AI 返回的创作结果 JSON")
    if raw.get("kind") != AUTHORING_RESULT_KIND:
        raise TemplateImportError(f"不支持的模板创作结果类型：{raw.get('kind')}")

    try:
        result = TemplateAuthoringResultEnvelope.from_payload(raw)
        baseline = _resolve_result_baseline(
            result,
            baseline_path=baseline_path,
            contracts_dir=contracts_dir,
        )
    except TemplateAuthoringContractError as exc:
        raise TemplateImportError(str(exc)) from exc
    profile = _validate_result_contract(
        result,
        baseline=baseline,
        mode_id=mode_id,
    )
    result_template = dict(result.template)
    baseline_template = dict(baseline.template)
    try:
        template = materialize_template_payload(
            result_template,
            profile=profile,
            baseline_template=baseline_template,
        )
        validate_authored_template_boundary(
            result_template,
            baseline_template=baseline_template,
            profile=profile,
        )
        validate_authored_template_semantics(
            result_template,
            baseline_template=baseline_template,
        )
        page_number_diagnostics = collect_static_page_number_diagnostics(
            template.header_footer
        )
        if page_number_diagnostics:
            raise TemplateAuthoringSemanticError(
                "页码计划未通过静态检查："
                + "；".join(
                    item.message for item in page_number_diagnostics[:4]
                )
            )
    except (TemplatePayloadCodecError, TemplateAuthoringSemanticError) as exc:
        raise TemplateImportError(str(exc)) from exc
    return _LoadedExternalTemplate(
        template=template,
        observations=result.observations,
        contract=result.contract,
    )


def _resolve_result_baseline(
    result: TemplateAuthoringResultEnvelope,
    *,
    baseline_path: Path,
    contracts_dir: Path,
) -> TemplateAuthoringBaselineEnvelope:
    """Resolve the exact baseline seen by the assistant, including history."""

    current = TemplateAuthoringBaselineEnvelope.from_payload(
        read_json_object(baseline_path)
    )
    if current.contract == result.contract:
        return current

    bundle_dir = contracts_dir / result.contract.fingerprint
    historical_path = bundle_dir / CONTRACT_BASELINE_FILENAME
    prompt_path = bundle_dir / CONTRACT_PROMPT_FILENAME
    if not historical_path.is_file() or not prompt_path.is_file():
        differing = _differing_contract_fields(result.contract, current.contract)
        raise TemplateImportError(
            "创作结果与当前合同不一致，且找不到对应的历史合同快照："
            + "、".join(differing)
        )

    historical = TemplateAuthoringBaselineEnvelope.from_payload(
        read_json_object(historical_path)
    )
    if historical.contract != result.contract:
        raise TemplateImportError("历史合同快照与创作结果指纹不一致")
    try:
        prompt_text = prompt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TemplateImportError(f"历史合同提示词无法读取：{exc}") from exc
    if (
        hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        != historical.contract.prompt_sha256
    ):
        raise TemplateImportError("历史合同提示词指纹校验失败")
    return historical


def _differing_contract_fields(
    actual: TemplateAuthoringContract,
    expected: TemplateAuthoringContract,
) -> list[str]:
    actual_payload = actual.to_payload()
    expected_payload = expected.to_payload()
    return [
        name
        for name in expected_payload
        if actual_payload.get(name) != expected_payload.get(name)
    ]


def _validate_result_contract(
    result: TemplateAuthoringResultEnvelope,
    *,
    baseline: TemplateAuthoringBaselineEnvelope,
    mode_id: str,
) -> TemplateAuthoringProfile:
    mode = get_work_mode(mode_id)
    if mode is None:
        raise TemplateImportError(f"未知工作模式：{mode_id}")
    profile_id = str(mode.template_authoring_profile_id or "").strip()
    profile = get_template_authoring_profile_by_id(profile_id)
    if profile is None:
        raise TemplateImportError(f"当前模式缺少模板创作 Profile：{mode_id}")
    expected = baseline.contract
    if expected.mode_id != mode.mode_id:
        raise TemplateImportError("当前模板生成基准与工作模式不匹配")
    if expected.profile_id != profile.profile_id or expected.profile_version != profile.version:
        raise TemplateImportError("当前模板生成基准与创作 Profile 不匹配")
    if expected.baseline_template_id != mode.default_template_id:
        raise TemplateImportError("当前模板生成基准与模式默认模板不匹配")
    if result.contract != expected:
        differing = _differing_contract_fields(result.contract, expected)
        raise TemplateImportError(
            "创作结果与当前工作模式或基准不匹配：" + "、".join(differing)
        )
    if canonical_json_sha256(baseline.template) != expected.baseline_sha256:
        raise TemplateImportError("当前模板生成基准指纹校验失败，请重新打开模板工作台")
    return profile


def _verify_saved_template(path: Path, expected: TemplateConfig) -> None:
    from src.config.loader import load_template

    if asdict(load_template(path)) != asdict(expected):
        raise TemplateImportError("模板写入后无法无损读回，已停止导入")


def _write_success_record(
    workspace: TemplateAuthoringWorkspace,
    *,
    success: TemplateImportSuccess,
) -> Path:
    archived_path = success.archived_path
    entry = success.entry
    record_path = workspace.success_dir / f"{archived_path.name}.导入记录.md"
    contract_lines = _contract_record_lines(success.contract)
    report = (
        "# 模板导入记录\n\n"
        "- 结果：成功\n"
        f"- 工作模式：{workspace.mode_id}\n"
        f"- 模板名称：{entry.name}\n"
        f"- 内部标识：`{entry.config_id}`\n"
        f"- 来源档案：{archived_path.name}\n"
        f"- 来源 SHA-256：`{hashlib.sha256(archived_path.read_bytes()).hexdigest()}`\n"
        f"{contract_lines}"
        f"- 导入时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"{_observations_markdown(success.observations)}"
    )
    return atomic_write_text(record_path, report, encoding="utf-8")


def _contract_record_lines(contract: TemplateAuthoringContract | None) -> str:
    if contract is None:
        return "- 创作合同：兼容版裸 TemplateConfig（无模式指纹）\n"
    return (
        f"- 创作 Profile：`{contract.profile_id}` V{contract.profile_version}\n"
        f"- 基准模板：`{contract.baseline_template_id}`\n"
        f"- 基准 SHA-256：`{contract.baseline_sha256}`\n"
        f"- 合同指纹：`{contract.fingerprint}`\n"
    )


def _observations_markdown(observations: TemplateAuthoringObservations) -> str:
    labels = {
        "master": "母版边界",
        "scene": "方案边界",
        "material": "资料边界",
        "unsupported": "当前无法表达",
    }
    lines = ["## 来源分析边界", ""]
    for field_name, label in labels.items():
        lines.extend([f"### {label}", ""])
        values = getattr(observations, field_name)
        lines.extend((f"- {value}" for value in values) if values else ("- 无",))
        lines.append("")
    return "\n".join(lines)


def _reject_source(
    source: Path,
    workspace: TemplateAuthoringWorkspace,
    *,
    code: str,
    stage: str,
    reason: str,
) -> TemplateImportIssue:
    failed_source = source
    try:
        failed_source = _move_to_unique_destination(source, workspace.failed_dir)
    except OSError as move_error:
        reason = f"{reason}；同时无法移动到失败目录：{move_error}"
    try:
        _write_failure_explanation(failed_source, reason)
    except OSError as write_error:
        reason = f"{reason}；同时无法写入错误说明：{write_error}"
    return TemplateImportIssue(
        code=code,
        stage=stage,
        message=f"{source.name}：{reason}",
        source_path=failed_source,
    )


def _write_failure_explanation(source: Path, reason: str) -> Path:
    report_path = source.with_name(f"{source.name}.错误说明.txt")
    report = (
        "AI 模板自动导入失败\n\n"
        f"原文件：{source.name}\n"
        f"原因：{reason}\n\n"
        f"处理建议：重新上传“{PROMPT_FILENAME}”、“{BASELINE_FILENAME}”和来源 Word 文档，"
        "让 AI 输出带模式与基准指纹的完整模板创作结果 JSON，然后放回待导入目录。\n"
    )
    return atomic_write_text(report_path, report, encoding="utf-8")


def _move_to_unique_destination(source: Path, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / source.name
    if candidate.exists():
        for index in range(2, 1001):
            candidate = directory / f"{source.stem}_{index}{source.suffix}"
            if not candidate.exists():
                break
        else:
            raise OSError(f"目标目录同名文件过多：{directory}")
    os.replace(source, candidate)
    return candidate


def _looks_temporary(error: OSError) -> bool:
    return isinstance(error, PermissionError) or getattr(error, "winerror", None) in {
        32,
        33,
    }


__all__ = [
    "TemplateImportBatch",
    "TemplateImportError",
    "TemplateImportIssue",
    "TemplateImportSuccess",
    "import_template_authoring_result_text",
    "process_template_import_inbox",
    "revalidate_template_authoring_failure",
]
