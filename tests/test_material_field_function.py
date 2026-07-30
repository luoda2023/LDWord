from datetime import datetime, timezone

from src.config.entity import (
    EntityArchive,
    EntityProfile,
    load_entity_archive,
    save_entity_archive,
)
from src.config.material_context import MaterialExecutionContext
from src.qt_api import QApplication, QPoint
from src.shared.engine.material_field_function import (
    normalize_field_functions,
    resolve_field_functions,
)
from src.shared.engine.official_document_material_package import (
    export_official_document_material_package,
    load_official_document_material_package,
)
from src.ui.panels.assets.field_function_dialog import _OfficialFieldFunctionDialog


def _app():
    return QApplication.instance() or QApplication([])


def test_realtime_field_functions_share_one_localized_snapshot():
    resolution = resolve_field_functions(
        {},
        {
            "date": {"function": "realtime_date"},
            "time": {"function": "realtime_time"},
            "datetime": {"function": "realtime_datetime"},
        },
        now=datetime(2026, 7, 12, 16, 30, 45, tzinfo=timezone.utc),
    )

    assert resolution.errors == {}
    assert resolution.values == {
        "date": "2026年7月13日",
        "time": "00:30:45",
        "datetime": "2026年7月13日 00:30:45",
    }


def test_field_functions_reject_old_rule_shape_and_unknown_functions():
    assert normalize_field_functions(
        {
            "old": {"operation": "current_date"},
            "unknown": {"function": "copy"},
            "valid": {"function": "realtime_date", "timezone": "UTC"},
        }
    ) == {"valid": {"function": "realtime_date"}}


def test_field_function_dialog_exposes_only_three_realtime_functions():
    app = _app()
    dialog = _OfficialFieldFunctionDialog(
        parent=None,
        target_key="正文1",
        fields=[("正文1", "正文1")],
        values={},
        field_functions={},
    )
    try:
        assert [
            dialog._function_combo.itemText(index)
            for index in range(dialog._function_combo.count())
        ] == ["实时日期", "实时时间", "实时日期时间"]
        assert dialog.selected_function() == {"function": "realtime_date"}
        assert dialog._function_combo.accessibleName() == "字段函数"
        assert dialog.content_layout.count() == 1
        dialog.show()
        app.processEvents()
        combo = dialog._function_combo
        combo.showPopup()
        app.processEvents()
        popup = combo._popup_panel.surface()
        combo_bottom = combo.mapTo(dialog, QPoint(0, combo.height())).y()
        assert popup.y() >= combo_bottom
        assert popup.height() >= combo._popup_content_height()
        assert combo.view().verticalScrollBar().maximum() == 0
        combo.hidePopup()
    finally:
        dialog.close()
        app.processEvents()


def test_material_context_resolves_and_clones_field_functions():
    context = MaterialExecutionContext(
        field_functions={
            "generated": {"function": "realtime_datetime"},
        }
    )

    clone = context.clone()
    resolution = context.resolve_material_fields(
        now=datetime(2026, 7, 12, 8, 0, 1, tzinfo=timezone.utc)
    )
    assert resolution.values["generated"] == "2026年7月12日 16:00:01"
    assert clone.field_functions == context.field_functions
    assert clone.field_functions is not context.field_functions


def test_material_archive_round_trips_field_functions(tmp_path):
    path = tmp_path / "function-material.json"
    functions = {"generated": {"function": "realtime_date"}}
    save_entity_archive(
        EntityArchive(
            profiles=[EntityProfile(field_functions=functions)],
        ),
        path,
    )

    loaded = load_entity_archive(path)
    assert loaded.profiles[0].field_functions == functions
    assert '"field_functions"' in path.read_text(encoding="utf-8")
    assert '"field_rules"' not in path.read_text(encoding="utf-8")


def test_official_material_package_round_trips_field_functions(tmp_path):
    path = tmp_path / "official-functions.material.json"
    export_official_document_material_package(
        MaterialExecutionContext(
            profile_id="official:notice",
            profile_name="通知",
            entity_data={
                "document_type": "notice",
                "title": "测试通知",
                "body": "正文",
                "organization": "示例单位",
                "document_no": "示发〔2026〕1号",
                "issue_date": "2026年7月12日",
            },
            field_functions={
                "printing_date": {"function": "realtime_date"},
            },
        ),
        path,
        profile_id="notice",
    )

    loaded = load_official_document_material_package(path)
    assert loaded.context.field_functions == {
        "printing_date": {"function": "realtime_date"}
    }
