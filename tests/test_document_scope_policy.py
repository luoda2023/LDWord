from src.config.document_scope import (
    DocumentScopePolicy,
    document_scope_policy_issue,
    selectable_document_scope_roles,
)
from src.qt_api import QLabel
from src.ui.panels.scene_scope_sections import (
    DOCUMENT_SCOPE_MODE_HELP,
    DOCUMENT_SCOPE_MODE_OPTIONS,
    DOCUMENT_SCOPE_ROLE_NOTE,
)


def test_document_scope_policy_projects_only_plan_intent():
    policy = DocumentScopePolicy(
        mode="selected",
        selected_roles=("references", "body", "references"),
    )

    assert policy.selected_roles == ["references", "body"]
    assert policy.included_roles("thesis") == ("body", "references")
    assert not hasattr(policy, "page_ranges_text")
    assert not hasattr(policy, "source_path")


def test_document_scope_policy_fails_closed_for_unknown_or_empty_selection():
    assert (
        document_scope_policy_issue(
            DocumentScopePolicy(mode="future"),
            mode_id="thesis",
        )
        == "document_scope_mode_invalid:future"
    )
    assert (
        document_scope_policy_issue(
            DocumentScopePolicy(mode="selected"),
            mode_id="thesis",
        )
        == "document_scope_selected_roles_missing"
    )


def test_document_scope_roles_are_mode_specific_and_master_modes_have_no_selector():
    assert "resume" in selectable_document_scope_roles("thesis")
    assert "resume" not in selectable_document_scope_roles("technical")
    assert selectable_document_scope_roles("official") == ()
    assert selectable_document_scope_roles("exam") == ()


def test_document_scope_policy_rejects_roles_from_another_mode():
    issue = document_scope_policy_issue(
        DocumentScopePolicy(mode="selected", selected_roles=("resume",)),
        mode_id="technical",
    )

    assert issue == "document_scope_roles_unsupported:resume"


def test_document_scope_copy_distinguishes_plan_capability_from_file_structure():
    assert dict(DOCUMENT_SCOPE_MODE_OPTIONS)["selected"] == "自选区域"
    assert "实际存在" in DOCUMENT_SCOPE_MODE_HELP["selected"]
    assert "不代表每份文件都包含" in DOCUMENT_SCOPE_ROLE_NOTE
    assert "不会被创建或处理" in DOCUMENT_SCOPE_ROLE_NOTE


def test_scope_section_keeps_explanation_when_mode_specific_roles_are_rebuilt():
    from src.ui.panels.scene_scope_sections import DocumentScopeSection

    section = DocumentScopeSection()
    section.set_mode_id("thesis")
    section.set_mode_id("custom")

    note = section.findChild(QLabel, "scn_document_scope_roles_note")
    assert note is not None
    assert note.text() == DOCUMENT_SCOPE_ROLE_NOTE
    assert tuple(section._role_checks) == (  # noqa: SLF001 - UI regression contract
        "toc",
        "body",
        "references",
        "appendix",
    )
