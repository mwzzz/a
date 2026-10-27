"""玩家库、开一局、押金记录和交班四个页面。"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.db import Database
from app.services import (
    AppError,
    add_deposit,
    create_player,
    delete_player,
    format_change,
    format_yuan,
    get_player,
    list_ledger,
    list_players,
    normalize_game_id,
    open_session,
    parse_yuan,
    preview_session,
    refund,
    transfer,
)

COLOR_TEXT = QColor("#1f1f1f")
COLOR_BAD = QColor("#a12626")
MONEY_ALIGN = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
TEXT_ALIGN = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def subtitle(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #444444;")
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
    table.verticalHeader().setVisible(False)
    table.setWordWrap(False)


def player_label(player: dict) -> str:
    return player["game_id"]


class PlayerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("新增玩家")
        self.setMinimumWidth(360)
        self.game_id_edit = QLineEdit()
        form = QFormLayout(self)
        form.addRow("游戏 id", self.game_id_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.game_id = ""

    def _accept(self) -> None:
        try:
            self.game_id = normalize_game_id(self.game_id_edit.text())
        except AppError as exc:
            QMessageBox.warning(self, "无法完成", str(exc))
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
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
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
        self.db = database
        self.on_changed = on_changed
        layout = QVBoxLayout(self)
        layout.addWidget(subtitle("每个玩家用游戏 id 识别。押金是还在管理员这里的余额。双击一行可查看流水。"))
        buttons = QHBoxLayout()
        add_button = QPushButton("新增玩家")
        delete_button = QPushButton("删除")
        add_button.clicked.connect(self.add_player)
        delete_button.clicked.connect(self.remove_player)
        buttons.addWidget(add_button)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        self.total_label = QLabel("总押金 0.00 元")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        buttons.addWidget(self.total_label)
        layout.addLayout(buttons)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["序号", "游戏 id", "押金", "总局数"])
        configure_table(self.table)
        self.table.cellDoubleClicked.connect(self._open_selected)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

    def reload(self) -> None:
        selected = self.selected_game_id()
        players = list_players(self.db.conn)
        total_cents = sum(int(player["deposit_cents"]) for player in players)
        self.total_label.setText(f"总押金 {format_yuan(total_cents)} 元")
        self.table.setRowCount(len(players))
        for row, player in enumerate(players):
            self.table.setItem(row, 0, readonly_item(str(row + 1), MONEY_ALIGN))
            self.table.setItem(row, 1, readonly_item(player["game_id"]))
            deposit = readonly_item(format_yuan(player["deposit_cents"]), MONEY_ALIGN)
            self.table.setItem(row, 2, deposit)
            games = readonly_item(str(player["games_played"]), MONEY_ALIGN)
            self.table.setItem(row, 3, games)
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
            create_player(self.db.conn, dialog.game_id)

        if run_action(self, action):
            self.on_changed()
            self._select(dialog.game_id)

    def remove_player(self) -> None:
        game_id = self._require_selected()
        if not game_id:
            return
        answer = QMessageBox.question(
            self,
            "删除玩家",
            f"确定删除玩家 {game_id}？\n只有从未记过账的玩家可以删除。",
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
        self.db = database
        self.on_changed = on_changed
        self._refreshing = False
        self._reset_checks = False
        layout = QVBoxLayout(self)
        layout.addWidget(subtitle("勾选本局玩家，按茶水批量正常扣押，每人总局数加 1。有人余额不够时，整局不会写入。"))
        form = QHBoxLayout()
        form.addWidget(QLabel("本局茶水（元）"))
        self.tea_edit = QLineEdit()
        self.tea_edit.setMaximumWidth(140)
        self.tea_edit.textChanged.connect(self.refresh_amounts)
        form.addWidget(self.tea_edit)
        form.addWidget(QLabel("备注"))
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("可选，例如晚场")
        form.addWidget(self.note_edit, 1)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        select_all = QPushButton("全选")
        select_none = QPushButton("全不选")
        self.confirm_button = QPushButton("确认开局")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none.clicked.connect(lambda: self._set_all(False))
        self.confirm_button.clicked.connect(self.confirm)
        buttons.addWidget(select_all)
        buttons.addWidget(select_none)
        buttons.addStretch(1)
        buttons.addWidget(self.confirm_button)
        layout.addLayout(buttons)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["选择", "游戏 id", "当前押金", "本局扣除", "扣后押金", "状态"]
        )
        configure_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self.tea_edit.setText("2.00")

    def reload(self) -> None:
        selected = set() if self._reset_checks else set(self.selected_ids())
        self._reset_checks = False
        players = list_players(self.db.conn)
        self.table.blockSignals(True)
        self.table.setRowCount(len(players))
        for row, player in enumerate(players):
            check = QCheckBox("本局")
            check.setProperty("game_id", player["game_id"])
            check.setChecked(player["game_id"] in selected)
            check.toggled.connect(self.refresh_amounts)
            self.table.setCellWidget(row, 0, check)
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
        return widget if isinstance(widget, QCheckBox) else None

    def selected_ids(self) -> list[str]:
        ids: list[str] = []
        for row in range(self.table.rowCount()):
            box = self._check_box(row)
            if box and box.isChecked():
                ids.append(str(box.property("game_id")))
        return ids

    def _set_all(self, checked: bool) -> None:
        for row in range(self.table.rowCount()):
            box = self._check_box(row)
            if box:
                box.blockSignals(True)
                box.setChecked(checked)
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
                    status_item.setText("押金不足")
                    status_item.setForeground(QBrush(COLOR_BAD))
                else:
                    status_item.setText("可以扣")
                    status_item.setForeground(QBrush(COLOR_TEXT))
        finally:
            self.table.blockSignals(False)
            self._refreshing = False

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
        short = [row["game_id"] for row in preview if not row["ok"]]
        if short:
            QMessageBox.warning(self, "无法完成", "押金不足，本局未写入：" + "、".join(short))
            return
        answer = QMessageBox.question(
            self,
            "确认开局",
            f"确认为 {len(preview)} 名玩家开局？\n每人正常扣押 {format_yuan(tea)} 元，总局数各加 1。",
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
        self.db = database
        self.on_changed = on_changed
        self._game_id = ""
        layout = QVBoxLayout(self)
        layout.addWidget(subtitle("查询某个游戏 id 的押金流水。最新的记录在最上面。"))
        query_row = QHBoxLayout()
        query_row.addWidget(QLabel("游戏 id"))
        self.player_combo = QComboBox()
        self.player_combo.setEditable(True)
        self.player_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.player_combo.setMinimumWidth(280)
        query_button = QPushButton("查询")
        query_button.clicked.connect(self.query)
        self.player_combo.activated.connect(lambda _index: self.query())
        query_row.addWidget(self.player_combo, 1)
        query_row.addWidget(query_button)
        layout.addLayout(query_row)
        self.summary = QLabel("请查询一个游戏 id")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        self.add_button = QPushButton("加押金")
        self.refund_button = QPushButton("退押金")
        self.transfer_button = QPushButton("划给其他人")
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
            self.player_combo.addItem(player_label(player), player["game_id"])
        self.player_combo.setCurrentText(current_text)
        self.player_combo.blockSignals(False)
        if self._game_id:
            self._load_player(self._game_id, quiet=True)

    def show_player(self, game_id: str) -> None:
        index = self.player_combo.findData(game_id)
        if index >= 0:
            self.player_combo.setCurrentIndex(index)
        else:
            self.player_combo.setCurrentText(game_id)
        self._load_player(game_id, quiet=False)

    def query(self) -> None:
        game_id = self._resolve_game_id(self.player_combo.currentText())
        if not game_id:
            QMessageBox.warning(self, "无法完成", "请输入游戏 id")
            return
        self._load_player(game_id, quiet=False)

    def _resolve_game_id(self, text: str) -> str:
        raw = text.strip()
        if not raw:
            return ""
        data = self.player_combo.currentData()
        if data and str(data) == raw:
            return str(data)
        for index in range(self.player_combo.count()):
            game_id = str(self.player_combo.itemData(index))
            player = self._player_by_id(game_id)
            if player and (raw == game_id or raw == player_label(player)):
                return game_id
        return raw

    def _player_by_id(self, game_id: str) -> dict | None:
        return get_player(self.db.conn, game_id)

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
            self.table.setItem(
                index, 2, readonly_item(format_change(entry["signed_amount_cents"]), MONEY_ALIGN)
            )
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

    def _require_loaded(self) -> str | None:
        if not self._game_id:
            QMessageBox.warning(self, "无法完成", "请先查询一个玩家")
            return None
        return self._game_id

    def add_money(self) -> None:
        game_id = self._require_loaded()
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
        game_id = self._require_loaded()
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
        game_id = self._require_loaded()
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
        self.db = database
        self.on_changed = on_changed
        layout = QVBoxLayout(self)
        layout.addWidget(
            subtitle(
                "换班时导出整个账本文件，交给下一位管理员导入。"
                "请使用这里导出的文件，不要直接拷贝正在使用的 deposit.db。"
            )
        )

        file_box = QGroupBox("交接账本")
        file_layout = QVBoxLayout(file_box)
        file_layout.addWidget(QLabel("导入会覆盖这台电脑上的当前账本。导入前会自动把当前账本备份到 data 目录。"))
        buttons = QHBoxLayout()
        export_button = QPushButton("导出账本…")
        import_button = QPushButton("导入账本…")
        export_button.clicked.connect(self.export_db)
        import_button.clicked.connect(self.import_db)
        buttons.addWidget(export_button)
        buttons.addWidget(import_button)
        buttons.addStretch(1)
        file_layout.addLayout(buttons)
        layout.addWidget(file_box)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        self.result.setTextFormat(Qt.TextFormat.PlainText)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.result)
        layout.addStretch(1)

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


class MainWindow(QMainWindow):
    def __init__(self, database: Database):
        super().__init__()
        self.db = database
        self.setWindowTitle("押金记账")
        self.setStyleSheet(
            """
            QWidget { font-family: "Microsoft YaHei UI"; font-size: 13px; }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f7f7f7;
                gridline-color: #e6e6e6;
            }
            QHeaderView::section {
                background: #f0f0f0;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #d0d0d0;
            }
            QLineEdit, QComboBox { padding: 4px 6px; min-height: 22px; }
            QPushButton { padding: 6px 14px; min-height: 22px; }
            QGroupBox { font-weight: 600; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            """
        )
        self.players_page = PlayersPage(database, self.notify)
        self.session_page = SessionPage(database, self.notify)
        self.ledger_page = LedgerPage(database, self.notify)
        self.handover_page = HandoverPage(database, self.notify)
        self.players_page.open_player.connect(self.open_player_ledger)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.players_page, "玩家库")
        self.tabs.addTab(self.session_page, "开一局")
        self.tabs.addTab(self.ledger_page, "押金记录")
        self.tabs.addTab(self.handover_page, "交班")
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)
        self.setMinimumSize(960, 640)
        self.notify()
        self.tabs.currentChanged.connect(self._refresh_tab)

    def notify(self) -> None:
        self.players_page.reload()
        self.session_page.reload()
        self.ledger_page.reload()
        self.handover_page.reload()
        players = list_players(self.db.conn)
        total_cents = sum(int(player["deposit_cents"]) for player in players)
        self.statusBar().showMessage(
            f"账本：{self.db.path}    玩家 {len(players)} 人    总押金 {format_yuan(total_cents)} 元"
        )

    def _refresh_tab(self, index: int) -> None:
        page = self.tabs.widget(index)
        if page is not None:
            page.reload()

    def open_player_ledger(self, game_id: str) -> None:
        self.tabs.setCurrentWidget(self.ledger_page)
        self.ledger_page.show_player(game_id)

    def closeEvent(self, event) -> None:
        self.db.close()
        super().closeEvent(event)
