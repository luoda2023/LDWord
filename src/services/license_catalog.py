"""Load the packaged project and third-party license catalog safely."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from src.services.problem_report import application_roots, resolve_application_file


class LicenseCatalogError(RuntimeError):
    """Raised when the packaged license bundle is missing or malformed."""


@dataclass(frozen=True)
class LicenseDocument:
    title: str
    license_id: str
    relative_path: str


@dataclass(frozen=True)
class LicenseComponent:
    component_id: str
    name: str
    version: str
    purpose: str
    license_expression: str
    declared_license_expression: str
    display_license: str
    homepage: str
    note: str
    documents: tuple[LicenseDocument, ...]


@dataclass(frozen=True)
class LicenseCatalog:
    bundle_root: Path
    components: tuple[LicenseComponent, ...]

    @property
    def component_count(self) -> int:
        return len(self.components)

    def read_document(self, document: LicenseDocument) -> str:
        relative = Path(document.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise LicenseCatalogError("许可文件路径无效")
        bundle_root = self.bundle_root.resolve()
        target = (bundle_root / relative).resolve()
        if bundle_root not in target.parents or not target.is_file():
            raise LicenseCatalogError(f"找不到许可文件：{document.title}")
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise LicenseCatalogError(f"无法读取许可文件：{document.title}") from exc


def _resolve_bundle_root() -> Path:
    candidates = [root / "licenses" for root in application_roots()]
    for candidate in candidates:
        if (candidate / "manifest.json").is_file():
            return candidate
    raise LicenseCatalogError("找不到第三方许可清单，请重新安装软件")


def _required_text(raw: dict, key: str, *, context: str) -> str:
    value = str(raw.get(key, "")).strip()
    if not value:
        raise LicenseCatalogError(f"许可清单中的{context}缺少 {key}")
    return value


def load_license_catalog() -> LicenseCatalog:
    bundle_root = _resolve_bundle_root()
    manifest_path = bundle_root / "manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LicenseCatalogError("第三方许可清单无法读取") from exc
    if payload.get("schema_version") != 1:
        raise LicenseCatalogError("第三方许可清单版本不受支持")

    components: list[LicenseComponent] = []
    seen_ids: set[str] = set()
    for raw_component in payload.get("components", ()):
        if not isinstance(raw_component, dict):
            raise LicenseCatalogError("第三方许可清单包含无效组件")
        component_id = _required_text(raw_component, "id", context="组件")
        if component_id in seen_ids:
            raise LicenseCatalogError(f"第三方许可清单包含重复组件：{component_id}")
        seen_ids.add(component_id)

        documents: list[LicenseDocument] = []
        for raw_document in raw_component.get("documents", ()):
            if not isinstance(raw_document, dict):
                raise LicenseCatalogError(f"组件 {component_id} 包含无效许可文件")
            document = LicenseDocument(
                title=_required_text(raw_document, "title", context=component_id),
                license_id=str(raw_document.get("license_id", "")).strip(),
                relative_path=_required_text(
                    raw_document,
                    "path",
                    context=component_id,
                ),
            )
            documents.append(document)
        if not documents:
            raise LicenseCatalogError(f"组件 {component_id} 没有许可文件")

        license_expression = _required_text(
            raw_component,
            "license_expression",
            context=component_id,
        )
        component = LicenseComponent(
            component_id=component_id,
            name=_required_text(raw_component, "name", context=component_id),
            version=str(raw_component.get("version", "")).strip(),
            purpose=_required_text(raw_component, "purpose", context=component_id),
            license_expression=license_expression,
            declared_license_expression=str(
                raw_component.get("declared_license_expression")
                or license_expression
            ).strip(),
            display_license=str(
                raw_component.get("display_license")
                or raw_component.get("license_expression")
                or ""
            ).strip(),
            homepage=str(raw_component.get("homepage", "")).strip(),
            note=str(raw_component.get("note", "")).strip(),
            documents=tuple(documents),
        )
        components.append(component)

    expected_count = payload.get("component_count")
    if expected_count != len(components) or not components:
        raise LicenseCatalogError("第三方许可清单的组件数量无效")
    catalog = LicenseCatalog(bundle_root=bundle_root, components=tuple(components))
    for component in catalog.components:
        for document in component.documents:
            catalog.read_document(document)
    return catalog


def read_project_license() -> str:
    path = resolve_application_file("LICENSE")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LicenseCatalogError("本软件许可文件无法读取") from exc


__all__ = [
    "LicenseCatalog",
    "LicenseCatalogError",
    "LicenseComponent",
    "LicenseDocument",
    "load_license_catalog",
    "read_project_license",
]
