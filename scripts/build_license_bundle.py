from __future__ import annotations

import argparse
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import shutil
import ssl
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "licenses" / "components.json"
MANIFEST_PATH = ROOT / "licenses" / "manifest.json"
PACKAGE_LICENSE_ROOT = ROOT / "licenses" / "packages"
NOTICES_PATH = ROOT / "THIRD_PARTY_NOTICES.md"


def _distribution_root(distribution: metadata.Distribution) -> Path:
    for entry in distribution.files or ():
        if entry.name == "METADATA" and entry.parent.name.endswith(".dist-info"):
            return Path(distribution.locate_file(entry)).resolve().parent
    raise RuntimeError(f"无法定位 {distribution.metadata['Name']} 的 .dist-info 目录")


def _declared_license_files(
    distribution: metadata.Distribution,
    explicit_names: Iterable[str] = (),
) -> tuple[tuple[str, Path], ...]:
    dist_root = _distribution_root(distribution)
    declared = list(distribution.metadata.get_all("License-File") or ())
    for name in explicit_names:
        if name not in declared:
            declared.append(name)

    resolved: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for raw_name in declared:
        relative = Path(str(raw_name).replace("\\", "/"))
        candidates = (dist_root / relative, dist_root / "licenses" / relative)
        source = next((path for path in candidates if path.is_file()), None)
        if source is None:
            raise RuntimeError(
                f"{distribution.metadata['Name']} 声明的许可文件不存在：{raw_name}"
            )
        key = str(source.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        resolved.append((relative.as_posix(), source))
    if not resolved:
        raise RuntimeError(f"{distribution.metadata['Name']} 没有可复制的许可文件")
    return tuple(resolved)


def _document_title(component_name: str, relative_name: str) -> str:
    relative = Path(relative_name)
    stem = relative.name
    lowered = stem.casefold()
    if (
        lowered in {"license", "license.txt", "licence", "licence.rst"}
        and relative.parent in {Path(""), Path(".")}
    ):
        return f"{component_name} 主许可证"
    if lowered in {"licenses.txt", "authors.txt"}:
        return f"{component_name} · {stem}"
    parent = relative.parent.name
    label = stem if parent in {"", ".", "licenses"} else f"{parent} · {stem}"
    return f"{component_name} · {label}"


def _copy_distribution_licenses(
    spec: dict,
    *,
    package_root: Path,
) -> tuple[str, list[dict]]:
    distribution = metadata.distribution(spec["distribution"])
    version = distribution.version
    if spec.get("include_distribution_licenses", True) is False:
        return version, []

    documents: list[dict] = []
    component_root = package_root / spec["id"]
    if component_root.exists():
        shutil.rmtree(component_root)
    for relative_name, source in _declared_license_files(
        distribution,
        spec.get("license_files", ()),
    ):
        target = component_root / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        documents.append(
            {
                "title": _document_title(spec["name"], relative_name),
                "license_id": spec["license_expression"],
                "path": target.relative_to(package_root.parent).as_posix(),
            }
        )
    return version, documents


def build_bundle(*, root: Path = ROOT) -> dict:
    config_path = root / "licenses" / "components.json"
    package_root = root / "licenses" / "packages"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise RuntimeError("不支持的许可组件配置版本")

    package_root.mkdir(parents=True, exist_ok=True)
    components: list[dict] = []
    active_package_ids: set[str] = set()
    for raw_spec in config.get("components", ()):
        spec = dict(raw_spec)
        documents = [dict(item) for item in spec.pop("documents", ())]
        distribution_name = spec.pop("distribution", "")
        additional_distributions = list(spec.pop("additional_distributions", ()))
        explicit_files = list(spec.pop("license_files", ()))
        include_distribution_licenses = spec.pop(
            "include_distribution_licenses",
            True,
        )

        version = str(spec.pop("version", "")).strip()
        version_source = str(spec.pop("version_source", "")).strip()
        if version_source == "python":
            version = platform.python_version()
            python_license = Path(sys.base_prefix) / "LICENSE.txt"
            if not python_license.is_file():
                raise RuntimeError("当前 Python 运行环境没有 LICENSE.txt")
            bundled_python_license = root / "licenses" / "static" / "python" / "LICENSE.txt"
            bundled_python_license.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(python_license, bundled_python_license)
        elif version_source == "openssl":
            match = re.search(r"OpenSSL\s+([^\s]+)", ssl.OPENSSL_VERSION)
            if match is None:
                raise RuntimeError("无法识别当前 OpenSSL 版本")
            version = match.group(1)
        elif version_source:
            raise RuntimeError(f"未知的版本来源：{version_source}")
        python_distributions: list[str] = []
        if distribution_name:
            distribution_spec = {
                **spec,
                "distribution": distribution_name,
                "license_files": explicit_files,
                "include_distribution_licenses": include_distribution_licenses,
            }
            version, copied_documents = _copy_distribution_licenses(
                distribution_spec,
                package_root=package_root,
            )
            documents.extend(copied_documents)
            python_distributions = [distribution_name, *additional_distributions]
            for additional in additional_distributions:
                additional_dist = metadata.distribution(additional)
                if additional_dist.version != version:
                    raise RuntimeError(
                        f"{distribution_name} 与 {additional} 的版本不一致"
                    )
            if include_distribution_licenses:
                active_package_ids.add(spec["id"])

        if not documents:
            raise RuntimeError(f"组件 {spec['name']} 没有许可文件")
        for document in documents:
            relative = Path(document["path"])
            target = (root / "licenses" / relative).resolve()
            license_root = (root / "licenses").resolve()
            if license_root not in target.parents or not target.is_file():
                raise RuntimeError(f"组件 {spec['name']} 的许可文件无效：{relative}")

        components.append(
            {
                **spec,
                "version": version,
                "python_distributions": python_distributions,
                "documents": documents,
            }
        )

    for child in package_root.iterdir():
        if child.is_dir() and child.name not in active_package_ids:
            shutil.rmtree(child)

    manifest = {
        "schema_version": 1,
        "component_count": len(components),
        "components": components,
    }
    manifest_path = root / "licenses" / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_notices(manifest, root / "THIRD_PARTY_NOTICES.md")
    return manifest


def _write_notices(manifest: dict, target: Path) -> None:
    lines = [
        "# Third-Party Notices",
        "",
        "Alavette Form 使用并随发行包提供以下第三方软件与资源。",
        "每个组件继续适用其原始许可证；完整原文位于 `licenses/` 目录，也可在软件的“第三方组件”窗口中查看。",
        "",
        "| 组件 | 版本 | 用途 | 本发行版采用许可证 |",
        "|---|---|---|---|",
    ]
    for component in manifest["components"]:
        version = component.get("version") or "—"
        display_license = component.get("display_license") or component[
            "license_expression"
        ]
        lines.append(
            f"| {component['name']} | {version} | {component['purpose']} | {display_license} |"
        )
    lines.extend(
        (
            "",
            "## Lucide 与 Feather",
            "",
            "应用界面内嵌 Lucide Icons 的 SVG 路径。Lucide 采用 ISC 许可证；其中部分图标源自 Feather Icons，并适用 MIT 许可证。完整官方声明随 `licenses/static/lucide/LICENSE` 提供。",
            "",
            "## Qt for Python",
            "",
            "PySide6、Shiboken6 与 Qt 并非 MIT 组件。上游社区版声明可选 LGPLv3/GPLv3；本发行版采用 LGPLv3，并随附 LGPLv3 及其所引用的 GPLv3 原文。",
            "",
            "## Alavette Flow 源码派生模块",
            "",
            "AI 文档助手中的消息合同、协作式取消、公开运行时事件和 OpenAI-compatible 流式适配器，基于 Alavette Flow 的 MIT 许可实现进行裁剪与重构。迁移版本、源文件哈希和修改范围记录在 `docs/audits/assistant_migration_manifest_2026-07-16.md`；完整 MIT 许可随 `licenses/static/alavette-flow/LICENSE` 提供。Alavette Form 不在运行时依赖本地 Alavette Flow 工作区。",
            "",
            "## 发行原则",
            "",
            "- 项目自身代码：MIT。",
            "- 第三方软件、图标和二进制：保留各自原始许可。",
            "- `licenses/manifest.json` 是应用内许可浏览器和发行检查使用的结构化清单。",
            "",
        )
    )
    target.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成当前环境对应的第三方许可包。")
    parser.parse_args()
    manifest = build_bundle()
    print(f"License bundle ready: {manifest['component_count']} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
