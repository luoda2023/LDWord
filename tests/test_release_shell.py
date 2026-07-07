from pathlib import Path

from scripts import engineering_gate


ROOT = Path(__file__).resolve().parent.parent


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
        ROOT / "scripts" / "export_scene_ambiguity_clarification_ui_audit.py",
        ROOT / "scripts" / "export_scene_ambiguous_boundary_audit.py",
        ROOT / "scripts" / "export_scene_business_capability_matrix_audit.py",
        ROOT / "scripts" / "export_scene_boundary_readiness_reconciliation_audit.py",
        ROOT / "scripts" / "export_scene_boundary_guarded_completion_audit.py",
        ROOT / "scripts" / "export_scene_boundary_subject_release_continuity_audit.py",
        ROOT / "scripts" / "export_scene_release_closure_ledger_audit.py",
        ROOT
        / "scripts"
        / "export_scene_boundary_maturity_release_envelope_audit.py",
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
        ROOT / "scripts" / "export_scene_non_subject_release_trace_attribution_audit.py",
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


def test_scene_matrix_release_gate_is_wired_into_ci_workflow():
    workflow = (
        ROOT / ".github" / "workflows" / "scene-matrix-release-gate.yml"
    ).read_text(encoding="utf-8")

    assert "Scene Matrix Release Gate" in workflow
    assert "workflow_dispatch" in workflow
    assert "python scripts/verify_scene_matrix_release_gate.py" in workflow
    assert "tests/test_scene_ambiguity_clarification_ui_audit.py" in workflow
    assert "tests/test_scene_ambiguous_boundary_audit.py" in workflow
    assert "tests/test_scene_boundary_capability_matrix.py" in workflow
    assert "tests/test_scene_boundary_readiness_reconciliation_audit.py" in workflow
    assert "tests/test_scene_boundary_guarded_completion_audit.py" in workflow
    assert "tests/test_scene_boundary_subject_release_continuity_audit.py" in workflow
    assert "tests/test_scene_release_closure_ledger_audit.py" in workflow
    assert (
        "tests/test_scene_boundary_maturity_release_envelope_audit.py" in workflow
    )
    assert "tests/test_scene_retained_gap_exit_criteria_audit.py" in workflow
    assert "tests/test_scene_release_residual_ratio_ledger_audit.py" in workflow
    assert "tests/test_scene_release_residual_explanation_audit.py" in workflow
    assert "tests/test_scene_release_acceptance_certificate_audit.py" in workflow
    assert "tests/test_scene_boundary_subject_release_dossier_audit.py" in workflow
    assert "tests/test_scene_business_capability_matrix_audit.py" in workflow
    assert "tests/test_scene_control_consistency_audit.py" in workflow
    assert "tests/test_scene_control_runtime_consistency_audit.py" in workflow
    assert "tests/test_scene_count_profile_audit.py" in workflow
    assert "tests/test_scene_delivery_preset_audit.py" in workflow
    assert "tests/test_scene_delivery_preset_execution_audit.py" in workflow
    assert "tests/test_scene_external_handoff_contract_audit.py" in workflow
    assert "tests/test_scene_family_fixture_depth_audit.py" in workflow
    assert "tests/test_scene_family_subscene_audit.py" in workflow
    assert "tests/test_scene_formula_output_watermark_audit.py" in workflow
    assert "tests/test_scene_word_risk_closure_audit.py" in workflow
    assert "tests/test_scene_sample_fixture_regression.py" in workflow
    assert "tests/test_scene_request_cell_registry_browser.py" in workflow
    assert "tests/test_scene_user_journey_fixture_audit.py" in workflow
    assert "tests/test_scene_high_frequency_completeness_audit.py" in workflow
    assert "tests/test_scene_high_frequency_request_samples.py" in workflow
    assert "tests/test_scene_high_frequency_task_lexicon_audit.py" in workflow
    assert "tests/test_scene_import_handoff_audit.py" in workflow
    assert "tests/test_scene_input_source_audit.py" in workflow
    assert "tests/test_scene_non_subject_release_trace_attribution_audit.py" in workflow
    assert "tests/test_scene_release_trace_partition_guard_audit.py" in workflow
    assert "tests/test_scene_release_projection_surface_parity_audit.py" in workflow
    assert "tests/test_scene_material_schema_audit.py" in workflow
    assert "tests/test_scene_material_repair_flow_audit.py" in workflow
    assert "tests/test_scene_fixed_layout_profile_audit.py" in workflow
    assert "tests/test_scene_report_artifact_drilldown_audit.py" in workflow
    assert "tests/test_scene_residual_warning_governance_audit.py" in workflow
    assert "tests/test_scene_terminal_release_exception_audit.py" in workflow
    assert "tests/test_scene_matrix_dashboard.py" in workflow
    assert "tests/test_scene_matrix_drilldown.py" in workflow
    assert "tests/test_scene_object_preflight_action_audit.py" in workflow
    assert "tests/test_scene_plugin_boundary_confirmation_audit.py" in workflow
    assert "tests/test_scene_product_maturity_upgrade_audit.py" in workflow
    assert "tests/test_scene_coverage_manifest.py" in workflow
    assert "tests/test_scene_parameter_ownership.py" in workflow


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
    script = (ROOT / "scripts" / "windows" / "install_env.bat").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'py -3.14 --version' in script
    assert 'python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"' in script
    assert '".venv\\Scripts\\python.exe" -m pip install -e ".[dev,build]"' in script
    assert "pyinstaller" not in requirements.lower()
    assert "pyinstaller" in pyproject.lower()
    assert "Environment is ready" in script


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


def test_windows_package_script_builds_pyside6_release_and_copies_notices():
    script = (ROOT / "scripts" / "windows" / "package_release.bat").read_text(encoding="utf-8")

    assert "PyInstaller" in script
    assert "main.py" in script
    assert "Alavette-Form_V1.0" in script
    assert "--collect-submodules PySide6" not in script
    assert '--hidden-import PySide6.QtCore' in script
    assert '--hidden-import PySide6.QtGui' in script
    assert '--hidden-import PySide6.QtWidgets' in script
    assert '--hidden-import PySide6.QtSvg' in script
    assert '--hidden-import shiboken6' in script
    assert '--exclude-module PySide6.QtGraphs' in script
    assert '--exclude-module PySide6.QtGraphsWidgets' in script
    assert '--exclude-module PySide6.QtHttpServer' in script
    assert '--exclude-module PySide6.QtNetworkAuth' in script
    assert '--exclude-module PySide6.QtQuick3D' in script
    assert '-m pip install pyinstaller' not in script
    assert "PyInstaller is missing in .venv" in script
    assert "THIRD_PARTY_NOTICES.md" in script
    assert "LICENSE" in script
    assert "defaults" in script


def test_windows_clean_script_removes_local_release_artifacts():
    script = (ROOT / "scripts" / "windows" / "clean_public_release.bat").read_text(encoding="utf-8")

    assert 'rmdir /s /q ".venv"' in script
    assert 'rmdir /s /q "build"' in script
    assert 'rmdir /s /q "dist"' in script
    assert 'del /q "crash.log"' in script
    assert 'del /q "demo_crash.log"' in script
    assert 'del /q "alavette_form.log"' in script
    assert 'for %%F in (*.spec)' in script
    assert "Failed to remove .venv" in script
    assert "Failed to remove build" in script
    assert "Failed to remove dist" in script
    assert "Failed to remove generated spec" in script


def test_public_release_checker_and_readme_document_mit_source_release():
    checker = (ROOT / "scripts" / "check_public_release.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "OPEN_SOURCE_MIT_RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    assert "--strict" in checker
    assert "THIRD_PARTY_NOTICES.md" in checker
    assert "README.md" in checker

    assert "PySide6" in readme
    assert "MIT" in readme
    assert "THIRD_PARTY_NOTICES.md" in readme
    assert ".\\install_env.bat" in readme
    assert ".\\package_release.bat" in readme
    assert ".\\check_public_release.bat" in readme
    assert ".\\clean_public_release.bat" in readme

    assert "MIT" in checklist
    assert "THIRD_PARTY_NOTICES.md" in checklist
    assert "clean_public_release.bat" in checklist


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
        assert not path.exists(), f"Local artifact should be removed before public release: {path}"
