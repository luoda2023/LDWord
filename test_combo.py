import sys

from src.qt_api import QApplication, QComboBox, QColor, QListView, QTimer, Qt


class MyCombo(QComboBox):
    def showPopup(self):
        popup = self.view().window()
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        popup.setAttribute(Qt.WA_TranslucentBackground, True)
        super().showPopup()


def main() -> int:
    app = QApplication(sys.argv)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

    combo = MyCombo()
    combo.addItems(["Test Option 1", "Test Option 2", "Test Option 3"])
    combo.resize(200, 40)
    combo.setStyleSheet(
        """
        QComboBox { background: white; border: 1px solid gray; }
        """
    )

    lv = QListView(combo)
    lv.setAttribute(Qt.WA_StyledBackground, True)
    lv.setStyleSheet(
        """
        QListView {
            background: lightblue;
            border-radius: 15px;
        }
        """
    )
    combo.setView(lv)

    def run_test():
        combo.showPopup()
        QTimer.singleShot(200, grab_and_check)

    def grab_and_check():
        screen = QApplication.primaryScreen()
        top_win = lv.window()
        geom = top_win.geometry()

        img = screen.grabWindow(0, geom.x(), geom.y(), geom.width(), geom.height()).toImage()

        w, h = img.width(), img.height()
        print(f"Screen Rect Grabbed: {w}x{h} at {geom.x()},{geom.y()}")

        corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
        for idx, (x, y) in enumerate(corners):
            c = QColor(img.pixelColor(x, y))
            print(f"Corner {idx} ({x}, {y}): RGBA({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})")

        app.quit()

    combo.show()
    QTimer.singleShot(200, run_test)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
