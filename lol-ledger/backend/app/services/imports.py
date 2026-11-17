"""Excel 批量导入玩家。第一列游戏 id，第二列押金（元，可空）。

整批校验通过才写入，任何一行有问题都不导入，避免导入一半。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session
from xlrd import open_workbook

from app.deps import Actor
from app.errors import AppError
from app.models import Player
from app.services import deposits
from app.services import players as player_service

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 1000
MAX_REPORTED_ERRORS = 100

HEADER_IDS = {
    "id",
    "game_id",
    "gameid",
    "玩家id",
    "玩家编号",
    "游戏id",
    "游戏名",
    "玩家",
}


class ImportValidationError(AppError):
    """带行号明细的导入错误。"""

    def __init__(self, errors: list[dict], message: str) -> None:
        super().__init__(message)
        self.errors = errors


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return format(value, ".15g")
    if isinstance(value, int):
        return str(value)
    return str(value).strip()


def _load_rows(filename: str, content: bytes) -> list[list[object]]:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in (".xls", ".xlsx"):
        raise AppError("只支持 Excel 文件（.xls 或 .xlsx）")
    if not content:
        raise AppError("文件是空的")
    if len(content) > MAX_FILE_BYTES:
        raise AppError("文件不能超过 5MB")

    try:
        if suffix == ".xlsx":
            workbook = load_workbook(
                BytesIO(content), read_only=True, data_only=True
            )
            try:
                if not workbook.worksheets:
                    raise AppError("Excel 里没有工作表")
                sheet = workbook.worksheets[0]
                return [list(row) for row in sheet.iter_rows(values_only=True)]
            finally:
                workbook.close()

        book = open_workbook(file_contents=content)
        if book.nsheets == 0:
            raise AppError("Excel 里没有工作表")
        sheet = book.sheet_by_index(0)
        return [
            [sheet.cell_value(row_index, col) for col in range(sheet.ncols)]
            for row_index in range(sheet.nrows)
        ]
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001 - 解析库异常类型很杂
        raise AppError("Excel 解析失败，请确认文件没有损坏且格式正确") from exc


def _is_header(row: list[object]) -> bool:
    first = _text(row[0]).lower().replace(" ", "") if row else ""
    second = _text(row[1]).lower() if len(row) > 1 else ""
    return first in HEADER_IDS or "押金" in second or "deposit" in second


def _parse_cents(value: object) -> int:
    text = (
        _text(value)
        .replace(",", "")
        .replace("￥", "")
        .replace("¥", "")
        .strip()
    )
    if not text:
        return 0
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("押金不是有效数字") from exc
    if not amount.is_finite():
        raise ValueError("押金不是有效数字")
    if amount < 0:
        raise ValueError("押金不能为负数")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("押金最多两位小数")
    return int(amount * 100)


def import_players(
    session: Session,
    actor: Actor,
    *,
    filename: str,
    content: bytes,
    ip: str = "",
) -> dict:
    rows = _load_rows(filename, content)

    existing = set(
        session.scalars(
            select(Player.game_id).where(
                Player.merchant_id == actor.merchant_id,
                Player.deleted_at.is_(None),
            )
        )
    )

    items: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    first_row = True
    processed = 0

    for index, row in enumerate(rows, start=1):
        values = list(row or [])
        if not values or all(_text(value) == "" for value in values):
            continue
        if first_row and _is_header(values):
            first_row = False
            continue
        first_row = False

        processed += 1
        if processed > MAX_ROWS:
            errors.append({"row": index, "message": f"最多一次导入 {MAX_ROWS} 行"})
            break

        try:
            game_id = player_service.normalize_game_id(_text(values[0]))
        except AppError as exc:
            errors.append({"row": index, "message": str(exc)})
            continue

        deposit_raw = values[1] if len(values) > 1 else ""
        try:
            deposit_cents = _parse_cents(deposit_raw)
        except ValueError as exc:
            errors.append({"row": index, "message": f"押金：{exc}"})
            continue

        if game_id in seen:
            errors.append({"row": index, "message": f"文件内游戏 id 重复：{game_id}"})
            continue
        if game_id in existing:
            errors.append({"row": index, "message": f"游戏 id 已存在：{game_id}"})
            continue

        seen.add(game_id)
        items.append({"game_id": game_id, "deposit_cents": deposit_cents})

    if errors:
        raise ImportValidationError(
            errors[:MAX_REPORTED_ERRORS],
            f"共 {len(errors)} 行有问题，未导入任何数据",
        )
    if not items:
        raise AppError("没有读到玩家数据，请检查第一列是不是游戏 id")

    created = 0
    deposited_cents = 0
    for item in items:
        player = player_service.create_player(
            session,
            actor,
            game_id=item["game_id"],
            ip=ip,
        )
        player_id = player.id
        created += 1
        if item["deposit_cents"] > 0:
            deposits.add_deposit(
                session,
                actor,
                player_id,
                item["deposit_cents"],
                note="Excel 批量导入",
                apply_campaign=False,
            )
            deposited_cents += item["deposit_cents"]

    return {
        "created": created,
        "deposited_cents": deposited_cents,
    }
