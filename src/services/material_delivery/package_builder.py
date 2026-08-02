"""Build a self-contained delivery directory and ZIP outside the UI layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
from uuid import uuid4
import zipfile

from src.config.atomic_io import atomic_write_text
from src.config.attachment_materials import AttachmentBinding
from src.config.content_artifacts import ContentMaterialBinding
from src.config.library import CONFIG_LIBRARY_ROOT
from src.services.material_content.artifact_repository import (
    ContentArtifactRepository,
    ContentArtifactRepositoryError,
)
from src.services.material_delivery.transaction import remove_owned_path


class DeliveryPackageBuildError(RuntimeError):
    """The package could not be staged and published as one transaction."""


@dataclass(frozen=True, slots=True)
class DeliveryPackageSourceReceipt:
    """Exact, caller-captured authority for one local package source file."""

    path: Path
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError("path must be a Path")
        if not self.path.is_absolute():
            raise ValueError("source receipt path must be absolute")
        digest = str(self.sha256 or "").strip().casefold()
        if not _is_sha256(digest):
            raise ValueError("source receipt sha256 must be a lowercase SHA-256")
        if (
            isinstance(self.byte_size, bool)
            or not isinstance(self.byte_size, int)
            or self.byte_size < 0
        ):
            raise ValueError("source receipt byte_size must be nonnegative")
        object.__setattr__(self, "sha256", digest)


@dataclass(frozen=True, slots=True)
class DeliveryPackageBuildRequest:
    input_path: Path
    output_dir: Path
    manifest_path: Path
    source_receipts: tuple[DeliveryPackageSourceReceipt, ...]
    content_artifact_root: Path | None = None

    def __post_init__(self) -> None:
        for name in ("input_path", "output_dir", "manifest_path"):
            value = getattr(self, name)
            if not isinstance(value, Path):
                raise TypeError(f"{name} must be a Path")
        if self.content_artifact_root is not None and not isinstance(
            self.content_artifact_root,
            Path,
        ):
            raise TypeError("content_artifact_root must be a Path when provided")
        if not isinstance(self.source_receipts, tuple) or any(
            not isinstance(item, DeliveryPackageSourceReceipt)
            for item in self.source_receipts
        ):
            raise TypeError(
                "source_receipts must be a tuple of DeliveryPackageSourceReceipt values"
            )
        receipt_paths: set[str] = set()
        for receipt in self.source_receipts:
            identity = _normalized_path_identity(receipt.path)
            if identity in receipt_paths:
                raise ValueError("source receipt paths must be unique")
            receipt_paths.add(identity)


def capture_delivery_package_source_receipt(
    path: Path,
) -> DeliveryPackageSourceReceipt:
    """Capture one stable file identity without accepting reparse traversal."""

    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    resolved = _resolve_non_reparse_regular_file(
        path,
        error_domain="material_package_source_receipt",
    )
    digest, byte_size = _stable_file_fingerprint(
        resolved,
        error_domain="material_package_source_receipt",
    )
    return DeliveryPackageSourceReceipt(
        path=resolved,
        sha256=digest,
        byte_size=byte_size,
    )


@dataclass(frozen=True, slots=True)
class DeliveryPackageReceipt:
    directory_path: Path
    zip_path: Path
    report_path: Path
    package_manifest_path: Path
    status: str
    copied_file_count: int
    missing_reference_count: int

    def to_path_map(self) -> dict[str, str]:
        return {
            "directory": str(self.directory_path),
            "zip": str(self.zip_path),
            "report": str(self.report_path),
            "package_manifest": str(self.package_manifest_path),
        }


class MaterialDeliveryPackageBuilder:
    """Stage all outputs first, then publish the directory and ZIP together."""

    def build(self, request: DeliveryPackageBuildRequest) -> DeliveryPackageReceipt:
        if not isinstance(request, DeliveryPackageBuildRequest):
            raise TypeError("request must be a DeliveryPackageBuildRequest")
        source_receipts = {
            _normalized_path_identity(item.path): item
            for item in request.source_receipts
        }
        manifest_receipt = _authorized_source_receipt(
            request.manifest_path,
            source_receipts,
            category="manifest",
            key="material_manifest",
            role="manifest",
        )
        manifest_path = manifest_receipt.path
        try:
            manifest_bytes = _read_verified_receipt_bytes(
                manifest_receipt,
                error_domain="material_manifest",
            )
            payload = json.loads(manifest_bytes.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DeliveryPackageBuildError(
                f"material_manifest_invalid:{manifest_path}"
            ) from exc
        if not isinstance(payload, dict):
            raise DeliveryPackageBuildError("material_manifest_root_not_object")
        if payload.get("kind") != "material_attachment_manifest":
            raise DeliveryPackageBuildError("material_manifest_kind_invalid")
        if payload.get("schema_version") != 1:
            raise DeliveryPackageBuildError("material_manifest_schema_unsupported")

        output_dir = request.output_dir.expanduser().resolve(strict=False)
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{request.input_path.stem}_material_package"
        final_dir = output_dir / base_name
        final_zip = output_dir / f"{base_name}.zip"
        transaction_id = uuid4().hex
        staging_dir = output_dir / f".{base_name}.{transaction_id}.staging"
        staged_zip = output_dir / f".{base_name}.{transaction_id}.zip.tmp"
        collector = _PackageCollector(
            staging_dir,
            source_receipts=source_receipts,
            content_artifact_root=(
                request.content_artifact_root
                or (CONFIG_LIBRARY_ROOT / "content_artifacts")
            ),
        )

        try:
            staging_dir.mkdir(parents=False, exist_ok=False)
            self._collect(
                payload,
                collector,
            )
            status = _package_status(payload, collector.missing)
            public_missing = _public_missing_references(collector.missing)
            public_manifest = _public_material_manifest(
                payload,
                status=status,
                files=collector.copied,
                missing_references=public_missing,
            )
            public_manifest_path = staging_dir / "manifest" / "material_manifest.json"
            public_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            _write_public_json(public_manifest_path, public_manifest)
            collector.record_generated(
                public_manifest_path,
                category="manifest",
                key="material_manifest",
                role="public_delivery",
            )
            package_manifest = _package_manifest(
                request=request,
                manifest_payload=payload,
                status=status,
                files=collector.copied,
                missing_references=public_missing,
            )
            _write_public_json(staging_dir / "package_manifest.json", package_manifest)
            _write_public_text(
                staging_dir / "archive_report.md",
                _render_archive_report(package_manifest),
            )
            _assert_public_archive_text_files(staging_dir)
            _write_zip(staging_dir, staged_zip, package_manifest)
            _publish_pair(
                staging_dir=staging_dir,
                final_dir=final_dir,
                staged_zip=staged_zip,
                final_zip=final_zip,
                owner=output_dir,
                transaction_id=transaction_id,
            )
        except DeliveryPackageBuildError:
            raise
        except Exception as exc:
            raise DeliveryPackageBuildError(
                f"material_package_build_failed:{type(exc).__name__}:{exc}"
            ) from exc
        finally:
            remove_owned_path(staging_dir, output_dir)
            staged_zip.unlink(missing_ok=True)

        return DeliveryPackageReceipt(
            directory_path=final_dir,
            zip_path=final_zip,
            report_path=final_dir / "archive_report.md",
            package_manifest_path=final_dir / "package_manifest.json",
            status=status,
            copied_file_count=len(collector.copied),
            missing_reference_count=len(collector.missing),
        )

    def _collect(
        self,
        payload: dict[str, object],
        collector: "_PackageCollector",
    ) -> None:
        for asset in _dict_items(payload.get("asset_items")):
            collector.copy_asset(asset)

        domains = payload.get("material_domains")
        if isinstance(domains, Mapping):
            collector.copy_content_domain(domains.get("content"))
            collector.copy_attachment_domain(domains.get("attachment"))

        delivery = payload.get("delivery")
        if not isinstance(delivery, Mapping):
            return
        collector.copy_path_map(delivery.get("output_paths"), "output", "outputs")
        collector.copy_path_map(
            delivery.get("compare_paths"), "compare", "compare"
        )
        collector.copy_path_map(
            delivery.get("intermediate_paths"),
            "intermediate",
            "intermediate",
        )
        reports = delivery.get("report_paths")
        if isinstance(reports, (list, tuple)):
            for raw_path in reports:
                collector.copy(
                    Path(str(raw_path or "")),
                    category="report",
                    target_dir="reports",
                )


@dataclass(slots=True)
class _PackageCollector:
    root: Path
    content_artifact_root: Path
    source_receipts: dict[str, DeliveryPackageSourceReceipt]
    copied: list[dict[str, object]]
    missing: list[dict[str, object]]
    vendored_content_artifact_ids: set[str]

    def __init__(
        self,
        root: Path,
        *,
        source_receipts: dict[str, DeliveryPackageSourceReceipt],
        content_artifact_root: Path,
    ) -> None:
        self.root = root
        self.content_artifact_root = content_artifact_root
        self.source_receipts = dict(source_receipts)
        self.copied = []
        self.missing = []
        self.vendored_content_artifact_ids = set()

    def copy(
        self,
        source: Path,
        *,
        category: str,
        target_dir: str,
        key: str = "",
        role: str = "",
        preferred_name: str = "",
        expected_sha256: str = "",
        expected_byte_size: int | None = None,
        strict_target: bool = False,
        receipt_required: bool = False,
        required_error_domain: str = "attachment_receipt",
    ) -> None:
        source_text = str(source or "").strip()
        if source_text:
            _assert_no_reparse_components(
                source,
                error_domain="material_package_source",
                allow_missing=True,
            )
        if not source_text or not source.is_file():
            if receipt_required:
                raise DeliveryPackageBuildError(
                    f"{required_error_domain}_source_missing:{source_text}"
                )
            self._missing(category, key, role, source_text, "source file missing")
            return
        source_receipt = _authorized_source_receipt(
            source,
            self.source_receipts,
            category=category,
            key=key,
            role=role,
        )
        safe_dir = _safe_relative_dir(target_dir)
        destination_dir = self.root.joinpath(*safe_dir.parts)
        destination_dir.mkdir(parents=True, exist_ok=True)
        requested_destination = destination_dir / _safe_filename(
            preferred_name or source.name
        )
        if strict_target and requested_destination.exists():
            if receipt_required:
                raise DeliveryPackageBuildError(
                    f"{required_error_domain}_target_collision:"
                    f"{requested_destination}"
                )
            self._missing(
                category,
                key,
                role,
                source_text,
                f"package target collision: {requested_destination}",
            )
            return
        destination = (
            requested_destination
            if strict_target
            else _unique_path(requested_destination)
        )
        copied_destination = False
        try:
            if expected_sha256 and not _is_sha256(expected_sha256):
                raise ValueError("declared source hash is not a SHA-256 digest")
            if expected_byte_size is not None and source_receipt.byte_size != int(
                expected_byte_size
            ):
                raise ValueError("source byte size differs from declared identity")
            if expected_sha256 and source_receipt.sha256 != expected_sha256:
                raise ValueError("source hash differs from declared identity")
            public_diagnostic = category in {
                "output",
                "report",
                "intermediate",
            } and (
                source_receipt.path.suffix.casefold() in {".json", ".md"}
            )
            if public_diagnostic and (expected_sha256 or expected_byte_size is not None):
                raise ValueError(
                    "public diagnostic projection cannot retain a source identity"
                )
            if source_receipt.path.resolve() != destination.resolve():
                if public_diagnostic:
                    _copy_public_diagnostic_file(source_receipt, destination)
                else:
                    _copy_verified_receipt(
                        source_receipt,
                        destination,
                        error_domain="material_package_source",
                    )
                copied_destination = True
            if (
                expected_byte_size is not None
                and not public_diagnostic
                and destination.stat().st_size != int(expected_byte_size)
            ):
                raise ValueError("copied byte size differs from declared identity")
            if (
                expected_sha256
                and not public_diagnostic
                and _sha256_file(destination) != expected_sha256
            ):
                raise ValueError("copied hash differs from declared identity")
        except (OSError, ValueError, DeliveryPackageBuildError) as exc:
            if copied_destination or _path_is_within(destination, self.root):
                try:
                    if destination.is_file() or destination.is_symlink():
                        destination.unlink()
                except OSError as cleanup_exc:
                    raise DeliveryPackageBuildError(
                        "material_package_partial_copy_cleanup_failed:"
                        f"{destination}"
                    ) from cleanup_exc
            if isinstance(exc, DeliveryPackageBuildError):
                raise
            if receipt_required:
                raise DeliveryPackageBuildError(
                    f"{required_error_domain}_evidence_invalid:{source_text}:{exc}"
                ) from exc
            self._missing(category, key, role, source_text, str(exc))
            return
        destination_sha256 = _sha256_file(destination)
        destination_byte_size = destination.stat().st_size
        self.copied.append(
            {
                "category": category,
                "key": key,
                "role": role,
                "path": destination.relative_to(self.root).as_posix(),
                "sha256": destination_sha256,
                "byte_size": destination_byte_size,
            }
        )

    def record_generated(
        self,
        path: Path,
        *,
        category: str,
        key: str = "",
        role: str = "",
    ) -> None:
        try:
            relative = path.resolve(strict=True).relative_to(self.root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise DeliveryPackageBuildError(
                "material_package_generated_file_escape"
            ) from exc
        _assert_no_reparse_components(
            path,
            error_domain="material_package_generated_file",
        )
        self.copied.append(
            {
                "category": category,
                "key": key,
                "role": role,
                "path": relative.as_posix(),
                "sha256": _sha256_file(path),
                "byte_size": path.stat().st_size,
            }
        )

    def copy_asset(self, asset: dict[str, object]) -> None:
        role = _text(asset.get("role")) or "asset"
        archive_dir = _safe_relative_dir(_text(asset.get("archive_dir")) or role)
        target = PurePosixPath("assets").joinpath(*archive_dir.parts).as_posix()
        path_text = _text(asset.get("path"))
        metadata = asset.get("metadata")
        cache_text = (
            _text(metadata.get("cache_path"))
            if isinstance(metadata, Mapping)
            else ""
        )
        source_text = ""
        if path_text and not _looks_remote(path_text) and Path(path_text).is_file():
            source_text = path_text
        elif cache_text and Path(cache_text).is_file():
            source_text = cache_text
        elif path_text and Path(path_text).is_file():
            source_text = path_text
        if not source_text:
            self._missing(
                "asset",
                "",
                role,
                cache_text if cache_text and not _looks_remote(path_text) else path_text,
                "source file missing",
            )
            return
        expected_sha256 = _normalized_sha256(
            asset.get("content_sha256") or asset.get("content_hash")
        )
        expected_byte_size = _optional_nonnegative_int(asset.get("byte_size"))
        if not expected_sha256 or expected_byte_size is None:
            self._missing(
                "asset",
                _text(asset.get("item_id")),
                role,
                source_text,
                "declared file identity missing or invalid",
            )
            return
        self.copy(
            Path(source_text),
            category="asset",
            target_dir=target,
            key=_text(asset.get("item_id")),
            role=role,
            expected_sha256=expected_sha256,
            expected_byte_size=expected_byte_size,
        )

    def copy_content_domain(self, domain: object) -> None:
        if not isinstance(domain, Mapping):
            return
        for raw_binding in _dict_items(domain.get("bindings")):
            content_id = _text(raw_binding.get("content_id")) or "content"
            try:
                binding = ContentMaterialBinding.from_dict(raw_binding)
            except (TypeError, ValueError) as exc:
                self._missing(
                    "content_artifact",
                    content_id,
                    "artifact",
                    "",
                    f"typed content binding invalid: {exc}",
                )
                continue
            self._vendor_content_artifact(binding)

    def _vendor_content_artifact(self, binding: ContentMaterialBinding) -> None:
        artifact_id = binding.artifact_ref.artifact_id
        repository = ContentArtifactRepository(self.content_artifact_root)
        try:
            resolved = repository.validate(binding.artifact_ref)
        except (ContentArtifactRepositoryError, OSError, ValueError) as exc:
            self._missing(
                "content_artifact",
                binding.content_id,
                "artifact",
                artifact_id,
                f"content artifact unavailable or invalid: {exc}",
            )
            return
        if artifact_id in self.vendored_content_artifact_ids:
            return
        try:
            vendor_directory = repository.vendor(
                binding.artifact_ref,
                self.root / "content_artifacts" / "sha256",
            )
        except (ContentArtifactRepositoryError, OSError, ValueError) as exc:
            self._missing(
                "content_artifact",
                binding.content_id,
                "artifact",
                artifact_id,
                f"content artifact unavailable or invalid: {exc}",
            )
            return

        manifest = resolved.manifest
        manifest_payload = manifest.to_json().encode("utf-8")
        declared_files = (
            ("manifest.json", binding.artifact_ref.manifest_sha256, len(manifest_payload)),
            *(
                (contract.path, contract.sha256, contract.byte_size)
                for contract in (
                    manifest.source.blob,
                    manifest.fragment,
                    manifest.receipt,
                    *(item.file for item in manifest.resources),
                )
            ),
        )
        for relative_path, expected_sha256, expected_byte_size in declared_files:
            destination = vendor_directory.joinpath(
                *PurePosixPath(relative_path).parts
            )
            if (
                not destination.is_file()
                or destination.stat().st_size != expected_byte_size
                or _sha256_file(destination) != expected_sha256
            ):
                raise DeliveryPackageBuildError(
                    "vendored_content_artifact_identity_mismatch:"
                    f"{artifact_id}:{relative_path}"
                )
            self.copied.append(
                {
                    "category": "content_artifact",
                    "key": binding.content_id,
                    "role": "artifact",
                    "path": destination.relative_to(self.root).as_posix(),
                    "sha256": expected_sha256,
                    "byte_size": expected_byte_size,
                }
            )
        self.vendored_content_artifact_ids.add(artifact_id)

    def copy_attachment_domain(self, domain: object) -> None:
        if not isinstance(domain, Mapping):
            return
        raw_bindings = _dict_items(domain.get("bindings"))
        bindings: list[tuple[dict[str, object], AttachmentBinding]] = []
        for raw_binding in raw_bindings:
            role = _text(raw_binding.get("role")) or "attachment"
            # Path traversal is a package-boundary violation, not a recoverable
            # missing material.  Reject it before typed-contract diagnostics can
            # downgrade the whole binding to an incomplete receipt.
            for raw_item in _dict_items(raw_binding.get("items")):
                _safe_optional_relative_path(
                    _text(raw_item.get("relative_path"))
                )
            try:
                typed_binding = AttachmentBinding.from_dict(raw_binding)
            except (TypeError, ValueError) as exc:
                self._missing(
                    "attachment_binding",
                    "",
                    role,
                    "",
                    f"typed attachment binding invalid: {exc}",
                )
                continue
            bindings.append((raw_binding, typed_binding))
        execution = domain.get("execution")
        if isinstance(execution, Mapping) and _text(execution.get("status")) in {
            "applied",
            "partial_success",
            "failed",
        }:
            self._copy_processed_attachment_bundles(
                [raw_binding for raw_binding, _typed_binding in bindings],
                execution,
            )
            return
        for raw_binding, binding in bindings:
            role = binding.role
            base_dir = _text(raw_binding.get("package_subdir"))
            if not base_dir:
                base_dir = f"attachments/{_safe_filename(role)}"
            base = _safe_relative_dir(base_dir)
            for item in binding.items:
                file_ref = item.file_ref
                source = Path(file_ref.source_path)
                relative = _safe_optional_relative_path(
                    item.relative_path
                )
                target = PurePosixPath(*base.parts)
                preferred_name = file_ref.original_name or source.name
                if relative is not None:
                    target = target.joinpath(*relative.parent.parts)
                    preferred_name = relative.name
                self.copy(
                    source,
                    category="attachment",
                    target_dir=target.as_posix(),
                    key=item.item_id,
                    role=role,
                    preferred_name=preferred_name,
                    expected_sha256=file_ref.content_sha256,
                    expected_byte_size=file_ref.byte_size,
                    strict_target=True,
                )

    def _copy_processed_attachment_bundles(
        self,
        bindings: list[dict[str, object]],
        execution: Mapping[str, object],
    ) -> None:
        binding_by_role = {
            _text(binding.get("role")): binding for binding in bindings
        }
        raw_receipts = execution.get("receipts")
        receipts = raw_receipts if isinstance(raw_receipts, Mapping) else {}
        for raw_role, raw_receipt in sorted(
            receipts.items(),
            key=lambda item: str(item[0]).casefold(),
        ):
            role = _text(raw_role) or "attachment"
            if not isinstance(raw_receipt, Mapping):
                raise DeliveryPackageBuildError(
                    f"attachment_receipt_invalid:{role}"
                )
            binding = binding_by_role.get(role, {})
            base_dir = _text(binding.get("package_subdir"))
            if not base_dir:
                base_dir = f"attachments/{_safe_filename(role)}"
            base = _safe_relative_dir(base_dir)
            output_text = _text(raw_receipt.get("output_directory"))
            output_directory = Path(output_text) if output_text else Path()
            if not output_text or not output_directory.is_dir():
                raise DeliveryPackageBuildError(
                    f"attachment_receipt_output_missing:{role}:{output_text}"
                )
            for file_receipt in _dict_items(raw_receipt.get("files")):
                relative = _safe_optional_relative_path(
                    _text(file_receipt.get("relative_path"))
                )
                if relative is None:
                    raise DeliveryPackageBuildError(
                        f"attachment_receipt_relative_path_invalid:{role}"
                    )
                source = output_directory.joinpath(*relative.parts)
                _assert_receipt_owned_path(
                    source,
                    output_directory,
                    role=role,
                )
                expected_sha256 = _text(file_receipt.get("output_sha256"))
                expected_byte_size = _optional_nonnegative_int(
                    file_receipt.get("output_byte_size")
                )
                if not _is_sha256(expected_sha256) or expected_byte_size is None:
                    raise DeliveryPackageBuildError(
                        f"attachment_receipt_file_evidence_invalid:{role}:"
                        f"{file_receipt.get('item_id', '')}"
                    )
                target = PurePosixPath(*base.parts).joinpath(
                    *relative.parent.parts
                )
                self.copy(
                    source,
                    category="attachment",
                    target_dir=target.as_posix(),
                    key=_text(file_receipt.get("item_id")),
                    role=role,
                    preferred_name=relative.name,
                    expected_sha256=expected_sha256,
                    expected_byte_size=expected_byte_size,
                    strict_target=True,
                    receipt_required=True,
                )
            receipt_target_dir = self.root.joinpath(*base.parts)
            receipt_target_dir.mkdir(parents=True, exist_ok=True)
            receipt_target = receipt_target_dir / "attachment_bundle_receipt.json"
            if receipt_target.exists():
                raise DeliveryPackageBuildError(
                    f"attachment_receipt_target_collision:{receipt_target}"
                )
            _write_public_json(
                receipt_target,
                _public_attachment_receipt(role, raw_receipt),
            )
            self.record_generated(
                receipt_target,
                category="attachment_receipt",
                role=role,
            )

    def copy_path_map(self, value: object, category: str, target_dir: str) -> None:
        if not isinstance(value, Mapping):
            return
        for raw_key, raw_path in value.items():
            key = _text(raw_key)
            source = Path(_text(raw_path))
            self.copy(
                source,
                category=category,
                target_dir=target_dir,
                key=key,
                preferred_name=f"{_safe_filename(key)}_{source.name}",
            )

    def _missing(
        self,
        category: str,
        key: str,
        role: str,
        source: str,
        reason: str,
    ) -> None:
        self.missing.append(
            {
                "category": category,
                "key": key,
                "role": role,
                "source": source,
                "reason": reason,
            }
        )


def build_material_delivery_package(
    request: DeliveryPackageBuildRequest,
) -> DeliveryPackageReceipt:
    return MaterialDeliveryPackageBuilder().build(request)


def _package_manifest(
    *,
    request: DeliveryPackageBuildRequest,
    manifest_payload: dict[str, object],
    status: str,
    files: list[dict[str, object]],
    missing_references: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "kind": "material_delivery_package",
        "schema_version": 1,
        "visibility": "public_delivery",
        "input_name": _safe_filename(request.input_path.name),
        "status": status,
        "material_schema": _public_schema(manifest_payload.get("material_schema")),
        "material_profile": _public_profile(
            manifest_payload.get("material_profile")
        ),
        "missing": _public_missing_material(manifest_payload.get("missing")),
        "summary": _public_summary(manifest_payload.get("summary")),
        "files": [_public_file_record(item) for item in files],
        "control_files": [
            "package_manifest.json",
            "archive_report.md",
        ],
        "missing_references": missing_references,
    }


def _public_material_manifest(
    payload: dict[str, object],
    *,
    status: str,
    files: list[dict[str, object]],
    missing_references: list[dict[str, object]],
) -> dict[str, object]:
    """Project the local diagnostic manifest onto an explicit delivery allowlist."""

    return {
        "kind": "material_attachment_manifest",
        "schema_version": 1,
        "visibility": "public_delivery",
        "status": status,
        "material_schema": _public_schema(payload.get("material_schema")),
        "material_profile": _public_profile(payload.get("material_profile")),
        "input_contract": _public_input_contract(payload.get("input_contract")),
        "compliance": _public_compliance(payload.get("compliance")),
        "fields": [_public_field(item) for item in _dict_items(payload.get("fields"))],
        "asset_roles": [
            _public_asset_role(item) for item in _dict_items(payload.get("asset_roles"))
        ],
        "material_domains": _public_material_domains(payload.get("material_domains")),
        "missing": _public_missing_material(payload.get("missing")),
        "summary": _public_summary(payload.get("summary")),
        "packaged_files": [_public_file_record(item) for item in files],
        "missing_references": missing_references,
    }


def _public_schema(value: object) -> dict[str, object]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "schema_id": _text(source.get("schema_id")),
        "schema_ids": _public_text_list(source.get("schema_ids")),
        "label": _text(source.get("label")),
        "labels": _public_text_list(source.get("labels")),
        "family": _text(source.get("family")),
        "required_field_keys": _public_text_list(
            source.get("required_field_keys")
        ),
        "required_asset_roles": _public_text_list(
            source.get("required_asset_roles")
        ),
    }


def _public_profile(value: object) -> dict[str, str]:
    source = value if isinstance(value, Mapping) else {}
    return {
        key: _text(source.get(key))
        for key in ("archive_id", "profile_id", "profile_name")
    }


def _public_input_contract(value: object) -> dict[str, object]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "accepted_formats": _public_text_list(source.get("accepted_formats")),
        "structured_formats": _public_text_list(source.get("structured_formats")),
        "failure_policy": _text(source.get("failure_policy")),
    }


def _public_compliance(value: object) -> dict[str, str]:
    source = value if isinstance(value, Mapping) else {}
    return {
        key: _text(source.get(key))
        for key in ("profile_id", "rule_family", "count_profile_id")
    }


def _public_field(item: Mapping[str, object]) -> dict[str, object]:
    return {
        "key": _text(item.get("key")),
        "label": _text(item.get("label")),
        "required": bool(item.get("required", False)),
        "present": bool(item.get("present", False)),
        "aliases": _public_text_list(item.get("aliases")),
    }


def _public_asset_role(item: Mapping[str, object]) -> dict[str, object]:
    maximum = item.get("max_items")
    if isinstance(maximum, bool) or not isinstance(maximum, int):
        maximum = None
    return {
        "role": _text(item.get("role")),
        "label": _text(item.get("label")),
        "required": bool(item.get("required", False)),
        "accepted_types": _public_text_list(item.get("accepted_types")),
        "cardinality": _text(item.get("cardinality")),
        "source_kind": _text(item.get("source_kind")),
        "recursive": bool(item.get("recursive", False)),
        "min_items": _optional_nonnegative_int(item.get("min_items")) or 0,
        "max_items": maximum,
        "order_policy": _text(item.get("order_policy")),
        "naming_template": _text(item.get("naming_template")),
        "archive_dir": _public_relative_text(item.get("archive_dir")),
        "package_subdir": _public_relative_text(item.get("package_subdir")),
        "material_domain": _text(item.get("material_domain")),
        "present": bool(item.get("present", False)),
        "missing": bool(item.get("missing", False)),
        "item_count": _optional_nonnegative_int(item.get("item_count")) or 0,
    }


def _public_material_domains(value: object) -> dict[str, object]:
    domains = value if isinstance(value, Mapping) else {}
    content = domains.get("content")
    content = content if isinstance(content, Mapping) else {}
    image = domains.get("image")
    image = image if isinstance(image, Mapping) else {}
    attachment = domains.get("attachment")
    attachment = attachment if isinstance(attachment, Mapping) else {}
    execution = attachment.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    raw_receipts = execution.get("receipts")
    raw_receipts = raw_receipts if isinstance(raw_receipts, Mapping) else {}
    return {
        "content": {
            "bindings": [
                _public_content_binding(item)
                for item in _dict_items(content.get("bindings"))
            ],
            "binding_count": len(_dict_items(content.get("bindings"))),
        },
        "image": {
            "item_count": len(_dict_items(image.get("items"))),
            "material_rule_count": len(
                _dict_items(image.get("material_rules"))
            ),
            "legacy_rule_count": len(
                _dict_items(image.get("legacy_insertion_rules"))
            ),
        },
        "attachment": {
            "bindings": [
                _public_attachment_binding(item)
                for item in _dict_items(attachment.get("bindings"))
            ],
            "execution": {
                "status": _text(execution.get("status")),
                "binding_count": _public_count(execution.get("binding_count")),
                "succeeded_binding_count": _public_count(
                    execution.get("succeeded_binding_count")
                ),
                "failed_binding_count": _public_count(
                    execution.get("failed_binding_count")
                ),
                "file_count": _public_count(execution.get("file_count")),
                "receipts": {
                    _safe_filename(role): _public_attachment_receipt(
                        _text(role), receipt
                    )
                    for role, receipt in sorted(
                        raw_receipts.items(), key=lambda pair: str(pair[0]).casefold()
                    )
                    if isinstance(receipt, Mapping)
                },
            },
        },
    }


def _public_content_binding(item: Mapping[str, object]) -> dict[str, object]:
    artifact = item.get("artifact_ref")
    artifact = artifact if isinstance(artifact, Mapping) else {}
    return {
        "content_id": _text(item.get("content_id")),
        "artifact_ref": {
            "artifact_id": _text(artifact.get("artifact_id")),
            "manifest_sha256": _normalized_sha256(
                artifact.get("manifest_sha256")
            ),
        },
    }


def _public_attachment_binding(item: Mapping[str, object]) -> dict[str, object]:
    maximum = item.get("max_items")
    if isinstance(maximum, bool) or not isinstance(maximum, int):
        maximum = None
    return {
        "role": _text(item.get("role")),
        "label": _text(item.get("label")),
        "source_kind": _text(item.get("source_kind")),
        "processing_mode": _text(item.get("processing_mode")),
        "cardinality": _text(item.get("cardinality")),
        "required": bool(item.get("required", False)),
        "recursive": bool(item.get("recursive", False)),
        "min_items": _public_count(item.get("min_items")),
        "max_items": maximum,
        "package_subdir": _public_relative_text(item.get("package_subdir")),
        "items": [
            _public_attachment_item(raw)
            for raw in _dict_items(item.get("items"))
        ],
    }


def _public_attachment_item(item: Mapping[str, object]) -> dict[str, object]:
    file_ref = item.get("file_ref")
    file_ref = file_ref if isinstance(file_ref, Mapping) else {}
    return {
        "item_id": _text(item.get("item_id")),
        "label": _text(item.get("label")),
        "sequence": _public_count(item.get("sequence")),
        "relative_path": _public_relative_text(item.get("relative_path")),
        "file": {
            "original_name": _safe_filename(file_ref.get("original_name")),
            "media_type": _text(file_ref.get("media_type")),
            "sha256": _normalized_sha256(file_ref.get("content_sha256")),
            "byte_size": _public_count(file_ref.get("byte_size")),
        },
    }


def _public_attachment_receipt(
    role: str,
    value: Mapping[str, object],
) -> dict[str, object]:
    return {
        "receipt_id": _text(value.get("receipt_id")),
        "snapshot_id": _normalized_sha256(value.get("snapshot_id")),
        "binding_role": _text(value.get("binding_role")) or role,
        "binding_revision": _normalized_sha256(value.get("binding_revision")),
        "dependency_index_id": _normalized_sha256(
            value.get("dependency_index_id")
        ),
        "bundle_sha256": _normalized_sha256(value.get("bundle_sha256")),
        "files": [
            {
                "item_id": _text(item.get("item_id")),
                "relative_path": _public_relative_text(item.get("relative_path")),
                "output_sha256": _normalized_sha256(item.get("output_sha256")),
                "output_byte_size": _public_count(item.get("output_byte_size")),
                "status": _text(item.get("status")),
                "field_replacement_count": _public_count(
                    item.get("field_replacement_count")
                ),
                "image_job_count": _public_count(item.get("image_job_count")),
            }
            for item in _dict_items(value.get("files"))
        ],
    }


def _public_missing_material(value: object) -> dict[str, list[str]]:
    source = value if isinstance(value, Mapping) else {}
    return {
        key: _public_text_list(source.get(key))
        for key in ("schema_ids", "field_keys", "asset_roles")
    }


def _public_summary(value: object) -> dict[str, int]:
    source = value if isinstance(value, Mapping) else {}
    return {
        str(key): int(raw)
        for key, raw in source.items()
        if str(key).endswith("_count")
        and isinstance(raw, int)
        and not isinstance(raw, bool)
        and raw >= 0
    }


def _public_file_record(value: Mapping[str, object]) -> dict[str, object]:
    relative = _safe_relative_path(_text(value.get("path"))).as_posix()
    digest = _normalized_sha256(value.get("sha256"))
    byte_size = _optional_nonnegative_int(value.get("byte_size"))
    if not digest or byte_size is None:
        raise DeliveryPackageBuildError(
            f"material_package_public_file_identity_invalid:{relative}"
        )
    return {
        "category": _text(value.get("category")),
        "key": _text(value.get("key")),
        "role": _text(value.get("role")),
        "path": relative,
        "sha256": digest,
        "byte_size": byte_size,
    }


def _public_missing_references(
    values: list[dict[str, object]],
) -> list[dict[str, str]]:
    return [
        {
            "category": _text(item.get("category")),
            "key": _text(item.get("key")),
            "role": _text(item.get("role")),
            "code": _public_missing_code(_text(item.get("reason"))),
        }
        for item in values
    ]


def _public_missing_code(reason: str) -> str:
    normalized = reason.casefold()
    if "source file missing" in normalized:
        return "source_missing"
    if "identity missing" in normalized:
        return "declared_identity_missing"
    if "typed" in normalized and "invalid" in normalized:
        return "typed_contract_invalid"
    if "content artifact" in normalized:
        return "content_artifact_unavailable"
    if "collision" in normalized:
        return "package_target_collision"
    if "hash" in normalized or "byte size" in normalized or "evidence" in normalized:
        return "source_identity_mismatch"
    return "material_unavailable"


def _public_relative_text(value: object) -> str:
    text = _text(value)
    return "" if not text else _safe_relative_path(text).as_posix()


def _public_text_list(value: object) -> list[str]:
    return [_text(item) for item in _list(value) if _text(item)]


def _public_count(value: object) -> int:
    return _optional_nonnegative_int(value) or 0


def _package_status(
    payload: dict[str, object],
    missing_references: list[dict[str, object]],
) -> str:
    domains = payload.get("material_domains")
    domains = domains if isinstance(domains, Mapping) else {}
    attachment = domains.get("attachment")
    attachment = attachment if isinstance(attachment, Mapping) else {}
    attachment_execution = attachment.get("execution")
    attachment_execution = (
        attachment_execution
        if isinstance(attachment_execution, Mapping)
        else {}
    )
    if _text(attachment_execution.get("status")) in {
        "failed",
        "partial_success",
    }:
        return "partial_success"
    missing = payload.get("missing")
    missing = missing if isinstance(missing, Mapping) else {}
    has_missing_material = any(
        bool(missing.get(key))
        for key in ("schema_ids", "field_keys", "asset_roles")
    )
    return "incomplete" if has_missing_material or missing_references else "complete"


def _optional_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _normalized_sha256(value: object) -> str:
    normalized = _text(value).casefold()
    if normalized.startswith("sha256:"):
        normalized = normalized.removeprefix("sha256:")
    return normalized if _is_sha256(normalized) else ""


def _assert_receipt_owned_path(source: Path, owner: Path, *, role: str) -> None:
    if not source.exists() and not source.is_symlink():
        return
    try:
        _assert_no_reparse_components(
            owner,
            error_domain="attachment_receipt_owner",
        )
        _assert_no_reparse_components(
            source,
            error_domain="attachment_receipt_source",
        )
        resolved_owner = owner.resolve(strict=True)
        resolved_source = source.resolve(strict=True)
        resolved_source.relative_to(resolved_owner)
    except (OSError, ValueError) as exc:
        raise DeliveryPackageBuildError(
            f"attachment_receipt_source_escape:{role}:{source}"
        ) from exc


def _path_is_within(path: Path, owner: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(owner.resolve(strict=False))
    except (OSError, ValueError):
        return False
    return True


def _normalized_path_identity(path: Path) -> str:
    absolute = path.expanduser()
    if not absolute.is_absolute():
        absolute = Path.cwd() / absolute
    return os.path.normcase(os.path.abspath(str(absolute)))


def _assert_no_reparse_components(
    path: Path,
    *,
    error_domain: str,
    allow_missing: bool = False,
) -> None:
    absolute = Path(_normalized_path_identity(path))
    current = Path(absolute.anchor)
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for part in parts:
        current = current / part
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            if allow_missing:
                return
            raise DeliveryPackageBuildError(
                f"{error_domain}_missing:{current}"
            ) from None
        except OSError as exc:
            raise DeliveryPackageBuildError(
                f"{error_domain}_inspect_failed:{current}"
            ) from exc
        file_attributes = int(getattr(current_stat, "st_file_attributes", 0) or 0)
        try:
            junction = bool(current.is_junction())
        except OSError:
            junction = True
        if (
            stat.S_ISLNK(current_stat.st_mode)
            or junction
            or bool(
                file_attributes
                & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400))
            )
        ):
            raise DeliveryPackageBuildError(
                f"{error_domain}_reparse_component:{current}"
            )


def _resolve_non_reparse_regular_file(
    path: Path,
    *,
    error_domain: str,
) -> Path:
    _assert_no_reparse_components(path, error_domain=error_domain)
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise DeliveryPackageBuildError(f"{error_domain}_missing:{path}") from exc
    if not resolved.is_file():
        raise DeliveryPackageBuildError(f"{error_domain}_not_regular:{path}")
    _assert_no_reparse_components(resolved, error_domain=error_domain)
    return resolved


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


def _stable_file_fingerprint(
    path: Path,
    *,
    error_domain: str,
) -> tuple[str, int]:
    resolved = _resolve_non_reparse_regular_file(path, error_domain=error_domain)
    digest = sha256()
    byte_size = 0
    try:
        with resolved.open("rb") as stream:
            before = os.fstat(stream.fileno())
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                byte_size += len(chunk)
            after = os.fstat(stream.fileno())
        path_after = resolved.stat()
    except OSError as exc:
        raise DeliveryPackageBuildError(
            f"{error_domain}_read_failed:{resolved}"
        ) from exc
    _assert_no_reparse_components(resolved, error_domain=error_domain)
    if (
        _stat_identity(before) != _stat_identity(after)
        or _stat_identity(after) != _stat_identity(path_after)
        or byte_size != int(after.st_size)
    ):
        raise DeliveryPackageBuildError(f"{error_domain}_identity_drift:{resolved}")
    return digest.hexdigest(), byte_size


def _authorized_source_receipt(
    source: Path,
    source_receipts: Mapping[str, DeliveryPackageSourceReceipt],
    *,
    category: str,
    key: str,
    role: str,
) -> DeliveryPackageSourceReceipt:
    _assert_no_reparse_components(
        source,
        error_domain="material_package_source",
        allow_missing=True,
    )
    try:
        resolved = _resolve_non_reparse_regular_file(
            source,
            error_domain="material_package_source",
        )
    except DeliveryPackageBuildError as exc:
        raise DeliveryPackageBuildError(
            "material_package_source_unauthorized:"
            f"{_safe_filename(category)}:{_safe_filename(key)}:{_safe_filename(role)}"
        ) from exc
    receipt = source_receipts.get(_normalized_path_identity(resolved))
    if receipt is None or receipt.path != resolved:
        raise DeliveryPackageBuildError(
            "material_package_source_unauthorized:"
            f"{_safe_filename(category)}:{_safe_filename(key)}:{_safe_filename(role)}"
        )
    return receipt


def _verify_source_receipt(
    receipt: DeliveryPackageSourceReceipt,
    *,
    error_domain: str,
) -> None:
    try:
        digest, byte_size = _stable_file_fingerprint(
            receipt.path,
            error_domain=error_domain,
        )
    except DeliveryPackageBuildError:
        raise
    if digest != receipt.sha256 or byte_size != receipt.byte_size:
        raise DeliveryPackageBuildError(
            f"{error_domain}_evidence_invalid:{receipt.path}"
        )


def _read_verified_receipt_bytes(
    receipt: DeliveryPackageSourceReceipt,
    *,
    error_domain: str,
) -> bytes:
    resolved = _resolve_non_reparse_regular_file(
        receipt.path,
        error_domain=error_domain,
    )
    try:
        with resolved.open("rb") as stream:
            before = os.fstat(stream.fileno())
            payload = stream.read()
            after = os.fstat(stream.fileno())
        path_after = resolved.stat()
    except OSError as exc:
        raise DeliveryPackageBuildError(
            f"{error_domain}_read_failed:{resolved}"
        ) from exc
    _assert_no_reparse_components(resolved, error_domain=error_domain)
    if (
        _stat_identity(before) != _stat_identity(after)
        or _stat_identity(after) != _stat_identity(path_after)
        or len(payload) != receipt.byte_size
        or sha256(payload).hexdigest() != receipt.sha256
    ):
        raise DeliveryPackageBuildError(
            f"{error_domain}_evidence_invalid:{resolved}"
        )
    return payload


def _copy_verified_receipt(
    receipt: DeliveryPackageSourceReceipt,
    destination: Path,
    *,
    error_domain: str,
) -> None:
    resolved = _resolve_non_reparse_regular_file(
        receipt.path,
        error_domain=error_domain,
    )
    digest = sha256()
    byte_size = 0
    try:
        with resolved.open("rb") as source_stream, destination.open("xb") as target_stream:
            before = os.fstat(source_stream.fileno())
            for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
                target_stream.write(chunk)
                digest.update(chunk)
                byte_size += len(chunk)
            target_stream.flush()
            os.fsync(target_stream.fileno())
            after = os.fstat(source_stream.fileno())
        path_after = resolved.stat()
    except OSError as exc:
        raise DeliveryPackageBuildError(
            f"{error_domain}_copy_failed:{resolved}"
        ) from exc
    _assert_no_reparse_components(resolved, error_domain=error_domain)
    if (
        _stat_identity(before) != _stat_identity(after)
        or _stat_identity(after) != _stat_identity(path_after)
        or digest.hexdigest() != receipt.sha256
        or byte_size != receipt.byte_size
    ):
        raise DeliveryPackageBuildError(
            f"{error_domain}_evidence_invalid:{resolved}"
        )


def _copy_public_diagnostic_file(
    receipt: DeliveryPackageSourceReceipt,
    destination: Path,
) -> None:
    payload = _read_verified_receipt_bytes(
        receipt,
        error_domain="material_package_diagnostic_source",
    )
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise DeliveryPackageBuildError(
            "material_package_diagnostic_text_invalid"
        ) from exc
    if receipt.path.suffix.casefold() == ".json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DeliveryPackageBuildError(
                "material_package_diagnostic_json_invalid"
            ) from exc
        _write_public_json(destination, _public_diagnostic_value(parsed))
        return
    projected_lines = [
        "[local-path-redacted]"
        if _WINDOWS_ABSOLUTE_REFERENCE.search(line)
        or _POSIX_LOCAL_ABSOLUTE_REFERENCE.search(line)
        else line
        for line in text.splitlines()
    ]
    _write_public_text(destination, "\n".join(projected_lines) + "\n")


def _public_diagnostic_value(value: object) -> object:
    if isinstance(value, Mapping):
        projected: dict[str, object] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            if key in {"input", "source", "source_manifest", "reason"}:
                continue
            if _contains_absolute_reference(key):
                key = "local_path_redacted"
            if key in projected:
                raise DeliveryPackageBuildError(
                    "material_package_diagnostic_key_collision"
                )
            projected[key] = _public_diagnostic_value(item)
        return projected
    if isinstance(value, (list, tuple)):
        return [_public_diagnostic_value(item) for item in value]
    if isinstance(value, str) and _contains_absolute_reference(value):
        stripped = value.strip()
        if re.match(r"(?i)^[a-z]:[\\/]", stripped) or stripped.startswith("\\\\"):
            name = PureWindowsPath(stripped).name
        elif stripped.startswith("/"):
            name = PurePosixPath(stripped).name
        else:
            name = ""
        return _safe_filename(name) if name else "[local-path-redacted]"
    return value


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _render_archive_report(
    package_manifest: dict[str, object],
) -> str:
    schema = package_manifest.get("material_schema")
    profile = package_manifest.get("material_profile")
    missing = package_manifest.get("missing")
    summary = package_manifest.get("summary")
    schema = schema if isinstance(schema, Mapping) else {}
    profile = profile if isinstance(profile, Mapping) else {}
    missing = missing if isinstance(missing, Mapping) else {}
    summary = summary if isinstance(summary, Mapping) else {}
    lines = [
        "# 资料交付包归档报告",
        "",
        f"- 状态: {_markdown_scalar(package_manifest.get('status', 'incomplete'))}",
        f"- Schema: {_markdown_scalar(schema.get('schema_id'))} / {_markdown_scalar(schema.get('label'))}",
        f"- 资料档案: {_markdown_scalar(profile.get('profile_name') or profile.get('profile_id'))}",
        f"- 字段: {_public_count(summary.get('filled_field_count'))}/{_public_count(summary.get('field_count'))} 已填写",
        f"- 素材: {_public_count(summary.get('asset_item_count'))} 个文件",
        "",
        "## 缺失项",
        "",
    ]
    missing_rows = [
        *(f"Schema: {_markdown_scalar(item)}" for item in _list(missing.get("schema_ids"))),
        *(f"字段: {_markdown_scalar(item)}" for item in _list(missing.get("field_keys"))),
        *(f"材料: {_markdown_scalar(item)}" for item in _list(missing.get("asset_roles"))),
    ]
    lines.extend(f"- {item}" for item in missing_rows)
    if not missing_rows:
        lines.append("- 无")
    lines.extend(["", "## 包内文件", ""])
    files = _dict_items(package_manifest.get("files"))
    lines.extend(
        f"- [{_markdown_scalar(item.get('category'))}] {_markdown_scalar(item.get('path'))}"
        for item in files
    )
    if not files:
        lines.append("- 无")
    missing_refs = _dict_items(package_manifest.get("missing_references"))
    if missing_refs:
        lines.extend(["", "## 未复制引用", ""])
        lines.extend(
            "- "
            f"[{_markdown_scalar(item.get('category'))}] "
            f"{_markdown_scalar(item.get('key') or item.get('role'))}: "
            f"{_markdown_scalar(item.get('code'))}"
            for item in missing_refs
        )
    lines.append("")
    return "\n".join(lines)


_WINDOWS_ABSOLUTE_REFERENCE = re.compile(
    r"(?i)(?:^|[\s\"'`(=:])(?:[a-z]:[\\/]|\\\\[^\\/\s]+[\\/][^\\/\s]+)"
)
_POSIX_LOCAL_ABSOLUTE_REFERENCE = re.compile(
    r"(?:^|[\s\"'`(=:])/(?:tmp|home|Users|var(?:/tmp)?|private|mnt|media|root|etc|opt|srv|usr/local)(?:/|$)"
)


def _contains_absolute_reference(value: str) -> bool:
    text = str(value or "")
    stripped = text.strip()
    if not stripped:
        return False
    if re.match(r"(?i)^[a-z]:[\\/]", stripped) or stripped.startswith("\\\\"):
        return True
    if stripped.startswith("/"):
        return True
    return bool(
        _WINDOWS_ABSOLUTE_REFERENCE.search(text)
        or _POSIX_LOCAL_ABSOLUTE_REFERENCE.search(text)
    )


def _assert_public_value(value: object, *, location: str) -> None:
    if isinstance(value, str):
        if _contains_absolute_reference(value):
            raise DeliveryPackageBuildError(
                f"material_package_public_path_leak:{location}"
            )
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_public_value(item, location=f"{location}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_public_value(item, location=f"{location}[{index}]")


def _assert_public_text(value: str, *, location: str) -> None:
    if _WINDOWS_ABSOLUTE_REFERENCE.search(value) or _POSIX_LOCAL_ABSOLUTE_REFERENCE.search(
        value
    ):
        raise DeliveryPackageBuildError(
            f"material_package_public_path_leak:{location}"
        )


def _write_public_json(path: Path, payload: object) -> None:
    _assert_public_value(payload, location=path.name)
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    _assert_public_text(serialized, location=path.name)
    atomic_write_text(path, serialized, encoding="utf-8")


def _write_public_text(path: Path, value: str) -> None:
    _assert_public_text(value, location=path.name)
    atomic_write_text(path, value, encoding="utf-8")


def _assert_public_archive_text_files(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if path.suffix.casefold() not in {".json", ".md"}:
            continue
        _assert_no_reparse_components(
            path,
            error_domain="material_package_public_file",
        )
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise DeliveryPackageBuildError(
                "material_package_public_text_invalid:"
                f"{path.relative_to(root).as_posix()}"
            ) from exc
        relative = path.relative_to(root).as_posix()
        if path.suffix.casefold() == ".json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise DeliveryPackageBuildError(
                    f"material_package_public_json_invalid:{relative}"
                ) from exc
            _assert_public_value(payload, location=relative)
        _assert_public_text(text, location=relative)


def _markdown_scalar(value: object) -> str:
    return _text(value).replace("\r", " ").replace("\n", " ")


def _write_zip(
    source_dir: Path,
    destination: Path,
    package_manifest: Mapping[str, object],
) -> None:
    declared_files = _dict_items(package_manifest.get("files"))
    declared: dict[str, tuple[str, int]] = {}
    for item in declared_files:
        relative = _safe_relative_path(_text(item.get("path"))).as_posix()
        digest = _normalized_sha256(item.get("sha256"))
        byte_size = _optional_nonnegative_int(item.get("byte_size"))
        if not digest or byte_size is None or relative in declared:
            raise DeliveryPackageBuildError(
                f"material_package_declared_file_invalid:{relative}"
            )
        declared[relative] = (digest, byte_size)
    controls = {
        _safe_relative_path(_text(path)).as_posix()
        for path in _list(package_manifest.get("control_files"))
    }
    expected_paths = set(declared).union(controls)
    actual_paths: set[str] = set()
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        _assert_no_reparse_components(
            path,
            error_domain="material_package_staging_file",
        )
        actual_paths.add(path.relative_to(source_dir).as_posix())
    if actual_paths != expected_paths:
        raise DeliveryPackageBuildError(
            "material_package_file_closure_mismatch:"
            f"missing={sorted(expected_paths - actual_paths)!r}:"
            f"undeclared={sorted(actual_paths - expected_paths)!r}"
        )
    for relative, (digest, byte_size) in declared.items():
        path = source_dir.joinpath(*PurePosixPath(relative).parts)
        if path.stat().st_size != byte_size or _sha256_file(path) != digest:
            raise DeliveryPackageBuildError(
                f"material_package_declared_file_drift:{relative}"
            )
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(expected_paths):
            archive.write(
                source_dir.joinpath(*PurePosixPath(relative).parts),
                relative,
            )


def _publish_pair(
    *,
    staging_dir: Path,
    final_dir: Path,
    staged_zip: Path,
    final_zip: Path,
    owner: Path,
    transaction_id: str,
) -> None:
    backup_dir = owner / f".{final_dir.name}.{transaction_id}.backup"
    backup_zip = owner / f".{final_zip.name}.{transaction_id}.backup"
    moved_old_dir = False
    moved_old_zip = False
    published_dir = False
    published_zip = False
    try:
        if final_dir.exists():
            os.replace(final_dir, backup_dir)
            moved_old_dir = True
        if final_zip.exists():
            os.replace(final_zip, backup_zip)
            moved_old_zip = True
        os.replace(staging_dir, final_dir)
        published_dir = True
        os.replace(staged_zip, final_zip)
        published_zip = True
    except OSError as exc:
        if published_zip:
            final_zip.unlink(missing_ok=True)
        if published_dir:
            remove_owned_path(final_dir, owner)
        if moved_old_dir and backup_dir.exists():
            os.replace(backup_dir, final_dir)
        if moved_old_zip and backup_zip.exists():
            os.replace(backup_zip, final_zip)
        raise DeliveryPackageBuildError("material_package_publish_failed") from exc
    finally:
        if published_dir and published_zip:
            remove_owned_path(backup_dir, owner)
            backup_zip.unlink(missing_ok=True)


def _safe_optional_relative_path(value: str) -> PurePosixPath | None:
    return None if not value.strip() else _safe_relative_path(value)


def _safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(str(value or "").replace("\\", "/"))
    if path.is_absolute() or not path.name or any(part in {"", ".", ".."} for part in path.parts):
        raise DeliveryPackageBuildError(f"unsafe_package_relative_path:{value}")
    return path


def _safe_relative_dir(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/").strip("/")
    if not text:
        return PurePosixPath("file")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DeliveryPackageBuildError(f"unsafe_package_directory:{value}")
    return PurePosixPath(*(_safe_filename(part) for part in path.parts))


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1_000_000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise DeliveryPackageBuildError("package_filename_collision_limit")


def _safe_filename(value: object) -> str:
    name = _text(value) or "file"
    for char in '<>:"\\|?*/':
        name = name.replace(char, "_")
    return name


def _looks_remote(value: str) -> bool:
    text = value.strip().casefold()
    return "://" in text or text.startswith("urn:")


def _dict_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _list(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _text(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "DeliveryPackageBuildError",
    "DeliveryPackageBuildRequest",
    "DeliveryPackageReceipt",
    "DeliveryPackageSourceReceipt",
    "MaterialDeliveryPackageBuilder",
    "build_material_delivery_package",
    "capture_delivery_package_source_receipt",
]
