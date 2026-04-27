"""
Alavette Form V1.0 — 主入口

用法:
    python main.py input.docx                           # CLI 模式
    python main.py input.docx -t defaults/thesis.yaml   # 指定模板
    python main.py --gui                                # GUI 模式
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.app_meta import APP_CLI_NAME, APP_DISPLAY_NAME_FULL, APP_LOG_FILE

# 项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _create_gui_exception_logger(log_path: Path):
    import logging

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog=APP_CLI_NAME,
        description=f"{APP_DISPLAY_NAME_FULL} — 文档排版格式化工具",
    )
    p.add_argument("input", nargs="?", default=None,
                   help="输入 .docx 文件路径 (GUI 模式可省略)")
    p.add_argument("-t", "--template", help="模板配置文件 (.yaml/.json)")
    p.add_argument("-s", "--scene", help="场景配置文件 (.yaml/.json)")
    p.add_argument("-o", "--output", help="输出目录 (默认: input目录/output/)")
    p.add_argument("--gui", action="store_true", help="启动 GUI 模式")
    return p.parse_args(argv)


def _start_gui() -> int:
    """启动 GUI 模式。"""
    import traceback

    from src.qt_api import QApplication, QFont, Qt

    # Hi-DPI 适配（必须在 QApplication 之前设置）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except AttributeError:
        pass  # Qt < 5.14

    from src.ui.main_window import MainWindow


    app = QApplication(sys.argv)

    # ── GUI 全局异常处理 ──
    _log_path = ROOT / APP_LOG_FILE
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
            pass

    sys.excepthook = _gui_excepthook

    # 全局字体
    font = QFont("Microsoft YaHei")
    font.setPointSize(10)
    try:
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    except AttributeError:
        pass
    app.setFont(font)

    # 全局输入守卫（滚轮防劫持 + SpinBox Enter/Click 行为修正）
    from src.shared.ui.input_guard import install_global_input_guard
    _input_guard = install_global_input_guard(app)  # noqa: F841  保持引用防 GC

    # 全局主题 tooltip，统一悬停延迟、浮层样式和锚点位置。
    from src.shared.ui.tooltip import install_global_tooltip
    _tooltip_guard = install_global_tooltip(app)  # noqa: F841  保持引用防 GC

    win = MainWindow()
    win.show()
    return app.exec()


def _run_cli(args: argparse.Namespace) -> int:
    """执行 CLI 模式。"""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"❌ 输入文件不存在: {input_path}")
        return 1
    if input_path.suffix.lower() != ".docx":
        print(f"❌ 不支持的文件格式: {input_path.suffix} (仅支持 .docx)")
        return 1

    from src.cli_runner import run

    return run(
        input_path,
        template_path=args.template,
        scene_path=args.scene,
        output_dir=Path(args.output) if args.output else None,
        project_root=ROOT,
    )


def run_app(argv: list[str] | None = None) -> int:
    """Route startup to GUI or CLI based on the provided arguments."""
    args = parse_args(argv)
    if args.gui or not args.input:
        return _start_gui()
    return _run_cli(args)


if __name__ == "__main__":
    sys.exit(run_app())
