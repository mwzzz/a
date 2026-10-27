#!/usr/bin/env python3
"""本机假 Zabbix API，方便不连生产也能测拉取脚本。

用法:
  1. 另开一个终端: python mock_zabbix_server.py
  2. 使用 config.local.json（已指向本 mock）
  3. python test_zabbix_fetch.py
     或: 把 config.local.json 复制/改名为 config.json 后再跑

说明:
  - 只实现本项目用到的接口: user.login / item.get / host.get / user.logout
  - 内置几台假主机，含「临近 400 天」和「刚从高位掉下来」的样例数据
  - 仅标准库，默认监听 http://127.0.0.1:18080
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# 监听地址（与 config.local.json 保持一致）
HOST = "127.0.0.1"
PORT = 18080

# 假账号：随便填，mock 里不校验密码，只要求有 user/password 字段
FAKE_TOKEN = "mock-auth-token-001"

# 一天的秒数
DAY = 86400

# 假监控项数据（lastvalue 单位：秒，对应 value_unit=seconds）
# 可按需要改天数，用来测规则 1 / 规则 2
FAKE_ITEMS = [
    {
        "itemid": "1001",
        "hostid": "101",
        "name": "System uptime",
        "key_": "system.uptime",
        "lastvalue": str(int(410 * DAY)),  # ~410 天：会进「临近上限」
        "units": "uptime",
        "lastclock": "1710000000",
        "hosts": [{"hostid": "101", "host": "web-01", "name": "web-01"}],
    },
    {
        "itemid": "1002",
        "hostid": "102",
        "name": "System uptime",
        "key_": "system.uptime",
        "lastvalue": str(int(2 * DAY)),  # ~2 天：配合 snapshot 可测「疑似回绕」
        "units": "uptime",
        "lastclock": "1710000000",
        "hosts": [{"hostid": "102", "host": "db-01", "name": "db-01"}],
    },
    {
        "itemid": "1003",
        "hostid": "103",
        "name": "System uptime",
        "key_": "system.uptime",
        "lastvalue": str(int(30 * DAY)),  # 正常几十天
        "units": "uptime",
        "lastclock": "1710000000",
        "hosts": [{"hostid": "103", "host": "app-01", "name": "app-01"}],
    },
    # 另一 key，方便测 item_keys 过滤
    {
        "itemid": "1004",
        "hostid": "104",
        "name": "HW uptime",
        "key_": "system.hw.uptime",
        "lastvalue": str(int(405 * DAY)),
        "units": "uptime",
        "lastclock": "1710000000",
        "hosts": [{"hostid": "104", "host": "sw-01", "name": "sw-01"}],
    },
]

# 假 inventory（负责人邮箱）
FAKE_HOSTS = {
    "101": {"poc_1_email": "alice@example.com"},
    "102": {"poc_1_email": "bob@example.com"},
    "103": {"poc_1_email": ""},
    "104": {"poc_1_email": "netops@example.com"},
}


def handle_rpc(payload: dict) -> dict:
    """根据 method 返回假 JSON-RPC 结果。"""
    method = payload.get("method")
    params = payload.get("params") or {}
    req_id = payload.get("id", 1)

    if method == "user.login":
        # 不校验密码，有调用就算成功
        return {"jsonrpc": "2.0", "result": FAKE_TOKEN, "id": req_id}

    if method == "user.logout":
        return {"jsonrpc": "2.0", "result": True, "id": req_id}

    if method == "item.get":
        # 按 filter.key_ 过滤；没传 filter 则返回全部
        keys = None
        filt = params.get("filter") or {}
        if "key_" in filt:
            keys = filt["key_"]
            if isinstance(keys, str):
                keys = [keys]
        items = FAKE_ITEMS
        if keys is not None:
            items = [it for it in items if it["key_"] in keys]
        return {"jsonrpc": "2.0", "result": items, "id": req_id}

    if method == "host.get":
        hostids = params.get("hostids") or []
        result = []
        for hid in hostids:
            inv = FAKE_HOSTS.get(str(hid), {})
            result.append(
                {
                    "hostid": str(hid),
                    "inventory": {
                        "poc_1_email": inv.get("poc_1_email", ""),
                        "poc_2_email": "",
                    },
                }
            )
        return {"jsonrpc": "2.0", "result": result, "id": req_id}

    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32601,
            "message": "Method not found",
            "data": f"mock 未实现: {method}",
        },
        "id": req_id,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        # 打印简短访问日志，方便确认脚本有打到 mock
        print(f"[mock] {self.address_string()} {fmt % args}")

    def do_POST(self) -> None:
        # 真实 Zabbix 路径一般是 /api_jsonrpc.php；这里路径随意，有 POST 就处理
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid json"})
            return

        print(f"[mock] method={payload.get('method')}")
        result = handle_rpc(payload)
        self._reply(200, result)

    def do_GET(self) -> None:
        # 浏览器打开时给个提示页
        body = (
            "Mock Zabbix API is running.\n"
            f"POST JSON-RPC to http://{HOST}:{PORT}/api_jsonrpc.php\n"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reply(self, code: int, obj: dict) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Mock Zabbix 已启动: http://{HOST}:{PORT}/api_jsonrpc.php")
    print("另开终端执行: python test_zabbix_fetch.py")
    print("（请使用 config.local.json，或把它复制为 config.json）")
    print("Ctrl+C 结束")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
