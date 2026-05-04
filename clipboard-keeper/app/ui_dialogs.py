from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .constants import DEFAULT_EXPORT_DIR
from .models import AppSettings


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
