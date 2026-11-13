"""分红计算口径。取消班次后仍然保留「按比例」和「每局固定」两种算法。"""

from __future__ import annotations

MODE_PERCENT = "percent"
MODE_FIXED = "fixed"


def dividend_cents(tea_cents: int, rate_percent: int) -> int:
    """按茶水比例分红，按分计算，四舍五入到分。"""
    return (int(tea_cents) * int(rate_percent) + 50) // 100


def fixed_dividend_cents(session_count: int, unit_cents: int) -> int:
    """按局固定分红：局数 × 每局金额。"""
    return max(0, int(session_count)) * max(0, int(unit_cents))


def dividend_by_mode(
    session_count: int,
    tea_cents: int,
    mode: str | None,
    rate_percent: int,
    fixed_cents: int,
) -> int:
    if (mode or MODE_PERCENT) == MODE_FIXED:
        return fixed_dividend_cents(session_count, fixed_cents)
    return dividend_cents(tea_cents, rate_percent)
