"""python -m castmane / castmane komutu girisi."""
from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .app import MainWindow
    from .config import AppConfig

    app = QApplication(sys.argv)
    app.setApplicationName("CastMane")
    win = MainWindow(AppConfig())
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
