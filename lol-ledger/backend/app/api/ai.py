"""AI 截图识别玩家。只返回候选，不写任何业务数据。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.deps import Actor, get_current_user, get_read_db
from app.schemas import AiRecognizeOut, AiStatusOut
from app.services import ai_recognition

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/status", response_model=AiStatusOut)
def ai_status(_: Actor = Depends(get_current_user)) -> dict:
    return ai_recognition.status_payload()


@router.post("/recognize-players", response_model=AiRecognizeOut)
def recognize_players(
    file: UploadFile = File(...),
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    content = file.file.read(ai_recognition.MAX_IMAGE_BYTES + 1)
    return ai_recognition.recognize_players(
        session,
        actor,
        content=content,
    )
