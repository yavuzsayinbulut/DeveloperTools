from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.constants import APP_NAME
from app.manager import AppManager
from app.state import HubState
from app.ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    state = HubState()
    manager = AppManager(state)
    window = MainWindow(state, manager)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
