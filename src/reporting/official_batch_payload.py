from __future__ import annotations

from typing import Any


def official_document_batch_item_payload(
    item: Any,
    assembly: Any,
    *,
    material_diagnostics: list[dict] | None = None,
    metadata: dict[str, object],
) -> dict[str, object]:
    output_paths = {
        str(key): str(value)
        for key, value in dict(getattr(assembly, "output_paths", {}) or {}).items()
        if str(key or "").strip() and str(value or "").strip()
    }
    diagnostics = [
        *list(material_diagnostics or []),
        *official_document_batch_diagnostics(assembly, metadata=metadata),
    ]
    success = bool(getattr(assembly, "ok", False))
    output_path = str(output_paths.get("official_docx", "") or "")
    error_text = "" if success else official_document_batch_error_text(assembly)
    manifest_paths = {
        key: value
        for key, value in output_paths.items()
        if key in {"archive_manifest", "archive_manifest_md"}
    }
    return {
        "status": "success" if success else "failed",
        "profile_id": item.profile_id,
        "profile_name": item.profile_name,
        "official_profile_id": str(getattr(assembly, "profile_id", "") or ""),
        "output_dir": item.output_dir,
        "output_path": output_path,
        "output_paths": output_paths,
        "compare_paths": {},
        "report_paths": [],
        "intermediate_paths": {},
        "material_manifest_paths": manifest_paths,
        "material_package_paths": {},
        "failed_count": 0 if success else 1,
        "error_text": error_text,
        "diagnostics_count": len(diagnostics),
        "diagnostics_summary": "\n".join(
            str(diagnostic.get("reason") or "")
            for diagnostic in diagnostics
            if str(diagnostic.get("reason") or "").strip()
        ),
        "material_diagnostics": diagnostics,
        "official_document_assembly": assembly.to_dict(),
        "batch_item_metadata": dict(metadata),
    }


def official_document_batch_preflight_failure_payload(
    item: Any,
    *,
    profile_id: str,
    error_text: str,
    material_diagnostics: list[dict],
    metadata: dict[str, object],
) -> dict[str, object]:
    diagnostics_summary = "\n".join(
        str(diagnostic.get("reason") or "")
        for diagnostic in material_diagnostics
        if str(diagnostic.get("reason") or "").strip()
    )
    return {
        "status": "failed",
        "profile_id": item.profile_id,
        "profile_name": item.profile_name,
        "official_profile_id": profile_id,
        "output_dir": item.output_dir,
        "output_path": "",
        "output_paths": {},
        "compare_paths": {},
        "report_paths": [],
        "intermediate_paths": {},
        "material_manifest_paths": {},
        "material_package_paths": {},
        "failed_count": 1,
        "error_text": error_text,
        "diagnostics_count": len(material_diagnostics),
        "diagnostics_summary": diagnostics_summary,
        "material_diagnostics": list(material_diagnostics),
        "official_document_assembly": {},
        "batch_item_metadata": dict(metadata),
    }


def official_document_batch_exception_payload(
    item: Any,
    *,
    profile_id: str,
    error_text: str,
    metadata: dict[str, object],
) -> dict[str, object]:
    reason = f"公文批次任务执行异常: {error_text or 'unknown error'}"
    diagnostic = {
        "rule_name": "official_document_batch",
        "target": profile_id or item.profile_id,
        "section": "input_to_delivery",
        "change_type": "official_document_batch_exception",
        "success": False,
        "level": "error",
        "reason": reason,
        "missing_field_keys": [],
        "repair_target_type": "",
        "repair_target_key": "",
    }
    return {
        "status": "failed",
        "profile_id": item.profile_id,
        "profile_name": item.profile_name,
        "official_profile_id": profile_id,
        "output_dir": item.output_dir,
        "output_path": "",
        "output_paths": {},
        "compare_paths": {},
        "report_paths": [],
        "intermediate_paths": {},
        "material_manifest_paths": {},
        "material_package_paths": {},
        "failed_count": 1,
        "error_text": reason,
        "diagnostics_count": 1,
        "diagnostics_summary": reason,
        "material_diagnostics": [diagnostic],
        "official_document_assembly": {},
        "batch_item_metadata": dict(metadata),
    }


def official_document_batch_diagnostics(
    assembly: Any,
    *,
    metadata: dict[str, object],
) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    missing_fields = [
        str(value)
        for value in list(getattr(assembly, "missing_required_fields", ()) or ())
        if str(value or "").strip()
    ]
    if missing_fields:
        diagnostics.append(
            {
                "rule_name": "official_document_assembly",
                "target": str(getattr(assembly, "profile_id", "") or ""),
                "section": "input",
                "change_type": "official_missing_required_fields",
                "success": False,
                "level": "error",
                "reason": "缺少公文必填字段: " + ", ".join(missing_fields),
                "missing_field_keys": missing_fields,
                "repair_target_type": "field",
                "repair_target_key": missing_fields[0],
            }
        )

    unknown_fields = [
        str(value)
        for value in list(metadata.get("unknown_fields", []) or [])
        if str(value or "").strip()
    ]
    if unknown_fields:
        diagnostics.append(
            {
                "rule_name": "official_document_material_import",
                "target": str(getattr(assembly, "profile_id", "") or ""),
                "section": "input",
                "change_type": "official_unknown_material_fields",
                "success": True,
                "level": "warning",
                "reason": "未识别的公文资料字段: " + ", ".join(unknown_fields),
                "missing_field_keys": [],
                "repair_target_type": "",
                "repair_target_key": "",
            }
        )

    unresolved = [
        str(value)
        for value in list(getattr(assembly, "unresolved_placeholders", ()) or ())
        if str(value or "").strip()
    ]
    if unresolved:
        diagnostics.append(
            {
                "rule_name": "official_document_assembly",
                "target": str(getattr(assembly, "profile_id", "") or ""),
                "section": "delivery",
                "change_type": "official_unresolved_placeholders",
                "success": False,
                "level": "error",
                "reason": "公文版式仍有未解析占位符: " + ", ".join(unresolved),
                "missing_field_keys": [],
                "repair_target_type": "",
                "repair_target_key": "",
            }
        )
    return diagnostics


def official_document_batch_error_text(assembly: Any) -> str:
    status = str(getattr(assembly, "status", "") or "failed")
    missing = [
        str(value)
        for value in list(getattr(assembly, "missing_required_fields", ()) or ())
        if str(value or "").strip()
    ]
    if status == "unknown_profile":
        return f"未知公文文种: {getattr(assembly, 'profile_id', '') or '-'}"
    if status == "missing_required_fields":
        return "缺少公文必填字段: " + ", ".join(missing)
    if status == "unresolved_placeholders":
        return "公文版式存在未解析占位符"
    return f"公文装配失败: {status}"


__all__ = [
    "official_document_batch_diagnostics",
    "official_document_batch_error_text",
    "official_document_batch_exception_payload",
    "official_document_batch_item_payload",
    "official_document_batch_preflight_failure_payload",
]
