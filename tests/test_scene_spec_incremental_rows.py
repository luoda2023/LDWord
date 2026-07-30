from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget
from src.shared.ui.asset_column_guide import AssetColumnGuide
from src.ui.panels.assets.asset_rows_presenter import AssetRowsPresenterMixin
from src.ui.panels.assets.scene_spec_presenter import SceneSpecPresenterMixin
from src.ui.panels.assets.specs import AssetSlotSpec, AttachmentRoleSpec


class _SceneSpecRowsHarness(
    SceneSpecPresenterMixin,
    AssetRowsPresenterMixin,
    QWidget,
):
    def __init__(self) -> None:
        super().__init__()
        self._asset_metadata: dict[str, dict[str, str]] = {}
        self._asset_slot_specs: tuple[AssetSlotSpec, ...] = ()
        self._attachment_role_specs: tuple[AttachmentRoleSpec, ...] = ()

        self._asset_slot_rows = {}
        self._asset_slot_choose_buttons = {}
        self._asset_slot_thumbnail_labels = {}
        self._asset_slot_status_labels = {}
        self._asset_slot_alt_text_inputs = {}
        self._asset_slot_open_buttons = {}
        self._asset_slot_clear_buttons = {}
        self._asset_slots_controller = None

        self._attachment_role_rows = {}
        self._attachment_role_status_labels = {}
        self._attachment_role_choose_buttons = {}
        self._attachment_role_open_buttons = {}
        self._attachment_role_clear_buttons = {}

        root_layout = QVBoxLayout(self)
        self._asset_slots_container = QWidget(self)
        self._asset_slots_layout = QVBoxLayout(self._asset_slots_container)
        root_layout.addWidget(self._asset_slots_container)

        self._independent_attachments_count = QLabel(self)
        self._independent_attachments_column_guide = AssetColumnGuide(
            source_text="附件来源",
            action_count=5,
            parent=self,
        )
        self._independent_attachments_container = QWidget(self)
        self._independent_attachments_layout = QVBoxLayout(
            self._independent_attachments_container
        )
        root_layout.addWidget(self._independent_attachments_container)
        self._attachment_folders_count = QLabel(self)
        self._attachment_folders_column_guide = AssetColumnGuide(
            source_text="文件夹来源",
            action_count=6,
            parent=self,
        )
        self._attachment_folders_container = QWidget(self)
        self._attachment_folders_layout = QVBoxLayout(
            self._attachment_folders_container
        )
        root_layout.addWidget(self._attachment_folders_container)

    def _schedule_summary_refresh(self) -> None:
        pass


def _layout_widgets(layout) -> list[QWidget]:
    return [
        layout.itemAt(index).widget()
        for index in range(layout.count())
        if layout.itemAt(index).widget() is not None
    ]


def test_asset_slot_sync_retains_existing_rows_and_mutates_only_target(qapp):
    harness = _SceneSpecRowsHarness()
    try:
        logo = AssetSlotSpec("logo", "Logo", "{{@img:logo}}")
        seal = AssetSlotSpec("seal", "Seal", "{{@img:seal}}")
        harness._asset_slot_specs = (logo, seal)
        harness._sync_asset_slot_rows()
        logo_row = harness._asset_slot_rows["logo"]
        seal_row = harness._asset_slot_rows["seal"]

        cover = AssetSlotSpec("cover", "Cover", "{{@img:cover}}")
        harness._asset_slot_specs = (logo, cover, seal)
        harness._sync_asset_slot_rows()

        cover_row = harness._asset_slot_rows["cover"]
        assert harness._asset_slot_rows["logo"] is logo_row
        assert harness._asset_slot_rows["seal"] is seal_row
        assert _layout_widgets(harness._asset_slots_layout) == [
            logo_row,
            cover_row,
            seal_row,
        ]

        harness._asset_slot_specs = (seal, logo)
        harness._sync_asset_slot_rows()

        assert harness._asset_slot_rows == {"logo": logo_row, "seal": seal_row}
        assert _layout_widgets(harness._asset_slots_layout) == [seal_row, logo_row]
        assert cover_row.parentWidget() is None
    finally:
        harness.close()


def test_asset_slot_sync_updates_mutable_spec_without_rebuilding_role(qapp):
    harness = _SceneSpecRowsHarness()
    try:
        logo = AssetSlotSpec("logo", "Logo", "{{@img:logo}}")
        seal = AssetSlotSpec("seal", "Seal", "{{@img:seal}}")
        harness._asset_slot_specs = (logo, seal)
        harness._sync_asset_slot_rows()
        old_logo_row = harness._asset_slot_rows["logo"]
        seal_row = harness._asset_slot_rows["seal"]

        # Required-only changes are not rendered by this row and keep identity.
        harness._asset_slot_specs = (
            AssetSlotSpec("logo", "Logo", "{{@img:logo}}", required=True),
            seal,
        )
        harness._sync_asset_slot_rows()
        assert harness._asset_slot_rows["logo"] is old_logo_row

        harness._asset_slot_specs = (
            AssetSlotSpec("logo", "Brand logo", "{{@img:brand_logo}}", required=True),
            seal,
        )
        harness._sync_asset_slot_rows()

        assert harness._asset_slot_rows["logo"] is old_logo_row
        assert harness._asset_slot_rows["seal"] is seal_row
        assert harness._asset_slot_target_edits["logo"].text() == "{{@img:brand_logo}}"
        assert (
            harness._asset_slot_choose_buttons["logo"].toolTip()
            == "为Brand logo选择图片"
        )
        assert (
            harness._asset_slot_open_buttons["logo"].toolTip()
            == "打开Brand logo所在文件夹"
        )
        assert harness._asset_slot_add_buttons["logo"].toolTip() == "新增一项Brand logo"
        assert harness._asset_slot_remove_buttons["logo"].toolTip() == "删除{{@img:brand_logo}}"
    finally:
        harness.close()


def test_attachment_role_sync_retains_existing_rows_and_mutates_only_target(qapp):
    harness = _SceneSpecRowsHarness()
    try:
        evidence = AttachmentRoleSpec("evidence", "Evidence", ("pdf",), True)
        appendix = AttachmentRoleSpec("appendix", "Appendix", ("pdf",), False)
        harness._attachment_role_specs = (evidence, appendix)
        harness._sync_attachment_role_rows()
        evidence_row = harness._attachment_role_rows["evidence"]
        appendix_row = harness._attachment_role_rows["appendix"]

        contract = AttachmentRoleSpec("contract", "Contract", ("docx", "pdf"), True)
        harness._attachment_role_specs = (evidence, contract, appendix)
        harness._sync_attachment_role_rows()

        contract_row = harness._attachment_role_rows["contract"]
        assert harness._attachment_role_rows["evidence"] is evidence_row
        assert harness._attachment_role_rows["appendix"] is appendix_row
        assert _layout_widgets(harness._independent_attachments_layout) == [
            evidence_row,
            contract_row,
            appendix_row,
        ]

        harness._attachment_role_specs = (appendix, evidence)
        harness._sync_attachment_role_rows()

        assert harness._attachment_role_rows == {
            "evidence": evidence_row,
            "appendix": appendix_row,
        }
        assert _layout_widgets(harness._independent_attachments_layout) == [
            appendix_row,
            evidence_row,
        ]
        assert contract_row.parentWidget() is None
    finally:
        harness.close()


def test_attachment_role_sync_updates_changed_contract_without_losing_row(qapp):
    harness = _SceneSpecRowsHarness()
    try:
        evidence = AttachmentRoleSpec("evidence", "Evidence", ("pdf",), True)
        appendix = AttachmentRoleSpec("appendix", "Appendix", ("pdf",), False)
        harness._attachment_role_specs = (evidence, appendix)
        harness._sync_attachment_role_rows()
        old_evidence_row = harness._attachment_role_rows["evidence"]
        appendix_row = harness._attachment_role_rows["appendix"]

        harness._attachment_role_specs = (
            AttachmentRoleSpec("evidence", "Evidence files", ("image", "pdf"), True),
            appendix,
        )
        harness._sync_attachment_role_rows()

        assert harness._attachment_role_rows["evidence"] is old_evidence_row
        assert harness._attachment_role_rows["appendix"] is appendix_row
        assert harness._attachment_role_name_edits["evidence"].text() == "Evidence files"
        assert harness._attachment_role_choose_buttons["evidence"].toolTip() == (
            "选择Evidence files文件"
        )
        assert harness._attachment_drop_controllers["evidence"].policy.suffixes == (
            ".bmp",
            ".jpeg",
            ".jpg",
            ".pdf",
            ".png",
            ".tif",
            ".tiff",
            ".webp",
        )
    finally:
        harness.close()
