from __future__ import annotations

from src.shared.engine.office_broker_command import (
    OFFICE_IMAGE_LAYOUT_CHILD_FLAG,
    build_office_broker_child_command,
)


def test_source_runtime_uses_module_child(tmp_path):
    request = tmp_path / "request.json"
    command = build_office_broker_child_command(
        module_name="src.shared.engine.office_image_layout",
        frozen_flag=OFFICE_IMAGE_LAYOUT_CHILD_FLAG,
        request_path=request,
        executable="python-test",
        frozen=False,
    )
    assert command == [
        "python-test",
        "-m",
        "src.shared.engine.office_image_layout",
        "--child-request",
        str(request),
    ]


def test_frozen_runtime_reenters_same_executable_before_gui(tmp_path):
    request = tmp_path / "request.json"
    command = build_office_broker_child_command(
        module_name="src.shared.engine.office_image_layout",
        frozen_flag=OFFICE_IMAGE_LAYOUT_CHILD_FLAG,
        request_path=request,
        executable="LarkFormatter.exe",
        frozen=True,
    )
    assert command == [
        "LarkFormatter.exe",
        OFFICE_IMAGE_LAYOUT_CHILD_FLAG,
        str(request),
    ]


def test_main_internal_dispatch_runs_before_argument_parser(monkeypatch, tmp_path):
    import main

    request = tmp_path / "request.json"
    monkeypatch.setattr(
        "src.shared.engine.office_image_layout.run_office_image_layout_child",
        lambda path: 17 if str(path) == str(request) else 99,
    )
    monkeypatch.setattr(
        main,
        "parse_args",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("argument parser must not run for broker child")
        ),
    )

    assert main.run_app([OFFICE_IMAGE_LAYOUT_CHILD_FLAG, str(request)]) == 17
