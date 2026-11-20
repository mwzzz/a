"""业务时间统一按中国时区生成，不依赖服务器时区。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

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


def parse_moment(value: str) -> datetime:
    """解析 'YYYY-MM-DD'、'YYYY-MM-DDTHH:MM[:SS]'、'YYYY-MM-DD HH:MM'，缺时区按东八区。"""
    text = (value or "").strip()
    if not text:
        raise ValueError("时间不能为空")
    if len(text) == 10:
        day = date.fromisoformat(text)
        return datetime(day.year, day.month, day.day, tzinfo=CN_TZ)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text.replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CN_TZ)
    return parsed.astimezone(CN_TZ).replace(microsecond=0)


def parse_end_moment(value: str) -> datetime:
    """区间右端点：左右闭合，按用户给的精度补到该精度的最后一秒。

    纯日期补 23:59:59、分钟补 :59，否则原样解析。少了这一步，
    `...T23:59` 会变成 23:59:00，23:59:01~59 的场次两头都不在区间内。
    """
    text = (value or "").strip()
    if len(text) == 10:
        text += "T23:59:59"
    elif len(text) == 16:
        text += ":59"
    return parse_moment(text)


def moment_bounds(
    date_from: str | None,
    date_to: str | None,
    default_day: date | None = None,
) -> tuple[str, str]:
    """把区间参数规整成左右闭合的 ISO 文本。

    - 只给一头：另一端落在 `default_day`（默认今天）的 00:00:00 / 23:59:59
    - 纯日期：补 00:00:00 / 23:59:59
    - 精确到分钟：补到该分钟末
    """
    base = default_day or now_cn().date()
    if date_from:
        start_dt = parse_moment(date_from)
    else:
        start_dt = datetime(base.year, base.month, base.day, tzinfo=CN_TZ)

    if date_to:
        end_dt = parse_end_moment(date_to)
    else:
        end_dt = datetime(base.year, base.month, base.day, 23, 59, 59, tzinfo=CN_TZ)

    if end_dt < start_dt:
        raise ValueError("结束时间不能早于开始时间")
    return to_text(start_dt), to_text(end_dt)


def bound_start_text(value: str) -> str:
    """区间起点：纯日期补 00:00:00。"""
    return to_text(parse_moment(value))


def bound_end_text(value: str) -> str:
    """区间终点：补到该精度的最后一秒。"""
    return to_text(parse_end_moment(value))


def bound_start_text_safe(value: str | None) -> str | None:
    """读取历史行用的容错版：解析不了返回 None，由调用方跳过而不是整页 500。"""
    try:
        return bound_start_text(value or "")
    except ValueError:
        logger.warning("无法解析的区间起点：%r", value)
        return None


def bound_end_text_safe(value: str | None) -> str | None:
    """读取历史行用的容错版：解析不了返回 None，由调用方跳过而不是整页 500。"""
    try:
        return bound_end_text(value or "")
    except ValueError:
        logger.warning("无法解析的区间终点：%r", value)
        return None


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
