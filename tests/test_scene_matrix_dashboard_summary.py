import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ui.panels.scene_summary_projection import (  # noqa: E402
    build_scene_matrix_dashboard_summary_items,
)


def test_scene_summary_projection_exposes_dashboard_cards():
    items = {
        item.key: item for item in build_scene_matrix_dashboard_summary_items()
    }

    assert items["scene_matrix_dashboard"].value == "12/12 packs"
    assert "high_frequency_coverage=12/12" in items["scene_matrix_dashboard"].detail
    assert "15 families" in items["scene_matrix_dashboard"].detail
    assert "11/11 P1 fixtures" in items["scene_matrix_dashboard"].detail
    assert "29 task families" in items["scene_matrix_dashboard"].detail
    assert "6 ambiguous pairs" in items["scene_matrix_dashboard"].detail
    assert "6/6 clarifications" in items["scene_matrix_dashboard"].detail
    assert "1 handoff" in items["scene_matrix_dashboard"].detail
    assert "12/12 input packs" in items["scene_matrix_dashboard"].detail
    assert "53 request cells" in items["scene_matrix_dashboard"].detail
    assert "100 user journeys" in items["scene_matrix_dashboard"].detail
    assert "18/18 business capabilities" in items["scene_matrix_dashboard"].detail
    assert "6/6 external handoffs" in items["scene_matrix_boundary"].detail
    assert "6/6 guarded" in items["scene_matrix_boundary"].detail
    assert "10/10 managed warnings" in items["scene_matrix_boundary"].detail
    assert "5/5 input warnings managed" in items["scene_matrix_boundary"].detail
    assert "2/2 count warnings managed" in items["scene_matrix_boundary"].detail
    assert "5/5 plugin/manual warnings managed" in items["scene_matrix_boundary"].detail
    assert "2/2 reference warnings managed" in items["scene_matrix_boundary"].detail
    assert "1/1 Visio fixture closed" in items["scene_matrix_boundary"].detail
    assert "3/3 dashboard warnings governed" in items["scene_matrix_boundary"].detail
    assert "15/15 readiness reconciled" in items["scene_matrix_boundary"].detail
    assert "5/5 release exceptions" in items["scene_matrix_boundary"].detail
    assert "2/2 static-closed governed" in items["scene_matrix_boundary"].detail
    assert "36 exception traces" in items["scene_matrix_boundary"].detail
    assert "6/6 boundary dossiers" in items["scene_matrix_boundary"].detail
    assert "10/10 non-subject traces" in items["scene_matrix_boundary"].detail
    assert "36/36 trace partition" in items["scene_matrix_boundary"].detail
    assert "13/13 release projections" in items["scene_matrix_boundary"].detail
    assert "6/6 subject continuity" in items["scene_matrix_boundary"].detail
    assert "13/13 release ledger" in items["scene_matrix_boundary"].detail
    assert "6/6 boundary release envelopes" in items["scene_matrix_boundary"].detail
    assert "6/6 L5 blockers enveloped" in items["scene_matrix_boundary"].detail
    assert "6/6 L5 blockers aligned" in items["scene_matrix_boundary"].detail
    assert "6/6 L5 receipts aligned" in items["scene_matrix_boundary"].detail
    assert "6/6 retained gaps enveloped" in items["scene_matrix_boundary"].detail
    assert "6/6 retained gap exit criteria" in items["scene_matrix_boundary"].detail
    assert "6/6 retained gap receipts" in items["scene_matrix_boundary"].detail
    assert "3/3 gap domains classified" in items["scene_matrix_boundary"].detail
    assert "3/3 release residual ratios" in items["scene_matrix_boundary"].detail
    assert "10 residual ratio exit criteria" in items["scene_matrix_boundary"].detail
    assert "10 residual ratio receipts" in items["scene_matrix_boundary"].detail
    assert (
        "4/4 count/delivery boundary links aligned"
        in items["scene_matrix_boundary"].detail
    )
    assert (
        "4/4 count/delivery receipts aligned"
        in items["scene_matrix_boundary"].detail
    )
    assert "6/6 boundary scopes guarded" in items["scene_matrix_boundary"].detail
    assert "14/14 residual explanations" in items["scene_matrix_boundary"].detail
    assert "14/14 release acceptance certificate" in items["scene_matrix_boundary"].detail
    assert "2/2 receipt certificates" in items["scene_matrix_boundary"].detail
    assert "10/10 requirement dimensions" in items["scene_matrix_boundary"].detail
    assert "15/15 acceptance evidence" in items["scene_matrix_boundary"].detail
    assert "6/6 handoff contracts" in items["scene_matrix_evidence"].detail
    assert "6/6 guarded completions" in items["scene_matrix_evidence"].detail
    assert "10/10 managed warnings" in items["scene_matrix_evidence"].detail
    assert "5/5 input warnings managed" in items["scene_matrix_evidence"].detail
    assert "2/2 count warnings managed" in items["scene_matrix_evidence"].detail
    assert "5/5 plugin/manual warnings managed" in items["scene_matrix_evidence"].detail
    assert "2/2 reference warnings managed" in items["scene_matrix_evidence"].detail
    assert "1/1 Visio fixture closed" in items["scene_matrix_evidence"].detail
    assert "3/3 dashboard warnings governed" in items["scene_matrix_evidence"].detail
    assert "15/15 readiness reconciled" in items["scene_matrix_evidence"].detail
    assert "5/5 release exceptions" in items["scene_matrix_evidence"].detail
    assert "2/2 static-closed governed" in items["scene_matrix_evidence"].detail
    assert "36 exception traces" in items["scene_matrix_evidence"].detail
    assert "6/6 boundary dossiers" in items["scene_matrix_evidence"].detail
    assert "10/10 non-subject traces" in items["scene_matrix_evidence"].detail
    assert "36/36 trace partition" in items["scene_matrix_evidence"].detail
    assert "13/13 release projections" in items["scene_matrix_evidence"].detail
    assert "6/6 subject continuity" in items["scene_matrix_evidence"].detail
    assert "13/13 Release closure ledger" in items["scene_matrix_evidence"].detail
    assert "6/6 boundary release envelopes" in items["scene_matrix_evidence"].detail
    assert "6/6 L5 blockers enveloped" in items["scene_matrix_evidence"].detail
    assert "6/6 L5 blockers aligned" in items["scene_matrix_evidence"].detail
    assert "6/6 L5 receipts aligned" in items["scene_matrix_evidence"].detail
    assert "6/6 retained gaps enveloped" in items["scene_matrix_evidence"].detail
    assert "6/6 retained gap exit criteria" in items["scene_matrix_evidence"].detail
    assert "3/3 gap domains classified" in items["scene_matrix_evidence"].detail
    assert "3/3 release residual ratios" in items["scene_matrix_evidence"].detail
    assert "10 residual ratio exit criteria" in items["scene_matrix_evidence"].detail
    assert "10 residual ratio receipts" in items["scene_matrix_evidence"].detail
    assert (
        "4/4 count/delivery boundary links aligned"
        in items["scene_matrix_evidence"].detail
    )
    assert (
        "4/4 count/delivery receipts aligned"
        in items["scene_matrix_evidence"].detail
    )
    assert "6/6 boundary scopes guarded" in items["scene_matrix_evidence"].detail
    assert "14/14 residual explanations" in items["scene_matrix_evidence"].detail
    assert "14/14 release acceptance certificate" in items["scene_matrix_evidence"].detail
    assert "2/2 receipt certificates" in items["scene_matrix_evidence"].detail
    assert "10/10 requirement dimensions" in items["scene_matrix_evidence"].detail
    assert "15/15 acceptance evidence" in items["scene_matrix_evidence"].detail
    assert items["scene_matrix_boundary"].value == "4 plugin packs"
    assert "4 manual-boundary packs" in items["scene_matrix_boundary"].detail
    assert "6 ambiguous pairs" in items["scene_matrix_boundary"].detail
    assert "1 handoff" in items["scene_matrix_boundary"].detail
    assert "4 gates" in items["scene_matrix_boundary"].detail
    assert "14 risk domains" in items["scene_matrix_boundary"].detail
    assert items["scene_matrix_evidence"].value == "15 Word risks"
    assert "13 control contracts" in items["scene_matrix_evidence"].detail
    assert "42 DOCX fixtures" in items["scene_matrix_evidence"].detail
    assert "100 user journeys" in items["scene_matrix_evidence"].detail
    assert "18/18 business capabilities" in items["scene_matrix_evidence"].detail
    assert "12/12 control runtime" in items["scene_matrix_evidence"].detail
    assert "11/11 ObjectPreflight actions" in (
        items["scene_matrix_evidence"].detail
    )
    assert "14/15 CountProfile families" in items["scene_matrix_evidence"].detail
    assert "15/15 CountProfile accounted" in items["scene_matrix_evidence"].detail
    assert "14 InputSourceProfile families" in items["scene_matrix_evidence"].detail
    assert "15 material families" in items["scene_matrix_evidence"].detail
    assert "14/15 delivery families" in items["scene_matrix_evidence"].detail
    assert "15/15 delivery accounted" in items["scene_matrix_evidence"].detail
    assert "12/12 fixed-layout profile" in items["scene_matrix_evidence"].detail
    assert "10/10 report/artifact drilldown" in items["scene_matrix_evidence"].detail
    assert "3/3 F/O/W" in items["scene_matrix_evidence"].detail
    assert "15/15 F/O/W families accounted" in items["scene_matrix_evidence"].detail
    assert "11 P1 family fixtures" in items["scene_matrix_evidence"].detail
    assert items["scene_matrix_readiness"].value == "27 subjects"
    assert "Green/L5" in items["scene_matrix_readiness"].detail
    assert "2/2 static-closed governed" in items["scene_matrix_readiness"].detail
    assert "6 L5-blocked" in items["scene_matrix_readiness"].detail
    assert "6/6 retained gaps enveloped" in items["scene_matrix_readiness"].detail
    assert "6/6 retained gap exit criteria" in items["scene_matrix_readiness"].detail
    assert "6/6 retained gap receipts" in items["scene_matrix_readiness"].detail
    assert "3/3 gap domains classified" in items["scene_matrix_readiness"].detail
    assert "6/6 L5 blockers enveloped" in items["scene_matrix_readiness"].detail
    assert "6/6 L5 receipts aligned" in items["scene_matrix_readiness"].detail
    assert "6 gaps" in items["scene_matrix_readiness"].detail
    assert "3 domains" in items["scene_matrix_readiness"].detail
    assert "6/6 boundary guarded" in items["scene_matrix_readiness"].detail
    assert "5/5 input warnings managed" in items["scene_matrix_readiness"].detail
    assert "2/2 count warnings managed" in items["scene_matrix_readiness"].detail
    assert "5/5 plugin/manual warnings managed" in items["scene_matrix_readiness"].detail
    assert "2/2 reference warnings managed" in items["scene_matrix_readiness"].detail
    assert "1/1 Visio fixture closed" in items["scene_matrix_readiness"].detail
    assert "3/3 dashboard warnings governed" in items["scene_matrix_readiness"].detail
    assert "0 unmanaged warnings" in items["scene_matrix_readiness"].detail
    assert "0 unreconciled readiness" in items["scene_matrix_readiness"].detail
    assert "0 ungoverned exceptions" in items["scene_matrix_readiness"].detail
    assert "0 dossier issues" in items["scene_matrix_readiness"].detail
    assert "0 unattributed traces" in items["scene_matrix_readiness"].detail
    assert "0 trace partition gaps" in items["scene_matrix_readiness"].detail
    assert "0 release projection gaps" in items["scene_matrix_readiness"].detail
    assert "0 subject continuity gaps" in items["scene_matrix_readiness"].detail
    assert "0 boundary envelope gaps" in items["scene_matrix_readiness"].detail
    assert "0 residual ratio gaps" in items["scene_matrix_readiness"].detail
    assert "10 residual ratio exit criteria" in items["scene_matrix_readiness"].detail
    assert "10 residual ratio receipts" in items["scene_matrix_readiness"].detail
    assert (
        "4/4 count/delivery receipts aligned"
        in items["scene_matrix_readiness"].detail
    )
