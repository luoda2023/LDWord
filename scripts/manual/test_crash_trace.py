import sys

try:
    from ._bootstrap import ensure_project_root
except ImportError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from src.qt_api import QApplication


def log(msg):
    print(msg)
    sys.stdout.flush()


def main() -> int:
    try:
        log("1. Importing StyleGallery...")
        from demo_style_gallery import StyleGallery
        from src.shared.ui.theme import DARK

        app = QApplication(sys.argv)
        log("2. Creating gallery...")
        gallery = StyleGallery()
        log("3. Showing gallery...")
        gallery.show()
        log("4. Switching theme...")
        gallery._switch_theme(DARK)
        log("5. Switched successfully!")
        app.processEvents()
        log("6. Processed events successfully, entering main loop...")
        return app.exec()
    except Exception:
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
