from __future__ import annotations

import os
import subprocess
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .constants import APP_NAME, DEFAULT_EXPORT_DIR
from .models import AppSettings, ClipEntry, WorkspaceTab
from .storage import StateStore
from .startup import StartupManager
from .utils import format_dt, format_time, humanize_entry_type, within_days


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


class EntryCard(QFrame):
    def __init__(
        self,
        entry: ClipEntry,
        on_open: Callable[[str], None],
        on_copy: Callable[[str], None],
        on_pin: Callable[[str], None],
        on_delete: Callable[[str], None],
        on_quick_open: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.entry = entry
        self.on_open = on_open
        self.setObjectName("Card")
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(entry.content or entry.preview)

        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(14, 12, 14, 12)
        wrapper.setSpacing(10)

        top_row = QHBoxLayout()
        badge = QLabel(humanize_entry_type(entry.entry_type))
        badge.setObjectName("BadgeLabel")
        top_row.addWidget(badge)

        time_label = QLabel(format_time(entry.created_at))
        time_label.setObjectName("MutedLabel")
        top_row.addWidget(time_label)
        top_row.addStretch()

        pin_button = QToolButton()
        pin_button.setText("Unpin" if entry.pinned else "Pin")
        pin_button.clicked.connect(lambda: on_pin(entry.id))
        top_row.addWidget(pin_button)

        open_button = QToolButton()
        open_button.setText("Sekme")
        open_button.clicked.connect(lambda: on_open(entry.id))
        top_row.addWidget(open_button)

        copy_button = QToolButton()
        copy_button.setText("Kopyala")
        copy_button.clicked.connect(lambda: on_copy(entry.id))
        top_row.addWidget(copy_button)

        if entry.entry_type in {"url", "url-list", "file-list", "image"}:
            quick_button = QToolButton()
            quick_button.setText("Ac")
            quick_button.clicked.connect(lambda: on_quick_open(entry.id))
            top_row.addWidget(quick_button)

        delete_button = QToolButton()
        delete_button.setText("Tek Sil")
        delete_button.setToolTip("Bu kaydi tek basina sil")
        delete_button.clicked.connect(lambda: on_delete(entry.id))
        top_row.addWidget(delete_button)

        wrapper.addLayout(top_row)

        title = QLabel(entry.title)
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        title.setWordWrap(True)
        wrapper.addWidget(title)

        preview = QLabel(entry.preview or entry.content)
        preview.setWordWrap(True)
        preview.setObjectName("MutedLabel")
        preview.setToolTip(entry.content or entry.preview)
        wrapper.addWidget(preview)

        note_text = entry.note.strip()
        if note_text:
            note_label = QLabel(f"Not: {note_text}")
            note_label.setWordWrap(True)
            note_label.setStyleSheet("color: #30538a;")
            wrapper.addWidget(note_label)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        super().mouseDoubleClickEvent(event)
        self.on_open(self.entry.id)


class EditorTab(QWidget):
    def __init__(
        self,
        tab_data: WorkspaceTab,
        source_entry: Optional[ClipEntry],
        on_change: Callable[[], None],
        on_save_source: Callable[[WorkspaceTab], None],
        on_copy: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.tab_data = tab_data
        self.source_entry = source_entry
        self.on_change = on_change
        self.on_save_source = on_save_source
        self.on_copy = on_copy
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        card = QFrame()
        card.setObjectName("EditorCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        title_row = QHBoxLayout()
        self.title_edit = QLineEdit(self.tab_data.title)
        self.title_edit.setPlaceholderText("Sekme basligi")
        self.title_edit.textChanged.connect(self._mark_changed)
        title_row.addWidget(self.title_edit)

        self.meta_label = QLabel(self._meta_text())
        self.meta_label.setObjectName("MutedLabel")
        title_row.addWidget(self.meta_label)
        card_layout.addLayout(title_row)

        if self.source_entry and self.source_entry.entry_type == "image" and self.source_entry.image_path:
            image_label = QLabel()
            pixmap = QPixmap(self.source_entry.image_path)
            if not pixmap.isNull():
                image_label.setPixmap(
                    pixmap.scaled(360, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                card_layout.addWidget(image_label)

        self.editor = QPlainTextEdit(self.tab_data.content)
        self.editor.setPlaceholderText("Burada duzenleyebilir, not alabilir, birlestirebilirsin.")
        self.editor.textChanged.connect(self._mark_changed)
        card_layout.addWidget(self.editor, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()

        copy_button = QPushButton("Metni Kopyala")
        copy_button.clicked.connect(lambda: self.on_copy(self.editor.toPlainText()))
        button_row.addWidget(copy_button)

        save_button = QPushButton("Kaydi Guncelle")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(lambda: self.on_save_source(self.to_workspace_tab()))
        button_row.addWidget(save_button)
        card_layout.addLayout(button_row)

        root.addWidget(card)

    def _meta_text(self) -> str:
        if self.source_entry:
            return f"Kaynak: {humanize_entry_type(self.source_entry.entry_type)}"
        return "Serbest not sekmesi"

    def _mark_changed(self) -> None:
        self.on_change()

    def to_workspace_tab(self) -> WorkspaceTab:
        return WorkspaceTab(
            id=self.tab_data.id,
            title=self.title_edit.text().strip() or "Adsiz sekme",
            content=self.editor.toPlainText(),
            source_entry_id=self.tab_data.source_entry_id,
            entry_type=self.tab_data.entry_type,
            created_at=self.tab_data.created_at,
            updated_at=datetime.now().astimezone().isoformat(),
        )


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.settings = settings
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.recent_limit = QSpinBox()
        self.recent_limit.setRange(5, 50)
        self.recent_limit.setValue(self.settings.recent_limit)
        form.addRow("Son kayit sayisi", self.recent_limit)

        self.show_all_days = QSpinBox()
        self.show_all_days.setRange(1, 180)
        self.show_all_days.setValue(self.settings.show_all_days)
        form.addRow("Show all gun araligi", self.show_all_days)

        self.retention_days = QSpinBox()
        self.retention_days.setRange(10, 365)
        self.retention_days.setValue(self.settings.retention_days)
        form.addRow("Veri saklama gunu", self.retention_days)

        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(350, 5000)
        self.poll_interval.setValue(self.settings.poll_interval_ms)
        self.poll_interval.setSuffix(" ms")
        form.addRow("Pano kontrol araligi", self.poll_interval)

        self.ignore_duplicates = QCheckBox("Ardisik ayni kopyalari atla")
        self.ignore_duplicates.setChecked(self.settings.ignore_consecutive_duplicates)
        form.addRow("", self.ignore_duplicates)

        self.show_notifications = QCheckBox("Yeni kopyalarda bildirim goster")
        self.show_notifications.setChecked(self.settings.show_notifications)
        form.addRow("", self.show_notifications)

        self.start_at_login = QCheckBox("Acilista baslat")
        self.start_at_login.setChecked(self.settings.start_at_login)
        form.addRow("", self.start_at_login)

        self.always_on_top = QCheckBox("Pencereyi her zaman ustte tut")
        self.always_on_top.setChecked(self.settings.always_on_top)
        form.addRow("", self.always_on_top)

        self.hide_dock_icon = QCheckBox("Dock ikonunu gizlemeyi dene")
        self.hide_dock_icon.setChecked(self.settings.hide_dock_icon)
        form.addRow("", self.hide_dock_icon)

        export_row = QHBoxLayout()
        self.export_dir = QLineEdit(self.settings.export_dir)
        export_row.addWidget(self.export_dir)
        choose_button = QPushButton("Sec")
        choose_button.clicked.connect(self._choose_export_dir)
        export_row.addWidget(choose_button)
        export_wrapper = QWidget()
        export_wrapper.setLayout(export_row)
        form.addRow("Export klasoru", export_wrapper)

        root.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton("Vazgec")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        save_button = QPushButton("Kaydet")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self.accept)
        buttons.addWidget(save_button)
        root.addLayout(buttons)

    def _choose_export_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Export klasoru sec",
            self.export_dir.text() or str(DEFAULT_EXPORT_DIR),
        )
        if selected:
            self.export_dir.setText(selected)

    def build_settings(self) -> AppSettings:
        return AppSettings(
            recent_limit=self.recent_limit.value(),
            show_all_days=self.show_all_days.value(),
            retention_days=self.retention_days.value(),
            always_on_top=self.always_on_top.isChecked(),
            start_at_login=self.start_at_login.isChecked(),
            show_notifications=self.show_notifications.isChecked(),
            ignore_consecutive_duplicates=self.ignore_duplicates.isChecked(),
            poll_interval_ms=self.poll_interval.value(),
            restore_tabs=True,
            hide_dock_icon=self.hide_dock_icon.isChecked(),
            export_dir=self.export_dir.text().strip() or str(DEFAULT_EXPORT_DIR),
        )


class MainWindow(QMainWindow):
    def __init__(self, store: StateStore, startup_manager: StartupManager) -> None:
        super().__init__()
        self.store = store
        self.startup_manager = startup_manager
        self.settings = self.store.get_settings()
        self.entries = self.store.get_entries()
        self.force_quit = False
        self.monitor = None
        self.show_all_enabled = self.store.get_window_state().get("show_all", False)
        self.tab_save_timer = QTimer(self)
        self.tab_save_timer.setInterval(400)
        self.tab_save_timer.setSingleShot(True)
        self.tab_save_timer.timeout.connect(self.persist_tabs)
        self._build()
        self._create_tray_icon()
        self.restore_tabs()
        self.refresh_history()
        self.apply_window_flags()
        self.restore_geometry_from_state()

    def attach_monitor(self, monitor) -> None:
        self.monitor = monitor
        self.monitor.entry_captured.connect(self.handle_new_entry)
        self.monitor.start(self.settings.poll_interval_ms)

    def _build(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(APP_STYLE)
        self.setWindowIcon(generate_tray_icon(64))

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("Surface")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(12)

        title_block = QVBoxLayout()
        title = QLabel("Clipboard Keeper Pro")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Pinned kayitlar, son 10 kayit, sekmeler ve export tek ekranda.")
        subtitle.setObjectName("MutedLabel")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header_layout.addLayout(title_block)

        header_layout.addStretch()

        self.stats_label = QLabel("")
        self.stats_label.setObjectName("MutedLabel")
        header_layout.addWidget(self.stats_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ara: metin, link, kod, not...")
        self.search_input.setFixedWidth(260)
        self.search_input.textChanged.connect(self.refresh_history)
        header_layout.addWidget(self.search_input)

        new_tab_button = QPushButton("Yeni Not")
        new_tab_button.clicked.connect(self.create_blank_tab)
        header_layout.addWidget(new_tab_button)

        self.show_all_button = QPushButton()
        self.show_all_button.clicked.connect(self.toggle_show_all)
        header_layout.addWidget(self.show_all_button)

        clear_button = QPushButton("Sonlari Temizle")
        clear_button.clicked.connect(self.clear_recent_entries)
        header_layout.addWidget(clear_button)

        export_button = QPushButton("TXT Kaydet")
        export_button.setObjectName("PrimaryButton")
        export_button.clicked.connect(self.export_to_txt)
        header_layout.addWidget(export_button)

        settings_button = QPushButton("Ayarlar")
        settings_button.clicked.connect(self.open_settings)
        header_layout.addWidget(settings_button)

        self.always_on_top_button = QPushButton()
        self.always_on_top_button.clicked.connect(self.toggle_always_on_top)
        header_layout.addWidget(self.always_on_top_button)

        root_layout.addWidget(header)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        history_frame = QFrame()
        history_frame.setObjectName("Surface")
        history_layout = QVBoxLayout(history_frame)
        history_layout.setContentsMargins(16, 16, 16, 16)
        history_layout.setSpacing(12)

        left_title = QLabel("Pano Gecmisi")
        left_title.setObjectName("SectionLabel")
        history_layout.addWidget(left_title)

        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(12)
        self.history_layout.addStretch()
        self.history_scroll.setWidget(self.history_container)
        history_layout.addWidget(self.history_scroll, 1)
        splitter.addWidget(history_frame)

        workspace_frame = QFrame()
        workspace_frame.setObjectName("Surface")
        workspace_layout = QVBoxLayout(workspace_frame)
        workspace_layout.setContentsMargins(16, 16, 16, 16)
        workspace_layout.setSpacing(12)

        right_title = QLabel("Calisma Sekmeleri")
        right_title.setObjectName("SectionLabel")
        workspace_layout.addWidget(right_title)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        workspace_layout.addWidget(self.tabs, 1)
        splitter.addWidget(workspace_frame)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        root_layout.addWidget(splitter, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.setCentralWidget(root)

        self.update_header_buttons()

    def _create_tray_icon(self) -> None:
        self.tray_icon = QSystemTrayIcon(generate_tray_icon())
        self.tray_icon.setToolTip(APP_NAME)

        menu = QMenu()
        show_action = QAction("Pencereyi Goster", self)
        show_action.triggered.connect(self.show_window)
        menu.addAction(show_action)

        hide_action = QAction("Pencereyi Gizle", self)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)

        new_tab_action = QAction("Yeni Not Sekmesi", self)
        new_tab_action.triggered.connect(self.create_blank_tab)
        menu.addAction(new_tab_action)

        menu.addSeparator()

        copy_latest_action = QAction("Son Kaydi Kopyala", self)
        copy_latest_action.triggered.connect(self.copy_latest_entry)
        menu.addAction(copy_latest_action)

        clear_recent_action = QAction("Pinli Disindakileri Temizle", self)
        clear_recent_action.triggered.connect(self.clear_recent_entries)
        menu.addAction(clear_recent_action)

        open_export_action = QAction("Export Klasorunu Ac", self)
        open_export_action.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(self.settings.export_dir).expanduser()))
            )
        )
        menu.addAction(open_export_action)

        menu.addSeparator()

        quit_action = QAction("Cikis", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._handle_tray_activation)
        self.tray_icon.show()

    def _handle_tray_activation(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh_history(self) -> None:
        clear_layout(self.history_layout)
        query = self.search_input.text().strip().lower()

        filtered = [
            entry
            for entry in self.entries
            if not query
            or query in entry.title.lower()
            or query in entry.preview.lower()
            or query in entry.content.lower()
            or query in entry.note.lower()
        ]

        pinned = [entry for entry in filtered if entry.pinned]
        non_pinned = [entry for entry in filtered if not entry.pinned]
        recent = non_pinned[: self.settings.recent_limit]
        overflow = [
            entry
            for entry in non_pinned[self.settings.recent_limit :]
            if within_days(entry.created_at, self.settings.show_all_days)
        ]

        self.history_layout.addWidget(self._section_label("Pinlenmis"))
        if pinned:
            for entry in pinned:
                self.history_layout.addWidget(self._card_for(entry))
        else:
            self.history_layout.addWidget(self._empty_label("Pinlenmis kayit yok."))

        self.history_layout.addSpacing(6)
        self.history_layout.addWidget(self._section_label("Son Kopyalananlar"))
        if recent:
            for entry in recent:
                self.history_layout.addWidget(self._card_for(entry))
        else:
            self.history_layout.addWidget(self._empty_label("Henüz kayit yok."))

        if self.show_all_enabled:
            self.history_layout.addSpacing(8)
            self.history_layout.addWidget(
                self._section_label(f"Show All - Son {self.settings.show_all_days} Gun")
            )
            if overflow:
                for entry in overflow:
                    self.history_layout.addWidget(self._card_for(entry))
            else:
                self.history_layout.addWidget(
                    self._empty_label("Ek gecmis kaydi bulunamadi.")
                )

        self.history_layout.addStretch()
        self.stats_label.setText(
            f"{len(pinned)} pinned | {len(recent)} gorunen | {len(self.entries)} toplam"
        )
        self.update_header_buttons()

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def _empty_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("MutedLabel")
        label.setWordWrap(True)
        return label

    def _card_for(self, entry: ClipEntry) -> EntryCard:
        return EntryCard(
            entry=entry,
            on_open=self.open_entry_in_tab,
            on_copy=self.copy_entry_to_clipboard,
            on_pin=self.toggle_pin_entry,
            on_delete=self.delete_entry,
            on_quick_open=self.quick_open_entry,
        )

    def update_header_buttons(self) -> None:
        self.show_all_button.setText(
            "Show All Kapat" if self.show_all_enabled else "Show All"
        )
        self.always_on_top_button.setText(
            "Pini Kaldir" if self.settings.always_on_top else "Ekrana Pinle"
        )

    def handle_new_entry(self, entry: ClipEntry) -> None:
        if (
            self.settings.ignore_consecutive_duplicates
            and self.entries
            and self.entries[0].source_signature == entry.source_signature
        ):
            return

        self.store.add_entry(entry, self.settings.retention_days)
        self.entries = self.store.get_entries()
        self.refresh_history()
        self.status_bar.showMessage(
            f"Yeni kayit eklendi: {entry.title}", 3000
        )
        self.show_capture_notification(entry)

    def show_capture_notification(self, entry: ClipEntry) -> None:
        if not self.settings.show_notifications:
            return

        title = f"Yeni kopya: {humanize_entry_type(entry.entry_type)}"
        body = entry.preview or entry.title
        body = body.strip().replace("\n", " ")
        if len(body) > 180:
            body = body[:179].rstrip() + "…"

        if QSystemTrayIcon.supportsMessages():
            self.tray_icon.showMessage(
                title,
                body,
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )
            return

        self.show_macos_notification(title, body)

    def show_macos_notification(self, title: str, body: str) -> None:
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        safe_body = body.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{safe_body}" with title "{safe_title}"'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            pass

    def copy_entry_to_clipboard(self, entry_or_text: str) -> None:
        entry = self.store.get_entry(entry_or_text)
        clipboard = QApplication.clipboard()
        if entry:
            if entry.entry_type == "image" and entry.image_path:
                image = QImage(entry.image_path)
                if not image.isNull():
                    clipboard.setImage(image)
            else:
                clipboard.setText(entry.content)
            self.status_bar.showMessage("Kayit panoya geri kopyalandi.", 2500)
            return

        clipboard.setText(entry_or_text)
        self.status_bar.showMessage("Sekme icerigi kopyalandi.", 2500)

    def toggle_pin_entry(self, entry_id: str) -> None:
        updated = self.store.toggle_pin(entry_id)
        self.entries = self.store.get_entries()
        self.refresh_history()
        if updated:
            message = "Kayit pinlendi." if updated.pinned else "Pin kaldirildi."
            self.status_bar.showMessage(message, 2500)

    def delete_entry(self, entry_id: str) -> None:
        self.store.delete_entry(entry_id)
        self.entries = self.store.get_entries()
        self.refresh_history()
        self.remove_tabs_for_entry(entry_id)
        self.status_bar.showMessage("Kayit silindi.", 2500)

    def clear_recent_entries(self) -> None:
        unpinned_count = len([entry for entry in self.entries if not entry.pinned])
        if unpinned_count == 0:
            self.status_bar.showMessage("Temizlenecek son kayit yok.", 2500)
            return

        answer = QMessageBox.question(
            self,
            "Son Kayitlari Temizle",
            (
                f"Pinli olanlar korunacak.\n"
                f"{unpinned_count} adet pinlenmemis kayit silinsin mi?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        removed_ids = self.store.clear_unpinned_entries()
        self.entries = self.store.get_entries()
        self.remove_tabs_for_entries(removed_ids)
        self.refresh_history()
        self.status_bar.showMessage(
            f"{len(removed_ids)} kayit temizlendi. Pinli olanlar korundu.",
            3500,
        )

    def open_entry_in_tab(self, entry_id: str) -> None:
        for index in range(self.tabs.count()):
            tab_widget = self.tabs.widget(index)
            if getattr(tab_widget, "tab_data", None) and tab_widget.tab_data.source_entry_id == entry_id:
                self.tabs.setCurrentIndex(index)
                return

        entry = self.store.get_entry(entry_id)
        if not entry:
            return

        tab_data = WorkspaceTab(
            id=str(uuid.uuid4()),
            title=entry.title,
            content=entry.content,
            source_entry_id=entry.id,
            entry_type=entry.entry_type,
        )
        widget = EditorTab(
            tab_data=tab_data,
            source_entry=entry,
            on_change=self.schedule_tab_save,
            on_save_source=self.save_tab_to_source,
            on_copy=self.copy_entry_to_clipboard,
        )
        widget.tab_data = tab_data
        self.tabs.addTab(widget, tab_data.title[:18] or "Sekme")
        self.tabs.setCurrentWidget(widget)
        self.persist_tabs()

    def create_blank_tab(self) -> None:
        tab_data = WorkspaceTab(
            id=str(uuid.uuid4()),
            title="Yeni Not",
            content="",
            source_entry_id="",
            entry_type="text",
        )
        widget = EditorTab(
            tab_data=tab_data,
            source_entry=None,
            on_change=self.schedule_tab_save,
            on_save_source=self.save_tab_to_source,
            on_copy=self.copy_entry_to_clipboard,
        )
        widget.tab_data = tab_data
        self.tabs.addTab(widget, "Yeni Not")
        self.tabs.setCurrentWidget(widget)
        self.persist_tabs()

    def save_tab_to_source(self, tab_state: WorkspaceTab) -> None:
        if not tab_state.source_entry_id:
            self.persist_tabs()
            self.status_bar.showMessage("Not sekmesi kaydedildi.", 2500)
            return

        source = self.store.get_entry(tab_state.source_entry_id)
        if not source:
            self.status_bar.showMessage("Kaynak kayit bulunamadi.", 3000)
            return

        source.title = tab_state.title
        source.content = tab_state.content
        source.preview = tab_state.content[:140]
        source.updated_at = tab_state.updated_at
        self.store.update_entry(source)
        self.entries = self.store.get_entries()
        self.refresh_history()
        self.persist_tabs()
        self.status_bar.showMessage("Kaynak kayit guncellendi.", 3000)

    def remove_tabs_for_entry(self, entry_id: str) -> None:
        for index in reversed(range(self.tabs.count())):
            widget = self.tabs.widget(index)
            if getattr(widget, "tab_data", None) and widget.tab_data.source_entry_id == entry_id:
                self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.create_blank_tab()
        self.persist_tabs()

    def remove_tabs_for_entries(self, entry_ids: List[str]) -> None:
        entry_id_set = set(entry_ids)
        for index in reversed(range(self.tabs.count())):
            widget = self.tabs.widget(index)
            if (
                getattr(widget, "tab_data", None)
                and widget.tab_data.source_entry_id in entry_id_set
            ):
                self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.create_blank_tab()
        self.persist_tabs()

    def schedule_tab_save(self) -> None:
        current = self.tabs.currentWidget()
        if current is not None:
            current.tab_data = current.to_workspace_tab()
            current_index = self.tabs.currentIndex()
            self.tabs.setTabText(current_index, current.tab_data.title[:18] or "Sekme")
        self.tab_save_timer.start()

    def persist_tabs(self) -> None:
        tabs: List[WorkspaceTab] = []
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if hasattr(widget, "to_workspace_tab"):
                tabs.append(widget.to_workspace_tab())
                self.tabs.setTabText(index, tabs[-1].title[:18] or "Sekme")
        self.store.set_tabs(tabs)

    def restore_tabs(self) -> None:
        if not self.settings.restore_tabs:
            return
        for tab_data in self.store.get_tabs():
            source = self.store.get_entry(tab_data.source_entry_id) if tab_data.source_entry_id else None
            widget = EditorTab(
                tab_data=tab_data,
                source_entry=source,
                on_change=self.schedule_tab_save,
                on_save_source=self.save_tab_to_source,
                on_copy=self.copy_entry_to_clipboard,
            )
            widget.tab_data = tab_data
            self.tabs.addTab(widget, tab_data.title[:18] or "Sekme")

        if self.tabs.count() == 0:
            self.create_blank_tab()

    def close_tab(self, index: int) -> None:
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.create_blank_tab()
        self.persist_tabs()

    def quick_open_entry(self, entry_id: str) -> None:
        entry = self.store.get_entry(entry_id)
        if not entry:
            return

        if entry.entry_type in {"url", "url-list"}:
            target = entry.content.splitlines()[0].strip()
            webbrowser.open(target)
            return

        if entry.entry_type == "file-list":
            first_path = entry.content.splitlines()[0].strip()
            QDesktopServices.openUrl(QUrl.fromLocalFile(first_path))
            return

        if entry.entry_type == "image" and entry.image_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(entry.image_path))

    def export_to_txt(self) -> None:
        export_dir = Path(self.settings.export_dir).expanduser()
        export_dir.mkdir(parents=True, exist_ok=True)
        default_name = export_dir / f"clipboard-export-{datetime.now():%Y%m%d-%H%M%S}.txt"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "TXT olarak kaydet",
            str(default_name),
            "Text Files (*.txt)",
        )
        if not selected:
            return

        lines = [
            APP_NAME,
            "=" * 80,
            f"Olusturulma: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
            "",
            "[PINLENMIS KAYITLAR]",
            "-" * 80,
        ]

        pinned = [entry for entry in self.entries if entry.pinned]
        recent = [entry for entry in self.entries if not entry.pinned][: self.settings.recent_limit]

        for section_entries in (pinned, recent):
            if not section_entries:
                lines.append("(Bos)")
            for index, entry in enumerate(section_entries, start=1):
                lines.extend(
                    [
                        f"{index}. {entry.title}",
                        f"Tarih: {format_dt(entry.created_at)}",
                        f"Tur: {humanize_entry_type(entry.entry_type)}",
                        "Icerik:",
                        entry.content,
                        "-" * 80,
                    ]
                )
            lines.append("")

        lines.extend(["[ACIK SEKMELER]", "-" * 80])
        if self.tabs.count() == 0:
            lines.append("(Bos)")
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            state = widget.to_workspace_tab()
            lines.extend(
                [
                    f"{index + 1}. {state.title}",
                    state.content,
                    "-" * 80,
                ]
            )

        Path(selected).write_text("\n".join(lines), encoding="utf-8")
        self.status_bar.showMessage(f"TXT export tamamlandi: {selected}", 4000)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != QDialog.Accepted:
            return

        previous_startup = self.settings.start_at_login
        self.settings = dialog.build_settings()
        self.store.update_settings(self.settings)

        if self.settings.start_at_login != previous_startup:
            try:
                if self.settings.start_at_login:
                    self.startup_manager.enable()
                else:
                    self.startup_manager.disable()
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Acilis Ayari",
                    f"Acilista baslatma ayari uygulanamadi:\n{exc}",
                )

        if self.monitor:
            self.monitor.update_interval(self.settings.poll_interval_ms)
        self.apply_window_flags()
        self.refresh_history()
        self.status_bar.showMessage("Ayarlar kaydedildi.", 3000)

    def toggle_show_all(self) -> None:
        self.show_all_enabled = not self.show_all_enabled
        self.store.update_window_state(show_all=self.show_all_enabled)
        self.refresh_history()

    def toggle_always_on_top(self) -> None:
        self.settings.always_on_top = not self.settings.always_on_top
        self.store.update_settings(self.settings)
        self.apply_window_flags()
        self.update_header_buttons()

    def apply_window_flags(self) -> None:
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.settings.always_on_top)
        self.show()
        self.update_header_buttons()

    def restore_geometry_from_state(self) -> None:
        geometry = self.store.get_window_state().get("geometry")
        if geometry and len(geometry) == 4:
            self.setGeometry(*geometry)

    def save_geometry_to_state(self) -> None:
        geometry = [self.x(), self.y(), self.width(), self.height()]
        self.store.update_window_state(geometry=geometry, show_all=self.show_all_enabled)

    def copy_latest_entry(self) -> None:
        if not self.entries:
            return
        self.copy_entry_to_clipboard(self.entries[0].id)

    def quit_application(self) -> None:
        self.force_quit = True
        self.persist_tabs()
        self.save_geometry_to_state()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.persist_tabs()
        self.save_geometry_to_state()
        if self.force_quit:
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()
        self.status_bar.showMessage("Uygulama menubar'da calismaya devam ediyor.", 3000)
