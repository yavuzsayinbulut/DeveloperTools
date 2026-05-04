from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d\s().-]{8,}$")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)


def format_dt(value: str) -> str:
    dt = parse_iso(value).astimezone()
    return dt.strftime("%d.%m.%Y %H:%M")


def format_time(value: str) -> str:
    dt = parse_iso(value).astimezone()
    return dt.strftime("%H:%M")


def within_days(value: str, days: int) -> bool:
    dt = parse_iso(value)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return dt >= cutoff


def ellipsize(text: str, limit: int = 100) -> str:
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def strip_html(html: str) -> str:
    text = HTML_TAG_RE.sub(" ", html)
    return " ".join(unescape(text).split())


def sha1_text(parts: Iterable[str]) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()


def sha1_bytes(data: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(data)
    return digest.hexdigest()


def detect_text_type(text: str) -> str:
    candidate = text.strip()
    if not candidate:
        return "text"
    if EMAIL_RE.match(candidate):
        return "email"
    if PHONE_RE.match(candidate):
        return "phone"
    if candidate.startswith(("http://", "https://")):
        return "url"
    try:
        parsed = urlparse(candidate)
        if parsed.scheme and parsed.netloc:
            return "url"
    except Exception:
        pass
    try:
        json.loads(candidate)
        return "json"
    except Exception:
        pass
    code_markers = ["def ", "class ", "import ", "{", "}", "=>", "SELECT ", "function "]
    if "\n" in candidate and any(marker in candidate for marker in code_markers):
        return "code"
    return "text"


def build_title(entry_type: str, content: str, metadata: dict | None = None) -> str:
    metadata = metadata or {}
    if entry_type == "image":
        width = metadata.get("width", "?")
        height = metadata.get("height", "?")
        return f"Image {width}x{height}"
    if entry_type == "file-list":
        files = metadata.get("items", [])
        if files:
            first = Path(files[0]).name or files[0]
            suffix = f" +{len(files) - 1}" if len(files) > 1 else ""
            return f"{first}{suffix}"
        return "File list"
    if entry_type == "url-list":
        items = metadata.get("items", [])
        if items:
            return ellipsize(items[0], 40)
        return "URL list"

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if lines:
        return ellipsize(lines[0], 48)
    return entry_type.replace("-", " ").title()


def build_preview(entry_type: str, content: str, metadata: dict | None = None) -> str:
    metadata = metadata or {}
    if entry_type == "image":
        width = metadata.get("width", "?")
        height = metadata.get("height", "?")
        return f"Gorsel kopyalandi ({width}x{height})"
    if entry_type in {"file-list", "url-list"}:
        items = metadata.get("items", [])
        return ellipsize(" | ".join(items), 120)
    return ellipsize(content, 140)


def humanize_entry_type(entry_type: str) -> str:
    mapping = {
        "text": "Metin",
        "url": "Link",
        "url-list": "Link Listesi",
        "json": "JSON",
        "code": "Kod",
        "email": "E-Posta",
        "phone": "Telefon",
        "html": "HTML",
        "file-list": "Dosya",
        "image": "Gorsel",
        "unknown": "Bilinmeyen",
    }
    return mapping.get(entry_type, entry_type.title())
