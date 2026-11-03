"""模型识别结果清洗与玩家库匹配。纯计算，不发起网络请求。"""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.models import Player

FUZZY_THRESHOLD = 0.72

STOPWORDS = {
    "空",
    "空位",
    "加入",
    "邀请",
    "邀请玩家",
    "观战",
    "观战者",
    "队伍1",
    "队伍2",
    "队伍一",
    "队伍二",
    "玩家",
    "房间",
}


def clean_name(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\u200b", "").replace("\ufeff", "").strip()


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", clean_name(value))
    text = " ".join(text.split())
    return text.casefold()


def base_name(value: object) -> str:
    return normalize_name(clean_name(value).split("#", 1)[0])


def player_ref(player: Player) -> dict:
    return {
        "id": player.id,
        "game_id": player.game_id,
        "account": player.account,
        "deposit_cents": player.deposit_cents,
    }


def filter_recognized(rows: list[dict]) -> list[dict]:
    """过滤界面词和重复名字，并统一字段类型。"""
    result: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        name = clean_name(row.get("name"))
        if not name or normalize_name(name) in STOPWORDS:
            continue
        key = normalize_name(name)
        if key in seen:
            continue
        seen.add(key)
        team = row.get("team")
        if team not in (1, 2):
            team = None
        confidence = row.get("confidence")
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = None
        result.append(
            {
                "name": name,
                "tag": clean_name(row.get("tag")) or None,
                "team": team,
                "confidence": confidence,
            }
        )
    return result


def fuzzy_score(recognized: dict, player: Player) -> float:
    full = normalize_name(recognized["name"])
    base = base_name(recognized["name"])
    player_full = normalize_name(player.game_id)
    player_base = base_name(player.game_id)
    return max(
        SequenceMatcher(None, full, player_full).ratio(),
        SequenceMatcher(None, base, player_base).ratio(),
        SequenceMatcher(None, full, player_base).ratio(),
    )


def match_players(session: Session, actor: Actor, recognized: list[dict]) -> list[dict]:
    players = list(
        session.scalars(
            select(Player).where(
                Player.merchant_id == actor.merchant_id,
                Player.deleted_at.is_(None),
            )
        )
    )
    items: list[dict] = []

    for row in recognized:
        full = normalize_name(row["name"])
        base = base_name(row["name"])
        exact_unique = {
            player.id: player
            for player in players
            if normalize_name(player.game_id) == full
            or base_name(player.game_id) == base
        }

        if len(exact_unique) == 1:
            player = next(iter(exact_unique.values()))
            items.append(
                {
                    "raw_name": row["name"],
                    "status": "matched",
                    "confidence": row["confidence"],
                    "team": row["team"],
                    "matched_player": player_ref(player),
                    "candidates": [],
                }
            )
            continue

        if len(exact_unique) > 1:
            items.append(
                {
                    "raw_name": row["name"],
                    "status": "ambiguous",
                    "confidence": row["confidence"],
                    "team": row["team"],
                    "matched_player": None,
                    "candidates": [
                        {"player": player_ref(player), "score": 1.0}
                        for player in exact_unique.values()
                    ],
                }
            )
            continue

        scored = sorted(
            ((player, fuzzy_score(row, player)) for player in players),
            key=lambda item: item[1],
            reverse=True,
        )
        candidates = [
            {"player": player_ref(player), "score": round(score, 3)}
            for player, score in scored[:3]
            if score >= FUZZY_THRESHOLD
        ]
        items.append(
            {
                "raw_name": row["name"],
                "status": "ambiguous" if candidates else "unmatched",
                "confidence": row["confidence"],
                "team": row["team"],
                "matched_player": None,
                "candidates": candidates,
            }
        )

    return items
