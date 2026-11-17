"""Excel 导出。玩家库只导出游戏名和押金（元）两列。"""

from __future__ import annotations

import re
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Player
from app.timeutil import now_text

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]+')


def _safe_filename_part(value: str) -> str:
    return _INVALID_FILENAME_CHARS.sub("_", (value or "").strip()) or "本店"


def build_players_xlsx(
    session: Session, merchant_id: int, merchant_name: str
) -> tuple[bytes, str]:
    players = list(
        session.scalars(
            select(Player)
            .where(
                Player.merchant_id == merchant_id,
                Player.deleted_at.is_(None),
            )
            .order_by(Player.game_id.asc())
        )
    )

    book = Workbook()
    sheet = book.active
    sheet.title = "玩家库"
    sheet.append(["游戏名", "押金(元)"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for player in players:
        sheet.append([player.game_id, player.deposit_cents / 100])
        sheet.cell(row=sheet.max_row, column=2).number_format = "0.00"

    sheet.freeze_panes = "A2"
    sheet.column_dimensions["A"].width = 32
    sheet.column_dimensions["B"].width = 14

    stream = BytesIO()
    book.save(stream)
    book.close()

    stamp = now_text()[:10].replace("-", "")
    filename = f"玩家库-{_safe_filename_part(merchant_name)}-{stamp}.xlsx"
    return stream.getvalue(), filename
