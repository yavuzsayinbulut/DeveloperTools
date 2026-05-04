from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

from .models import DiscoveredApp, RuntimeState, now_iso
from .state import HubState
from .utils import is_pid_running, is_url_reachable, terminate_pid


class AppManager:
    def __init__(self, state: HubState) -> None:
        self.state = state

    def get_runtime(self, app: DiscoveredApp) -> RuntimeState:
        runtime = self.state.get_runtime(app.key)
        if runtime.pid and not is_pid_running(runtime.pid):
            runtime.pid = None
            self.state.set_runtime(app.key, runtime)
        return runtime

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

    def start_app(self, app: DiscoveredApp) -> tuple[bool, str]:
        runtime = self.get_runtime(app)
        if runtime.pid and is_pid_running(runtime.pid):
            return True, "Uygulama zaten calisiyor."

        current_url = self.get_url(app)
        if app.app_type == "web" and current_url and is_url_reachable(current_url):
            return True, "Uygulama zaten URL uzerinden erisilebilir."

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
        if runtime.pid and is_pid_running(runtime.pid):
            if terminate_pid(runtime.pid):
                self.state.patch_runtime(app.key, pid=None)
                return True, "Durdurma sinyali gonderildi."

        if app.stop_script:
            try:
                subprocess.Popen(
                    ["/bin/zsh", "stop.command"],
                    cwd=app.path,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                self.state.patch_runtime(app.key, pid=None)
                return True, "Stop script calistirildi."
            except Exception as exc:
                return False, str(exc)

        return False, "Calisan surec bulunamadi."
