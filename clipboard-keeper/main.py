from __future__ import annotations

import signal
import sys

from PySide6.QtWidgets import QApplication

from app.constants import APP_ID, APP_NAME, ROOT_DIR
from app.clipboard_monitor import ClipboardMonitor
from app.startup import StartupManager, set_macos_activation_policy
from app.storage import StateStore
from app.ui import MainWindow


def _detach_from_terminal() -> None:
    if hasattr(signal, "SIGHUP"):
        try:
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
        except (OSError, ValueError):
            pass


def main() -> int:
    _detach_from_terminal()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setQuitOnLastWindowClosed(False)

    store = StateStore()
    settings = store.get_settings()
    set_macos_activation_policy(settings.hide_dock_icon)

    startup_manager = StartupManager(ROOT_DIR / "main.py")
    window = MainWindow(store, startup_manager)
    monitor = ClipboardMonitor()
    window.attach_monitor(monitor)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
