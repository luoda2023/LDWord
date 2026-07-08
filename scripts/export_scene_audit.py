from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.scene_release_governance_registry import (  # noqa: E402
    SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS,
    SceneReleaseGovernanceReportSpec,
    build_scene_release_governance_report,
)


def main(argv: list[str] | None = None) -> int:
    specs_by_report_id = _specs_by_report_id()
    parser = argparse.ArgumentParser(
        description="Export a registered scene audit report.",
    )
    parser.add_argument(
        "--audit",
        required=True,
        choices=tuple(specs_by_report_id),
        help="Registered audit report id to export.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    args = parser.parse_args(argv)

    spec = specs_by_report_id[args.audit]
    if args.format == "json":
        report = _build_report(spec)
        content = json.dumps(report.to_payload(), ensure_ascii=False, indent=2)
        _write_or_print(content, args.output)
        return 0 if getattr(report, "status", "") == "passed" else 1
    return _delegate_markdown_export(spec, args.output)


def run_registered_scene_audit_export(
    report_id: str,
    argv: list[str] | None = None,
    *,
    description: str,
    markdown_formatter: Callable[[object], str],
    configure_parser: Callable[[argparse.ArgumentParser], None] | None = None,
    builder_kwargs_from_args: (
        Callable[[argparse.Namespace], Mapping[str, object]] | None
    ) = None,
) -> int:
    spec = _specs_by_report_id()[report_id]
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Export format. Defaults to markdown.",
    )
    parser.add_argument("--output", help="Optional output file. Defaults to stdout.")
    if configure_parser is not None:
        configure_parser(parser)
    args = parser.parse_args(argv)

    builder_kwargs = (
        dict(builder_kwargs_from_args(args))
        if builder_kwargs_from_args is not None
        else None
    )
    report = _build_report(spec, builder_kwargs=builder_kwargs)
    if args.format == "json":
        content = json.dumps(report.to_payload(), ensure_ascii=False, indent=2)
    else:
        content = markdown_formatter(report)
    _write_or_print(content, args.output)
    return 0 if getattr(report, "status", "") == "passed" else 1


def _specs_by_report_id() -> dict[str, SceneReleaseGovernanceReportSpec]:
    return {
        spec.report_id: spec for spec in SCENE_RELEASE_GOVERNANCE_EXPORT_REPORT_SPECS
    }


def _build_report(
    spec: SceneReleaseGovernanceReportSpec,
    *,
    builder_kwargs: Mapping[str, object] | None = None,
) -> object:
    return build_scene_release_governance_report(
        spec.report_id,
        project_root=ROOT,
        builder_kwargs=builder_kwargs,
    )


def _delegate_markdown_export(
    spec: SceneReleaseGovernanceReportSpec,
    output: str | None,
) -> int:
    export_module = _load_export_module(ROOT / spec.export_script_path)
    delegate_args = ["--format", "markdown"]
    if output:
        delegate_args.extend(["--output", output])
    return int(export_module.main(delegate_args))


def _write_or_print(content: str, output: str | None) -> None:
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content + "\n", encoding="utf-8")
    else:
        print(content)


def _load_export_module(path: Path) -> ModuleType:
    module_name = f"_scene_audit_export_{path.stem}"
    module_spec = importlib.util.spec_from_file_location(module_name, path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Cannot load export script: {path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    if not hasattr(module, "main"):
        raise RuntimeError(f"Export script has no main(): {path}")
    return module


if __name__ == "__main__":
    raise SystemExit(main())
