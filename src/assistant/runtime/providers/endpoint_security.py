"""Transport security policy for credential-bearing provider endpoints."""

from __future__ import annotations

import ipaddress
import os
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
    if parsed.scheme == "http" and not _http_allowed_host(parsed.hostname):
        raise ValueError(
            "Provider HTTP endpoints are allowed only for loopback, private "
            "intranet hosts, or hosts listed in " + _HTTP_ALLOWLIST_ENV
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


_ALLOW_HTTP_HOSTS_ENV = "LDWORD_FORM_ALLOW_HTTP_HOSTS"
_HTTP_ALLOWLIST_ENV = "LDWORD_FORM_ALLOW_HTTP"


def _is_loopback_host(hostname: str) -> bool:
    normalized = str(hostname or "").strip().rstrip(".").casefold()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_private_intranet_host(hostname: str) -> bool:
    """True for RFC1918 / link-local / CGNAT / unique-local addresses."""
    normalized = str(hostname or "").strip().rstrip(".").casefold()
    if normalized == "localhost":
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_global
        and int(address) in _CGNAT_RANGE
    )


_CGNAT_RANGE = range(int(ipaddress.ip_address("100.64.0.0")), int(ipaddress.ip_address("100.127.255.255")) + 1)


def _allowlist_http_hosts() -> set[str]:
    """Return explicitly trusted HTTP hostnames from the environment."""
    raw = str(os.environ.get(_HTTP_ALLOWLIST_ENV, "") or "").strip()
    allowed: set[str] = set()
    for item in raw.replace(";", ",").split(","):
        host = str(item or "").strip().rstrip(".").casefold()
        if host:
            allowed.add(host)
    return allowed


def _http_allowed_host(hostname: str) -> bool:
    if _is_loopback_host(hostname) or _is_private_intranet_host(hostname):
        return True
    return str(hostname or "").strip().rstrip(".").casefold() in _allowlist_http_hosts()


__all__ = ["provider_origin", "validate_provider_endpoint"]
