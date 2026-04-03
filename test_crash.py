import sys

from src.qt_api import QApplication
from demo_style_gallery import StyleGallery
from src.shared.ui.theme import DARK


def main() -> int:
    app = QApplication(sys.argv)
    gallery = StyleGallery()
    gallery.show()
    print("Switching theme...")
    gallery._switch_theme(DARK)
    print("Switched successfully!")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
