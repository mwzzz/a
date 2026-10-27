"""卡密服务。只提供登录、心跳和下线。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from license_server.store import CardStore


def make_handler(store: CardStore):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.rstrip("/") == "":
                self._send(200, {"ok": True})
                return
            self._send(404, {"ok": False, "error": "invalid"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            if not isinstance(payload, dict):
                self._send(403, {"ok": False, "error": "invalid"})
                return
            card = str(payload.get("card") or "").strip()
            machine_id = str(payload.get("machine_id") or "").strip()
            path = self.path.rstrip("/")
            if not machine_id:
                self._send(403, {"ok": False, "error": "invalid"})
                return
            if path == "/v1/session":
                outcome = store.login(card, machine_id)
            elif path == "/v1/session/heartbeat":
                outcome = store.heartbeat(card, machine_id)
            elif path == "/v1/session/logout":
                outcome = store.logout(card, machine_id)
            else:
                self._send(404, {"ok": False, "error": "invalid"})
                return
            self._send(outcome.status, outcome.body)

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def serve(host: str, port: int, db_path: Path) -> None:
    store = CardStore(db_path)
    server = ThreadingHTTPServer((host, port), make_handler(store))
    print(f"卡密服务已启动：http://{host}:{port}  数据库：{db_path}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        store.close()
