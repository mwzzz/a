import threading
from datetime import timedelta
from http.server import ThreadingHTTPServer

from app.license_client import LicenseSession, login
from license_server.http import make_handler
from license_server.store import CardStore, format_dt, now_cn, parse_dt


def _start(store: CardStore) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def test_one_card_cannot_be_used_on_two_machines_at_once(tmp_path):
    store = CardStore(tmp_path / "cards.db")
    card, expires_at = store.issue(30)
    server, base = _start(store)
    try:
        first = login(base, card, "machine-a")
        assert first.ok
        assert first.expires_at == expires_at
        second = login(base, card, "machine-b")
        assert second.error == "in_use"
        assert second.message == "这张卡正在另一台电脑上使用"

        session = LicenseSession(base, card, "machine-a", first.expires_at)
        assert session.heartbeat().ok
        session.logout()
        assert login(base, card, "machine-b").ok
        assert login(base, card, "machine-a").error == "in_use"
    finally:
        server.shutdown()
        server.server_close()
        store.close()


def test_expired_lease_lets_another_machine_login(tmp_path):
    store = CardStore(tmp_path / "cards.db")
    card, _expires = store.issue(30)
    store.conn.execute(
        "UPDATE cards SET holder_machine_id = ?, last_seen = ? WHERE card = ?",
        ("machine-a", format_dt(now_cn() - timedelta(seconds=61)), card),
    )
    server, base = _start(store)
    try:
        taken = login(base, card, "machine-b")
        assert taken.ok
        assert login(base, card, "machine-a").error == "in_use"
    finally:
        server.shutdown()
        server.server_close()
        store.close()


def test_unknown_and_expired_cards(tmp_path):
    store = CardStore(tmp_path / "cards.db")
    card, _expires = store.issue(1)
    store.conn.execute(
        "UPDATE cards SET expires_at = ? WHERE card = ?",
        ("2000-01-01 00:00:00", card),
    )
    server, base = _start(store)
    try:
        assert login(base, "NO-SUCH-CARD", "machine-a").error == "invalid"
        assert login(base, card, "machine-a").error == "expired"
        session = LicenseSession(base, card, "machine-a", "")
        assert session.heartbeat().error == "expired"
    finally:
        server.shutdown()
        server.server_close()
        store.close()


def test_extend_adds_days_to_the_same_card(tmp_path):
    store = CardStore(tmp_path / "cards.db")
    try:
        card, expires_at = store.issue(10)
        extended = store.extend(card, 20)
        assert extended > expires_at
        assert store.list_cards()[0]["card"] == card
        store.conn.execute(
            "UPDATE cards SET expires_at = ? WHERE card = ?",
            ("2000-01-01 00:00:00", card),
        )
        renewed = store.extend(card, 5)
        renewed_at = parse_dt(renewed)
        assert abs((renewed_at - (now_cn() + timedelta(days=5))).total_seconds()) < 2
    finally:
        store.close()


def test_trial_accepts_any_card_until_turned_off(tmp_path):
    store = CardStore(tmp_path / "cards.db")
    store.set_trial(True)
    real, _expires = store.issue(30)
    server, base = _start(store)
    try:
        assert login(base, "", "machine-a").ok
        assert login(base, "", "machine-b").ok
        assert login(base, "随便写", "machine-c").ok
        assert login(base, real, "machine-a").ok
        assert login(base, real, "machine-b").error == "in_use"
        store.set_trial(False)
        assert login(base, "", "machine-a").error == "invalid"
        assert login(base, "随便写", "machine-c").error == "invalid"
        assert login(base, real, "machine-a").ok
    finally:
        server.shutdown()
        server.server_close()
        store.close()


def test_heartbeat_does_not_steal_a_live_card(tmp_path):
    store = CardStore(tmp_path / "cards.db")
    card, _expires = store.issue(7)
    server, base = _start(store)
    try:
        assert login(base, card, "machine-a").ok
        other = LicenseSession(base, card, "machine-b", "")
        assert other.heartbeat().error == "in_use"
        assert LicenseSession(base, card, "machine-a", "").heartbeat().ok
    finally:
        server.shutdown()
        server.server_close()
        store.close()
