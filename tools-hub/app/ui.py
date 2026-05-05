from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QCursor, QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .constants import APP_NAME
from .discovery import discover_apps
from .manager import AppManager
from .models import DiscoveredApp
from .projects_view import ProjectsView
from .state import HubState
from .utils import (
    activate_pid,
    describe_pid,
    find_pids_by_port,
    find_ports_by_pid,
    format_dt,
    is_pid_running,
    is_url_reachable,
    kill_pid,
    kill_port,
    tail_file,
)


APP_STYLE = """
* {
    font-family: "SF Pro Text", "Helvetica Neue", "Inter", Arial, sans-serif;
}
QMainWindow, QWidget#RootSurface {
    background: #F5F6F9;
}
QWidget {
    color: #0F172A;
    font-size: 13px;
}

/* ---------- Sidebar ---------- */
QFrame#Sidebar {
    background: #0E1117;
    border: none;
}
QLabel#SidebarBrand {
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.2px;
}
QLabel#SidebarTagline {
    color: #6B7280;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.3px;
}
QLabel#SidebarSection {
    color: #6B7280;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 4px 4px 2px 4px;
}
QPushButton#NavButton {
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    color: #C7CDD6;
    font-size: 13.5px;
    font-weight: 500;
    text-align: left;
}
QPushButton#NavButton:hover {
    background: #1A1F29;
    color: #FFFFFF;
}
QPushButton#NavButton[active="true"] {
    background: #1F2530;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton#SidebarAction {
    background: transparent;
    border: 1px solid #20242E;
    border-radius: 10px;
    padding: 8px 12px;
    color: #C7CDD6;
    font-weight: 500;
    text-align: left;
}
QPushButton#SidebarAction:hover {
    background: #1A1F29;
    border-color: #2A3140;
    color: #FFFFFF;
}
QToolButton#SidebarToolMenu {
    background: transparent;
    border: 1px solid #20242E;
    border-radius: 10px;
    padding: 8px 12px;
    color: #C7CDD6;
    font-weight: 500;
    text-align: left;
}
QToolButton#SidebarToolMenu:hover {
    background: #1A1F29;
    border-color: #2A3140;
    color: #FFFFFF;
}
QToolButton#SidebarToolMenu::menu-indicator {
    image: none;
    width: 0;
}
QFrame#SidebarDivider {
    background: #1B1F27;
    max-height: 1px;
    min-height: 1px;
    margin: 8px 4px;
    border: none;
}
QFrame#SidebarFooter {
    background: transparent;
    border-top: 1px solid #1B1F27;
}

/* ---------- Surfaces ---------- */
QFrame#Surface {
    background: #FFFFFF;
    border: 1px solid #E5E7EE;
    border-radius: 14px;
}
QFrame#Card {
    background: #FFFFFF;
    border: 1px solid #E5E7EE;
    border-radius: 12px;
}
QFrame#Card:hover {
    border-color: #C8CFDC;
}
QFrame#Card[selected="true"] {
    border: 1px solid #4F46E5;
    background: #F7F7FE;
}
QFrame#DetailCard {
    background: #FFFFFF;
    border: 1px solid #E5E7EE;
    border-radius: 14px;
}
QFrame#InsetPanel {
    background: #F8F9FC;
    border: 1px solid #ECEEF3;
    border-radius: 12px;
}
QFrame#SectionDivider {
    background: #ECEEF3;
    max-height: 1px;
    min-height: 1px;
    border: none;
}

/* ---------- Header ---------- */
QFrame#HeaderBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 1px solid #ECEEF3;
}
QLabel#HeaderTitle {
    color: #0F172A;
    font-size: 19px;
    font-weight: 700;
    letter-spacing: -0.3px;
}
QLabel#HeaderSubtitle {
    color: #64748B;
    font-size: 12px;
    font-weight: 500;
}

/* ---------- Typography ---------- */
QLabel#TitleLabel {
    font-size: 22px;
    font-weight: 700;
    color: #0F172A;
    letter-spacing: -0.3px;
}
QLabel#SectionLabel {
    font-size: 13.5px;
    font-weight: 700;
    color: #0F172A;
    letter-spacing: -0.1px;
}
QLabel#GroupLabel {
    color: #64748B;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 1.0px;
}
QLabel#MutedLabel {
    color: #64748B;
}
QLabel#FaintLabel {
    color: #94A3B8;
    font-size: 11.5px;
}
QLabel#StatNumber {
    color: #0F172A;
    font-size: 18px;
    font-weight: 700;
}
QLabel#StatLabel {
    color: #64748B;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

/* ---------- Badges ---------- */
QLabel#BadgeBlue, QLabel#BadgeGreen, QLabel#BadgeGray,
QLabel#BadgeOrange, QLabel#BadgeRed, QLabel#BadgeIndigo {
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.4px;
}
QLabel#BadgeBlue {
    background: #EEF2FF;
    color: #4338CA;
}
QLabel#BadgeIndigo {
    background: #F3F2FE;
    color: #4F46E5;
}
QLabel#BadgeGreen {
    background: #ECFDF5;
    color: #047857;
}
QLabel#BadgeGray {
    background: #F1F3F8;
    color: #64748B;
}
QLabel#BadgeOrange {
    background: #FFF7ED;
    color: #C2410C;
}
QLabel#BadgeRed {
    background: #FEF2F2;
    color: #B91C1C;
}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit {
    background: #FFFFFF;
    border: 1px solid #DDE1EA;
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: #C7D2FE;
    selection-color: #1E1B4B;
}
QLineEdit:focus, QPlainTextEdit:focus {
    border-color: #4F46E5;
}
QLineEdit#SearchInput {
    padding-left: 14px;
    font-size: 13px;
}
QPlainTextEdit {
    font-family: "JetBrains Mono", "SF Mono", "Menlo", monospace;
    font-size: 12px;
    color: #1F2937;
}

/* ---------- Buttons ---------- */
QPushButton {
    background: #FFFFFF;
    border: 1px solid #DDE1EA;
    border-radius: 9px;
    padding: 7px 14px;
    color: #1F2937;
    font-weight: 600;
    font-size: 12.5px;
}
QPushButton:hover {
    background: #F8F9FC;
    border-color: #BFC6D4;
    color: #0F172A;
}
QPushButton:pressed {
    background: #EEF0F4;
    border-color: #9AA3B8;
}
QPushButton:focus {
    outline: none;
    border-color: #4F46E5;
}
QPushButton:disabled {
    background: #F4F5F8;
    border-color: #E5E7EE;
    color: #B0B7C5;
}
QPushButton#PrimaryButton {
    background: #4F46E5;
    color: #FFFFFF;
    border: 1px solid #4F46E5;
}
QPushButton#PrimaryButton:hover {
    background: #4338CA;
    border-color: #4338CA;
}
QPushButton#PrimaryButton:pressed {
    background: #3730A3;
    border-color: #3730A3;
}
QPushButton#PrimaryButton:disabled {
    background: #C7C5F4;
    border-color: #C7C5F4;
    color: #FFFFFF;
}
QPushButton#DangerButton {
    background: #FFFFFF;
    color: #B91C1C;
    border: 1px solid #FECACA;
}
QPushButton#DangerButton:hover {
    background: #FEF2F2;
    border-color: #F87171;
    color: #991B1B;
}
QPushButton#DangerButton:pressed {
    background: #FEE2E2;
    border-color: #DC2626;
}
QPushButton#DangerButton:disabled {
    background: #FCFCFD;
    border-color: #F1F3F8;
    color: #C9CFDB;
}
QPushButton#GhostButton {
    background: transparent;
    border: 1px solid transparent;
    color: #4F46E5;
    font-weight: 600;
}
QPushButton#GhostButton:hover {
    background: #F3F2FE;
    border-color: #E0DEFB;
}
QToolButton#ToolsMenuButton {
    background: #FFFFFF;
    border: 1px solid #DDE1EA;
    border-radius: 9px;
    padding: 7px 14px;
    color: #1F2937;
    font-weight: 600;
    font-size: 12.5px;
}
QToolButton#ToolsMenuButton:hover {
    background: #F8F9FC;
    border-color: #BFC6D4;
}
QToolButton#ToolsMenuButton::menu-indicator {
    image: none;
    width: 0;
}

/* ---------- Scrollbars ---------- */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 2px;
}
QScrollBar::handle:vertical {
    background: #D7DCE5;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #B8C0CD;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px 4px;
}
QScrollBar::handle:horizontal {
    background: #D7DCE5;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ---------- Status / Splitter / Tabs (legacy) ---------- */
QStatusBar {
    background: #FFFFFF;
    border-top: 1px solid #ECEEF3;
    color: #475569;
    font-size: 12px;
}
QStatusBar::item {
    border: none;
}
QSplitter::handle {
    background: transparent;
}
QSplitter::handle:horizontal {
    width: 8px;
}
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabBar::tab {
    background: transparent;
    color: #64748B;
    padding: 8px 14px;
    font-weight: 600;
}
QTabBar::tab:selected {
    color: #4F46E5;
}

/* ---------- Menu ---------- */
QMenu {
    background: #FFFFFF;
    border: 1px solid #E5E7EE;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 14px;
    border-radius: 6px;
    color: #1F2937;
}
QMenu::item:selected {
    background: #F3F2FE;
    color: #4338CA;
}
QMenu::item:disabled {
    color: #94A3B8;
}
QMenu::separator {
    height: 1px;
    background: #ECEEF3;
    margin: 6px 4px;
}

/* ---------- Tooltip ---------- */
QToolTip {
    background: #0F172A;
    color: #F8FAFC;
    border: 1px solid #1F2937;
    border-radius: 6px;
    padding: 6px 9px;
    font-size: 12px;
}
"""


def clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def build_dot(color: str, size: int = 10) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color)))
    painter.setBrush(QColor(color))
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return pixmap


def generate_tray_icon(size: int = 22) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    color = QColor("#4F46E5")
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)

    cell = (size - 8) / 2.0
    gap = 2.0
    x0 = 3.0
    y0 = 3.0
    radius = 2.4
    for row in range(2):
        for col in range(2):
            x = x0 + col * (cell + gap)
            y = y0 + row * (cell + gap)
            painter.drawRoundedRect(x, y, cell, cell, radius, radius)

    painter.end()
    return QIcon(pixmap)


def generate_brand_mark(size: int = 28) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#4F46E5"))
    painter.drawRoundedRect(0, 0, size, size, size * 0.28, size * 0.28)
    painter.setBrush(QColor("#FFFFFF"))
    cell = size * 0.20
    gap = size * 0.08
    base_x = (size - (cell * 2 + gap)) / 2
    base_y = (size - (cell * 2 + gap)) / 2
    radius = cell * 0.22
    for r in range(2):
        for c in range(2):
            x = base_x + c * (cell + gap)
            y = base_y + r * (cell + gap)
            painter.drawRoundedRect(x, y, cell, cell, radius, radius)
    painter.end()
    return pixmap


class AppCard(QFrame):
    def __init__(
        self,
        app: DiscoveredApp,
        selected: bool,
        running: bool,
        reachable: bool,
        on_click: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.app = app
        self.on_click = on_click
        self.setObjectName("Card")
        self.setProperty("selected", selected)
        self.setCursor(Qt.PointingHandCursor)
        self._build(running, reachable)

    def _build(self, running: bool, reachable: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        top = QHBoxLayout()
        top.setSpacing(10)

        status_color = "#10B981" if running else "#F59E0B" if reachable else "#CBD2DD"
        status_icon = QLabel()
        status_icon.setPixmap(build_dot(status_color, 9))
        status_icon.setFixedWidth(10)
        top.addWidget(status_icon, 0, Qt.AlignVCenter)

        name = QLabel(self.app.name)
        name.setStyleSheet(
            "font-size: 13.5px; font-weight: 600; color: #0F172A; letter-spacing: -0.1px;"
        )
        name.setWordWrap(True)
        name.setMinimumWidth(0)
        top.addWidget(name, 1)

        if running:
            status_text, badge = "Çalışıyor", "BadgeGreen"
        elif reachable:
            status_text, badge = "Erişilebilir", "BadgeOrange"
        else:
            status_text, badge = "Durdu", "BadgeGray"
        status = QLabel(status_text)
        status.setObjectName(badge)
        top.addWidget(status, 0, Qt.AlignVCenter)
        layout.addLayout(top)

        desc_text = self.app.description or self.app.metadata.get("folder_name", "")
        if desc_text:
            desc = QLabel(desc_text)
            desc.setWordWrap(True)
            desc.setObjectName("MutedLabel")
            desc.setStyleSheet("font-size: 12px; color: #64748B;")
            layout.addWidget(desc)

        meta = QHBoxLayout()
        meta.setSpacing(6)
        app_type = QLabel(self.app.app_type.upper())
        app_type.setObjectName("BadgeIndigo")
        meta.addWidget(app_type)

        mode = QLabel(self.app.start_mode)
        mode.setObjectName("BadgeGray")
        meta.addWidget(mode)

        meta.addStretch()
        layout.addLayout(meta)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        self.on_click(self.app.key)


class NavButton(QPushButton):
    def __init__(self, text: str, key: str, on_click: Callable[[str], None]) -> None:
        super().__init__(text)
        self.key = key
        self.setObjectName("NavButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("active", False)
        self.clicked.connect(lambda: on_click(key))

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    def __init__(self, state: HubState, manager: AppManager) -> None:
        super().__init__()
        self.state = state
        self.manager = manager
        self.apps: List[DiscoveredApp] = []
        self.selected_key = self.state.get_window().get("selected_key", "")
        self.force_quit = False
        self.launching: dict[str, bool] = {}
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2500)
        self.refresh_timer.timeout.connect(self.refresh_runtime_state)
        self._build()
        self._create_tray_icon()
        self.refresh_apps()
        self.restore_geometry_from_state()
        self.refresh_timer.start()

    def _build(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(APP_STYLE)
        self.setWindowIcon(generate_tray_icon(64))

        root = QWidget()
        root.setObjectName("RootSurface")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.header_bar = self._build_header_bar()
        body_layout.addWidget(self.header_bar)

        self.content_stack = QStackedWidget()
        self.content_stack.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.content_stack, 1)

        apps_view = self._build_apps_view()
        self.content_stack.addWidget(apps_view)

        self.projects_view = ProjectsView(self.state)
        projects_wrapper = QWidget()
        projects_wrapper_layout = QVBoxLayout(projects_wrapper)
        projects_wrapper_layout.setContentsMargins(24, 18, 24, 24)
        projects_wrapper_layout.setSpacing(0)
        projects_wrapper_layout.addWidget(self.projects_view, 1)
        self.content_stack.addWidget(projects_wrapper)

        root_layout.addWidget(body, 1)

        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.setStatusBar(self.status_bar)
        self.setCentralWidget(root)

        self._select_nav("apps")

        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(244)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(6)

        # Brand
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(generate_brand_mark(28))
        logo.setFixedSize(28, 28)
        brand_row.addWidget(logo)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        brand_name = QLabel("Tools Hub")
        brand_name.setObjectName("SidebarBrand")
        brand_tag = QLabel("Local Workspace")
        brand_tag.setObjectName("SidebarTagline")
        brand_col.addWidget(brand_name)
        brand_col.addWidget(brand_tag)
        brand_row.addLayout(brand_col, 1)
        brand_wrap = QWidget()
        brand_wrap.setLayout(brand_row)
        layout.addWidget(brand_wrap)

        layout.addSpacing(20)

        nav_label = QLabel("WORKSPACE")
        nav_label.setObjectName("SidebarSection")
        layout.addWidget(nav_label)

        self.nav_buttons: dict[str, NavButton] = {}
        apps_btn = NavButton("  Lokal Uygulamalar", "apps", self._select_nav)
        services_btn = NavButton("  Servis URL'leri", "projects", self._select_nav)
        layout.addWidget(apps_btn)
        layout.addWidget(services_btn)
        self.nav_buttons["apps"] = apps_btn
        self.nav_buttons["projects"] = services_btn

        layout.addSpacing(18)

        actions_label = QLabel("ARAÇLAR")
        actions_label.setObjectName("SidebarSection")
        layout.addWidget(actions_label)

        rescan_btn = QPushButton("  Yeniden Tara")
        rescan_btn.setObjectName("SidebarAction")
        rescan_btn.setCursor(Qt.PointingHandCursor)
        rescan_btn.clicked.connect(self.refresh_apps)
        layout.addWidget(rescan_btn)

        tools_button = QToolButton()
        tools_button.setObjectName("SidebarToolMenu")
        tools_button.setText("  PID & Port  ▾")
        tools_button.setPopupMode(QToolButton.InstantPopup)
        tools_button.setCursor(Qt.PointingHandCursor)
        tools_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tools_menu = QMenu(tools_button)

        pid_info_action = QAction("PID Bilgi", tools_menu)
        pid_info_action.triggered.connect(self.prompt_pid_info)
        tools_menu.addAction(pid_info_action)
        port_info_action = QAction("Port Bilgi", tools_menu)
        port_info_action.triggered.connect(self.prompt_port_info)
        tools_menu.addAction(port_info_action)
        tools_menu.addSeparator()
        kill_pid_action = QAction("PID Kill", tools_menu)
        kill_pid_action.triggered.connect(self.prompt_kill_pid)
        tools_menu.addAction(kill_pid_action)
        kill_port_action = QAction("Port Kill", tools_menu)
        kill_port_action.triggered.connect(self.prompt_kill_port)
        tools_menu.addAction(kill_port_action)
        tools_button.setMenu(tools_menu)
        layout.addWidget(tools_button)

        layout.addStretch(1)

        footer = QFrame()
        footer.setObjectName("SidebarFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 14, 0, 0)
        footer_layout.setSpacing(2)
        hint = QLabel("Menubar'dan da erişebilirsin")
        hint.setStyleSheet("color: #6B7280; font-size: 11px;")
        footer_layout.addWidget(hint)
        layout.addWidget(footer)

        return sidebar

    def _build_header_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("HeaderBar")
        bar.setFixedHeight(72)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 16, 24, 16)
        layout.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.header_title = QLabel("Lokal Uygulamalar")
        self.header_title.setObjectName("HeaderTitle")
        self.header_subtitle = QLabel("Tools klasöründeki uygulamaları başlat, durdur ve izle.")
        self.header_subtitle.setObjectName("HeaderSubtitle")
        title_col.addWidget(self.header_title)
        title_col.addWidget(self.header_subtitle)
        layout.addLayout(title_col)
        layout.addStretch(1)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("FaintLabel")
        self.summary_label.setStyleSheet("color: #64748B; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.summary_label)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Uygulama ara…")
        self.search_input.setFixedWidth(280)
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.refresh_app_list)
        layout.addWidget(self.search_input)

        return bar

    def _build_apps_view(self) -> QWidget:
        view = QWidget()
        outer = QVBoxLayout(view)
        outer.setContentsMargins(24, 18, 24, 24)
        outer.setSpacing(14)

        action_bar = QFrame()
        action_bar_layout = QHBoxLayout(action_bar)
        action_bar_layout.setContentsMargins(0, 0, 0, 0)
        action_bar_layout.setSpacing(8)

        action_bar_layout.addStretch(1)

        start_all_button = QPushButton("Hepsini Başlat")
        start_all_button.setObjectName("PrimaryButton")
        start_all_button.clicked.connect(self.start_all_apps)
        action_bar_layout.addWidget(start_all_button)

        stop_all_button = QPushButton("Hepsini Durdur")
        stop_all_button.setObjectName("DangerButton")
        stop_all_button.clicked.connect(self.stop_all_apps)
        action_bar_layout.addWidget(stop_all_button)

        outer.addWidget(action_bar)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        left = QFrame()
        left.setObjectName("Surface")
        left.setMinimumWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 18, 18, 14)
        left_layout.setSpacing(12)

        list_header = QHBoxLayout()
        list_title = QLabel("Uygulamalar")
        list_title.setObjectName("SectionLabel")
        list_header.addWidget(list_title)
        list_header.addStretch()
        self.list_count_label = QLabel("")
        self.list_count_label.setObjectName("FaintLabel")
        list_header.addWidget(self.list_count_label)
        left_layout.addLayout(list_header)

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(10)
        self.list_scroll.setWidget(self.list_container)
        left_layout.addWidget(self.list_scroll, 1)

        splitter.addWidget(left)

        right = QFrame()
        right.setObjectName("Surface")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(22, 22, 22, 22)
        right_layout.setSpacing(18)

        # ---- Header block (name + status) ----
        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        self.app_name_label = QLabel("Uygulama Seç")
        self.app_name_label.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #0F172A; letter-spacing: -0.4px;"
        )
        name_row.addWidget(self.app_name_label)
        name_row.addStretch()
        self.status_badge = QLabel("Hazır")
        self.status_badge.setObjectName("BadgeGray")
        name_row.addWidget(self.status_badge)
        right_layout.addLayout(name_row)

        self.description_label = QLabel("Soldan bir uygulama seç.")
        self.description_label.setWordWrap(True)
        self.description_label.setObjectName("MutedLabel")
        self.description_label.setStyleSheet("font-size: 13px; color: #475569;")
        right_layout.addWidget(self.description_label)

        # ---- Stat strip ----
        stat_strip = QFrame()
        stat_strip.setObjectName("InsetPanel")
        stat_layout = QHBoxLayout(stat_strip)
        stat_layout.setContentsMargins(16, 12, 16, 12)
        stat_layout.setSpacing(20)
        self.meta_label = QLabel("")
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet(
            "color: #475569; font-size: 12px; line-height: 1.55;"
        )
        stat_layout.addWidget(self.meta_label, 1)
        right_layout.addWidget(stat_strip)

        # ---- URL row ----
        url_label = QLabel("URL")
        url_label.setObjectName("GroupLabel")
        right_layout.addWidget(url_label)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("URL yaz veya otomatik tespit edilen URL'yi düzenle")
        url_row.addWidget(self.url_input, 1)
        save_url_button = QPushButton("Kaydet")
        save_url_button.clicked.connect(self.save_url_override)
        url_row.addWidget(save_url_button)
        right_layout.addLayout(url_row)

        # ---- Lifecycle ----
        lifecycle_label = QLabel("YAŞAM DÖNGÜSÜ")
        lifecycle_label.setObjectName("GroupLabel")
        right_layout.addWidget(lifecycle_label)

        lifecycle_row = QHBoxLayout()
        lifecycle_row.setSpacing(8)
        self.open_button = QPushButton("Aç")
        self.open_button.setObjectName("PrimaryButton")
        self.open_button.clicked.connect(self.open_selected_app)
        lifecycle_row.addWidget(self.open_button)

        self.start_button = QPushButton("Başlat")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_selected_app)
        lifecycle_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Durdur")
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.clicked.connect(self.stop_selected_app)
        lifecycle_row.addWidget(self.stop_button)

        self.restart_button = QPushButton("Yeniden Başlat")
        self.restart_button.clicked.connect(self.restart_selected_app)
        lifecycle_row.addWidget(self.restart_button)
        lifecycle_row.addStretch()
        right_layout.addLayout(lifecycle_row)

        # ---- Access ----
        access_label = QLabel("ERİŞİM & KAYNAKLAR")
        access_label.setObjectName("GroupLabel")
        right_layout.addWidget(access_label)

        access_row = QHBoxLayout()
        access_row.setSpacing(8)
        self.open_url_button = QPushButton("URL Aç")
        self.open_url_button.clicked.connect(self.open_selected_url)
        access_row.addWidget(self.open_url_button)

        self.open_terminal_button = QPushButton("Terminal")
        self.open_terminal_button.clicked.connect(self.open_selected_terminal)
        access_row.addWidget(self.open_terminal_button)

        self.open_folder_button = QPushButton("Klasör")
        self.open_folder_button.clicked.connect(self.open_selected_folder)
        access_row.addWidget(self.open_folder_button)

        self.open_logs_button = QPushButton("Loglar")
        self.open_logs_button.clicked.connect(self.open_selected_logs)
        access_row.addWidget(self.open_logs_button)

        self.open_readme_button = QPushButton("README")
        self.open_readme_button.clicked.connect(self.open_selected_readme)
        access_row.addWidget(self.open_readme_button)

        self.health_check_button = QPushButton("Health Check")
        self.health_check_button.clicked.connect(self.show_selected_health_check)
        access_row.addWidget(self.health_check_button)

        access_row.addStretch()
        right_layout.addLayout(access_row)

        # ---- Command preview ----
        command_title = QLabel("BAŞLATMA KOMUTU")
        command_title.setObjectName("GroupLabel")
        right_layout.addWidget(command_title)

        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setFixedHeight(64)
        right_layout.addWidget(self.command_preview)

        # ---- Logs ----
        logs_title = QLabel("LOG ÖNİZLEMESİ")
        logs_title.setObjectName("GroupLabel")
        right_layout.addWidget(logs_title)

        self.logs_preview = QPlainTextEdit()
        self.logs_preview.setReadOnly(True)
        right_layout.addWidget(self.logs_preview, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([380, 860])
        self.splitter = splitter
        splitter.splitterMoved.connect(self._on_splitter_moved)

        outer.addWidget(splitter, 1)
        return view

    def _select_nav(self, key: str) -> None:
        for nav_key, btn in self.nav_buttons.items():
            btn.set_active(nav_key == key)

        if key == "apps":
            self.content_stack.setCurrentIndex(0)
            self.header_title.setText("Lokal Uygulamalar")
            self.header_subtitle.setText(
                "Tools klasöründeki uygulamaları başlat, durdur ve izle."
            )
            self.search_input.setVisible(True)
            self.summary_label.setVisible(True)
        else:
            self.content_stack.setCurrentIndex(1)
            self.header_title.setText("Servis URL'leri")
            self.header_subtitle.setText(
                "Projelerinin Swagger ve Hangfire URL'lerini ortamlara göre yönet."
            )
            self.search_input.setVisible(False)
            self.summary_label.setVisible(False)

    def _create_tray_icon(self) -> None:
        self.tray_icon = QSystemTrayIcon(generate_tray_icon())
        self.tray_icon.setToolTip(APP_NAME)

        self.tray_menu = QMenu()
        self._rebuild_tray_menu()

        self.tray_icon.activated.connect(self._handle_tray_activation)
        self.tray_icon.show()

    def _rebuild_tray_menu(self) -> None:
        self.tray_menu.clear()

        header = QAction("Uygulamalar", self.tray_menu)
        header.setEnabled(False)
        self.tray_menu.addAction(header)

        if not self.apps:
            empty = QAction("(Henuz uygulama bulunamadi)", self.tray_menu)
            empty.setEnabled(False)
            self.tray_menu.addAction(empty)
        else:
            for app in self.apps:
                runtime = self.manager.get_runtime(app)
                running = bool(runtime.pid and is_pid_running(runtime.pid))
                url = self.manager.get_url(app)
                reachable = bool(url and is_url_reachable(url))

                if running:
                    icon = QIcon(build_dot("#16a34a", 14))
                elif reachable:
                    icon = QIcon(build_dot("#f59e0b", 14))
                else:
                    icon = QIcon(build_dot("#dc2626", 14))

                action = QAction(app.name, self.tray_menu)
                action.setIcon(icon)
                action.triggered.connect(lambda _checked=False, key=app.key: self._tray_open_app(key))
                self.tray_menu.addAction(action)

        self.tray_menu.addSeparator()

        start_all_action = QAction("Start All", self.tray_menu)
        start_all_action.triggered.connect(self.start_all_apps)
        self.tray_menu.addAction(start_all_action)

        stop_all_action = QAction("Stop All", self.tray_menu)
        stop_all_action.triggered.connect(self.stop_all_apps)
        self.tray_menu.addAction(stop_all_action)

        self.tray_menu.addSeparator()

        show_action = QAction("Pencereyi Goster", self.tray_menu)
        show_action.triggered.connect(self.show_window)
        self.tray_menu.addAction(show_action)

        hide_action = QAction("Pencereyi Gizle", self.tray_menu)
        hide_action.triggered.connect(self.hide)
        self.tray_menu.addAction(hide_action)

        rescan_action = QAction("Yeniden Tara", self.tray_menu)
        rescan_action.triggered.connect(self.refresh_apps)
        self.tray_menu.addAction(rescan_action)

        self.tray_menu.addSeparator()

        quit_action = QAction("Cikis", self.tray_menu)
        quit_action.triggered.connect(self.quit_application)
        self.tray_menu.addAction(quit_action)

    def _tray_open_app(self, app_key: str) -> None:
        previous = self.selected_key
        self.selected_key = app_key
        try:
            self.open_selected_app()
        finally:
            self.selected_key = previous if any(a.key == previous for a in self.apps) else app_key
            self.refresh_app_list()
            self.refresh_details()
            self._rebuild_tray_menu()

    def _handle_tray_activation(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()
        elif reason == QSystemTrayIcon.Context:
            self._rebuild_tray_menu()
            self.tray_menu.popup(QCursor.pos())

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_application(self) -> None:
        self.force_quit = True
        self.save_geometry_to_state()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def refresh_apps(self) -> None:
        self.apps = discover_apps()
        if self.apps and not any(app.key == self.selected_key for app in self.apps):
            self.selected_key = self.apps[0].key
        self.refresh_app_list()
        self.refresh_details()
        if hasattr(self, "tray_menu"):
            self._rebuild_tray_menu()

    def refresh_runtime_state(self) -> None:
        self.refresh_app_list()
        self.refresh_details()
        if hasattr(self, "tray_menu") and not self.tray_menu.isVisible():
            self._rebuild_tray_menu()

    def refresh_app_list(self) -> None:
        clear_layout(self.list_layout)
        query = self.search_input.text().strip().lower()
        visible_apps = [
            app
            for app in self.apps
            if not query
            or query in app.name.lower()
            or query in app.path.lower()
            or query in app.description.lower()
        ]

        running_count = 0
        for app in visible_apps:
            runtime = self.manager.get_runtime(app)
            running = bool(runtime.pid and is_pid_running(runtime.pid))
            reachable = bool(self.manager.get_url(app) and is_url_reachable(self.manager.get_url(app)))
            if running:
                running_count += 1
            card = AppCard(
                app=app,
                selected=app.key == self.selected_key,
                running=running,
                reachable=reachable,
                on_click=self.select_app,
            )
            self.list_layout.addWidget(card)

        if not visible_apps:
            empty = QLabel("Bu aramaya uyan uygulama bulunamadi.")
            empty.setObjectName("MutedLabel")
            self.list_layout.addWidget(empty)

        self.list_layout.addStretch()
        total = len(self.apps)
        self.summary_label.setText(
            f"{running_count} aktif  ·  {total} uygulama" if total else "Henüz uygulama yok"
        )
        if hasattr(self, "list_count_label"):
            self.list_count_label.setText(f"{len(visible_apps)}/{total}")

    def select_app(self, app_key: str) -> None:
        self.selected_key = app_key
        self.state.update_window(selected_key=app_key)
        self.refresh_app_list()
        self.refresh_details()

    def get_selected_app(self) -> Optional[DiscoveredApp]:
        for app in self.apps:
            if app.key == self.selected_key:
                return app
        return None

    def refresh_details(self) -> None:
        app = self.get_selected_app()
        if not app:
            self.app_name_label.setText("Uygulama Seç")
            self.description_label.setText("Detay görmek için soldan bir uygulama seç.")
            self.meta_label.setText("")
            self.url_input.setText("")
            self.command_preview.setPlainText("")
            self.logs_preview.setPlainText("")
            self.status_badge.setText("Hazır")
            self.status_badge.setObjectName("BadgeGray")
            self.status_badge.style().unpolish(self.status_badge)
            self.status_badge.style().polish(self.status_badge)
            return

        runtime = self.manager.get_runtime(app)
        running = bool(runtime.pid and is_pid_running(runtime.pid))
        resolved_url = self.manager.get_url(app)
        reachable = bool(resolved_url and is_url_reachable(resolved_url))

        status_text = "Çalışıyor" if running else "Erişilebilir" if reachable else "Durdu"
        badge_name = "BadgeGreen" if running else "BadgeOrange" if reachable else "BadgeGray"

        self.app_name_label.setText(app.name)
        self.description_label.setText(
            app.description or "Bu uygulama için açıklama bulunamadı."
        )
        self.meta_label.setText(
            "    ".join(
                [
                    f"Tip: <b>{app.app_type}</b>",
                    f"Mod: <b>{app.start_mode}</b>",
                    f"PID: <b>{runtime.pid or '—'}</b>",
                    f"URL: <b>{'OK' if reachable else 'Yok'}</b>",
                    f"Son başlatma: <b>{format_dt(runtime.started_at) or '—'}</b>",
                ]
            )
        )
        self.meta_label.setTextFormat(Qt.RichText)

        current_url_text = self.url_input.text().strip()
        if self.url_input.hasFocus():
            pass
        elif current_url_text != resolved_url:
            self.url_input.setText(resolved_url)

        command_text = " ".join(app.start_command) if app.start_command else "Otomatik komut yok"
        self.command_preview.setPlainText(command_text)
        self.logs_preview.setPlainText(self.build_log_preview(app, runtime))

        self.status_badge.setText(status_text)
        self.status_badge.setObjectName(badge_name)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

        self.start_button.setEnabled(bool(app.start_command) and not running and not reachable)
        self.open_button.setEnabled(bool(app.start_command) or bool(resolved_url))
        self.stop_button.setEnabled(running or bool(app.stop_script))
        self.restart_button.setEnabled(bool(app.start_command) or bool(app.stop_script))
        self.open_url_button.setEnabled(bool(resolved_url))
        self.open_terminal_button.setEnabled(True)
        self.health_check_button.setEnabled(True)
        self.open_readme_button.setEnabled(bool(app.readme_path))

    def build_log_preview(self, app: DiscoveredApp, runtime) -> str:
        log_sections: List[str] = []
        preferred_logs = [runtime.stdout_log, runtime.stderr_log] + app.log_paths
        seen = set()
        for path in preferred_logs:
            if not path or path in seen:
                continue
            seen.add(path)
            preview = tail_file(path, 50)
            if preview:
                title = Path(path).name
                log_sections.append(f"[{title}]\n{preview}")
            if len(log_sections) >= 2:
                break
        if not log_sections:
            return "Henuz goruntulenecek log bulunamadi."
        return "\n\n".join(log_sections)

    def save_url_override(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        url = self.url_input.text().strip()
        self.manager.set_url_override(app, url)
        self.refresh_details()
        self.status_bar.showMessage("URL bilgisi kaydedildi.", 2500)

    def start_selected_app(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        if self.launching.get(app.key):
            self.status_bar.showMessage("Bu uygulama zaten baslatiliyor.", 2500)
            return
        if self.manager.is_app_running(app):
            self.status_bar.showMessage("Uygulama zaten calisiyor.", 2500)
            self.refresh_runtime_state()
            return
        ok, message = self.manager.start_app(app)
        self.status_bar.showMessage(message, 3500)
        if not ok:
            QMessageBox.warning(self, "Start Hatasi", message)
        self.refresh_runtime_state()

    def start_all_apps(self) -> None:
        if not self.apps:
            self.status_bar.showMessage("Baslatilacak uygulama yok.", 2500)
            return
        started = 0
        already = 0
        failed: List[str] = []
        for app in self.apps:
            if self.manager.is_app_running(app):
                already += 1
                continue
            ok, message = self.manager.start_app(app)
            if ok:
                started += 1
            else:
                failed.append(f"{app.name}: {message}")
        self.refresh_runtime_state()
        self._rebuild_tray_menu()
        summary = f"Start All: {started} baslatildi, {already} zaten calisiyordu."
        if failed:
            summary += f" {len(failed)} hata."
            QMessageBox.warning(self, "Start All", "\n".join(failed))
        self.status_bar.showMessage(summary, 5000)

    def stop_all_apps(self) -> None:
        if not self.apps:
            self.status_bar.showMessage("Durdurulacak uygulama yok.", 2500)
            return
        answer = QMessageBox.question(
            self,
            "Stop All",
            "Tum uygulamalar durdurulsun mu?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        stopped = 0
        skipped = 0
        failed: List[str] = []
        for app in self.apps:
            if not self.manager.is_app_running(app):
                skipped += 1
                continue
            ok, message = self.manager.stop_app(app)
            if ok:
                stopped += 1
            else:
                failed.append(f"{app.name}: {message}")
        self.refresh_runtime_state()
        self._rebuild_tray_menu()
        summary = f"Stop All: {stopped} durduruldu, {skipped} zaten kapaliydi."
        if failed:
            summary += f" {len(failed)} hata."
            QMessageBox.warning(self, "Stop All", "\n".join(failed))
        self.status_bar.showMessage(summary, 5000)

    def open_selected_app(self) -> None:
        app = self.get_selected_app()
        if not app:
            return

        if self.launching.get(app.key):
            self.status_bar.showMessage(
                f"{app.name} zaten baslatiliyor, URL hazir olunca acilacak.", 2500
            )
            return

        runtime = self.manager.get_runtime(app)
        running = bool(runtime.pid and is_pid_running(runtime.pid))
        url = self.manager.get_url(app)
        reachable = bool(url and is_url_reachable(url))

        if app.app_type == "web":
            if not url:
                QMessageBox.information(self, "URL Yok", "Bu web uygulamasi icin URL tanimli degil.")
                return

            if reachable or running:
                QDesktopServices.openUrl(QUrl(url))
                self.status_bar.showMessage(f"{app.name} URL'i acildi.", 2500)
                self.refresh_runtime_state()
                return

            ok, message = self.manager.start_app(app)
            if not ok:
                self.status_bar.showMessage(message, 3500)
                QMessageBox.warning(self, "Acma Hatasi", message)
                self.refresh_runtime_state()
                return

            self.status_bar.showMessage(f"{app.name} baslatiliyor, URL bekleniyor...", 0)
            self._begin_url_poll(app.key, attempts_left=60)
            self.refresh_runtime_state()
            return

        # Desktop app
        if running:
            activated = activate_pid(runtime.pid)
            if activated:
                self.status_bar.showMessage(f"{app.name} one getirildi.", 2500)
            else:
                self.status_bar.showMessage(f"{app.name} zaten calisiyor.", 2500)
            self.refresh_runtime_state()
            return

        ok, message = self.manager.start_app(app)
        self.status_bar.showMessage(message, 3500)
        if not ok:
            QMessageBox.warning(self, "Acma Hatasi", message)
            self.refresh_runtime_state()
            return

        self.launching[app.key] = True
        QTimer.singleShot(1500, lambda key=app.key: self._after_desktop_start(key))

    def _begin_url_poll(self, app_key: str, attempts_left: int) -> None:
        self.launching[app_key] = True
        QTimer.singleShot(500, lambda: self._poll_url_once(app_key, attempts_left))

    def _poll_url_once(self, app_key: str, attempts_left: int) -> None:
        app = next((a for a in self.apps if a.key == app_key), None)
        if not app:
            self.launching.pop(app_key, None)
            return

        url = self.manager.get_url(app)
        if url and is_url_reachable(url):
            self.launching.pop(app_key, None)
            QDesktopServices.openUrl(QUrl(url))
            self.status_bar.showMessage(f"{app.name} hazir, URL acildi.", 3000)
            self.refresh_runtime_state()
            self._rebuild_tray_menu()
            return

        if attempts_left <= 0:
            self.launching.pop(app_key, None)
            self.status_bar.showMessage(
                f"{app.name} 30 saniyede hazir olmadi.", 4500
            )
            QMessageBox.warning(
                self,
                "Web Uygulamasi Hazir Degil",
                f"{app.name} baslatildi ama URL erisilebilir olmadi. Log'lari kontrol et.",
            )
            self.refresh_runtime_state()
            return

        QTimer.singleShot(500, lambda: self._poll_url_once(app_key, attempts_left - 1))

    def _after_desktop_start(self, app_key: str) -> None:
        self.launching.pop(app_key, None)
        app = next((a for a in self.apps if a.key == app_key), None)
        if not app:
            return
        runtime = self.manager.get_runtime(app)
        if runtime.pid:
            activate_pid(runtime.pid)
        self.refresh_runtime_state()
        self._rebuild_tray_menu()

    def stop_selected_app(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        ok, message = self.manager.stop_app(app)
        self.status_bar.showMessage(message, 3500)
        if not ok:
            QMessageBox.warning(self, "Stop Hatasi", message)
        self.refresh_runtime_state()

    def restart_selected_app(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        ok, message = self.manager.restart_app(app)
        self.status_bar.showMessage(message, 3500)
        if not ok:
            QMessageBox.warning(self, "Restart Hatasi", message)
        self.refresh_runtime_state()

    def open_selected_terminal(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        ok, message = self.manager.open_terminal(app)
        self.status_bar.showMessage(message, 3000)
        if not ok:
            QMessageBox.warning(self, "Terminal Hatasi", message)

    def show_selected_health_check(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        report = self.manager.health_check(app)
        lines = [
            f"Ad: {report['name']}",
            f"Tip: {report['type']}",
            f"Klasor: {report['path']}",
            f"Start yontemi: {report['start_mode']}",
            f"Calisiyor: {'Evet' if report['running'] else 'Hayir'}",
            f"PID: {report['pid'] or '-'}",
            f"Son baslatma: {format_dt(str(report['started_at'] or ''))}",
            f"URL: {report['url'] or '-'}",
            f"URL erisimi: {'OK' if report['url_reachable'] else 'Yok'}",
            f"Stdout log: {report['stdout_log'] or '-'}",
            f"Stderr log: {report['stderr_log'] or '-'}",
            f"Stop script: {report['stop_script'] or '-'}",
            f"README: {report['readme_path'] or '-'}",
        ]
        if report["last_error"]:
            lines.append(f"Son hata: {report['last_error']}")

        QMessageBox.information(self, "Health Check", "\n".join(lines))

    def open_selected_url(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        url = self.manager.get_url(app)
        if not url:
            QMessageBox.information(self, "URL Yok", "Bu uygulama icin URL tanimli degil.")
            return
        QDesktopServices.openUrl(QUrl(url))

    def open_selected_folder(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(app.path))

    def open_selected_logs(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        runtime = self.manager.get_runtime(app)
        preferred_path = runtime.stdout_log or runtime.stderr_log
        if preferred_path:
            target = Path(preferred_path).parent
        elif app.log_paths:
            target = Path(app.log_paths[0]).parent
        else:
            target = Path(app.path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def open_selected_readme(self) -> None:
        app = self.get_selected_app()
        if not app or not app.readme_path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(app.readme_path))

    def find_apps_for_pid(self, pid: int) -> List[DiscoveredApp]:
        matches: List[DiscoveredApp] = []
        command = describe_pid(pid).lower()
        for app in self.apps:
            runtime = self.manager.get_runtime(app)
            if runtime.pid == pid:
                matches.append(app)
                continue
            if command and app.path.lower() in command:
                matches.append(app)
        return matches

    def find_apps_for_port(self, port: int) -> List[DiscoveredApp]:
        token = f":{port}"
        matches: List[DiscoveredApp] = []
        for app in self.apps:
            url = self.manager.get_url(app)
            if url and token in url:
                matches.append(app)
        return matches

    def prompt_pid_info(self) -> None:
        pid, accepted = QInputDialog.getInt(
            self,
            "PID Bilgi",
            "Bilgi gosterilecek PID gir:",
            value=0,
            minValue=0,
            maxValue=999999,
        )
        if not accepted or pid <= 0:
            return

        running = is_pid_running(pid)
        command = describe_pid(pid)
        ports = find_ports_by_pid(pid) if running else []
        matched_apps = self.find_apps_for_pid(pid) if running else []

        lines = [
            f"PID: {pid}",
            f"Calisiyor: {'Evet' if running else 'Hayir'}",
            f"Komut: {command or '-'}",
            f"Dinlenen portlar: {', '.join(str(p) for p in ports) if ports else '-'}",
        ]

        if matched_apps:
            lines.append("")
            lines.append("Eslesen uygulama(lar):")
            for app in matched_apps:
                url = self.manager.get_url(app) or "-"
                lines.append(f"  - {app.name} | {url}")
                lines.append(f"    {app.path}")
        elif ports:
            external_apps: List[DiscoveredApp] = []
            for port in ports:
                for app in self.find_apps_for_port(port):
                    if app not in external_apps:
                        external_apps.append(app)
            if external_apps:
                lines.append("")
                lines.append("Port eslesen uygulama(lar):")
                for app in external_apps:
                    url = self.manager.get_url(app) or "-"
                    lines.append(f"  - {app.name} | {url}")

        QMessageBox.information(self, "PID Bilgi", "\n".join(lines))
        self.status_bar.showMessage(
            f"PID {pid}: {len(ports)} port, {len(matched_apps)} eslesen uygulama.",
            3500,
        )

    def prompt_port_info(self) -> None:
        port, accepted = QInputDialog.getInt(
            self,
            "Port Bilgi",
            "Bilgi gosterilecek port gir:",
            value=0,
            minValue=0,
            maxValue=65535,
        )
        if not accepted or port <= 0:
            return

        pids = find_pids_by_port(port)
        matched_apps = self.find_apps_for_port(port)
        url_for_port = ""
        for app in matched_apps:
            candidate = self.manager.get_url(app)
            if candidate:
                url_for_port = candidate
                break

        lines = [
            f"Port: {port}",
            f"Dinleyen PID(ler): {', '.join(str(p) for p in pids) if pids else '-'}",
            f"URL tahmini: {url_for_port or f'http://127.0.0.1:{port}/'}",
        ]

        if pids:
            lines.append("")
            lines.append("Surec detaylari:")
            for pid in pids:
                command = describe_pid(pid) or "-"
                lines.append(f"  - PID {pid}: {command}")

        if matched_apps:
            lines.append("")
            lines.append("Eslesen uygulama(lar):")
            for app in matched_apps:
                url = self.manager.get_url(app) or "-"
                lines.append(f"  - {app.name} | {url}")
                lines.append(f"    {app.path}")

        QMessageBox.information(self, "Port Bilgi", "\n".join(lines))
        self.status_bar.showMessage(
            f"Port {port}: {len(pids)} surec, {len(matched_apps)} eslesen uygulama.",
            3500,
        )

    def prompt_kill_pid(self) -> None:
        pid, accepted = QInputDialog.getInt(
            self,
            "PID Kill",
            "Kapatilacak PID gir:",
            value=0,
            minValue=0,
            maxValue=999999,
        )
        if not accepted or pid <= 0:
            return

        answer = QMessageBox.question(
            self,
            "PID Kill Onayi",
            f"PID {pid} kapatilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        ok, message = kill_pid(pid)
        self.status_bar.showMessage(message, 4000)
        if ok:
            self.refresh_runtime_state()
        else:
            QMessageBox.warning(self, "PID Kill Hatasi", message)

    def prompt_kill_port(self) -> None:
        port, accepted = QInputDialog.getInt(
            self,
            "Port Kill",
            "Kapatilacak port gir:",
            value=0,
            minValue=0,
            maxValue=65535,
        )
        if not accepted or port <= 0:
            return

        answer = QMessageBox.question(
            self,
            "Port Kill Onayi",
            f"Port {port} kullanan surec(ler) kapatilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        ok, message = kill_port(port)
        self.status_bar.showMessage(message, 4500)
        if ok:
            self.refresh_runtime_state()
        else:
            QMessageBox.warning(self, "Port Kill Hatasi", message)

    def restore_geometry_from_state(self) -> None:
        window_state = self.state.get_window()
        geometry = window_state.get("geometry")
        if geometry and len(geometry) == 4:
            self.setGeometry(*geometry)
        sizes = window_state.get("splitter_sizes")
        if sizes and len(sizes) == 2 and all(isinstance(v, int) and v > 0 for v in sizes):
            self.splitter.setSizes(sizes)

    def save_geometry_to_state(self) -> None:
        self.state.update_window(
            geometry=[self.x(), self.y(), self.width(), self.height()],
            selected_key=self.selected_key,
            splitter_sizes=list(self.splitter.sizes()),
        )

    def _on_splitter_moved(self, *_args) -> None:
        self.state.update_window(splitter_sizes=list(self.splitter.sizes()))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.save_geometry_to_state()
        if self.force_quit:
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()
        self.status_bar.showMessage("Tools Hub menubar'da calismaya devam ediyor.", 3000)
