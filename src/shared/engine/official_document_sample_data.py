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
        "resolution": {
            "title": "关于加强档案数字化建设的决议",
            "body": "会议审议并通过档案数字化建设方案，决定分阶段组织实施。",
            "organization": "示例市档案工作委员会",
            "document_no": "示档委〔2026〕1号",
            "recipient": "各成员单位",
        },
        "decision": {
            "title": "关于表彰档案工作先进集体的决定",
            "body": "为树立典型、激励担当，决定对有关先进集体予以表彰。",
            "document_no": "示档发〔2026〕6号",
            "recipient": "各区县档案主管部门",
        },
        "bulletin": {
            "title": "示例市档案事业发展情况公报",
            "body": "现将本市档案事业年度发展情况予以公布。",
            "document_no": "",
            "recipient": "",
            "attachment_note": "",
        },
        "announcement": {
            "title": "关于开放一批馆藏档案的公告",
            "body": "经鉴定审核，现依法向社会开放一批馆藏档案。",
            "document_no": "",
            "recipient": "",
            "attachment_note": "开放档案目录",
        },
        "notice_public": {
            "title": "关于档案馆临时调整开放时间的通告",
            "body": "因设施维护，档案馆开放时间临时调整，现将有关事项通告如下。",
            "document_no": "",
            "recipient": "",
            "attachment_note": "",
        },
        "opinion": {
            "title": "关于推进基层档案规范化建设的意见",
            "body": "为提升基层档案治理能力，现就规范化建设提出如下意见。",
            "document_no": "示档发〔2026〕7号",
            "recipient": "各区县档案主管部门",
        },
        "notice": {
            "title": "关于开展资料归档检查的通知",
            "body": "请各部门按要求完成自查，并于本周五前提交归档材料。",
        },
        "circular": {
            "title": "关于年度档案执法检查情况的通报",
            "body": "现将年度档案执法检查总体情况、发现问题和整改要求予以通报。",
            "document_no": "示档发〔2026〕9号",
            "recipient": "各区县档案主管部门",
        },
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
