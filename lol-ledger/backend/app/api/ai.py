"""AI 识别玩家：这一期只占位，下一期接视觉模型。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import Actor, get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/recognize-players", status_code=501)
def recognize_players(_: Actor = Depends(get_current_user)) -> dict:
    raise HTTPException(status_code=501, detail="AI 识别玩家即将上线，先手动选人")
