import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.modules.structure.heading_recognition import DocSection, DocTree
from src.shared.engine.sequence_numbering import (
    build_heading_chapter_ranges,
    resolve_chapter_number,
)


def test_build_heading_chapter_ranges_only_counts_body_h1_anchors():
    doc_tree = DocTree(
        sections=[
            DocSection("abstract_cn", 0, 2),
            DocSection("body", 2, 6),
            DocSection("references", 6, 8),
        ]
    )
    heading_map = {
        0: 1,
        2: 1,
        4: 1,
        6: 1,
    }

    ranges = build_heading_chapter_ranges(
        heading_map,
        8,
        doc_tree=doc_tree,
    )

    assert ranges == [
        (2, 3, 1),
        (4, 5, 2),
    ]


def test_resolve_chapter_number_returns_zero_outside_body_scoped_ranges():
    doc_tree = DocTree(
        sections=[
            DocSection("toc", 0, 2),
            DocSection("body", 2, 5),
            DocSection("appendix", 5, 7),
        ]
    )
    heading_map = {
        0: 1,
        2: 1,
        5: 1,
    }

    ranges = build_heading_chapter_ranges(
        heading_map,
        7,
        doc_tree=doc_tree,
    )

    assert ranges == [(2, 4, 1)]
    assert resolve_chapter_number(1, ranges) == 0
    assert resolve_chapter_number(3, ranges) == 1
    assert resolve_chapter_number(5, ranges) == 0
