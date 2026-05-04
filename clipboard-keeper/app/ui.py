from __future__ import annotations

import os
import subprocess
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QCursor,
    QDesktopServices,
    QImage,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .constants import APP_NAME
from .models import ClipEntry, WorkspaceTab
from .storage import StateStore
from .startup import StartupManager
from .ui_dialogs import SettingsDialog
from .ui_shared import APP_STYLE, clear_layout, generate_tray_icon
from .ui_widgets import EditorTab, EntryCard
from .utils import format_dt, format_time, humanize_entry_type, within_days


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

        self.tray_menu = QMenu()
        show_action = QAction("Pencereyi Goster", self)
        show_action.triggered.connect(self.show_window)
        self.tray_menu.addAction(show_action)

        hide_action = QAction("Pencereyi Gizle", self)
        hide_action.triggered.connect(self.hide)
        self.tray_menu.addAction(hide_action)

        new_tab_action = QAction("Yeni Not Sekmesi", self)
        new_tab_action.triggered.connect(self.create_blank_tab)
        self.tray_menu.addAction(new_tab_action)

        self.tray_menu.addSeparator()

        copy_latest_action = QAction("Son Kaydi Kopyala", self)
        copy_latest_action.triggered.connect(self.copy_latest_entry)
        self.tray_menu.addAction(copy_latest_action)

        clear_recent_action = QAction("Pinli Disindakileri Temizle", self)
        clear_recent_action.triggered.connect(self.clear_recent_entries)
        self.tray_menu.addAction(clear_recent_action)

        open_export_action = QAction("Export Klasorunu Ac", self)
        open_export_action.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(self.settings.export_dir).expanduser()))
            )
        )
        self.tray_menu.addAction(open_export_action)

        self.tray_menu.addSeparator()

        quit_action = QAction("Cikis", self)
        quit_action.triggered.connect(self.quit_application)
        self.tray_menu.addAction(quit_action)

        self.tray_icon.activated.connect(self._handle_tray_activation)
        self.tray_icon.show()

    def _handle_tray_activation(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()
        elif reason == QSystemTrayIcon.Context:
            self.tray_menu.popup(QCursor.pos())

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
