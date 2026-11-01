"""金额与展示口径。金额一律整数分。"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

from app.errors import AppError

DepositLevel = Literal["low", "warn", "safe"]

REASON_LABELS = {
    "normal_deduct": "正常扣押",
    "manual_deduct": "手动扣押",
    "refund": "退押金",
    "add_deposit": "加押金",
    "transfer_out": "划押转出",
    "transfer_in": "划押转入",
}

INCOMING_REASONS = {"add_deposit", "transfer_in"}


def parse_yuan(text: str) -> int:
    raw = str(text).strip().replace(",", "")
    if not raw:
        raise AppError("请输入金额")
    if "e" in raw.lower():
        raise AppError("金额格式不正确")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise AppError("金额格式不正确") from exc
    if not value.is_finite():
        raise AppError("金额格式不正确")
    if value < 0:
        raise AppError("金额不能为负")
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized != value:
        raise AppError("金额最多保留两位小数")
    return int(quantized * 100)


def format_yuan(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    value = abs(int(cents))
    return f"{sign}{value // 100}.{value % 100:02d}"


def format_change(cents: int) -> str:
    return f"+{format_yuan(cents)}" if cents > 0 else format_yuan(cents)


def signed_cents(reason: str, amount_cents: int) -> int:
    return int(amount_cents) if reason in INCOMING_REASONS else -int(amount_cents)


def deposit_level(cents: int, low_cents: int, high_cents: int) -> DepositLevel:
    if cents < low_cents:
        return "low"
    if cents <= high_cents:
        return "warn"
    return "safe"


def reason_label(reason: str, counterparty_game_id: str | None = None) -> str:
    label = REASON_LABELS.get(reason, reason)
    if reason == "transfer_out":
        return f"{label} → {counterparty_game_id or '未知'}"
    if reason == "transfer_in":
        return f"{label} ← {counterparty_game_id or '未知'}"
    return label


def require_positive(amount_cents: int, message: str) -> None:
    if amount_cents <= 0:
        raise AppError(message)
