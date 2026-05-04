from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import ClipEntry, WorkspaceTab
from .utils import format_time, humanize_entry_type


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
