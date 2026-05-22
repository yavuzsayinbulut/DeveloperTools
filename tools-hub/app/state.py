from __future__ import annotations

import json
from typing import Any, Dict

from .constants import STATE_FILE, SUPPORT_DIR
from .models import RuntimeState


class HubState:
    def __init__(self) -> None:
        SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "apps": {},
            "window": {"geometry": None, "selected_key": ""},
            "hidden_apps": [],
            "projects": [],
            "projects_window": {"selected_key": ""},
        }

    def _load(self) -> Dict[str, Any]:
        if not STATE_FILE.exists():
            state = self._default_state()
            self._write(state)
            return state
        try:
            payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            payload = self._default_state()
        merged = self._default_state()
        merged.update(payload)
        merged["apps"] = payload.get("apps", {})
        merged["window"] = {**merged["window"], **payload.get("window", {})}
        merged["hidden_apps"] = payload.get("hidden_apps", [])
        merged["projects"] = payload.get("projects", [])
        merged["projects_window"] = {
            **merged["projects_window"],
            **payload.get("projects_window", {}),
        }
        return merged

    def _write(self, payload: Dict[str, Any]) -> None:
        STATE_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save(self) -> None:
        self._write(self.state)

    def get_runtime(self, app_key: str) -> RuntimeState:
        payload = self.state.get("apps", {}).get(app_key, {})
        return RuntimeState.from_dict(payload)

    def set_runtime(self, app_key: str, runtime: RuntimeState) -> None:
        self.state.setdefault("apps", {})[app_key] = runtime.to_dict()
        self.save()

    def patch_runtime(self, app_key: str, **kwargs: Any) -> RuntimeState:
        runtime = self.get_runtime(app_key)
        for key, value in kwargs.items():
            setattr(runtime, key, value)
        self.set_runtime(app_key, runtime)
        return runtime

    def update_window(self, **kwargs: Any) -> None:
        self.state.setdefault("window", {}).update(kwargs)
        self.save()

    def get_window(self) -> Dict[str, Any]:
        return self.state.get("window", {})

    def get_hidden_apps(self) -> list[str]:
        return list(self.state.get("hidden_apps", []))

    def is_app_hidden(self, app_key: str) -> bool:
        return app_key in set(self.get_hidden_apps())

    def set_app_hidden(self, app_key: str, hidden: bool) -> None:
        hidden_apps = set(self.get_hidden_apps())
        if hidden:
            hidden_apps.add(app_key)
        else:
            hidden_apps.discard(app_key)
        self.state["hidden_apps"] = sorted(hidden_apps)
        self.save()

    def get_projects(self) -> list[Dict[str, Any]]:
        return list(self.state.get("projects", []))

    def set_projects(self, projects: list[Dict[str, Any]]) -> None:
        self.state["projects"] = list(projects)
        self.save()

    def get_projects_window(self) -> Dict[str, Any]:
        return dict(self.state.get("projects_window", {}))

    def update_projects_window(self, **kwargs: Any) -> None:
        self.state.setdefault("projects_window", {}).update(kwargs)
        self.save()
