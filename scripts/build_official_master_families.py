"""Rebuild built-in official DOCX master families and their manifests."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.master_placeholder_index import scan_master_placeholder_index  # noqa: E402
from src.shared.engine.official_document_master import (  # noqa: E402
    OFFICIAL_MASTER_FAMILIES,
    OFFICIAL_MASTER_VERSION,
    write_official_master_family_docx,
)


BUILTIN_DIR = ROOT / "config_library" / "masters" / "official" / "builtin"

FAMILY_META = {
    "common": (
        "official_gbt_standard",
        "GB/T 9704 通用红头公文版式",
        "普通平行文和下行文红头版式；文种规则由工作台资料契约控制。",
    ),
    "upward": (
        "official_gbt_upward",
        "GB/T 9704 上行文版式",
        "报告、请示、议案使用的签发人版头版式。",
    ),
    "letter": (
        "official_gbt_letter",
        "GB/T 9704 信函格式",
        "函默认使用的信函特定格式；通知和批复可按场景显式选用。",
    ),
    "minutes": (
        "official_gbt_minutes",
        "GB/T 9704 纪要格式",
        "纪要标志、期号、制发机关日期栏和会议字段专用版式。",
    ),
    "order": (
        "official_gbt_order",
        "GB/T 9704 命令（令）格式",
        "命令（令）的机关标志、令号、签发人和日期专用版式。",
    ),
}

COMMON_OPTIONAL_PLACEHOLDERS = (
    "official_security_level",
    "official_urgency",
    "official_organization",
    "official_document_no",
    "official_recipient",
    "official_attachment_note",
    "official_issuer",
    "official_issue_date",
    "official_copy_scope",
    "official_printing_org",
    "official_printing_date",
)
OPTIONAL_PLACEHOLDERS_BY_FAMILY = {
    "common": COMMON_OPTIONAL_PLACEHOLDERS,
    "upward": (*COMMON_OPTIONAL_PLACEHOLDERS, "official_signer"),
    "letter": tuple(
        value
        for value in COMMON_OPTIONAL_PLACEHOLDERS
        if value not in {"official_printing_org", "official_printing_date"}
    ),
    "minutes": (
        "official_security_level",
        "official_urgency",
        "official_organization",
        "official_document_no",
        "official_issuer",
        "official_issue_date",
        "official_meeting_time",
        "official_meeting_attendees",
        "official_copy_scope",
        "official_printing_org",
        "official_printing_date",
    ),
    "order": (
        "official_security_level",
        "official_urgency",
        "official_organization",
        "official_document_no",
        "official_issue_date",
        "official_signer",
    ),
}


def main() -> None:
    BUILTIN_DIR.mkdir(parents=True, exist_ok=True)
    for family_id, (master_id, label, summary) in FAMILY_META.items():
        docx_path = BUILTIN_DIR / f"{master_id}.docx"
        write_official_master_family_docx(docx_path, family_id=family_id)
        index = scan_master_placeholder_index(docx_path, use_cache=False)
        index_payload = index.to_payload()
        index_payload.pop("docx_path", None)
        manifest = {
            "master_id": master_id,
            "mode_id": "official",
            "label": label,
            "family": "official",
            "layout_family": family_id,
            "source_type": "builtin",
            "docx_path": str(docx_path.relative_to(ROOT)).replace("\\", "/"),
            "summary": summary,
            "status": "内置，已接入文种版式路由和 runtime 公文装配",
            "template_config_id": "official_gbt",
            "compatible_template_config_ids": ["official_gbt", "official_custom"],
            "master_version": OFFICIAL_MASTER_VERSION,
            "placeholder_contract": {
                "required": ["official_title", "official_body"],
                "optional": list(OPTIONAL_PLACEHOLDERS_BY_FAMILY[family_id]),
                "runtime_fields": [
                    "title",
                    "body",
                    "organization",
                    "document_no",
                    "recipient",
                    "attachment_note",
                    "issuer",
                    "issue_date",
                    "security_level",
                    "urgency",
                    "signer",
                    "copy_scope",
                    "printing_org",
                    "printing_date",
                    "meeting_date",
                    "participants",
                ],
                "generated_fields": ["delivery_version"],
                "runtime_inserted_placeholders": [],
                "legacy_aliases": [],
            },
            "placeholder_index": index_payload,
            "supported_assembly_types": list(OFFICIAL_MASTER_FAMILIES[family_id]),
            "boundaries": [
                "does not certify official release validity",
                "does not verify seal legality",
                "does not replace archive-office approval",
            ],
        }
        manifest_path = BUILTIN_DIR / f"{master_id}.master.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{family_id}: {docx_path.name} -> {index.sha256}")


if __name__ == "__main__":
    main()
