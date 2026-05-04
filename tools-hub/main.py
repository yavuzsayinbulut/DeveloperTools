from __future__ import annotations

import signal
import sys

from PySide6.QtWidgets import QApplication

from app.constants import APP_NAME
from app.manager import AppManager
from app.state import HubState
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
    app.setQuitOnLastWindowClosed(False)

    state = HubState()
    manager = AppManager(state)
    window = MainWindow(state, manager)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
