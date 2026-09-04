from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

_PPR_TAG = f"{{{_W_NS}}}pPr"
_RUN_TAG = f"{{{_W_NS}}}r"
_PROOF_ERR_TAG = f"{{{_W_NS}}}proofErr"
_BOOKMARK_START_TAG = f"{{{_W_NS}}}bookmarkStart"
_BOOKMARK_END_TAG = f"{{{_W_NS}}}bookmarkEnd"
_OMATH_TAG = f"{{{_M_NS}}}oMath"
_OMATH_PARA_TAG = f"{{{_M_NS}}}oMathPara"

_PRESERVED_MARKER_TAGS = {
    _BOOKMARK_START_TAG,
    _BOOKMARK_END_TAG,
}

_REMOVABLE_CONTENT_TAGS = {
    _RUN_TAG,
    _PROOF_ERR_TAG,
    _OMATH_TAG,
    _OMATH_PARA_TAG,
}


@dataclass(frozen=True)
class ParagraphRewriteResult:
    applied: bool
    reason: str = ""


def replace_paragraph_payload_with_omml(paragraph_el, omml_element) -> ParagraphRewriteResult:
    """Replace paragraph payload while preserving safe bookmark markers.

    This helper is intentionally conservative: if the paragraph contains
    unsupported direct-child markup, it refuses to rewrite instead of risking
    semantic corruption.
    """

    if paragraph_el is None or omml_element is None:
        return ParagraphRewriteResult(False, "missing_input")

    omml_copy = deepcopy(omml_element)
    local = omml_copy.tag.split("}")[-1] if "}" in omml_copy.tag else omml_copy.tag
    if local == "oMathPara":
        inline_math = omml_copy.find(_OMATH_TAG)
        if inline_math is None:
            return ParagraphRewriteResult(False, "missing_inline_math")
        omml_copy = deepcopy(inline_math)
    elif local != "oMath":
        return ParagraphRewriteResult(False, "unsupported_omml_root")

    first_content_index = None
    removable_children = []

    for idx, child in enumerate(list(paragraph_el)):
        if child.tag == _PPR_TAG or child.tag in _PRESERVED_MARKER_TAGS:
            continue
        if child.tag not in _REMOVABLE_CONTENT_TAGS:
            return ParagraphRewriteResult(False, "unsupported_paragraph_markup")
        removable_children.append(child)
        if first_content_index is None:
            first_content_index = idx

    if first_content_index is None:
        first_content_index = len(paragraph_el)

    for child in removable_children:
        paragraph_el.remove(child)

    # Inline native math is a direct paragraph child.  m:oMathPara belongs at
    # block/container level and w:r cannot contain m:oMath.
    paragraph_el.insert(min(first_content_index, len(paragraph_el)), omml_copy)
    return ParagraphRewriteResult(True, "applied")
