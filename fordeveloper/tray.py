from __future__ import annotations

import signal
import sys
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from config import HOST, PORT


APP_NAME = "Deployment Tracking"
APP_URL = f"http://{HOST}:{PORT}/"


def generate_tray_icon(size: int = 22) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    pen = QPen(QColor("#f59e0b"))
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    painter.drawLine(9, 5, 4, 11)
    painter.drawLine(4, 11, 9, 17)
    painter.drawLine(size - 9, 5, size - 4, 11)
    painter.drawLine(size - 4, 11, size - 9, 17)

    slash_pen = QPen(QColor("#f59e0b"))
    slash_pen.setWidthF(2.0)
    slash_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(slash_pen)
    painter.drawLine(13, 6, 9, 16)

    painter.end()
    return QIcon(pixmap)


def open_app_url() -> None:
    webbrowser.open(APP_URL)


def main() -> int:
    if hasattr(signal, "SIGHUP"):
        try:
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
        except (OSError, ValueError):
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        sys.stderr.write("System tray kullanilamiyor.\n")
        return 1

    tray = QSystemTrayIcon(generate_tray_icon())
    tray.setToolTip(f"{APP_NAME} - {APP_URL}")

    menu = QMenu()

    open_action = QAction(f"{APP_NAME} Ac", menu)
    open_action.triggered.connect(open_app_url)
    menu.addAction(open_action)

    menu.addSeparator()

    quit_action = QAction("Cikis", menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    def handle_activation(reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            open_app_url()
        elif reason == QSystemTrayIcon.Context:
            menu.popup(QCursor.pos())

    tray.activated.connect(handle_activation)
    tray.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
