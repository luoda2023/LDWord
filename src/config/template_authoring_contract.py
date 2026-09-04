"""Typed contracts for AI-assisted template authoring envelopes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


AUTHORING_BASELINE_KIND = "alavette.template_authoring.baseline"
AUTHORING_RESULT_KIND = "alavette.template_authoring.result"
AUTHORING_SCHEMA_VERSION = 1
AUTHORING_PROMPT_VERSION = 5

CONTRACT_FIELD_NAMES: tuple[str, ...] = (
    "mode_id",
    "profile_id",
    "profile_version",
    "baseline_template_id",
    "baseline_sha256",
    "prompt_version",
    "prompt_sha256",
)
OBSERVATION_FIELD_NAMES: tuple[str, ...] = (
    "master",
    "scene",
    "material",
    "unsupported",
)


class TemplateAuthoringContractError(ValueError):
    """An authoring envelope violates its typed contract."""


@dataclass(frozen=True, slots=True)
class TemplateAuthoringContract:
    mode_id: str
    profile_id: str
    profile_version: int
    baseline_template_id: str
    baseline_sha256: str
    prompt_version: int
    prompt_sha256: str

    def to_payload(self) -> dict[str, object]:
        return {
            "mode_id": self.mode_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "baseline_template_id": self.baseline_template_id,
            "baseline_sha256": self.baseline_sha256,
            "prompt_version": self.prompt_version,
            "prompt_sha256": self.prompt_sha256,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_json_sha256(self.to_payload())

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        context: str,
    ) -> "TemplateAuthoringContract":
        values: dict[str, object] = {}
        for name in CONTRACT_FIELD_NAMES:
            if name not in payload:
                raise TemplateAuthoringContractError(
                    f"{context}缺少合同字段：{name}"
                )
            values[name] = payload[name]

        for name in (
            "mode_id",
            "profile_id",
            "baseline_template_id",
            "baseline_sha256",
            "prompt_sha256",
        ):
            value = values[name]
            if not isinstance(value, str) or not value.strip():
                raise TemplateAuthoringContractError(
                    f"{context}{name} 必须是非空文本"
                )
        for name in ("profile_version", "prompt_version"):
            if type(values[name]) is not int:
                raise TemplateAuthoringContractError(
                    f"{context}{name} 必须是整数"
                )
        return cls(
            mode_id=str(values["mode_id"]),
            profile_id=str(values["profile_id"]),
            profile_version=int(values["profile_version"]),
            baseline_template_id=str(values["baseline_template_id"]),
            baseline_sha256=str(values["baseline_sha256"]),
            prompt_version=int(values["prompt_version"]),
            prompt_sha256=str(values["prompt_sha256"]),
        )


@dataclass(frozen=True, slots=True)
class TemplateAuthoringObservations:
    master: tuple[str, ...] = ()
    scene: tuple[str, ...] = ()
    material: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, list[str]]:
        return {
            name: list(getattr(self, name))
            for name in OBSERVATION_FIELD_NAMES
        }

    @classmethod
    def from_payload(
        cls,
        payload: object,
    ) -> "TemplateAuthoringObservations":
        if not isinstance(payload, Mapping):
            raise TemplateAuthoringContractError(
                "创作结果 observations 必须是对象"
            )
        keys = {str(key) for key in payload}
        expected = set(OBSERVATION_FIELD_NAMES)
        if keys != expected:
            raise TemplateAuthoringContractError(
                "observations 必须且只能包含 master、scene、material、unsupported"
            )
        values: dict[str, tuple[str, ...]] = {}
        for name in OBSERVATION_FIELD_NAMES:
            raw_values = payload.get(name)
            if not isinstance(raw_values, list) or any(
                not isinstance(value, str) for value in raw_values
            ):
                raise TemplateAuthoringContractError(
                    f"observations.{name} 必须是文本数组"
                )
            values[name] = tuple(value.strip() for value in raw_values if value.strip())
        return cls(**values)

    @property
    def is_empty(self) -> bool:
        return not any(getattr(self, name) for name in OBSERVATION_FIELD_NAMES)


@dataclass(frozen=True, slots=True)
class TemplateAuthoringBaselineEnvelope:
    contract: TemplateAuthoringContract
    template: Mapping[str, Any]

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": AUTHORING_BASELINE_KIND,
            "schema_version": AUTHORING_SCHEMA_VERSION,
            **self.contract.to_payload(),
            "contract_fingerprint": self.contract.fingerprint,
            "template": dict(self.template),
        }

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "TemplateAuthoringBaselineEnvelope":
        _validate_envelope_keys(payload, result=False)
        _validate_envelope_header(payload, AUTHORING_BASELINE_KIND, "模板生成基准")
        contract = TemplateAuthoringContract.from_payload(
            payload,
            context="模板生成基准 ",
        )
        _validate_fingerprint(payload, contract, "模板生成基准")
        template = payload.get("template")
        if not isinstance(template, Mapping):
            raise TemplateAuthoringContractError(
                "模板生成基准 template 必须是对象"
            )
        return cls(contract=contract, template=dict(template))


@dataclass(frozen=True, slots=True)
class TemplateAuthoringResultEnvelope:
    contract: TemplateAuthoringContract
    template: Mapping[str, Any]
    observations: TemplateAuthoringObservations

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": AUTHORING_RESULT_KIND,
            "schema_version": AUTHORING_SCHEMA_VERSION,
            **self.contract.to_payload(),
            "contract_fingerprint": self.contract.fingerprint,
            "template": dict(self.template),
            "observations": self.observations.to_payload(),
        }

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "TemplateAuthoringResultEnvelope":
        _validate_envelope_keys(payload, result=True)
        _validate_envelope_header(payload, AUTHORING_RESULT_KIND, "创作结果")
        contract = TemplateAuthoringContract.from_payload(
            payload,
            context="创作结果 ",
        )
        _validate_fingerprint(payload, contract, "创作结果")
        template = payload.get("template")
        if not isinstance(template, Mapping):
            raise TemplateAuthoringContractError("创作结果 template 必须是对象")
        return cls(
            contract=contract,
            template=dict(template),
            observations=TemplateAuthoringObservations.from_payload(
                payload.get("observations")
            ),
        )


def canonical_json_sha256(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_json_object_without_duplicate_keys,
            parse_constant=_reject_non_finite_json_number,
        )
    except json.JSONDecodeError as exc:
        raise TemplateAuthoringContractError(
            f"JSON 语法错误（第 {exc.lineno} 行，第 {exc.colno} 列）：{exc.msg}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise TemplateAuthoringContractError(
            "JSON 根节点必须是对象，不能是数组或其他值"
        )
    return dict(raw)


def _validate_envelope_keys(
    payload: Mapping[str, Any],
    *,
    result: bool,
) -> None:
    expected = {
        "kind",
        "schema_version",
        *CONTRACT_FIELD_NAMES,
        "contract_fingerprint",
        "template",
    }
    if result:
        expected.add("observations")
    keys = {str(key) for key in payload}
    missing = sorted(expected - keys)
    unknown = sorted(keys - expected)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append("缺少：" + "、".join(missing))
        if unknown:
            details.append("不支持：" + "、".join(unknown))
        label = "创作结果" if result else "模板生成基准"
        raise TemplateAuthoringContractError(
            f"{label} envelope 结构不完整（{'；'.join(details)}）"
        )


def _validate_envelope_header(
    payload: Mapping[str, Any],
    expected_kind: str,
    label: str,
) -> None:
    if payload.get("kind") != expected_kind:
        raise TemplateAuthoringContractError(
            f"{label} kind 不受支持：{payload.get('kind')}"
        )
    if payload.get("schema_version") != AUTHORING_SCHEMA_VERSION:
        raise TemplateAuthoringContractError(
            f"{label} schema_version 不受支持"
        )


def _validate_fingerprint(
    payload: Mapping[str, Any],
    contract: TemplateAuthoringContract,
    label: str,
) -> None:
    fingerprint = payload.get("contract_fingerprint")
    if not isinstance(fingerprint, str) or fingerprint != contract.fingerprint:
        raise TemplateAuthoringContractError(f"{label}合同指纹校验失败")


def _json_object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TemplateAuthoringContractError(f"JSON 存在重复字段：{key}")
        result[key] = value
    return result


def _reject_non_finite_json_number(value: str) -> None:
    raise TemplateAuthoringContractError(f"JSON 不允许使用非有限数值：{value}")


__all__ = [
    "AUTHORING_BASELINE_KIND",
    "AUTHORING_PROMPT_VERSION",
    "AUTHORING_RESULT_KIND",
    "AUTHORING_SCHEMA_VERSION",
    "CONTRACT_FIELD_NAMES",
    "OBSERVATION_FIELD_NAMES",
    "TemplateAuthoringBaselineEnvelope",
    "TemplateAuthoringContract",
    "TemplateAuthoringContractError",
    "TemplateAuthoringObservations",
    "TemplateAuthoringResultEnvelope",
    "canonical_json_sha256",
    "read_json_object",
]
