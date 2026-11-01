"""路由汇总。所有业务接口统一挂在 /api/v1 下。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    ai,
    auth,
    batches,
    deposits,
    overview,
    players,
    records,
    sessions,
    settings as settings_api,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(players.router)
api_router.include_router(deposits.router)
api_router.include_router(batches.router)
api_router.include_router(sessions.router)
api_router.include_router(records.router)
api_router.include_router(overview.router)
api_router.include_router(settings_api.router)
api_router.include_router(ai.router)
