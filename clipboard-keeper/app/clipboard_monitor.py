from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage

from .constants import IMAGE_DIR
from .models import ClipEntry
from .utils import (
    build_preview,
    build_title,
    detect_text_type,
    sha1_bytes,
    sha1_text,
    strip_html,
)


class ClipboardMonitor(QObject):
    entry_captured = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.clipboard = QGuiApplication.clipboard()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_clipboard)
        self.last_signature = ""

    def start(self, interval_ms: int) -> None:
        self.timer.start(max(350, interval_ms))
        QTimer.singleShot(500, self.poll_clipboard)

    def update_interval(self, interval_ms: int) -> None:
        if self.timer.isActive():
            self.timer.start(max(350, interval_ms))

    def poll_clipboard(self) -> None:
        payload = self._extract_payload()
        if not payload:
            return

        signature = payload["signature"]
        if signature == self.last_signature:
            return

        self.last_signature = signature
        entry = ClipEntry(
            id=str(uuid.uuid4()),
            entry_type=payload["entry_type"],
            title=payload["title"],
            preview=payload["preview"],
            content=payload.get("content", ""),
            html=payload.get("html", ""),
            image_path=payload.get("image_path", ""),
            source_signature=signature,
            metadata=payload.get("metadata", {}),
        )
        self.entry_captured.emit(entry)

    def _extract_payload(self) -> dict | None:
        mime = self.clipboard.mimeData()
        if mime is None:
            return None

        if mime.hasImage():
            image = self.clipboard.image()
            if image.isNull():
                return None
            return self._image_payload(image)

        if mime.hasUrls():
            items = []
            for url in mime.urls():
                items.append(url.toLocalFile() or url.toString())
            content = "\n".join(items).strip()
            if not content:
                return None
            entry_type = "file-list" if any(Path(item).exists() for item in items) else "url-list"
            metadata = {"items": items}
            return {
                "entry_type": entry_type,
                "title": build_title(entry_type, content, metadata),
                "preview": build_preview(entry_type, content, metadata),
                "content": content,
                "signature": sha1_text([entry_type, content]),
                "metadata": metadata,
            }

        if mime.hasHtml():
            html = mime.html().strip()
            text = strip_html(html)
            if text:
                entry_type = detect_text_type(text)
                return {
                    "entry_type": "html" if entry_type == "text" else entry_type,
                    "title": build_title(entry_type, text),
                    "preview": build_preview(entry_type, text),
                    "content": text,
                    "html": html,
                    "signature": sha1_text(["html", html]),
                }

        if mime.hasText():
            text = self.clipboard.text().strip()
            if not text:
                return None
            entry_type = detect_text_type(text)
            return {
                "entry_type": entry_type,
                "title": build_title(entry_type, text),
                "preview": build_preview(entry_type, text),
                "content": text,
                "signature": sha1_text([entry_type, text]),
            }

        return None

    def _image_payload(self, image: QImage) -> dict | None:
        image_buffer = QByteArray()
        buffer = QBuffer(image_buffer)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        signature = sha1_bytes(bytes(image_buffer))

        image_id = str(uuid.uuid4())
        image_path = IMAGE_DIR / f"{image_id}.png"
        if not image.save(str(image_path), "PNG"):
            return None

        metadata = {"width": image.width(), "height": image.height()}
        content = str(image_path)
        return {
            "entry_type": "image",
            "title": build_title("image", content, metadata),
            "preview": build_preview("image", content, metadata),
            "content": content,
            "image_path": str(image_path),
            "signature": signature,
            "metadata": metadata,
        }
