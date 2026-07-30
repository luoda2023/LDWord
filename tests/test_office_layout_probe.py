from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.shared.engine import office_layout_probe as probe_module
from src.shared.engine.office_layout_probe import (
    CapabilityOutcome,
    CapabilityReceipt,
    OfficeCapability,
    OfficeLayoutProbeReceipt,
    OfficeProvider,
    OfficeProviderReceipt,
    OfficeProviderSpec,
    ProviderOutcome,
    probe_office_layout,
)


FAKE_SPEC = OfficeProviderSpec(
    provider=OfficeProvider.WORD,
    prog_id="Definitely.Missing.Office.Application",
    process_names=("definitely-missing",),
)


def test_capability_and_probe_receipts_round_trip_json() -> None:
    capabilities = tuple(
        CapabilityReceipt(
            capability=name,
            outcome=CapabilityOutcome.PASSED,
            elapsed_ms=1.25,
            detail="proved",
            evidence=(("value", 7),),
        )
        for name in OfficeCapability
    )
    provider = OfficeProviderReceipt(
        provider=OfficeProvider.WORD,
        prog_id="Word.Application",
        registered=True,
        outcome=ProviderOutcome.QUALIFIED,
        elapsed_ms=20.0,
        application_pid=4321,
        capabilities=capabilities,
    )
    receipt = OfficeLayoutProbeReceipt(
        schema_version=1,
        started_at_utc="2026-07-12T00:00:00+00:00",
        platform="win32",
        python_version="3.12.0",
        timeout_seconds=45.0,
        elapsed_ms=25.0,
        providers=(provider,),
    )

    restored = OfficeLayoutProbeReceipt.from_dict(
        json.loads(json.dumps(receipt.to_dict()))
    )

    assert restored == receipt
    assert restored.exact_layout_ready is True
    assert restored.qualified_providers == (OfficeProvider.WORD,)


def test_unregistered_provider_is_reported_without_starting_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "_registration_status",
        lambda _prog_id: (False, "CLSID absent"),
    )

    def child_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("unregistered provider must not start a child")

    monkeypatch.setattr(probe_module, "_run_provider_child", child_must_not_run)

    receipt = probe_office_layout(
        timeout_seconds=1,
        provider_specs=(FAKE_SPEC,),
    )

    provider = receipt.providers[0]
    assert provider.outcome is ProviderOutcome.UNAVAILABLE
    assert provider.exact_layout_ready is False
    assert provider.capability(OfficeCapability.REGISTRATION).outcome is (
        CapabilityOutcome.UNAVAILABLE
    )
    assert all(
        item.outcome is CapabilityOutcome.NOT_RUN
        for item in provider.capabilities
        if item.capability is not OfficeCapability.REGISTRATION
    )


def test_discovery_only_never_starts_office(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "_registration_status",
        lambda _prog_id: (True, "registered"),
    )

    def child_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("discovery-only mode must not start a child")

    monkeypatch.setattr(probe_module, "_run_provider_child", child_must_not_run)

    receipt = probe_office_layout(
        timeout_seconds=1,
        provider_specs=(FAKE_SPEC,),
        execute_live=False,
    )

    provider = receipt.providers[0]
    assert provider.outcome is ProviderOutcome.DISCOVERED
    assert provider.capability(OfficeCapability.REGISTRATION).passed
    assert provider.exact_layout_ready is False


def test_provider_is_not_qualified_when_one_required_capability_fails() -> None:
    capabilities = tuple(
        CapabilityReceipt(
            capability=name,
            outcome=(
                CapabilityOutcome.FAILED
                if name is OfficeCapability.VERTICAL_POSITION
                else CapabilityOutcome.PASSED
            ),
        )
        for name in OfficeCapability
    )
    provider = OfficeProviderReceipt(
        provider=OfficeProvider.WORD,
        prog_id="Word.Application",
        registered=True,
        outcome=ProviderOutcome.DISQUALIFIED,
        elapsed_ms=1,
        capabilities=capabilities,
    )

    assert provider.exact_layout_ready is False
    assert provider.failed_capabilities == (OfficeCapability.VERTICAL_POSITION,)


def test_timeout_receipt_targets_only_reported_owned_pid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeProcess:
        pid = 8111
        returncode = None
        calls = 0

        def communicate(self, timeout: float) -> tuple[str, str]:
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(["python"], timeout)
            self.returncode = -9
            return "", ""

        def poll(self) -> int | None:
            return self.returncode

    monkeypatch.setattr(
        probe_module,
        "_build_probe_fixture",
        lambda docx, image: (
            docx.write_bytes(b"synthetic"),
            image.write_bytes(b"png"),
        ),
    )
    monkeypatch.setattr(probe_module, "_process_ids_for_names", lambda _names: set())
    monkeypatch.setattr(probe_module.subprocess, "Popen", lambda *_a, **_k: FakeProcess())
    monkeypatch.setattr(probe_module, "_terminate_child_process", lambda _p: None)
    monkeypatch.setattr(probe_module, "_read_owned_pid", lambda _path: 9222)
    cleaned: list[int | None] = []

    def record_cleanup(pid: int | None) -> str:
        cleaned.append(pid)
        return "owned PID stopped"

    monkeypatch.setattr(probe_module, "_ensure_owned_process_stopped", record_cleanup)
    monkeypatch.setattr(probe_module, "_pid_exists", lambda _pid: False)

    receipt = probe_module._run_provider_child(FAKE_SPEC, timeout_seconds=0.01)

    assert receipt.outcome is ProviderOutcome.TIMED_OUT
    assert receipt.application_pid == 9222
    assert cleaned == [9222]
    assert receipt.capability(OfficeCapability.CLEAN_SHUTDOWN).passed


def test_cli_discovery_emits_json_without_requiring_office() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "probe_office_layout.py"),
            "--discover-only",
            "--provider",
            "word",
            "--compact",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["schema_version"] == 1
    assert payload["providers"][0]["provider"] == "word"
