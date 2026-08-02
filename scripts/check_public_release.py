from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.stage_source_release import (
    SOURCE_MANIFEST_NAME,
    verify_source_manifest,
)
from src.app_meta import APP_DISPLAY_NAME, APP_PACKAGE_NAME, APP_SEMVER

REQUIRED_DOCS = [
    "README.md",
    "CHANGELOG.md",
    "RELEASE_NOTES.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "requirements.txt",
    "licenses/components.json",
    "licenses/manifest.json",
    "docs/user/README.md",
    "docs/user/00-开始这里.md",
    "docs/user/quick-start.md",
    "docs/user/user-guide.md",
    "docs/user/_meta/screenshot-manifest.yml",
    "docs/user/screenshots/01-workbench-overview.png",
    "docs/user/screenshots/02-document-selected.png",
    "docs/user/screenshots/03-output-and-generate.png",
    "docs/user/screenshots/04-ai-assistant-overview.png",
    "docs/user/samples/快速开始示例.docx",
]
BLOCKING_PATHS = [
    ".venv",
    "build",
    "dist",
]
LOCAL_ONLY_PATHS = [
    "artifacts",
    "exam_masters/user",
    "exam_samples",
    "output",
]
LOCAL_ONLY_GLOBS = [
    "config_library/plans/*/user",
    "config_library/templates/*/user",
    "config_library/masters/*/user",
    "config_library/material_packages/*/user",
]
BLOCKING_GLOBS = [
    "*_new.docx",
    "*_对比稿.docx",
    "*_报告.json",
    "*_报告.md",
]
WARNING_GLOBS = [
    "crash.log",
    "demo_crash.log",
    "alavette_form.log",
]
PYQT5_IMPORT_RE = re.compile(r"^\s*(from|import)\s+PyQt5\b", re.MULTILINE)
LOCAL_PROFILE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:|/[A-Za-z]:)[\\/]+Users[\\/]+(?P<user>[^\\/\s`\"']+)",
    re.IGNORECASE,
)
SYNTHETIC_TEST_USER_NAMES = {"alice", "developer", "example", "test"}
RELEASE_TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PUBLIC_DOCX_AUTHORS = {"", "alavette form", "python-docx"}
SCAN_PRUNE_DIRS = {
    ".agents",
    ".claude",
    ".codex-exam-plan-task",
    ".codex-qa",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".worktrees",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "output",
    "tmp",
    "_codex_work",
    "verification_outputs",
}
BINARY_REQUIRED_PATHS = [
    f"{APP_PACKAGE_NAME}.exe",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "RELEASE_NOTES.md",
    "SECURITY.md",
    "licenses/manifest.json",
    "config_library",
    "SBOM.cdx.json",
    "RELEASE_MANIFEST.json",
]


def _normalized_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", str(value or "").strip()).casefold()


def validate_license_bundle(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "licenses" / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"Invalid license manifest: {exc}"]
    components = manifest.get("components")
    if manifest.get("schema_version") != 1 or not isinstance(components, list):
        return ["Invalid license manifest schema"]
    if manifest.get("component_count") != len(components) or not components:
        errors.append("License manifest component_count does not match components")

    license_root = (root / "licenses").resolve()
    component_ids: set[str] = set()
    components_by_id: dict[str, dict] = {}
    declared_distributions: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            errors.append("License manifest contains a non-object component")
            continue
        component_id = str(component.get("id", "")).strip()
        if not component_id or component_id in component_ids:
            errors.append(
                f"Missing or duplicate license component id: {component_id!r}"
            )
            continue
        component_ids.add(component_id)
        components_by_id[component_id] = component
        for distribution in component.get("python_distributions", ()):
            declared_distributions.add(_normalized_distribution_name(distribution))
        documents = component.get("documents")
        if not isinstance(documents, list) or not documents:
            errors.append(f"License component has no documents: {component_id}")
            continue
        for document in documents:
            relative = Path(str(document.get("path", "")))
            target = (license_root / relative).resolve()
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or license_root not in target.parents
                or not target.is_file()
                or target.stat().st_size == 0
            ):
                errors.append(
                    f"Missing or unsafe license document for {component_id}: {relative}"
                )

    required_component_ids = {
        "python-runtime",
        "qt-for-python",
        "lucide-icons",
        "openssl",
    }
    for component_id in sorted(required_component_ids - component_ids):
        errors.append(f"Required bundled component is missing: {component_id}")

    qt_component = components_by_id.get("qt-for-python")
    if qt_component is not None:
        if qt_component.get("license_expression") != "LGPL-3.0-only":
            errors.append("Qt for Python concluded license must be LGPL-3.0-only")
        if qt_component.get("declared_license_expression") != (
            "LGPL-3.0-only OR GPL-3.0-only"
        ):
            errors.append("Qt for Python upstream license choices are invalid")
        qt_document_ids = {
            str(document.get("license_id", "")).strip()
            for document in qt_component.get("documents", ())
            if isinstance(document, dict)
        }
        if qt_document_ids != {"LGPL-3.0-only", "GPL-3.0-only"}:
            errors.append("Qt for Python must bundle LGPLv3 and GPLv3 texts only")

    requirements_path = root / "requirements.txt"
    if requirements_path.is_file():
        runtime_distributions: set[str] = set()
        for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.partition("#")[0].strip()
            if not line:
                continue
            name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0]
            runtime_distributions.add(_normalized_distribution_name(name))
        for missing in sorted(runtime_distributions - declared_distributions):
            errors.append(
                f"Runtime dependency missing from license manifest: {missing}"
            )

    notices = (root / "THIRD_PARTY_NOTICES.md").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    for required_name in ("Lucide", "Feather", "Qt for Python", "Alavette Flow"):
        if required_name not in notices:
            errors.append(f"THIRD_PARTY_NOTICES.md does not mention {required_name}")
    return errors


def iter_repo_files(root: Path) -> Iterable[Path]:
    for current, directory_names, file_names in os.walk(root):
        current_path = Path(current)
        directory_names[:] = [
            name
            for name in directory_names
            if name not in SCAN_PRUNE_DIRS and not name.startswith(".codex_tmp")
        ]
        for name in directory_names:
            yield current_path / name
        for name in file_names:
            yield current_path / name


def scan_release_tree(
    root: Path,
    *,
    kind: str = "source",
) -> tuple[list[str], list[str]]:
    if kind == "binary":
        return scan_binary_release_tree(root)
    if kind != "source":
        raise ValueError(f"Unsupported release scan kind: {kind}")
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED_DOCS:
        if not (root / rel).exists():
            errors.append(f"Missing required release file: {rel}")
    if (root / "licenses" / "manifest.json").is_file():
        errors.extend(validate_license_bundle(root))
    if (root / SOURCE_MANIFEST_NAME).is_file():
        errors.extend(verify_source_manifest(root))

    for rel in BLOCKING_PATHS:
        if (root / rel).exists():
            warnings.append(f"Local-only path present: {rel}")
    for rel in LOCAL_ONLY_PATHS:
        if (root / rel).exists():
            warnings.append(f"Runtime/user path should not be published: {rel}")

    for path in iter_repo_files(root):
        rel = path.relative_to(root).as_posix()

        if path.is_dir():
            for pattern in LOCAL_ONLY_GLOBS:
                if fnmatch.fnmatch(rel, pattern):
                    warnings.append(f"Runtime/user path should not be published: {rel}")

        if path.is_file():
            for pattern in BLOCKING_GLOBS:
                if fnmatch.fnmatch(path.name, pattern):
                    warnings.append(
                        f"Generated artifact should not be published: {rel}"
                    )
            for pattern in WARNING_GLOBS:
                if fnmatch.fnmatch(path.name, pattern):
                    warnings.append(f"Runtime log present: {rel}")

            if path.suffix == ".py":
                text = path.read_text(encoding="utf-8", errors="ignore")
                if PYQT5_IMPORT_RE.search(text):
                    errors.append(f"PyQt5 import remains in: {rel}")
            elif path.suffix.casefold() in RELEASE_TEXT_SUFFIXES:
                text = path.read_text(encoding="utf-8", errors="ignore")

            profile_matches = (
                list(LOCAL_PROFILE_PATH_RE.finditer(text))
                if path.suffix.casefold() in RELEASE_TEXT_SUFFIXES
                else []
            )
            unsafe_profile_match = any(
                not rel.startswith("tests/")
                or match.group("user").casefold() not in SYNTHETIC_TEST_USER_NAMES
                for match in profile_matches
            )
            if unsafe_profile_match:
                errors.append(f"Local user profile path remains in: {rel}")
            if path.suffix.casefold() == ".docx":
                errors.extend(validate_public_docx(path, relative_path=rel))

    return errors, warnings


def validate_public_docx(path: Path, *, relative_path: str | None = None) -> list[str]:
    """Reject contact data, local paths and personal author metadata in DOCX."""

    display_path = relative_path or path.name
    try:
        with zipfile.ZipFile(path) as archive:
            if corrupt_member := archive.testzip():
                return [f"Corrupt DOCX member in {display_path}: {corrupt_member}"]
            story_text = "\n".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.endswith((".xml", ".rels"))
            )
            core_xml = archive.read("docProps/core.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        return [f"Invalid public DOCX {display_path}: {exc}"]

    errors: list[str] = []
    if EMAIL_RE.search(story_text):
        errors.append(f"Email address remains in public DOCX: {display_path}")
    if LOCAL_PROFILE_PATH_RE.search(story_text):
        errors.append(f"Local user profile path remains in public DOCX: {display_path}")
    try:
        core = ET.fromstring(core_xml)
    except ET.ParseError as exc:
        errors.append(f"Invalid DOCX core metadata in {display_path}: {exc}")
        return errors
    namespaces = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    }
    for label, expression in (
        ("creator", "dc:creator"),
        ("lastModifiedBy", "cp:lastModifiedBy"),
    ):
        value = str(
            core.findtext(expression, default="", namespaces=namespaces)
        ).strip()
        if value.casefold() not in PUBLIC_DOCX_AUTHORS:
            errors.append(
                f"Personal DOCX {label} metadata remains in {display_path}: {value!r}"
            )
    return errors


def scan_binary_release_tree(root: Path) -> tuple[list[str], list[str]]:
    """Scan the final one-folder payload without traversing a developer tree."""

    errors = [
        f"Missing required binary release file: {relative}"
        for relative in BINARY_REQUIRED_PATHS
        if not (root / relative).exists()
    ]
    warnings: list[str] = []
    manifest = root / "licenses" / "manifest.json"
    if manifest.is_file():
        errors.extend(validate_license_bundle(root))
    release_manifest = root / "RELEASE_MANIFEST.json"
    if release_manifest.is_file():
        errors.extend(validate_binary_release_manifest(root))
    sbom = root / "SBOM.cdx.json"
    if sbom.is_file():
        errors.extend(validate_binary_sbom(sbom, license_manifest_path=manifest))

    pdf_documents = list(root.glob("Alavette Form V1.0 - *.pdf"))
    if len(pdf_documents) != 2 or any(
        item.stat().st_size == 0 for item in pdf_documents
    ):
        errors.append(
            "Binary release must contain exactly two non-empty V1.0 PDF guides"
        )
    sample_documents = [
        item
        for item in root.glob("*.docx")
        if not item.name.startswith("Alavette Form V1.0 - ")
    ]
    if len(sample_documents) != 1 or any(
        item.stat().st_size == 0 for item in sample_documents
    ):
        errors.append("Binary release must contain exactly one non-empty sample DOCX")
    for path in iter_repo_files(root):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            if path.name.casefold() == "user":
                warnings.append(
                    f"Runtime/user path should not be published: {relative}"
                )
            continue
        if path.suffix.casefold() == ".py":
            warnings.append(f"Raw Python source present in binary package: {relative}")
        if path.name.casefold() in {name.casefold() for name in WARNING_GLOBS}:
            warnings.append(f"Runtime log present: {relative}")
    return errors, warnings


def validate_binary_release_manifest(root: Path) -> list[str]:
    """Verify the final payload against its release manifest."""

    manifest_path = root / "RELEASE_MANIFEST.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"Invalid binary release manifest: {exc}"]
    files = payload.get("files")
    if payload.get("schema_version") != 1 or not isinstance(files, list):
        return ["Invalid binary release manifest schema"]
    expected: list[dict[str, object]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path == manifest_path:
            continue
        expected.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    errors: list[str] = []
    if files != expected:
        errors.append("Binary release manifest does not match payload files")
    if payload.get("file_count") != len(expected):
        errors.append("Binary release manifest file_count is invalid")
    signed = payload.get("signed")
    release_ready = payload.get("release_ready")
    if (
        not isinstance(signed, bool)
        or not isinstance(release_ready, bool)
        or release_ready != signed
    ):
        errors.append(
            "Binary release manifest release_ready/signed status is inconsistent"
        )
    return errors


def validate_binary_sbom(
    path: Path,
    *,
    license_manifest_path: Path | None = None,
) -> list[str]:
    """Validate the minimum CycloneDX application/component contract."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"Invalid binary SBOM: {exc}"]
    components = payload.get("components")
    application = payload.get("metadata", {}).get("component", {})
    errors: list[str] = []
    if payload.get("bomFormat") != "CycloneDX" or payload.get("specVersion") != "1.5":
        errors.append("Binary SBOM must be CycloneDX 1.5")
    if (
        application.get("name") != APP_DISPLAY_NAME
        or application.get("version") != APP_SEMVER
    ):
        errors.append("Binary SBOM application metadata is invalid")
    if not isinstance(components, list) or not components:
        errors.append("Binary SBOM has no dependency components")
    if license_manifest_path is not None and license_manifest_path.is_file():
        try:
            license_payload = json.loads(
                license_manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"Cannot cross-check binary SBOM license manifest: {exc}")
            return errors
        expected_ids = {
            str(component.get("id") or "").strip()
            for component in license_payload.get("components", [])
            if isinstance(component, dict)
        }
        actual_ids = {
            str(property_item.get("value") or "").strip()
            for component in components or []
            if isinstance(component, dict)
            for property_item in component.get("properties", [])
            if isinstance(property_item, dict)
            and property_item.get("name") == "alavette:license-component-id"
        }
        if expected_ids != actual_ids:
            errors.append("Binary SBOM does not cover the license component manifest")
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan the repository for obvious blockers before a MIT-source public release.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any warning or error is found.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Isolated source tree or binary payload directory to scan.",
    )
    parser.add_argument(
        "--kind",
        choices=("source", "binary"),
        default="source",
        help="Apply source-release or final-binary rules.",
    )
    args = parser.parse_args()

    scan_root = args.root.resolve()
    errors, warnings = scan_release_tree(scan_root, kind=args.kind)

    print("== Public release scan ==")
    print(f"Release tree: {scan_root}")
    print(f"Scan kind: {args.kind}")
    print("Required docs and structured license bundle checked")

    if errors:
        print("\n[ERRORS]")
        for item in errors:
            print(f"- {item}")

    if warnings:
        print("\n[WARNINGS]")
        for item in warnings:
            print(f"- {item}")

    if not errors and not warnings:
        print("\n[OK] No obvious public-release blockers were found.")
        return 0

    if args.strict:
        print("\n[FAIL] Strict mode enabled: fix the findings above before publishing.")
        return 1

    print("\n[WARN] Findings detected. Review them before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
