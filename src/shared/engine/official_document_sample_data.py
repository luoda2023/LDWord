"""Deterministic sample material shared by official previews and verification."""

from __future__ import annotations


def official_sample_entity_data(profile_id: str) -> dict[str, str]:
    normalized = str(profile_id or "notice").strip() or "notice"
    data = {
        "document_type": normalized,
        "title": "关于开展资料归档检查的通知",
        "body": "请各部门按要求完成自查，并于本周五前提交归档材料。",
        "organization": "示例市档案局",
        "document_no": "示档发〔2026〕5号",
        "recipient": "各部门",
        "attachment_note": "资料归档检查清单",
        "issuer": "示例市档案局",
        "issue_date": "2026年7月10日",
        "copy_scope": "办公室",
        "printing_org": "示例市档案局办公室",
        "printing_date": "2026年7月10日",
        "security_level": "",
        "urgency": "",
        "signer": "",
    }
    variants = {
        "letter": {
            "title": "关于商请协助提供归档材料的函",
            "body": "为推进资料归集工作，现商请贵单位协助提供相关归档材料。",
            "document_no": "示档函〔2026〕3号",
            "recipient": "有关单位",
            "attachment_note": "归档材料目录",
        },
        "minutes": {
            "title": "专题协调会议纪要",
            "body": "会议研究了近期资料归档和流程优化事项。",
            "document_no": "会议纪要〔2026〕2号",
            "meeting_date": "2026年7月10日上午",
            "participants": "张三、李四、王五",
            "attachment_note": "会议任务清单",
        },
        "report": {
            "title": "关于年度资料归档工作情况的报告",
            "body": "现将年度资料归档工作开展情况、存在问题和下一步安排报告如下。",
            "document_no": "示档报〔2026〕8号",
            "recipient": "示例市人民政府",
            "attachment_note": "",
            "signer": "张明",
        },
        "request": {
            "title": "关于升级电子档案管理系统的请示",
            "body": "为提升电子档案归集和利用效率，拟对现有管理系统进行升级。妥否，请批示。",
            "document_no": "示档请〔2026〕4号",
            "recipient": "示例市人民政府",
            "attachment_note": "电子档案管理系统升级方案",
            "signer": "张明",
        },
        "approval": {
            "title": "关于电子档案管理系统升级事项的批复",
            "body": "你局有关请示收悉。经研究，同意按程序推进电子档案管理系统升级工作。",
            "organization": "示例市人民政府",
            "document_no": "示政复〔2026〕12号",
            "recipient": "示例市档案局",
            "issuer": "示例市人民政府",
            "attachment_note": "",
        },
        "order": {
            "title": "关于公布档案管理办法的命令",
            "body": "现公布《示例市档案管理办法》，自公布之日起施行。",
            "organization": "示例市人民政府",
            "document_no": "第1号",
            "issuer": "",
            "recipient": "",
            "attachment_note": "",
            "copy_scope": "",
            "printing_org": "",
            "printing_date": "",
            "signer": "市长 张明",
        },
        "proposal": {
            "title": "关于提请审议档案管理条例草案的议案",
            "body": "现提请审议《示例市档案管理条例（草案）》。",
            "organization": "示例市人民政府",
            "document_no": "示政案〔2026〕1号",
            "recipient": "示例市人民代表大会常务委员会",
            "attachment_note": "示例市档案管理条例（草案）",
            "signer": "市长 张明",
        },
    }
    data.update(variants.get(normalized, {}))
    return data


__all__ = ["official_sample_entity_data"]
