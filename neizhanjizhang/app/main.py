"""押金记账入口。同一份账本同时只允许打开一个窗口。"""

from __future__ import annotations

import sys
import traceback

import PySide6.QtSvg  # 打包时带上 SVG 插件，窗口图标和勾选标记才显示
from PySide6.QtCore import QLockFile
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.db import Database, default_db_path, install_dir
from app.license_client import (
    DEFAULT_SERVER_URL,
    LicenseConfig,
    LicenseSession,
    ensure_machine_id,
    load_config,
    login,
    save_config,
)
from app.ui import LoginDialog, MainWindow, app_icon, app_stylesheet


def _install_crash_log() -> None:
    if not getattr(sys, "frozen", False):
        return

    def hook(exc_type, exc, tb) -> None:
        log_path = install_dir() / "error.log"
        log_path.write_text(
            "".join(traceback.format_exception(exc_type, exc, tb)),
            encoding="utf-8",
        )

    sys.excepthook = hook


def main() -> int:
    _install_crash_log()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setApplicationName("押金记账")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(app_stylesheet())

    data_dir = default_db_path().parent
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str((data_dir / "app.lock").resolve()))
    lock.setStaleLockTime(3000)
    if not lock.tryLock(200):
        QMessageBox.warning(None, "押金记账", "程序已在运行，请先使用已经打开的窗口。")
        return 1

    config = ensure_machine_id(load_config())
    dialog = LoginDialog(config.server_url or DEFAULT_SERVER_URL, config.card)
    session: LicenseSession | None = None
    while session is None:
        if dialog.exec() != LoginDialog.DialogCode.Accepted:
            lock.unlock()
            return 0
        server_url, card = dialog.values()
        result = login(server_url, card, config.machine_id)
        if not result.ok:
            dialog.show_error(result.message)
            continue
        config = LicenseConfig(server_url=server_url, card=card, machine_id=config.machine_id)
        save_config(config)
        session = LicenseSession(server_url, card, config.machine_id, result.expires_at)

    database = Database(default_db_path())
    window = MainWindow(database)
    window.lock = lock
    window.resize(1100, 720)
    window.start_license_watch(session)
    window.show()
    code = app.exec()
    database.close()
    lock.unlock()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
