"""业务时间统一按中国时区生成，不依赖服务器时区。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

CN_TZ = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    return datetime.now(CN_TZ).replace(microsecond=0)


def now_text() -> str:
    """2026-10-30T20:04:12+08:00，字典序即时间序。"""
    return now_cn().isoformat()


def to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=CN_TZ)
    return value.astimezone(CN_TZ).replace(microsecond=0).isoformat()


def parse_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CN_TZ)
    return parsed


def day_start_text(day: date) -> str:
    return datetime(day.year, day.month, day.day, tzinfo=CN_TZ).isoformat()


def day_after_text(day: date) -> str:
    start = datetime(day.year, day.month, day.day, tzinfo=CN_TZ) + timedelta(days=1)
    return start.isoformat()


def today_bounds() -> tuple[str, str]:
    today = now_cn().date()
    return day_start_text(today), day_after_text(today)


def normalize_played_at(value: str | None) -> str:
    """前端传 ISO 或 'YYYY-MM-DD HH:MM'，统一成带 +08:00 的文本。"""
    if not value:
        return now_text()
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:  # pragma: no cover - 由接口层兜底
        raise ValueError("场次时间格式不正确") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CN_TZ)
    return to_text(parsed)
