"""上游战绩接口客户端（lzyumi 站点）。

只由后端调用，用户侧完全接触不到上游地址、账号与 token：
- 时间签名在服务端生成（固定按 UTC+8，不依赖服务器本地时区）；
- token 进程内缓存，快过期或上游返回 code=6 时用 .env 里的账号密码自动重登并重试一次；
- 全局串行限速（跨用户共享），避免付费 token 被上游风控；
- 短 TTL 结果缓存，压掉同一批里重复粘贴同一人的请求。
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings
from app.errors import AppError

logger = logging.getLogger(__name__)

# 北京时间：上游按本机时间校验签名，服务器时区不确定，这里固定 UTC+8。
CN_TZ = timezone(timedelta(hours=8), "CST")

REQUEST_TIMEOUT_SECONDS = 15.0
TOKEN_CHECK_SECONDS = 300.0
CACHE_MAX_ENTRIES = 500
MAX_ATTEMPTS = 2

# areaId -> 大区名（与客户端一致，上游要求两个参数同时给）
AREAS: dict[int, str] = {
    1: "艾欧尼亚",
    2: "比尔吉沃特",
    3: "祖安",
    4: "诺克萨斯",
    5: "班德尔城",
    6: "德玛西亚",
    7: "皮尔特沃夫",
    8: "战争学院",
    9: "弗雷尔卓德",
    10: "巨神峰",
    11: "雷瑟守备",
    12: "无畏先锋",
    13: "裁决之地",
    14: "黑色玫瑰",
    15: "暗影岛",
    16: "恕瑞玛",
    17: "钢铁烈阳",
    18: "水晶之痕",
    19: "均衡教派",
    20: "扭曲丛林",
    21: "教育网专区",
    22: "影流",
    30: "男爵领域",
    31: "峡谷之巅",
}


class ZjUpstreamError(AppError):
    """上游业务或连接异常，统一 502，不把原始细节抛给前端。"""

    status_code = 502


class ZjUpstreamTimeout(AppError):
    status_code = 504


class ZjNotConfigured(AppError):
    status_code = 503


class ZjPlayerNotFound(AppError):
    """上游 code=2：ID 不存在/合区/名字不对，属于用户可修正的错误，不是服务故障。"""

    status_code = 400


_TAG_RE = re.compile(r"<[^>]+>")


def _extract_hint(payload: dict[str, Any]) -> str:
    """上游把「这个ID在xx不存在」塞在 data[0] 的文本字段里，去掉 HTML 标签再给前端。"""
    data = payload.get("data")
    items = data if isinstance(data, list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("titleTime", "info", "title", "message"):
            raw = item.get(key)
            if not raw:
                continue
            text = _TAG_RE.sub(" ", str(raw))
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return text[:80]
    return ""


def area_name(area_id: int) -> str:
    return AREAS.get(int(area_id), AREAS[1])


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_sign(now: datetime | None = None) -> tuple[str, str]:
    """返回 (lzyumiSign, signStr)，算法与前端页面完全一致。

    lzyumiSign = md5("d"+MM+"o"+DD+"u"+HH+"d"+mm+"o"+ss+"d")，各段补零到两位；
    signStr   = 不补零的 MM+DD+HH+mm+ss + 每段十进制长度的 3 倍。
    """
    moment = (now or datetime.now(CN_TZ)).astimezone(CN_TZ)
    parts = [moment.month, moment.day, moment.hour, moment.minute, moment.second]
    pairs = [f"{value:02d}" for value in parts]
    sign_source = (
        f"d{pairs[0]}o{pairs[1]}u{pairs[2]}d{pairs[3]}o{pairs[4]}d"
    )
    sign_str = "".join(str(value) for value in parts) + "".join(
        str(len(str(value)) * 3) for value in parts
    )
    return md5_hex(sign_source), sign_str


# ---------------- 进程内状态（token / 限速 / 缓存） ----------------

_state_lock = threading.Lock()
_token: dict[str, Any] = {"value": "", "end_time": "", "checked_at": 0.0}

_pace_lock = threading.Lock()
_last_call_at = 0.0

_cache_lock = threading.Lock()
_cache: OrderedDict[tuple[str, int, int], tuple[float, list[dict[str, Any]]]] = OrderedDict()


def reset_state() -> None:
    """测试与排障用：清空 token、限速计时与结果缓存。"""
    global _last_call_at
    with _state_lock:
        _token.update({"value": "", "end_time": "", "checked_at": 0.0})
    with _pace_lock:
        _last_call_at = 0.0
    with _cache_lock:
        _cache.clear()


def is_configured() -> bool:
    return settings.lzyumi_ready


def _base_url() -> str:
    return settings.lzyumi_base_url.rstrip("/")


def _require_config() -> None:
    if not settings.lzyumi_ready:
        raise ZjNotConfigured("查战绩服务未配置，请联系管理员")


def _pace() -> None:
    """全局串行限速：跨用户共享，保证两次上游调用间隔不小于配置值。"""
    global _last_call_at
    interval = max(float(settings.zj_min_interval_seconds), 0.0)
    with _pace_lock:
        if interval > 0 and _last_call_at:
            wait = _last_call_at + interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        _last_call_at = time.monotonic()


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json, text/plain, */*"}
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.get(url, params=params, headers=headers)
    except httpx.TimeoutException as exc:
        raise ZjUpstreamTimeout("上游查询超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        raise ZjUpstreamError("上游服务连接失败，请稍后重试") from exc

    if response.status_code != 200:
        raise ZjUpstreamError(f"上游服务异常（HTTP {response.status_code}）")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ZjUpstreamError("上游返回格式异常，请稍后重试") from exc
    if not isinstance(payload, dict):
        raise ZjUpstreamError("上游返回格式异常，请稍后重试")
    return payload


def _token_is_valid(token: str) -> tuple[bool, str]:
    """调 /tokenIsSucc 校验，返回 (是否有效, 到期时间)。网络异常按无效处理。"""
    try:
        payload = _get_json(
            f"{_base_url()}/tokenIsSucc",
            {"lzyumitokenstrinfo": token},
        )
    except AppError as exc:
        logger.warning("上游 token 校验失败：%s", exc)
        return False, ""
    data = payload.get("data") or {}
    end_time = str(data.get("endTime") or "")
    if payload.get("code") in (1, 2) and end_time:
        return True, end_time
    return False, ""


def _login() -> str:
    user = settings.lzyumi_user.strip()
    password = settings.lzyumi_pwd.strip()
    if not (user and password):
        raise ZjNotConfigured("查战绩服务未配置登录账号，请联系管理员")
    payload = _get_json(
        f"{_base_url()}/login",
        {"name": user, "pwd": md5_hex(f"dou{user}{password}dou"), "type": 2},
    )
    data = payload.get("data") or {}
    token = str(data.get("token") or "")
    if payload.get("code") != 1 or not token:
        message = str(payload.get("message") or f"code={payload.get('code')}")
        logger.error("上游账号登录失败：%s", message)
        raise ZjUpstreamError("上游账号登录失败，请联系管理员")
    end_time = str(data.get("endTime") or "")
    logger.info("上游 token 已重新获取，到期时间 %s", end_time or "未知")
    return token


def _refresh_token() -> str:
    token = _login()
    with _state_lock:
        _token.update(
            {"value": token, "end_time": "", "checked_at": time.monotonic()}
        )
    return token


def current_token(force_refresh: bool = False) -> str:
    """取可用 token。首次使用或缓存过期会校验，失效则自动重登。

    校验与登录都在锁外执行，避免一次网络抖动把其他用户一起卡住。
    """
    _require_config()
    if force_refresh:
        with _state_lock:
            _token.update({"value": "", "checked_at": 0.0})
        return _refresh_token()

    with _state_lock:
        cached = str(_token["value"])
        fresh = bool(cached) and (
            time.monotonic() - float(_token["checked_at"]) < TOKEN_CHECK_SECONDS
        )
    if fresh:
        return cached

    configured = settings.lzyumi_token.strip()
    if configured:
        valid, end_time = _token_is_valid(configured)
        if valid:
            with _state_lock:
                _token.update(
                    {
                        "value": configured,
                        "end_time": end_time,
                        "checked_at": time.monotonic(),
                    }
                )
            return configured
        with _state_lock:
            _token.update({"value": "", "end_time": "", "checked_at": 0.0})
        if not (settings.lzyumi_user.strip() and settings.lzyumi_pwd.strip()):
            raise ZjUpstreamError("上游 token 已失效，请联系管理员")
    return _refresh_token()


def _cache_get(key: tuple[str, int, int]) -> list[dict[str, Any]] | None:
    ttl = int(settings.zj_cache_ttl_seconds)
    if ttl <= 0:
        return None
    with _cache_lock:
        hit = _cache.get(key)
        if hit is None:
            return None
        saved_at, value = hit
        if time.monotonic() - saved_at > ttl:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return value


def _cache_put(key: tuple[str, int, int], value: list[dict[str, Any]]) -> None:
    if int(settings.zj_cache_ttl_seconds) <= 0:
        return
    with _cache_lock:
        _cache[key] = (time.monotonic(), value)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)


def _request_matches(nickname: str, area_id: int, all_count: int) -> list[dict[str, Any]]:
    params_base = {
        "nickname": nickname.replace("#", "*~*~*"),
        "allCount": str(all_count),
        "areaId": str(area_id),
        "areaName": area_name(area_id),
        "seleMe": "1",
        "filter": "1",
        "modelId": "1",
        "openId": "",
    }
    last_error: AppError | None = None
    for attempt in range(MAX_ATTEMPTS):
        token = current_token(force_refresh=attempt > 0)
        sign, sign_str = build_sign()
        params = dict(params_base)
        params.update(
            {
                "lzyumiSign": sign,
                "signStr": sign_str,
                "lzyumitokenstr": token,
            }
        )
        _pace()
        payload = _get_json(_base_url(), params)
        code = int(payload.get("code") or 0)
        if code == 1:
            data = payload.get("data") or []
            return [item for item in data if isinstance(item, dict)]
        if code == 6 and attempt + 1 < MAX_ATTEMPTS:
            logger.warning("上游 token 失效（code=6），尝试重新登录后重试")
            continue
        if code == 2:
            hint = _extract_hint(payload)
            logger.info("上游未查到玩家：%s（%s）", nickname, hint or "无提示")
            raise ZjPlayerNotFound(
                f"未查到这名玩家：{hint}" if hint else "未查到这名玩家，检查昵称和编号是否正确"
            )
        message = str(payload.get("message") or "").strip()
        last_error = ZjUpstreamError(
            f"上游查询失败：{message}" if message else "上游查询失败，请稍后重试"
        )
    raise last_error or ZjUpstreamError("上游查询失败，请稍后重试")


def query_matches(
    nickname: str, area_id: int, all_count: int
) -> tuple[list[dict[str, Any]], bool]:
    """查一个玩家的对局列表，返回 (原始对局数组, 是否命中缓存)。"""
    _require_config()
    key = (nickname, int(area_id), int(all_count))
    cached = _cache_get(key)
    if cached is not None:
        return cached, True
    matches = _request_matches(nickname, int(area_id), int(all_count))
    _cache_put(key, matches)
    return matches, False
