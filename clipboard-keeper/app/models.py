from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

from .constants import DEFAULT_EXPORT_DIR


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ClipEntry:
    id: str
    entry_type: str
    title: str
    preview: str
    content: str = ""
    html: str = ""
    image_path: str = ""
    source_signature: str = ""
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    pinned: bool = False
    note: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ClipEntry":
        return cls(**payload)


@dataclass
class WorkspaceTab:
    id: str
    title: str
    content: str
    source_entry_id: str = ""
    entry_type: str = "text"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WorkspaceTab":
        return cls(**payload)


@dataclass
class AppSettings:
    recent_limit: int = 10
    show_all_days: int = 10
    retention_days: int = 30
    always_on_top: bool = False
    start_at_login: bool = False
    show_notifications: bool = True
    ignore_consecutive_duplicates: bool = True
    poll_interval_ms: int = 700
    restore_tabs: bool = True
    hide_dock_icon: bool = True
    export_dir: str = str(DEFAULT_EXPORT_DIR)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AppSettings":
        return cls(**payload)
