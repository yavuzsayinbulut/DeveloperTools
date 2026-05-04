from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import DATA_FILE, DEFAULT_EXPORT_DIR, IMAGE_DIR, SUPPORT_DIR
from .models import AppSettings, ClipEntry, WorkspaceTab
from .utils import parse_iso


class StateStore:
    def __init__(self) -> None:
        SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "settings": AppSettings().to_dict(),
            "entries": [],
            "tabs": [],
            "window": {"show_all": False, "geometry": None},
        }

    def _load(self) -> Dict[str, Any]:
        if not DATA_FILE.exists():
            state = self._default_state()
            self._write(state)
            return state

        try:
            payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            payload = self._default_state()

        merged = self._default_state()
        merged.update(payload)
        merged["settings"] = {**merged["settings"], **payload.get("settings", {})}
        merged["window"] = {**merged["window"], **payload.get("window", {})}
        return merged

    def _write(self, state: Dict[str, Any]) -> None:
        DATA_FILE.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save(self) -> None:
        self._write(self.state)

    def get_settings(self) -> AppSettings:
        return AppSettings.from_dict(self.state["settings"])

    def update_settings(self, settings: AppSettings) -> None:
        self.state["settings"] = settings.to_dict()
        export_dir = Path(settings.export_dir).expanduser()
        export_dir.mkdir(parents=True, exist_ok=True)
        self.save()

    def get_entries(self) -> List[ClipEntry]:
        entries = [ClipEntry.from_dict(item) for item in self.state.get("entries", [])]
        return sorted(entries, key=lambda item: item.created_at, reverse=True)

    def add_entry(self, entry: ClipEntry, retention_days: int) -> None:
        entries = [entry.to_dict()] + self.state.get("entries", [])
        self.state["entries"] = self._prune_entries(entries, retention_days)
        self.save()

    def update_entry(self, updated: ClipEntry) -> None:
        entries = self.state.get("entries", [])
        for index, payload in enumerate(entries):
            if payload["id"] == updated.id:
                entries[index] = updated.to_dict()
                break
        self.state["entries"] = entries
        self.save()

    def toggle_pin(self, entry_id: str) -> Optional[ClipEntry]:
        entries = self.state.get("entries", [])
        for index, payload in enumerate(entries):
            if payload["id"] == entry_id:
                payload["pinned"] = not payload.get("pinned", False)
                entries[index] = payload
                self.save()
                return ClipEntry.from_dict(payload)
        return None

    def delete_entry(self, entry_id: str) -> None:
        self.state["entries"] = [
            payload
            for payload in self.state.get("entries", [])
            if payload.get("id") != entry_id
        ]
        self.state["tabs"] = [
            payload
            for payload in self.state.get("tabs", [])
            if payload.get("source_entry_id") != entry_id
        ]
        self.save()

    def clear_unpinned_entries(self) -> List[str]:
        removed_ids = [
            payload.get("id", "")
            for payload in self.state.get("entries", [])
            if not payload.get("pinned", False)
        ]
        removed_ids = [entry_id for entry_id in removed_ids if entry_id]

        self.state["entries"] = [
            payload
            for payload in self.state.get("entries", [])
            if payload.get("pinned", False)
        ]
        self.state["tabs"] = [
            payload
            for payload in self.state.get("tabs", [])
            if payload.get("source_entry_id") not in removed_ids
        ]
        self.save()
        return removed_ids

    def get_entry(self, entry_id: str) -> Optional[ClipEntry]:
        for payload in self.state.get("entries", []):
            if payload.get("id") == entry_id:
                return ClipEntry.from_dict(payload)
        return None

    def get_tabs(self) -> List[WorkspaceTab]:
        return [WorkspaceTab.from_dict(item) for item in self.state.get("tabs", [])]

    def set_tabs(self, tabs: List[WorkspaceTab]) -> None:
        self.state["tabs"] = [tab.to_dict() for tab in tabs]
        self.save()

    def get_window_state(self) -> Dict[str, Any]:
        return self.state.get("window", {})

    def update_window_state(self, **kwargs: Any) -> None:
        window = self.state.setdefault("window", {})
        window.update(kwargs)
        self.save()

    def _prune_entries(
        self, entries: List[Dict[str, Any]], retention_days: int
    ) -> List[Dict[str, Any]]:
        pruned: List[Dict[str, Any]] = []
        seen = set()
        cutoff_entries: List[Dict[str, Any]] = []

        for payload in entries:
            entry_id = payload.get("id")
            if not entry_id or entry_id in seen:
                continue
            seen.add(entry_id)
            cutoff_entries.append(payload)

        if retention_days <= 0:
            return cutoff_entries[:3000]

        latest = sorted(
            cutoff_entries,
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        for payload in latest:
            if payload.get("pinned"):
                pruned.append(payload)
                continue
            created_at = parse_iso(payload.get("created_at", ""))
            if created_at >= cutoff:
                pruned.append(payload)

        return pruned[:3000]
