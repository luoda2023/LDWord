"""Cached production gate for exact Word/WPS image-layout capability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
from typing import Callable, Mapping, Sequence

from src.shared.engine.office_image_layout_contracts import (
    LAYOUT_SCHEMA_VERSION,
    OfficeImageProvider,
)
from src.shared.engine.office_layout_probe import (
    DEFAULT_PROVIDER_SPECS,
    PROBE_SCHEMA_VERSION,
    OfficeLayoutProbeReceipt,
    OfficeProviderSpec,
    probe_office_layout,
)


CAPABILITY_GATE_CONTRACT_VERSION = 1
DEFAULT_CAPABILITY_CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


class OfficeLayoutCapabilityUnavailable(RuntimeError):
    """Raised when no exact-layout provider passed the production gate."""


@dataclass(frozen=True, slots=True)
class OfficeLayoutCapabilityDecision:
    provider: OfficeImageProvider
    probe_receipt: OfficeLayoutProbeReceipt
    cache_hit: bool
    cache_identity: str
    cache_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider.value,
            "cache_hit": self.cache_hit,
            "cache_identity": self.cache_identity,
            "cache_path": self.cache_path,
            "probe": self.probe_receipt.to_dict(),
        }


ProbeRunner = Callable[..., OfficeLayoutProbeReceipt]
FingerprintResolver = Callable[[OfficeProviderSpec], Mapping[str, object]]


def resolve_office_layout_capability(
    cache_path: str | Path,
    *,
    preferred_providers: Sequence[OfficeImageProvider | str] = (
        OfficeImageProvider.WORD,
        OfficeImageProvider.WPS,
    ),
    provider_specs: Sequence[OfficeProviderSpec] = DEFAULT_PROVIDER_SPECS,
    timeout_seconds: float = 45.0,
    max_age_seconds: float = DEFAULT_CAPABILITY_CACHE_MAX_AGE_SECONDS,
    force_probe: bool = False,
    probe_runner: ProbeRunner = probe_office_layout,
    fingerprint_resolver: FingerprintResolver | None = None,
    now_utc: datetime | None = None,
) -> OfficeLayoutCapabilityDecision:
    """Return a qualified provider, probing only when bound cache evidence is stale."""

    path = Path(cache_path)
    now = now_utc or datetime.now(timezone.utc)
    resolver = fingerprint_resolver or _provider_installation_evidence
    identity_payload = {
        "gate_contract": CAPABILITY_GATE_CONTRACT_VERSION,
        "probe_schema": PROBE_SCHEMA_VERSION,
        "layout_schema": LAYOUT_SCHEMA_VERSION,
        "platform": platform.platform(),
        "python_architecture": platform.architecture()[0],
        "providers": [dict(resolver(spec)) for spec in provider_specs],
    }
    cache_identity = _stable_sha256(identity_payload)

    receipt: OfficeLayoutProbeReceipt | None = None
    cache_hit = False
    if not force_probe:
        receipt = _load_cached_receipt(
            path,
            expected_identity=cache_identity,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        cache_hit = receipt is not None
    if receipt is None:
        receipt = probe_runner(
            timeout_seconds=timeout_seconds,
            provider_specs=provider_specs,
            execute_live=True,
        )
        _write_cache(path, cache_identity=cache_identity, receipt=receipt, now=now)

    provider = _select_provider(receipt, preferred_providers)
    if provider is None:
        issues = [
            issue
            for item in receipt.providers
            for issue in item.issues
            if str(issue or "").strip()
        ]
        detail = "; ".join(issues) or "Word/WPS exact layout capability is unavailable"
        raise OfficeLayoutCapabilityUnavailable(detail)
    return OfficeLayoutCapabilityDecision(
        provider=provider,
        probe_receipt=receipt,
        cache_hit=cache_hit,
        cache_identity=cache_identity,
        cache_path=str(path),
    )


def _select_provider(
    receipt: OfficeLayoutProbeReceipt,
    preferred: Sequence[OfficeImageProvider | str],
) -> OfficeImageProvider | None:
    qualified = {item.value for item in receipt.qualified_providers}
    for raw in preferred:
        provider = OfficeImageProvider(str(getattr(raw, "value", raw)))
        if provider.value in qualified:
            return provider
    return None


def _load_cached_receipt(
    path: Path,
    *,
    expected_identity: str,
    now: datetime,
    max_age_seconds: float,
) -> OfficeLayoutProbeReceipt | None:
    if max_age_seconds <= 0 or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if int(payload.get("contract_version", 0)) != CAPABILITY_GATE_CONTRACT_VERSION:
            return None
        if str(payload.get("cache_identity", "")) != expected_identity:
            return None
        created = datetime.fromisoformat(str(payload["created_at_utc"]))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = (now - created.astimezone(timezone.utc)).total_seconds()
        if age < 0 or age > max_age_seconds:
            return None
        return OfficeLayoutProbeReceipt.from_dict(payload["probe"])
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return None


def _write_cache(
    path: Path,
    *,
    cache_identity: str,
    receipt: OfficeLayoutProbeReceipt,
    now: datetime,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_version": CAPABILITY_GATE_CONTRACT_VERSION,
        "created_at_utc": now.astimezone(timezone.utc).isoformat(),
        "cache_identity": cache_identity,
        "probe": receipt.to_dict(),
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _provider_installation_evidence(spec: OfficeProviderSpec) -> Mapping[str, object]:
    evidence: dict[str, object] = {
        "provider": spec.provider.value,
        "prog_id": spec.prog_id,
        "registered": False,
        "clsid": "",
        "server": "",
        "server_size": 0,
        "server_mtime_ns": 0,
        "server_version": "",
    }
    if os.name != "nt":
        return evidence
    try:
        import winreg
    except ImportError:
        return evidence
    access_modes = (0, winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    for access in access_modes:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                rf"{spec.prog_id}\CLSID",
                0,
                winreg.KEY_READ | access,
            ) as key:
                clsid, _kind = winreg.QueryValueEx(key, None)
            clsid = str(clsid or "").strip()
            if not clsid:
                continue
            evidence["registered"] = True
            evidence["clsid"] = clsid
            server = _registered_local_server(winreg, clsid, access)
            evidence["server"] = server
            executable = _server_executable_path(server)
            if executable.is_file():
                stat = executable.stat()
                evidence["server_size"] = stat.st_size
                evidence["server_mtime_ns"] = stat.st_mtime_ns
                evidence["server_version"] = _windows_file_version(executable)
            return evidence
        except OSError:
            continue
    return evidence


def _registered_local_server(winreg, clsid: str, access: int) -> str:
    for suffix in ("LocalServer32", "InprocServer32"):
        try:
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                rf"CLSID\{clsid}\{suffix}",
                0,
                winreg.KEY_READ | access,
            ) as key:
                value, _kind = winreg.QueryValueEx(key, None)
            if str(value or "").strip():
                return str(value).strip()
        except OSError:
            continue
    return ""


def _server_executable_path(command: str) -> Path:
    text = os.path.expandvars(str(command or "").strip())
    if not text:
        return Path()
    match = re.match(r'^"([^"]+)"|^([^\s]+)', text)
    candidate = (match.group(1) or match.group(2)) if match else text
    return Path(candidate)


def _windows_file_version(path: Path) -> str:
    try:
        import win32api

        info = win32api.GetFileVersionInfo(str(path), "\\")
        ms = int(info["FileVersionMS"])
        ls = int(info["FileVersionLS"])
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    except Exception:
        return ""


def _stable_sha256(payload: object) -> str:
    return sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "CAPABILITY_GATE_CONTRACT_VERSION",
    "DEFAULT_CAPABILITY_CACHE_MAX_AGE_SECONDS",
    "OfficeLayoutCapabilityDecision",
    "OfficeLayoutCapabilityUnavailable",
    "resolve_office_layout_capability",
]
