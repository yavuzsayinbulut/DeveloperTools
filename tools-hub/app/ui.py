from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .constants import APP_NAME
from .discovery import discover_apps
from .manager import AppManager
from .models import DiscoveredApp
from .state import HubState
from .utils import (
    activate_pid,
    format_dt,
    is_pid_running,
    is_url_reachable,
    kill_pid,
    kill_port,
    tail_file,
)


APP_STYLE = """
QWidget {
    background: #f4f6fb;
    color: #172033;
    font-family: "Helvetica Neue", Arial;
    font-size: 13px;
}
QFrame#Surface, QFrame#Card, QFrame#DetailCard {
    background: #ffffff;
    border: 1px solid #dde4f0;
    border-radius: 18px;
}
QFrame#Card[selected="true"] {
    border: 2px solid #2b6cf6;
    background: #f8fbff;
}
QFrame#Card:hover {
    border-color: #b8c8f2;
}
QLabel#TitleLabel {
    font-size: 24px;
    font-weight: 700;
}
QLabel#SectionLabel {
    font-size: 15px;
    font-weight: 700;
}
QLabel#MutedLabel {
    color: #5f6a82;
}
QLabel#BadgeBlue, QLabel#BadgeGreen, QLabel#BadgeGray, QLabel#BadgeOrange {
    border-radius: 10px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#BadgeBlue {
    background: #ebf3ff;
    color: #1c56cc;
}
QLabel#BadgeGreen {
    background: #e9f9ef;
    color: #137b3f;
}
QLabel#BadgeGray {
    background: #eef1f6;
    color: #5f6a82;
}
QLabel#BadgeOrange {
    background: #fff4e8;
    color: #a85712;
}
QLineEdit, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #d7deeb;
    border-radius: 12px;
    padding: 8px 10px;
}
QLineEdit:focus, QPlainTextEdit:focus {
    border-color: #2b6cf6;
}
QPushButton {
    background: #edf2ff;
    border: 1px solid #d8e4ff;
    border-radius: 12px;
    padding: 8px 12px;
    color: #16336b;
}
QPushButton:hover {
    background: #e2ebff;
}
QPushButton#PrimaryButton {
    background: #2b6cf6;
    color: white;
    border: 1px solid #2b6cf6;
}
QPushButton#DangerButton {
    background: #fff1f2;
    color: #9f1239;
    border: 1px solid #ffd2da;
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
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)

        status_icon = QLabel()
        status_icon.setPixmap(build_dot("#16a34a" if running else "#94a3b8"))
        top.addWidget(status_icon)

        name = QLabel(self.app.name)
        name.setStyleSheet("font-size: 14px; font-weight: 700;")
        top.addWidget(name)
        top.addStretch()

        status = QLabel("RUNNING" if running else "STOPPED")
        status.setObjectName("BadgeGreen" if running else "BadgeGray")
        top.addWidget(status)
        layout.addLayout(top)

        desc = QLabel(self.app.description or self.app.metadata.get("folder_name", ""))
        desc.setWordWrap(True)
        desc.setObjectName("MutedLabel")
        layout.addWidget(desc)

        meta = QHBoxLayout()
        app_type = QLabel(self.app.app_type.upper())
        app_type.setObjectName("BadgeBlue")
        meta.addWidget(app_type)

        mode = QLabel(self.app.start_mode)
        mode.setObjectName("BadgeGray")
        meta.addWidget(mode)

        if reachable:
            url_badge = QLabel("URL OK")
            url_badge.setObjectName("BadgeOrange")
            meta.addWidget(url_badge)

        meta.addStretch()
        layout.addLayout(meta)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        self.on_click(self.app.key)


class MainWindow(QMainWindow):
    def __init__(self, state: HubState, manager: AppManager) -> None:
        super().__init__()
        self.state = state
        self.manager = manager
        self.apps: List[DiscoveredApp] = []
        self.selected_key = self.state.get_window().get("selected_key", "")
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2500)
        self.refresh_timer.timeout.connect(self.refresh_runtime_state)
        self._build()
        self.refresh_apps()
        self.restore_geometry_from_state()
        self.refresh_timer.start()

    def _build(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1240, 800)
        self.setStyleSheet(APP_STYLE)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("Surface")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)

        title_col = QVBoxLayout()
        title = QLabel("Tools Hub")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Tools klasorundeki uygulamalari tek yerden baslat, durdur ve izle.")
        subtitle.setObjectName("MutedLabel")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col)
        header_layout.addStretch()

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("MutedLabel")
        header_layout.addWidget(self.summary_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Uygulama ara...")
        self.search_input.setFixedWidth(260)
        self.search_input.textChanged.connect(self.refresh_app_list)
        header_layout.addWidget(self.search_input)

        refresh_button = QPushButton("Yeniden Tara")
        refresh_button.clicked.connect(self.refresh_apps)
        header_layout.addWidget(refresh_button)

        kill_pid_button = QPushButton("PID Kill")
        kill_pid_button.clicked.connect(self.prompt_kill_pid)
        header_layout.addWidget(kill_pid_button)

        kill_port_button = QPushButton("Port Kill")
        kill_port_button.clicked.connect(self.prompt_kill_port)
        header_layout.addWidget(kill_port_button)

        root_layout.addWidget(header)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        left = QFrame()
        left.setObjectName("Surface")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        list_title = QLabel("Tespit Edilen Uygulamalar")
        list_title.setObjectName("SectionLabel")
        left_layout.addWidget(list_title)

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(12)
        self.list_scroll.setWidget(self.list_container)
        left_layout.addWidget(self.list_scroll, 1)

        splitter.addWidget(left)

        right = QFrame()
        right.setObjectName("Surface")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        detail_title = QLabel("Detay ve Kontrol")
        detail_title.setObjectName("SectionLabel")
        right_layout.addWidget(detail_title)

        self.detail_card = QFrame()
        self.detail_card.setObjectName("DetailCard")
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_layout.setSpacing(12)

        name_row = QHBoxLayout()
        self.app_name_label = QLabel("Uygulama Sec")
        self.app_name_label.setStyleSheet("font-size: 22px; font-weight: 700;")
        name_row.addWidget(self.app_name_label)
        name_row.addStretch()
        self.status_badge = QLabel("READY")
        self.status_badge.setObjectName("BadgeGray")
        name_row.addWidget(self.status_badge)
        detail_layout.addLayout(name_row)

        self.description_label = QLabel("Soldan bir uygulama sec.")
        self.description_label.setWordWrap(True)
        self.description_label.setObjectName("MutedLabel")
        detail_layout.addWidget(self.description_label)

        self.meta_label = QLabel("")
        self.meta_label.setWordWrap(True)
        self.meta_label.setObjectName("MutedLabel")
        detail_layout.addWidget(self.meta_label)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("URL yaz veya otomatik tespit edilen URL'yi duzenle")
        url_row.addWidget(self.url_input)

        save_url_button = QPushButton("URL Kaydet")
        save_url_button.clicked.connect(self.save_url_override)
        url_row.addWidget(save_url_button)
        detail_layout.addLayout(url_row)

        action_row = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_selected_app)
        action_row.addWidget(self.start_button)

        self.open_button = QPushButton("Ac")
        self.open_button.setObjectName("PrimaryButton")
        self.open_button.clicked.connect(self.open_selected_app)
        action_row.addWidget(self.open_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.clicked.connect(self.stop_selected_app)
        action_row.addWidget(self.stop_button)

        self.open_url_button = QPushButton("URL Ac")
        self.open_url_button.clicked.connect(self.open_selected_url)
        action_row.addWidget(self.open_url_button)

        self.open_folder_button = QPushButton("Klasor Ac")
        self.open_folder_button.clicked.connect(self.open_selected_folder)
        action_row.addWidget(self.open_folder_button)

        self.open_logs_button = QPushButton("Log Ac")
        self.open_logs_button.clicked.connect(self.open_selected_logs)
        action_row.addWidget(self.open_logs_button)

        self.open_readme_button = QPushButton("README Ac")
        self.open_readme_button.clicked.connect(self.open_selected_readme)
        action_row.addWidget(self.open_readme_button)

        action_row.addStretch()
        detail_layout.addLayout(action_row)

        command_title = QLabel("Baslatma Komutu")
        command_title.setObjectName("SectionLabel")
        detail_layout.addWidget(command_title)

        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setFixedHeight(78)
        detail_layout.addWidget(self.command_preview)

        logs_title = QLabel("Log Onizlemesi")
        logs_title.setObjectName("SectionLabel")
        detail_layout.addWidget(logs_title)

        self.logs_preview = QPlainTextEdit()
        self.logs_preview.setReadOnly(True)
        detail_layout.addWidget(self.logs_preview, 1)

        right_layout.addWidget(self.detail_card, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)

        root_layout.addWidget(splitter, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.setCentralWidget(root)

    def refresh_apps(self) -> None:
        self.apps = discover_apps()
        if self.apps and not any(app.key == self.selected_key for app in self.apps):
            self.selected_key = self.apps[0].key
        self.refresh_app_list()
        self.refresh_details()

    def refresh_runtime_state(self) -> None:
        self.refresh_app_list()
        self.refresh_details()

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
        self.summary_label.setText(f"{running_count} calisan | {len(self.apps)} toplam uygulama")

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
            self.app_name_label.setText("Uygulama Sec")
            self.description_label.setText("Detay gormek icin soldan bir uygulama sec.")
            self.meta_label.setText("")
            self.url_input.setText("")
            self.command_preview.setPlainText("")
            self.logs_preview.setPlainText("")
            self.status_badge.setText("READY")
            self.status_badge.setObjectName("BadgeGray")
            self.status_badge.style().unpolish(self.status_badge)
            self.status_badge.style().polish(self.status_badge)
            return

        runtime = self.manager.get_runtime(app)
        running = bool(runtime.pid and is_pid_running(runtime.pid))
        resolved_url = self.manager.get_url(app)
        reachable = bool(resolved_url and is_url_reachable(resolved_url))

        status_text = "RUNNING" if running else "REACHABLE" if reachable else "STOPPED"
        badge_name = "BadgeGreen" if running else "BadgeOrange" if reachable else "BadgeGray"

        self.app_name_label.setText(app.name)
        self.description_label.setText(
            app.description or "Bu uygulama icin aciklama bulunamadi."
        )
        self.meta_label.setText(
            "\n".join(
                [
                    f"Tip: {app.app_type}",
                    f"Klasor: {app.path}",
                    f"Start yontemi: {app.start_mode}",
                    f"PID: {runtime.pid or '-'}",
                    f"Son baslatma: {format_dt(runtime.started_at)}",
                    f"URL erisimi: {'OK' if reachable else 'Yok'}",
                ]
            )
        )

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
        self.open_url_button.setEnabled(bool(resolved_url))
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
        ok, message = self.manager.start_app(app)
        self.status_bar.showMessage(message, 3500)
        if not ok:
            QMessageBox.warning(self, "Start Hatasi", message)
        self.refresh_runtime_state()

    def open_selected_app(self) -> None:
        app = self.get_selected_app()
        if not app:
            return

        runtime = self.manager.get_runtime(app)
        running = bool(runtime.pid and is_pid_running(runtime.pid))
        url = self.manager.get_url(app)

        if app.app_type == "web":
            if not url:
                QMessageBox.information(self, "URL Yok", "Bu web uygulamasi icin URL tanimli degil.")
                return

            if not running and not is_url_reachable(url):
                ok, message = self.manager.start_app(app)
                self.status_bar.showMessage(message, 3500)
                if not ok:
                    QMessageBox.warning(self, "Acma Hatasi", message)
                    self.refresh_runtime_state()
                    return

                ready = self.manager.wait_until_ready(app, timeout_seconds=12.0)
                self.refresh_runtime_state()
                if not ready:
                    QMessageBox.warning(
                        self,
                        "Web Uygulamasi Hazir Degil",
                        "Uygulama baslatildi ama URL henuz erisilebilir olmadi. Log'lari kontrol et.",
                    )
                    return

            QDesktopServices.openUrl(QUrl(url))
            self.status_bar.showMessage("Web uygulamasi acildi.", 2500)
            self.refresh_runtime_state()
            return

        ok, message = self.manager.start_app(app)
        self.status_bar.showMessage(message, 3500)
        if not ok:
            QMessageBox.warning(self, "Acma Hatasi", message)
        else:
            runtime = self.manager.get_runtime(app)
            activated = activate_pid(runtime.pid)
            if activated:
                self.status_bar.showMessage("Masaustu uygulamasi one getirildi.", 2500)
            else:
                QMessageBox.information(
                    self,
                    "Uygulama Baslatildi",
                    "Masaustu uygulamasi baslatildi. Gorunurde degilse menubar veya acik pencereler arasinda kontrol et.",
                )
        self.refresh_runtime_state()

    def stop_selected_app(self) -> None:
        app = self.get_selected_app()
        if not app:
            return
        ok, message = self.manager.stop_app(app)
        self.status_bar.showMessage(message, 3500)
        if not ok:
            QMessageBox.warning(self, "Stop Hatasi", message)
        self.refresh_runtime_state()

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
        geometry = self.state.get_window().get("geometry")
        if geometry and len(geometry) == 4:
            self.setGeometry(*geometry)

    def save_geometry_to_state(self) -> None:
        self.state.update_window(
            geometry=[self.x(), self.y(), self.width(), self.height()],
            selected_key=self.selected_key,
        )

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.save_geometry_to_state()
        super().closeEvent(event)
