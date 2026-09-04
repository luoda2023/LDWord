"""Parent-side transaction coordinator for Office image layout."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from src.shared.win_process import popen_hidden, run_hidden
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

from src.config.image_materials import ResolvedImageInsertionPlan
from src.shared.engine.office_broker_command import (
    OFFICE_IMAGE_LAYOUT_CHILD_FLAG,
    build_office_broker_child_command,
)
from src.shared.engine.office_image_layout_contracts import (
    PROVIDER_SPECS,
    LayoutFailure,
    LayoutFailureCode,
    LayoutStatus,
    LayoutWarning,
    LayoutWarningCode,
    OfficeImageLayoutJob,
    OfficeImageLayoutReceipt,
    OfficeImageLayoutRequest,
    OfficeImageProvider,
    OfficeProviderSpec,
    OOXMLImageIdentity,
    build_layout_receipt,
)
from src.shared.engine.office_image_layout_fileio import (
    atomic_write_json,
    safe_file_sha256,
)
from src.shared.engine.office_image_layout_inventory import (
    OFFICE_DOCX_PACKAGE_LIMITS,
    image_inventory_sha256,
    image_preservation_sha256,
    inventory_ooxml_images,
    marker_text_run_visibility,
    verify_ooxml_image_invariants,
)
from src.shared.engine.office_image_layout_preflight import parent_preflight
from src.shared.engine.office_layout_probe import (
    _pid_exists,
    _process_ids_for_names,
    _registration_status,
)
from src.shared.engine.prepared_image import PreparedImage
from src.shared.io.layout_shadow import (
    build_controlled_layout_shadow_path,
    is_controlled_layout_shadow,
)
from src.shared.io.safe_docx_package import SafeDocxPackage

OFFICE_COM_PATH_MAX_UTF16_UNITS = 240

def build_office_image_layout_request(
    source_docx_path: str | Path,
    plans: Sequence[ResolvedImageInsertionPlan],
    prepared_by_job: Mapping[str, PreparedImage],
    *,
    provider: OfficeImageProvider | str,
    transaction_id: str = "",
    **options: object,
) -> OfficeImageLayoutRequest:
    source = Path(source_docx_path)
    package = SafeDocxPackage.open_path(
        source,
        limits=OFFICE_DOCX_PACKAGE_LIMITS,
    )
    jobs = tuple(
        OfficeImageLayoutJob(plan, prepared_by_job[plan.job_id]) for plan in plans
    )
    return OfficeImageLayoutRequest(
        transaction_id=(
            transaction_id or f"layout-{package.source_sha256[:16]}"
        ),
        source_docx_path=str(source),
        source_docx_sha256=package.source_sha256,
        source_docx_size=package.source_size,
        provider=OfficeImageProvider(str(getattr(provider, "value", provider))),
        jobs=jobs,
        **options,
    )

@dataclass(frozen=True, slots=True)
class _SourceEvidence:
    inventory: tuple[OOXMLImageIdentity, ...] = ()
    inventory_sha256: str = ""
    semantic_sha256: str = ""
    protected_hidden_markers: tuple[str, ...] = ()
    failures: tuple[LayoutFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class _InputIntegrityEvidence:
    source_sha256_after: str
    source_images_unchanged: bool
    prepared_images_unchanged: bool
    failures: tuple[LayoutFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class _ShadowEvidence:
    inventory: tuple[OOXMLImageIdentity, ...] = ()
    inventory_sha256: str = ""
    matched_semantic_sha256: str = ""
    inserted: tuple[OOXMLImageIdentity, ...] = ()
    preexisting_unchanged: bool = False
    inserted_job_owned: bool = False
    inserted_visible: bool = False
    sentinels_hidden: bool = False
    failures: tuple[LayoutFailure, ...] = ()


def run_office_image_layout(request: OfficeImageLayoutRequest) -> OfficeImageLayoutReceipt:
    """Execute one non-publishing Office layout transaction."""

    if not isinstance(request, OfficeImageLayoutRequest):
        raise TypeError("request must be an OfficeImageLayoutRequest")
    started = time.perf_counter()
    spec = PROVIDER_SPECS[request.provider]
    source = Path(request.source_docx_path).resolve()
    source_evidence = _collect_source_evidence(source, request.jobs)
    failures, input_hashes = parent_preflight(request)
    failures = [*source_evidence.failures, *failures]
    if failures:
        return _build_parent_blocked_receipt(
            request,
            spec,
            started,
            source_evidence,
            tuple(failures),
        )
    registered, detail = _registration_status(spec.prog_id)
    if not registered:
        return _build_parent_blocked_receipt(
            request,
            spec,
            started,
            source_evidence,
            (
                LayoutFailure(LayoutFailureCode.PROVIDER_UNAVAILABLE, detail),
            ),
        )

    shadow = build_controlled_layout_shadow_path(source)
    try:
        _create_controlled_shadow(source, shadow)
    except Exception as exc:
        return _build_parent_blocked_receipt(
            request,
            spec,
            started,
            source_evidence,
            (
                LayoutFailure(LayoutFailureCode.SHADOW_CREATE_FAILED, str(exc)),
            ),
        )

    try:
        receipt = _run_layout_child(request, spec, shadow)
    except Exception as exc:
        receipt = build_layout_receipt(
            request,
            spec,
            LayoutStatus.CHILD_FAILED,
            failures=(
                LayoutFailure(
                    LayoutFailureCode.CHILD_PROTOCOL_ERROR,
                    f"{type(exc).__name__}: {exc}",
                ),
            ),
        )
    try:
        return _finalize_layout_receipt(
            request,
            receipt,
            source=source,
            shadow=shadow,
            source_evidence=source_evidence,
            input_hashes=input_hashes,
            started=started,
        )
    except Exception as exc:
        _cleanup_controlled_shadow(source, shadow)
        return replace(
            receipt,
            status=LayoutStatus.CHILD_FAILED,
            source_docx_sha256_after=safe_file_sha256(source),
            shadow_path="",
            shadow_sha256="",
            shadow_retained=False,
            failures=(
                *receipt.failures,
                LayoutFailure(
                    LayoutFailureCode.CHILD_PROTOCOL_ERROR,
                    f"parent finalization failed: {type(exc).__name__}: {exc}",
                ),
            ),
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            source_image_inventory_sha256=source_evidence.inventory_sha256,
            preexisting_image_semantic_sha256_before=source_evidence.semantic_sha256,
            source_image_inventory=source_evidence.inventory,
        )


def _collect_source_evidence(
    source: Path,
    jobs: Sequence[OfficeImageLayoutJob],
) -> _SourceEvidence:
    if not source.is_file():
        return _SourceEvidence()
    try:
        inventory = inventory_ooxml_images(
            source,
            limits=OFFICE_DOCX_PACKAGE_LIMITS,
        )
        marker_visibility = marker_text_run_visibility(
            source,
            tuple(job.plan.anchor.stable_marker_id for job in jobs),
        )
    except ValueError as exc:
        return _SourceEvidence(
            failures=(
                LayoutFailure(LayoutFailureCode.IMAGE_INVENTORY_INVALID, str(exc)),
            )
        )
    protected_markers = tuple(
        sorted(
            marker
            for marker, values in marker_visibility.items()
            if values
            and all(value not in {"visible", "outside_run"} for value in values)
        )
    )
    return _SourceEvidence(
        inventory=inventory,
        inventory_sha256=image_inventory_sha256(inventory),
        semantic_sha256=image_preservation_sha256(inventory),
        protected_hidden_markers=protected_markers,
    )


def _build_parent_blocked_receipt(
    request: OfficeImageLayoutRequest,
    spec: OfficeProviderSpec,
    started: float,
    evidence: _SourceEvidence,
    failures: tuple[LayoutFailure, ...],
) -> OfficeImageLayoutReceipt:
    return build_layout_receipt(
        request,
        spec,
        LayoutStatus.BLOCKED,
        failures=failures,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
        source_image_inventory=evidence.inventory,
        source_image_inventory_sha256=evidence.inventory_sha256,
        preexisting_image_semantic_sha256_before=evidence.semantic_sha256,
    )


def _check_input_integrity(
    request: OfficeImageLayoutRequest,
    source: Path,
    input_hashes: Sequence[tuple[str, str]],
) -> _InputIntegrityEvidence:
    source_after = safe_file_sha256(source)
    source_images_unchanged = all(
        safe_file_sha256(Path(job.plan.image_ref.source_path)) == digest
        for job, (digest, _prepared_digest) in zip(request.jobs, input_hashes, strict=True)
    )
    prepared_images_unchanged = all(
        safe_file_sha256(Path(job.prepared_image.output_path)) == prepared_digest
        for job, (_source_digest, prepared_digest) in zip(request.jobs, input_hashes, strict=True)
    )
    failures: tuple[LayoutFailure, ...] = ()
    if (
        source_after != request.source_docx_sha256
        or not source_images_unchanged
        or not prepared_images_unchanged
    ):
        failures = (
            LayoutFailure(
                LayoutFailureCode.INPUT_MUTATED,
                "source DOCX or source/prepared image changed during the transaction",
            ),
        )
    return _InputIntegrityEvidence(
        source_after,
        source_images_unchanged,
        prepared_images_unchanged,
        failures,
    )


def _verify_shadow_evidence(
    request: OfficeImageLayoutRequest,
    receipt: OfficeImageLayoutReceipt,
    shadow: Path,
    source_evidence: _SourceEvidence,
) -> _ShadowEvidence:
    if receipt.status is not LayoutStatus.SUCCESS:
        return _ShadowEvidence()
    failures: list[LayoutFailure] = []
    try:
        inventory = inventory_ooxml_images(
            shadow,
            limits=OFFICE_DOCX_PACKAGE_LIMITS,
        )
        verification = verify_ooxml_image_invariants(
            source_evidence.inventory,
            inventory,
            request.jobs,
            receipt.jobs,
        )
        if not verification.preexisting_unchanged:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.PREEXISTING_IMAGE_MUTATED,
                    "one or more preexisting OOXML image identities or target "
                    "media hashes changed during the Office transaction",
                )
            )
        if not verification.inserted_images_job_owned:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.UNOWNED_IMAGE_ADDED,
                    "saved shadow image additions do not correspond one-for-one "
                    "to the transaction's job-owned inline image plans",
                )
            )
        elif not verification.inserted_images_visible:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.JOB_IMAGE_HIDDEN,
                    "one or more job-owned image runs retain vanish/hidden "
                    "OOXML formatting",
                )
            )
        marker_visibility = marker_text_run_visibility(
            shadow,
            source_evidence.protected_hidden_markers,
        )
        sentinels_hidden = all(
            all(value not in {"visible", "outside_run"} for value in values)
            for values in marker_visibility.values()
        )
        if not sentinels_hidden:
            failures.append(
                LayoutFailure(
                    LayoutFailureCode.SENTINEL_REVEALED,
                    "clearing job image visibility exposed a protected hidden "
                    "sentinel text run",
                )
            )
        return _ShadowEvidence(
            inventory=inventory,
            inventory_sha256=image_inventory_sha256(inventory),
            matched_semantic_sha256=image_preservation_sha256(
                verification.matched_preexisting
            ),
            inserted=verification.inserted,
            preexisting_unchanged=verification.preexisting_unchanged,
            inserted_job_owned=verification.inserted_images_job_owned,
            inserted_visible=verification.inserted_images_visible,
            sentinels_hidden=sentinels_hidden,
            failures=tuple(failures),
        )
    except ValueError as exc:
        return _ShadowEvidence(
            failures=(
                LayoutFailure(LayoutFailureCode.IMAGE_INVENTORY_INVALID, str(exc)),
            )
        )


def _finalize_layout_receipt(
    request: OfficeImageLayoutRequest,
    receipt: OfficeImageLayoutReceipt,
    *,
    source: Path,
    shadow: Path,
    source_evidence: _SourceEvidence,
    input_hashes: Sequence[tuple[str, str]],
    started: float,
) -> OfficeImageLayoutReceipt:
    integrity = _check_input_integrity(request, source, input_hashes)
    shadow_evidence = _verify_shadow_evidence(
        request,
        receipt,
        shadow,
        source_evidence,
    )
    final_failures = (
        *receipt.failures,
        *integrity.failures,
        *shadow_evidence.failures,
    )
    shadow_hash = safe_file_sha256(shadow)
    success = (
        receipt.status is LayoutStatus.SUCCESS
        and not final_failures
        and bool(shadow_hash)
    )
    if not success:
        _cleanup_controlled_shadow(source, shadow)
        shadow_hash = ""
    resulting_status = (
        LayoutStatus.SUCCESS
        if success
        else LayoutStatus.BLOCKED
        if receipt.status is LayoutStatus.SUCCESS
        else receipt.status
    )
    receipt = replace(
        receipt,
        status=resulting_status,
        source_docx_sha256_after=integrity.source_sha256_after,
        shadow_path=str(shadow) if success else "",
        shadow_sha256=shadow_hash,
        shadow_retained=success,
        source_images_unchanged=integrity.source_images_unchanged,
        prepared_images_unchanged=integrity.prepared_images_unchanged,
        failures=final_failures,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
        source_image_inventory_sha256=source_evidence.inventory_sha256,
        shadow_image_inventory_sha256=shadow_evidence.inventory_sha256,
        preexisting_image_semantic_sha256_before=source_evidence.semantic_sha256,
        preexisting_image_semantic_sha256_after=(
            shadow_evidence.matched_semantic_sha256
        ),
        preexisting_images_unchanged=shadow_evidence.preexisting_unchanged,
        inserted_images_job_owned=shadow_evidence.inserted_job_owned,
        inserted_images_visible=shadow_evidence.inserted_visible,
        sentinel_texts_hidden=shadow_evidence.sentinels_hidden,
        source_image_inventory=source_evidence.inventory,
        shadow_image_inventory=shadow_evidence.inventory,
        inserted_image_inventory=shadow_evidence.inserted,
    )
    return receipt

def _create_controlled_shadow(source: Path, shadow: Path) -> None:
    _assert_controlled_shadow(source, shadow)
    descriptor = os.open(shadow, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        shutil.copy2(source, shadow)
    except Exception:
        shadow.unlink(missing_ok=True)
        raise

def _assert_controlled_shadow(source: Path, shadow: Path) -> None:
    if not is_controlled_layout_shadow(source, shadow):
        raise ValueError("shadow path is not controlled by this transaction")

def _cleanup_controlled_shadow(source: Path, shadow: Path) -> None:
    try:
        _assert_controlled_shadow(source, shadow)
        shadow.unlink(missing_ok=True)
    except Exception:
        pass

class _BrokerInputError(RuntimeError):
    def __init__(self, failure: LayoutFailure):
        self.failure = failure
        super().__init__(failure.message)


@dataclass(frozen=True, slots=True)
class _ChildCommunication:
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: Exception | None = None

def _office_path_utf16_units(path: str | Path) -> int:
    absolute = str(Path(path).expanduser().resolve())
    return len(absolute.encode("utf-16-le")) // 2 + 1

def _require_office_path_budget(
    path: str | Path,
    *,
    label: str,
    job_id: str = "",
) -> None:
    units = _office_path_utf16_units(path)
    if units > OFFICE_COM_PATH_MAX_UTF16_UNITS:
        raise _BrokerInputError(
            LayoutFailure(
                LayoutFailureCode.PATH_TOO_LONG,
                f"{label} path uses {units} UTF-16 units; Office budget is "
                f"{OFFICE_COM_PATH_MAX_UTF16_UNITS}",
                job_id,
            )
        )

def _stage_prepared_images_for_office(
    request: OfficeImageLayoutRequest,
    ipc_dir: Path,
) -> OfficeImageLayoutRequest:
    suffix_by_media_type = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
    }
    staged_jobs: list[OfficeImageLayoutJob] = []
    for index, job in enumerate(request.jobs):
        media_type = job.prepared_image.media_type.casefold()
        suffix = suffix_by_media_type.get(media_type)
        if suffix is None:
            raise _BrokerInputError(
                LayoutFailure(
                    LayoutFailureCode.OFFICE_INPUT_STAGE_FAILED,
                    f"unsupported prepared image media type {media_type!r}",
                    job.job_id,
                )
            )
        target = (ipc_dir / f"i{index:04d}{suffix}").resolve()
        _require_office_path_budget(
            target,
            label="staged prepared image",
            job_id=job.job_id,
        )
        try:
            if target.exists():
                raise FileExistsError(f"staged image already exists: {target.name}")
            shutil.copyfile(job.prepared_image.output_path, target)
        except OSError as exc:
            raise _BrokerInputError(
                LayoutFailure(
                    LayoutFailureCode.OFFICE_INPUT_STAGE_FAILED,
                    f"cannot stage prepared image: {exc}",
                    job.job_id,
                )
            ) from exc
        if safe_file_sha256(target) != job.prepared_image.output_sha256:
            raise _BrokerInputError(
                LayoutFailure(
                    LayoutFailureCode.PREPARED_IMAGE_IDENTITY_MISMATCH,
                    "short Office image copy does not match prepared image SHA-256",
                    job.job_id,
                )
            )
        staged_jobs.append(
            replace(
                job,
                prepared_image=replace(
                    job.prepared_image,
                    output_path=str(target),
                ),
            )
        )
    return replace(request, jobs=tuple(staged_jobs))

def _run_layout_child(
    request: OfficeImageLayoutRequest,
    spec: OfficeProviderSpec,
    shadow: Path,
) -> OfficeImageLayoutReceipt:
    with tempfile.TemporaryDirectory(prefix="lk-ol-") as raw_dir:
        ipc_dir = Path(raw_dir)
        request_path = ipc_dir / "request.json"
        result_path = ipc_dir / "result.json"
        pid_path = ipc_dir / "office-pid.json"
        try:
            _require_office_path_budget(shadow, label="DOCX shadow")
            child_request = _stage_prepared_images_for_office(request, ipc_dir)
        except _BrokerInputError as exc:
            return build_layout_receipt(
                request,
                spec,
                LayoutStatus.BLOCKED,
                failures=(exc.failure,),
            )
        before_pids = _process_ids_for_names(spec.process_names)
        envelope = {
            "request": child_request.to_dict(),
            "shadow_path": str(shadow),
            "result_path": str(result_path),
            "pid_path": str(pid_path),
            "before_pids": sorted(before_pids),
        }
        try:
            atomic_write_json(request_path, envelope)
            command = build_office_broker_child_command(
                module_name="src.shared.engine.office_image_layout",
                frozen_flag=OFFICE_IMAGE_LAYOUT_CHILD_FLAG,
                request_path=request_path,
            )
            flags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                if os.name == "nt"
                else 0
            )
            process = popen_hidden(
                command,
                cwd=str(Path(__file__).resolve().parents[3]),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=flags,
            )
        except Exception as exc:
            return build_layout_receipt(
                request,
                spec,
                LayoutStatus.CHILD_FAILED,
                failures=(LayoutFailure(LayoutFailureCode.CHILD_PROTOCOL_ERROR, str(exc)),),
            )
        communication = _communicate_layout_child(
            process,
            timeout_seconds=request.timeout_seconds,
        )
        owned_pid = _read_pid_file(pid_path)
        forced = _ensure_owned_pid_stopped(owned_pid) if owned_pid is not None else ""
        cleanup_warnings = _forced_cleanup_warnings(forced)
        if communication.timed_out:
            return build_layout_receipt(
                request,
                spec,
                LayoutStatus.TIMED_OUT,
                application_pid=owned_pid,
                warnings=cleanup_warnings,
                failures=(
                    LayoutFailure(
                        LayoutFailureCode.OFFICE_TIMEOUT,
                        f"Office layout exceeded {request.timeout_seconds:g}s",
                    ),
                ),
            )
        if communication.error is not None:
            return build_layout_receipt(
                request,
                spec,
                LayoutStatus.CHILD_FAILED,
                application_pid=owned_pid,
                warnings=cleanup_warnings,
                failures=(
                    LayoutFailure(
                        LayoutFailureCode.CHILD_PROTOCOL_ERROR,
                        f"child communication failed: {communication.error}",
                    ),
                ),
            )
        if process.returncode != 0 or not result_path.is_file():
            detail = (
                communication.stderr or communication.stdout or ""
            ).strip() or f"child exit {process.returncode}"
            return build_layout_receipt(
                request,
                spec,
                LayoutStatus.CHILD_FAILED,
                application_pid=owned_pid,
                warnings=cleanup_warnings,
                failures=(LayoutFailure(LayoutFailureCode.CHILD_PROTOCOL_ERROR, detail),),
            )
        return _load_child_receipt(
            request,
            spec,
            result_path,
            owned_pid=owned_pid,
            before_pids=before_pids,
            cleanup_warnings=cleanup_warnings,
        )


def _load_child_receipt(
    request: OfficeImageLayoutRequest,
    spec: OfficeProviderSpec,
    result_path: Path,
    *,
    owned_pid: int | None,
    before_pids: set[int],
    cleanup_warnings: tuple[LayoutWarning, ...],
) -> OfficeImageLayoutReceipt:
    try:
        receipt = OfficeImageLayoutReceipt.from_dict(
            json.loads(result_path.read_text(encoding="utf-8"))
        )
    except Exception as exc:
        return build_layout_receipt(
            request,
            spec,
            LayoutStatus.CHILD_FAILED,
            application_pid=owned_pid,
            warnings=cleanup_warnings,
            failures=(LayoutFailure(LayoutFailureCode.CHILD_PROTOCOL_ERROR, str(exc)),),
        )
    reported_pid = receipt.application_pid
    if owned_pid is not None and reported_pid != owned_pid:
        return build_layout_receipt(
            request,
            spec,
            LayoutStatus.CHILD_FAILED,
            application_pid=owned_pid,
            warnings=cleanup_warnings,
            failures=(
                LayoutFailure(
                    LayoutFailureCode.CHILD_PROTOCOL_ERROR,
                    "child receipt PID does not match the owned PID record",
                ),
            ),
        )
    if reported_pid is None and receipt.status is LayoutStatus.SUCCESS:
        return build_layout_receipt(
            request,
            spec,
            LayoutStatus.CHILD_FAILED,
            warnings=cleanup_warnings,
            failures=(
                LayoutFailure(
                    LayoutFailureCode.CHILD_PROTOCOL_ERROR,
                    "successful child receipt did not report an owned Office PID",
                ),
            ),
        )
    if owned_pid is None and reported_pid is not None:
        if reported_pid in before_pids:
            return build_layout_receipt(
                request,
                spec,
                LayoutStatus.CHILD_FAILED,
                failures=(
                    LayoutFailure(
                        LayoutFailureCode.CHILD_PROTOCOL_ERROR,
                        "child receipt reported a pre-existing Office PID",
                    ),
                ),
            )
        cleanup_warnings = (
            *cleanup_warnings,
            *_forced_cleanup_warnings(_ensure_owned_pid_stopped(reported_pid)),
        )
    if cleanup_warnings:
        receipt = replace(receipt, warnings=(*receipt.warnings, *cleanup_warnings))
    return receipt


def _communicate_layout_child(
    process: subprocess.Popen[str],
    *,
    timeout_seconds: float,
) -> _ChildCommunication:
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return _ChildCommunication(stdout=stdout, stderr=stderr)
    except subprocess.TimeoutExpired:
        stdout, stderr = _terminate_and_drain_child(process)
        return _ChildCommunication(
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )
    except Exception as exc:
        stdout, stderr = _terminate_and_drain_child(process)
        return _ChildCommunication(
            stdout=stdout,
            stderr=stderr,
            error=exc,
        )


def _terminate_and_drain_child(
    process: subprocess.Popen[str],
) -> tuple[str, str]:
    _terminate_child(process)
    try:
        return process.communicate(timeout=3)
    except Exception:
        try:
            process.kill()
        except Exception:
            return "", ""
    try:
        return process.communicate(timeout=1)
    except Exception:
        return "", ""


def _forced_cleanup_warnings(forced: str) -> tuple[LayoutWarning, ...]:
    if not forced:
        return ()
    return (
        LayoutWarning(
            LayoutWarningCode.OWNED_PROCESS_FORCED_CLEANUP,
            forced,
        ),
    )

def _read_pid_file(path: Path) -> int | None:
    try:
        pid = int(json.loads(path.read_text(encoding="utf-8")).get("pid", 0))
    except Exception:
        return None
    return pid if pid > 0 else None

def _terminate_child(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            completed = run_hidden(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if completed.returncode == 0:
                return
        except Exception:
            pass
    try:
        process.kill()
    except Exception:
        pass

def _ensure_owned_pid_stopped(pid: int | None) -> str:
    if pid is None:
        return ""
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if not _pid_exists(pid):
            return ""
        time.sleep(0.05)
    if os.name == "nt":
        try:
            completed = run_hidden(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if completed.returncode == 0 or not _pid_exists(pid):
                return "owned Office PID required forced cleanup"
        except Exception:
            pass
    return "owned Office PID did not exit cleanly"

__all__ = [
    "OFFICE_COM_PATH_MAX_UTF16_UNITS",
    "build_office_image_layout_request",
    "run_office_image_layout",
]
