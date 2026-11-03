"""截图识别玩家：调用 DeepSeek 视觉模型，只返回候选，不写业务数据。"""

from __future__ import annotations

import base64
import json
import logging
import time
from collections import deque
from threading import Lock

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import Actor
from app.errors import AppError, RateLimitError
from app.services.ai_matching import (
    clean_name,
    filter_recognized,
    match_players,
)

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PLAYERS = 10
MAX_MODEL_PLAYERS = 20
RATE_LIMIT = 10
RATE_WINDOW_SECONDS = 60

SYSTEM_PROMPT = (
    "你是英雄联盟客户端截图信息提取助手。"
    "只提取截图中真实存在的玩家名，不猜测、不补全、不翻译。"
    "只输出 JSON，不要输出任何解释。"
)

USER_PROMPT = """请读取这张英雄联盟对局截图，提取所有真实玩家名。

规则：
1. 双方队伍都算，只提取玩家名，不提取房间名、段位、胜场、等级、数字、头像文字或按钮文字。
2. 忽略「空」「加入」「邀请」「邀请玩家」「观战者」「队伍1」「队伍2」等界面文字。
3. 保留名字里的中文、英文、数字、符号和尾部标点；不要改写、不要翻译、不要补全。
4. 看不清或不确定的名字不要编造，把 confidence 填低一些。
5. tag 是名字后面的 #1234 部分；截图里没有就填 null。

只返回如下 json 结构：
{"players":[{"name":"玩家名","tag":null,"team":1,"confidence":0.95}]}
"""

_rate_lock = Lock()
_rate_calls: dict[int, deque[float]] = {}


class AiUnavailableError(AppError):
    status_code = 503


class AiTimeoutError(AppError):
    status_code = 504


class AiResponseError(AppError):
    status_code = 502


def reset_rate_limit() -> None:
    with _rate_lock:
        _rate_calls.clear()


def status_payload() -> dict:
    return {
        "enabled": settings.ai_ready,
        "model": settings.ai_model if settings.ai_ready else "",
    }


def _check_rate(user_id: int) -> None:
    now = time.monotonic()
    with _rate_lock:
        calls = _rate_calls.setdefault(user_id, deque())
        while calls and now - calls[0] > RATE_WINDOW_SECONDS:
            calls.popleft()
        if len(calls) >= RATE_LIMIT:
            raise RateLimitError("识别太频繁，请稍后再试")
        calls.append(now)


def _image_mime(content: bytes) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    raise AppError("请上传 jpg、png、webp 或 gif 图片")


def _validate_image(content: bytes) -> str:
    if not content:
        raise AppError("图片是空的")
    if len(content) > MAX_IMAGE_BYTES:
        raise AppError("图片不能超过 5MB")
    return _image_mime(content)


def _parse_model_content(content: str) -> list[dict]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise AiResponseError("AI 返回格式不正确，请手动选人")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AiResponseError("AI 返回格式不正确，请手动选人") from exc

    rows = payload.get("players")
    if not isinstance(rows, list):
        raise AiResponseError("AI 返回格式不正确，请手动选人")

    raw: list[dict] = []
    for row in rows[:MAX_MODEL_PLAYERS]:
        if not isinstance(row, dict):
            continue
        name = clean_name(row.get("name"))
        if not name:
            continue
        raw.append(
            {
                "name": name,
                "tag": row.get("tag"),
                "team": row.get("team"),
                "confidence": row.get("confidence"),
            }
        )
    return filter_recognized(raw)


def _call_model(image_bytes: bytes, mime: str) -> list[dict]:
    if not settings.ai_ready:
        raise AiUnavailableError("AI 识别未启用，请手动选人")

    url = settings.ai_base_url.rstrip("/") + "/chat/completions"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{encoded}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        "temperature": 0,
        "max_tokens": 1200,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key.strip()}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise AiTimeoutError("识别超时，请换一张图或手动选人") from exc
    except httpx.HTTPError as exc:
        logger.warning("AI 请求失败：%s", type(exc).__name__)
        raise AiUnavailableError("AI 服务连接失败，请手动选人") from exc

    if response.status_code in (401, 403):
        logger.error("AI 鉴权失败，请检查 AI_API_KEY")
        raise AiUnavailableError("AI 服务配置有误，请手动选人")
    if response.status_code >= 400:
        logger.warning("AI 服务返回 %s", response.status_code)
        raise AiUnavailableError("AI 服务暂时不可用，请手动选人")

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AiResponseError("AI 返回格式不正确，请手动选人") from exc
    if not isinstance(content, str):
        raise AiResponseError("AI 返回格式不正确，请手动选人")
    return _parse_model_content(content)


def recognize_players(
    session: Session,
    actor: Actor,
    *,
    content: bytes,
) -> dict:
    started = time.monotonic()
    _check_rate(actor.id)
    mime = _validate_image(content)
    recognized = filter_recognized(_call_model(content, mime))

    if not recognized:
        raise AiResponseError("没有识别到玩家，请换一张截图或手动选人")

    warnings: list[str] = []
    if len(recognized) > MAX_PLAYERS:
        warnings.append(
            f"识别到 {len(recognized)} 个名字，超过 {MAX_PLAYERS} 人，只保留前 {MAX_PLAYERS} 个"
        )
        recognized = recognized[:MAX_PLAYERS]
    elif len(recognized) != MAX_PLAYERS:
        warnings.append(f"识别到 {len(recognized)} 个玩家，请确认是否完整")

    items = match_players(session, actor, recognized)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "AI 识别完成 merchant=%s user=%s count=%s elapsed=%sms",
        actor.merchant_id,
        actor.id,
        len(items),
        elapsed_ms,
    )
    return {
        "items": items,
        "count": len(items),
        "warnings": warnings,
        "elapsed_ms": elapsed_ms,
    }
