from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DiscoveredApp:
    key: str
    name: str
    path: str
    app_type: str
    start_mode: str
    start_command: List[str] = field(default_factory=list)
    start_script: str = ""
    stop_script: str = ""
    default_url: str = ""
    description: str = ""
    readme_path: str = ""
    log_paths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeState:
    url_override: str = ""
    pid: int | None = None
    started_at: str = ""
    stdout_log: str = ""
    stderr_log: str = ""
    last_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RuntimeState":
        return cls(**payload)
