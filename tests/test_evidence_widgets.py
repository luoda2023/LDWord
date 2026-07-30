import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui.evidence_widgets import (
    EvidenceActionBar,
    EvidenceLineItem,
    EvidenceLineList,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_evidence_line_list_projects_readable_rows():
    _app()
    widget = EvidenceLineList()
    try:
        widget.set_items(
            [
                EvidenceLineItem(kind="parameter_path", label="参数", text="body.font"),
                EvidenceLineItem(
                    kind="evidence_file",
                    label="证据文件",
                    text="src/shared/ui/paragraph_style_inputs.py:120",
                    action_type="open_evidence",
                    action_value="src/shared/ui/paragraph_style_inputs.py:120",
                ),
            ]
        )

        assert widget.line_count() == 2
        assert widget.text_at(0) == "参数：body.font"
        assert widget.text_at(1).startswith("证据文件：src/shared/ui")
        assert widget.current_items()[1].has_action()
    finally:
        widget.close()


def test_evidence_line_list_reconciles_rows_by_stable_identity():
    _app()
    widget = EvidenceLineList()
    try:
        parameter = EvidenceLineItem(
            kind="parameter_path",
            label="参数",
            text="body.font",
        )
        evidence = EvidenceLineItem(
            kind="evidence_file",
            label="证据文件",
            text="before.py:10",
        )
        widget.set_items([parameter, evidence])
        parameter_row, evidence_row = widget._rows

        updated_parameter = EvidenceLineItem(
            kind="parameter_path",
            label="参数",
            text="body.font_size",
            tone="primary",
        )
        output = EvidenceLineItem(
            kind="output_file",
            label="输出文件",
            text="result.docx",
        )
        widget.set_items([updated_parameter, evidence, output])

        assert widget._rows[0] is parameter_row
        assert widget._rows[1] is evidence_row
        output_row = widget._rows[2]
        assert parameter_row._body.text() == "body.font_size"

        widget.set_items([output, updated_parameter])

        assert widget._rows == [output_row, parameter_row]
        assert evidence_row not in widget._rows
        assert output_row.parent() is widget
        assert parameter_row.parent() is widget
        assert evidence_row.parent() is None
    finally:
        widget.close()


def test_evidence_line_list_retained_action_uses_latest_item_content():
    _app()
    widget = EvidenceLineList(show_inline_actions=True)
    requested: list[tuple[str, str]] = []
    try:
        widget.action_requested.connect(
            lambda action_type, action_value: requested.append(
                (action_type, action_value)
            )
        )
        original = EvidenceLineItem(
            kind="evidence_file",
            label="证据文件",
            text="before.py:10",
            action_type="open_evidence",
            action_value="before.py:10",
            action_label="打开证据",
        )
        widget.set_items([original])
        original_row = widget._rows[0]

        updated = EvidenceLineItem(
            kind="evidence_file",
            label="来源文件",
            text="before.py:20",
            action_type="open_evidence",
            action_value="before.py:10",
            action_label="查看来源",
            tone="info",
        )
        widget.set_items([updated])

        assert widget._rows[0] is original_row
        assert original_row._label.text() == "来源文件"
        assert original_row._body.text() == "before.py:20"
        assert original_row._action_btn is not None
        assert original_row._action_btn.text() == "查看来源"

        original_row._action_btn.click()
        assert requested == [("open_evidence", "before.py:10")]
    finally:
        widget.close()


def test_evidence_action_bar_dedupes_and_emits_actions():
    _app()
    bar = EvidenceActionBar()
    requested: list[tuple[str, str]] = []
    try:
        bar.action_requested.connect(
            lambda action_type, action_value: requested.append(
                (action_type, action_value)
            )
        )
        bar.set_actions(
            [
                EvidenceLineItem(
                    kind="parameter_path",
                    label="参数",
                    text="body.font",
                    action_type="navigate_parameter",
                    action_value="body.font",
                    action_label="定位参数",
                ),
                EvidenceLineItem(
                    kind="parameter_path",
                    label="参数",
                    text="body.font",
                    action_type="navigate_parameter",
                    action_value="body.font",
                    action_label="定位参数",
                ),
                EvidenceLineItem(
                    kind="evidence_file",
                    label="证据文件",
                    text="src/shared/ui/paragraph_style_inputs.py:120",
                    action_type="open_evidence",
                    action_value="src/shared/ui/paragraph_style_inputs.py:120",
                    action_label="打开证据",
                ),
            ]
        )

        assert bar.current_actions() == [
            ("parameter_path", "navigate_parameter", "body.font"),
            (
                "evidence_file",
                "open_evidence",
                "src/shared/ui/paragraph_style_inputs.py:120",
            ),
        ]
        parameter_button = bar.button_for_action_type("navigate_parameter")
        evidence_button = bar.button_for_action_type("open_evidence")
        assert parameter_button is not None
        assert evidence_button is not None
        assert parameter_button.text() == "定位参数"
        assert evidence_button.text() == "打开证据"

        parameter_button.click()
        evidence_button.click()

        assert requested == [
            ("navigate_parameter", "body.font"),
            ("open_evidence", "src/shared/ui/paragraph_style_inputs.py:120"),
        ]
    finally:
        bar.close()


def test_evidence_action_bar_reconciles_buttons_and_emits_latest_target():
    _app()
    bar = EvidenceActionBar()
    requested: list[tuple[str, str]] = []
    try:
        bar.action_requested.connect(
            lambda action_type, action_value: requested.append(
                (action_type, action_value)
            )
        )
        parameter = EvidenceLineItem(
            kind="parameter_path",
            label="参数",
            text="body.font",
            action_type="navigate_parameter",
            action_value="body.font",
            action_label="定位参数",
        )
        evidence = EvidenceLineItem(
            kind="evidence_file",
            label="证据文件",
            text="source.py:10",
            action_type="open_evidence",
            action_value="source.py:10",
            action_label="打开证据",
        )
        bar.set_actions([parameter, evidence])
        parameter_button = bar.button_for_action_type("navigate_parameter")
        evidence_button = bar.button_for_action_type("open_evidence")
        assert parameter_button is not None
        assert evidence_button is not None

        updated_parameter = EvidenceLineItem(
            kind="parameter_path",
            label="参数",
            text="heading.font",
            action_type="navigate_parameter",
            action_value="heading.font",
            action_label="定位标题参数",
        )
        output = EvidenceLineItem(
            kind="output_file",
            label="输出文件",
            text="result.docx",
            action_type="open_output",
            action_value="result.docx",
            action_label="打开输出",
        )
        bar.set_actions([updated_parameter, evidence, output])

        assert bar.button_for_action_type("navigate_parameter") is parameter_button
        assert bar.button_for_action_type("open_evidence") is evidence_button
        output_button = bar.button_for_action_type("open_output")
        assert output_button is not None
        assert output_button not in (parameter_button, evidence_button)
        assert parameter_button.text() == "定位标题参数"
        parameter_button.click()
        assert requested == [("navigate_parameter", "heading.font")]

        bar.set_actions([output, updated_parameter])

        assert bar._button_controller.widgets() == (
            output_button,
            parameter_button,
        )
        assert output_button.parent() is bar
        assert parameter_button.parent() is bar
        assert evidence_button.parent() is None
        assert bar.button_for_action_type("open_evidence") is None
        tail_item = bar._layout.itemAt(bar._layout.count() - 1)
        assert tail_item is not None
        assert tail_item.spacerItem() is not None
    finally:
        bar.close()
