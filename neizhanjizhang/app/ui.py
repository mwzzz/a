"""玩家库、开一局、押金记录和交班四个页面。"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.db import Database
from app.license_client import (
    DEFAULT_SERVER_URL,
    HEARTBEAT_INTERVAL_MS,
    LicenseSession,
    note_heartbeat,
)
from app.services import (
    AppError,
    add_deposit,
    create_player,
    delete_player,
    format_change,
    format_yuan,
    get_player,
    get_last_tea_cents,
    list_ledger,
    list_players,
    list_session_players,
    normalize_game_id,
    open_session,
    parse_yuan,
    preview_session,
    refund,
    set_last_tea_cents,
    export_player_workbook,
    import_players,
    transfer,
    update_remark,
)

COLOR_TEXT = QColor("#1E2422")
COLOR_OK = QColor("#1F6B4A")
COLOR_BAD = QColor("#9C3B32")
MONEY_ALIGN = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
TEXT_ALIGN = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def icon_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "app" / "assets" / "icon.svg"
    return Path(__file__).resolve().parent / "assets" / "icon.svg"


def app_icon() -> QIcon:
    return QIcon(str(icon_path()))


def app_stylesheet() -> str:
    check_icon = (icon_path().parent / "check.svg").as_posix()
    chevron_icon = (icon_path().parent / "chevron.svg").as_posix()
    return f"""
    QMainWindow, QDialog, QMessageBox {{
        background: #F3EFE6;
        color: #1E2422;
        font-family: "Microsoft YaHei UI";
        font-size: 13px;
    }}
    QWidget#shell {{
        background: #F3EFE6;
    }}
    QWidget#page {{
        background: transparent;
    }}
    QLabel#appTitle {{
        color: #14352C;
        font-size: 20px;
        font-weight: 700;
    }}
    QLabel#appHint, QLabel#subtitle {{
        color: #6E665C;
    }}
    QLabel#warn {{
        color: #7A4E32;
    }}
    QLabel#result {{
        color: #3E4A45;
    }}
    QLabel#summary {{
        background: #F6F1E7;
        color: #14352C;
        border: 1px solid #E4D9C8;
        border-radius: 10px;
        padding: 8px 12px;
        font-weight: 600;
    }}
    QLabel#selectedCount {{
        color: #14352C;
        font-weight: 600;
        padding: 0 8px;
    }}
    QFrame#totalCard {{
        background: #14352C;
        border-radius: 12px;
    }}
    QLabel#totalCaption {{
        color: #D5E0D8;
        font-size: 11px;
        background: transparent;
    }}
    QLabel#totalAmount {{
        color: #F6EDD8;
        font-size: 18px;
        font-weight: 700;
        background: transparent;
    }}
    QTabWidget::pane {{
        background: #FFFCF6;
        border: 1px solid #E3D9C8;
        border-radius: 14px;
        top: 8px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: #6E665C;
        padding: 8px 18px;
        margin-right: 6px;
        border-radius: 9px;
        min-width: 72px;
    }}
    QTabBar::tab:selected {{
        background: #14352C;
        color: #F6EDD8;
    }}
    QTabBar::tab:hover:!selected {{
        background: #E7E0D2;
        color: #1E2422;
    }}
    QTableWidget {{
        background: #FFFCF6;
        alternate-background-color: #F7F4EE;
        color: #1E2422;
        border: 1px solid #E3D9C8;
        border-radius: 10px;
        gridline-color: transparent;
        selection-background-color: #E3EFE8;
        selection-color: #1E2422;
    }}
    QTableWidget::item {{
        border-bottom: 1px solid #EFE8DC;
        padding: 2px 8px;
    }}
    QTableWidget::item:selected {{
        background: #E3EFE8;
        color: #1E2422;
    }}
    QHeaderView::section {{
        background: #F6F1E7;
        color: #5E574E;
        font-weight: 600;
        border: none;
        border-bottom: 1px solid #E3D9C8;
        padding: 8px 10px;
    }}
    QLineEdit, QComboBox {{
        background: #FFFCF6;
        color: #1E2422;
        border: 1px solid #D9D0C2;
        border-radius: 8px;
        padding: 6px 8px;
        min-height: 28px;
        selection-background-color: #D5E6DC;
    }}
    QComboBox {{
        padding-right: 36px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid #14352C;
    }}
    QComboBox QLineEdit {{
        border: none;
        background: transparent;
        padding: 0 4px;
        min-height: 0;
        selection-background-color: #D5E6DC;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 36px;
        border: none;
        border-left: 1px solid #C9BFAE;
        background: #E7EFE9;
        border-top-right-radius: 8px;
        border-bottom-right-radius: 8px;
    }}
    QComboBox::drop-down:hover {{
        background: #D5E6DC;
    }}
    QComboBox::down-arrow {{
        image: url("{chevron_icon}");
        width: 14px;
        height: 14px;
    }}
    QPushButton {{
        background: #FFFCF6;
        color: #1E2422;
        border: 1px solid #D4CBBC;
        border-radius: 8px;
        padding: 6px 14px;
        min-height: 24px;
    }}
    QPushButton:hover {{
        background: #F6F1E7;
    }}
    QPushButton:pressed {{
        background: #EBE4D6;
    }}
    QPushButton:disabled {{
        color: #A8A093;
        background: #F4F0E8;
        border-color: #E4DDD2;
    }}
    QPushButton[role="primary"] {{
        background: #14352C;
        color: #F6EDD8;
        border: 1px solid #14352C;
    }}
    QPushButton[role="primary"]:hover {{
        background: #1C4A3E;
    }}
    QPushButton[role="primary"]:pressed {{
        background: #0E261F;
    }}
    QPushButton[role="primary"]:disabled {{
        background: #8AA097;
        color: #F6EDD8;
        border-color: #8AA097;
    }}
    QPushButton[role="danger"] {{
        background: #FFFCF6;
        color: #9C3B32;
        border: 1px solid #E4C4BE;
    }}
    QPushButton[role="danger"]:hover {{
        background: #F8ECEA;
    }}
    QCheckBox {{
        spacing: 6px;
        color: #1E2422;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid #C9BFAE;
        border-radius: 4px;
        background: #FFFCF6;
    }}
    QCheckBox::indicator:checked {{
        background: #14352C;
        border-color: #14352C;
        image: url("{check_icon}");
    }}
    QGroupBox {{
        background: #FFFCF6;
        border: 1px solid #E3D9C8;
        border-radius: 12px;
        margin-top: 16px;
        padding: 18px 14px 14px 14px;
        font-weight: 600;
        color: #14352C;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 6px;
    }}
    QStatusBar {{
        background: #14352C;
        color: #F4EFE4;
    }}
    QStatusBar QLabel {{
        color: #F4EFE4;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #D4CBBC;
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    """


def set_role(widget: QWidget, role: str) -> None:
    widget.setProperty("role", role)


def subtitle(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("subtitle")
    label.setWordWrap(True)
    return label


def run_action(parent: QWidget, action) -> bool:
    try:
        action()
    except AppError as exc:
        QMessageBox.warning(parent, "无法完成", str(exc))
        return False
    except sqlite3.IntegrityError:
        QMessageBox.warning(parent, "无法完成", "这笔操作未能写入，请检查余额和玩家是否有效")
        return False
    return True


def readonly_item(text: str, align: Qt.AlignmentFlag = TEXT_ALIGN) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    item.setTextAlignment(align)
    return item


def configure_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(38)
    table.setWordWrap(False)


def player_label(player: dict) -> str:
    return player["game_id"]


class PlayerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("新增玩家")
        self.setMinimumWidth(360)
        self.game_id_edit = QLineEdit()
        self.remark_edit = QLineEdit()
        self.remark_edit.setPlaceholderText("可选")
        form = QFormLayout(self)
        form.setContentsMargins(22, 18, 22, 16)
        form.setSpacing(12)
        form.addRow("游戏 id", self.game_id_edit)
        form.addRow("备注", self.remark_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("确定")
        set_role(ok_button, "primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.game_id = ""
        self.remark = ""

    def _accept(self) -> None:
        try:
            self.game_id = normalize_game_id(self.game_id_edit.text())
            self.remark = self.remark_edit.text()
        except AppError as exc:
            QMessageBox.warning(self, "无法完成", str(exc))
            return
        self.accept()


class ImportPlayersDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("批量导入玩家")
        self.setWindowIcon(app_icon())
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)
        layout.addWidget(
            subtitle("每行一个玩家。只写游戏 id，或写成「游戏 id,备注」。已存在的游戏 id 会跳过，不会改动原来的押金。")
        )
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("东子\n执笔,常客")
        layout.addWidget(self.editor)
        file_row = QHBoxLayout()
        file_button = QPushButton("从文件读入…")
        file_button.clicked.connect(self._load_file)
        file_row.addWidget(file_button)
        file_row.addStretch(1)
        layout.addLayout(file_row)
        self.error_label = QLabel("")
        self.error_label.setObjectName("warn")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        confirm = QPushButton("导入")
        set_role(confirm, "primary")
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

    def text(self) -> str:
        return self.editor.toPlainText()

    def _load_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self, "选择玩家名单", str(Path.home()), "文本 (*.txt *.csv)"
        )
        if not path:
            return
        data = Path(path).read_bytes()
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "gbk"):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if not text and data:
            self.error_label.setText("无法读取这个文件，请用 UTF-8 或 GBK 保存。")
            return
        self.editor.setPlainText(text)
        self.error_label.setText("")

    def _accept(self) -> None:
        if not self.editor.toPlainText().strip():
            self.error_label.setText("请先填写要导入的玩家。")
            return
        self.accept()


class AmountDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, targets: list[dict] | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.cents = 0
        self.note_text = ""
        self.target_id = ""
        form = QFormLayout(self)
        form.setContentsMargins(22, 18, 22, 16)
        form.setSpacing(12)
        self.target_combo: QComboBox | None = None
        if targets is not None:
            self.target_combo = QComboBox()
            for player in targets:
                self.target_combo.addItem(player_label(player), player["game_id"])
            form.addRow("对方", self.target_combo)
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("可选")
        form.addRow("金额（元）", self.amount_edit)
        form.addRow("备注", self.note_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("确定")
        set_role(ok_button, "primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _accept(self) -> None:
        try:
            cents = parse_yuan(self.amount_edit.text())
            if cents <= 0:
                raise AppError("金额必须大于 0")
            note = self.note_edit.text()
        except AppError as exc:
            QMessageBox.warning(self, "无法完成", str(exc))
            return
        self.cents = cents
        self.note_text = note
        if self.target_combo is not None:
            self.target_id = str(self.target_combo.currentData() or "")
            if not self.target_id:
                QMessageBox.warning(self, "无法完成", "请选择对方玩家")
                return
        self.accept()


class PlayersPage(QWidget):
    open_player = Signal(str)

    def __init__(self, database: Database, on_changed):
        super().__init__()
        self.setObjectName("page")
        self.db = database
        self.on_changed = on_changed
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(subtitle("每个玩家用游戏 id 识别。押金是还在管理员这里的余额。双击一行可查看流水。"))
        buttons = QHBoxLayout()
        add_button = QPushButton("新增玩家")
        import_button = QPushButton("批量导入")
        remark_button = QPushButton("修改备注")
        delete_button = QPushButton("删除")
        set_role(add_button, "primary")
        set_role(delete_button, "danger")
        add_button.clicked.connect(self.add_player)
        import_button.clicked.connect(self.import_players)
        remark_button.clicked.connect(self.edit_remark)
        delete_button.clicked.connect(self.remove_player)
        buttons.addWidget(add_button)
        buttons.addWidget(import_button)
        buttons.addWidget(remark_button)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        card = QFrame()
        card.setObjectName("totalCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 8, 16, 8)
        card_layout.setSpacing(0)
        caption = QLabel("总押金")
        caption.setObjectName("totalCaption")
        self.total_label = QLabel("0.00 元")
        self.total_label.setObjectName("totalAmount")
        card_layout.addWidget(caption)
        card_layout.addWidget(self.total_label)
        buttons.addWidget(card)
        layout.addLayout(buttons)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["序号", "游戏 id", "押金", "总局数", "备注"])
        configure_table(self.table)
        self.table.cellDoubleClicked.connect(self._open_selected)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def reload(self) -> None:
        selected = self.selected_game_id()
        players = list_players(self.db.conn)
        total_cents = sum(int(player["deposit_cents"]) for player in players)
        self.total_label.setText(f"{format_yuan(total_cents)} 元")
        self.table.setRowCount(len(players))
        for row, player in enumerate(players):
            self.table.setItem(row, 0, readonly_item(str(row + 1), MONEY_ALIGN))
            self.table.setItem(row, 1, readonly_item(player["game_id"]))
            deposit = readonly_item(format_yuan(player["deposit_cents"]), MONEY_ALIGN)
            if int(player["deposit_cents"]) < 0:
                deposit.setForeground(QBrush(COLOR_BAD))
            self.table.setItem(row, 2, deposit)
            games = readonly_item(str(player["games_played"]), MONEY_ALIGN)
            self.table.setItem(row, 3, games)
            self.table.setItem(row, 4, readonly_item(player.get("remark") or ""))
            if player["game_id"] == selected:
                self.table.selectRow(row)

    def selected_game_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)
        return item.text() if item else None

    def _require_selected(self) -> str | None:
        game_id = self.selected_game_id()
        if not game_id:
            QMessageBox.warning(self, "无法完成", "请先选择玩家")
            return None
        return game_id

    def add_player(self) -> None:
        dialog = PlayerDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        def action() -> None:
            create_player(self.db.conn, dialog.game_id, remark=dialog.remark)

        if run_action(self, action):
            self.on_changed()
            self._select(dialog.game_id)

    def import_players(self) -> None:
        dialog = ImportPlayersDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = import_players(self.db.conn, dialog.text())
        created = result["created"]
        skipped = result["skipped"]
        errors = result["errors"]
        if created:
            self.on_changed()
        lines = [f"新导入 {len(created)} 人。"]
        if skipped:
            lines.append("已存在并跳过：" + "、".join(skipped))
        if errors:
            lines.extend(errors)
        QMessageBox.information(self, "批量导入", "\n".join(lines))

    def edit_remark(self) -> None:
        game_id = self._require_selected()
        if not game_id:
            return
        player = get_player(self.db.conn, game_id)
        current = "" if player is None else str(player.get("remark") or "")
        text, ok = QInputDialog.getText(self, "修改备注", "备注", text=current)
        if not ok:
            return

        def action() -> None:
            update_remark(self.db.conn, game_id, text)

        if run_action(self, action):
            self.on_changed()
            self._select(game_id)

    def remove_player(self) -> None:
        game_id = self._require_selected()
        if not game_id:
            return
        answer = QMessageBox.question(
            self,
            "删除玩家",
            f"确定删除玩家 {game_id}？\n只有押金为 0 才能删除。删除后，这个玩家自己的流水也会去掉。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def action() -> None:
            delete_player(self.db.conn, game_id)

        if run_action(self, action):
            self.on_changed()

    def _select(self, game_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item and item.text() == game_id:
                self.table.selectRow(row)
                return

    def _open_selected(self, row: int, _column: int) -> None:
        item = self.table.item(row, 1)
        if item:
            self.open_player.emit(item.text())


class SessionPage(QWidget):
    def __init__(self, database: Database, on_changed):
        super().__init__()
        self.setObjectName("page")
        self.db = database
        self.on_changed = on_changed
        self._refreshing = False
        self._reset_checks = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(subtitle("勾选本局玩家，按茶水批量正常扣押，每人总局数加 1。余额不够也可以开局，扣完后的押金记为负数。最近扣过茶水的玩家排在前面。"))
        form = QHBoxLayout()
        form.addWidget(QLabel("本局茶水（元）"))
        self.tea_edit = QLineEdit()
        self.tea_edit.setMaximumWidth(140)
        self.tea_edit.textChanged.connect(self.refresh_amounts)
        self.tea_edit.editingFinished.connect(self.save_tea)
        form.addWidget(self.tea_edit)
        form.addWidget(QLabel("备注"))
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("可选，例如晚场")
        form.addWidget(self.note_edit, 1)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        select_first = QPushButton("选前10个")
        self.selected_label = QLabel("已选 0 人")
        self.selected_label.setObjectName("selectedCount")
        self.confirm_button = QPushButton("确认开局")
        set_role(self.confirm_button, "primary")
        select_first.clicked.connect(self._toggle_first)
        self.confirm_button.clicked.connect(self.confirm)
        buttons.addWidget(select_first)
        buttons.addWidget(self.selected_label)
        buttons.addStretch(1)
        buttons.addWidget(self.confirm_button)
        layout.addLayout(buttons)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["选择", "游戏 id", "当前押金", "本局扣除", "扣后押金", "状态"]
        )
        configure_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 72)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self.load_tea()

    def load_tea(self) -> None:
        self.tea_edit.setText(format_yuan(get_last_tea_cents(self.db.conn)))

    def save_tea(self) -> None:
        try:
            cents = parse_yuan(self.tea_edit.text())
        except AppError:
            return
        set_last_tea_cents(self.db.conn, cents)

    def reload(self) -> None:
        selected = set() if self._reset_checks else set(self.selected_ids())
        self._reset_checks = False
        players = list_session_players(self.db.conn)
        self.table.blockSignals(True)
        self.table.setRowCount(len(players))
        for row, player in enumerate(players):
            holder = QWidget()
            holder.setStyleSheet("background: transparent;")
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            check = QCheckBox()
            check.setProperty("game_id", player["game_id"])
            check.setChecked(player["game_id"] in selected)
            check.toggled.connect(self.refresh_amounts)
            holder_layout.addWidget(check)
            self.table.setCellWidget(row, 0, holder)
            self.table.setItem(row, 1, readonly_item(player["game_id"]))
            deposit = readonly_item(format_yuan(player["deposit_cents"]), MONEY_ALIGN)
            deposit.setData(Qt.ItemDataRole.UserRole, int(player["deposit_cents"]))
            self.table.setItem(row, 2, deposit)
            self.table.setItem(row, 3, readonly_item("—", MONEY_ALIGN))
            self.table.setItem(row, 4, readonly_item("—", MONEY_ALIGN))
            self.table.setItem(row, 5, readonly_item(""))
        self.table.blockSignals(False)
        self.refresh_amounts()

    def _check_box(self, row: int) -> QCheckBox | None:
        widget = self.table.cellWidget(row, 0)
        if widget is None:
            return None
        return widget.findChild(QCheckBox)

    def selected_ids(self) -> list[str]:
        ids: list[str] = []
        for row in range(self.table.rowCount()):
            box = self._check_box(row)
            if box and box.isChecked():
                ids.append(str(box.property("game_id")))
        return ids

    def _toggle_first(self) -> None:
        count = min(10, self.table.rowCount())
        already = count > 0 and all(
            (box := self._check_box(row)) is not None and box.isChecked()
            for row in range(count)
        ) and all(
            (box := self._check_box(row)) is not None and not box.isChecked()
            for row in range(count, self.table.rowCount())
        )
        for row in range(self.table.rowCount()):
            box = self._check_box(row)
            if box is None:
                continue
            box.blockSignals(True)
            box.setChecked((not already) and row < count)
            box.blockSignals(False)
        self.refresh_amounts()

    def refresh_amounts(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self.table.blockSignals(True)
        try:
            tea, error = self._parse_tea()
            for row in range(self.table.rowCount()):
                check = self._check_box(row)
                deposit_item = self.table.item(row, 2)
                deduct_item = self.table.item(row, 3)
                after_item = self.table.item(row, 4)
                status_item = self.table.item(row, 5)
                if check is None or not deposit_item or not deduct_item or not after_item or not status_item:
                    continue
                if not check.isChecked():
                    deduct_item.setText("—")
                    after_item.setText("—")
                    after_item.setForeground(QBrush(COLOR_TEXT))
                    status_item.setText("")
                    status_item.setForeground(QBrush(COLOR_TEXT))
                    continue
                if tea is None:
                    deduct_item.setText("—")
                    after_item.setText("—")
                    status_item.setText(error or "金额有误")
                    status_item.setForeground(QBrush(COLOR_BAD))
                    continue
                before = int(deposit_item.data(Qt.ItemDataRole.UserRole))
                after = before - tea
                deduct_item.setText(format_yuan(tea))
                after_item.setText(format_yuan(after))
                if after < 0:
                    after_item.setForeground(QBrush(COLOR_BAD))
                    status_item.setText("记为负数")
                    status_item.setForeground(QBrush(COLOR_BAD))
                else:
                    after_item.setForeground(QBrush(COLOR_TEXT))
                    status_item.setText("可以扣")
                    status_item.setForeground(QBrush(COLOR_OK))
        finally:
            self.table.blockSignals(False)
            self._refreshing = False
            self.selected_label.setText(f"已选 {len(self.selected_ids())} 人")

    def _parse_tea(self) -> tuple[int | None, str | None]:
        try:
            return parse_yuan(self.tea_edit.text()), None
        except AppError as exc:
            return None, str(exc)

    def confirm(self) -> None:
        tea, error = self._parse_tea()
        if tea is None:
            QMessageBox.warning(self, "无法完成", error or "请输入茶水")
            return
        ids = self.selected_ids()
        if not ids:
            QMessageBox.warning(self, "无法完成", "请勾选本局玩家")
            return
        try:
            preview = preview_session(self.db.conn, ids, tea)
        except AppError as exc:
            QMessageBox.warning(self, "无法完成", str(exc))
            return
        negative = [row["game_id"] for row in preview if row["after"] < 0]
        message = f"确认为 {len(preview)} 名玩家开局？\n每人正常扣押 {format_yuan(tea)} 元，总局数各加 1。"
        if negative:
            message += "\n以下玩家扣完后押金为负数：" + "、".join(negative)
        answer = QMessageBox.question(
            self,
            "确认开局",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        note = self.note_edit.text()
        session_id: dict[str, int] = {}

        def action() -> None:
            session_id["id"] = open_session(self.db.conn, ids, tea, note)

        self.confirm_button.setEnabled(False)
        try:
            saved = run_action(self, action)
        finally:
            self.confirm_button.setEnabled(True)
        if not saved:
            return
        self._reset_checks = True
        self.note_edit.clear()
        self.on_changed()
        QMessageBox.information(self, "已开局", f"本局已记下，局号 {session_id['id']}。")


class LedgerPage(QWidget):
    def __init__(self, database: Database, on_changed):
        super().__init__()
        self.setObjectName("page")
        self.db = database
        self.on_changed = on_changed
        self._game_id = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(subtitle("从玩家库选择游戏 id，或输入游戏 id 查询。最新的记录在最上面。"))
        query_row = QHBoxLayout()
        query_row.addWidget(QLabel("游戏 id"))
        self.player_combo = QComboBox()
        self.player_combo.setEditable(True)
        self.player_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.player_combo.setMinimumWidth(280)
        query_button = QPushButton("查询")
        set_role(query_button, "primary")
        query_button.clicked.connect(self.query)
        self.player_combo.activated.connect(self._on_player_picked)
        query_row.addWidget(self.player_combo, 1)
        query_row.addWidget(query_button)
        layout.addLayout(query_row)
        self.summary = QLabel("请查询一个游戏 id")
        self.summary.setObjectName("summary")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        self.add_button = QPushButton("加押金")
        self.refund_button = QPushButton("退押金")
        self.transfer_button = QPushButton("划给其他人")
        set_role(self.add_button, "primary")
        self.add_button.clicked.connect(self.add_money)
        self.refund_button.clicked.connect(self.refund_money)
        self.transfer_button.clicked.connect(self.transfer_money)
        actions.addWidget(self.add_button)
        actions.addWidget(self.refund_button)
        actions.addWidget(self.transfer_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self._set_actions_enabled(False)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["时间", "原因", "变动金额", "当时押金", "操作后押金", "对方", "局号", "备注"]
        )
        configure_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 3, 4, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        line_edit = self.player_combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("输入或选择游戏 id")
            line_edit.returnPressed.connect(self.query)

    def reload(self) -> None:
        current_text = self.player_combo.currentText()
        players = list_players(self.db.conn)
        self.player_combo.blockSignals(True)
        self.player_combo.clear()
        for player in players:
            self.player_combo.addItem(player["game_id"], player["game_id"])
        self.player_combo.setCurrentText(current_text)
        self.player_combo.blockSignals(False)
        if self._game_id:
            self._load_player(self._game_id, quiet=True)

    def _on_player_picked(self, index: int) -> None:
        game_id = str(self.player_combo.itemData(index) or "")
        if game_id:
            self._load_player(game_id, quiet=False)

    def show_player(self, game_id: str) -> None:
        self.player_combo.blockSignals(True)
        index = self.player_combo.findData(game_id)
        if index >= 0:
            self.player_combo.setCurrentIndex(index)
        else:
            self.player_combo.setCurrentText(game_id)
        self.player_combo.blockSignals(False)
        self._load_player(game_id, quiet=False)

    def query(self) -> None:
        game_id = self.player_combo.currentText().strip()
        if not game_id or game_id == "输入或选择游戏 id":
            QMessageBox.warning(self, "无法完成", "请输入或选择游戏 id")
            return
        self._load_player(game_id, quiet=False)

    def _load_player(self, game_id: str, quiet: bool) -> None:
        player = get_player(self.db.conn, game_id)
        if player is None:
            self._game_id = ""
            self.table.setRowCount(0)
            self.summary.setText("没有这个玩家")
            self._set_actions_enabled(False)
            if not quiet:
                QMessageBox.warning(self, "无法完成", f"找不到玩家：{game_id}")
            return
        self._game_id = player["game_id"]
        self.summary.setText(
            f"当前押金 {format_yuan(player['deposit_cents'])} 元    总局数 {player['games_played']}"
        )
        self._set_actions_enabled(True)
        rows = list_ledger(self.db.conn, player["game_id"])
        self.table.setRowCount(len(rows))
        for index, entry in enumerate(rows):
            self.table.setItem(index, 0, readonly_item(entry["created_at"]))
            self.table.setItem(index, 1, readonly_item(entry["reason_label"]))
            change = readonly_item(format_change(entry["signed_amount_cents"]), MONEY_ALIGN)
            if entry["signed_amount_cents"] > 0:
                change.setForeground(QBrush(COLOR_OK))
            elif entry["signed_amount_cents"] < 0:
                change.setForeground(QBrush(COLOR_BAD))
            self.table.setItem(index, 2, change)
            self.table.setItem(
                index, 3, readonly_item(format_yuan(entry["balance_before_cents"]), MONEY_ALIGN)
            )
            self.table.setItem(
                index, 4, readonly_item(format_yuan(entry["balance_after_cents"]), MONEY_ALIGN)
            )
            self.table.setItem(index, 5, readonly_item(entry["counterparty_game_id"] or ""))
            session_text = "" if entry["session_id"] is None else str(entry["session_id"])
            self.table.setItem(index, 6, readonly_item(session_text, MONEY_ALIGN))
            self.table.setItem(index, 7, readonly_item(entry["note"]))

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.add_button.setEnabled(enabled)
        self.refund_button.setEnabled(enabled)
        self.transfer_button.setEnabled(enabled)

    def _target_game_id(self) -> str | None:
        typed = self.player_combo.currentText().strip()
        if typed and typed != "输入或选择游戏 id":
            if typed != self._game_id:
                self._load_player(typed, quiet=False)
            return self._game_id or None
        if not self._game_id:
            QMessageBox.warning(self, "无法完成", "请先查询一个玩家")
            return None
        return self._game_id

    def add_money(self) -> None:
        game_id = self._target_game_id()
        if not game_id:
            return
        dialog = AmountDialog(self, "加押金")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        def action() -> None:
            add_deposit(self.db.conn, game_id, dialog.cents, dialog.note_text)

        if run_action(self, action):
            self.on_changed()

    def refund_money(self) -> None:
        game_id = self._target_game_id()
        if not game_id:
            return
        dialog = AmountDialog(self, "退押金")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        def action() -> None:
            refund(self.db.conn, game_id, dialog.cents, dialog.note_text)

        if run_action(self, action):
            self.on_changed()

    def transfer_money(self) -> None:
        game_id = self._target_game_id()
        if not game_id:
            return
        targets = [player for player in list_players(self.db.conn) if player["game_id"] != game_id]
        if not targets:
            QMessageBox.warning(self, "无法完成", "没有其他玩家可以划入")
            return
        dialog = AmountDialog(self, "划给其他人押金", targets)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        def action() -> None:
            transfer(self.db.conn, game_id, dialog.target_id, dialog.cents, dialog.note_text)

        if run_action(self, action):
            self.on_changed()


class HandoverPage(QWidget):
    def __init__(self, database: Database, on_changed):
        super().__init__()
        self.setObjectName("page")
        self.db = database
        self.on_changed = on_changed
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(
            subtitle(
                "交接班时导出整个账本文件，交给下一位管理员导入。"
                "请使用这里导出的文件，不要直接拷贝正在使用的 deposit.db。"
            )
        )

        file_box = QGroupBox("交接账本")
        file_layout = QVBoxLayout(file_box)
        warn = QLabel("导入会覆盖这台电脑上的当前账本。导入前会自动把当前账本备份到 data 目录。")
        warn.setObjectName("warn")
        warn.setWordWrap(True)
        file_layout.addWidget(warn)
        buttons = QHBoxLayout()
        export_button = QPushButton("导出账本…")
        import_button = QPushButton("导入账本…")
        set_role(export_button, "primary")
        set_role(import_button, "danger")
        export_button.clicked.connect(self.export_db)
        import_button.clicked.connect(self.import_db)
        buttons.addWidget(export_button)
        buttons.addWidget(import_button)
        buttons.addStretch(1)
        file_layout.addLayout(buttons)
        layout.addWidget(file_box)
        player_box = QGroupBox("导出玩家库")
        player_layout = QVBoxLayout(player_box)
        hint = QLabel("导出当前玩家名单，包含游戏 id、押金、总局数和备注。这是一份给查看用的表格，不能代替上面的账本交接。")
        hint.setWordWrap(True)
        player_layout.addWidget(hint)
        player_buttons = QHBoxLayout()
        export_players_button = QPushButton("导出玩家库…")
        export_players_button.clicked.connect(self.export_players)
        player_buttons.addWidget(export_players_button)
        player_buttons.addStretch(1)
        player_layout.addLayout(player_buttons)
        layout.addWidget(player_box)
        self.result = QLabel("")
        self.result.setObjectName("result")
        self.result.setWordWrap(True)
        self.result.setTextFormat(Qt.TextFormat.PlainText)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.result)
        layout.addStretch(1)

    def export_players(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default = str(Path.home() / f"玩家库-{stamp}.xlsx")
        path, _selected = QFileDialog.getSaveFileName(self, "导出玩家库", default, "Excel (*.xlsx)")
        if not path:
            return
        dest = Path(path)
        if dest.suffix.lower() != ".xlsx":
            dest = dest.with_name(dest.name + ".xlsx")

        def action() -> None:
            export_player_workbook(self.db.conn, dest)

        if not run_action(self, action):
            return
        self.result.setText(f"已导出玩家库：{dest}")
        QMessageBox.information(self, "导出完成", f"玩家库已导出到：\n{dest}")

    def reload(self) -> None:
        return

    def export_db(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default = str(Path.home() / f"jizhang-{stamp}.db")
        path, _selected = QFileDialog.getSaveFileName(self, "导出账本", default, "账本 (*.db)")
        if not path:
            return
        dest = Path(path)
        if dest.suffix.lower() != ".db":
            dest = dest.with_name(dest.name + ".db")

        def action() -> None:
            self.db.export_to(dest)

        if not run_action(self, action):
            return
        self.result.setText(f"已导出：{dest}")
        QMessageBox.information(
            self,
            "导出完成",
            f"账本已导出到：\n{dest}\n\n把这个文件交给下一位管理员导入。",
        )

    def import_db(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self, "导入账本", str(Path.home()), "账本 (*.db)"
        )
        if not path:
            return
        answer = QMessageBox.question(
            self,
            "确认导入",
            "导入会用所选文件覆盖这台电脑上的当前账本。\n"
            "导入前会自动把当前账本备份到 data 目录。\n\n"
            "确定导入吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        src = Path(path)
        backup_holder: dict[str, Path] = {}

        def action() -> None:
            backup_holder["path"] = self.db.import_from(src)

        if not run_action(self, action):
            return
        backup = backup_holder["path"]
        self.result.setText(f"已导入：{src}\n导入前的账本备份在：{backup}")
        self.on_changed()
        QMessageBox.information(
            self,
            "导入完成",
            f"已切换到导入的账本。\n导入前的账本备份在：\n{backup}",
        )


class LoginDialog(QDialog):
    def __init__(self, server_url: str = "", card: str = ""):
        super().__init__()
        del server_url
        self.setWindowTitle("登录")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(12)
        self.card_edit = QLineEdit(card)
        self.card_edit.setPlaceholderText("直接点击登录")
        form.addRow("卡密", self.card_edit)
        layout.addLayout(form)
        self.error_label = QLabel("")
        self.error_label.setObjectName("warn")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("退出")
        login_button = QPushButton("登录")
        set_role(login_button, "primary")
        cancel.clicked.connect(self.reject)
        login_button.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(login_button)
        layout.addLayout(buttons)

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)

    def values(self) -> tuple[str, str]:
        return DEFAULT_SERVER_URL, self.card_edit.text().strip()


class MainWindow(QMainWindow):
    def __init__(self, database: Database):
        super().__init__()
        self.db = database
        self.setWindowTitle("押金记账")
        self.setWindowIcon(app_icon())
        self.players_page = PlayersPage(database, self.notify)
        self.session_page = SessionPage(database, self.notify)
        self.ledger_page = LedgerPage(database, self.notify)
        self.handover_page = HandoverPage(database, self.notify)
        self.players_page.open_player.connect(self.open_player_ledger)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(app_icon().pixmap(32, 32))
        title = QLabel("押金记账")
        title.setObjectName("appTitle")
        hint = QLabel("本机账本")
        hint.setObjectName("appHint")
        brand.addWidget(mark)
        brand.addWidget(title)
        brand.addWidget(hint)
        brand.addStretch(1)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.players_page, "玩家库")
        self.tabs.addTab(self.session_page, "开一局")
        self.tabs.addTab(self.ledger_page, "押金记录")
        self.tabs.addTab(self.handover_page, "交接班")
        central = QWidget()
        central.setObjectName("shell")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(4)
        layout.addLayout(brand)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)
        self.setMinimumSize(980, 660)
        self._license: LicenseSession | None = None
        self._expires_at = ""
        self._heartbeat_failures = 0
        self._license_locked = False
        self._timer: QTimer | None = None
        self.notify()
        self.tabs.currentChanged.connect(self._refresh_tab)

    def start_license_watch(self, session: LicenseSession) -> None:
        self._license = session
        self._expires_at = session.expires_at
        self._heartbeat_failures = 0
        self._timer = QTimer(self)
        self._timer.setInterval(HEARTBEAT_INTERVAL_MS)
        self._timer.timeout.connect(self._on_heartbeat)
        self._timer.start()
        self.notify()

    def _on_heartbeat(self) -> None:
        if self._license is None or self._license_locked:
            return
        result = self._license.heartbeat()
        self._heartbeat_failures, must_lock = note_heartbeat(self._heartbeat_failures, result)
        if result.ok and result.expires_at:
            self._expires_at = result.expires_at
            self.notify()
        if must_lock:
            self.lock_for_license(result.message)

    def lock_for_license(self, message: str) -> None:
        if self._license_locked:
            return
        self._license_locked = True
        if self._timer is not None:
            self._timer.stop()
        self.centralWidget().setEnabled(False)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("授权已失效")
        box.setText(message + "\n请退出程序。")
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        button = box.button(QMessageBox.StandardButton.Ok)
        if button is not None:
            button.setText("退出")
        box.exec()
        self.close()

    def notify(self) -> None:
        self.players_page.reload()
        self.session_page.reload()
        self.ledger_page.reload()
        self.handover_page.reload()
        players = list_players(self.db.conn)
        total_cents = sum(int(player["deposit_cents"]) for player in players)
        expiry = f"    卡密到期：{self._expires_at}" if self._expires_at else ""
        self.statusBar().showMessage(
            f"账本：{self.db.path}    玩家 {len(players)} 人    总押金 {format_yuan(total_cents)} 元{expiry}"
        )

    def _refresh_tab(self, index: int) -> None:
        page = self.tabs.widget(index)
        if page is not None:
            page.reload()

    def open_player_ledger(self, game_id: str) -> None:
        self.tabs.setCurrentWidget(self.ledger_page)
        self.ledger_page.show_player(game_id)

    def closeEvent(self, event) -> None:
        if self._timer is not None:
            self._timer.stop()
        if self._license is not None:
            self._license.logout()
            self._license = None
        self.session_page.save_tea()
        self.db.close()
        super().closeEvent(event)
