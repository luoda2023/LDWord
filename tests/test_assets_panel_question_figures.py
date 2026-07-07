import json

from src.config.materials import AssetItem
from src.ui.panels import assets_panel
from src.ui.panels.assets import question_figures


def test_question_figure_helpers_are_compatibly_exported_from_assets_panel():
    assert (
        assets_panel._question_figure_asset_items
        is question_figures._question_figure_asset_items
    )
    assert (
        assets_panel._asset_item_library_asset_id
        is question_figures._asset_item_library_asset_id
    )
    assert not hasattr(assets_panel, "_asset_item_remote_asset_id")
    assert not hasattr(question_figures, "_asset_item_remote_asset_id")
    assert not hasattr(question_figures, "asset_item_remote_asset_id")


def test_question_figure_helpers_sort_and_match_local_items(tmp_path):
    q2_path = tmp_path / "q2.png"
    q1_path = tmp_path / "q1.png"
    q2_path.write_bytes(b"q2")
    q1_path.write_bytes(b"q1")

    q2 = AssetItem(
        item_id="q2",
        label="Question 2",
        role="question_figure",
        path=str(q2_path),
        metadata={
            "question_index": "2",
            "figure_order": "1",
            "asset_id": "library-q2",
            "alt_text": "diagram",
        },
    )
    q1 = AssetItem(
        item_id="q1",
        label="Question 1",
        role="question_figure",
        path=str(q1_path),
        metadata={"question_index": "1", "asset_id": "library-q1"},
    )
    logo = AssetItem(item_id="logo", label="Logo", role="logo", path=str(q1_path))

    question_items = question_figures._question_figure_asset_items([q2, logo, q1])

    assert [item.item_id for item in question_items] == ["q1", "q2"]
    assert question_figures._asset_item_alt_text(q2) == "diagram"
    assert question_figures._asset_item_library_asset_id(q2) == "library-q2"
    assert question_figures._asset_item_preview_reference(q2) == str(q2_path)
    assert question_figures._question_figure_payload_matches_item(
        {"role": "question_figure", "metadata": {"question_index": "2"}},
        q2,
    )


def test_question_figure_helpers_parse_repair_targets():
    payload = {
        "role": "question_figure",
        "path": "cache/q3.png",
        "metadata": {"question_index": "3", "asset_id": "library-q3"},
    }

    target = question_figures._question_figure_repair_target_payload(
        json.dumps(payload)
    )

    assert target["role"] == "question_figure"
    assert target["question_index"] == "3"
    assert target["asset_id"] == "library-q3"
    assert question_figures._question_figure_repair_target_payload(
        "question_figure:7"
    ) == {"role": "question_figure", "question_index": "7"}
