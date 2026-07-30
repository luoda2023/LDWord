"""Pure projection for the official-document plan preview surface."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.master_preflight import check_master_preflight
from src.config.official_document_profiles import get_official_document_profile
from src.ui.adapters.config_selector_models import master_display_label
from src.ui.panels.scene_delivery_helpers import _template_label_with_id


@dataclass(frozen=True, slots=True)
class OfficialPlanPreviewProjection:
    header_text: str
    material_status_text: str
    contract_text: str
    sample_enabled: bool
    open_master_enabled: bool
    request_word_preview: bool


def _field_list(fields) -> str:
    values = [
        str(field or "").strip() for field in fields or () if str(field or "").strip()
    ]
    return "、".join(values)


def _required_fields(contract) -> tuple[str, ...]:
    if contract is None:
        return ()
    return tuple(
        dict.fromkeys(
            binding.field_key for binding in contract.field_bindings if binding.required
        )
    )


def build_official_plan_preview_projection(
    *,
    profile_id: str,
    master,
    contract,
    material_context,
    current_template_id: str,
) -> OfficialPlanPreviewProjection:
    """Project labels and actions without mutating widgets or runtime state."""

    profile = get_official_document_profile(profile_id)
    template_id = (
        str(getattr(master, "template_config_id", "") or "").strip()
        or str(current_template_id or "").strip()
        or "official_gbt"
    )
    template_label = (
        _template_label_with_id(template_id, mode_id="official") or template_id
    )
    master_label = master_display_label(master) if master is not None else "未登记版式"
    profile_label = str(getattr(profile, "label", "") or profile_id)
    header_text = (
        f"当前文种：{profile_label}　·　关联版式：{master_label}　·　"
        f"格式模板：{template_label}"
    )

    entity_data = dict(getattr(material_context, "entity_data", {}) or {})
    missing_fields = [
        field_id
        for field_id in _required_fields(contract)
        if not str(entity_data.get(field_id, "") or "").strip()
    ]
    if entity_data:
        material_status = f"资料包：已填 {len(entity_data)} 项"
        if missing_fields:
            material_status += f"；缺少必填字段 {_field_list(missing_fields)}"
        else:
            material_status += "；必填字段已齐"
    else:
        material_status = (
            "资料状态：尚未填写；预览使用结构占位内容，实际内容请到资料包填写。"
        )

    if master is None:
        return OfficialPlanPreviewProjection(
            header_text=header_text,
            material_status_text=material_status,
            contract_text="版式：未登记公文版式。",
            sample_enabled=False,
            open_master_enabled=False,
            request_word_preview=False,
        )

    preflight = check_master_preflight(master)
    preflight_text = (
        "通过"
        if preflight.status == "ok"
        else (
            f"{preflight.status}，缺少 "
            f"{_field_list(preflight.missing_required_placeholders)}"
        )
    )
    schema_text = "、".join(contract.material_schema_ids) if contract else "未登记"
    placeholder_text = "、".join(contract.placeholder_ids[:8]) if contract else "未登记"
    if contract and len(contract.placeholder_ids) > 8:
        placeholder_text += f" 等 {len(contract.placeholder_ids)} 项"
    delivery_text = "、".join(contract.delivery_versions) if contract else "未登记"
    return OfficialPlanPreviewProjection(
        header_text=header_text,
        material_status_text=material_status,
        contract_text=(
            f"装配检查：{preflight_text}；资料契约：{schema_text}；"
            f"字段槽位：{placeholder_text}；交付版本：{delivery_text}。"
        ),
        sample_enabled=preflight.status == "ok",
        open_master_enabled=master.docx_path.exists(),
        request_word_preview=preflight.status == "ok",
    )
