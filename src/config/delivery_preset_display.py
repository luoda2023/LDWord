from __future__ import annotations


DELIVERY_PRESET_DISPLAY_LABELS = {
    "final": "最终 Word",
    "final_docx": "最终 Word",
    "review": "审阅稿",
    "review_copy": "审阅稿",
    "review_public": "对外审阅稿",
    "original": "正本",
    "copy": "副本",
    "formal": "正式稿",
    "internal_review": "内部审阅稿",
    "change_report": "修改报告",
    "package_report": "打包报告",
    "compliance_report": "合规报告",
    "formal_minutes": "正式纪要",
    "policy_collection": "政策资料归档",
    "archive_manifest": "归档清单",
    "customer_copy": "客户版",
    "internal_copy": "内部版",
    "application_package": "申报包",
    "attachment_inventory_report": "附件清单报告",
    "pre_sales_package": "售前资料包",
    "asset_report": "资料检查报告",
    "board_review_copy": "董事会审阅稿",
    "public_release_copy": "公开发布稿",
    "disclosure_archive_package": "披露归档包",
    "per_person_docx": "按人员生成",
    "per_record_docx": "按记录生成",
    "batch_summary_report": "批量汇总报告",
    "failed_items_report": "失败项报告",
    "residue_check_report": "残留检查报告",
    "missing_items_report": "缺项报告",
    "field_consistency_report": "字段一致性报告",
    "signing_copy": "签署稿",
    "student": "学生卷",
    "student_version": "学生版",
    "teacher_version": "教师版",
    "answer": "答案速查",
    "answer_key": "答案速查",
    "analysis_version": "解析版",
    "answer_sheet": "答题卡",
    "submission_manuscript": "投稿正文",
    "cover_letter": "投稿信",
    "declaration_package": "声明材料包",
    "customer_quote": "客户报价稿",
    "attachment_report": "附件报告",
    "attachment_package": "附件包",
    "bilingual_review_copy": "双语审阅稿",
    "parallel_comparison": "双语对照稿",
    "term_consistency_report": "术语一致性报告",
    "proof_copy": "校样稿",
    "archive_package": "归档包",
    "Final DOCX": "最终 Word",
    "Final manuscript": "最终稿",
    "Final report": "最终报告",
    "Review copy": "审阅稿",
    "Original copy": "正本",
    "Duplicate copy": "副本",
    "Formal copy": "正式稿",
    "Internal review": "内部审阅稿",
    "Policy collection archive": "政策资料归档",
    "Archive package": "归档包",
    "Proof copy": "校样稿",
    "Per-person DOCX": "按人员生成",
    "Per-record DOCX": "按记录生成",
    "Batch summary report": "批量汇总报告",
    "Failed items report": "失败项报告",
    "Compliance report": "合规报告",
    "Submission manuscript": "投稿正文",
    "Cover letter": "投稿信",
    "Declaration package": "声明材料包",
    "Student version": "学生版",
    "Teacher version": "教师版",
    "Answer key": "答案速查",
    "Analysis version": "解析版",
    "Answer sheet": "答题卡",
    "Application package": "申报包",
    "Attachment inventory report": "附件清单报告",
    "Asset report": "资料检查报告",
    "Pre-sales package": "售前资料包",
    "Archive manifest": "归档清单",
    "Residue check report": "残留检查报告",
    "Customer quote": "客户报价稿",
    "Bilingual review copy": "双语审阅稿",
    "Attachment package": "附件包",
    "Missing items report": "缺项报告",
    "Formal minutes": "正式纪要",
    "Customer copy": "客户版",
    "Board review copy": "董事会审阅稿",
    "Public release copy": "公开发布稿",
    "Disclosure archive package": "披露归档包",
    "Attachment report": "附件报告",
    "Parallel comparison": "双语对照稿",
    "Term consistency report": "术语一致性报告",
}


def _display_id(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return DELIVERY_PRESET_DISPLAY_LABELS.get(normalized, normalized.replace("_", " "))


def delivery_preset_display_name(preset_or_id: object) -> str:
    if preset_or_id is None:
        return "未设置"
    if hasattr(preset_or_id, "preset_id"):
        preset_id = str(getattr(preset_or_id, "preset_id", "") or "").strip()
        label = str(getattr(preset_or_id, "label", "") or "").strip()
        if label and label not in {preset_id, "Final DOCX"}:
            return DELIVERY_PRESET_DISPLAY_LABELS.get(label, label)
        if preset_id in DELIVERY_PRESET_DISPLAY_LABELS:
            return DELIVERY_PRESET_DISPLAY_LABELS[preset_id]
        return _display_id(preset_id)
    return _display_id(preset_or_id)


def delivery_preset_option_tooltip(preset_or_id: object) -> str:
    preset_id = str(getattr(preset_or_id, "preset_id", "") or "").strip()
    label = str(getattr(preset_or_id, "label", "") or "").strip()
    display_name = delivery_preset_display_name(preset_or_id)
    lines = [f"交付版本：{display_name}"]
    if preset_id:
        lines.append(f"版本 ID：{preset_id}")
    if label and label != display_name:
        lines.append(f"原始标签：{label}")
    return "\n".join(lines)


__all__ = [
    "DELIVERY_PRESET_DISPLAY_LABELS",
    "delivery_preset_display_name",
    "delivery_preset_option_tooltip",
]
