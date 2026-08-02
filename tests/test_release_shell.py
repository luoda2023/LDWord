import ast
import json
from pathlib import Path

from docx import Document

from scripts import check_public_release, engineering_gate
from src.ui.panel_registry import PANEL_FACTORIES

ROOT = Path(__file__).resolve().parent.parent


def _required_lazy_shared_ui_hidden_imports() -> set[str]:
    init_path = ROOT / "src" / "shared" / "ui" / "__init__.py"
    init_tree = ast.parse(init_path.read_text(encoding="utf-8-sig"))
    export_map: dict[str, tuple[str, str]] = {}
    for node in init_tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_EXPORT_MAP"
        ):
            export_map = ast.literal_eval(node.value)
            break

    imported_names: set[str] = set()
    for source_path in (ROOT / "src").rglob("*.py"):
        source_tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(source_tree):
            if isinstance(node, ast.ImportFrom) and node.module == "src.shared.ui":
                imported_names.update(alias.name for alias in node.names)

    missing_exports = imported_names.difference(export_map)
    assert not missing_exports, (
        "src.shared.ui package imports must resolve through _EXPORT_MAP: "
        f"{sorted(missing_exports)}"
    )
    return {f"src.shared.ui{export_map[name][0]}" for name in imported_names}


def _pyinstaller_hidden_imports() -> set[str]:
    tree = ast.parse((ROOT / "Alavette-Form_V1.0.spec").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Analysis":
            for keyword in node.keywords:
                if keyword.arg == "hiddenimports":
                    return set(ast.literal_eval(keyword.value))
    raise AssertionError("PyInstaller Analysis.hiddenimports is missing")


def test_release_shell_files_exist():
    required_files = [
        ROOT / "README.md",
        ROOT / ".github" / "workflows" / "engineering-gate.yml",
        ROOT / ".github" / "workflows" / "scene-matrix-release-gate.yml",
        ROOT / "install_env.bat",
        ROOT / "package_release.bat",
        ROOT / "check_public_release.bat",
        ROOT / "clean_public_release.bat",
        ROOT / "scripts" / "windows" / "install_env.bat",
        ROOT / "scripts" / "windows" / "engineering_gate.bat",
        ROOT / "scripts" / "windows" / "package_release.bat",
        ROOT / "scripts" / "windows" / "check_public_release.bat",
        ROOT / "scripts" / "windows" / "clean_public_release.bat",
        ROOT / "scripts" / "check_public_release.py",
        ROOT / "scripts" / "build_release.py",
        ROOT / "scripts" / "generate_windows_version_info.py",
        ROOT / "scripts" / "stage_source_release.py",
        ROOT / "scripts" / "verify_release_environment.py",
        ROOT / "requirements-release.lock",
        ROOT / "Alavette-Form_V1.0.spec",
        ROOT / "scripts" / "scene_matrix_release_gate_payload.py",
        ROOT / "scripts" / "export_scene_ambiguity_clarification_ui_audit.py",
        ROOT / "scripts" / "export_scene_ambiguous_boundary_audit.py",
        ROOT / "scripts" / "export_scene_business_capability_matrix_audit.py",
        ROOT / "scripts" / "export_scene_boundary_readiness_reconciliation_audit.py",
        ROOT / "scripts" / "export_scene_boundary_guarded_completion_audit.py",
        ROOT / "scripts" / "export_scene_boundary_subject_release_continuity_audit.py",
        ROOT / "scripts" / "export_scene_release_closure_ledger_audit.py",
        ROOT / "scripts" / "export_scene_boundary_maturity_release_envelope_audit.py",
        ROOT / "scripts" / "export_scene_retained_gap_exit_criteria_audit.py",
        ROOT / "scripts" / "export_scene_release_residual_ratio_ledger_audit.py",
        ROOT / "scripts" / "export_scene_release_residual_explanation_audit.py",
        ROOT / "scripts" / "export_scene_release_acceptance_certificate_audit.py",
        ROOT / "scripts" / "export_scene_boundary_subject_release_dossier_audit.py",
        ROOT / "scripts" / "export_scene_control_consistency_audit.py",
        ROOT / "scripts" / "export_scene_control_runtime_consistency_audit.py",
        ROOT / "scripts" / "export_scene_count_profile_audit.py",
        ROOT / "scripts" / "export_scene_delivery_preset_audit.py",
        ROOT / "scripts" / "export_scene_delivery_preset_execution_audit.py",
        ROOT / "scripts" / "export_scene_external_handoff_contract_audit.py",
        ROOT / "scripts" / "export_scene_family_subscene_audit.py",
        ROOT / "scripts" / "export_scene_family_fixture_depth_audit.py",
        ROOT / "scripts" / "export_scene_formula_output_watermark_audit.py",
        ROOT / "scripts" / "export_scene_high_frequency_completeness.py",
        ROOT / "scripts" / "export_scene_high_frequency_task_lexicon_audit.py",
        ROOT / "scripts" / "export_scene_import_handoff_audit.py",
        ROOT / "scripts" / "export_scene_input_source_audit.py",
        ROOT
        / "scripts"
        / "export_scene_non_subject_release_trace_attribution_audit.py",
        ROOT / "scripts" / "export_scene_release_trace_partition_guard_audit.py",
        ROOT / "scripts" / "export_scene_release_projection_surface_parity_audit.py",
        ROOT / "scripts" / "export_scene_material_schema_audit.py",
        ROOT / "scripts" / "export_scene_material_repair_flow_audit.py",
        ROOT / "scripts" / "export_scene_fixed_layout_profile_audit.py",
        ROOT / "scripts" / "export_scene_report_artifact_drilldown_audit.py",
        ROOT / "scripts" / "export_scene_residual_warning_governance_audit.py",
        ROOT / "scripts" / "export_scene_terminal_release_exception_audit.py",
        ROOT / "scripts" / "export_scene_matrix_dashboard.py",
        ROOT / "scripts" / "export_scene_matrix_drilldown.py",
        ROOT / "scripts" / "export_scene_object_preflight_action_audit.py",
        ROOT / "scripts" / "export_scene_plugin_boundary_confirmation_audit.py",
        ROOT / "scripts" / "export_scene_product_maturity_upgrade_audit.py",
        ROOT / "scripts" / "export_scene_request_cell_registry.py",
        ROOT / "scripts" / "export_scene_user_journey_fixture_audit.py",
        ROOT / "scripts" / "export_scene_word_risk_closure_audit.py",
        ROOT / "docs" / "OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md",
    ]

    for path in required_files:
        assert path.exists(), f"Missing release-shell file: {path}"


def test_root_batch_wrappers_delegate_to_windows_scripts():
    install_wrapper = (ROOT / "install_env.bat").read_text(encoding="utf-8")
    package_wrapper = (ROOT / "package_release.bat").read_text(encoding="utf-8")
    public_wrapper = (ROOT / "check_public_release.bat").read_text(encoding="utf-8")
    clean_wrapper = (ROOT / "clean_public_release.bat").read_text(encoding="utf-8")

    assert 'call "%~dp0scripts\\windows\\install_env.bat" %*' in install_wrapper
    assert 'call "%~dp0scripts\\windows\\package_release.bat" %*' in package_wrapper
    assert 'call "%~dp0scripts\\windows\\check_public_release.bat" %*' in public_wrapper
    assert 'call "%~dp0scripts\\windows\\clean_public_release.bat" %*' in clean_wrapper


def test_windows_install_script_bootstraps_env_from_pyproject_extras():
    script = (ROOT / "scripts" / "windows" / "install_env.bat").read_text(
        encoding="utf-8"
    )
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "py -3.12 --version" in script
    assert "requirements-release.lock" in script
    assert 'pip install -c "requirements-release.lock" -e ".[dev,build]"' in script
    assert "scripts\\verify_release_environment.py" in script
    assert "py -3.14" not in script
    assert "pyinstaller" not in requirements.lower()
    assert "pyinstaller" in pyproject.lower()
    assert "CPython 3.12" in script


def test_windows_engineering_gate_script_delegates_to_python_gate():
    script = (ROOT / "scripts" / "windows" / "engineering_gate.bat").read_text(
        encoding="utf-8"
    )

    assert 'cd /d "%~dp0..\\.."' in script
    assert "python scripts\\engineering_gate.py %*" in script
    assert "exit /b %ERRORLEVEL%" in script


def test_engineering_gate_ci_installs_dev_dependencies_from_pyproject():
    workflow = (ROOT / ".github" / "workflows" / "engineering-gate.yml").read_text(
        encoding="utf-8"
    )
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "python scripts/engineering_gate.py" in workflow
    assert 'python -m pip install -e ".[dev]"' in workflow
    assert any(
        command[1:3] == ("-m", "pytest")
        for command, _summarize_success in engineering_gate.BASELINE_COMMANDS
    )
    assert "pytest" not in requirements.lower()
    assert "pytest" in pyproject.lower()


def test_engineering_gate_uses_explicit_low_dispute_ruff_rules():
    ruff_commands = [
        command
        for command, _summarize_success in engineering_gate.BASELINE_COMMANDS
        if command[1:3] == ("-m", "ruff")
    ]

    assert len(ruff_commands) == 1
    command = ruff_commands[0]
    assert command[3:6] == ("check", "--select", "E9,F63,F7,F82")
    assert command[6:] == ("main.py", "scripts", "src", "tests")


def test_ci_workflows_install_project_dev_dependency_profile():
    workflow_dir = ROOT / ".github" / "workflows"
    workflows = {
        "engineering-gate.yml": (workflow_dir / "engineering-gate.yml").read_text(
            encoding="utf-8"
        ),
        "scene-matrix-release-gate.yml": (
            workflow_dir / "scene-matrix-release-gate.yml"
        ).read_text(encoding="utf-8"),
    }

    for workflow_name, workflow in workflows.items():
        assert 'python -m pip install -e ".[dev]"' in workflow, workflow_name
        assert "python-docx lxml PyYAML pytest" not in workflow, workflow_name


def test_windows_package_script_delegates_to_gated_release_builder():
    script = (ROOT / "scripts" / "windows" / "package_release.bat").read_text(
        encoding="utf-8"
    )
    builder = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")

    assert "scripts\\verify_release_environment.py" in script
    assert '"scripts\\build_release.py" %*' in script
    for marker in (
        "scripts/engineering_gate.py",
        "scripts/verify_scene_matrix_release_gate.py",
        '"pytest", "-q", "tests"',
        "stage_source_revision",
        'kind="source"',
        "PyInstaller",
        "stage_user_documentation.ps1",
        "scan_binary_release_tree",
        "_sign_and_verify",
        "SBOM.cdx.json",
        "RELEASE_MANIFEST.json",
        "UNSIGNED-QA",
    ):
        assert marker in builder
    assert builder.count("cwd=source_root") >= 7

    hidden_imports = _pyinstaller_hidden_imports()
    assert {factory.module_name for factory in PANEL_FACTORIES.values()}.issubset(
        hidden_imports
    )
    assert {
        item for item in hidden_imports if item.startswith("src.shared.ui.")
    } == _required_lazy_shared_ui_hidden_imports()
    spec = (ROOT / "Alavette-Form_V1.0.spec").read_text(encoding="utf-8")
    assert "version='build\\\\windows_version_info.txt'" in spec
    assert "contents_directory='.'" in spec
    assert "('licenses', 'licenses')" in spec
    assert (
        "('src\\\\shared\\\\ui\\\\icons\\\\app_logo.svg', "
        "'src\\\\shared\\\\ui\\\\icons')"
    ) in spec
    assert "('src\\\\shared\\\\ui\\\\icons', 'src\\\\shared\\\\ui\\\\icons')" not in spec
    assert "('RELEASE_NOTES.md', '.')" in spec
    assert "('SECURITY.md', '.')" in spec
    assert "('build\\\\release_config_library', 'config_library')" in spec
    assert "src.document_batch.plan" not in hidden_imports


def test_windows_clean_script_removes_local_release_artifacts():
    script = (ROOT / "scripts" / "windows" / "clean_public_release.bat").read_text(
        encoding="utf-8"
    )

    assert 'rmdir /s /q "build"' in script
    assert 'rmdir /s /q "dist"' in script
    assert 'rmdir /s /q ".venv"' not in script
    assert "*.spec" not in script
    assert "alavette_form.log" not in script
    assert "never deletes .venv" in script
    assert "Failed to remove generated build directory" in script


def test_public_release_checker_and_readme_document_mit_source_release():
    checker = (ROOT / "scripts" / "check_public_release.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md").read_text(
        encoding="utf-8"
    )

    assert "--strict" in checker
    assert "THIRD_PARTY_NOTICES.md" in checker
    assert "licenses/manifest.json" in checker
    assert "docs/user/quick-start.md" in checker
    assert "docs/user/user-guide.md" in checker
    assert "docs/user/00-开始这里.md" in checker
    assert "README.md" in checker
    assert "exam_masters/user" in checker
    assert "config_library/plans/*/user" in checker
    assert "config_library/material_packages/*/user" in checker

    assert "PySide6" in readme
    assert "MIT" in readme
    assert "THIRD_PARTY_NOTICES.md" in readme
    assert "licenses/manifest.json" in readme
    assert ".\\install_env.bat" in readme
    assert ".\\package_release.bat" in readme
    assert ".\\check_public_release.bat" in readme
    assert ".\\clean_public_release.bat" in readme
    assert "docs/user/quick-start.md" in readme
    assert "docs/user/user-guide.md" in readme
    assert "docs/user/00-开始这里.md" in readme

    assert "MIT" in checklist
    assert "THIRD_PARTY_NOTICES.md" in checklist
    assert "Lucide" in checklist
    assert "Feather" in checklist
    assert "clean_public_release.bat" in checklist
    assert "docs/user/" in checklist


def test_public_release_checker_flags_user_resource_pools_without_blocking_builtins(
    tmp_path,
):
    for rel in check_public_release.REQUIRED_DOCS:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix.casefold() == ".docx":
            document = Document()
            document.core_properties.author = "Alavette Form"
            document.core_properties.last_modified_by = "Alavette Form"
            document.add_paragraph("synthetic fixture")
            document.save(target)
        else:
            target.write_text("placeholder", encoding="utf-8")
    license_text = tmp_path / "licenses" / "fixture-license.txt"
    license_text.write_text("fixture license", encoding="utf-8")
    components = [
        {
            "id": component_id,
            "name": component_id,
            "purpose": "fixture",
            "license_expression": "MIT",
            "python_distributions": [],
            "documents": [
                {
                    "title": "fixture",
                    "path": "fixture-license.txt",
                }
            ],
        }
        for component_id in (
            "python-runtime",
            "qt-for-python",
            "lucide-icons",
            "openssl",
        )
    ]
    components[1].update(
        {
            "license_expression": "LGPL-3.0-only",
            "declared_license_expression": "LGPL-3.0-only OR GPL-3.0-only",
            "documents": [
                {
                    "title": "LGPLv3",
                    "license_id": "LGPL-3.0-only",
                    "path": "fixture-license.txt",
                },
                {
                    "title": "GPLv3",
                    "license_id": "GPL-3.0-only",
                    "path": "fixture-license.txt",
                },
            ],
        }
    )
    (tmp_path / "licenses" / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "component_count": len(components),
                "components": components,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "THIRD_PARTY_NOTICES.md").write_text(
        "Lucide Feather Qt for Python Alavette Flow",
        encoding="utf-8",
    )

    user_dirs = [
        tmp_path / "exam_masters" / "user",
        tmp_path / "config_library" / "plans" / "exam" / "user",
        tmp_path / "config_library" / "templates" / "official" / "user",
        tmp_path / "config_library" / "masters" / "exam" / "user",
        tmp_path / "config_library" / "material_packages" / "official" / "user",
    ]
    builtin_dirs = [
        tmp_path / "exam_masters" / "builtin",
        tmp_path / "config_library" / "plans" / "exam" / "builtin",
        tmp_path / "config_library" / "templates" / "official" / "builtin",
        tmp_path / "config_library" / "masters" / "exam" / "builtin",
        tmp_path / "config_library" / "material_packages" / "official" / "builtin",
    ]
    for directory in (*user_dirs, *builtin_dirs):
        directory.mkdir(parents=True)
        (directory / ".keep").write_text("", encoding="utf-8")

    errors, warnings = check_public_release.scan_release_tree(tmp_path)
    warning_text = "\n".join(warnings)

    assert errors == []
    assert (
        "Runtime/user path should not be published: exam_masters/user" in warning_text
    )
    assert (
        "Runtime/user path should not be published: config_library/plans/exam/user"
        in warning_text
    )
    assert (
        "Runtime/user path should not be published: config_library/templates/official/user"
        in warning_text
    )
    assert (
        "Runtime/user path should not be published: config_library/masters/exam/user"
        in warning_text
    )
    assert (
        "Runtime/user path should not be published: config_library/material_packages/official/user"
        in warning_text
    )
    assert "exam_masters/builtin" not in warning_text
    assert "config_library/plans/exam/builtin" not in warning_text
    assert "config_library/templates/official/builtin" not in warning_text
    assert "config_library/masters/exam/builtin" not in warning_text
    assert "config_library/material_packages/official/builtin" not in warning_text


def test_gitignore_covers_local_release_artifacts():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for entry in [
        ".venv/",
        "build/",
        "dist/",
        "crash.log",
        "demo_crash.log",
        "alavette_form.log",
        "*_new.docx",
        "/exam_masters/",
        "config_library/plans/*/user/",
        "config_library/templates/*/user/",
        "config_library/masters/*/user/",
        "config_library/material_packages/*/user/",
        ".pytest_cache/",
    ]:
        assert entry in gitignore


def test_no_local_release_artifacts_remain_in_workspace():
    unwanted_paths = [
        ROOT / "crash.log",
        ROOT / "demo_crash.log",
        ROOT / "alavette_form.log",
        ROOT / "tests" / "test_input_new.docx",
        ROOT / "tests" / "TEST-1" / "测试文档_new.docx",
    ]

    for path in unwanted_paths:
        assert not path.exists(), (
            f"Local artifact should be removed before public release: {path}"
        )
