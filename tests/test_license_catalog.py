from __future__ import annotations

import json

import pytest

from src.services import license_catalog as license_catalog_module
from src.services.license_catalog import LicenseCatalogError, load_license_catalog


def test_packaged_license_catalog_contains_assets_runtime_and_raw_documents():
    catalog = load_license_catalog()
    by_id = {component.component_id: component for component in catalog.components}

    assert catalog.component_count == 18
    assert by_id["alavette-flow-derived"].license_expression == "MIT"
    assert "Alavette Flow Contributors" in catalog.read_document(
        by_id["alavette-flow-derived"].documents[0]
    )
    assert by_id["lucide-icons"].display_license == "ISC + MIT"
    assert "Feather" in by_id["lucide-icons"].note
    assert by_id["qt-for-python"].version
    assert by_id["qt-for-python"].license_expression == "LGPL-3.0-only"
    assert by_id["qt-for-python"].declared_license_expression == (
        "LGPL-3.0-only OR GPL-3.0-only"
    )
    assert {document.license_id for document in by_id["qt-for-python"].documents} == {
        "LGPL-3.0-only",
        "GPL-3.0-only",
    }
    assert len(by_id["pypdfium2"].documents) >= 19
    assert by_id["latex2mathml"].license_expression == "MIT"
    assert by_id["olefile"].license_expression == "BSD-2-Clause AND HPND"
    assert "ISC License" in catalog.read_document(
        by_id["lucide-icons"].documents[0]
    )


def test_license_catalog_rejects_paths_outside_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / "licenses"
    bundle.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("not part of bundle", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "component_count": 1,
        "components": [
            {
                "id": "unsafe",
                "name": "Unsafe",
                "version": "1",
                "purpose": "test",
                "license_expression": "MIT",
                "documents": [
                    {
                        "title": "unsafe",
                        "license_id": "MIT",
                        "path": "../outside.txt",
                    }
                ],
            }
        ],
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(
        license_catalog_module,
        "application_roots",
        lambda: (tmp_path,),
    )

    with pytest.raises(LicenseCatalogError, match="路径无效|找不到许可文件"):
        load_license_catalog()
