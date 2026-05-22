from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

import re

from .models import DiscoveredApp, RuntimeState, now_iso
from .state import HubState
from .utils import (
    find_pids_by_path,
    find_pids_by_port,
    is_pid_running,
    is_url_reachable,
    terminate_pid,
)


_PORT_RE = re.compile(r":(\d{2,5})(?:[/?#]|$)")


def _port_from_url(url: str) -> int | None:
    if not url:
        return None
    match = _PORT_RE.search(url)
    if not match:
        return None
    value = int(match.group(1))
    if 0 < value <= 65535:
        return value
    return None


class AppManager:
    def __init__(self, state: HubState) -> None:
        self.state = state

    def get_runtime(self, app: DiscoveredApp) -> RuntimeState:
        runtime = self.state.get_runtime(app.key)
        if runtime.pid and not is_pid_running(runtime.pid):
            runtime.pid = None
            self.state.set_runtime(app.key, runtime)
        if not runtime.pid:
            adopted = self._adopt_external_pid(app, runtime)
            if adopted:
                runtime = self.state.get_runtime(app.key)
        return runtime

    def _adopt_external_pid(self, app: DiscoveredApp, runtime: RuntimeState) -> bool:
        url = runtime.url_override.strip() or app.default_url.strip()
        port = _port_from_url(url)
        if port and is_url_reachable(url):
            pids = find_pids_by_port(port)
            if pids:
                self.state.patch_runtime(app.key, pid=pids[0])
                return True

        pids = find_pids_by_path(app.path)
        if pids:
            self.state.patch_runtime(app.key, pid=pids[0])
            return True
        return False

    def get_url(self, app: DiscoveredApp) -> str:
        runtime = self.get_runtime(app)
        return runtime.url_override.strip() or app.default_url.strip()

    def set_url_override(self, app: DiscoveredApp, url: str) -> None:
        self.state.patch_runtime(app.key, url_override=url.strip())

    def wait_until_ready(self, app: DiscoveredApp, timeout_seconds: float = 10.0) -> bool:
        url = self.get_url(app)
        if app.app_type != "web" or not url:
            return True

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if is_url_reachable(url):
                return True
            time.sleep(0.4)
        return False

    def is_app_running(self, app: DiscoveredApp) -> bool:
        runtime = self.get_runtime(app)
        if runtime.pid and is_pid_running(runtime.pid):
            return True
        url = runtime.url_override.strip() or app.default_url.strip()
        if app.app_type == "web" and url and is_url_reachable(url):
            return True
        if find_pids_by_path(app.path):
            return True
        return False

    def start_app(self, app: DiscoveredApp) -> tuple[bool, str]:
        runtime = self.get_runtime(app)
        if runtime.pid and is_pid_running(runtime.pid):
            return True, "Uygulama zaten calisiyor."

        current_url = self.get_url(app)
        if app.app_type == "web" and current_url and is_url_reachable(current_url):
            return True, "Uygulama zaten URL uzerinden erisilebilir."

        external_pids = find_pids_by_path(app.path)
        if external_pids:
            self.state.patch_runtime(app.key, pid=external_pids[0])
            return True, f"Uygulama zaten calisiyor (PID {external_pids[0]})."

        if not app.start_command:
            return False, "Bu uygulama icin otomatik start komutu bulunamadi."

        app_dir = Path(app.path)
        log_dir = app_dir / ".hub_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_log = log_dir / "stdout.log"
        stderr_log = log_dir / "stderr.log"

        stdout_handle = stdout_log.open("ab")
        stderr_handle = stderr_log.open("ab")

        try:
            process = subprocess.Popen(
                app.start_command,
                cwd=app.path,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                start_new_session=True,
            )
        except Exception as exc:
            stdout_handle.close()
            stderr_handle.close()
            self.state.patch_runtime(app.key, last_error=str(exc))
            return False, str(exc)

        self.state.set_runtime(
            app.key,
            RuntimeState(
                url_override=runtime.url_override,
                pid=process.pid,
                started_at=now_iso(),
                stdout_log=str(stdout_log),
                stderr_log=str(stderr_log),
                last_error="",
            ),
        )

        return True, "Baslatildi."

    def stop_app(self, app: DiscoveredApp) -> tuple[bool, str]:
        runtime = self.get_runtime(app)
        if app.stop_script:
            ok, message = self._run_stop_script(app, runtime)
            if ok:
                return ok, message

        if runtime.pid and is_pid_running(runtime.pid):
            if terminate_pid(runtime.pid):
                self.state.patch_runtime(app.key, pid=None)
                return True, "Durdurma sinyali gonderildi."

        return False, "Calisan surec bulunamadi."

    def _run_stop_script(
        self,
        app: DiscoveredApp,
        runtime: RuntimeState,
    ) -> tuple[bool, str]:
        try:
            subprocess.run(
                ["/bin/zsh", "stop.command"],
                cwd=app.path,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                timeout=6,
                check=False,
            )
        except Exception as exc:
            return False, str(exc)

        if runtime.pid:
            deadline = time.time() + 3.0
            while time.time() < deadline:
                if not is_pid_running(runtime.pid):
                    self.state.patch_runtime(app.key, pid=None)
                    return True, "Stop script calistirildi."
                time.sleep(0.15)

        self.state.patch_runtime(app.key, pid=None)
        return True, "Stop script calistirildi."

    def restart_app(self, app: DiscoveredApp) -> tuple[bool, str]:
        stop_ok, stop_message = self.stop_app(app)
        if not stop_ok and "Calisan surec bulunamadi" not in stop_message:
            return False, stop_message

        deadline = time.time() + 4.0
        while time.time() < deadline:
            runtime = self.get_runtime(app)
            if not (runtime.pid and is_pid_running(runtime.pid)):
                break
            time.sleep(0.2)

        time.sleep(0.3)
        start_ok, start_message = self.start_app(app)
        if start_ok:
            return True, "Uygulama yeniden baslatildi."
        return False, start_message

    def open_terminal(self, app: DiscoveredApp) -> tuple[bool, str]:
        try:
            subprocess.Popen(
                ["open", "-a", "Terminal", app.path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True, "Terminal acildi."
        except Exception as exc:
            return False, str(exc)

    def health_check(self, app: DiscoveredApp) -> dict[str, object]:
        runtime = self.get_runtime(app)
        resolved_url = self.get_url(app)
        running = bool(runtime.pid and is_pid_running(runtime.pid))
        reachable = bool(resolved_url and is_url_reachable(resolved_url))

        return {
            "name": app.name,
            "path": app.path,
            "type": app.app_type,
            "start_mode": app.start_mode,
            "running": running,
            "pid": runtime.pid,
            "started_at": runtime.started_at,
            "url": resolved_url,
            "url_reachable": reachable,
            "stdout_log": runtime.stdout_log,
            "stderr_log": runtime.stderr_log,
            "stop_script": app.stop_script,
            "readme_path": app.readme_path,
            "last_error": runtime.last_error,
        }
