import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from docx import Document

from src.config.section_semantics import canonicalize_section_type, style_key_for_section
from src.modules.basic.paragraph_style import _resolve_style_key
from src.modules.structure.heading_recognition import _detect_special_section


def test_canonicalize_section_type_merges_acknowledgment_and_resume_aliases():
    assert canonicalize_section_type("acknowledgements") == "acknowledgment"
    assert canonicalize_section_type("acknowledgement") == "acknowledgment"
    assert canonicalize_section_type("bio") == "resume"


def test_style_key_for_section_routes_body_variants_to_canonical_style_keys():
    assert style_key_for_section("references") == "references_body"
    assert style_key_for_section("acknowledgements") == "acknowledgment_body"
    assert style_key_for_section("bio") == "resume_body"
    assert style_key_for_section("abstract_en") == "abstract_body"


def test_heading_recognition_special_sections_use_canonical_ids():
    assert _detect_special_section("致谢") == "acknowledgment"
    assert _detect_special_section("Acknowledgements") == "acknowledgment"
    assert _detect_special_section("个人简历") == "resume"


def test_paragraph_style_resolve_style_key_uses_canonical_section_mapping():
    doc = Document()
    para = doc.add_paragraph("致谢内容")
    context = SimpleNamespace(
        doc_tree=SimpleNamespace(get_section_for_paragraph=lambda _index: "acknowledgements")
    )

    assert _resolve_style_key(para, context) == "acknowledgment_body"
