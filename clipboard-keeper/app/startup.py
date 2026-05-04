from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from .constants import APP_ID, LAUNCH_AGENT_PATH


class StartupManager:
    def __init__(self, main_script: Path) -> None:
        self.main_script = main_script.resolve()
        self.python_executable = Path(sys.executable).resolve()

    def is_enabled(self) -> bool:
        return LAUNCH_AGENT_PATH.exists()

    def enable(self) -> None:
        LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "Label": APP_ID,
            "ProgramArguments": [
                str(self.python_executable),
                str(self.main_script),
            ],
            "RunAtLoad": True,
            "KeepAlive": False,
            "WorkingDirectory": str(self.main_script.parent),
            "EnvironmentVariables": {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": str(self.main_script.parent),
            },
            "StandardOutPath": str(self.main_script.parent / "launchd.out.log"),
            "StandardErrorPath": str(self.main_script.parent / "launchd.err.log"),
        }
        with LAUNCH_AGENT_PATH.open("wb") as handle:
            plistlib.dump(payload, handle)

        uid = str(os.getuid())
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(LAUNCH_AGENT_PATH)],
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(LAUNCH_AGENT_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )

    def disable(self) -> None:
        if not LAUNCH_AGENT_PATH.exists():
            return
        uid = str(os.getuid())
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(LAUNCH_AGENT_PATH)],
            check=False,
            capture_output=True,
            text=True,
        )
        LAUNCH_AGENT_PATH.unlink(missing_ok=True)


def set_macos_activation_policy(hide_dock_icon: bool) -> None:
    if not hide_dock_icon:
        return

    try:
        from AppKit import (
            NSApplication,
            NSApplicationActivationPolicyAccessory,
        )
    except Exception:
        return

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
