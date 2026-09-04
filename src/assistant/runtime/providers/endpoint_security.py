"""Transport security policy for credential-bearing provider endpoints."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def validate_provider_endpoint(value: str, *, allow_path_query: bool = False) -> str:
    """Return a validated endpoint or raise before any credential is attached."""

    endpoint = str(value or "").strip()
    parsed = urlparse(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or (parsed.query and not allow_path_query)
    ):
        raise ValueError(
            "Provider endpoint must be HTTP(S) without embedded credentials, "
            "query, or fragment"
        )
    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        raise ValueError(
            "Provider HTTP endpoints are allowed only for localhost or loopback IPs"
        )
    return endpoint


def provider_origin(value: str) -> tuple[str, str, int]:
    """Return the normalized origin after enforcing the provider endpoint policy."""

    endpoint = validate_provider_endpoint(value, allow_path_query=True)
    parsed = urlparse(endpoint)
    default_port = 443 if parsed.scheme == "https" else 80
    try:
        port = parsed.port or default_port
    except ValueError as exc:
        raise ValueError("Provider endpoint contains an invalid port") from exc
    return parsed.scheme.casefold(), str(parsed.hostname).casefold(), port


def _is_loopback_host(hostname: str) -> bool:
    normalized = str(hostname or "").strip().rstrip(".").casefold()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


__all__ = ["provider_origin", "validate_provider_endpoint"]
