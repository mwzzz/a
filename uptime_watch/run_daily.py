#!/usr/bin/env python3
"""方案 C：sysUpTime 可疑回绕 / 临近上限巡检，每日跑一次。

用法:
  1. 本机 mock: 先 python mock_zabbix_server.py
     再 python run_daily.py --config config.local.json
  2. 生产: copy config.example.json config.json 并改配置后
     python run_daily.py
  3. 确认后把 dry_run=false、mail.enabled=true，挂计划任务
"""

from __future__ import annotations

import argparse
import json
import smtplib
import ssl
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DAY = 86400


# ---------- 配置 / 快照 ----------

def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"scraped_at": None, "hosts": {}}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(path: Path, hosts: dict[str, dict[str, Any]]) -> None:
    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "hosts": hosts,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ---------- Zabbix API ----------

def zabbix_call(url: str, method: str, params: dict, auth: str | None = None) -> Any:
    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
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
    if "error" in result:
        raise RuntimeError(f"Zabbix API error: {result['error']}")
    return result["result"]


def fetch_uptime_hosts(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """返回 [{hostid, host, name, uptime_sec, owner_email}, ...]"""
    zcfg = cfg["zabbix"]
    url = zcfg["url"]
    auth = zabbix_call(
        url,
        "user.login",
        {"username": zcfg["user"], "password": zcfg["password"]},
    )

    items = zabbix_call(
        url,
        "item.get",
        {
            "output": ["itemid", "hostid", "name", "key_", "lastvalue", "units"],
            "filter": {"key_": zcfg["item_keys"]},
            "selectHosts": ["hostid", "host", "name"],
            "monitored": True,
        },
        auth=auth,
    )

    # 可选：从 inventory 取负责人邮箱（没有也不影响）
    hostids = sorted({it["hostid"] for it in items})
    owners: dict[str, str] = {}
    if hostids:
        hosts = zabbix_call(
            url,
            "host.get",
            {
                "output": ["hostid"],
                "hostids": hostids,
                "selectInventory": ["alias", "notes", "poc_1_email", "poc_2_email"],
            },
            auth=auth,
        )
        for h in hosts:
            inv = h.get("inventory") or {}
            email = (
                (inv.get("poc_1_email") or "").strip()
                or (inv.get("poc_2_email") or "").strip()
            )
            if email:
                owners[h["hostid"]] = email

    unit = zcfg.get("value_unit", "seconds")
    out: list[dict[str, Any]] = []
    seen_host: set[str] = set()

    for it in items:
        hosts = it.get("hosts") or []
        if not hosts:
            continue
        h = hosts[0]
        hostid = h["hostid"]
        if hostid in seen_host:
            continue
        seen_host.add(hostid)

        raw = it.get("lastvalue") or ""
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue

        if unit == "ticks":
            uptime_sec = val / 100.0
        else:
            uptime_sec = val

        out.append(
            {
                "hostid": hostid,
                "host": h.get("host") or "",
                "name": h.get("name") or h.get("host") or "",
                "uptime_sec": uptime_sec,
                "owner_email": owners.get(hostid, ""),
                "item_key": it.get("key_", ""),
            }
        )

    try:
        zabbix_call(url, "user.logout", {}, auth=auth)
    except Exception:
        pass

    return out


# ---------- 规则 ----------

def sec_to_days(sec: float) -> float:
    return sec / DAY


def apply_rules(
    today_hosts: list[dict[str, Any]],
    snapshot: dict[str, Any],
    high_days: float,
    drop_curr_days: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """返回 (疑似回绕列表, 临近上限列表)"""
    prev_map: dict[str, Any] = snapshot.get("hosts") or {}
    high_sec = high_days * DAY
    drop_sec = drop_curr_days * DAY

    wrap_suspects: list[dict[str, Any]] = []
    near_limit: list[dict[str, Any]] = []

    for h in today_hosts:
        hid = h["hostid"]
        curr = h["uptime_sec"]
        prev = prev_map.get(hid)

        # 规则2：昨日很高、今日很低 → 疑似回绕
        if prev is not None:
            prev_sec = float(prev.get("uptime_sec", 0))
            if prev_sec >= high_sec and curr < drop_sec and curr < prev_sec:
                wrap_suspects.append(
                    {
                        **h,
                        "prev_uptime_sec": prev_sec,
                        "prev_days": round(sec_to_days(prev_sec), 1),
                        "curr_days": round(sec_to_days(curr), 1),
                    }
                )
                continue  # 已进 A，不必再进 B

        # 规则1：临近上限
        if curr >= high_sec:
            near_limit.append(
                {
                    **h,
                    "curr_days": round(sec_to_days(curr), 1),
                }
            )

    wrap_suspects.sort(key=lambda x: x["prev_days"], reverse=True)
    near_limit.sort(key=lambda x: x["curr_days"], reverse=True)
    return wrap_suspects, near_limit


# ---------- 邮件 ----------

def render_body(
    wrap_suspects: list[dict[str, Any]],
    near_limit: list[dict[str, Any]],
    today: str,
) -> str:
    lines = [
        f"日期: {today}",
        "",
        "本邮件不提供精确「已运行超过 497 天」列表，仅作 sysUpTime 数据质量巡检。",
        "平台上的未重启时长若基于 sysUpTime，在回绕后会不可信，请登录主机人工核对。",
        "",
        f"=== A. 疑似已回绕（优先看）共 {len(wrap_suspects)} 台 ===",
    ]
    if not wrap_suspects:
        lines.append("（无）")
    else:
        lines.append(f"{'主机':<32} {'昨日':>10} {'今日':>10} {'负责人'}")
        lines.append("-" * 72)
        for h in wrap_suspects:
            name = (h.get("name") or h.get("host") or "")[:32]
            owner = h.get("owner_email") or "-"
            lines.append(
                f"{name:<32} {h['prev_days']:>8.1f}天 {h['curr_days']:>8.1f}天 {owner}"
            )

    lines += [
        "",
        f"=== B. 临近上限（预防）共 {len(near_limit)} 台 ===",
    ]
    if not near_limit:
        lines.append("（无）")
    else:
        lines.append(f"{'主机':<32} {'当前':>10} {'负责人'}")
        lines.append("-" * 56)
        for h in near_limit:
            name = (h.get("name") or h.get("host") or "")[:32]
            owner = h.get("owner_email") or "-"
            lines.append(f"{name:<32} {h['curr_days']:>8.1f}天 {owner}")

    lines += [
        "",
        "长期建议: 可装 Agent 的机器改采 system.uptime（秒），避免 497 天 TimeTicks 回绕。",
    ]
    return "\n".join(lines)


def group_by_owner(
    wrap_suspects: list[dict[str, Any]],
    near_limit: list[dict[str, Any]],
    default_to: list[str],
) -> dict[str, tuple[list, list]]:
    """owner -> (wrap_list, near_list)。无负责人的进 default_to 第一个地址。"""
    buckets: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    fallback = default_to[0] if default_to else "ops@example.com"

    for h in wrap_suspects:
        owner = (h.get("owner_email") or "").strip() or fallback
        buckets[owner][0].append(h)
    for h in near_limit:
        owner = (h.get("owner_email") or "").strip() or fallback
        buckets[owner][1].append(h)
    return buckets


def send_mail(cfg: dict[str, Any], to_addrs: list[str], subject: str, body: str) -> None:
    mcfg = cfg["mail"]
    msg = MIMEMultipart()
    msg["From"] = mcfg["from"]
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if mcfg.get("use_ssl", True):
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(mcfg["smtp_host"], mcfg["smtp_port"], context=context) as s:
            if mcfg.get("user"):
                s.login(mcfg["user"], mcfg["password"])
            s.sendmail(mcfg["from"], to_addrs, msg.as_string())
    else:
        with smtplib.SMTP(mcfg["smtp_host"], mcfg["smtp_port"]) as s:
            s.starttls()
            if mcfg.get("user"):
                s.login(mcfg["user"], mcfg["password"])
            s.sendmail(mcfg["from"], to_addrs, msg.as_string())


# ---------- main ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="uptime 可疑回绕巡检")
    p.add_argument(
        "--config",
        default="config.json",
        help="配置文件（本机 mock 用 config.local.json）",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    if not cfg_path.exists():
        print(
            f"缺少 {cfg_path}，本机测: python run_daily.py --config config.local.json",
            file=sys.stderr,
        )
        return 1

    cfg = load_config(cfg_path)
    print(f"使用配置: {cfg_path}")
    snap_path = ROOT / cfg["snapshot"]["path"]
    snapshot = load_snapshot(snap_path)

    print("正在从 Zabbix 拉取 uptime ...")
    today_hosts = fetch_uptime_hosts(cfg)
    print(f"共 {len(today_hosts)} 台有 uptime 数据")

    rules = cfg["rules"]
    wrap_suspects, near_limit = apply_rules(
        today_hosts,
        snapshot,
        high_days=float(rules["high_days"]),
        drop_curr_days=float(rules["drop_curr_days"]),
    )

    today = date.today().isoformat()
    body = render_body(wrap_suspects, near_limit, today)
    print()
    print(body)
    print()

    dry_run = bool(cfg.get("dry_run", True))
    mail_cfg = cfg.get("mail") or {}

    if mail_cfg.get("enabled") and not dry_run:
        prefix = mail_cfg.get("subject_prefix", "[Uptime巡检]")
        total = len(wrap_suspects) + len(near_limit)
        # 按负责人拆分；也可改成只发一封给 default_to
        grouped = group_by_owner(
            wrap_suspects, near_limit, mail_cfg.get("default_to") or []
        )
        if total == 0:
            # 无异常：只通知 default_to
            to_list = mail_cfg.get("default_to") or []
            if to_list:
                subj = f"{prefix} 无异常 — {today}"
                send_mail(cfg, to_list, subj, body)
                print(f"已发「无异常」邮件 -> {to_list}")
        else:
            for owner, (w, n) in grouped.items():
                part = render_body(w, n, today)
                subj = f"{prefix} 可疑回绕/临近上限 — {today}（{len(w)+len(n)} 台）"
                # 负责人 + 抄送 default（可选：这里只发给负责人）
                recipients = [owner]
                send_mail(cfg, recipients, subj, part)
                print(f"已发邮件 -> {recipients}（A={len(w)} B={len(n)}）")
    elif dry_run:
        print("[dry_run] 未发信、未写快照。确认名单后设 dry_run: false")
    else:
        print("mail.enabled=false，跳过发信")

    if not dry_run and cfg.get("write_snapshot", True):
        hosts_snap = {
            h["hostid"]: {
                "host": h["host"],
                "name": h["name"],
                "uptime_sec": h["uptime_sec"],
                "owner_email": h.get("owner_email") or "",
            }
            for h in today_hosts
        }
        save_snapshot(snap_path, hosts_snap)
        print(f"已更新快照: {snap_path}")
    elif dry_run:
        pass
    else:
        print("write_snapshot=false，未写快照")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
