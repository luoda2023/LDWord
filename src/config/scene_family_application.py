"""Apply planning-level scene family defaults to editable scenes."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from src.config.content_visibility_selectors import content_visibility_selector_label
from src.config.delivery_preset_display import delivery_preset_display_name
from src.config.feature_configs import OutputConfig
from src.config.material_schema_registry import get_material_schema
from src.config.scene import ContentVisibilityRule, DeliveryPreset, SceneWorkspace
from src.config.scene_family_registry import (
    get_planned_scene_family,
    list_planned_scene_families,
)
from src.shared.engine.object_preflight import object_preflight_targets_for_touchpoints


@dataclass(frozen=True, slots=True)
class SceneFamilyApplicationResult:
    family_id: str
    applied: bool = False
    added_presets: tuple[str, ...] = ()
    updated_presets: tuple[str, ...] = ()
    default_delivery_preset_id: str = ""


_SUPPORTED_FAMILY_IDS = {
    "bilingual_translation_documents",
    "contract_delivery",
    "exam_teaching",
    "finance_quote_documents",
    "form_batch_documents",
    "hr_batch_documents",
    "journal_en",
    "long_document_publishing",
    "meeting_policy_documents",
    "product_sales_documents",
    "project_application",
    "qualification_archive_packages",
    "regulated_disclosure_documents",
    "thesis_cn",
}

_PLUGIN_MANUAL_ONLY_FAMILY_IDS = {
    "ip_patent_documents",
}

_CONTRACT_REQUIRED_FIELDS = (
    "party_a",
    "party_b",
    "contract_amount",
    "signing_date",
)

_CONTRACT_REQUIRED_IMAGE_ROLES = ("seal",)

_CONTRACT_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_CONTRACT_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "review_copy",
        "label": "合同审阅稿",
        "final_docx": True,
        "compare_docx": True,
        "report_level": "detailed",
        "include_structured_intermediate": True,
    },
    {
        "preset_id": "signing_copy",
        "label": "合同签署稿",
        "final_docx": True,
        "compare_docx": False,
        "material_manifest": True,
        "material_package": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "field_consistency_report",
        "label": "字段一致性报告",
        "final_docx": False,
        "compare_docx": False,
        "report_level": "detailed",
    },
)

_HR_BATCH_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "per_person_docx",
        "label": "Per-person DOCX",
        "output_dir_template": "hr_batch/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "summary",
    },
    {
        "preset_id": "batch_summary_report",
        "label": "Batch summary report",
        "output_dir_template": "hr_batch/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "failed_items_report",
        "label": "Failed items report",
        "output_dir_template": "hr_batch/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "report_level": "detailed",
    },
)

_HR_BATCH_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "content_controls": ["paragraph_style", "section_format"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_THESIS_CN_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "final",
        "label": "Final manuscript",
        "target_template_id": "thesis_gbt",
        "output_dir_template": "{document_dir}/output",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_level": "summary",
    },
    {
        "preset_id": "review",
        "label": "Review copy",
        "target_template_id": "thesis_gbt",
        "output_dir_template": "{document_dir}/output",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "compliance_report",
        "label": "Compliance report",
        "target_template_id": "thesis_gbt",
        "output_dir_template": "{document_dir}/output",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_level": "detailed",
    },
)

_THESIS_CN_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["heading_numbering", "md_cleanup"],
    "comments": ["heading_numbering"],
    "fields": ["toc", "citation_link", "reference_format"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_JOURNAL_EN_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "submission_manuscript",
        "label": "Submission manuscript",
        "output_dir_template": "journal/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "review_copy",
        "label": "Review copy",
        "output_dir_template": "journal/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "cover_letter",
        "label": "Cover letter",
        "output_dir_template": "journal/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_level": "summary",
    },
    {
        "preset_id": "declaration_package",
        "label": "Declaration package",
        "output_dir_template": "journal/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "compliance_report",
        "label": "Compliance report",
        "output_dir_template": "journal/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "report_level": "detailed",
    },
)

_JOURNAL_EN_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "citation_link", "reference_format"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_EXAM_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "student_version",
        "label": "Student version",
        "output_dir_template": "exam/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "include_structured_intermediate": True,
        "report_level": "summary",
        "visibility_rules": (
            ("answer", "remove"),
            ("analysis", "remove"),
            ("solution", "remove"),
            ("teacher_note", "remove"),
            ("knowledge_points", "remove"),
        ),
    },
    {
        "preset_id": "teacher_version",
        "label": "Teacher version",
        "output_dir_template": "exam/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "answer_key",
        "label": "Answer key",
        "output_dir_template": "exam/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "include_structured_intermediate": True,
        "report_level": "detailed",
        "visibility_rules": (
            ("question_only", "remove"),
            ("analysis", "remove"),
            ("solution", "remove"),
            ("teacher_note", "remove"),
            ("knowledge_points", "remove"),
        ),
    },
    {
        "preset_id": "analysis_version",
        "label": "Analysis version",
        "output_dir_template": "exam/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "include_structured_intermediate": True,
        "report_level": "detailed",
        "visibility_rules": (
            ("student_blank", "remove"),
            ("question_only", "remove"),
        ),
    },
    {
        "preset_id": "answer_sheet",
        "label": "Answer sheet",
        "output_dir_template": "exam/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "summary",
        "visibility_rules": (
            ("answer", "remove"),
            ("analysis", "remove"),
            ("solution", "remove"),
            ("teacher_note", "remove"),
            ("knowledge_points", "remove"),
            ("question_body", "remove"),
        ),
    },
)

_EXAM_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_TECHNICAL_LONG_DOC_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "review_copy",
        "label": "Review copy",
        "target_template_id": "tech_standard",
        "output_dir_template": "technical/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "proof_copy",
        "label": "Proof copy",
        "target_template_id": "tech_standard",
        "output_dir_template": "technical/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "final_docx",
        "label": "Final DOCX",
        "target_template_id": "tech_standard",
        "output_dir_template": "technical/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_level": "summary",
    },
    {
        "preset_id": "archive_package",
        "label": "Archive package",
        "target_template_id": "tech_standard",
        "output_dir_template": "technical/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_TECHNICAL_LONG_DOC_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "header_footer", "citation_link", "reference_format"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_PROJECT_APPLICATION_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "application_package",
        "label": "Application package",
        "output_dir_template": "application/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "attachment_inventory_report",
        "label": "Attachment inventory report",
        "output_dir_template": "application/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_PROJECT_APPLICATION_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_PRODUCT_SALES_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "customer_copy",
        "label": "Customer copy",
        "output_dir_template": "product/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "summary",
    },
    {
        "preset_id": "internal_review",
        "label": "Internal review",
        "output_dir_template": "product/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "report_json": True,
        "report_markdown": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "asset_report",
        "label": "Asset report",
        "output_dir_template": "product/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "pre_sales_package",
        "label": "Pre-sales package",
        "output_dir_template": "product/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_PRODUCT_SALES_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_REGULATED_DISCLOSURE_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "board_review_copy",
        "label": "Board review copy",
        "output_dir_template": "disclosure/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "public_release_copy",
        "label": "Public release copy",
        "output_dir_template": "disclosure/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "summary",
    },
    {
        "preset_id": "disclosure_archive_package",
        "label": "Disclosure archive package",
        "output_dir_template": "disclosure/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "archive_manifest",
        "label": "Archive manifest",
        "output_dir_template": "disclosure/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_REGULATED_DISCLOSURE_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "hidden_text": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_FORM_BATCH_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "per_record_docx",
        "label": "Per-record DOCX",
        "output_dir_template": "form_batch/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "summary",
    },
    {
        "preset_id": "batch_summary_report",
        "label": "Batch summary report",
        "output_dir_template": "form_batch/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "residue_check_report",
        "label": "Residue check report",
        "output_dir_template": "form_batch/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_FORM_BATCH_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "textboxes": ["paragraph_style", "section_format", "table_format"],
    "content_controls": ["paragraph_style", "section_format", "table_format"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_FINANCE_QUOTE_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "customer_quote",
        "label": "Customer quote",
        "output_dir_template": "finance/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "summary",
    },
    {
        "preset_id": "internal_review",
        "label": "Internal review",
        "output_dir_template": "finance/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "report_json": True,
        "report_markdown": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "attachment_report",
        "label": "Attachment report",
        "output_dir_template": "finance/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_FINANCE_QUOTE_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format", "table_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_BILINGUAL_REVIEW_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "bilingual_review_copy",
        "label": "Bilingual review copy",
        "output_dir_template": "bilingual/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "parallel_comparison",
        "label": "Parallel comparison",
        "output_dir_template": "bilingual/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "report_json": True,
        "report_markdown": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "term_consistency_report",
        "label": "Term consistency report",
        "output_dir_template": "bilingual/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_BILINGUAL_REVIEW_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "textboxes": ["paragraph_style", "section_format"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_QUALIFICATION_ARCHIVE_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "attachment_package",
        "label": "Attachment package",
        "output_dir_template": "qualification/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "missing_items_report",
        "label": "Missing items report",
        "output_dir_template": "qualification/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "archive_manifest",
        "label": "Archive manifest",
        "output_dir_template": "qualification/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_QUALIFICATION_ARCHIVE_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}

_MEETING_POLICY_DELIVERY_PRESET_SPECS = (
    {
        "preset_id": "formal_minutes",
        "label": "Formal minutes",
        "target_template_id": "official_gbt",
        "output_dir_template": "official/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "internal_review",
        "label": "Internal review",
        "target_template_id": "official_gbt",
        "output_dir_template": "official/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": True,
        "report_json": True,
        "report_markdown": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "policy_collection",
        "label": "Policy collection archive",
        "target_template_id": "official_gbt",
        "output_dir_template": "official/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": True,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
    {
        "preset_id": "archive_manifest",
        "label": "Archive manifest",
        "target_template_id": "official_gbt",
        "output_dir_template": "official/{preset_id}",
        "filename_template": "{stem}_{preset_id}",
        "final_docx": False,
        "compare_docx": False,
        "report_json": True,
        "report_markdown": True,
        "material_manifest": True,
        "material_package": True,
        "include_structured_intermediate": True,
        "report_level": "detailed",
    },
)

_MEETING_POLICY_SKIP_MODULES_BY_FINDING = {
    "tracked_changes": ["paragraph_style", "section_format", "heading_numbering", "md_cleanup"],
    "comments": ["paragraph_style", "section_format", "heading_numbering"],
    "fields": ["toc", "header_footer"],
    "ole_objects": ["section_format"],
    "embedded_workbooks": ["section_format"],
    "embedded_packages": ["section_format"],
    "visio_drawings": ["section_format"],
    "macros": ["section_format"],
}


def planned_family_id_for_scene(scene: SceneWorkspace) -> str:
    """Resolve the planning family most relevant to an editable scene."""

    scene_id = str(getattr(scene, "scene_id", "") or "").strip()
    category = str(getattr(scene, "category", "") or "").strip()
    compliance = getattr(scene, "compliance_profile", None)
    rule_family = str(getattr(compliance, "rule_family", "") or "").strip()
    profile_id = str(getattr(compliance, "profile_id", "") or "").strip()
    if (
        scene_id in {"official", "meeting_policy_documents"}
        or category in {"official", "government", "meeting_policy_documents"}
        or rule_family in {
            "official_document",
            "meeting_minutes",
            "policy_collection",
            "meeting_policy_documents",
        }
        or profile_id in {
            "official_document",
            "meeting_minutes",
            "policy_collection",
            "meeting_policy_documents_default",
        }
    ):
        return "meeting_policy_documents"
    if (
        scene_id == "technical"
        or category == "technical"
        or rule_family == "technical_review"
        or profile_id == "technical_document"
    ):
        return "long_document_publishing"

    candidates = [
        scene_id,
        category,
    ]
    candidates.extend(
        [
            profile_id,
            rule_family,
            getattr(compliance, "count_profile_id", ""),
        ]
    )
    schema_id = str(
        getattr(getattr(scene, "input_source_profile", None), "material_schema_id", "")
        or ""
    ).strip()
    if schema_id:
        try:
            candidates.append(get_material_schema(schema_id).family)
        except KeyError:
            pass
    for schema_id in list(
        getattr(getattr(scene, "input_source_profile", None), "material_schema_ids", [])
        or []
    ):
        normalized_schema_id = str(schema_id or "").strip()
        if not normalized_schema_id:
            continue
        try:
            candidates.append(get_material_schema(normalized_schema_id).family)
        except KeyError:
            pass

    for candidate in candidates:
        normalized = str(candidate or "").strip()
        if not normalized:
            continue
        try:
            return get_planned_scene_family(normalized).family_id
        except KeyError:
            continue
    return ""


def has_planned_scene_family_application(scene: SceneWorkspace) -> bool:
    return planned_family_id_for_scene(scene) in _SUPPORTED_FAMILY_IDS


def planned_family_is_application_boundary_only(family_id: str) -> bool:
    return str(family_id or "").strip() in _PLUGIN_MANUAL_ONLY_FAMILY_IDS


def audit_planned_scene_family_application_parity() -> dict[str, str]:
    """Return planned families that are neither executable nor explicitly gated."""

    gaps: dict[str, str] = {}
    for family in list_planned_scene_families():
        if family.family_id in _SUPPORTED_FAMILY_IDS:
            continue
        if planned_family_is_application_boundary_only(family.family_id):
            continue
        gaps[family.family_id] = (
            "missing scene_family_application defaults or plugin/manual-only boundary"
        )
    return gaps


def apply_planned_scene_family_defaults(
    scene: SceneWorkspace,
    *,
    family_id: str | None = None,
) -> SceneFamilyApplicationResult:
    resolved_family_id = str(family_id or "").strip() or planned_family_id_for_scene(scene)
    if resolved_family_id == "thesis_cn":
        return _apply_thesis_cn_defaults(scene)
    if resolved_family_id == "journal_en":
        return _apply_journal_en_defaults(scene)
    if resolved_family_id == "exam_teaching":
        return _apply_exam_teaching_defaults(scene)
    if resolved_family_id == "contract_delivery":
        return _apply_contract_delivery_defaults(scene)
    if resolved_family_id == "hr_batch_documents":
        return _apply_hr_batch_defaults(scene)
    if resolved_family_id == "long_document_publishing":
        return _apply_long_document_publishing_defaults(scene)
    if resolved_family_id == "form_batch_documents":
        return _apply_form_batch_defaults(scene)
    if resolved_family_id == "meeting_policy_documents":
        return _apply_meeting_policy_defaults(scene)
    if resolved_family_id == "project_application":
        return _apply_project_application_defaults(scene)
    if resolved_family_id == "product_sales_documents":
        return _apply_product_sales_defaults(scene)
    if resolved_family_id == "qualification_archive_packages":
        return _apply_qualification_archive_defaults(scene)
    if resolved_family_id == "finance_quote_documents":
        return _apply_finance_quote_defaults(scene)
    if resolved_family_id == "bilingual_translation_documents":
        return _apply_bilingual_review_defaults(scene)
    if resolved_family_id == "regulated_disclosure_documents":
        return _apply_regulated_disclosure_defaults(scene)
    return SceneFamilyApplicationResult(family_id=resolved_family_id)


def _apply_thesis_cn_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("thesis_cn")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json",))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "formula_fragments_only"
    if not str(getattr(profile, "material_schema_id", "") or "").strip():
        profile.material_schema_id = "thesis_school_rule_context_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        family.material_schema_ids,
    )
    profile.require_material_package = False
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "thesis_cn"
    compliance.rule_family = "academic_thesis"
    compliance.count_profile_id = "school_thesis"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        (
            "abstract_cn",
            "abstract_en",
            "body",
            "references",
            "tables",
            "figures",
            "appendix",
        ),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_THESIS_CN_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "validation",
            "citation_link",
            "reference_format",
            "equation_table_format",
            "caption",
            "toc",
        ),
    )
    added, updated = _upsert_delivery_presets(scene, _THESIS_CN_DELIVERY_PRESET_SPECS)
    scene.default_delivery_preset_id = "final"
    default = _delivery_preset_by_id(scene, "final")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="thesis_cn",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_journal_en_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("journal_en")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(
        profile.structured_formats,
        ("bibtex", "csl_json", "json"),
    )
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "formula_fragments_only"
    profile.require_material_package = True
    profile.material_schema_id = "journal_submission_materials_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("journal_submission_materials_v1",),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "journal_submission"
    compliance.rule_family = "journal_submission"
    compliance.count_profile_id = "journal_words"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        (
            "validation",
            "object_preflight",
            "journal_citations",
            "journal_submission_package",
        ),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("title", "abstract", "body", "methods", "references", "tables", "figures"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_JOURNAL_EN_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "validation",
            "citation_link",
            "reference_format",
            "equation_table_format",
            "caption",
            "figure_table_center",
            "toc",
        ),
    )
    added, updated = _upsert_delivery_presets(scene, _JOURNAL_EN_DELIVERY_PRESET_SPECS)
    scene.default_delivery_preset_id = "submission_manuscript"
    default = _delivery_preset_by_id(scene, "submission_manuscript")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="journal_en",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_contract_delivery_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("contract_delivery")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json",))
    profile.require_material_package = True
    profile.material_schema_id = "contract_parties_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        family.material_schema_ids,
    )
    profile.required_material_fields = _merged_values(
        profile.required_material_fields,
        _CONTRACT_REQUIRED_FIELDS,
    )
    profile.required_image_roles = _merged_values(
        profile.required_image_roles,
        _CONTRACT_REQUIRED_IMAGE_ROLES,
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "contract_format"
    compliance.rule_family = "contract_delivery"
    compliance.count_profile_id = "contract_fields"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight", "material_field_consistency"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("body", "headers_footers", "comments", "tracked_changes"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "strict"
    preflight.scan_targets = list(object_preflight_targets_for_touchpoints(family.ooxml_touchpoints))
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_CONTRACT_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "entity_fill",
            "placeholder_replace",
            "image_insertion",
            "validation",
        ),
    )
    added, updated = _upsert_delivery_presets(scene, _CONTRACT_DELIVERY_PRESET_SPECS)
    scene.default_delivery_preset_id = "review_copy"
    default = _delivery_preset_by_id(scene, "review_copy")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="contract_delivery",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_hr_batch_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("hr_batch_documents")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "disabled"
    profile.latex_policy = "disabled"
    profile.require_material_package = True
    profile.material_schema_id = "personnel_records_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("personnel_records_v1",),
    )
    profile.required_material_fields = _merged_values(
        profile.required_material_fields,
        ("employee_name", "employee_id"),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "personnel_batch"
    compliance.rule_family = "hr_batch_documents"
    compliance.count_profile_id = "batch_item_inventory"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("records", "fields", "tables", "images", "batch_items"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_HR_BATCH_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        ("entity_fill", "placeholder_replace", "image_insertion", "validation"),
    )
    _remove_delivery_presets(scene, ("final", "review", "change_report", "package_report"))
    added, updated = _upsert_delivery_presets(scene, _HR_BATCH_DELIVERY_PRESET_SPECS)
    scene.default_delivery_preset_id = "per_person_docx"
    default = _delivery_preset_by_id(scene, "per_person_docx")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="hr_batch_documents",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_exam_teaching_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("exam_teaching")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "formula_fragments_only"
    profile.require_material_package = True
    profile.material_schema_id = "exam_items_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        family.material_schema_ids,
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "exam_paper"
    compliance.rule_family = "exam_teaching"
    compliance.count_profile_id = "exam_items"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight", "exam_question_schema"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("body", "tables", "figures", "answer_blocks", "analysis_blocks"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_EXAM_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "placeholder_replace",
            "image_insertion",
            "validation",
            "equation_table_format",
            "caption",
            "figure_table_center",
        ),
    )
    added, updated = _upsert_delivery_presets(scene, _EXAM_DELIVERY_PRESET_SPECS)
    scene.default_delivery_preset_id = "student_version"
    default = _delivery_preset_by_id(scene, "student_version")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="exam_teaching",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_long_document_publishing_defaults(
    scene: SceneWorkspace,
) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("long_document_publishing")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json",))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "formula_fragments_only"
    profile.require_material_package = False
    if not str(getattr(profile, "material_schema_id", "") or "").strip():
        profile.material_schema_id = "long_document_metadata_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("long_document_metadata_v1",),
    )
    profile.required_image_roles = _merged_values(
        profile.required_image_roles,
        ("diagram", "figure"),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "long_document_publishing"
    compliance.rule_family = "long_document_structure"
    compliance.count_profile_id = "chapter_inventory"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight", "technical_chapter_inventory"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        (
            "body",
            "toc",
            "tables",
            "figures",
            "appendix",
            "headers_footers",
            "fields",
            "relationships",
        ),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "strict"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros", "ole_objects", "embedded_workbooks"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_TECHNICAL_LONG_DOC_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "validation",
            "heading_recognition",
            "heading_numbering",
            "toc",
            "caption",
            "table_format",
            "figure_table_center",
            "equation_table_format",
            "md_cleanup",
            "whitespace_normalize",
        ),
    )
    _remove_delivery_presets(scene, ("final", "review", "change_report"))
    added, updated = _upsert_delivery_presets(
        scene,
        _TECHNICAL_LONG_DOC_DELIVERY_PRESET_SPECS,
    )
    scene.default_delivery_preset_id = "final_docx"
    default = _delivery_preset_by_id(scene, "final_docx")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="long_document_publishing",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_project_application_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("project_application")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "formula_fragments_only"
    profile.require_material_package = True
    profile.material_schema_id = "project_application_materials_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("project_application_materials_v1",),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "project_application"
    compliance.rule_family = "project_application"
    compliance.count_profile_id = "application_word_limits"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("body", "toc", "tables", "figures", "attachments", "fields"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_PROJECT_APPLICATION_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "placeholder_replace",
            "image_insertion",
            "validation",
            "toc",
            "caption",
            "table_format",
            "figure_table_center",
        ),
    )
    _remove_delivery_presets(scene, ("final", "review", "change_report"))
    added, updated = _upsert_delivery_presets(
        scene,
        _PROJECT_APPLICATION_DELIVERY_PRESET_SPECS,
    )
    scene.default_delivery_preset_id = "application_package"
    default = _delivery_preset_by_id(scene, "application_package")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="project_application",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_form_batch_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("form_batch_documents")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "disabled"
    profile.latex_policy = "disabled"
    profile.require_material_package = True
    profile.material_schema_id = "form_batch_fields_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("form_batch_fields_v1",),
    )
    profile.required_material_fields = _merged_values(
        profile.required_material_fields,
        ("form_title", "record_id", "applicant_name"),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "form_batch_fields"
    compliance.rule_family = "form_batch_documents"
    compliance.count_profile_id = "batch_item_inventory"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("records", "fields", "tables", "textboxes", "content_controls", "residue"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_FORM_BATCH_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        ("entity_fill", "placeholder_replace", "image_insertion", "validation"),
    )
    _remove_delivery_presets(scene, ("final", "review", "change_report", "package_report"))
    added, updated = _upsert_delivery_presets(scene, _FORM_BATCH_DELIVERY_PRESET_SPECS)
    scene.default_delivery_preset_id = "per_record_docx"
    default = _delivery_preset_by_id(scene, "per_record_docx")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="form_batch_documents",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_product_sales_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("product_sales_documents")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "formula_fragments_only"
    profile.require_material_package = True
    profile.material_schema_id = "product_assets_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("product_assets_v1", "case_study_assets_v1"),
    )
    profile.required_image_roles = _merged_values(
        profile.required_image_roles,
        ("product_image",),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "product_document"
    compliance.rule_family = "product_sales_documents"
    compliance.count_profile_id = "product_asset_inventory"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("body", "tables", "figures", "assets", "case_studies", "fields"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_PRODUCT_SALES_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "entity_fill",
            "placeholder_replace",
            "image_insertion",
            "validation",
            "toc",
            "caption",
            "table_format",
            "figure_table_center",
        ),
    )
    _remove_delivery_presets(scene, ("final", "review", "change_report", "package_report"))
    added, updated = _upsert_delivery_presets(
        scene,
        _PRODUCT_SALES_DELIVERY_PRESET_SPECS,
    )
    scene.default_delivery_preset_id = "customer_copy"
    default = _delivery_preset_by_id(scene, "customer_copy")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="product_sales_documents",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_qualification_archive_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("qualification_archive_packages")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "disabled"
    profile.latex_policy = "disabled"
    profile.require_material_package = True
    profile.material_schema_id = "qualification_archive_assets_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("qualification_archive_assets_v1",),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "qualification_inventory"
    compliance.rule_family = "qualification_archive_packages"
    compliance.count_profile_id = "attachment_inventory"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("attachments", "fields", "relationships", "package_parts"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_QUALIFICATION_ARCHIVE_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "placeholder_replace",
            "image_insertion",
            "validation",
        ),
    )
    _remove_delivery_presets(scene, ("final", "review", "change_report", "package_report"))
    added, updated = _upsert_delivery_presets(
        scene,
        _QUALIFICATION_ARCHIVE_DELIVERY_PRESET_SPECS,
    )
    scene.default_delivery_preset_id = "attachment_package"
    default = _delivery_preset_by_id(scene, "attachment_package")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="qualification_archive_packages",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_finance_quote_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("finance_quote_documents")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "disabled"
    profile.require_material_package = True
    profile.material_schema_id = "finance_quote_fields_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("finance_quote_fields_v1",),
    )
    profile.required_material_fields = _merged_values(
        profile.required_material_fields,
        ("customer_name", "quote_no", "amount"),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "quote_document_format"
    compliance.rule_family = "finance_quote_documents"
    compliance.count_profile_id = "finance_attachment_inventory"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("body", "tables", "attachments", "fields", "comments", "relationships"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_FINANCE_QUOTE_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "entity_fill",
            "placeholder_replace",
            "image_insertion",
            "validation",
            "table_format",
            "figure_table_center",
        ),
    )
    _remove_delivery_presets(scene, ("final", "review", "change_report", "package_report"))
    added, updated = _upsert_delivery_presets(scene, _FINANCE_QUOTE_DELIVERY_PRESET_SPECS)
    scene.default_delivery_preset_id = "customer_quote"
    default = _delivery_preset_by_id(scene, "customer_quote")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="finance_quote_documents",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_bilingual_review_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("bilingual_translation_documents")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "disabled"
    profile.require_material_package = True
    profile.material_schema_id = "bilingual_terms_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("bilingual_terms_v1",),
    )
    profile.required_material_fields = _merged_values(
        profile.required_material_fields,
        ("source_language", "target_language", "document_title"),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "bilingual_layout"
    compliance.rule_family = "bilingual_translation_documents"
    compliance.count_profile_id = "bilingual_parallel_text"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("body", "tables", "comments", "revisions", "terminology", "textboxes"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_BILINGUAL_REVIEW_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        ("placeholder_replace", "validation", "table_format", "figure_table_center"),
    )
    _remove_delivery_presets(scene, ("final", "review", "change_report", "package_report"))
    added, updated = _upsert_delivery_presets(scene, _BILINGUAL_REVIEW_DELIVERY_PRESET_SPECS)
    scene.default_delivery_preset_id = "bilingual_review_copy"
    default = _delivery_preset_by_id(scene, "bilingual_review_copy")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="bilingual_translation_documents",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_regulated_disclosure_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("regulated_disclosure_documents")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json", "xlsx"))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "disabled"
    profile.require_material_package = True
    profile.material_schema_id = "regulated_disclosure_materials_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("regulated_disclosure_materials_v1",),
    )
    profile.required_material_fields = _merged_values(
        profile.required_material_fields,
        ("organization", "report_period", "report_type"),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "regulated_disclosure_structure"
    compliance.rule_family = "regulated_disclosure_documents"
    compliance.count_profile_id = "disclosure_section_inventory"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        (
            "body",
            "tables",
            "figures",
            "attachments",
            "comments",
            "revisions",
            "hidden_text",
            "relationships",
        ),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_REGULATED_DISCLOSURE_SKIP_MODULES_BY_FINDING),
    }

    _enable_modules(
        scene,
        (
            "placeholder_replace",
            "image_insertion",
            "validation",
            "toc",
            "caption",
            "table_format",
            "figure_table_center",
        ),
    )
    _remove_delivery_presets(
        scene,
        ("final", "review", "change_report", "package_report", "archive_package"),
    )
    added, updated = _upsert_delivery_presets(
        scene,
        _REGULATED_DISCLOSURE_DELIVERY_PRESET_SPECS,
    )
    scene.default_delivery_preset_id = "board_review_copy"
    default = _delivery_preset_by_id(scene, "board_review_copy")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="regulated_disclosure_documents",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _apply_meeting_policy_defaults(scene: SceneWorkspace) -> SceneFamilyApplicationResult:
    family = get_planned_scene_family("meeting_policy_documents")
    profile = scene.input_source_profile
    profile.accepted_formats = _merged_values(profile.accepted_formats, family.input_formats)
    profile.structured_formats = _merged_values(profile.structured_formats, ("json",))
    profile.markdown_policy = "preview_and_cleanup"
    profile.latex_policy = "disabled"
    profile.require_material_package = True
    profile.material_schema_id = "administrative_meeting_fields_v1"
    profile.material_schema_ids = _merged_values(
        profile.material_schema_ids,
        ("administrative_meeting_fields_v1",),
    )
    profile.required_material_fields = _merged_values(
        profile.required_material_fields,
        ("organization", "meeting_title", "meeting_date"),
    )
    profile.required_image_roles = _merged_values(
        profile.required_image_roles,
        ("seal",),
    )
    profile.failure_policy = "warn"

    compliance = scene.compliance_profile
    compliance.profile_id = "meeting_minutes"
    compliance.rule_family = "meeting_policy_documents"
    compliance.count_profile_id = "administrative_sections"
    compliance.enabled_checks = _merged_values(
        compliance.enabled_checks,
        ("validation", "object_preflight", "official_numbering_preservation"),
    )
    compliance.check_scopes = _merged_values(
        compliance.check_scopes,
        ("body", "headers_footers", "metadata", "appendix", "archive"),
    )
    compliance.report_level = "detailed"
    compliance.failure_policy = "warn"

    preflight = compliance.object_preflight
    preflight.enabled = True
    preflight.preservation_mode = "warn"
    preflight.scan_targets = _merged_values(
        preflight.scan_targets,
        object_preflight_targets_for_touchpoints(family.ooxml_touchpoints),
    )
    preflight.block_on = ["macros"]
    preflight.skip_high_risk_modules = True
    preflight.skip_modules_by_finding = {
        **dict(getattr(preflight, "skip_modules_by_finding", {}) or {}),
        **copy.deepcopy(_MEETING_POLICY_SKIP_MODULES_BY_FINDING),
    }

    scene.watermark.enabled = True
    scene.watermark.text = "内部传阅"
    scene.watermark.color = "#C0C0C0"

    _enable_modules(
        scene,
        (
            "entity_fill",
            "placeholder_replace",
            "image_insertion",
            "validation",
            "watermark",
            "toc",
            "header_footer",
        ),
    )
    _remove_delivery_presets(scene, ("formal", "change_report", "package_report"))
    added, updated = _upsert_delivery_presets(
        scene,
        _MEETING_POLICY_DELIVERY_PRESET_SPECS,
    )
    scene.default_delivery_preset_id = "formal_minutes"
    default = _delivery_preset_by_id(scene, "formal_minutes")
    if default is not None:
        scene.output = copy.deepcopy(default.artifacts)

    return SceneFamilyApplicationResult(
        family_id="meeting_policy_documents",
        applied=True,
        added_presets=tuple(added),
        updated_presets=tuple(updated),
        default_delivery_preset_id=scene.default_delivery_preset_id,
    )


def _upsert_delivery_presets(
    scene: SceneWorkspace,
    specs: tuple[dict[str, object], ...],
) -> tuple[list[str], list[str]]:
    added: list[str] = []
    updated: list[str] = []
    for spec in specs:
        preset_id = str(spec.get("preset_id") or "").strip()
        if not preset_id:
            continue
        preset = _delivery_preset_by_id(scene, preset_id)
        if preset is None:
            preset = DeliveryPreset(preset_id=preset_id)
            scene.delivery_presets.append(preset)
            added.append(preset_id)
        else:
            updated.append(preset_id)
        _apply_delivery_spec(preset, spec)
    return added, updated


def _apply_delivery_spec(preset: DeliveryPreset, spec: dict[str, object]) -> None:
    compare_docx = bool(spec.get("compare_docx", False))
    preset.label = delivery_preset_display_name(str(spec.get("label") or preset.preset_id))
    preset.target_template_id = str(spec.get("target_template_id") or "")
    preset.output_dir_template = str(
        spec.get("output_dir_template") or "contract_delivery/{preset_id}"
    )
    preset.filename_template = str(spec.get("filename_template") or "{stem}_{preset_id}")
    preset.artifacts = OutputConfig(
        final_docx=bool(spec.get("final_docx", True)),
        compare_docx=compare_docx,
        compare_text=compare_docx,
        compare_formatting=compare_docx,
        report_json=bool(spec.get("report_json", True)),
        report_markdown=bool(spec.get("report_markdown", True)),
        material_manifest=bool(spec.get("material_manifest", False)),
        material_package=bool(spec.get("material_package", False)),
    )
    preset.include_structured_intermediate = bool(
        spec.get("include_structured_intermediate", False)
    )
    preset.report_level = str(spec.get("report_level") or "summary")
    preset.content_visibility_rules = _content_visibility_rules_from_spec(
        preset.preset_id,
        spec.get("visibility_rules"),
    )


def _content_visibility_rules_from_spec(
    preset_id: str,
    visibility_rules: object,
) -> list[ContentVisibilityRule]:
    rules: list[ContentVisibilityRule] = []
    if not isinstance(visibility_rules, (list, tuple)):
        return rules
    for index, item in enumerate(visibility_rules, start=1):
        if not isinstance(item, (list, tuple)) or not item:
            continue
        selector = str(item[0] or "").strip()
        action = str(item[1] if len(item) > 1 else "remove").strip() or "remove"
        if not selector:
            continue
        rules.append(
            ContentVisibilityRule(
                rule_id=f"{preset_id}_{selector}_{action}_{index}",
                label=content_visibility_selector_label(selector),
                selector_type="marker_block",
                selector=selector,
                action=action,
            )
        )
    return rules


def _delivery_preset_by_id(scene: SceneWorkspace, preset_id: str) -> DeliveryPreset | None:
    target = str(preset_id or "").strip()
    for preset in list(getattr(scene, "delivery_presets", []) or []):
        if str(getattr(preset, "preset_id", "") or "").strip() == target:
            return preset
    return None


def _remove_delivery_presets(scene: SceneWorkspace, preset_ids: tuple[str, ...]) -> None:
    targets = {str(preset_id or "").strip() for preset_id in preset_ids}
    scene.delivery_presets = [
        preset
        for preset in list(getattr(scene, "delivery_presets", []) or [])
        if str(getattr(preset, "preset_id", "") or "").strip() not in targets
    ]


def _enable_modules(scene: SceneWorkspace, module_names: tuple[str, ...]) -> None:
    for module_name in module_names:
        if module_name in scene.module_switches:
            scene.module_switches[module_name] = True


def _merged_values(existing, additions) -> list[str]:
    merged: list[str] = []
    for value in [*(existing or []), *(additions or [])]:
        normalized = str(value or "").strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


__all__ = [
    "SceneFamilyApplicationResult",
    "audit_planned_scene_family_application_parity",
    "apply_planned_scene_family_defaults",
    "has_planned_scene_family_application",
    "planned_family_is_application_boundary_only",
    "planned_family_id_for_scene",
]
