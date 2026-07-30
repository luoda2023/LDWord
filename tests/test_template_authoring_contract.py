from __future__ import annotations

from dataclasses import replace

import pytest

from src.config.template_authoring_contract import (
    TemplateAuthoringBaselineEnvelope,
    TemplateAuthoringContract,
    TemplateAuthoringContractError,
    TemplateAuthoringObservations,
    TemplateAuthoringResultEnvelope,
)


def _contract() -> TemplateAuthoringContract:
    return TemplateAuthoringContract(
        mode_id="thesis",
        profile_id="template_authoring.thesis.v1",
        profile_version=1,
        baseline_template_id="thesis_gbt",
        baseline_sha256="a" * 64,
        prompt_version=3,
        prompt_sha256="b" * 64,
    )


def test_typed_baseline_and_result_envelopes_round_trip() -> None:
    contract = _contract()
    baseline = TemplateAuthoringBaselineEnvelope(
        contract=contract,
        template={"name": "基准"},
    )
    observations = TemplateAuthoringObservations(
        master=("封面属于母版",),
        scene=("处理范围属于方案",),
    )
    result = TemplateAuthoringResultEnvelope(
        contract=contract,
        template={"name": "校级论文模板"},
        observations=observations,
    )

    assert TemplateAuthoringBaselineEnvelope.from_payload(
        baseline.to_payload()
    ) == baseline
    assert TemplateAuthoringResultEnvelope.from_payload(result.to_payload()) == result


def test_contract_fingerprint_changes_with_mode_or_prompt() -> None:
    contract = _contract()

    assert replace(contract, mode_id="official").fingerprint != contract.fingerprint
    assert replace(contract, prompt_sha256="c" * 64).fingerprint != contract.fingerprint


def test_result_rejects_unknown_fields_and_bad_fingerprint() -> None:
    result = TemplateAuthoringResultEnvelope(
        contract=_contract(),
        template={"name": "模板"},
        observations=TemplateAuthoringObservations(),
    ).to_payload()
    result["unexpected"] = True

    with pytest.raises(TemplateAuthoringContractError, match="不支持"):
        TemplateAuthoringResultEnvelope.from_payload(result)

    result.pop("unexpected")
    result["contract_fingerprint"] = "0" * 64
    with pytest.raises(TemplateAuthoringContractError, match="指纹"):
        TemplateAuthoringResultEnvelope.from_payload(result)


def test_observations_are_typed_and_trimmed() -> None:
    observations = TemplateAuthoringObservations.from_payload(
        {
            "master": [" 固定封面 "],
            "scene": [],
            "material": ["学生姓名"],
            "unsupported": ["  "],
        }
    )

    assert observations.master == ("固定封面",)
    assert observations.material == ("学生姓名",)
    assert observations.unsupported == ()
