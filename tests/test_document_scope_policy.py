from src.config.document_scope import (
    DocumentScopePolicy,
    document_scope_policy_issue,
    selectable_document_scope_roles,
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
