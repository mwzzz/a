"""卡密登录客户端。本地只保存地址、卡密和机器码，每次仍向服务器确认。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from app.db import install_dir

DEFAULT_SERVER_URL = "http://47.95.146.168:8000"
HEARTBEAT_INTERVAL_MS = 20_000
HEARTBEAT_TIMEOUT_SECONDS = 8
LOCK_AFTER_FAILURES = 2

_MESSAGES = {
    "in_use": "这张卡正在另一台电脑上使用",
    "expired": "卡密已过期",
    "invalid": "卡密无效",
    "offline": "无法连接授权服务器",
    "missing_server": "请填写服务器地址",
    "missing_card": "请填写卡密",
}


@dataclass
class LicenseConfig:
    server_url: str
    card: str
    machine_id: str


@dataclass
class LicenseResult:
    ok: bool
    error: str = ""
    expires_at: str = ""
    message: str = ""


def license_path() -> Path:
    return install_dir() / "data" / "license.json"


def load_config() -> LicenseConfig:
    path = license_path()
    if not path.is_file():
        return LicenseConfig(server_url="", card="", machine_id="")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LicenseConfig(server_url="", card="", machine_id="")
    if not isinstance(payload, dict):
        return LicenseConfig(server_url="", card="", machine_id="")
    return LicenseConfig(
        server_url=str(payload.get("server_url") or "").strip(),
        card=str(payload.get("card") or "").strip(),
        machine_id=str(payload.get("machine_id") or "").strip(),
    )


def save_config(config: LicenseConfig) -> None:
    path = license_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "server_url": config.server_url.strip(),
        "card": config.card.strip(),
        "machine_id": config.machine_id.strip(),
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def ensure_machine_id(config: LicenseConfig) -> LicenseConfig:
    if config.machine_id:
        return config
    updated = LicenseConfig(
        server_url=config.server_url,
        card=config.card,
        machine_id=uuid.uuid4().hex,
    )
    save_config(updated)
    return updated


def note_heartbeat(previous_failures: int, result: LicenseResult) -> tuple[int, bool]:
    """返回新的连续失败次数，以及是否必须锁住主窗口。"""
    if result.ok:
        return 0, False
    if result.error in {"in_use", "expired", "invalid"}:
        return previous_failures + 1, True
    failures = previous_failures + 1
    return failures, failures >= LOCK_AFTER_FAILURES


class LicenseSession:
    def __init__(self, server_url: str, card: str, machine_id: str, expires_at: str):
        self.server_url = server_url
        self.card = card
        self.machine_id = machine_id
        self.expires_at = expires_at

    def heartbeat(self) -> LicenseResult:
        result = _post(self.server_url, "/v1/session/heartbeat", self.card, self.machine_id)
        if result.ok and result.expires_at:
            self.expires_at = result.expires_at
        return result

    def logout(self) -> None:
        try:
            _post(self.server_url, "/v1/session/logout", self.card, self.machine_id)
        except Exception:
            return


def login(server_url: str, card: str, machine_id: str) -> LicenseResult:
    server_url = server_url.strip()
    card = card.strip()
    if not server_url:
        return _failure("missing_server")
    if not server_url.startswith(("http://", "https://")):
        return LicenseResult(ok=False, error="invalid", message="服务器地址需要以 http:// 或 https:// 开头")
    return _post(server_url, "/v1/session", card, machine_id)


def _failure(error: str) -> LicenseResult:
    return LicenseResult(ok=False, error=error, message=_MESSAGES[error])


def _endpoint(server_url: str, path: str) -> str:
    return server_url.rstrip("/") + path


def _post(server_url: str, path: str, card: str, machine_id: str) -> LicenseResult:
    body = json.dumps({"card": card, "machine_id": machine_id}).encode("utf-8")
    req = request.Request(
        _endpoint(server_url, path),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _open(req) as response:
            status = getattr(response, "status", 200)
            raw = response.read()
    except error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
    except error.URLError:
        return _failure("offline")
    return _interpret(status, raw)


def _open(req: request.Request):
    url = req.full_url
    if url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
        opener = request.build_opener(request.ProxyHandler({}))
        return opener.open(req, timeout=HEARTBEAT_TIMEOUT_SECONDS)
    return request.urlopen(req, timeout=HEARTBEAT_TIMEOUT_SECONDS)


def _interpret(status: int, raw: bytes) -> LicenseResult:
    payload: dict = {}
    if raw:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
    if status == 200 and payload.get("ok") is True:
        return LicenseResult(ok=True, expires_at=str(payload.get("expires_at") or ""))
    error_code = str(payload.get("error") or "")
    if status == 409 or error_code == "in_use":
        return _failure("in_use")
    if error_code == "expired":
        return _failure("expired")
    if status == 403 or error_code == "invalid":
        return _failure("invalid")
    return _failure("offline")
