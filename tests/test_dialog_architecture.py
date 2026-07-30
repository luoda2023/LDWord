import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication
from src.shared.ui import dialogs
from src.shared.ui.base_dialog import BaseDialog
from src.shared.ui.confirm_dialog import ConfirmDialog
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.sizing import control_size_metrics
from src.shared.ui.theme import LIGHT


def _app():
    return QApplication.instance() or QApplication([])


def test_base_dialog_buttons_delegate_to_shared_variant_helpers():
    primary_source = inspect.getsource(BaseDialog.add_primary_button)
    secondary_source = inspect.getsource(BaseDialog.add_secondary_button)
    style_source = inspect.getsource(BaseDialog._apply_style)

    assert "apply_button_variant" in primary_source
    assert "apply_button_variant" in secondary_source
    assert "setStyleSheet" not in primary_source
    assert "setStyleSheet" not in secondary_source
    assert "build_button_stylesheet" in style_source


def test_confirm_dialog_is_built_on_base_dialog_without_local_button_qss():
    assert issubclass(ConfirmDialog, BaseDialog)

    source = inspect.getsource(ConfirmDialog)
    assert ".setStyleSheet" not in source


def test_base_dialog_does_not_reserve_outer_shadow_margin_in_top_level_layout():
    _app()
    dialog = BaseDialog()
    try:
        margins = dialog.layout().contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
    finally:
        dialog.close()


def test_confirm_dialog_uses_readable_default_copy_constants():
    source = (ROOT / "src/shared/ui/confirm_dialog.py").read_text(encoding="utf-8")

    assert 'DEFAULT_CONFIRM_DIALOG_TITLE = "请确认"' in source
    assert 'DEFAULT_CONFIRM_BUTTON_TEXT = "确认"' in source
    assert 'DEFAULT_CANCEL_BUTTON_TEXT = "取消"' in source
    assert "title: str = DEFAULT_CONFIRM_DIALOG_TITLE" in source
    assert "confirm_text: str = DEFAULT_CONFIRM_BUTTON_TEXT" in source
    assert "cancel_text: str = DEFAULT_CANCEL_BUTTON_TEXT" in source
    assert "??" not in source


def test_confirm_dialog_further_decomposes_constructor_helpers():
    source = inspect.getsource(ConfirmDialog)
    init_source = inspect.getsource(ConfirmDialog.__init__)

    assert "def _add_optional_message" in source
    assert "def _build_cancel_button" in source
    assert "def _build_confirm_button" in source
    assert "self._add_optional_message" in init_source
    assert "self._build_cancel_button" in init_source
    assert "self._build_confirm_button" in init_source
    assert "self.add_secondary_button(cancel_text)" not in init_source
    assert "self.add_primary_button(confirm_text" not in init_source


def test_shared_text_input_stylesheet_uses_theme_tokens():
    qss = build_text_input_stylesheet(LIGHT)

    assert f"border-radius: {LIGHT.input_radius}px;" in qss
    assert f"padding: {LIGHT.input_padding_y}px {LIGHT.input_padding_x}px;" in qss
    metrics = control_size_metrics(
        LIGHT,
        "md",
        vertical_padding=LIGHT.input_padding_y,
        border_width=1,
    )
    assert f"min-height: {metrics.content_height}px;" in qss
    assert f"max-height: {metrics.content_height}px;" in qss
    assert "font-size:" not in qss
    assert "font-weight:" not in qss


def test_dialogs_input_text_uses_shared_text_input_helper():
    source = inspect.getsource(dialogs.input_text)

    assert "add_text_input" in source or "build_text_input_stylesheet" in source
    assert "QLineEdit {" not in source


def test_folder_picker_uses_shared_input_and_button_helpers():
    source = inspect.getsource(FolderPicker)

    assert "bind_theme" in source
    assert "build_text_input_stylesheet" in source
    assert "apply_button_variant" in source


def test_folder_picker_uses_readable_copy_constants():
    source = (ROOT / "src/shared/ui/folder_picker.py").read_text(encoding="utf-8")
    init_source = inspect.getsource(FolderPicker.__init__)

    assert 'DEFAULT_FOLDER_PLACEHOLDER = "请选择文件夹"' in source
    assert 'BROWSE_BUTTON_TEXT = "浏览"' in source
    assert 'FOLDER_DIALOG_TITLE = "选择文件夹"' in source
    assert "placeholder: str = DEFAULT_FOLDER_PLACEHOLDER" in init_source
    assert "QPushButton(BROWSE_BUTTON_TEXT)" in source
    assert "QFileDialog.getExistingDirectory(self, FOLDER_DIALOG_TITLE)" in source
    assert "??" not in source


def test_folder_picker_further_decomposes_constructor_helpers():
    source = inspect.getsource(FolderPicker)
    init_source = inspect.getsource(FolderPicker.__init__)

    assert "def _build_path_input" in source
    assert "def _build_browse_button" in source
    assert "self._build_path_input" in init_source
    assert "self._build_browse_button" in init_source
    assert "QLineEdit()" not in init_source
    assert "QPushButton(BROWSE_BUTTON_TEXT)" not in init_source


def test_folder_picker_wrapper_does_not_clip_themed_controls():
    app = _app()
    picker = FolderPicker()
    try:
        picker.resize(700, picker.sizeHint().height())
        picker.show()
        app.processEvents()

        assert picker.height() >= picker.minimumSizeHint().height()
        assert picker._path.geometry().bottom() <= picker.rect().bottom()
        assert picker._btn.geometry().bottom() <= picker.rect().bottom()
        assert picker._path.height() >= picker._path.minimumSizeHint().height()
        assert picker._btn.height() >= picker._btn.minimumSizeHint().height()
    finally:
        picker.close()
        app.processEvents()


def test_dialog_cluster_uses_shared_dialog_style_helpers():
    dialog_style_source = (ROOT / "src/shared/ui/dialog_style.py").read_text(encoding="utf-8")
    base_dialog_source = (ROOT / "src/shared/ui/base_dialog.py").read_text(encoding="utf-8")
    dialogs_source = (ROOT / "src/shared/ui/dialogs.py").read_text(encoding="utf-8")
    error_dialog_source = (ROOT / "src/shared/ui/error_dialog.py").read_text(encoding="utf-8")

    assert "def build_dialog_icon_container_stylesheet" in dialog_style_source
    assert "def build_dialog_message_stylesheet" in dialog_style_source
    assert "def build_dialog_detail_stylesheet" in dialog_style_source
    assert "def build_dialog_path_label_stylesheet" in dialog_style_source

    assert "build_dialog_icon_container_stylesheet" in base_dialog_source
    assert "build_dialog_message_stylesheet" in base_dialog_source
    assert 'icon_container.setStyleSheet(f"' not in base_dialog_source

    assert "build_dialog_detail_stylesheet" in dialogs_source
    assert "build_dialog_path_label_stylesheet" in dialogs_source
    assert "build_dialog_detail_stylesheet" in error_dialog_source
    assert "build_dialog_path_label_stylesheet" in error_dialog_source


def test_error_dialog_source_uses_readable_text_constants():
    source = (ROOT / "src/shared/ui/error_dialog.py").read_text(encoding="utf-8")

    assert 'title=f"{APP_DISPLAY_NAME} - 错误"' in source
    assert "处理过程中发生错误，请查看以下详情。" in source
    assert 'self._ok_btn = self.add_primary_button(OK_TEXT)' in source
    assert 'path_label = QLabel(f"{LOG_PATH_PREFIX}{log_path}")' in source
    assert "????" not in source
