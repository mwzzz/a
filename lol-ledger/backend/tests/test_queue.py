"""排队登记（小工具）接口测试。"""

from __future__ import annotations


def _add(client, headers, name: str, note: str = ""):
    return client.post("/api/v1/queue", json={"game_id": name, "note": note}, headers=headers)


def _status(client, headers, entry_id: int, status: str):
    return client.patch(f"/api/v1/queue/{entry_id}", json={"status": status}, headers=headers)


def test_create_and_list(client, admin_headers, admin) -> None:
    response = _add(client, admin_headers, "等风息y", "想坐 3 号机")
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry["game_id"] == "等风息y"
    assert entry["status"] == "waiting"
    assert entry["status_label"] == "排队中"
    assert entry["note"] == "想坐 3 号机"
    assert entry["operator"]["id"] == admin["id"]

    data = client.get("/api/v1/queue", headers=admin_headers).json()
    assert data["counts"]["waiting"] == 1
    assert len(data["entries"]) == 1
    assert data["shop_name"] == "默认商家"
    assert data["date"]


def test_duplicate_name_rejected(client, admin_headers) -> None:
    assert _add(client, admin_headers, "励志哥").status_code == 201
    again = _add(client, admin_headers, "励志哥")
    assert again.status_code == 400
    assert "已经在队列里" in again.json()["detail"]


def test_same_name_allowed_after_done(client, admin_headers) -> None:
    first = _add(client, admin_headers, "张启山").json()
    assert _status(client, admin_headers, first["id"], "cancelled").status_code == 200
    assert _add(client, admin_headers, "张启山").status_code == 201


def test_validation(client, admin_headers) -> None:
    assert client.post("/api/v1/queue", json={"game_id": ""}, headers=admin_headers).status_code == 422
    assert (
        client.post("/api/v1/queue", json={"game_id": "x" * 65}, headers=admin_headers).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/queue",
            json={"game_id": "正常名字", "note": "x" * 101},
            headers=admin_headers,
        ).status_code
        == 422
    )


def test_status_flow(client, admin_headers) -> None:
    entry = _add(client, admin_headers, "Alone").json()

    playing = _status(client, admin_headers, entry["id"], "playing")
    assert playing.status_code == 200
    assert playing.json()["status"] == "playing"
    assert playing.json()["called_at"]

    done = _status(client, admin_headers, entry["id"], "done")
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    assert done.json()["finished_at"]

    # 终态不能再改
    assert _status(client, admin_headers, entry["id"], "playing").status_code == 400


def test_illegal_transition(client, admin_headers) -> None:
    entry = _add(client, admin_headers, "跳跃哥").json()
    response = _status(client, admin_headers, entry["id"], "done")
    assert response.status_code == 400
    assert "不能从" in response.json()["detail"]

    assert _status(client, admin_headers, entry["id"], "waiting").status_code == 400
    assert _status(client, admin_headers, entry["id"], "unknown").status_code == 422


def test_cancel_waiting(client, admin_headers) -> None:
    entry = _add(client, admin_headers, "临时不来").json()
    response = _status(client, admin_headers, entry["id"], "cancelled")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_staff_can_use(client, staff_headers, admin_headers) -> None:
    response = _add(client, staff_headers, "店员登记")
    assert response.status_code == 201
    entry = response.json()
    assert _status(client, staff_headers, entry["id"], "playing").status_code == 200

    data = client.get("/api/v1/queue", headers=admin_headers).json()
    assert any(item["game_id"] == "店员登记" for item in data["entries"])


def test_merchant_isolation(client, admin_headers, admin_b_headers) -> None:
    entry = _add(client, admin_headers, "甲店客人").json()

    other = client.get("/api/v1/queue", headers=admin_b_headers).json()
    assert other["entries"] == []

    assert _status(client, admin_b_headers, entry["id"], "playing").status_code == 404
    assert client.get("/api/v1/queue/9999", headers=admin_headers).status_code in (200, 404, 405)


def test_snapshot(client, admin_headers) -> None:
    _add(client, admin_headers, "快照甲")
    _add(client, admin_headers, "快照乙")
    data = client.get("/api/v1/queue/snapshot", headers=admin_headers).json()
    assert data["shop_name"] == "默认商家"
    assert data["counts"]["waiting"] == 2
    assert data["updated_at"]


def test_requires_login(client) -> None:
    assert client.get("/api/v1/queue").status_code == 401
    assert client.post("/api/v1/queue", json={"game_id": "匿名"}).status_code == 401
