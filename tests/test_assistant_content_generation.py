from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from src.assistant.adapters.content_generation_adapter import (
    AssistantContentGenerationAdapter,
)
from src.assistant.application.content_generation_service import (
    AssistantContentGenerationService,
    ContentGenerationRequest,
)
from src.assistant.contracts.permissions import DisclosureGrant
from src.assistant.runtime.mock_provider import MockModelGateway
from src.assistant.runtime.provider_contract import (
    PROVIDER_DONE,
    PROVIDER_START,
    PROVIDER_TEXT_DELTA,
    ProviderStreamEvent,
)


def test_generated_markdown_compiles_to_fragment_and_reviewable_docx(tmp_path):
    draft = AssistantContentGenerationAdapter(tmp_path).compile_and_compose(
        session_id="session-1",
        markdown="# 项目报告\n\n## 结论\n\n- 第一项\n- 第二项\n",
    )

    assert Path(draft.markdown_path).is_file()
    assert Path(draft.document_path).is_file()
    assert [block["kind"] for block in draft.fragment["blocks"]] == [
        "heading",
        "heading",
        "list",
    ]
    assert len(draft.fragment_digest) == 64
    assert len(draft.compose_receipt_id) == 64


def test_generated_content_rejects_direct_ooxml(tmp_path):
    adapter = AssistantContentGenerationAdapter(tmp_path)

    with pytest.raises(ValueError, match="direct_ooxml_is_forbidden"):
        adapter.compile_and_compose(
            session_id="session-1",
            markdown="<w:document>not allowed</w:document>",
        )


@pytest.mark.parametrize(
    ("markdown", "expected_code"),
    (
        (
            "# 投标文件\n\n"
            "{{@text:company_name}}\n"
            "{{@text:project_name}}\n"
            "{{@text:legal_person}}\n",
            "required_section_missing:project_understanding",
        ),
        (
            "# 投标文件\n\n"
            "{{@text:company_name}}\n"
            "{{@text:project_name}}\n"
            "{{@text:legal_person}}\n\n"
            "## 项目理解\n\n内容\n\n"
            "## 响应内容\n\n内容\n\n"
            "## 实施方案\n\n内容\n\n"
            "## 承诺事项\n\n{{@img:LOGO1}}\n",
            "provider_owned_image_token_forbidden",
        ),
    ),
)
def test_bidding_draft_fails_closed_on_domain_contract_violations(
    tmp_path,
    markdown,
    expected_code,
):
    adapter = AssistantContentGenerationAdapter(tmp_path)

    with pytest.raises(ValueError, match=expected_code):
        adapter.compile_and_compose(
            session_id="session-bidding-invalid",
            markdown=markdown,
            prompt_profile_id="assistant.bidding-markdown.v1",
        )


def test_context_cannot_reach_provider_without_exact_disclosure_grant(tmp_path):
    with pytest.raises(PermissionError, match="not_authorized"):
        ContentGenerationRequest(
            session_id="session-1",
            turn_id="turn-1",
            prompt="起草报告",
            provider_id="cloud-main",
            model_id="model-a",
            context_text="confidential body",
            context_refs=("doc-1",),
            context_fields=("paragraphs",),
            context_fingerprints=(("doc-1", "hash-a"),),
        )

    wrong_model = DisclosureGrant(
        grant_id="grant-1",
        session_id="session-1",
        provider_id="cloud-main",
        model_id="model-b",
        allowed_refs=("doc-1",),
        allowed_fields=("paragraphs",),
        content_fingerprints={"doc-1": "hash-a"},
    )
    with pytest.raises(PermissionError, match="not_authorized"):
        ContentGenerationRequest(
            session_id="session-1",
            turn_id="turn-1",
            prompt="起草报告",
            provider_id="cloud-main",
            model_id="model-a",
            context_text="confidential body",
            context_refs=("doc-1",),
            context_fields=("paragraphs",),
            context_fingerprints=(("doc-1", "hash-a"),),
            disclosure_grant=wrong_model,
        )


def test_prompt_only_generation_uses_provider_then_local_compiler(tmp_path):
    service = AssistantContentGenerationService(
        AssistantContentGenerationAdapter(tmp_path)
    )
    request = ContentGenerationRequest(
        session_id="session-1",
        turn_id="turn-1",
        prompt="生成一份项目报告",
        provider_id="mock-default",
        model_id="form-assistant-mock",
    )

    draft = service.generate(request, MockModelGateway())

    assert Path(draft.document_path).is_file()
    assert draft.fragment["blocks"]


def test_material_generation_extracts_authorized_docx_in_worker_context(tmp_path):
    material = tmp_path / "confidential-brief.docx"
    document = Document()
    document.add_paragraph("Approved material fact: launch is in October.")
    document.save(material)

    class CapturingGateway:
        def __init__(self) -> None:
            self.request = None

        def stream(self, request):
            self.request = request
            yield ProviderStreamEvent(PROVIDER_START)
            yield ProviderStreamEvent(PROVIDER_TEXT_DELTA, text="# Draft\n\nGenerated body")
            yield ProviderStreamEvent(PROVIDER_DONE)

        def cancel(self) -> bool:
            return True

    reference = str(material)
    grant = DisclosureGrant(
        grant_id="grant-material",
        session_id="session-material",
        provider_id="cloud-main",
        model_id="model-a",
        allowed_refs=(reference,),
        allowed_fields=("document_text",),
    )
    request = ContentGenerationRequest(
        session_id="session-material",
        turn_id="turn-material",
        prompt="Generate a launch report",
        provider_id="cloud-main",
        model_id="model-a",
        context_documents=({"title": material.name, "path": reference},),
        context_refs=(reference,),
        context_fields=("document_text",),
        disclosure_grant=grant,
    )
    gateway = CapturingGateway()

    draft = AssistantContentGenerationService(
        AssistantContentGenerationAdapter(tmp_path / "outputs")
    ).generate(request, gateway)

    assert Path(draft.document_path).is_file()
    assert gateway.request is not None
    provider_text = gateway.request.messages[0]["content"]
    assert "launch is in October" in provider_text
    assert str(tmp_path) not in provider_text
