"""常用名单（小工具）接口测试。"""

from __future__ import annotations

BASE = "/api/v1/tools/name-lists"


def _lists(client, headers) -> list[dict]:
    return client.get(BASE, headers=headers).json()["lists"]


def _first(client, headers, name: str) -> dict:
    return next(item for item in _lists(client, headers) if item["name"] == name)


def test_preset_lists(client, admin_headers) -> None:
    lists = _lists(client, admin_headers)
    assert [item["name"] for item in lists] == ["打手", "免茶水", "每天up", "免押金"]

    hand = next(item for item in lists if item["name"] == "打手")
    assert [row["content"] for row in hand["items"]] == ["能天使", "浮沉野马"]

    free_tea = next(item for item in lists if item["name"] == "免茶水")
    assert free_tea["items"] == []

    deposit = next(item for item in lists if item["name"] == "免押金")
    assert len(deposit["items"]) == 10
    assert deposit["items"][0]["content"] == "江南"
    assert deposit["items"][-1]["content"] == "海哥调料"


def test_create_and_rename_list(client, admin_headers) -> None:
    created = client.post(BASE, json={"name": "替补"}, headers=admin_headers)
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "替补"

    dup = client.post(BASE, json={"name": "替补"}, headers=admin_headers)
    assert dup.status_code == 400
    assert "已经存在" in dup.json()["detail"]

    list_id = created.json()["id"]
    renamed = client.patch(f"{BASE}/{list_id}", json={"name": "替补席"}, headers=admin_headers)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "替补席"

    clash = client.patch(f"{BASE}/{list_id}", json={"name": "打手"}, headers=admin_headers)
    assert clash.status_code == 400


def test_delete_list_cascades(client, admin_headers) -> None:
    target = _first(client, admin_headers, "打手")
    response = client.delete(f"{BASE}/{target['id']}", headers=admin_headers)
    assert response.status_code == 200

    lists = _lists(client, admin_headers)
    assert "打手" not in [item["name"] for item in lists]

    left = client.get(BASE, headers=admin_headers).json()["lists"]
    total_items = sum(len(item["items"]) for item in left)
    assert total_items == 15


def test_item_crud_and_reorder(client, admin_headers) -> None:
    target = _first(client, admin_headers, "打手")
    list_id = target["id"]

    added = client.post(
        f"{BASE}/{list_id}/items",
        json={"content": "新打手", "note": "周末来"},
        headers=admin_headers,
    )
    assert added.status_code == 201, added.text
    item_id = added.json()["id"]
    assert added.json()["sort_order"] == 2

    updated = client.patch(
        f"{BASE}/{list_id}/items/{item_id}",
        json={"content": "改名打手"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "改名打手"

    moved = client.post(
        f"{BASE}/{list_id}/items/{item_id}/move",
        json={"direction": "up"},
        headers=admin_headers,
    )
    assert moved.status_code == 200
    assert moved.json()["sort_order"] == 1

    detail = _first(client, admin_headers, "打手")
    assert [row["content"] for row in detail["items"]] == ["能天使", "改名打手", "浮沉野马"]

    removed = client.delete(f"{BASE}/{list_id}/items/{item_id}", headers=admin_headers)
    assert removed.status_code == 200
    detail = _first(client, admin_headers, "打手")
    assert [row["content"] for row in detail["items"]] == ["能天使", "浮沉野马"]
    assert [row["sort_order"] for row in detail["items"]] == [0, 1]


def test_empty_and_limits(client, admin_headers) -> None:
    assert client.post(BASE, json={"name": "  "}, headers=admin_headers).status_code == 400

    target = _first(client, admin_headers, "打手")
    blank = client.post(
        f"{BASE}/{target['id']}/items", json={"content": "   "}, headers=admin_headers
    )
    assert blank.status_code in (400, 422)

    long_note = client.post(
        f"{BASE}/{target['id']}/items",
        json={"content": "某人", "note": "x" * 101},
        headers=admin_headers,
    )
    assert long_note.status_code == 422


def test_staff_can_edit(client, staff_headers) -> None:
    created = client.post(BASE, json={"name": "店员加的"}, headers=staff_headers)
    assert created.status_code == 201
    item = client.post(
        f"{BASE}/{created.json()['id']}/items",
        json={"content": "店员条目"},
        headers=staff_headers,
    )
    assert item.status_code == 201


def test_merchant_isolation(client, admin_headers, admin_b_headers) -> None:
    target = _first(client, admin_headers, "打手")

    # 测试里的第二个商家是直接插库建的，不带预置；它自己新建的名单不能串到第一家
    assert _lists(client, admin_b_headers) == []
    created = client.post(BASE, json={"name": "乙店名单"}, headers=admin_b_headers)
    assert created.status_code == 201
    other = _lists(client, admin_b_headers)
    assert [item["name"] for item in other] == ["乙店名单"]
    assert other[0]["id"] != target["id"]

    assert (
        client.patch(
            f"{BASE}/{target['id']}", json={"name": "越权改名"}, headers=admin_b_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"{BASE}/{target['id']}", headers=admin_b_headers).status_code == 404
    )
    assert (
        client.post(
            f"{BASE}/{target['id']}/items",
            json={"content": "越权条目"},
            headers=admin_b_headers,
        ).status_code
        == 404
    )


def test_requires_login(client) -> None:
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json={"name": "匿名"}).status_code == 401
