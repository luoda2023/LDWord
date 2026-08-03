"""
Alavette Form V1.0 — 主入口

用法:
    python main.py input.docx                          # CLI: custom/default
    python main.py input.docx --scene plan.json        # 按方案引用解析模板
    python main.py input.docx --template template.json # 显式覆盖模板
    python main.py --gui                               # GUI 模式
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src.app_meta import APP_CLI_NAME, APP_DISPLAY_NAME_FULL, APP_LOG_FILE
from src.app_paths import log_data_root
from src.services.console_output import (
    configure_console_output,
    console_print,
    write_console,
)

# 项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

_STARTUP_READY_FILE_ENV = "ALAVETTE_STARTUP_READY_FILE"
_PACKAGE_IMPORT_PROBE_FLAG = "--internal-package-import-probe"
_UNINSTALL_CLEANUP_FLAG = "--internal-uninstall-clean-user-data"


class _ConsoleSafeArgumentParser(argparse.ArgumentParser):
    def _print_message(self, message, file=None) -> None:
        if message:
            write_console(message, stream=file or sys.stderr)


def _create_gui_exception_logger(log_path: Path):
    import logging

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("alavette.gui")
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    resolved_log_path = str(log_path.resolve())
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == resolved_log_path:
            return logger

    handler = logging.FileHandler(resolved_log_path, encoding="utf-8", delay=True)
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _publish_startup_ready_probe(
    environment: dict[str, str] | None = None,
) -> Path | None:
    """Confirm to packaging QA that the main window constructed successfully."""

    values = os.environ if environment is None else environment
    destination = str(values.get(_STARTUP_READY_FILE_ENV) or "").strip()
    if not destination:
        return None
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ready\n", encoding="utf-8")
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = _ConsoleSafeArgumentParser(
        prog=APP_CLI_NAME,
        description=f"{APP_DISPLAY_NAME_FULL} — 文档排版格式化工具",
    )
    p.add_argument("input", nargs="?", default=None,
                   help="输入 .docx 文件路径 (GUI 模式可省略)")
    p.add_argument(
        "-t",
        "--template",
        help="显式模板配置文件 (.yaml/.json)；省略时使用方案引用",
    )
    p.add_argument("-s", "--scene", help="方案配置文件 (.yaml/.json)")
    p.add_argument("-o", "--output", help="输出目录 (默认: input目录/output/)")
    p.add_argument(
        "--document-type",
        default=None,
        help="公文模式的文种 ID（公文模式必填，其他模式不可用）",
    )
    p.add_argument("--gui", action="store_true", help="启动 GUI 模式")
    p.add_argument(
        "--font-engine",
        choices=("freetype", "directwrite", "system"),
        default=None,
        help=(
            "Windows GUI 字体后端（默认 freetype；也可通过 "
            "ALAVETTE_FORM_FONT_ENGINE 设置）"
        ),
    )
    return p.parse_args(argv)


def _start_gui(font_engine: str | None = None) -> int:
    """启动 GUI 模式。"""
    # The Windows font backend is a QPA startup option and must be selected
    # before src.qt_api imports PySide6 or QApplication is constructed.
    from src.shared.ui.font_engine_policy import (
        configure_application_windows_font_engine,
    )

    font_engine_configuration = configure_application_windows_font_engine(font_engine)

    import traceback

    from PySide6.QtCore import QDir, QLockFile
    from src.qt_api import QApplication, Qt

    # PySide6 always enables high-DPI support. Keep the exact Windows scale;
    # custom-painted strokes are snapped at the paint boundary instead.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    from src.shared.ui.icons.catalog import get_application_icon

    app.setWindowIcon(get_application_icon())
    instance_lock = QLockFile(
        QDir.temp().filePath("alavette-form-v1-gui.lock")
    )
    instance_lock_acquired = instance_lock.tryLock(0)

    # FreeType needs the OS-provided YaHei TTC faces registered explicitly so
    # that weight 700 resolves the real Bold face instead of synthetic bold.
    # This must precede imports that may construct application fonts/widgets.
    from src.shared.ui.typography_policy import (
        apply_application_typography,
        register_windows_ui_fonts_for_freetype,
    )

    _font_registration = register_windows_ui_fonts_for_freetype(
        font_engine_configuration.engine
    )
    apply_application_typography(app)

    if not instance_lock_acquired:
        from src.shared.ui.dialogs import info as show_info

        show_info(
            "程序已在运行",
            "Alavette Form 已经打开。请使用现有窗口，避免两个实例持有不同的草稿状态。",
        )
        return 0

    from src.ui.startup_splash import StartupSplash

    splash = StartupSplash()
    splash.show()
    splash.set_status("正在准备工作台")
    app.processEvents()

    from src.ui.main_window import MainWindow

    # ── GUI 全局异常处理 ──
    _log_path = log_data_root() / APP_LOG_FILE
    gui_logger = _create_gui_exception_logger(_log_path)

    def _gui_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        gui_logger.error(msg)
        try:
            from src.shared.ui.dialogs import error as show_error
            show_error(
                title="未预期错误",
                message="发生了意外错误，已记录到日志文件。",
                detail=msg,
                log_path=str(_log_path),
            )
        except Exception:
            gui_logger.exception("Failed to display the unhandled-exception dialog")

    sys.excepthook = _gui_excepthook

    # 全局输入守卫（滚轮防劫持 + SpinBox Enter/Click 行为修正）
    from src.shared.ui.input_guard import install_global_input_guard
    _input_guard = install_global_input_guard(app)

    # 全局主题 tooltip，统一悬停延迟、浮层样式和锚点位置。
    from src.shared.ui.tooltip import install_global_tooltip
    _tooltip_guard = install_global_tooltip(app)

    win = MainWindow(enable_background_services=True)

    def _show_main_window() -> None:
        splash.set_status("正在打开首页")
        win.show()
        app.processEvents()
        splash.finish_and_close()
        _publish_startup_ready_probe()

    win.startup_status_changed.connect(splash.set_status)
    win.startup_ready.connect(_show_main_window)
    try:
        return app.exec()
    finally:
        instance_lock.unlock()


def _run_cli(args: argparse.Namespace) -> int:
    """执行 CLI 模式。"""
    input_path = Path(args.input)

    if not input_path.exists():
        console_print(f"[ERROR] 输入文件不存在: {input_path}")
        return 1
    if input_path.suffix.lower() != ".docx":
        console_print(
            f"[ERROR] 不支持的文件格式: {input_path.suffix} (仅支持 .docx)"
        )
        return 1

    from src.cli_runner import run

    try:
        return run(
            input_path,
            template_path=args.template,
            scene_path=args.scene,
            output_dir=Path(args.output) if args.output else None,
            document_type_id=args.document_type,
        )
    except Exception as exc:  # noqa: BLE001 - CLI process boundary
        console_print(f"[ERROR] CLI 未预期失败: {str(exc) or type(exc).__name__}")
        return 1


def run_app(argv: list[str] | None = None) -> int:
    """Route startup to GUI or CLI based on the provided arguments."""
    configure_console_output()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    maintenance_result = _run_internal_maintenance_command(raw_argv)
    if maintenance_result is not None:
        return maintenance_result
    internal_result = _run_internal_office_child(raw_argv)
    if internal_result is not None:
        return internal_result
    args = parse_args(raw_argv)
    if args.gui or not args.input:
        return _start_gui(args.font_engine)
    return _run_cli(args)


def _run_internal_maintenance_command(argv: list[str]) -> int | None:
    """Run release-owned internal commands before public argument parsing."""

    if argv == [_PACKAGE_IMPORT_PROBE_FLAG]:
        return _run_package_import_probe()

    if argv != [_UNINSTALL_CLEANUP_FLAG]:
        return None
    from src.services.user_data_cleanup import clear_current_user_data

    try:
        result = clear_current_user_data()
    except Exception:  # noqa: BLE001 - process boundary used by the uninstaller
        return 1
    return 0 if result.succeeded else 1


def _run_package_import_probe() -> int:
    """Verify frozen-only and lazy UI imports in the installed payload."""

    from importlib import import_module

    required_modules = (
        "win32timezone",
        "src.ui.panels.preferences_panel",
        "src.assistant.ui.assistant_panel",
        "src.ui.panels.workbench.batch_generation_detail",
        "src.ui.panels.workbench.file_batch_execution_detail",
    )
    try:
        for module_name in required_modules:
            import_module(module_name)
    except Exception:  # noqa: BLE001 - executable self-test process boundary
        return 1
    return 0


def _run_internal_office_child(argv: list[str]) -> int | None:
    """Dispatch frozen broker children before importing Qt or app surfaces."""

    if len(argv) != 2:
        return None
    flag, request_path = argv
    from src.shared.engine.office_broker_command import (
        MATHTYPE_OFFICE_CHILD_FLAG,
        OFFICE_IMAGE_LAYOUT_CHILD_FLAG,
        OFFICE_LAYOUT_PROBE_CHILD_FLAG,
    )

    if flag == MATHTYPE_OFFICE_CHILD_FLAG:
        from src.shared.io.mathtype_office_fallback import (
            run_mathtype_office_child,
        )

        return run_mathtype_office_child(request_path)

    if flag == OFFICE_IMAGE_LAYOUT_CHILD_FLAG:
        from src.shared.engine.office_image_layout import (
            run_office_image_layout_child,
        )

        return run_office_image_layout_child(request_path)
    if flag == OFFICE_LAYOUT_PROBE_CHILD_FLAG:
        from src.shared.engine.office_layout_probe import (
            run_office_layout_probe_child,
        )

        return run_office_layout_probe_child(request_path)
    return None


if __name__ == "__main__":
    sys.exit(run_app())
