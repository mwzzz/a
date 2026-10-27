import pytest

from app.db import Database
from app.services import (
    AppError,
    add_deposit,
    create_player,
    delete_player,
    get_player,
    list_ledger,
    open_session,
    parse_yuan,
    refund,
    transfer,
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


def test_open_session_batch_and_rollback(db):
    create_player(db.conn, "a", "甲")
    create_player(db.conn, "b", "乙")
    create_player(db.conn, "c", "丙")
    add_deposit(db.conn, "a", 1000)
    add_deposit(db.conn, "b", 800)
    add_deposit(db.conn, "c", 100)

    with pytest.raises(AppError, match="押金不足"):
        open_session(db.conn, ["a", "c"], 300)
    assert get_player(db.conn, "a")["deposit_cents"] == 1000
    assert get_player(db.conn, "a")["games_played"] == 0
    assert get_player(db.conn, "c")["games_played"] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert db.conn.execute(
        "SELECT COUNT(*) FROM ledger WHERE reason = 'normal_deduct'"
    ).fetchone()[0] == 0

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
