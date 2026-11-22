"""路由汇总。所有业务接口统一挂在 /api/v1 下。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    ai,
    auth,
    deposits,
    dividends,
    overview,
    platform,
    players,
    queue,
    records,
    salary,
    sessions,
    settings as settings_api,
    summary,
    tool_lists,
    users,
    zj,
    zj_admin,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(platform.router)
api_router.include_router(users.router)
api_router.include_router(dividends.router)
api_router.include_router(players.router)
api_router.include_router(deposits.router)
api_router.include_router(sessions.router)
api_router.include_router(summary.router)
api_router.include_router(salary.router)
api_router.include_router(records.router)
api_router.include_router(overview.router)
api_router.include_router(queue.router)
api_router.include_router(tool_lists.router)
api_router.include_router(settings_api.router)
api_router.include_router(ai.router)
api_router.include_router(zj.router)
api_router.include_router(zj_admin.router)
