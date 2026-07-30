from __future__ import annotations

from src.services.license_catalog import load_license_catalog, read_project_license
from src.shared.ui.license_dialog import LicenseDialog
from src.shared.ui.preview_dialog import PreviewShellDialog


def test_project_license_uses_proportional_reader_without_preview_controls(qapp):
    dialog = LicenseDialog.for_project(read_project_license())
    try:
        dialog.show()
        qapp.processEvents()

        assert isinstance(dialog, PreviewShellDialog)
        assert dialog.project_viewer.isReadOnly()
        assert dialog.project_viewer.toPlainText().startswith("MIT License")
        assert dialog.project_viewer.font().families()[0] == "Segoe UI"
        assert not hasattr(dialog, "viewport")
        assert dialog._toolbar_layout.count() == 1
    finally:
        dialog.close()
        qapp.processEvents()


def test_third_party_licenses_are_one_continuous_document(qapp):
    catalog = load_license_catalog()
    dialog = LicenseDialog.for_third_party(catalog)
    try:
        dialog.show()
        qapp.processEvents()

        text = dialog.third_party_viewer.toPlainText()
        assert dialog.third_party_viewer.isReadOnly()
        assert dialog.third_party_viewer.maximumWidth() == 1120
        assert not hasattr(dialog, "_component_list")
        assert not hasattr(dialog, "detail_pane")
        assert all(component.name in text for component in catalog.components)
        assert "Lucide Icons" in text
        assert "ISC + MIT" in text
        assert "Feather" in text
        assert "pypdfium2 / PDFium" in text
        python_component = next(
            component
            for component in catalog.components
            if component.component_id == "python-runtime"
        )
        assert f"Python · {python_component.version} · PSF-2.0" in text
        assert "https://www.python.org/" in text
        assert "应用运行环境" not in text
        assert "Python was created in the early 1990s" not in text
        assert "完整许可原文" in text
        assert "licenses/ 目录" in text
        assert text.count("\n---\n") == catalog.component_count
        assert len(text.splitlines()) < 100
        qt_text = text[
            text.index("Qt for Python (PySide6)") : text.index("python-docx")
        ]
        assert "LGPL-3.0" in qt_text
        assert "GPL-2.0" not in qt_text
        assert text.index(catalog.components[0].name) < text.index("Lucide Icons")
    finally:
        dialog.close()
        qapp.processEvents()
