"""AI 截图识别：匹配、空位、异常与限流。"""

from __future__ import annotations

import base64

import pytest

from app.config import settings
from app.services import ai_recognition
from tests.test_players import new_player

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z0YQAAAAASUVORK5CYII="
)

SCREENSHOT_NAMES = [
    "中山刘德华、",
    "u小哥",
    "cat",
    "迪拜Music",
    "等我c那就寄",
    "小小狮子king",
    "奇迹行者",
    "EightySix剑士",
    "江南、大蛇",
]


@pytest.fixture(autouse=True)
def _reset_rate() -> None:
    ai_recognition.reset_rate_limit()
    yield
    ai_recognition.reset_rate_limit()


def _model_returns(monkeypatch, names: list[str], **extra) -> None:
    rows = [
        {
            "name": name,
            "tag": None,
            "team": 1,
            "confidence": 0.9,
            **extra,
        }
        for name in names
    ]

    def fake(_image: bytes, _mime: str) -> list[dict]:
        return rows

    monkeypatch.setattr(ai_recognition, "_call_model", fake)


def _upload(client, headers, content: bytes = PNG, filename: str = "shot.png"):
    return client.post(
        "/api/v1/ai/recognize-players",
        files={"file": (filename, content, "image/png")},
        headers=headers,
    )


def test_recognize_nine_players_and_ignore_ui_text(
    client, admin_headers, monkeypatch
) -> None:
    for name in SCREENSHOT_NAMES:
        new_player(client, admin_headers, name)
    _model_returns(
        monkeypatch,
        SCREENSHOT_NAMES + ["空", "邀请玩家", "队伍1"],
    )

    response = _upload(client, admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 9
    assert all(item["status"] == "matched" for item in body["items"])
    assert [item["raw_name"] for item in body["items"]] == SCREENSHOT_NAMES
    assert body["warnings"] == ["识别到 9 个玩家，请确认是否完整"]
    assert body["items"][0]["matched_player"]["game_id"] == "中山刘德华、"


def test_tag_and_fuzzy_and_unmatched(client, admin_headers, monkeypatch) -> None:
    tagged = new_player(client, admin_headers, "小明#1234")["id"]
    fuzzy = new_player(client, admin_headers, "江南大蛇")["id"]
    loose = new_player(client, admin_headers, "小明爱猫")["id"]
    _model_returns(monkeypatch, ["小明", "江南、大蛇", "小明爱狗", "完全新人"])

    body = _upload(client, admin_headers).json()
    assert body["items"][0]["status"] == "matched"
    assert body["items"][0]["matched_player"]["id"] == tagged

    assert body["items"][1]["status"] == "matched"
    assert body["items"][1]["matched_player"]["id"] == fuzzy

    assert body["items"][2]["status"] == "ambiguous"
    assert body["items"][2]["candidates"][0]["player"]["id"] == loose
    assert body["items"][2]["candidates"][0]["score"] >= 0.72

    assert body["items"][3]["status"] == "unmatched"
    assert body["items"][3]["candidates"] == []


def test_fuzzy_at_eighty_percent_is_matched(
    client, admin_headers, monkeypatch
) -> None:
    player_id = new_player(client, admin_headers, "专属丶黑店")["id"]
    _model_returns(monkeypatch, ["专属、黑店"])

    item = _upload(client, admin_headers).json()["items"][0]
    assert item["status"] == "matched"
    assert item["matched_player"]["id"] == player_id


def test_model_retry_on_broken_json(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, content: str) -> None:
            self.status_code = 200
            self._content = content

        def json(self) -> dict:
            return {"choices": [{"message": {"content": self._content}}]}

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            calls.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

        def post(self, *args, **kwargs) -> FakeResponse:
            if len(calls) == 1:
                return FakeResponse("not json")
            return FakeResponse(
                '{"players":[{"name":"猫","team":1,"confidence":0.9}]}'
            )

    monkeypatch.setattr(ai_recognition.httpx, "Client", FakeClient)
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    rows = ai_recognition._call_model(PNG, "image/png")
    assert len(calls) == 2
    assert calls[0]["trust_env"] is False
    assert rows[0]["name"] == "猫"


def test_thinking_flag_is_optional(monkeypatch) -> None:
    payloads: list[dict] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"players":[{"name":"猫","team":1,"confidence":0.9}]}'
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

        def post(self, *args, **kwargs) -> FakeResponse:
            payloads.append(kwargs["json"])
            return FakeResponse()

    monkeypatch.setattr(ai_recognition.httpx, "Client", FakeClient)
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    monkeypatch.setattr(settings, "ai_enable_thinking", False)
    ai_recognition._call_model(PNG, "image/png")
    assert payloads[-1]["enable_thinking"] is False

    payloads.clear()
    monkeypatch.setattr(settings, "ai_enable_thinking", None)
    ai_recognition._call_model(PNG, "image/png")
    assert "enable_thinking" not in payloads[-1]


def test_same_name_is_ambiguous(client, admin_headers, monkeypatch) -> None:
    first = new_player(client, admin_headers, "Cat")["id"]
    second = new_player(client, admin_headers, "cat")["id"]
    _model_returns(monkeypatch, ["CAT"])

    item = _upload(client, admin_headers).json()["items"][0]
    assert item["status"] == "ambiguous"
    assert {candidate["player"]["id"] for candidate in item["candidates"]} == {
        first,
        second,
    }


def test_more_than_ten_is_truncated(client, admin_headers, monkeypatch) -> None:
    names = [f"玩家{i}" for i in range(11)]
    _model_returns(monkeypatch, names)
    body = _upload(client, admin_headers).json()
    assert body["count"] == 10
    assert "超过 10 人" in body["warnings"][0]


def test_model_json_fences_and_bad_json(monkeypatch) -> None:
    parsed = ai_recognition._parse_model_content(
        '```json\n{"players":[{"name":"猫","team":1,"confidence":0.8}]}\n```'
    )
    assert parsed[0]["name"] == "猫"

    with pytest.raises(ai_recognition.AiResponseError):
        ai_recognition._parse_model_content("not json")


def test_disabled_without_key(client, admin_headers, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "ai_api_key", "")
    status = client.get("/api/v1/ai/status", headers=admin_headers).json()
    assert status == {"enabled": False, "model": ""}

    response = _upload(client, admin_headers)
    assert response.status_code == 503
    assert "未启用" in response.json()["detail"]


def test_invalid_image_and_size(client, admin_headers, monkeypatch) -> None:
    _model_returns(monkeypatch, ["猫"])
    bad = _upload(client, admin_headers, b"not an image", "shot.txt")
    assert bad.status_code == 400
    assert "jpg" in bad.json()["detail"]

    huge = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    response = _upload(client, admin_headers, huge)
    assert response.status_code == 400
    assert "5MB" in response.json()["detail"]


def test_requires_login(client) -> None:
    response = client.post(
        "/api/v1/ai/recognize-players",
        files={"file": ("shot.png", PNG, "image/png")},
    )
    assert response.status_code == 401


def test_cannot_match_other_merchant(client, admin_headers, admin_b_headers, monkeypatch) -> None:
    new_player(client, admin_headers, "甲店的人")
    _model_returns(monkeypatch, ["甲店的人"])
    item = _upload(client, admin_b_headers).json()["items"][0]
    assert item["status"] == "unmatched"


def test_rate_limit(client, admin_headers, monkeypatch) -> None:
    _model_returns(monkeypatch, ["猫"])
    for _ in range(10):
        assert _upload(client, admin_headers).status_code == 200
    blocked = _upload(client, admin_headers)
    assert blocked.status_code == 429
    assert "频繁" in blocked.json()["detail"]


def test_matched_player_includes_blacklist_flag(
    client, admin_headers, monkeypatch
) -> None:
    new_player(client, admin_headers, "黑名单AI哥", is_blacklisted=True)
    _model_returns(monkeypatch, ["黑名单AI哥"])
    item = _upload(client, admin_headers).json()["items"][0]
    assert item["status"] == "matched"
    assert item["matched_player"]["is_blacklisted"] is True
