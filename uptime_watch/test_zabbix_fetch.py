#!/usr/bin/env python3
"""单独测试：能否从 Zabbix 拉到 uptime 数据。

用途:
  - 验证 config.json 里的地址、账号、密码是否正确
  - 验证 item_keys 是否能匹配到监控项
  - 确认 lastvalue 的单位（秒还是 TimeTicks），便于改 value_unit

用法:
  1. 本机假数据（推荐先这样测）:
       终端A: python mock_zabbix_server.py
       终端B: python test_zabbix_fetch.py --config config.local.json
  2. 或准备 config.json 指向真实/测试 Zabbix 后:
       python test_zabbix_fetch.py

说明:
  - 只读 Zabbix，不写快照、不发邮件
  - 仅使用 Python 标准库，无需额外安装依赖
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# 脚本所在目录（配置文件默认放这里）
ROOT = Path(__file__).resolve().parent
# 一天的秒数，用于把 uptime 换算成「天」方便肉眼看
DAY = 86400


def load_config(path: Path) -> dict[str, Any]:
    """读取 JSON 配置文件。"""
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="测试从 Zabbix 拉取 uptime")
    p.add_argument(
        "--config",
        default="config.json",
        help="配置文件名或路径（默认 config.json；本机 mock 用 config.local.json）",
    )
    return p.parse_args()


def zabbix_call(
    url: str,
    method: str,
    params: dict[str, Any],
    auth: str | None = None,
) -> Any:
    """调用 Zabbix JSON-RPC 接口。

    url:    一般是 http(s)://主机/api_jsonrpc.php
    method: 如 user.login、item.get、user.logout
    params: 该方法的参数字典
    auth:   登录后拿到的 token；登录接口本身不要传 auth
    """
    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    # Zabbix 5/6 常见写法：把 auth 放在请求体里
    if auth is not None:
        body["auth"] = auth

    data = json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json-rpc"},
        method="POST",
    )

    with urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    # API 业务错误（账号错、权限不足等）会在 error 字段里
    if "error" in result:
        raise RuntimeError(f"Zabbix API error: {result['error']}")
    return result["result"]


def to_seconds(raw: str, value_unit: str) -> float | None:
    """把 Zabbix lastvalue 转成秒。

    value_unit:
      - seconds: lastvalue 已经是秒
      - ticks:   SNMP TimeTicks，百分之一秒，需要 /100
    """
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if value_unit == "ticks":
        return val / 100.0
    return val


def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    if not cfg_path.exists():
        print(f"缺少配置文件: {cfg_path}", file=sys.stderr)
        print(
            "本机测试: python mock_zabbix_server.py 后，"
            "再 python test_zabbix_fetch.py --config config.local.json",
            file=sys.stderr,
        )
        print(
            "或: copy config.example.json config.json 后改真实地址",
            file=sys.stderr,
        )
        return 1

    cfg = load_config(cfg_path)
    print(f"使用配置: {cfg_path}")
    zcfg = cfg["zabbix"]
    url = zcfg["url"]
    item_keys = zcfg.get("item_keys") or []
    value_unit = zcfg.get("value_unit", "seconds")

    print("=== Zabbix 拉取测试 ===")
    print(f"API 地址 : {url}")
    print(f"用户     : {zcfg.get('user')}")
    print(f"item_keys: {item_keys}")
    print(f"value_unit: {value_unit}  (seconds=已是秒, ticks=TimeTicks需/100)")
    print()

    # ---------- 1) 登录 ----------
    print("[1/3] user.login ...")
    try:
        # Zabbix 6+ 常用 username；若你们是更老版本且报错，可改成 user 字段
        auth = zabbix_call(
            url,
            "user.login",
            {"username": zcfg["user"], "password": zcfg["password"]},
        )
    except (HTTPError, URLError, RuntimeError, TimeoutError) as e:
        print(f"登录失败: {e}", file=sys.stderr)
        print(
            "请检查: url 是否可达、账号密码、防火墙、HTTPS 证书等",
            file=sys.stderr,
        )
        return 2

    print(f"登录成功，auth token 前 8 位: {str(auth)[:8]}...")
    print()

    # ---------- 2) 按 key 拉 uptime 监控项 ----------
    print("[2/3] item.get (按 item_keys 过滤) ...")
    try:
        items = zabbix_call(
            url,
            "item.get",
            {
                # 需要哪些字段就列哪些，减少无关数据
                "output": [
                    "itemid",
                    "hostid",
                    "name",
                    "key_",
                    "lastvalue",
                    "units",
                    "lastclock",
                ],
                # 精确匹配 key_；匹配不到就返回空列表
                "filter": {"key_": item_keys},
                # 顺带带上主机名，方便对照
                "selectHosts": ["hostid", "host", "name"],
                # 只看已启用监控的项
                "monitored": True,
            },
            auth=auth,
        )
    except RuntimeError as e:
        print(f"item.get 失败: {e}", file=sys.stderr)
        # 尽量登出，避免会话堆积（失败也无所谓）
        try:
            zabbix_call(url, "user.logout", {}, auth=auth)
        except Exception:
            pass
        return 3

    print(f"匹配到 {len(items)} 条 item")
    if not items:
        print()
        print("未匹配到任何 item。常见原因:")
        print("  1) config.json 里 item_keys 与 Zabbix 实际 key 不一致")
        print("  2) 对应 item 未启用 / 主机未监控")
        print("  3) API 账号对该主机/模板无读权限")
        print("建议: 在 Zabbix 网页打开某台机器的 Latest data，核对准确的 Item key")
        try:
            zabbix_call(url, "user.logout", {}, auth=auth)
        except Exception:
            pass
        return 4

    # ---------- 3) 打印样例，方便人工核对单位 ----------
    print()
    print("[3/3] 打印前 20 条（或全部，若不足 20）:")
    print(
        f"{'主机名':<28} {'key_':<28} {'raw':>14} {'换算天':>10} {'units':<8}"
    )
    print("-" * 96)

    # 同一主机可能有多个 key，这里全部列出便于挑对 key
    show = items[:20]
    for it in show:
        hosts = it.get("hosts") or []
        host_name = ""
        if hosts:
            host_name = hosts[0].get("name") or hosts[0].get("host") or ""
        host_name = host_name[:28]

        key = (it.get("key_") or "")[:28]
        raw = it.get("lastvalue") or ""
        units = it.get("units") or ""
        sec = to_seconds(raw, value_unit)
        days_str = f"{sec / DAY:.2f}" if sec is not None else "N/A"

        print(f"{host_name:<28} {key:<28} {raw:>14} {days_str:>10} {units:<8}")

    if len(items) > 20:
        print(f"... 其余 {len(items) - 20} 条已省略")

    print()
    print("核对建议:")
    print("  - 若「换算天」和机器真实 uptime 差约 100 倍 → 把 value_unit 改成 ticks")
    print("  - 若「换算天」合理（比如几十天）→ value_unit=seconds 即可")
    print("  - 记下真正在用的 key_，写回 config.json 的 item_keys")

    # ---------- 登出 ----------
    try:
        zabbix_call(url, "user.logout", {}, auth=auth)
        print()
        print("已 user.logout")
    except Exception as e:
        print(f"logout 忽略失败: {e}")

    print()
    print("测试完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
