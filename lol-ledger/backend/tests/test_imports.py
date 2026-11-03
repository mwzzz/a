"""Excel 批量导入玩家：格式、押金、整批校验。"""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from tests.test_players import add_money, new_player


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def _upload(client, headers, content: bytes, filename: str = "players.xlsx"):
    return client.post(
        "/api/v1/players/import",
        files={
            "file": (
                filename,
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )


def _players(client, headers) -> dict:
    return client.get(
        "/api/v1/players", params={"page_size": 50}, headers=headers
    ).json()


def test_import_xlsx_with_header_and_deposit(client, admin_headers) -> None:
    content = _xlsx(
        [
            ["玩家id", "押金"],
            ["导入甲", 100],
            ["导入乙", None],
            ["导入丙", 0],
        ]
    )
    response = _upload(client, admin_headers, content)
    assert response.status_code == 200, response.text
    assert response.json() == {"created": 3, "deposited_cents": 10000}

    body = _players(client, admin_headers)
    assert body["total"] == 3
    rows = {row["game_id"]: row for row in body["items"]}
    assert rows["导入甲"]["deposit_cents"] == 10000
    assert rows["导入乙"]["deposit_cents"] == 0
    assert rows["导入丙"]["deposit_cents"] == 0

    ledger = client.get(
        f"/api/v1/players/{rows['导入甲']['id']}/ledger", headers=admin_headers
    ).json()
    assert ledger["total"] == 1
    assert ledger["items"][0]["reason"] == "add_deposit"
    assert ledger["items"][0]["note"] == "Excel 批量导入"


def test_import_without_header_and_numeric_id(client, admin_headers) -> None:
    content = _xlsx([[12345.0, 50.5]])
    response = _upload(client, admin_headers, content)
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1

    row = _players(client, admin_headers)["items"][0]
    assert row["game_id"] == "12345"
    assert row["deposit_cents"] == 5050


def test_import_existing_player_rejected_atomically(client, admin_headers) -> None:
    new_player(client, admin_headers, "已存在")
    content = _xlsx(
        [
            ["新人", 100],
            ["已存在", 0],
        ]
    )
    response = _upload(client, admin_headers, content)
    assert response.status_code == 400
    body = response.json()
    assert "1 行有问题" in body["detail"]
    assert body["errors"][0]["row"] == 2
    assert "已存在" in body["errors"][0]["message"]
    names = {item["game_id"] for item in _players(client, admin_headers)["items"]}
    assert names == {"已存在"}


def test_import_duplicate_in_file_rejected(client, admin_headers) -> None:
    content = _xlsx([["重复", 100], ["重复", 200]])
    response = _upload(client, admin_headers, content)
    assert response.status_code == 400
    assert "重复" in response.json()["errors"][0]["message"]
    assert _players(client, admin_headers)["total"] == 0


def test_import_negative_and_precision_rejected(client, admin_headers) -> None:
    for bad in (-1, 1.234):
        content = _xlsx([["坏人", bad]])
        response = _upload(client, admin_headers, content)
        assert response.status_code == 400, bad
        assert "押金" in response.json()["errors"][0]["message"]
        assert _players(client, admin_headers)["total"] == 0


def test_import_bad_extension_and_empty_file(client, admin_headers) -> None:
    bad = _upload(
        client,
        admin_headers,
        "a,b\n1,2".encode(),
        filename="players.csv",
    )
    assert bad.status_code == 400
    assert "只支持 Excel" in bad.json()["detail"]

    empty = _upload(client, admin_headers, _xlsx([]))
    assert empty.status_code == 400
    assert "没有读到玩家数据" in empty.json()["detail"]


def test_import_staff_allowed(client, staff_headers) -> None:
    response = _upload(client, staff_headers, _xlsx([["店员导入", 20]]))
    assert response.status_code == 200, response.text
    assert _players(client, staff_headers)["total"] == 1


def test_import_legacy_xls(client, admin_headers) -> None:
    xlwt = pytest.importorskip("xlwt")
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("玩家")
    sheet.write(0, 0, "玩家id")
    sheet.write(0, 1, "押金")
    sheet.write(1, 0, "老格式")
    sheet.write(1, 1, 30)
    buffer = BytesIO()
    workbook.save(buffer)

    response = _upload(
        client,
        admin_headers,
        buffer.getvalue(),
        filename="players.xls",
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"created": 1, "deposited_cents": 3000}

    row = _players(client, admin_headers)["items"][0]
    assert row["game_id"] == "老格式"
    assert row["deposit_cents"] == 3000


def test_import_zero_deposit_has_no_ledger(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "只建号")
    add_money(client, admin_headers, player["id"], 100)
    response = _upload(client, admin_headers, _xlsx([["零押金", ""]]))
    assert response.status_code == 200
    row = next(
        item
        for item in _players(client, admin_headers)["items"]
        if item["game_id"] == "零押金"
    )
    ledger = client.get(
        f"/api/v1/players/{row['id']}/ledger", headers=admin_headers
    ).json()
    assert ledger["total"] == 0
