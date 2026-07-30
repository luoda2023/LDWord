from __future__ import annotations

from dataclasses import fields
import hashlib
import json
from pathlib import Path

import pytest

from src.config import library
from src.config.builtin_templates import create_builtin_template, list_builtin_template_ids
from src.config.loader import load_template
from src.config.template import TemplateConfig
from src.config.template_authoring_profile import (
    TEMPLATE_AUTHORABLE_ROOTS,
    TEMPLATE_FROZEN_ROOTS,
    get_template_authoring_profile,
    get_template_authoring_profile_by_id,
    list_template_authoring_profiles,
)
from src.config.template_authoring_workspace import (
    AUTHORING_BASELINE_KIND,
    AUTHORING_RESULT_KIND,
    AUTHORING_SCHEMA_VERSION,
    ensure_template_authoring_workspace,
    process_template_import_inbox,
)
from src.config.work_mode import list_template_authoring_work_modes


@pytest.fixture
def isolated_authoring_library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    config_root = tmp_path / "config_library"
    monkeypatch.setattr(library, "TEMPLATE_LIBRARY_DIR", config_root / "templates")
    monkeypatch.setattr(library, "SCENE_LIBRARY_DIR", config_root / "plans")
    return config_root


def _read_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_from_baseline(path: Path, *, name: str = "校级论文模板") -> dict:
    baseline = _read_payload(path)
    result = dict(baseline)
    result["kind"] = AUTHORING_RESULT_KIND
    result["template"] = dict(baseline["template"])
    result["template"]["name"] = name
    result["template"]["description"] = "由来源 Word 范例确认的排版模板。"
    result["observations"] = {
        "master": ["固定封面属于论文母版。"],
        "scene": ["引用处理策略属于论文方案。"],
        "material": ["学生姓名属于逐篇资料。"],
        "unsupported": [],
    }
    return result


def test_profiles_are_resolved_from_optional_mode_bindings() -> None:
    modes = list_template_authoring_work_modes()
    profiles = list_template_authoring_profiles()

    assert modes
    assert len({profile.profile_id for profile in profiles}) == len(profiles)
    for mode in modes:
        profile_id = mode.template_authoring_profile_id
        assert profile_id
        assert get_template_authoring_profile_by_id(profile_id) is not None
        assert get_template_authoring_profile(mode.mode_id).profile_id == profile_id


def test_authoring_profile_lookup_supports_profile_ids_and_mode_aliases() -> None:
    thesis = get_template_authoring_profile("thesis")
    assert thesis is not None
    assert thesis.profile_id == "template_authoring.thesis.v1"
    assert get_template_authoring_profile("论文") == thesis
    assert get_template_authoring_profile(thesis.profile_id) == thesis
    assert get_template_authoring_profile("") is None
    assert get_template_authoring_profile("unknown-mode") is None


def test_authorable_and_frozen_roots_partition_template_config_contract() -> None:
    assert set(TEMPLATE_AUTHORABLE_ROOTS).isdisjoint(TEMPLATE_FROZEN_ROOTS)
    persisted_roots = {
        field.name
        for field in fields(TemplateConfig)
        if field.name not in {"name", "description"}
    }
    assert set(TEMPLATE_AUTHORABLE_ROOTS) | set(TEMPLATE_FROZEN_ROOTS) == persisted_roots
    for profile in list_template_authoring_profiles():
        assert profile.authorable_roots == TEMPLATE_AUTHORABLE_ROOTS
        assert profile.frozen_roots == TEMPLATE_FROZEN_ROOTS


def test_mode_default_templates_satisfy_bound_profile_style_contracts() -> None:
    builtin_ids = set(list_builtin_template_ids())
    for mode in list_template_authoring_work_modes():
        assert mode.default_template_id in builtin_ids
        profile = get_template_authoring_profile(mode.mode_id)
        assert profile is not None
        template = create_builtin_template(mode.default_template_id)
        missing = set(profile.required_style_roles) - set(template.styles)
        assert not missing, f"{mode.mode_id}: {sorted(missing)}"


def test_profiles_record_non_template_boundaries() -> None:
    for profile in list_template_authoring_profiles():
        assert all(text.strip() for text in profile.master_boundaries)
        assert all(text.strip() for text in profile.scene_boundaries)
        assert all(text.strip() for text in profile.material_boundaries)
    assert "default_exam" in " ".join(
        get_template_authoring_profile("exam").master_boundaries
    )
    assert "official_document_v1" in " ".join(
        get_template_authoring_profile("official").material_boundaries
    )


def test_workspace_baseline_and_prompt_are_driven_by_mode_binding(
    isolated_authoring_library: Path,
) -> None:
    workspace = ensure_template_authoring_workspace("official")
    mode = next(
        mode for mode in list_template_authoring_work_modes() if mode.mode_id == "official"
    )
    profile = get_template_authoring_profile("official")
    assert profile is not None

    baseline = _read_payload(workspace.baseline_path)
    assert baseline["kind"] == AUTHORING_BASELINE_KIND
    assert baseline["schema_version"] == AUTHORING_SCHEMA_VERSION
    assert baseline["mode_id"] == mode.mode_id
    assert baseline["profile_id"] == mode.template_authoring_profile_id
    assert baseline["profile_version"] == profile.version
    assert baseline["baseline_template_id"] == mode.default_template_id
    canonical_template = json.dumps(
        baseline["template"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert baseline["baseline_sha256"] == hashlib.sha256(
        canonical_template.encode("utf-8")
    ).hexdigest()
    prompt = workspace.prompt_path.read_text(encoding="utf-8")
    assert profile.profile_id in prompt
    assert "official_gbt_standard" in prompt
    assert "official_document_v1" in prompt


def test_enveloped_result_imports_and_delivers_boundary_observations(
    isolated_authoring_library: Path,
) -> None:
    workspace = ensure_template_authoring_workspace("thesis")
    result = _result_from_baseline(workspace.baseline_path)
    result["template"]["page_setup"]["margin"]["left_cm"] = 3.1
    source = workspace.inbox_path / "ai-template-result.json"
    source.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    batch = process_template_import_inbox("thesis", settle_seconds=0)

    assert len(batch.successes) == 1
    assert not batch.rejections
    imported = load_template(batch.successes[0].entry.path)
    assert imported.page_setup.margin.left_cm == 3.1
    record = next(workspace.success_dir.glob("*.md")).read_text(encoding="utf-8")
    assert "固定封面属于论文母版" in record
    assert "引用处理策略属于论文方案" in record
    assert "学生姓名属于逐篇资料" in record
    assert result["contract_fingerprint"] in record


@pytest.mark.parametrize(
    "case",
    ("cross_mode", "bad_fingerprint", "changed_frozen", "missing_nested", "wrong_type"),
)
def test_enveloped_result_rejects_contract_and_template_violations(
    isolated_authoring_library: Path,
    case: str,
) -> None:
    workspace = ensure_template_authoring_workspace("thesis")
    result = _result_from_baseline(workspace.baseline_path)
    if case == "cross_mode":
        result["mode_id"] = "exam"
    elif case == "bad_fingerprint":
        result["contract_fingerprint"] = "0" * 64
    elif case == "changed_frozen":
        result["template"]["watermark"]["enabled"] = True
    elif case == "missing_nested":
        del result["template"]["page_setup"]["margin"]["left_cm"]
    else:
        result["template"]["page_setup"]["margin"]["left_cm"] = "3.1"
    source = workspace.inbox_path / f"{case}.json"
    source.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    batch = process_template_import_inbox("thesis", settle_seconds=0)

    assert not batch.successes
    assert len(batch.rejections) == 1
    assert not list(library.template_user_dir("thesis").glob("*.json"))
