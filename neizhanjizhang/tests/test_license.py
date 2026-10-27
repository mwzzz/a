import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.license_client import (
    load_config,
    login,
    note_heartbeat,
    save_config,
    LicenseConfig,
    LicenseSession,
)


class _State:
    def __init__(self) -> None:
        self.mode = "ok"
        self.expires_at = "2027-01-01 00:00:00"
        self.logouts = 0


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        state: _State = self.server.state  # type: ignore[attr-defined]
        if self.path == "/v1/session/logout":
            state.logouts += 1
            self._send(200, {"ok": True})
            return
        if state.mode == "down":
            self._send(500, {"ok": False, "error": "offline"})
            return
        if state.mode == "in_use":
            self._send(409, {"ok": False, "error": "in_use"})
            return
        if state.mode == "expired":
            self._send(403, {"ok": False, "error": "expired"})
            return
        if state.mode == "invalid":
            self._send(403, {"ok": False, "error": "invalid"})
            return
        self._send(200, {"ok": True, "expires_at": state.expires_at})

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


@pytest.fixture
def license_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.state = _State()  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def _url(server: ThreadingHTTPServer) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}"


def test_login_success_does_not_store_expiry(tmp_path, monkeypatch, license_server):
    monkeypatch.setattr("app.license_client.install_dir", lambda: tmp_path)
    result = login(_url(license_server), "CARD-1", "machine-a")
    assert result.ok
    assert result.expires_at == "2027-01-01 00:00:00"
    save_config(LicenseConfig(_url(license_server), "CARD-1", "machine-a"))
    saved = json.loads((tmp_path / "data" / "license.json").read_text(encoding="utf-8"))
    assert saved == {
        "server_url": _url(license_server),
        "card": "CARD-1",
        "machine_id": "machine-a",
    }
    assert "expires_at" not in saved
    assert load_config().card == "CARD-1"


def test_login_rejects_card_in_use(license_server):
    license_server.state.mode = "in_use"
    result = login(_url(license_server), "CARD-1", "machine-b")
    assert not result.ok
    assert result.error == "in_use"
    assert result.message == "这张卡正在另一台电脑上使用"


def test_login_rejects_expired_and_invalid(license_server):
    license_server.state.mode = "expired"
    expired = login(_url(license_server), "CARD-1", "machine-a")
    assert expired.error == "expired"
    assert expired.message == "卡密已过期"
    license_server.state.mode = "invalid"
    invalid = login(_url(license_server), "NOPE", "machine-a")
    assert invalid.error == "invalid"
    assert invalid.message == "卡密无效"


def test_login_requires_server():
    missing_server = login("  ", "CARD-1", "machine-a")
    assert missing_server.error == "missing_server"


def test_heartbeat_failure_locks_on_second_offline_and_immediately_when_taken(license_server):
    base = _url(license_server)
    session = LicenseSession(base, "CARD-1", "machine-a", "")
    ok = session.heartbeat()
    assert ok.ok
    assert session.expires_at == "2027-01-01 00:00:00"

    license_server.state.mode = "down"
    first = session.heartbeat()
    failures, must_lock = note_heartbeat(0, first)
    assert first.error == "offline"
    assert failures == 1
    assert must_lock is False
    failures, must_lock = note_heartbeat(failures, session.heartbeat())
    assert failures == 2
    assert must_lock is True

    license_server.state.mode = "in_use"
    taken = session.heartbeat()
    _, must_lock = note_heartbeat(0, taken)
    assert taken.error == "in_use"
    assert must_lock is True

    license_server.state.mode = "ok"
    session.logout()
    assert license_server.state.logouts == 1
