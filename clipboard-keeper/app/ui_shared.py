from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QVBoxLayout


APP_STYLE = """
QWidget {
    background: #f6f7fb;
    color: #172033;
    font-family: "Helvetica Neue", Arial;
    font-size: 13px;
}
QMainWindow {
    background: #f6f7fb;
}
QFrame#Surface, QFrame#Card, QFrame#EditorCard {
    background: #ffffff;
    border: 1px solid #dde3f0;
    border-radius: 16px;
}
QFrame#Card:hover {
    border-color: #b7c8f6;
}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox {
    background: #ffffff;
    border: 1px solid #d8dfec;
    border-radius: 12px;
    padding: 8px 10px;
    selection-background-color: #2b6cf6;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border-color: #2b6cf6;
}
QPushButton, QToolButton {
    background: #edf2ff;
    border: 1px solid #d8e4ff;
    border-radius: 12px;
    padding: 8px 12px;
    color: #16336b;
}
QPushButton:hover, QToolButton:hover {
    background: #e1ebff;
}
QPushButton#PrimaryButton {
    background: #2b6cf6;
    border: 1px solid #2b6cf6;
    color: white;
}
QPushButton#PrimaryButton:hover {
    background: #1e5de0;
}
QPushButton#DangerButton {
    background: #fff1f2;
    border: 1px solid #ffd4db;
    color: #9f1239;
}
QLabel#TitleLabel {
    font-size: 21px;
    font-weight: 700;
}
QLabel#MutedLabel {
    color: #5d6780;
}
QLabel#SectionLabel {
    font-size: 15px;
    font-weight: 700;
    color: #24314d;
}
QLabel#BadgeLabel {
    background: #eef3ff;
    color: #1f57d1;
    border: 1px solid #d6e2ff;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    background: #e8edf8;
    border: none;
    padding: 10px 14px;
    margin-right: 6px;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}
QTabBar::tab:selected {
    background: #ffffff;
}
QScrollArea {
    border: none;
    background: transparent;
}
QStatusBar {
    background: #ffffff;
    border-top: 1px solid #e1e6f2;
}
"""


def generate_tray_icon(size: int = 22) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    pen = QPen(QColor("#2563eb"))
    pen.setWidthF(1.7)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(4, 3, size - 8, size - 7, 4, 4)
    painter.drawRoundedRect(size / 2 - 4, 1.5, 8, 5, 3, 3)
    painter.drawLine(7, 10, size - 7, 10)
    painter.drawLine(7, 14, size - 7, 14)
    painter.drawLine(7, 18, size - 11, 18)
    painter.end()
    return QIcon(pixmap)


def clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)  # type: ignore[arg-type]
