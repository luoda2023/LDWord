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
