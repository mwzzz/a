"""造一份演示数据，只用于本地看界面。生产环境不要执行。

    cd backend
    DB_PATH=data/dev.db python tools/seed_demo.py

会创建：10 个玩家、一个进行中的批次、3 局场次、几笔加押金与划转。
已经有玩家时直接退出，不会重复灌数据。
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app import db  # noqa: E402
from app.deps import Actor  # noqa: E402
from app.models import Merchant, Player, User  # noqa: E402
from app.services import batches, deposits, players, sessions  # noqa: E402

CN = timezone(timedelta(hours=8))

NAMES = [
    ("等风息y", "ceb1"),
    ("Alone", "alone01"),
    ("我的少女女孩#62594", "girl62594"),
    ("励志哥", "lizhi"),
    ("张启山", "zqs"),
    ("一只鱼、#47845", "fish47845"),
    ("予我暖吻#82822", "kiss82822"),
    ("谁不重要", "who"),
    ("养了一只小鱼", "xiaoyu"),
    ("下流的喜洋洋", "xyy"),
    ("沉默冷静怡鸡", "chenmo"),
    ("美丽君、", "meili"),
]

TEAMS = [
    [0, 1, 2, 3, 4],
    [5, 6, 7, 8, 9],
    [0, 2, 4, 6, 8, 10],
    [1, 3, 5, 7, 9, 11],
]

REMARKS = ["常来", "包夜", "学生", "老客", "", "", "爱玩打野", ""]


def main() -> int:
    db.ensure_schema()
    with db.write_session() as session:
        admin = session.scalar(
            select(User).where(User.role == "admin").order_by(User.id)
        )
        if admin is None:
            print("先创建管理员：python -m app.cli create-admin --username admin")
            return 1
        merchant = session.get(Merchant, admin.merchant_id)
        if merchant is None:
            print(f"管理员 {admin.username} 没有归属商家，先跑 app.migrations")
            return 1
        existing = int(
            session.scalar(
                select(func.count())
                .select_from(Player)
                .where(Player.merchant_id == admin.merchant_id)
            )
            or 0
        )
        if existing > 0:
            print("这个商家库里已经有玩家，跳过")
            return 0
        actor = Actor(
            id=admin.id,
            username=admin.username,
            display_name=admin.display_name or admin.username,
            role=admin.role,
            merchant_id=admin.merchant_id,
            merchant_name=merchant.name,
        )

        created: list[int] = []
        for index, (name, account) in enumerate(NAMES):
            player = players.create_player(
                session,
                actor,
                game_id=name,
                account=account,
                remark=REMARKS[index % len(REMARKS)],
            )
            created.append(player.id)

        batch = batches.open_batch(session, actor, label="", note="演示数据")

        for player_id, cents in zip(created, [5000, 3300, 7250, 3100, 4700, 8900, 8750, 4200, 12500, 600, 3000, 1500]):
            deposits.add_deposit(session, actor, player_id, cents, "开卡充值")

        base = datetime.now(CN) - timedelta(hours=6)
        for index, team in enumerate(TEAMS):
            moment = (base + timedelta(minutes=47 * index)).replace(microsecond=0).isoformat()
            sessions.open_session(
                session,
                actor,
                batch_id=batch.id,
                played_at=moment,
                tea_fee_cents=200,
                player_ids=[created[i] for i in team],
                note="",
            )

        deposits.transfer(session, actor, created[0], created[7], 600, "帮朋友垫一局")
        deposits.manual_deduct(session, actor, created[9], 300, "迟到罚款")

        print(f"演示数据完成：{len(created)} 个玩家，批次 #{batch.id}，{len(TEAMS)} 局")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
