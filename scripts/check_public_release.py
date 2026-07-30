from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = [
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "requirements.txt",
    "licenses/components.json",
    "licenses/manifest.json",
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
    "*.spec",
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
PYQT5_IMPORT_RE = re.compile(r"^\s*(from|import)\s+PyQt5\b", re.M)


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
            errors.append(f"Missing or duplicate license component id: {component_id!r}")
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
            errors.append(f"Runtime dependency missing from license manifest: {missing}")

    notices = (root / "THIRD_PARTY_NOTICES.md").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    for required_name in ("Lucide", "Feather", "Qt for Python", "Alavette Flow"):
        if required_name not in notices:
            errors.append(f"THIRD_PARTY_NOTICES.md does not mention {required_name}")
    return errors


def iter_repo_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if ".agents" in path.parts or "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        yield path


def scan_release_tree(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED_DOCS:
        if not (root / rel).exists():
            errors.append(f"Missing required release file: {rel}")
    if (root / "licenses" / "manifest.json").is_file():
        errors.extend(validate_license_bundle(root))

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
                    warnings.append(f"Generated artifact should not be published: {rel}")
            for pattern in WARNING_GLOBS:
                if fnmatch.fnmatch(path.name, pattern):
                    warnings.append(f"Runtime log present: {rel}")

            if path.suffix == ".py":
                text = path.read_text(encoding="utf-8", errors="ignore")
                if PYQT5_IMPORT_RE.search(text):
                    errors.append(f"PyQt5 import remains in: {rel}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan the repository for obvious blockers before a MIT-source public release.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any warning or error is found.",
    )
    args = parser.parse_args()

    errors, warnings = scan_release_tree(ROOT)

    print("== Public release scan ==")
    print(f"Repository: {ROOT}")
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
