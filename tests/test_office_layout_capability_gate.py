from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.shared.engine.office_image_layout import OfficeImageProvider
from src.shared.engine.office_layout_capability_gate import (
    OfficeLayoutCapabilityUnavailable,
    resolve_office_layout_capability,
)
from src.shared.engine.office_layout_probe import (
    CapabilityOutcome,
    CapabilityReceipt,
    OfficeCapability,
    OfficeLayoutProbeReceipt,
    OfficeProvider,
    OfficeProviderReceipt,
    ProviderOutcome,
)


NOW = datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc)


def _receipt(*qualified: OfficeProvider) -> OfficeLayoutProbeReceipt:
    providers = []
    for provider in (OfficeProvider.WORD, OfficeProvider.WPS):
        is_qualified = provider in qualified
        providers.append(
            OfficeProviderReceipt(
                provider=provider,
                prog_id=(
                    "Word.Application"
                    if provider is OfficeProvider.WORD
                    else "KWPS.Application"
                ),
                registered=is_qualified,
                outcome=(
                    ProviderOutcome.QUALIFIED
                    if is_qualified
                    else ProviderOutcome.UNAVAILABLE
                ),
                elapsed_ms=1.0,
                capabilities=tuple(
                    CapabilityReceipt(
                        capability=name,
                        outcome=(
                            CapabilityOutcome.PASSED
                            if is_qualified
                            else CapabilityOutcome.NOT_RUN
                        ),
                    )
                    for name in OfficeCapability
                ),
                issues=() if is_qualified else ("unavailable",),
            )
        )
    return OfficeLayoutProbeReceipt(
        schema_version=1,
        started_at_utc=NOW.isoformat(),
        platform="test",
        python_version="test",
        timeout_seconds=1,
        elapsed_ms=2,
        providers=tuple(providers),
    )


def _fingerprint(spec):
    return {"provider": spec.provider.value, "install": "same"}


def test_gate_probes_once_then_reuses_installation_bound_cache(tmp_path):
    calls = []

    def probe(**kwargs):
        calls.append(kwargs)
        return _receipt(OfficeProvider.WORD)

    cache = tmp_path / "office-capability.json"
    first = resolve_office_layout_capability(
        cache,
        probe_runner=probe,
        fingerprint_resolver=_fingerprint,
        now_utc=NOW,
    )
    second = resolve_office_layout_capability(
        cache,
        probe_runner=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("fresh cache must avoid a live probe")
        ),
        fingerprint_resolver=_fingerprint,
        now_utc=NOW,
    )

    assert len(calls) == 1
    assert first.provider is OfficeImageProvider.WORD
    assert first.cache_hit is False
    assert second.provider is OfficeImageProvider.WORD
    assert second.cache_hit is True
    assert first.cache_identity == second.cache_identity


def test_gate_reprobes_when_office_installation_identity_changes(tmp_path):
    cache = tmp_path / "office-capability.json"
    resolve_office_layout_capability(
        cache,
        probe_runner=lambda **_kwargs: _receipt(OfficeProvider.WORD),
        fingerprint_resolver=_fingerprint,
        now_utc=NOW,
    )
    calls = []
    decision = resolve_office_layout_capability(
        cache,
        probe_runner=lambda **kwargs: calls.append(kwargs)
        or _receipt(OfficeProvider.WPS),
        fingerprint_resolver=lambda spec: {
            "provider": spec.provider.value,
            "install": "changed",
        },
        now_utc=NOW,
    )

    assert len(calls) == 1
    assert decision.cache_hit is False
    assert decision.provider is OfficeImageProvider.WPS


def test_gate_honors_preference_and_blocks_without_qualified_provider(tmp_path):
    both = resolve_office_layout_capability(
        tmp_path / "both.json",
        preferred_providers=(OfficeImageProvider.WPS, OfficeImageProvider.WORD),
        probe_runner=lambda **_kwargs: _receipt(
            OfficeProvider.WORD,
            OfficeProvider.WPS,
        ),
        fingerprint_resolver=_fingerprint,
        now_utc=NOW,
    )
    assert both.provider is OfficeImageProvider.WPS

    with pytest.raises(OfficeLayoutCapabilityUnavailable, match="unavailable"):
        resolve_office_layout_capability(
            tmp_path / "none.json",
            probe_runner=lambda **_kwargs: _receipt(),
            fingerprint_resolver=_fingerprint,
            now_utc=NOW,
        )
