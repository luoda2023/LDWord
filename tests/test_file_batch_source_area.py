from src.shared.ui.theme import get_theme, theme_rgba
from src.ui.panels.workbench.file_batch_execution_detail import (
    FileBatchSourceArea,
)


def test_selected_file_uses_primary_surface_and_file_icon(qapp, tmp_path):
    source = tmp_path / "draft.docx"
    source.write_bytes(b"")
    area = FileBatchSourceArea()

    area.set_paths((str(source),))

    theme = get_theme()
    assert area.paths() == (str(source.resolve()),)
    assert area._background.name() == theme.primary.lower()
    assert area._icon.property("sourceKind") == "file"
    assert theme.text_on_primary in area._title.styleSheet()
    assert theme_rgba(theme.text_on_primary, 0.85) in area._hint.styleSheet()
    assert not area._clear_button.isHidden()
    assert area._files_button.isHidden()
    assert area._folder_button.isHidden()


def test_empty_folder_keeps_selected_surface_and_folder_icon(qapp, tmp_path):
    source_folder = tmp_path / "incoming"
    source_folder.mkdir()
    area = FileBatchSourceArea()

    area.set_paths((str(source_folder),))

    theme = get_theme()
    assert area.paths() == ()
    assert area.title_text() == "已选择 1 个文件夹"
    assert "暂未发现支持的 .docx 文档" in area.hint_text()
    assert area._background.name() == theme.primary.lower()
    assert area._icon.property("sourceKind") == "folder"
    assert not area._clear_button.isHidden()
    assert area._files_button.isHidden()
    assert area._folder_button.isHidden()


def test_folder_icon_wins_when_file_and_its_parent_are_both_selected(
    qapp,
    tmp_path,
):
    source = tmp_path / "draft.docx"
    source.write_bytes(b"")
    area = FileBatchSourceArea()

    area.set_paths((str(source), str(tmp_path)))

    assert area.paths() == (str(source.resolve()),)
    assert area._icon.property("sourceKind") == "folder"


def test_clearing_source_restores_idle_surface(qapp, tmp_path):
    source_folder = tmp_path / "incoming"
    source_folder.mkdir()
    area = FileBatchSourceArea()
    area.set_paths((str(source_folder),))

    area.clear()

    theme = get_theme()
    assert area.title_text() == "拖拽文件或文件夹至此处"
    assert area._background.name() == theme.bg_card.lower()
    assert area._icon.property("sourceKind") == "idle"
    assert area._clear_button.isHidden()
    assert not area._files_button.isHidden()
    assert not area._folder_button.isHidden()
