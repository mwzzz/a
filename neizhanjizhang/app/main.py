"""押金记账入口。同一份账本同时只允许打开一个窗口。"""

from __future__ import annotations

import sys

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.db import Database, default_db_path
from app.ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setApplicationName("押金记账")

    data_dir = default_db_path().parent
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str((data_dir / "app.lock").resolve()))
    lock.setStaleLockTime(3000)
    if not lock.tryLock(200):
        QMessageBox.warning(None, "押金记账", "程序已在运行，请先使用已经打开的窗口。")
        return 1

    database = Database(default_db_path())
    window = MainWindow(database)
    window.lock = lock
    window.resize(1100, 720)
    window.show()
    code = app.exec()
    database.close()
    lock.unlock()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
