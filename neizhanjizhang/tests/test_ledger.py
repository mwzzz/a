import os
import sqlite3
import stat

import pytest

from app.db import Database
from app.services import (
    AppError,
    add_deposit,
    create_player,
    delete_player,
    get_player,
    get_last_tea_cents,
    list_ledger,
    list_players,
    list_session_players,
    open_session,
    parse_yuan,
    refund,
    set_last_tea_cents,
    transfer,
    update_remark,
    export_player_workbook,
    import_players,
)


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "deposit.db")
    yield database
    database.close()


def test_parse_yuan():
    assert parse_yuan("10") == 1000
    assert parse_yuan("10.5") == 1050
    assert parse_yuan(" 0.01 ") == 1
    assert parse_yuan("0") == 0
    with pytest.raises(AppError):
        parse_yuan("1.001")
    with pytest.raises(AppError):
        parse_yuan("-1")
    with pytest.raises(AppError):
        parse_yuan("")


def test_refund_insufficient_rolls_back(db):
    create_player(db.conn, "a", "甲")
    add_deposit(db.conn, "a", 1000)
    with pytest.raises(AppError, match="押金不足"):
        refund(db.conn, "a", 1001)
    player = get_player(db.conn, "a")
    assert player["deposit_cents"] == 1000
    rows = list_ledger(db.conn, "a")
    assert len(rows) == 1
    assert rows[0]["reason"] == "add_deposit"

    refund(db.conn, "a", 400)
    player = get_player(db.conn, "a")
    assert player["deposit_cents"] == 600
    latest = list_ledger(db.conn, "a")[0]
    assert latest["reason"] == "refund"
    assert latest["balance_before_cents"] == 1000
    assert latest["balance_after_cents"] == 600
    assert latest["signed_amount_cents"] == -400


def test_delete_player_rules(db):
    create_player(db.conn, "a", "甲")
    delete_player(db.conn, "a")
    assert get_player(db.conn, "a") is None

    create_player(db.conn, "a", "甲")
    add_deposit(db.conn, "a", 100)
    with pytest.raises(AppError, match="不能删除"):
        delete_player(db.conn, "a")
    assert get_player(db.conn, "a")["deposit_cents"] == 100
    refund(db.conn, "a", 100)
    delete_player(db.conn, "a")
    assert get_player(db.conn, "a") is None
    assert list_ledger(db.conn, "a") == []

    create_player(db.conn, "b", remark="常客")
    assert get_player(db.conn, "b")["remark"] == "常客"
    update_remark(db.conn, "b", "改后备注")
    assert get_player(db.conn, "b")["remark"] == "改后备注"
    add_deposit(db.conn, "b", 100)
    open_session(db.conn, ["b"], 300)
    with pytest.raises(AppError, match="不能删除"):
        delete_player(db.conn, "b")


def test_import_players_skips_existing_and_blank_lines(db):
    create_player(db.conn, "东子", remark="旧备注")
    result = import_players(
        db.conn,
        "\n# 注释\n东子,新备注\n执笔\n执笔,重复\n,缺id\n面包人，晚上来\n",
    )
    assert result["created"] == ["执笔", "面包人"]
    assert result["skipped"] == ["东子", "执笔"]
    assert result["errors"]
    assert get_player(db.conn, "东子")["remark"] == "旧备注"
    assert get_player(db.conn, "执笔")["remark"] == ""
    assert get_player(db.conn, "面包人")["remark"] == "晚上来"
    assert get_player(db.conn, "执笔")["deposit_cents"] == 0


def test_transfer_creates_pair(db):
    create_player(db.conn, "a", "")
    create_player(db.conn, "b", "")
    add_deposit(db.conn, "a", 5000)
    transfer(db.conn, "a", "b", 1500, note="换人")

    assert get_player(db.conn, "a")["deposit_cents"] == 3500
    assert get_player(db.conn, "b")["deposit_cents"] == 1500
    outgoing = list_ledger(db.conn, "a")[0]
    incoming = list_ledger(db.conn, "b")[0]
    assert outgoing["reason"] == "transfer_out"
    assert incoming["reason"] == "transfer_in"
    assert outgoing["reason_label"] == "划给其他人押金"
    assert incoming["reason_label"] == "收到他人划入"
    assert outgoing["transfer_group_id"] == incoming["transfer_group_id"]
    assert outgoing["counterparty_game_id"] == "b"
    assert incoming["counterparty_game_id"] == "a"
    assert outgoing["balance_before_cents"] == 5000
    assert outgoing["balance_after_cents"] == 3500
    assert incoming["balance_before_cents"] == 0
    assert incoming["balance_after_cents"] == 1500
    assert outgoing["signed_amount_cents"] == -1500
    assert incoming["signed_amount_cents"] == 1500
    assert outgoing["note"] == "换人"


def test_transfer_rejects_self_and_insufficient_balance(db):
    create_player(db.conn, "a", "")
    create_player(db.conn, "b", "")
    add_deposit(db.conn, "a", 100)
    with pytest.raises(AppError, match="不能划给自己"):
        transfer(db.conn, "a", "a", 50)
    with pytest.raises(AppError, match="押金不足"):
        transfer(db.conn, "a", "b", 101)
    assert get_player(db.conn, "a")["deposit_cents"] == 100
    assert get_player(db.conn, "b")["deposit_cents"] == 0
    assert list_ledger(db.conn, "b") == []


def test_open_session_records_negative_deposit(db):
    create_player(db.conn, "a", "甲")
    create_player(db.conn, "c", "丙")
    add_deposit(db.conn, "a", 1000)
    add_deposit(db.conn, "c", 100)

    session_id = open_session(db.conn, ["a", "c"], 300)
    assert get_player(db.conn, "a")["deposit_cents"] == 700
    assert get_player(db.conn, "a")["games_played"] == 1
    assert get_player(db.conn, "c")["deposit_cents"] == -200
    assert get_player(db.conn, "c")["games_played"] == 1
    deducted = list_ledger(db.conn, "c")[0]
    assert deducted["reason"] == "normal_deduct"
    assert deducted["session_id"] == session_id
    assert deducted["balance_before_cents"] == 100
    assert deducted["balance_after_cents"] == -200


def test_open_session_batch_and_zero_tea(db):
    create_player(db.conn, "a", "甲")
    create_player(db.conn, "b", "乙")
    create_player(db.conn, "c", "丙")
    add_deposit(db.conn, "a", 1000)
    add_deposit(db.conn, "b", 800)
    add_deposit(db.conn, "c", 100)

    session_id = open_session(db.conn, ["a", "b", "a"], 300, note="晚场")
    assert get_player(db.conn, "a")["deposit_cents"] == 700
    assert get_player(db.conn, "b")["deposit_cents"] == 500
    assert get_player(db.conn, "a")["games_played"] == 1
    assert get_player(db.conn, "b")["games_played"] == 1
    deduct = list_ledger(db.conn, "a")[0]
    assert deduct["reason"] == "normal_deduct"
    assert deduct["amount_cents"] == 300
    assert deduct["balance_before_cents"] == 1000
    assert deduct["balance_after_cents"] == 700
    assert deduct["session_id"] == session_id
    assert deduct["note"] == "晚场"
    assert list_ledger(db.conn, "b")[0]["session_id"] == session_id

    open_session(db.conn, ["b"], 0)
    player_b = get_player(db.conn, "b")
    assert player_b["games_played"] == 2
    assert player_b["deposit_cents"] == 500
    zero = list_ledger(db.conn, "b")[0]
    assert zero["reason"] == "normal_deduct"
    assert zero["amount_cents"] == 0
    assert zero["balance_before_cents"] == 500
    assert zero["balance_after_cents"] == 500


def test_import_replaces_database_and_keeps_backup(tmp_path):
    database = Database(tmp_path / "data" / "deposit.db")
    create_player(database.conn, "p1", "甲")
    add_deposit(database.conn, "p1", 100)
    exported = tmp_path / "jizhang.db"
    database.export_to(exported)

    add_deposit(database.conn, "p1", 50)
    assert get_player(database.conn, "p1")["deposit_cents"] == 150

    backup = database.import_from(exported)
    assert backup.exists()
    assert get_player(database.conn, "p1")["deposit_cents"] == 100
    assert list_ledger(database.conn, "p1")[0]["balance_after_cents"] == 100

    foreign = tmp_path / "notes.db"
    foreign.write_text("not a database", encoding="utf-8")
    with pytest.raises(AppError, match="不是本程序的账本"):
        database.import_from(foreign)
    assert get_player(database.conn, "p1")["deposit_cents"] == 100
    database.close()


def test_old_database_allows_negative_deposit(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE players (
            game_id TEXT PRIMARY KEY,
            nickname TEXT NOT NULL DEFAULT '',
            deposit_cents INTEGER NOT NULL DEFAULT 0 CHECK (deposit_cents >= 0),
            games_played INTEGER NOT NULL DEFAULT 0 CHECK (games_played >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tea_fee_cents INTEGER NOT NULL CHECK (tea_fee_cents >= 0),
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_game_id TEXT NOT NULL REFERENCES players(game_id),
            session_id INTEGER REFERENCES sessions(id),
            reason TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            balance_before_cents INTEGER NOT NULL CHECK (balance_before_cents >= 0),
            balance_after_cents INTEGER NOT NULL CHECK (balance_after_cents >= 0),
            counterparty_game_id TEXT,
            transfer_group_id TEXT,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    conn.close()
    database = Database(path)
    create_player(database.conn, "c", "")
    add_deposit(database.conn, "c", 100)
    open_session(database.conn, ["c"], 300)
    assert get_player(database.conn, "c")["deposit_cents"] == -200
    database.close()


def test_import_of_readonly_ledger_stays_writable(tmp_path):
    database = Database(tmp_path / "data" / "deposit.db")
    create_player(database.conn, "p1", "")
    add_deposit(database.conn, "p1", 100)
    exported = tmp_path / "received.db"
    database.export_to(exported)
    os.chmod(exported, stat.S_IREAD)

    database.import_from(exported)
    add_deposit(database.conn, "p1", 50)
    assert get_player(database.conn, "p1")["deposit_cents"] == 150
    assert database.path.stat().st_mode & stat.S_IWRITE
    database.close()


def test_reopen_clears_readonly_ledger(tmp_path):
    path = tmp_path / "deposit.db"
    database = Database(path)
    create_player(database.conn, "p1", "")
    database.close()
    os.chmod(path, stat.S_IREAD)

    reopened = Database(path)
    add_deposit(reopened.conn, "p1", 100)
    assert get_player(reopened.conn, "p1")["deposit_cents"] == 100
    assert path.stat().st_mode & stat.S_IWRITE
    reopened.close()


def test_session_list_puts_the_latest_tea_group_first(db):
    for game_id in [str(index) for index in range(12)]:
        create_player(db.conn, game_id, "")
        add_deposit(db.conn, game_id, 1000)
    create_player(db.conn, "new", "")
    open_session(db.conn, ["0", "1"], 100)
    latest = ["11", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
    open_session(db.conn, latest, 100)

    ordered = [player["game_id"] for player in list_session_players(db.conn)]
    assert ordered[:10] == latest
    assert ordered[10:] == ["0", "1", "new"]
    assert [player["game_id"] for player in list_players(db.conn) if player["games_played"]][:2] == [
        "0",
        "1",
    ]


def test_players_are_sorted_by_games_played(db):
    create_player(db.conn, "10", "")
    create_player(db.conn, "2", "")
    create_player(db.conn, "a", "")
    add_deposit(db.conn, "10", 500)
    add_deposit(db.conn, "2", 500)
    add_deposit(db.conn, "a", 500)
    open_session(db.conn, ["2"], 100)
    open_session(db.conn, ["2"], 100)
    open_session(db.conn, ["a"], 100)
    assert [player["game_id"] for player in list_players(db.conn)] == ["2", "a", "10"]


def test_last_tea_is_remembered_and_player_export_matches_the_list(db, tmp_path):
    assert get_last_tea_cents(db.conn) == 200
    set_last_tea_cents(db.conn, 1000)
    assert get_last_tea_cents(db.conn) == 1000
    create_player(db.conn, "东子", remark="晚上")
    add_deposit(db.conn, "东子", 250)
    dest = tmp_path / "players.xlsx"
    assert export_player_workbook(db.conn, dest) == 1
    from openpyxl import load_workbook
    sheet = load_workbook(dest).active
    assert [cell.value for cell in sheet[1]] == ["序号", "游戏 id", "押金", "总局数", "备注"]
    assert sheet["B2"].value == "东子"
    assert sheet["C2"].value == 2.5
    assert sheet["E2"].value == "晚上"
