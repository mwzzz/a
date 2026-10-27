"""发卡、续期和查看：python -m license_server.issue --days 30"""

from __future__ import annotations

import argparse
from pathlib import Path

from license_server.store import CardStore


def main() -> None:
    parser = argparse.ArgumentParser(description="发放或查看卡密")
    parser.add_argument("--db", default="data/cards.db")
    parser.add_argument("--days", type=int, default=0, help="新卡的有效天数，或给已有卡增加的天数")
    parser.add_argument("--card", default="", help="要续期的卡密。不填则新发一张")
    parser.add_argument("--list", action="store_true", help="列出已有卡密")
    parser.add_argument("--trial", choices=("on", "off"), help="开启或关闭试用。试用时不填或乱填卡密也能登录")
    args = parser.parse_args()
    store = CardStore(Path(args.db))
    try:
        if args.trial:
            store.set_trial(args.trial == "on")
            print("试用已开启" if store.trial_enabled() else "试用已关闭，只接受已发放的卡密")
        if args.card and not args.days and not args.trial:
            raise SystemExit("续期需要同时写上 --days，例如 --card 卡密 --days 30")
        if args.card:
            expires_at = store.extend(args.card, args.days)
            print(f"卡密：{args.card.strip()}")
            print(f"新的到期：{expires_at}")
        elif args.days:
            card, expires_at = store.issue(args.days)
            print(f"卡密：{card}")
            print(f"到期：{expires_at}")
        if args.list or not (args.days or args.card or args.trial):
            rows = store.list_cards()
            if not rows:
                print("还没有卡密。发放示例：python -m license_server.issue --days 30")
                return
            for row in rows:
                holder = row["holder_machine_id"] or "空闲"
                print(f"{row['card']}  到期 {row['expires_at']}  占用 {holder}  心跳 {row['last_seen'] or '-'}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
