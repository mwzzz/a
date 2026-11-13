"""上游客户端：签名算法、code=2 友好提示、code=6 重登重试、结果缓存。"""

from __future__ import annotations

import hashlib
from datetime import datetime

import pytest

from app.config import settings
from app.services import zjyumi


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    monkeypatch.setattr(settings, "lzyumi_user", "u1")
    monkeypatch.setattr(settings, "lzyumi_pwd", "p1")
    monkeypatch.setattr(settings, "lzyumi_token", "")
    monkeypatch.setattr(settings, "zj_cache_ttl_seconds", 300)
    monkeypatch.setattr(settings, "zj_min_interval_seconds", 0.0)
    monkeypatch.setattr(zjyumi, "current_token", lambda force_refresh=False: "token-a")
    zjyumi.reset_state()
    yield
    zjyumi.reset_state()


def test_build_sign_matches_frontend_formula() -> None:
    moment = datetime(2026, 11, 5, 16, 3, 7, tzinfo=zjyumi.CN_TZ)

    sign, sign_str = zjyumi.build_sign(moment)

    assert sign == hashlib.md5(b"d11o05u16d03o07d").hexdigest()
    # 不补零拼接 11/5/16/3/7，再拼每段长度的 3 倍（6/3/6/3/3）
    assert sign_str == "115163763633"


def test_not_configured_returns_503(monkeypatch) -> None:
    monkeypatch.setattr(settings, "lzyumi_user", "")
    monkeypatch.setattr(settings, "lzyumi_pwd", "")

    with pytest.raises(zjyumi.ZjNotConfigured) as exc:
        zjyumi.query_matches("某玩家#12345", 1, 20)

    assert exc.value.status_code == 503


def test_code2_becomes_friendly_error(monkeypatch) -> None:
    payload = {
        "code": 2,
        "message": "",
        "data": [
            {
                "titleTime": "这个ID在艾欧尼亚不存在！<br/>可能是由于合区所导致，请输入原ID🌹"
            }
        ],
    }
    monkeypatch.setattr(zjyumi, "_get_json", lambda url, params=None: payload)

    with pytest.raises(zjyumi.ZjPlayerNotFound) as exc:
        zjyumi.query_matches("某玩家#12345", 1, 20)

    text = str(exc.value)
    assert "不存在" in text
    assert "<br" not in text
    assert exc.value.status_code == 400


def test_code6_relogins_and_retries(monkeypatch) -> None:
    tokens = []

    def fake_get(url, params=None):
        tokens.append(params["lzyumitokenstr"])
        if len(tokens) == 1:
            return {"code": 6, "message": "token 失效"}
        return {"code": 1, "data": [{"isWin": 1, "championId": 1}]}

    monkeypatch.setattr(zjyumi, "_get_json", fake_get)
    monkeypatch.setattr(
        zjyumi, "current_token", lambda force_refresh=False: "new" if force_refresh else "old"
    )

    matches, cached = zjyumi.query_matches("某玩家#12345", 1, 20)

    assert tokens == ["old", "new"]
    assert matches == [{"isWin": 1, "championId": 1}]
    assert cached is False


def test_other_codes_stay_502(monkeypatch) -> None:
    monkeypatch.setattr(
        zjyumi, "_get_json", lambda url, params=None: {"code": 9, "message": "系统繁忙"}
    )

    with pytest.raises(zjyumi.ZjUpstreamError) as exc:
        zjyumi.query_matches("某玩家#12345", 1, 20)

    assert "系统繁忙" in str(exc.value)
    assert exc.value.status_code == 502


def test_result_cache_hits_once(monkeypatch) -> None:
    calls = []

    def fake_get(url, params=None):
        calls.append(params["nickname"])
        return {"code": 1, "data": [{"isWin": 1}]}

    monkeypatch.setattr(zjyumi, "_get_json", fake_get)

    first = zjyumi.query_matches("兜兜#45870", 1, 20)
    second = zjyumi.query_matches("兜兜#45870", 1, 20)

    assert first[1] is False
    assert second[1] is True
    assert calls == ["兜兜*~*~*45870"]
