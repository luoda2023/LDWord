from __future__ import annotations

from src.ui.panels.workbench.document_execution_state import (
    resolve_document_execution_topology,
)
from src.ui.panels.workbench.output_location_card import OutputLocationCard
from src.ui.panels.workbench.output_path_policy import (
    default_workbench_output_root,
    next_available_workbench_output_root,
    resolve_workbench_output_root,
)


def test_single_document_output_root_uses_the_source_name(tmp_path):
    source = tmp_path / "项目报告.docx"

    output = default_workbench_output_root((source,))

    assert output == (tmp_path / "项目报告-输出").resolve()


def test_same_folder_batch_uses_the_source_folder_name(tmp_path):
    source_dir = tmp_path / "项目甲"

    output = default_workbench_output_root(
        (source_dir / "一.docx", source_dir / "二.docx")
    )

    assert output == (tmp_path / "项目甲-输出").resolve()


def test_custom_output_root_is_kept_exact(tmp_path):
    selected = tmp_path / "我的交付目录"

    output = resolve_workbench_output_root(
        selected,
        (tmp_path / "source.docx",),
    )

    assert output == selected.resolve()


def test_existing_default_output_root_uses_the_next_free_number(tmp_path):
    source = tmp_path / "source.docx"
    first = tmp_path / "source-输出"
    second = tmp_path / "source-输出 (2)"
    first.mkdir()
    second.mkdir()

    output = resolve_workbench_output_root("", (source,))

    assert output == (tmp_path / "source-输出 (3)").resolve()


def test_available_output_root_does_not_modify_an_existing_folder(tmp_path):
    existing = tmp_path / "delivery"
    marker = existing / "keep.txt"
    existing.mkdir()
    marker.write_text("previous result", encoding="utf-8")

    output = next_available_workbench_output_root(existing)

    assert output == (tmp_path / "delivery (2)").resolve()
    assert marker.read_text(encoding="utf-8") == "previous result"


def test_output_card_previews_the_actual_default_folder(qapp, tmp_path):
    source = tmp_path / "项目报告.docx"
    card = OutputLocationCard()
    try:
        card.set_source_paths((str(source),))
        card.set_topology(
            resolve_document_execution_topology(
                document_paths=(str(source),),
            )
        )

        assert card._preview.text() == "项目报告-输出 · 1 份"
        assert card._preview.toolTip() == str(
            (tmp_path / "项目报告-输出").resolve()
        )
    finally:
        card.close()
